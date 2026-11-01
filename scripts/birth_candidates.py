"""跨日期或多个候选出生时间: 哪几柱不变、哪几柱会变、各自牵动哪些结论.

birth_interval.py 只核同一天内的钟面范围; 用户说「可能是 3 月 5 日深夜，也可能是
6 日凌晨」或给出几个互不相连的时刻时, 由这里处理。范围每 30 分钟取样, 相邻两样
四柱不同就二分到分钟, 得到每一段的四柱; 不猜哪一段是真的。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from bazi_calc import build_parser as bazi_parser
from bazi_calc import calculate_bazi
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

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


def _parse(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'时间须为 YYYY-MM-DDTHH:MM：{value}') from exc


def _chart(base: dict, moment: datetime) -> dict:
    values = {**base, 'year': moment.year, 'month': moment.month, 'day': moment.day,
              'hour': moment.hour, 'minute': moment.minute}
    chart = calculate_bazi(argparse.Namespace(**values))
    if not chart.get('ok'):
        raise ValueError(f"{moment:%Y-%m-%d %H:%M} 排盘失败：{chart.get('message')}")
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
            'da_yun': [c['ganzhi'] for c in chart.get('da_yun', [])[:3]]}


def scan_range(base: dict, start: datetime, end: datetime) -> list[dict]:
    if end < start:
        raise ValueError('结束时间早于开始时间')
    if end - start > LIMIT:
        raise ValueError('范围超过 72 小时；请先缩小到最可能的几天，或改给离散候选')
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
        say.append('不变：' + '、'.join(f'{NAMES[p]}{v}' for p, v in fixed.items()) + '，这几柱的结论各候选相同。')
    for p, values in varying.items():
        spans = '；'.join(f"{a.replace('T', ' ')} 至 {b.replace('T', ' ')} 为{v}" for a, b, v in _runs(segments, p))
        say.append(f"{NAMES[p]}会变（{'、'.join(values)}）：{spans}。牵动{'、'.join(AFFECTS[p])}，要按每个候选分别解读。")
    if not varying:
        say.append('四柱在整个范围内都不变，解读不受出生时间不确定影响（起运时刻仍可能有几天差别）。')
    return {'fixed': fixed, 'varying': varying,
            'affects': {p: AFFECTS[p] for p in varying}, 'say': say}


def run(request: dict) -> dict:
    birth = request.get('birth')
    if not isinstance(birth, dict) or birth.get('gender') not in ('male', 'female'):
        raise ValueError('需要 birth.gender（male/female）')
    defaults = vars(bazi_parser().parse_args(['--year', '2000', '--month', '1', '--day', '1', '--gender', 'male']))
    base = {**defaults, 'no_shensha': True, 'no_geju': True, 'no_yongshen': True,
            **{k: birth[k] for k in ('gender', 'timezone', 'longitude', 'city', 'time_standard', 'sect') if k in birth}}
    if 'range' in request:
        rng = request['range']
        segments = scan_range(base, _parse(rng.get('start')), _parse(rng.get('end')))
        mode = 'range'
    elif isinstance(request.get('candidates'), list) and 2 <= len(request['candidates']) <= 12:
        moments = sorted(_parse(c) for c in request['candidates'])
        segments = [_segment(m, m, _chart(base, m)) for m in moments]
        mode = 'candidates'
    else:
        raise ValueError('给 range {"start","end"}（YYYY-MM-DDTHH:MM，最长 72 小时）或 2–12 个 candidates')
    return ok_envelope('birth_candidates', {
        'mode': mode, 'segments': segments, **compare(segments),
        'boundary': '只列各候选的四柱与受影响的结论，不判断哪一个才是真实出生时间；不要拿「哪张更像」去校准时辰。',
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='跨日期或多个候选出生时间：哪几柱不变、哪几柱会变、各自牵动哪些结论',
        epilog='stdin JSON: {"birth": {"gender", "timezone", "longitude"|"city", "time_standard"?, "sect"?}, '
               '"range": {"start": "YYYY-MM-DDTHH:MM", "end": ...} | "candidates": [...]}. '
               'Top-level JSON keys: ok tool version mode segments fixed varying affects say boundary; '
               'errors: ok=false error message.')
    p.add_argument('--stdin', action='store_true', required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    build_parser().parse_args(argv)
    try:
        result = run(json.loads(sys.stdin.read()))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        json_print(error_envelope('birth_candidates', 'invalid_request', str(exc)))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
