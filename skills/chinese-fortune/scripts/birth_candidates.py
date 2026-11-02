"""跨日期或多个候选出生时间: 哪几柱不变、哪几柱会变、各自牵动哪些结论.

birth_interval.py 只核同一天内的钟面范围; 用户说「可能是 3 月 5 日深夜，也可能是
6 日凌晨」或给出几个互不相连的时刻时, 由这里处理。范围每 30 分钟取样, 相邻两样
四柱不同就二分到分钟, 得到每一段的四柱; 不猜哪一段是真的。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone

from bazi_calc import _apply_birthplace, _ChartError, calculate_bazi
from bazi_calc import build_parser as bazi_parser
from utils import (
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    normalize_birth_time,
    ok_envelope,
    validate_birth_input,
)

PILLARS = ('year', 'month', 'day', 'hour')
NAMES = {'year': '年柱', 'month': '月柱', 'day': '日柱', 'hour': '时柱'}
# What a change in each pillar takes with it; the reading must be done once per candidate.
AFFECTS = {
    'year': ['年柱与生肖', '大运顺逆（阳男阴女顺、阴男阳女逆，看年干阴阳）', '择日相主（出生年干支）', '年支神煞'],
    'month': ['月令与格局取用', '大运干支序列与起运岁数', '调候（按月令）'],
    'day': ['日主', '全部十神', '格局与喜忌判断', '合婚的日主互见'],
    'hour': ['时柱与时干十神', '起运时刻（只差几天到几个月）'],
}
STEP = timedelta(minutes=30)
LIMIT = timedelta(hours=72)
BIRTH_FIELDS = ('year', 'month', 'day', 'hour', 'minute', 'gender', 'lunar', 'leap', 'timezone', 'longitude', 'city',
                'time_standard', 'sect', 'fold')
BIRTH_SETTINGS = ('gender', 'timezone', 'longitude', 'city', 'time_standard', 'sect', 'fold')


class BirthInputError(ValueError):
    """A rejected external field, shared by the two birth JSON entry points."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f'{field}：{message}')
        self.field = field


def birth_arguments(birth: object, field: str) -> argparse.Namespace:
    """Validate supplied identity and options before applying optional parser defaults."""
    if not isinstance(birth, dict):
        raise BirthInputError(field, '需要出生资料对象')
    unknown = set(birth) - set(BIRTH_FIELDS)
    if unknown:
        raise BirthInputError(field, f"不认识的字段：{'、'.join(sorted(unknown))}")
    for key in ('year', 'month', 'day', 'gender'):
        if key not in birth or birth[key] is None:
            raise BirthInputError(f'{field}.{key}', '必须明确提供，不能从示例生日补入')
    for key in ('year', 'month', 'day', 'hour', 'minute', 'sect', 'fold'):
        if key in birth and not (key in ('hour', 'fold') and birth[key] is None) and type(birth[key]) is not int:
            raise BirthInputError(f'{field}.{key}', '须为整数，不接受布尔值或数字字符串')
    choices = {'gender': ('male', 'female'), 'sect': (1, 2), 'fold': (None, 0, 1),
               'time_standard': ('true-solar', 'clock')}
    for key, allowed in choices.items():
        if key in birth and birth[key] not in allowed:
            raise BirthInputError(f'{field}.{key}', f'须为 {allowed} 中的一个值')
    for key in ('lunar', 'leap'):
        if key in birth and type(birth[key]) is not bool:
            raise BirthInputError(f'{field}.{key}', '须为 true 或 false')
    for key in ('city', 'timezone'):
        if key in birth and birth[key] is not None and (not isinstance(birth[key], str) or not birth[key].strip()):
            raise BirthInputError(f'{field}.{key}', '须为非空字符串或 null')
    longitude = birth.get('longitude')
    if longitude is not None and (type(longitude) not in (int, float) or not -180 <= longitude <= 180
                                  or not math.isfinite(longitude)):
        raise BirthInputError(f'{field}.longitude', '须为 -180..180 的有限数')
    values = dict(birth)
    lunar, leap, month = values.get('lunar', False), values.pop('leap', None), values['month']
    if not lunar and (leap or month < 0):
        raise BirthInputError(f'{field}.month' if month < 0 else f'{field}.leap', '公历日期不能指定闰月')
    if lunar and month < 0 and leap is False:
        raise BirthInputError(f'{field}.leap', '负月份已表示闰月，与 leap=false 冲突')
    if lunar and leap:
        values['month'] = -abs(month)
    invalid = validate_birth_input(values['year'], values['month'], values['day'],
                                   values.get('hour'), values.get('minute', 0), lunar=lunar)
    if invalid:
        raise BirthInputError(field, invalid)
    args = bazi_parser(diagnostics=False).parse_args([
        '--year', str(values['year']), '--month', str(values['month']), '--day', str(values['day']),
        '--gender', values['gender'],
    ])
    vars(args).update(values)
    return args


def canonical_birth(args: argparse.Namespace) -> dict:
    """One replay form uses a signed lunar month and the effective optional defaults."""
    return {key: getattr(args, key) for key in BIRTH_FIELDS if key != 'leap'}


def calculation_context(chart: dict) -> dict:
    """Keep actual chart resolution distinct from the caller's replay settings."""
    settings = {key: chart['input'][key] for key in BIRTH_SETTINGS}
    resolved_zone = chart['timezone']
    return {'effective_settings': settings, 'birthplace': chart['birthplace'], 'timezone': resolved_zone,
            'offset_hours': resolved_zone['offset_hours'] if resolved_zone else chart['input']['tz'],
            'fold': resolved_zone['fold'] if resolved_zone else None,
            'hour_known': chart['hour_known'], 'solar_date': chart['solar_date'],
            'true_solar_time': chart['true_solar_time'], 'calendar_context': chart['calendar_context']}


def _parse(value: object, field: str = 'time') -> datetime:
    if not isinstance(value, str) or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}', value) is None:
        raise BirthInputError(field, '只接受当地钟面分钟 YYYY-MM-DDTHH:MM；不要附 Z、UTC 偏移、秒或日期简写')
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise BirthInputError(field, f'时间须为真实存在的 YYYY-MM-DDTHH:MM：{value}') from exc


def _chart(base: dict, moment: datetime, field: str = 'range') -> dict:
    values = {**base, 'year': moment.year, 'month': moment.month, 'day': moment.day,
              'hour': moment.hour, 'minute': moment.minute}
    chart = calculate_bazi(argparse.Namespace(**values))
    if not chart.get('ok'):
        raise BirthInputError(field, f"{moment:%Y-%m-%d %H:%M} 排盘失败 [{chart.get('error')}]：{chart.get('message')}")
    return chart


def _key(chart: dict) -> tuple[str, ...]:
    return tuple(chart['four_pillars'][p]['ganzhi'] for p in PILLARS)


def _boundary(base: dict, lo: datetime, hi: datetime, lo_key: tuple) -> datetime:
    """First minute in (lo, hi] whose pillars differ from lo_key."""
    while hi - lo > timedelta(minutes=1):
        mid = lo + timedelta(minutes=((hi - lo).total_seconds() // 60) // 2)
        if _key(_chart(base, mid)) == lo_key:
            lo = mid
        else:
            hi = mid
    return hi


def _segment(moment_from: datetime, moment_to: datetime, chart: dict) -> dict:
    qi = chart.get('qi_yun') or {}
    return {'from': f'{moment_from:%Y-%m-%dT%H:%M}', 'to': f'{moment_to:%Y-%m-%dT%H:%M}',
            'four_pillars': dict(zip(PILLARS, _key(chart))),
            'day_master': chart['day_master'].get('stem'),
            'qi_yun_start': qi.get('start_calendar_datetime'),
            'qi_yun_basis': 'segment_start_only', 'sampled_at': f'{moment_from:%Y-%m-%dT%H:%M}',
            'qi_yun_note': '起运时刻只对应本段起点；四柱相同不表示段内起运时刻、各步年龄与年份相同。',
            'da_yun': [c['ganzhi'] for c in chart.get('da_yun', [])[:3]],
            'calculation_context': calculation_context(chart)}


def _validate_range(base: dict, start: datetime, end: datetime) -> None:
    if end < start:
        raise BirthInputError('range.end', '结束时间早于开始时间')
    if end - start > LIMIT:
        raise BirthInputError('range', '范围超过 72 小时；请先缩小到最可能的几天，或改给离散候选')
    resolved = argparse.Namespace(**base)
    try:
        _apply_birthplace(resolved)
    except _ChartError as exc:
        raise BirthInputError('birth.city', str(exc)) from exc
    previous: datetime | None = None
    first_offset: float | None = None
    moment = start
    while moment <= end:
        try:
            normalized = normalize_birth_time(moment.year, moment.month, moment.day, moment.hour, moment.minute,
                                               resolved.longitude, resolved.tz, resolved.timezone,
                                               resolved.fold, resolved.time_standard)
        except ValueError as exc:
            raise BirthInputError('range', f'{exc}；请明确 fold 并拆分为有效且偏移恒定的范围，或改给有效离散候选') from exc
        zone = normalized['timezone']
        offset = zone['offset_hours'] if zone else resolved.tz
        instant = moment.replace(tzinfo=timezone(timedelta(hours=offset))).astimezone(timezone.utc)
        if previous is not None and (offset != first_offset or instant - previous != timedelta(minutes=1)):
            raise BirthInputError('range', f'{moment:%Y-%m-%dT%H:%M} 跨越时区偏移变化；'
                                  '请拆分为偏移恒定的范围，或改给有效离散候选')
        first_offset, previous = offset, instant
        moment += timedelta(minutes=1)


def scan_range(base: dict, start: datetime, end: datetime) -> list[dict]:
    _validate_range(base, start, end)
    segments, cursor = [], start
    chart = _chart(base, cursor)
    seg_start = cursor
    while cursor < end:
        nxt = min(cursor + STEP, end)
        probe = _chart(base, nxt)
        if _key(probe) != _key(chart):
            change = _boundary(base, cursor, nxt, _key(chart))
            segments.append(_segment(seg_start, change - timedelta(minutes=1), chart))
            seg_start, chart = change, _chart(base, change)
            if change < nxt and _key(_chart(base, nxt)) != _key(chart):
                cursor = change    # a second boundary inside the same half hour
                continue
        cursor = nxt
    segments.append(_segment(seg_start, end, chart))
    return segments


def _runs(segments: list[dict], pillar: str) -> list[tuple[str, str, str]]:
    """Consecutive segments with the same value of one pillar, merged."""
    runs: list[list[str]] = []
    for seg in segments:
        value = seg['four_pillars'][pillar]
        if runs and runs[-1][2] == value:
            runs[-1][1] = seg['to']
        else:
            runs.append([seg['from'], seg['to'], value])
    return [(a, b, v) for a, b, v in runs]


def compare(segments: list[dict]) -> dict:
    by_pillar = {p: list(dict.fromkeys(s['four_pillars'][p] for s in segments)) for p in PILLARS}
    fixed = {p: v[0] for p, v in by_pillar.items() if len(v) == 1}
    varying = {p: v for p, v in by_pillar.items() if len(v) > 1}
    say = []
    if fixed:
        say.append('干支不变：' + '、'.join(f'{NAMES[p]}{v}' for p, v in fixed.items())
                   + '；只表示这些柱的干支相同，十神与格局仍须结合日主及其他变化柱分别核对。')
    for p, values in varying.items():
        spans = '；'.join(f"{a.replace('T', ' ')} 至 {b.replace('T', ' ')} 为{v}" for a, b, v in _runs(segments, p))
        say.append(f"{NAMES[p]}会变（{'、'.join(values)}）：{spans}。牵动{'、'.join(AFFECTS[p])}，要按每个候选分别解读。")
    if not varying:
        say.append('四柱干支在所列候选范围内都不变；起运时刻与各步大运起止年龄、年份仍可能变化，不能据此选定真实生时。')
    return {'fixed': fixed, 'varying': varying,
            'affects': {p: AFFECTS[p] for p in varying}, 'say': say}


def run(request: object) -> dict:
    if not isinstance(request, dict):
        raise BirthInputError('request', '需要 JSON 对象')
    unknown = set(request) - {'birth', 'range', 'candidates'}
    if unknown:
        raise BirthInputError('request', f"不认识的字段：{'、'.join(sorted(unknown))}")
    birth = request.get('birth')
    if not isinstance(birth, dict):
        raise BirthInputError('birth', '需要出生设置对象及 birth.gender（male/female）')
    unknown = set(birth) - set(BIRTH_SETTINGS)
    if unknown:
        raise BirthInputError('birth', f"不认识的字段：{'、'.join(sorted(unknown))}；年月日时分由候选时间提供")
    if ('range' in request) == ('candidates' in request):
        raise BirthInputError('request', '只能给 range 或 candidates 中的一种')
    if 'range' in request:
        rng = request['range']
        if not isinstance(rng, dict) or set(rng) != {'start', 'end'}:
            raise BirthInputError('range', '须为仅含 start 与 end 的对象')
        moments = [_parse(rng['start'], 'range.start'), _parse(rng['end'], 'range.end')]
        mode = 'range'
    elif isinstance(request.get('candidates'), list) and 2 <= len(request['candidates']) <= 12:
        moments = sorted(_parse(c, f'candidates[{i}]') for i, c in enumerate(request['candidates']))
        mode = 'candidates'
    else:
        raise BirthInputError('candidates', '给 2–12 个 YYYY-MM-DDTHH:MM 当地钟面候选')
    first = moments[0]
    args = birth_arguments({**birth, 'year': first.year, 'month': first.month, 'day': first.day,
                            'hour': first.hour, 'minute': first.minute}, 'birth')
    base = vars(args)
    canonical = {key: base[key] for key in BIRTH_SETTINGS}
    replay: dict
    if mode == 'range':
        segments = scan_range(base, *moments)
        replay = {'birth': canonical, 'range': {'start': moments[0].strftime('%Y-%m-%dT%H:%M'),
                                               'end': moments[1].strftime('%Y-%m-%dT%H:%M')}}
    else:
        segments = [_segment(m, m, _chart(base, m, f'candidates[{i}]')) for i, m in enumerate(moments)]
        replay = {'birth': canonical, 'candidates': [m.strftime('%Y-%m-%dT%H:%M') for m in moments]}
    context = segments[0]['calculation_context']
    return ok_envelope('birth_candidates', {
        'input': replay, 'method': 'bazi-candidate-pillars',
        'time_context': {'source': 'birth_local_minutes', 'precision': 'minute',
                         'time_standard': base['time_standard'], 'sect': base['sect'], 'fold': base['fold'],
                         'timezone': context['effective_settings']['timezone'] or 'UTC+08:00',
                         'range_endpoints': 'inclusive', 'calculation_context': 'segments[].calculation_context',
                         'range_preflight': 'every_local_minute_constant_offset' if mode == 'range' else None},
        'mode': mode, 'segments': segments, **compare(segments),
        'boundary': '只列各候选的四柱与受影响的结论，不判断哪一个才是真实出生时间；不要拿「哪张更像」去校准时辰。',
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='跨日期或多个候选出生时间：哪几柱不变、哪几柱会变、各自牵动哪些结论',
        epilog='stdin JSON: {"birth": {"gender", "timezone"?, "longitude"|"city"?, "time_standard"?, "sect"?, "fold"?}, '
               '"range": {"start": "YYYY-MM-DDTHH:MM", "end": ...} | "candidates": [...]}. '
               '仅接受当地钟面分钟，不接受 UTC 偏移或秒；range 含首尾，最长 72 小时且须保持时区偏移恒定。'
               'Top-level JSON keys: ok tool version input method time_context mode segments fixed varying affects say boundary; '
               'errors: ok=false error message field.')
    p.add_argument('--stdin', action='store_true', required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    build_parser().parse_args(argv)
    try:
        result = run(json.loads(sys.stdin.read()))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        json_print(error_envelope('birth_candidates', 'invalid_request', str(exc), field=getattr(exc, 'field', 'request')))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
