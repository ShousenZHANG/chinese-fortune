"""流年斗君 -> 流月 -> 流日 -> 流时: the palace each layer occupies on one date.

《紫微斗数全书》卷二安斗君诀 fixes the 流年正月 palace (ziwei:c002:p0064). Each
later month moves one palace clockwise; 流日 counts the lunar day on from that
month's palace, and 流时 counts the hour branch on from that day's palace.
The selected year boundary supplies the annual stem and branch. 月 uses
五虎遁 on that year stem and the lunar month (闰月十五日后作下月). 日 and 时
follow the calendar under the chart's 晚子时 convention. Nominal age always
uses lunar years. Each active layer's 将前 and 岁前 gods follow its own branch
under a separately cited modern-software convention.

Placing a layer is arithmetic. What a palace means for that month, day or hour
is interpretation this module does not make.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from utils import DIZHI, TIANGAN, hour_branch_index
from ziwei_gods import layer_gods_basis, year_gods
from ziwei_palaces import SI_HUA, calc_dou_jun
from ziwei_stars import KUI_YUE_VARIANTS, LU_CUN, TIAN_KUI, TIAN_MA, TIAN_YUE, _sanhe_set

# 五虎遁: the stem of 寅月 for each year stem.
TIGER = {'甲': '丙', '己': '丙', '乙': '戊', '庚': '戊', '丙': '庚', '辛': '庚',
         '丁': '壬', '壬': '壬', '戊': '甲', '癸': '甲'}
# 运限流曜的昌曲按该层天干 (iztro 口径), 与本命按时辰安的文昌文曲不同。
LAYER_CHANG = dict(zip(TIANGAN, '巳午申酉申酉亥子寅卯'))
LAYER_QU = dict(zip(TIANGAN, '酉申午巳午巳卯寅子亥'))
DOU_JUN_PASSAGE = 'ziwei:c002:p0064'
CONVENTIONS = (
    '流月用斗君起正月顺行；闰月十五日及以前算本月，十五日后算下月。目标运限沿用此口径，本命盘另按 --leap-month 选择。',
    '流月天干按农历月序五虎遁；按节气定月的流派在月初前后可能不同。',
    '流日从流月宫起初一顺数农历日；流时从流日宫起子时顺数。',
    '晚子时（23:00 后）按本盘 --sect：1 整体推进到次日；2 流日与宫位仍算当日，流时时干按历法库取次日干'
    '（与八字同一口径；iztro 默认按当日起时干，流时干支与四化会不同）。',
    '原书只直接记载斗君起法（安斗君诀）；流月逐月顺行、流日、流时的起法是现代排盘通行口径，所选《全书》转录未载明。',
    '各层流曜（运/流/月/日/时 + 禄羊陀魁钺昌曲马鸾喜）：禄羊陀魁钺昌曲按该层天干，马鸾喜按该层地支；流年另有年解。'
    '这是 iztro 等排盘软件的通行口径，所选《全书》转录未载。',
    '各活动层的将前、岁前十二神按该层干支的地支安置，采用 Renhuai 固定版本的现代软件口径；'
    '来源和岁前第七位的大耗/岁破名称差异见各层 twelve_gods_basis，不归于安斗君诀。',
    '大限层按虚岁（目标农历年减出生农历年加一）找当前大限；未到第一个大限的起运岁数时为 null。',
)
YEAR_CONVENTIONS = {
    'lunar-new-year': '流年按农历正月初一换年；农历日期仍依本盘晚子时取日。',
    'lichun': '流年按原始目标钟面时刻的立春交节换年，先于晚子时合成次日处理；'
              '流年干支、四化、斗君、流曜、年解与十二神及流月五虎遁都用这一年干支。',
}
LIMIT = '只定各层所在宫位与四化星，不解释当月、当日、当时吉凶，也不推出具体事件。'


def _lunar(target: datetime, sect: int) -> tuple[Any, date]:
    from lunar_python import Solar
    day = target.date()
    hour = target.hour
    if sect == 1 and hour == 23:
        day, hour = day + timedelta(days=1), 0
    return Solar.fromYmdHms(day.year, day.month, day.day, hour, target.minute, target.second).getLunar(), day


def layer_stars(prefix: str, stem: str, branch: str, kui_yue: str = 'tongxing') -> dict[str, str]:
    """One layer's 流曜, e.g. prefix '流' gives 流禄 流羊 … 流喜."""
    lu = DIZHI.index(LU_CUN[stem])
    kui, yue = KUI_YUE_VARIANTS[kui_yue].get(stem, (TIAN_KUI[stem], TIAN_YUE[stem]))
    luan = (3 - DIZHI.index(branch)) % 12
    return {prefix + '禄': DIZHI[lu], prefix + '羊': DIZHI[(lu + 1) % 12], prefix + '陀': DIZHI[(lu - 1) % 12],
            prefix + '魁': kui, prefix + '钺': yue, prefix + '昌': LAYER_CHANG[stem], prefix + '曲': LAYER_QU[stem],
            prefix + '马': TIAN_MA[_sanhe_set(branch)], prefix + '鸾': DIZHI[luan],
            prefix + '喜': DIZHI[(luan + 6) % 12]}


def _decade(da_xian: list[dict] | None, age: int, palaces: dict[str, str], kui_yue: str) -> dict | None:
    step = next((s for s in da_xian or [] if s['start_age'] <= age <= s['end_age']), None)
    if step is None:
        return None
    stem, branch = step['palace_stem'], step['palace_branch']
    out = {'layer': '大限', 'ganzhi': stem + branch, 'palace_branch': branch, 'natal_palace': palaces.get(branch),
           'age_range': step['age_range'], 'nominal_age': age, 'age_basis': 'lunar-new-year',
           'stars': layer_stars('运', stem, branch, kui_yue),
           'twelve_gods': year_gods(branch), 'twelve_gods_basis': layer_gods_basis(branch)}
    if 'transformations' in step:
        out['transformations'] = dict(step['transformations'])
    return out


def _layer(name: str, stem: str, branch: str, palace_branch: str, palaces: dict[str, str],
           table: dict[str, dict[str, str]]) -> dict:
    return {'layer': name, 'ganzhi': stem + branch, 'palace_branch': palace_branch,
            'natal_palace': palaces.get(palace_branch), 'transformations': dict(table.get(stem, {})),
            'twelve_gods': year_gods(branch), 'twelve_gods_basis': layer_gods_basis(branch)}


def horoscope_layers(target: datetime, *, birth_month: int, birth_hour: int,
                     palaces: list[dict], sect: int = 2, include_hour: bool = True,
                     sihua: dict[str, dict[str, str]] | None = None, da_xian: list[dict] | None = None,
                     birth_lunar_year: int | None = None, kui_yue: str = 'tongxing',
                     year_divide: str = 'lunar-new-year', star_branches: dict[str, str] | None = None) -> dict:
    """Layers for ``target`` (local clock). ``birth_month`` is the chart's effective lunar month."""
    natal = {p['branch']: p['name'] for p in palaces}
    table = sihua or SI_HUA
    lunar, civil_day = _lunar(target, sect)
    lichun_clock = None
    if year_divide == 'lichun':
        original_lunar, _ = _lunar(target, 2)
        year_stem, year_branch = original_lunar.getYearGanExact(), original_lunar.getYearZhiExact()
        lichun_clock = original_lunar.getJieQiTable()['立春'].toYmdHms()
    else:
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
    age = lunar.getYear() - birth_lunar_year + 1 if birth_lunar_year else 0
    year_stars = {**layer_stars('流', year_stem, year_branch, kui_yue),
                  '年解': DIZHI[(10 - DIZHI.index(year_branch)) % 12]}
    layers = {
        'da_xian': _decade(da_xian, age, natal, kui_yue),
        'liu_nian': {**_layer('流年', year_stem, year_branch, year_branch, natal, table),
                     'stars': year_stars},
        'liu_yue': {**_layer('流月', month_stem, month_branch, DIZHI[month_at], natal, table), 'lunar_month': effective,
                    'stars': layer_stars('月', month_stem, month_branch, kui_yue)},
        'liu_ri': {**_layer('流日', day_ganzhi[0], day_ganzhi[1], DIZHI[day_at], natal, table), 'lunar_day': lunar_day,
                   'stars': layer_stars('日', day_ganzhi[0], day_ganzhi[1], kui_yue)},
        'liu_shi': None,
    }
    if include_hour:
        hour_ganzhi = lunar.getTimeInGanZhi()
        hour_at = DIZHI[(day_at + hour_branch_index(target.hour)) % 12]
        layers['liu_shi'] = {**_layer('流时', hour_ganzhi[0], hour_ganzhi[1], hour_at, natal, table),
                             'stars': layer_stars('时', hour_ganzhi[0], hour_ganzhi[1], kui_yue)}
    if star_branches:
        for layer in layers.values():
            if layer and layer.get('transformations'):
                layer['transformation_palaces'] = transformation_palaces(layer['transformations'], star_branches, natal)
    return {
        'target': {'clock': target.strftime('%Y-%m-%d %H:%M') if include_hour else target.strftime('%Y-%m-%d'),
                   'clock_used': target.isoformat(timespec='seconds' if target.second else 'minutes'),
                   'clock_representative': None if include_hour else '12:00',
                   'calendar_day_used': civil_day.isoformat(),
                   'year_divide': year_divide, 'annual_ganzhi': year_stem + year_branch,
                   'year_boundary_basis': 'original_target_clock' if year_divide == 'lichun' else 'sect_adjusted_lunar_date',
                   'year_boundary_provider': 'lunar_python (随包固定版本)', 'lichun_clock': lichun_clock,
                   'age_basis': 'lunar-new-year', 'nominal_age': age if birth_lunar_year else None,
                   'lunar': {'year': lunar.getYear(), 'year_ganzhi': lunar.getYearInGanZhi(), 'month': month,
                             'is_leap_month': raw_month < 0, 'effective_month': effective, 'day': lunar_day}},
        'dou_jun': {'branch': dou_jun, 'basis': '流年太岁宫起正月，逆数至生月；生月宫起子，顺数至生时',
                    'passage_id': DOU_JUN_PASSAGE},
        **layers,
        'conventions': [YEAR_CONVENTIONS[year_divide], *CONVENTIONS,
                        '选择立春年界只改变流年相关干支，不替换实际农历年月日；虚岁与大限年龄仍按农历正月初一。']
        + (['立春采用随包 lunar_python 的交节秒值，按目标当地历法钟面比较；此 API 不转换目标时区。'
            '固定历算值不保证真实天文误差，不同历算在交节附近可能跨分钟。'] if year_divide == 'lichun' else [])
        + (['只给目标日期时，以该日 12:00 当地钟面作为代表时刻，含交节当日；流时仍为 null。'] if not include_hour else []),
        'limit': LIMIT,
    }


def transformation_palaces(transformations: dict[str, str], star_branches: dict[str, str],
                           natal: dict[str, str]) -> list[dict]:
    """Where each transformed star sits in the natal chart: 化禄太阴在辰（本命某宫）. A star the chart
    does not place (none should be missing) is listed with a null branch rather than dropped."""
    rows = []
    for kind, star in transformations.items():
        branch = star_branches.get(star)
        rows.append({'kind': '化' + kind, 'star': star, 'branch': branch,
                     'natal_palace': natal.get(branch) if branch else None})
    return rows


def parse_target(day: str, clock: str | None) -> tuple[datetime, bool]:
    """``YYYY-MM-DD`` plus optional ``HH:MM``; the flag says whether 流时 was asked for."""
    parsed = date.fromisoformat(day)
    if clock is None:
        return datetime(parsed.year, parsed.month, parsed.day, 12), False
    hour, minute = (int(x) for x in clock.split(':', 1))
    return datetime(parsed.year, parsed.month, parsed.day, hour, minute), True
