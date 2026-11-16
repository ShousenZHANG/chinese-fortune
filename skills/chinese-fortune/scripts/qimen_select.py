"""奇门择时：在一段日子里逐时辰排《遁甲演义》转盘，列出有吉格、又不犯原文禁忌的时辰。

只用原文写明的条件筛：
- 候选：该时辰有九遁、吉格、诈假的正条（「又曰」异说另列，不单独成候选）。
- 整个时辰不用：五不遇时「縱有竒門不可行」（dunjia:c002:p0041）；三奇入墓与时干入墓「縱有竒門不可舉兵」
  「亦不可用」（p0042）；六仪击刑「其時極凶不可用事」（p0043）；伏吟反吟「雖得竒不可用」（p0045）。
- 吉格所在宫门迫的不算：天遁条「亦不可犯竒墓門迫」（p0003）。
- 三奇得使兼成青龙逃走、荧入太白、朱雀投江时，本旬直符同临才可用（p0009「如遇本旬直符同臨其上方可用之」），
  否则不算吉格；其他吉格所在宫兼成凶格的保留，标「有微疵」。
不看个人八字；候选按时间先后列，彼此不分高下。

CLI:
    python qimen_select.py --from 2026-11-02 --days 3 --target-timezone Asia/Shanghai
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qimen_cast import dunjia_futou
from qimen_dingju import solar_term_boundaries
from qimen_patterns import NOT_COMPUTED
from qimen_tables import PALACE_INFO
from utils import UTC, __version__, ensure_utf8_stdio, error_envelope, json_print, require_lunar

MAX_DAYS = 31
EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version method input candidates excluded excluded_windows skipped_dates
  interval_convention rules patterns_not_computed say

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""
GOOD = ('九遁', '吉格', '诈假')
SLOT_VETO = {'五不遇时': 'dunjia:c002:p0041', '三奇入墓': 'dunjia:c002:p0042', '时干入墓': 'dunjia:c002:p0042',
             '六仪击刑': 'dunjia:c002:p0043', '伏吟': 'dunjia:c002:p0045', '反吟': 'dunjia:c002:p0045'}
RULES = [
    '候选：九遁、吉格、诈假正条；异说另列（dunjia:c002 各条）',
    '整时不用：五不遇时 p0041、三奇入墓与时干入墓 p0042、六仪击刑 p0043、伏吟反吟 p0045',
    '吉格所在宫门迫不算（p0003「亦不可犯竒墓門迫」）',
    '三奇得使兼成凶格而本旬直符未同临的不算吉格（p0009「如遇本旬直符同臨其上方可用之」）',
    '其他吉格所在宫兼成凶格者保留并标微疵',
]


@dataclass(frozen=True)
class _Window:
    start_utc: datetime
    end_utc: datetime
    boundary_reasons: tuple[str, ...]


def _windows(start: date, days: int, zone: ZoneInfo) -> tuple[_Window, ...]:
    """Partition actual instants in the requested civil dates, including gaps and folds."""
    end = start + timedelta(days=days)
    lower = datetime(start.year, start.month, start.day, tzinfo=UTC) - timedelta(days=1)
    upper = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
    cuts: dict[datetime, set[str]] = {lower: {'search_limit'}, upper: {'search_limit'}}
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        for hour in (0, *range(1, 24, 2)):
            wall = datetime(day.year, day.month, day.day, hour)
            for fold in (0, 1):
                instant = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
                if instant.astimezone(zone).replace(tzinfo=None) == wall:
                    cuts.setdefault(instant, set()).add('local_midnight' if hour == 0 else 'double_hour')

    # 时区切换点：逐时探针发现偏移变化后二分精化到秒（与
    # fortune_time.civil_boundaries 同款）。旧实现逐秒扫全程，33 天要
    # ~285 万次 astimezone；TZif 转换点秒级对齐且转换不会在一小时内
    # 往返，逐时探针的端点差必能捕获每一次切换，结果相同、耗时毫秒级。
    cursor = lower
    while cursor < upper:
        probe = min(cursor + timedelta(hours=1), upper)
        if cursor.astimezone(zone).utcoffset() != probe.astimezone(zone).utcoffset():
            lo, hi = cursor, probe
            while (hi - lo).total_seconds() > 1:
                mid = lo + timedelta(seconds=int((hi - lo).total_seconds() // 2))
                if lo.astimezone(zone).utcoffset() == mid.astimezone(zone).utcoffset():
                    lo = mid
                else:
                    hi = mid
            cuts.setdefault(hi, set()).add('timezone_transition')
            cursor = hi
        else:
            cursor = probe
    for instant in solar_term_boundaries(lower, upper):
        cuts.setdefault(instant, set()).add('solar_term')
    ordered = sorted(cuts)
    return tuple(_Window(left, right, tuple(sorted(cuts[left])))
                 for left, right in zip(ordered, ordered[1:])
                 if start <= left.astimezone(zone).date() < end)


def hour_slot(window: _Window, zone: ZoneInfo) -> dict:
    """Evaluate the inclusive start; the full dated boundaries identify repeated clock times."""
    start = window.start_utc.astimezone(zone)
    end = window.end_utc.astimezone(zone)
    chart = dunjia_futou(start)
    term = chart['solar_term']
    clock_format = '%H:%M:%S' if start.second or end.second else '%H:%M'
    end_label = '24:00' if end.date() > start.date() and end.hour == end.minute == end.second == 0 else end.strftime(clock_format)
    return {'date': start.date().isoformat(), 'window': f'{start.strftime(clock_format)}–{end_label}',
            'start': start.isoformat(), 'end': end.isoformat(), 'sampled_at': start.isoformat(),
            'boundary_reasons': list(window.boundary_reasons), 'ganzhi': chart['ganzhi'],
            'ju': f'{chart["ju_type"]}{chart["ju_number"]}局（{term["name"]}{chart["san_yuan"]}）',
            'patterns': chart['patterns']}


def judge(slot: dict) -> dict | str:
    """The candidate record, or the reason the 时辰 is left out."""
    hits = slot['patterns']
    veto = next((h['name'] for h in hits if h['name'] in SLOT_VETO), None)
    if veto:
        return veto
    forced = {h['palace'] for h in hits if h['category'] == '门迫'}
    bad: dict[int, list[str]] = {}
    for h in hits:
        if h['kind'] == '凶' and h['palace'] is not None and h['category'] != '门迫':
            bad.setdefault(h['palace'], []).append(h['name'])
    listed = [h for h in hits if h['category'] in GOOD and not h['variant']]
    good = [h for h in listed if h.get('usable', True)]
    usable = [h for h in good if h['palace'] not in forced]
    if listed and not good:
        return '只有本旬直符未同临的三奇得使'
    if not good:
        return '无吉格'
    if not usable:
        return '吉格所在宫门迫'
    rows = [{'name': h['name'], 'palace': h['palace'], 'direction': PALACE_INFO[h['palace']]['direction'],
             'evidence': h['evidence'], 'passage_id': h['passage_id'],
             **({'flaw': '本宫兼成' + '、'.join(dict.fromkeys(bad[h['palace']]))} if h['palace'] in bad else {})}
            for h in usable]
    variants = [h['name'] for h in hits if h['category'] in GOOD and h['variant'] and h['palace'] not in forced]
    return {'date': slot['date'], 'window': slot['window'], 'sampled_at': slot['sampled_at'],
            'ganzhi': {k: slot['ganzhi'][k] for k in ('day', 'hour')}, 'ju': slot['ju'], 'auspicious': rows,
            'variant_also': list(dict.fromkeys(variants))}


def select(start: date, days: int, zone: ZoneInfo) -> dict:
    candidates: list[dict] = []
    excluded: dict[str, int] = {}
    excluded_windows: list[dict] = []
    seen_dates: set[str] = set()
    for window in _windows(start, days, zone):
        slot = hour_slot(window, zone)
        seen_dates.add(slot['date'])
        interval = {key: slot[key] for key in ('date', 'window', 'start', 'end', 'sampled_at', 'boundary_reasons')}
        got = judge(slot)
        if isinstance(got, str):
            excluded[got] = excluded.get(got, 0) + 1
            excluded_windows.append(dict(interval, reason=got))
        else:
            candidates.append(dict(got, **interval))
    skipped = [(start + timedelta(days=offset)).isoformat() for offset in range(days)
               if (start + timedelta(days=offset)).isoformat() not in seen_dates]
    return {'candidates': candidates, 'excluded': excluded, 'excluded_windows': excluded_windows,
            'skipped_dates': skipped, 'interval_convention': '[start,end); sampled_at=start; UTC order'}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='奇门择时：按当地日期覆盖全部实际区间，交节与时区切换处分段筛选', epilog=EPILOG,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--from', dest='start', required=True, help='起始公历日期 YYYY-MM-DD')
    p.add_argument('--days', type=int, default=7, help=f'连续天数 1..{MAX_DAYS}，默认 7')
    p.add_argument('--target-timezone', required=True, help='择时地点的 IANA 时区；交节按实际瞬间比较')
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        start = date.fromisoformat(args.start)
    except ValueError:
        json_print(error_envelope('qimen_select', 'invalid_date', '起始日期须为有效的 YYYY-MM-DD'))
        return 1
    if not 1 <= args.days <= MAX_DAYS:
        json_print(error_envelope('qimen_select', 'invalid_days', f'天数须在 1..{MAX_DAYS}'))
        return 1
    if not 1900 <= start.year <= 2100:
        json_print(error_envelope('qimen_select', 'out_of_range', '起始年份须在 1900..2100'))
        return 1
    try:
        zone = ZoneInfo(args.target_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        json_print(error_envelope('qimen_select', 'invalid_timezone', f'无效 IANA 时区: {args.target_timezone}'))
        return 1
    require_lunar()
    try:
        result = select(start, args.days, zone)
    except (ValueError, KeyError, OverflowError) as exc:
        json_print(error_envelope('qimen_select', 'interval_calculation_failed', str(exc)))
        return 1
    n = len(result['candidates'])
    json_print({
        'ok': True, 'tool': 'qimen_select', 'version': __version__, 'method': 'dunjia-zhuanpan',
        'input': {'from': start.isoformat(), 'days': args.days, 'target_timezone': args.target_timezone},
        **result, 'rules': RULES, 'patterns_not_computed': NOT_COMPUTED,
        'say': (f'{n} 个时段符合；按时间先后列出，彼此不分高下。' if n else '这段时间没有符合条件的时段。')
               + '只按《遁甲演义》格局字面筛，不含个人八字，不保证结果。',
    })
    return 0


if __name__ == '__main__':
    sys.exit(main())
