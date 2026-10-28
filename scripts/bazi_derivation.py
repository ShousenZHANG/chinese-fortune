"""How each pillar and the luck start were reached, in steps a user can redo.

Every input below is already in chart_facts; this only lays it out in the order
a person checks a chart by hand: clock time and zone, the solar-term window for
year and month, the true-solar correction, the day boundary, the hour stem by
五鼠遁, and the luck direction and start. Nothing is recomputed here, so the
steps cannot disagree with the chart they explain.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from utils import hour_branch, parse_iso

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
                   f"{tst.get('clock_time')} → {tst.get('true_solar_time')}。"}


def _day_step(facts: dict) -> dict:
    tst = facts.get('true_solar_time') or {}
    sect = facts.get('sect') or {}
    if _gz(facts, 'day') == '未定':
        return {'step': '日柱', 'result': '未定', 'how': UNDECIDED}
    return {'step': '日柱', 'result': _gz(facts, 'day'),
            'how': f"取 {tst.get('effective_date', '出生日')} 这一天的干支；晚子时口径：{sect.get('label', '默认')}。"}


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
                   f"换算口径：{qi.get('method', '所用算法')}。"}


def derivation_steps(facts: dict) -> list[dict]:
    steps = [_clock_step(facts), _term_step(facts), _solar_step(facts), _day_step(facts), _hour_step(facts)]
    luck = _luck_step(facts)
    return steps + ([luck] if luck else [])

