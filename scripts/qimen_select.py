"""奇门择时：在一段日子里逐时辰排《遁甲演义》转盘，列出有吉格、又不犯原文禁忌的时辰。

只用原文写明的条件筛：
- 候选：该时辰有九遁、吉格、诈假的正条（「又曰」异说另列，不单独成候选）。
- 整个时辰不用：五不遇时「縱有竒門不可行」（dunjia:c002:p0041）；三奇入墓与时干入墓「縱有竒門不可舉兵」
  「亦不可用」（p0042）；六仪击刑「其時極凶不可用事」（p0043）；伏吟反吟「雖得竒不可用」（p0045）。
- 吉格所在宫门迫的不算：天遁条「亦不可犯竒墓門迫」（p0003）。
- 吉格所在宫同时成凶格的保留，标「有微疵」（p0009「尚有㣲疵不吉」）。
不看个人八字；候选按时间先后列，彼此不分高下。

CLI:
    python qimen_select.py --from 2026-11-02 --days 3 --target-timezone Asia/Shanghai
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qimen_cast import earth_plate
from qimen_dingju import determine_ju, seasonal_context
from qimen_patterns import NOT_COMPUTED, detect
from qimen_tables import PALACE_INFO
from qimen_zhuanpan import plate
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print, require_lunar

MAX_DAYS = 31
EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version method input candidates excluded rules patterns_not_computed say

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""
GOOD = ('九遁', '吉格', '诈假')
SLOT_VETO = {'五不遇时': 'dunjia:c002:p0041', '三奇入墓': 'dunjia:c002:p0042', '时干入墓': 'dunjia:c002:p0042',
             '六仪击刑': 'dunjia:c002:p0043', '伏吟': 'dunjia:c002:p0045', '反吟': 'dunjia:c002:p0045'}
RULES = [
    '候选：九遁、吉格、诈假正条；异说另列（dunjia:c002 各条）',
    '整时不用：五不遇时 p0041、三奇入墓与时干入墓 p0042、六仪击刑 p0043、伏吟反吟 p0045',
    '吉格所在宫门迫不算（p0003「亦不可犯竒墓門迫」）',
    '吉格所在宫兼成凶格者保留并标微疵（p0009）',
]


def hour_slot(day: date, hour: int, zone: ZoneInfo) -> dict:
    """One 时辰 sampled at its midpoint (子时取当日 00:00，即早子)."""
    from lunar_python import Lunar, Solar  # type: ignore
    lunar = Solar.fromYmdHms(day.year, day.month, day.day, hour, 0, 0).getLunar()
    gz = {'year': lunar.getYearInGanZhi(), 'month': lunar.getMonthInGanZhi(), 'day': lunar.getDayInGanZhi(),
          'hour': lunar.getTimeInGanZhi(),
          'month_shuo': Lunar.fromYmd(lunar.getYear(), lunar.getMonth(), 1).getDayInGanZhi()}
    term = seasonal_context(datetime(day.year, day.month, day.day, hour, tzinfo=zone))
    ju_type, yuan, number = determine_ju(term['name'], gz['day'])
    pl = plate(earth_plate(ju_type, number), ju_type, gz['hour'])
    window = '00:00–01:00' if hour == 0 else f'{hour - 1:02d}:00–{hour + 1:02d}:00'
    return {'date': day.isoformat(), 'window': window, 'sampled_at': f'{hour:02d}:00', 'ganzhi': gz,
            'ju': f'{ju_type}{number}局（{term["name"]}{yuan}）', 'patterns': detect(pl, gz)}


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
    good = [h for h in hits if h['category'] in GOOD and not h['variant']]
    usable = [h for h in good if h['palace'] not in forced]
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
    for offset in range(days):
        day = start + timedelta(days=offset)
        for hour in range(0, 24, 2):
            got = judge(hour_slot(day, hour, zone))
            if isinstance(got, str):
                excluded[got] = excluded.get(got, 0) + 1
            else:
                candidates.append(got)
    return {'candidates': candidates, 'excluded': excluded}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='奇门择时：遁甲演义转盘逐时辰筛吉格与禁忌', epilog=EPILOG,
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
    result = select(start, args.days, zone)
    n = len(result['candidates'])
    json_print({
        'ok': True, 'tool': 'qimen_select', 'version': __version__, 'method': 'dunjia-zhuanpan',
        'input': {'from': start.isoformat(), 'days': args.days, 'target_timezone': args.target_timezone},
        **result, 'rules': RULES, 'patterns_not_computed': NOT_COMPUTED,
        'say': (f'{n} 个时辰符合；按时间先后列出，彼此不分高下。' if n else '这段时间没有符合条件的时辰。')
               + '只按《遁甲演义》格局字面筛，不含个人八字，不保证结果。',
    })
    return 0


if __name__ == '__main__':
    sys.exit(main())
