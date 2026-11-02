"""《遁甲演义》转盘：天盘奇仪、九星、八门随值符值使沿八宫环整体转动，中五寄坤二，八神阳顺阴逆。

书证（四库本《遁甲演义》）：
- 甲辰在五，天禽为直符，死门为直使，「甲辰五乃寄在坤二宫」（dunjia:c001:p0007）。
- 中五之仪随坤二同转：阳三局丙寅时「六庚在五宫寄二宫……即得天禽为六庚下临六己于四宫」（c002:p0031）；
  地盘中五之干也在坤二之下：阴三局丙在五，戊寅时「六庚下临六丙于二宫」（c002:p0034）。
- 八神：阳遁直符前一螣蛇、前二太阴、前三六合，后一九天、后二九地；阴遁反向（c002:p0005）。
- 值使：自旬首原宫沿一至九宫阳顺阴逆数到本时，数到中五寄坤二（c002:p0024「直使在五宫寄坤二宫」）。

与默认的《元灵经》核心（qimen_cast.source_core）不是同一部书：元灵经卷一例有「天任加中」，不寄坤。
两法分列，不混作一盘。
"""
from __future__ import annotations

from qimen_dingju import zhi_shi_position
from qimen_tables import EIGHT_SHEN_ORDER, MEN_HOME_PALACE, PALACE_INFO, STAR_HOME_PALACE, XUN_HEADS
from utils import jiazi_index

RING = [1, 8, 3, 4, 9, 2, 7, 6]  # 坎艮震巽离坤兑乾，顺时针
CENTRE_TO = 2
HOME_STAR = {p: s for s, p in STAR_HOME_PALACE.items() if p != 5}
HOME_DOOR = {p: d for d, p in MEN_HOME_PALACE.items()}
SOURCES = ['dunjia:c001:p0007', 'dunjia:c002:p0005', 'dunjia:c002:p0024', 'dunjia:c002:p0031',
           'dunjia:c002:p0034']


def _ring(palace: int) -> int:
    return CENTRE_TO if palace == 5 else palace


def hidden_stem(ganzhi: str) -> str:
    """甲遁于本旬六仪；其余干照原样。"""
    if ganzhi[0] != '甲':
        return ganzhi[0]
    return XUN_HEADS[jiazi_index(ganzhi[0], ganzhi[1]) // 10][1]


def earth_under(earth: dict[int, str]) -> dict[int, list[str]]:
    """八宫地盘；中五之干寄在坤二之下。"""
    under = {p: [earth[p]] for p in RING}
    under[CENTRE_TO] = [earth[CENTRE_TO], earth[5]]
    return under


def plate(earth: dict[int, str], ju_type: str, hour_gz: str) -> dict:
    if ju_type not in ('阳遁', '阴遁') or len(hour_gz) != 2:
        raise ValueError('须给阳遁/阴遁与两字时干支')
    head, yi = XUN_HEADS[jiazi_index(hour_gz[0], hour_gz[1]) // 10]
    origin = next(p for p, s in earth.items() if s == yi)
    target = next(p for p, s in earth.items() if s == hidden_stem(hour_gz))
    shift = (RING.index(_ring(target)) - RING.index(_ring(origin))) % 8
    under = earth_under(earth)
    heaven = {RING[(i + shift) % 8]: under[p] for i, p in enumerate(RING)}
    stars = {RING[(i + shift) % 8]: [HOME_STAR[p]] + (['天禽'] if p == CENTRE_TO else [])
             for i, p in enumerate(RING)}
    raw, landed = zhi_shi_position(origin, hour_gz, ju_type)
    door_shift = (RING.index(landed) - RING.index(_ring(origin))) % 8
    doors = {RING[(i + door_shift) % 8]: HOME_DOOR[p] for i, p in enumerate(RING)}
    zhi_fu_palace = _ring(target)
    sign = 1 if ju_type == '阳遁' else -1
    start = RING.index(zhi_fu_palace)
    gods = {RING[(start + sign * k) % 8]: name for k, name in enumerate(EIGHT_SHEN_ORDER)}
    return {
        'method': 'dunjia-zhuanpan', 'ju_type': ju_type, 'hour': hour_gz,
        'earth': under, 'earth_centre': earth[5], 'heaven': heaven, 'stars': stars, 'doors': doors, 'gods': gods,
        'xun_head': head, 'xun_yi': yi,
        'zhi_fu': {'origin_palace': origin, 'palace': zhi_fu_palace, 'stem': yi,
                   'star': '天禽' if origin == 5 else HOME_STAR[origin]},
        'zhi_shi': {'raw_palace': raw, 'palace': landed, 'door': HOME_DOOR[_ring(origin)]},
        'star_shift': shift, 'door_shift': door_shift, 'sources': SOURCES,
    }


def palace_rows(pl: dict) -> list[dict]:
    """Nine palace records in qimen_cast's shape; 中五 only carries its earth stem."""
    rows = []
    for p in range(1, 10):
        info = PALACE_INFO[p]
        if p == 5:
            rows.append({'index': 5, 'palace': info['palace'], 'direction': info['direction'], 'wuxing': info['wuxing'],
                         'earth_yi_qi': pl['earth_centre'], 'heaven_yi_qi': None, 'men': None, 'star': None, 'shen': None,
                         'notes': '中五寄坤二：地盘之干与天禽随坤二宫同转'})
            continue
        rows.append({'index': p, 'palace': info['palace'], 'direction': info['direction'], 'wuxing': info['wuxing'],
                     'earth_yi_qi': '、'.join(pl['earth'][p]), 'heaven_yi_qi': '、'.join(pl['heaven'][p]),
                     'men': pl['doors'][p], 'star': '、'.join(pl['stars'][p]), 'shen': pl['gods'][p],
                     'notes': '含中五寄来之干' if len(pl['earth'][p]) > 1 or len(pl['heaven'][p]) > 1 else ''})
    return rows
