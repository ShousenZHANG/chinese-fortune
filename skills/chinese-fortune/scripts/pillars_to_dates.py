"""由四柱反查可能的出生日期与时辰窗口.

日柱六十天一轮, 先按日柱逐日筛出候选日; 日柱、时柱按真太阳时 (子正换日)。年柱、月柱按
真实瞬间与交节表比较, 交节表是 UTC+8 钟面 (lunar_python 精确值), 两种坐标不能混用:
- 给了 --longitude: 把窗口换成 UTC+8 瞬间核年月, 交节落在窗口里时切到分钟, 再换回真太阳时。
- 没给: 窗口照真太阳时列整段; 若交节落在中国境内经度 (73°–135°E) 可能对应的瞬间范围里, 标
  depends_on_longitude 并给交节的 UTC+8 时刻, 要补出生地经度才能切。
子时只列与时柱相符的一段: 早子 (00:00–01:00) 时干按当日五鼠遁, 晚子 (23:00–24:00) 日柱仍是当日、
时干按次日 (与 bazi_calc 的晚子口径一致)。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from utils import (
    DIZHI,
    TIANGAN,
    WUHU_DUN,
    WUSHU_DUN,
    ensure_utf8_stdio,
    equation_of_time,
    error_envelope,
    json_print,
    ok_envelope,
)

ANCHOR = date(1900, 1, 1)      # 甲戌日, 六十甲子序号 10
ANCHOR_INDEX = 10
JIAZI = [TIANGAN[i % 10] + DIZHI[i % 12] for i in range(60)]
MAX_SPAN = 400
# True solar = UTC+8 clock + (lon - 120°) × 4 min + equation of time. Across China (73°–135°E) and the
# year's EoT range (about -14.5 to +16.5 min) the UTC+8 instant lies this far before / after true solar.
CLOCK_BEFORE = timedelta(minutes=(135 - 120) * 4 + 17)
CLOCK_AFTER = timedelta(minutes=(120 - 73) * 4 + 15)


def _zi_stem(day_stem: str) -> str:
    return WUSHU_DUN[day_stem]


def _hour_stem_ok(day: str, hour: str) -> tuple[bool, str | None]:
    """(consistent, which 子 window): 早子 uses the day's own 五鼠遁, 晚子 the next day's."""
    start = TIANGAN.index(WUSHU_DUN[day[0]])
    if hour[1] != '子':
        return TIANGAN[(start + DIZHI.index(hour[1])) % 10] == hour[0], None
    if hour[0] == _zi_stem(day[0]):
        return True, '早子时'
    if hour[0] == _zi_stem(TIANGAN[(TIANGAN.index(day[0]) + 1) % 10]):
        return True, '晚子时'
    return False, None


def _check(pillar: str, name: str) -> str:
    if pillar not in JIAZI:
        raise ValueError(f'{name}「{pillar}」不是六十甲子中的干支')
    return pillar


def _consistent(year: str, month: str, day: str, hour: str | None) -> list[str]:
    problems = []
    first = TIANGAN.index(WUHU_DUN[year[0]])
    month_offset = (DIZHI.index(month[1]) - 2) % 12          # 寅月为第一个月
    if TIANGAN[(first + month_offset) % 10] != month[0]:
        problems.append(f'{year}年的{month[1]}月应为{TIANGAN[(first + month_offset) % 10]}{month[1]}（五虎遁），不是{month}')
    if hour and not _hour_stem_ok(day, hour)[0]:
        start = TIANGAN.index(WUSHU_DUN[day[0]])
        expected = TIANGAN[(start + DIZHI.index(hour[1])) % 10]
        if hour[1] == '子':
            late = _zi_stem(TIANGAN[(TIANGAN.index(day[0]) + 1) % 10])
            problems.append(f'{day}日的子时应为{expected}子（早子，五鼠遁）或{late}子（晚子，时干取次日），不是{hour}')
        else:
            problems.append(f'{day}日的{hour[1]}时应为{expected}{hour[1]}（五鼠遁），不是{hour}')
    return problems


def _pillars_at(moment: datetime) -> tuple[str, str]:
    from lunar_python import Solar
    lunar = Solar.fromYmdHms(moment.year, moment.month, moment.day, moment.hour, moment.minute, 0).getLunar()
    return lunar.getYearInGanZhiExact(), lunar.getMonthInGanZhiExact()


def _window(day: date, hour_branch: str | None, zi: str | None = None) -> list[tuple[datetime, datetime, str]]:
    """(start, end exclusive, label) true-solar windows for the hour branch on this day; the whole day if none."""
    midnight = datetime(day.year, day.month, day.day)
    if hour_branch is None:
        return [(midnight, midnight + timedelta(days=1), '全天')]
    if hour_branch == '子':
        early = (midnight, midnight + timedelta(hours=1), '早子时')
        late = (midnight + timedelta(hours=23), midnight + timedelta(days=1), '晚子时')
        return [w for w in (early, late) if zi in (None, w[2])]
    i = DIZHI.index(hour_branch)
    start = midnight + timedelta(hours=2 * i - 1)
    return [(start, start + timedelta(hours=2), f'{hour_branch}时')]


def _matching_span(start: datetime, end: datetime, want: tuple[str, str]) -> tuple[datetime, datetime] | None:
    """The part of [start, end) whose exact year and month pillars equal want (one 交节 at most)."""
    last = end - timedelta(minutes=1)
    at_start, at_end = _pillars_at(start), _pillars_at(last)
    if at_start == want and at_end == want:
        return start, end
    if at_start != want and at_end != want:
        return None
    lo, hi = start, last          # bisect the minute the pillars change
    while hi - lo > timedelta(minutes=1):
        mid = lo + (hi - lo) // 2
        mid = mid.replace(second=0, microsecond=0)
        if (_pillars_at(mid) == want) == (at_start == want):
            lo = mid
        else:
            hi = mid
    return (start, hi) if at_start == want else (hi, end)


def _solar_offset(moment: datetime, longitude: float) -> timedelta:
    """True solar minus UTC+8 clock at this longitude and date."""
    import calendar
    eot = equation_of_time(moment.timetuple().tm_yday, leap=calendar.isleap(moment.year))
    return timedelta(minutes=(longitude - 120) * 4 + eot)


def _candidate(cursor: date, start: datetime, end: datetime, label: str, want: tuple[str, str],
               longitude: float | None) -> dict | None:
    base = {'date': cursor.isoformat(), 'window_label': label}
    if longitude is not None:
        offset = _solar_offset(start, longitude)
        span = _matching_span(start - offset, end - offset, want)
        if span is None:
            return None
        cut = span != (start - offset, end - offset)
        return {**base, 'true_solar_from': f'{span[0] + offset:%Y-%m-%d %H:%M}',
                'true_solar_to': f'{span[1] + offset:%Y-%m-%d %H:%M}', 'cut_by_solar_term': cut,
                'depends_on_longitude': False,
                **({'term_cut_utc8': f'{(span[0] if span[0] != start - offset else span[1]):%Y-%m-%d %H:%M}'}
                   if cut else {})}
    # Without a longitude only the range of UTC+8 instants a China birth could have is known.
    span = _matching_span(start - CLOCK_BEFORE, end + CLOCK_AFTER, want)
    if span is None:
        return None
    full = span == (start - CLOCK_BEFORE, end + CLOCK_AFTER)
    row = {**base, 'true_solar_from': f'{start:%Y-%m-%d %H:%M}', 'true_solar_to': f'{end:%Y-%m-%d %H:%M}',
           'cut_by_solar_term': False, 'depends_on_longitude': not full}
    if not full:
        row['term_cut_utc8'] = f'{(span[0] if span[0] != start - CLOCK_BEFORE else span[1]):%Y-%m-%d %H:%M}'
        row['term_side'] = 'after' if span[0] != start - CLOCK_BEFORE else 'before'
    return row


def lookup(year: str, month: str, day: str, hour: str | None, first_year: int, last_year: int,
           longitude: float | None = None) -> dict:
    for value, name in ((year, '年柱'), (month, '月柱'), (day, '日柱')):
        _check(value, name)
    if hour is not None:
        _check(hour, '时柱')
    problems = _consistent(year, month, day, hour)
    if problems:
        raise ValueError('四柱本身不成立：' + '；'.join(problems))
    if not 1 <= last_year - first_year + 1 <= MAX_SPAN or first_year < 1600 or last_year > 2399:
        raise ValueError('年份范围须在 1600–2399 之间，且不超过 400 年')
    if longitude is not None and not -180 <= longitude <= 180:
        raise ValueError('经度须在 -180..180')
    offset = (JIAZI.index(day) - ANCHOR_INDEX - (date(first_year, 1, 1) - ANCHOR).days) % 60
    cursor = date(first_year, 1, 1) + timedelta(days=offset)
    zi = _hour_stem_ok(day, hour)[1] if hour else None
    found = []
    while cursor.year <= last_year:
        for start, end, label in _window(cursor, hour[1] if hour else None, zi):
            row = _candidate(cursor, start, end, label, (year, month), longitude)
            if row:
                found.append(row)
        cursor += timedelta(days=60)

    def describe(c: dict) -> str:
        if c['depends_on_longitude']:
            side = '之后' if c['term_side'] == 'after' else '之前'
            return (f"{c['true_solar_from']} 至 {c['true_solar_to']}（真太阳时；交节约在 UTC+8 {c['term_cut_utc8']}（分钟精度），"
                    f"出生瞬间须在其{side}，要出生地经度才能切开）")
        return f"{c['true_solar_from']} 至 {c['true_solar_to']}（真太阳时{'，交节切开' if c['cut_by_solar_term'] else ''}）"

    head = f"{year} {month} {day}{' ' + hour if hour else ''} 在 {first_year}–{last_year} 年间"
    say = (head + f'有 {len(found)} 个可能：' + '；'.join(describe(c) for c in found[:8])
           + ('……' if len(found) > 8 else '') + '。') if found else head + '没有对应日期。'
    return ok_envelope('pillars_to_dates', {
        'pillars': {'year': year, 'month': month, 'day': day, 'hour': hour},
        'range': {'first_year': first_year, 'last_year': last_year}, 'longitude': longitude,
        'candidates': found, 'say': say,
        'conventions': ['年柱、月柱按真实瞬间比较交节表，交节表是 UTC+8 钟面（lunar_python 精确值）',
                        '日柱、时柱按真太阳时；子正换日；晚子时 23:00–24:00 日柱仍取当日、时干取次日',
                        '给了经度才把交节换成真太阳时切开窗口；没给时按中国境内经度范围判断交节是否可能落进窗口',
                        '换成钟表时间还要按出生地经度、均时差和当年时制（含夏令时）反推'],
        'boundary': '同一组四柱每六十年左右重现一次，反查只给历法上的全部可能，不判断哪一个是本人。',
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='由四柱反查可能的出生日期与时辰窗口（日时按真太阳时，年月按 UTC+8 交节表）',
                                epilog='Top-level JSON keys: ok tool version pillars range longitude candidates say conventions '
                                       'boundary; errors: ok=false error message.')
    p.add_argument('--year-pillar', required=True)
    p.add_argument('--month-pillar', required=True)
    p.add_argument('--day-pillar', required=True)
    p.add_argument('--hour-pillar', default=None, help='可省；省略时给整天')
    p.add_argument('--from-year', type=int, default=1900)
    p.add_argument('--to-year', type=int, default=2100)
    p.add_argument('--longitude', type=float, default=None,
                   help='出生地经度；给了才能把交节换成真太阳时切开窗口')
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        result = lookup(args.year_pillar, args.month_pillar, args.day_pillar, args.hour_pillar,
                        args.from_year, args.to_year, args.longitude)
    except ImportError as exc:
        json_print(error_envelope('pillars_to_dates', 'missing_dependency', f'缺少历法库：{exc.name or exc}'))
        return 1
    except (ValueError, TypeError) as exc:
        json_print(error_envelope('pillars_to_dates', 'invalid_input', str(exc)))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
