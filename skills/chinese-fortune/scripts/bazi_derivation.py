"""How each pillar and the luck start were reached, in steps a user can redo.

Every input below is already in chart_facts; this only lays it out in the order
a person checks a chart by hand: clock time and zone, the solar-term window for
year and month, the true-solar correction, the day boundary, the hour stem by
五鼠遁, and the luck direction and start. Nothing is recomputed here, so the
steps cannot disagree with the chart they explain.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from utils import (
    DIZHI,
    DIZHI_WUXING,
    HIDDEN_STEMS,
    TIANGAN,
    TIANGAN_WUXING,
    hour_branch,
    jiazi_index,
    parse_iso,
)

# 1900-01-01 was a 甲戌 day, number 11 (index 10) of the sixty.
ANCHOR = date(1900, 1, 1)
ANCHOR_INDEX = 10

# 五鼠遁: the stem of 子时 for each day stem.
RAT = {'甲': '甲', '己': '甲', '乙': '丙', '庚': '丙', '丙': '戊', '辛': '戊',
       '丁': '庚', '壬': '庚', '戊': '壬', '癸': '壬'}
ASK_WORDS = ('怎么算', '怎么排', '如何排', '推算', '复核', '复算', '为什么是', '起运', '交节', '真太阳时', '日柱')


def asks_derivation(question: str) -> bool:
    return any(word in question for word in ASK_WORDS)


def _gz(facts: dict, pillar: str) -> str:
    """The pillar's 干支, or 未定 when an unknown birth time leaves it open."""
    return (facts.get('four_pillars', {}).get(pillar) or {}).get('ganzhi') or '未定'


UNDECIDED = '出生时辰未知，这一柱可能随时辰不同，候选见 birth_time_uncertainty；不用占位时辰补齐。'


def _clock_step(facts: dict) -> dict:
    tz = facts.get('timezone') or {}
    ctx = facts.get('calendar_context') or {}
    if not ctx.get('birth_instant_utc'):
        return {'step': '出生时刻', 'result': '只知日期',
                'how': f"没有出生时刻，按出生地时区 {tz.get('tz_name') or '未给'} 的日期计算；依赖时刻的柱保留未定。"}
    clock = _clock(facts)
    if tz.get('tz_name'):
        zone = (f"时区 {tz['tz_name']}，当时偏移 UTC{tz.get('offset_hours', 0):+g}"
                f"（含夏令时 {tz.get('dst_hours', 0):g} 小时）")
    else:
        offset = _fixed_offset(facts, clock)
        fixed = f' UTC{offset:+g}' if offset is not None else ''
        zone = f"未给 IANA 时区，按固定偏移{fixed}（不判断夏令时）"
    return {'step': '出生时刻', 'result': ctx.get('birth_instant_utc'),
            'how': f"当地钟表 {clock}，{zone}，换成 UTC 瞬间。"}


def _clock(facts: dict) -> str:
    """The birth clock time as entered: the raw clock, never the true-solar result."""
    tst = facts.get('true_solar_time') or {}
    if tst.get('clock_time'):
        return str(tst['clock_time'])
    solar = facts.get('solar_date') or {}
    return f"{solar.get('hour', 0):02d}:{solar.get('minute', 0):02d}"


def _effective_time(facts: dict) -> str:
    """The time the day and hour pillars were taken from: true solar when applied, else the clock."""
    tst = facts.get('true_solar_time') or {}
    return str(tst['true_solar_time']) if tst.get('applied') and tst.get('true_solar_time') else _clock(facts)


def _fixed_offset(facts: dict, clock: str) -> float | None:
    """Hours between the entered clock and the UTC instant; None when the facts cannot show it."""
    tst = facts.get('true_solar_time') or {}
    solar = facts.get('solar_date') or {}
    try:
        instant = parse_iso((facts.get('calendar_context') or {})['birth_instant_utc'])
        if tst.get('effective_date'):
            day = date.fromisoformat(tst['effective_date']) - timedelta(days=tst.get('day_offset') or 0)
        else:
            day = date(solar['year'], solar['month'], solar['day'])
        hour, minute = (int(x) for x in clock.split(':')[:2])
    except (KeyError, ValueError, TypeError):
        return None
    local = datetime(day.year, day.month, day.day, hour, minute)
    return round((local - instant.replace(tzinfo=None)).total_seconds() / 3600, 2)


def _term_step(facts: dict) -> dict:
    ctx = facts.get('calendar_context') or {}
    prev, nxt = ctx.get('previous_jie') or {}, ctx.get('next_jie') or {}
    if not prev or not nxt:
        return {'step': '年柱与月柱', 'result': f"{_gz(facts, 'year')}年 {_gz(facts, 'month')}月",
                'how': '按出生日期所在的节气月定月、立春定年；出生日若正逢交节，年柱或月柱要看出生时刻，未定者不补。'}
    return {'step': '年柱与月柱', 'result': f"{_gz(facts, 'year')}年 {_gz(facts, 'month')}月",
            'how': f"出生瞬间落在 {prev.get('name', '?')}（{prev.get('calendar_datetime', '?')}）之后、"
                   f"{nxt.get('name', '?')}（{nxt.get('calendar_datetime', '?')}）之前，按此节定月；"
                   '年柱以立春换年。交节时刻按固定的 UTC+08:00 交节表比较。'}


def _solar_step(facts: dict) -> dict:
    tst = facts.get('true_solar_time') or {}
    if not tst.get('applied'):
        return {'step': '真太阳时', 'result': '未校正', 'how': '没有经度或选择了钟表时间口径，日柱与时柱直接用钟表时间。'}
    dst = float((facts.get('timezone') or {}).get('dst_hours') or 0)
    longitude, meridian = float(tst.get('longitude', 0)), float(tst.get('ref_meridian', 0)) - 15 * dst
    parts = [f"经度 {longitude:g}° 对标准时经线 {meridian:g}° 差 {round((longitude - meridian) * 4, 2):g} 分钟"]
    if dst:
        parts.append(f"出生时行夏令时，钟表快 {dst * 60:g} 分钟，扣回 {-dst * 60:g} 分钟")
    parts.append(f"均时差 {tst.get('equation_of_time_min')} 分钟")
    return {'step': '真太阳时', 'result': f"{tst.get('effective_date')} {tst.get('true_solar_time')}",
            'how': '，'.join(parts) + f"，合计 {tst.get('total_offset_min')} 分钟："
                   f"{tst.get('clock_time')} → {tst.get('true_solar_time')}。",
            'say': offset_sentence(tst)}


def offset_sentence(tst: dict) -> str:
    """The direction in words, so nobody has to turn a signed number into 快 or 慢."""
    total = float(tst.get('total_offset_min') or 0)
    if total == 0:
        return f"真太阳时与钟表读数相同（{tst.get('clock_time')}）。"
    # 「读数少」 alone was still rewritten as 「晚」 (R3 T05); 早/晚 is said outright.
    return (f"真太阳时 {tst.get('true_solar_time')} 比钟表 {tst.get('clock_time')} {'早' if total < 0 else '晚'} "
            f"{abs(total):g} 分钟（读数{'少' if total < 0 else '多'} {abs(total):g} 分钟）。")


# A 时辰 starts at every odd hour; a birth this close to one can sit in either (R3 N19).
BOUNDARY_MINUTES = 15


def _minute_of_day(text: str | None) -> int | None:
    try:
        hour, minute = (int(part) for part in str(text).split(':')[:2])
    except ValueError:
        return None
    return hour * 60 + minute


def _branch_at(minute: int) -> str:
    return hour_branch((minute // 60) % 24)


def hour_boundary(tst: dict, dst_hours: float = 0.0) -> dict | None:
    """The hour branch the birth time falls in, and the neighbour it nearly is.

    Returned when the time used for the hour pillar (true solar time when applied, else the clock) is within
    BOUNDARY_MINUTES of a 时辰 edge, when the standard-time clock alone would give another branch, or when a
    daylight-saving birth would land in another branch had the clock already been standard time (R4 N02: the
    raw DST clock is not a second method, the question is which time was written down).
    """
    used = _minute_of_day(tst.get('true_solar_time') if tst.get('applied') else tst.get('clock_time'))
    clock = _minute_of_day(tst.get('clock_time'))
    if used is None:
        return None
    shift = round(dst_hours * 60)
    if not tst.get('applied'):
        used -= shift
    branch = _branch_at(used)
    which = '真太阳时' if tst.get('applied') else '标准时'
    if shift:
        recorded_as_standard = _branch_at(used + shift)
        if recorded_as_standard != branch:
            say = (f"出生时当地行夏令时：钟表 {tst.get('clock_time')} 若是夏令时，扣回 {shift} 分钟后按{which}是{branch}时；"
                   f"若当时记的已是标准时，就是{recorded_as_standard}时。要问清出生时间记的是哪种，"
                   "用到时柱的结论两种都说。")
            return {'branch': branch, 'clock_branch': recorded_as_standard, 'other_branch': recorded_as_standard,
                    'minutes_to_boundary': None, 'time_used': which, 'kind': 'dst_record', 'say': say}
    since = (used - 60) % 120          # minutes since the current 时辰 began
    before, after = since, 120 - since
    other, gap = (_branch_at(used - 1 - since), before) if before <= after else (_branch_at(used + after), after)
    clock_branch = _branch_at(clock - shift) if clock is not None else branch
    if gap > BOUNDARY_MINUTES and clock_branch == branch:
        return None
    if clock_branch != branch:
        other = clock_branch
    shown = tst.get('true_solar_time') if tst.get('applied') else tst.get('clock_time')
    say = (f"按{which} {shown} 是{branch}时，离{other}时只差 {gap} 分钟" if gap <= BOUNDARY_MINUTES else
           f"按{which}是{branch}时，按钟表 {tst.get('clock_time')} 是{other}时")
    say += f"：出生时间差这么一点，时柱就换成{other}时，用到时柱的结论要两种都说。"
    return {'branch': branch, 'clock_branch': clock_branch, 'other_branch': other, 'minutes_to_boundary': gap,
            'time_used': which, 'kind': 'edge' if gap <= BOUNDARY_MINUTES else 'clock', 'say': say}


def _day_step(facts: dict) -> dict:
    tst = facts.get('true_solar_time') or {}
    sect = facts.get('sect') or {}
    if _gz(facts, 'day') == '未定':
        return {'step': '日柱', 'result': '未定', 'how': UNDECIDED}
    how = f"取 {tst.get('effective_date', '出生日')} 这一天的干支；晚子时口径：{sect.get('label', '默认')}。"
    return {'step': '日柱', 'result': _gz(facts, 'day'), 'how': how + _day_count(facts, tst.get('effective_date'))}


def _day_count(facts: dict, effective: str | None) -> str:
    """The day pillar by plain arithmetic from a fixed anchor, stated only when it agrees with the chart."""
    day = facts['four_pillars']['day']
    try:
        base = date.fromisoformat(str(effective))
        index = jiazi_index(day['stem'], day['branch'])
    except (TypeError, ValueError, KeyError):
        return ''
    # A late-zi birth under 子初换日 takes the next day's pillar; say so rather than drop the arithmetic.
    for shift in (0, 1):
        offset = (base + timedelta(days=shift) - ANCHOR).days
        if (ANCHOR_INDEX + offset) % 60 == index:
            break
    else:
        return ''
    note = '（晚子时按子初换日取次日）' if shift else ''
    pillar_date = (base + timedelta(days=shift)).isoformat()
    return (f"手算复核{note}：以 1900-01-01（甲戌日，六十甲子第 11 位）为基准，到 {pillar_date} 相隔 {offset} 天；"
            f"(10 + {offset}) 除以 60 余 {index}，即第 {index + 1} 位"
            f"{TIANGAN[index % 10]}{DIZHI[index % 12]}。")


def _hour_step(facts: dict) -> dict:
    if not facts.get('hour_known', True) or '未定' in (_gz(facts, 'hour'), _gz(facts, 'day')):
        return {'step': '时柱', 'result': '未定', 'how': '出生时辰未知，不用占位时辰排时柱；依赖时柱的结论保留未定。'}
    day_stem = facts['four_pillars']['day']['stem']
    clock = _effective_time(facts)
    hour = int(clock.split(':')[0])
    branch = hour_branch(hour)
    return {'step': '时柱', 'result': facts['four_pillars']['hour']['ganzhi'],
            'how': f"{clock} 属{branch}时；日干{day_stem}按五鼠遁子时起{RAT.get(day_stem, '?')}，"
                   f"顺数到{branch}时得{facts['four_pillars']['hour']['stem']}。"
                   + ('晚子时的时干按所用历法库取次日干。' if hour == 23 else '')}


def _luck_step(facts: dict) -> dict | None:
    qi = facts.get('qi_yun') or {}
    cycles = facts.get('da_yun') or []
    year = facts.get('four_pillars', {}).get('year') or {}
    if not qi or not cycles or not year.get('stem'):
        return None
    forward = qi.get('direction') == 'forward'
    first = cycles[0]
    return {'step': '大运方向与起运', 'result': f"{qi.get('text')}起运（{qi.get('start_calendar_datetime')}），首运{first.get('ganzhi')}",
            'how': f"年干{year['stem']}属{year.get('stem_yin_yang', '?')}：阳年男、阴年女顺排，阴年男、阳年女逆排，"
                   f"本盘{'顺' if forward else '逆'}排，从月柱{_gz(facts, 'month')}"
                   f"{'下一位' if forward else '上一位'}起。起运间隔量到{'下一个' if forward else '上一个'}节，"
                   f"换算口径：{qi.get('method', '所用算法')}。" + _interval_text(facts, forward)}


def _interval_text(facts: dict, forward: bool) -> str:
    """How far the birth is from the governing 节, and the conversion that turns it into the start age."""
    ctx = facts.get('calendar_context') or {}
    qi = facts.get('qi_yun') or {}
    jie = ctx.get('next_jie' if forward else 'previous_jie') or {}
    try:
        birth = parse_iso(ctx['birth_calendar_datetime'])
        boundary = parse_iso(jie['calendar_datetime'])
    except (KeyError, TypeError, ValueError):
        return ''
    hours = abs((boundary - birth).total_seconds()) / 3600
    return (f"出生到{'下一个' if forward else '上一个'}节（{jie.get('name')} {jie['calendar_datetime'][:16]}）"
            f"相距约 {int(hours // 24)} 天 {int(hours % 24)} 小时；按 3 天折 1 年、1 天折 4 个月、1 个时辰（2 小时）"
            f"折 10 天换算（天数取整天，时辰按出生与交节所在时辰计），得 {qi.get('years')} 年 {qi.get('months')} 个月 "
            f"{qi.get('days')} 天。")


def derivation_steps(facts: dict) -> list[dict]:
    steps = [_clock_step(facts), _term_step(facts), _solar_step(facts), _day_step(facts), _hour_step(facts)]
    luck = _luck_step(facts)
    return steps + ([luck] if luck else [])



# 节气月 → 传统月名 (R4 T05 called a 丑 month 「冬月」, the name of the 子 month).
MONTH_NAMES = {'寅': ('孟春', '正月', '立春', '惊蛰'), '卯': ('仲春', '二月', '惊蛰', '清明'),
               '辰': ('季春', '三月', '清明', '立夏'), '巳': ('孟夏', '四月', '立夏', '芒种'),
               '午': ('仲夏', '五月', '芒种', '小暑'), '未': ('季夏', '六月', '小暑', '立秋'),
               '申': ('孟秋', '七月', '立秋', '白露'), '酉': ('仲秋', '八月', '白露', '寒露'),
               '戌': ('季秋', '九月', '寒露', '立冬'), '亥': ('孟冬', '十月', '立冬', '大雪'),
               '子': ('仲冬', '冬月（十一月）', '大雪', '小寒'), '丑': ('季冬', '腊月（十二月）', '小寒', '立春')}
ELEMENTS = ('木', '火', '土', '金', '水')


def month_name(branch: str | None) -> dict | None:
    if branch not in MONTH_NAMES:
        return None
    season, name, start, end = MONTH_NAMES[branch]
    return {'branch': branch, 'season': season, 'name': name, 'from_term': start, 'to_term': end,
            'say': f"月令{branch}：节气月从{start}到{end}，传统称{season}、{name}；节气月和农历月不完全对齐，不按农历日期改称。"}


def wuxing_counts(pillars: dict, hour_known: bool = True) -> dict:
    """Unweighted element counts of the eight characters and, separately, of the hidden stems (R4 T22 miscounted)."""
    keys = [k for k in ('year', 'month', 'day', 'hour') if k != 'hour' or hour_known]
    surface = dict.fromkeys(ELEMENTS, 0)
    hidden = dict.fromkeys(ELEMENTS, 0)
    for key in keys:
        pillar = pillars.get(key) or {}
        if pillar.get('stem') in TIANGAN_WUXING:
            surface[TIANGAN_WUXING[pillar['stem']]] += 1
        if pillar.get('branch') in DIZHI_WUXING:
            surface[DIZHI_WUXING[pillar['branch']]] += 1
        for stem in HIDDEN_STEMS.get(pillar.get('branch') or '', []):
            hidden[TIANGAN_WUXING[stem]] += 1
    def row(counts: dict) -> str:
        return ' '.join(f'{e}{counts[e]}' for e in ELEMENTS)
    scope = '四柱' if hour_known else '年月日三柱（时辰未知）'
    return {'pillars_counted': keys, 'surface': surface, 'surface_total': sum(surface.values()),
            'hidden': hidden, 'hidden_total': sum(hidden.values()),
            'say': (f"只数{scope}的天干地支（每字记 1，不加权）：{row(surface)}，共 {sum(surface.values())} 个；"
                    f"藏干另数（每个记 1，不加权）：{row(hidden)}，共 {sum(hidden.values())} 个。个数不等于力量，也不等于喜忌。")}
