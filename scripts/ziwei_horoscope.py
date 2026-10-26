"""流年斗君 -> 流月 -> 流日 -> 流时: the palace each layer occupies on one date.

《紫微斗数全书》卷二安斗君诀 fixes the 流年正月 palace (ziwei:c002:p0064). Each
later month moves one palace clockwise; 流日 counts the lunar day on from that
month's palace, and 流时 counts the hour branch on from that day's palace.
Stems for each layer's 四化 follow the lunar calendar: 年 from 正月初一, 月 by
五虎遁 on the lunar month (闰月十五日后作下月, the same rule the natal chart
uses), 日 and 时 from the calendar under the chart's 晚子时 convention.

Placing a layer is arithmetic. What a palace means for that month, day or hour
is interpretation this module does not make.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from utils import DIZHI, TIANGAN, hour_branch_index
from ziwei_palaces import SI_HUA, calc_dou_jun

# 五虎遁: the stem of 寅月 for each year stem.
TIGER = {'甲': '丙', '己': '丙', '乙': '戊', '庚': '戊', '丙': '庚', '辛': '庚',
         '丁': '壬', '壬': '壬', '戊': '甲', '癸': '甲'}
DOU_JUN_PASSAGE = 'ziwei:c002:p0064'
CONVENTIONS = (
    '流年按农历正月初一换年；立春换年的流派会在正月初一与立春之间得到不同流年。',
    '流月用斗君起正月顺行；闰月十五日及以前算本月，十五日后算下月，与本命盘同一取法。',
    '流月天干按农历月序五虎遁；按节气定月的流派在月初前后可能不同。',
    '流日从流月宫起初一顺数农历日；流时从流日宫起子时顺数。',
    '晚子时（23:00 后）按本盘 --sect：1 整体推进到次日，2 仍算当日。',
)
LIMIT = '只定各层所在宫位与四化星，不解释当月、当日、当时吉凶，也不推出具体事件。'


def _lunar(target: datetime, sect: int) -> tuple[Any, date]:
    from lunar_python import Solar
    day = target.date()
    hour = target.hour
    if sect == 1 and hour == 23:
        day, hour = day + timedelta(days=1), 0
    return Solar.fromYmdHms(day.year, day.month, day.day, hour, target.minute, 0).getLunar(), day


def _layer(name: str, stem: str, branch: str, palace_branch: str, palaces: dict[str, str]) -> dict:
    return {'layer': name, 'ganzhi': stem + branch, 'palace_branch': palace_branch,
            'natal_palace': palaces.get(palace_branch), 'transformations': dict(SI_HUA.get(stem, {}))}


def horoscope_layers(target: datetime, *, birth_month: int, birth_hour: int,
                     palaces: list[dict], sect: int = 2, include_hour: bool = True) -> dict:
    """Layers for ``target`` (local clock). ``birth_month`` is the chart's effective lunar month."""
    natal = {p['branch']: p['name'] for p in palaces}
    lunar, civil_day = _lunar(target, sect)
    year_stem, year_branch = lunar.getYearGan(), lunar.getYearZhi()
    raw_month, lunar_day = lunar.getMonth(), lunar.getDay()
    month = abs(raw_month)
    effective = month % 12 + 1 if raw_month < 0 and lunar_day > 15 else month
    dou_jun = calc_dou_jun(year_branch, birth_month, birth_hour)
    month_at = (DIZHI.index(dou_jun) + effective - 1) % 12
    day_at = (month_at + lunar_day - 1) % 12
    month_stem = TIANGAN[(TIANGAN.index(TIGER[year_stem]) + effective - 1) % 10]
    month_branch = DIZHI[(DIZHI.index('寅') + effective - 1) % 12]
    day_ganzhi = lunar.getDayInGanZhiExact2()
    layers = {
        'liu_nian': _layer('流年', year_stem, year_branch, year_branch, natal),
        'liu_yue': {**_layer('流月', month_stem, month_branch, DIZHI[month_at], natal), 'lunar_month': effective},
        'liu_ri': {**_layer('流日', day_ganzhi[0], day_ganzhi[1], DIZHI[day_at], natal), 'lunar_day': lunar_day},
        'liu_shi': None,
    }
    if include_hour:
        hour_ganzhi = lunar.getTimeInGanZhi()
        hour_at = DIZHI[(day_at + hour_branch_index(target.hour)) % 12]
        layers['liu_shi'] = _layer('流时', hour_ganzhi[0], hour_ganzhi[1], hour_at, natal)
    return {
        'target': {'clock': target.strftime('%Y-%m-%d %H:%M') if include_hour else target.strftime('%Y-%m-%d'),
                   'calendar_day_used': civil_day.isoformat(),
                   'lunar': {'year_ganzhi': year_stem + year_branch, 'month': month,
                             'is_leap_month': raw_month < 0, 'effective_month': effective, 'day': lunar_day}},
        'dou_jun': {'branch': dou_jun, 'basis': '流年太岁宫起正月，逆数至生月；生月宫起子，顺数至生时',
                    'passage_id': DOU_JUN_PASSAGE},
        **layers,
        'conventions': list(CONVENTIONS),
        'limit': LIMIT,
    }


def parse_target(day: str, clock: str | None) -> tuple[datetime, bool]:
    """``YYYY-MM-DD`` plus optional ``HH:MM``; the flag says whether 流时 was asked for."""
    parsed = date.fromisoformat(day)
    if clock is None:
        return datetime(parsed.year, parsed.month, parsed.day, 12), False
    hour, minute = (int(x) for x in clock.split(':', 1))
    return datetime(parsed.year, parsed.month, parsed.day, hour, minute), True
