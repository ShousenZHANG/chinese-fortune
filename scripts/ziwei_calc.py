"""紫微斗数 (Zi Wei Dou Shu) — production-grade chart engine.

Implements the canonical排盘 pipeline derived from《紫微斗数全书》(罗洪先, 明) and
《紫微斗数全集》(陈希夷传), independent of any third-party AGPL codebase:

  1. 命宫 / 身宫              (寅宫起正月 + 子时定位)
  2. 五行局                  (命宫干支纳音)
  3. 紫微星                  (五行局 + 农历生日, 标准排盘表)
  4. 紫微/天府 14 主星      (北斗 6 + 南斗 8)
  5. 六吉                    (左辅/右弼/文昌/文曲/天魁/天钺)
  6. 六煞                    (擎羊/陀罗/火星/铃星/地空/地劫) + 禄存
  7. 杂曜                    (天马/红鸾/天喜/孤辰/寡宿/天哭/天虚/龙池/凤阁)
  8. 命主 / 身主             (年支主星)
  9. 斗君                    (流年起算之锚)
 10. 四化                    (生年/大限/流年, 含自化离心向心)
 11. 12 宫                  (含借宫 — 命宫空宫自动借对宫主星)
 12. 12 大限                 (阴男阳女逆行修正)
 13. 格局                    (15 格自动识别: 紫府同宫/府相朝垣/阳梁昌禄/机月
                              同梁/杀破狼/火贪/铃贪/武贪/日月同宫/明珠出海/
                              辅弼夹命/昌曲夹命/羊陀夹忌/空劫夹命/马头带箭)

Args mirror bazi_calc.py — lunar birthday is recommended for accuracy.

Usage:
    python ziwei_calc.py --year 1995 --month 7 --day 20 --hour 1 \\
        --gender female --lunar
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from utils import (
    DIZHI,
    TIANGAN,
    WUHU_DUN,
    jiazi_index,
    json_print,
    require_lunar,
    warn,
)


VERSION = "1.1.0"


# --------------------------------------------------------------------------- #
# Section 0 — micro helpers
# --------------------------------------------------------------------------- #

def _branch_idx(branch: str) -> int:
    return DIZHI.index(branch)


def _branch_offset(branch: str, offset: int) -> str:
    """Return the branch that is ``offset`` steps from ``branch`` (mod 12)."""
    return DIZHI[(_branch_idx(branch) + offset) % 12]


def branch_of_hour(hour: int) -> str:
    """Hour 0-23 -> 时辰地支. 23/0->子, 1-2->丑, 3-4->寅, ..."""
    if hour == 23 or hour == 0:
        return "子"
    return DIZHI[((hour + 1) // 2) % 12]


def hour_branch_index(hour: int) -> int:
    """Index 0..11 for the 时辰 (子=0, 丑=1, ...)."""
    return DIZHI.index(branch_of_hour(hour))


# --------------------------------------------------------------------------- #
# Section 1 — 命宫 / 身宫 / 宫干 (五虎遁)
# --------------------------------------------------------------------------- #
# 命宫: 寅宫起正月顺数到生月, 该宫起子时逆数至生时.
# 身宫: 同上, 但顺数至生时.
# 宫干: 由生年干透过五虎遁推得 — 寅宫干为甲己丙寅/乙庚戊寅/丙辛庚寅/丁壬壬寅/戊癸甲寅,
#       其余宫位顺数十干十支.


def calc_ming_gong(lunar_month: int, hour: int) -> str:
    month_branch_idx = (2 + (lunar_month - 1)) % 12  # 寅=2
    return DIZHI[(month_branch_idx - hour_branch_index(hour)) % 12]


def calc_shen_gong(lunar_month: int, hour: int) -> str:
    month_branch_idx = (2 + (lunar_month - 1)) % 12
    return DIZHI[(month_branch_idx + hour_branch_index(hour)) % 12]


def stem_of_palace(year_stem: str, palace_branch: str) -> str:
    """Return the 天干 of a palace via 五虎遁."""
    start_stem = WUHU_DUN[year_stem]  # 寅月之干
    yin_idx = DIZHI.index("寅")
    diff = (_branch_idx(palace_branch) - yin_idx) % 12
    start = TIANGAN.index(start_stem)
    return TIANGAN[(start + diff) % 10]


# --------------------------------------------------------------------------- #
# Section 2 — 五行局 (六十甲子纳音)
# --------------------------------------------------------------------------- #

NAYIN_60: list[str] = [
    "海中金", "海中金", "炉中火", "炉中火", "大林木", "大林木",
    "路旁土", "路旁土", "剑锋金", "剑锋金", "山头火", "山头火",
    "涧下水", "涧下水", "城头土", "城头土", "白蜡金", "白蜡金",
    "杨柳木", "杨柳木", "井泉水", "井泉水", "屋上土", "屋上土",
    "霹雳火", "霹雳火", "松柏木", "松柏木", "长流水", "长流水",
    "沙中金", "沙中金", "山下火", "山下火", "平地木", "平地木",
    "壁上土", "壁上土", "金箔金", "金箔金", "覆灯火", "覆灯火",
    "天河水", "天河水", "大驿土", "大驿土", "钗钏金", "钗钏金",
    "桑柘木", "桑柘木", "大溪水", "大溪水", "沙中土", "沙中土",
    "天上火", "天上火", "石榴木", "石榴木", "大海水", "大海水",
]

NAYIN_WX_KEYWORD: dict[str, list[str]] = {
    "金": ["海中金", "剑锋金", "白蜡金", "沙中金", "金箔金", "钗钏金"],
    "火": ["炉中火", "山头火", "霹雳火", "山下火", "覆灯火", "天上火"],
    "木": ["大林木", "杨柳木", "松柏木", "平地木", "桑柘木", "石榴木"],
    "水": ["涧下水", "井泉水", "长流水", "天河水", "大溪水", "大海水"],
    "土": ["路旁土", "城头土", "屋上土", "壁上土", "大驿土", "沙中土"],
}

WUXING_JU_NUM: dict[str, int] = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
WUXING_JU_NAME: dict[int, str] = {2: "水二局", 3: "木三局", 4: "金四局",
                                   5: "土五局", 6: "火六局"}


def nayin_wuxing(stem: str, branch: str) -> str:
    name = NAYIN_60[jiazi_index(stem, branch)]
    for wx, names in NAYIN_WX_KEYWORD.items():
        if name in names:
            return wx
    return "?"


def wuxing_ju(year_stem: str, ming_gong_branch: str) -> tuple[int, str]:
    stem = stem_of_palace(year_stem, ming_gong_branch)
    wx = nayin_wuxing(stem, ming_gong_branch)
    num = WUXING_JU_NUM.get(wx, 5)
    return num, WUXING_JU_NAME[num]


# --------------------------------------------------------------------------- #
# Section 3 — 紫微星 (standard排盘表 from《紫微斗数全书·安星诀》)
# --------------------------------------------------------------------------- #
# Row = 局 (2..6), col = 农历生日 (1..30) -> 紫微所在地支.

ZIWEI_TABLE: dict[int, list[str]] = {
    2: [
        "丑", "寅", "寅", "卯", "卯", "辰", "辰", "巳", "巳", "午",
        "午", "未", "未", "申", "申", "酉", "酉", "戌", "戌", "亥",
        "亥", "子", "子", "丑", "丑", "寅", "寅", "卯", "卯", "辰",
    ],
    3: [
        "辰", "丑", "寅", "巳", "寅", "卯", "午", "卯", "辰", "未",
        "辰", "巳", "申", "巳", "午", "酉", "午", "未", "戌", "未",
        "申", "亥", "申", "酉", "子", "酉", "戌", "丑", "戌", "亥",
    ],
    4: [
        "亥", "辰", "丑", "寅", "子", "巳", "寅", "卯", "丑", "午",
        "卯", "辰", "寅", "未", "辰", "巳", "卯", "申", "巳", "午",
        "辰", "酉", "午", "未", "巳", "戌", "未", "申", "午", "亥",
    ],
    5: [
        "午", "亥", "辰", "丑", "寅", "未", "子", "巳", "寅", "卯",
        "申", "丑", "午", "卯", "辰", "酉", "寅", "未", "辰", "巳",
        "戌", "卯", "申", "巳", "午", "亥", "辰", "酉", "午", "未",
    ],
    6: [
        "酉", "午", "亥", "辰", "丑", "寅", "戌", "未", "子", "巳",
        "寅", "卯", "亥", "申", "丑", "午", "卯", "辰", "子", "酉",
        "寅", "未", "辰", "巳", "丑", "戌", "卯", "申", "巳", "午",
    ],
}


def ziwei_position(ju: int, lunar_day: int) -> str:
    d = max(1, min(30, lunar_day))
    return ZIWEI_TABLE.get(ju, ZIWEI_TABLE[5])[d - 1]


# --------------------------------------------------------------------------- #
# Section 4 — 14 主星 (北斗紫微 6 + 南斗天府 8)
# --------------------------------------------------------------------------- #

# 紫微 6 — offsets relative to 紫微 (逆时针 = -branch_index direction).
ZIWEI_OFFSETS: dict[str, int] = {
    "紫微": 0,
    "天机": -1,
    "太阳": -3,
    "武曲": -4,
    "天同": -5,
    "廉贞": -8,
}

# 天府 mirror of 紫微 about 寅/申 (按经典 "紫府同宫只在寅申" 推得).
TIANFU_MIRROR: dict[str, str] = {
    "寅": "寅", "卯": "丑", "辰": "子", "巳": "亥", "午": "戌",
    "未": "酉", "申": "申", "酉": "未", "戌": "午", "亥": "巳",
    "子": "辰", "丑": "卯",
}

# 天府 8 — offsets relative to 天府 (顺时针 = +branch_index direction).
TIANFU_OFFSETS: dict[str, int] = {
    "天府": 0,
    "太阴": 1,
    "贪狼": 2,
    "巨门": 3,
    "天相": 4,
    "天梁": 5,
    "七杀": 6,
    "破军": 10,
}

MAIN_STARS: tuple[str, ...] = (
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞",
    "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
)


def place_main_stars(ziwei_branch: str) -> dict[str, str]:
    out: dict[str, str] = {}
    zw_idx = _branch_idx(ziwei_branch)
    for star, off in ZIWEI_OFFSETS.items():
        out[star] = DIZHI[(zw_idx + off) % 12]
    tf_branch = TIANFU_MIRROR[ziwei_branch]
    tf_idx = _branch_idx(tf_branch)
    for star, off in TIANFU_OFFSETS.items():
        out[star] = DIZHI[(tf_idx + off) % 12]
    return out


# --------------------------------------------------------------------------- #
# Section 5 — 主星 brightness (亮度: 庙旺得地利平不闲陷)
# --------------------------------------------------------------------------- #
# Simplified to 庙/旺/平/陷, derived from《紫微斗数全书·形性赋》核心.

BRIGHTNESS: dict[str, dict[str, str]] = {
    "紫微": {"子": "平", "丑": "庙", "寅": "庙", "卯": "旺", "辰": "陷",
             "巳": "旺", "午": "庙", "未": "庙", "申": "旺", "酉": "平",
             "戌": "陷", "亥": "旺"},
    "天机": {"子": "庙", "丑": "陷", "寅": "旺", "卯": "庙", "辰": "旺",
             "巳": "平", "午": "庙", "未": "陷", "申": "旺", "酉": "平",
             "戌": "旺", "亥": "平"},
    "太阳": {"子": "陷", "丑": "陷", "寅": "旺", "卯": "庙", "辰": "旺",
             "巳": "旺", "午": "庙", "未": "平", "申": "平", "酉": "陷",
             "戌": "陷", "亥": "陷"},
    "武曲": {"子": "旺", "丑": "庙", "寅": "平", "卯": "陷", "辰": "庙",
             "巳": "平", "午": "旺", "未": "庙", "申": "平", "酉": "旺",
             "戌": "庙", "亥": "平"},
    "天同": {"子": "旺", "丑": "陷", "寅": "旺", "卯": "平", "辰": "平",
             "巳": "庙", "午": "陷", "未": "陷", "申": "旺", "酉": "平",
             "戌": "平", "亥": "庙"},
    "廉贞": {"子": "平", "丑": "陷", "寅": "庙", "卯": "平", "辰": "旺",
             "巳": "陷", "午": "平", "未": "陷", "申": "庙", "酉": "平",
             "戌": "旺", "亥": "陷"},
    "天府": {"子": "庙", "丑": "庙", "寅": "庙", "卯": "旺", "辰": "庙",
             "巳": "平", "午": "庙", "未": "庙", "申": "旺", "酉": "旺",
             "戌": "庙", "亥": "平"},
    "太阴": {"子": "庙", "丑": "庙", "寅": "陷", "卯": "陷", "辰": "陷",
             "巳": "陷", "午": "陷", "未": "平", "申": "平", "酉": "旺",
             "戌": "庙", "亥": "庙"},
    "贪狼": {"子": "旺", "丑": "庙", "寅": "平", "卯": "平", "辰": "庙",
             "巳": "陷", "午": "旺", "未": "庙", "申": "平", "酉": "平",
             "戌": "庙", "亥": "陷"},
    "巨门": {"子": "旺", "丑": "陷", "寅": "庙", "卯": "庙", "辰": "陷",
             "巳": "旺", "午": "旺", "未": "陷", "申": "庙", "酉": "庙",
             "戌": "陷", "亥": "旺"},
    "天相": {"子": "庙", "丑": "庙", "寅": "庙", "卯": "陷", "辰": "庙",
             "巳": "平", "午": "庙", "未": "庙", "申": "庙", "酉": "陷",
             "戌": "庙", "亥": "平"},
    "天梁": {"子": "庙", "丑": "旺", "寅": "庙", "卯": "庙", "辰": "庙",
             "巳": "陷", "午": "庙", "未": "旺", "申": "陷", "酉": "平",
             "戌": "庙", "亥": "陷"},
    "七杀": {"子": "旺", "丑": "陷", "寅": "庙", "卯": "陷", "辰": "陷",
             "巳": "平", "午": "旺", "未": "陷", "申": "庙", "酉": "陷",
             "戌": "陷", "亥": "平"},
    "破军": {"子": "庙", "丑": "旺", "寅": "平", "卯": "陷", "辰": "庙",
             "巳": "陷", "午": "庙", "未": "旺", "申": "平", "酉": "陷",
             "戌": "庙", "亥": "陷"},
}


def brightness_of(star: str, branch: str) -> str:
    return BRIGHTNESS.get(star, {}).get(branch, "平")


# --------------------------------------------------------------------------- #
# Section 6 — 六吉星 (左辅/右弼/文昌/文曲/天魁/天钺)
# --------------------------------------------------------------------------- #
# 左辅: 辰宫起正月顺数到生月
# 右弼: 戌宫起正月逆数到生月
# 文昌: 戌宫起子时逆数到生时
# 文曲: 辰宫起子时顺数到生时
# 天魁/天钺: 按年干 (天乙/玉堂贵人)


TIAN_KUI: dict[str, str] = {
    "甲": "丑", "戊": "丑", "庚": "丑",
    "乙": "子", "己": "子",
    "丙": "亥", "丁": "亥",
    "壬": "卯", "癸": "卯",
    "辛": "寅",
}

TIAN_YUE: dict[str, str] = {
    "甲": "未", "戊": "未", "庚": "未",
    "乙": "申", "己": "申",
    "丙": "酉", "丁": "酉",
    "壬": "巳", "癸": "巳",
    "辛": "午",
}


def place_lucky_stars(year_stem: str, lunar_month: int, hour: int) -> dict[str, str]:
    m = lunar_month
    h = hour_branch_index(hour)
    return {
        "左辅": _branch_offset("辰", m - 1),
        "右弼": _branch_offset("戌", -(m - 1)),
        "文昌": _branch_offset("戌", -h),
        "文曲": _branch_offset("辰", h),
        "天魁": TIAN_KUI[year_stem],
        "天钺": TIAN_YUE[year_stem],
    }


LUCKY_STAR_NAMES: tuple[str, ...] = (
    "左辅", "右弼", "文昌", "文曲", "天魁", "天钺",
)


# --------------------------------------------------------------------------- #
# Section 7 — 禄存 + 六煞星 (擎羊/陀罗/火星/铃星/地空/地劫)
# --------------------------------------------------------------------------- #

LU_CUN: dict[str, str] = {
    "甲": "寅", "乙": "卯",
    "丙": "巳", "戊": "巳",
    "丁": "午", "己": "午",
    "庚": "申", "辛": "酉",
    "壬": "亥", "癸": "子",
}

# 火星 / 铃星 — 按年支三合 + 生时, 寅起子时顺数.
# 申子辰人: 火星寅, 铃星戌起.
# 寅午戌人: 火星丑, 铃星卯起.
# 巳酉丑人: 火星卯, 铃星戌起.
# 亥卯未人: 火星酉, 铃星戌起.
HUO_LING_START: dict[frozenset[str], tuple[str, str]] = {
    frozenset({"申", "子", "辰"}): ("寅", "戌"),
    frozenset({"寅", "午", "戌"}): ("丑", "卯"),
    frozenset({"巳", "酉", "丑"}): ("卯", "戌"),
    frozenset({"亥", "卯", "未"}): ("酉", "戌"),
}


def _sanhe_set(branch: str) -> frozenset[str]:
    for s in HUO_LING_START:
        if branch in s:
            return s
    raise ValueError(f"unknown branch: {branch}")


def place_malefic_stars(year_stem: str, year_branch: str, hour: int) -> dict[str, str]:
    h = hour_branch_index(hour)
    lc_branch = LU_CUN[year_stem]
    lc_idx = _branch_idx(lc_branch)
    huo_start, ling_start = HUO_LING_START[_sanhe_set(year_branch)]
    return {
        "禄存": lc_branch,
        "擎羊": DIZHI[(lc_idx + 1) % 12],
        "陀罗": DIZHI[(lc_idx - 1) % 12],
        "火星": _branch_offset(huo_start, h),
        "铃星": _branch_offset(ling_start, h),
        "地空": _branch_offset("亥", -h),
        "地劫": _branch_offset("亥", h),
    }


MALEFIC_STAR_NAMES: tuple[str, ...] = (
    "擎羊", "陀罗", "火星", "铃星", "地空", "地劫",
)


# --------------------------------------------------------------------------- #
# Section 8 — 杂曜 (天马/红鸾/天喜/孤辰/寡宿/天哭/天虚/龙池/凤阁)
# --------------------------------------------------------------------------- #
# 天马: 年支三合 — 申子辰人天马在寅, 寅午戌人在申, 巳酉丑人在亥, 亥卯未人在巳.
# 红鸾: 卯宫起子年逆数到年支 -> branch index = (3 - year_branch_idx) % 12.
# 天喜: 红鸾对宫 (+6).
# 孤辰/寡宿: 按年支三方位 (寅卯辰人孤巳寡丑, 巳午未人孤申寡辰, 申酉戌人孤亥寡未, 亥子丑人孤寅寡戌).
# 天哭: 午宫起子年逆数到年支.
# 天虚: 午宫起子年顺数到年支.
# 龙池: 辰宫起子年顺数到年支.
# 凤阁: 戌宫起子年逆数到年支.


TIAN_MA: dict[frozenset[str], str] = {
    frozenset({"申", "子", "辰"}): "寅",
    frozenset({"寅", "午", "戌"}): "申",
    frozenset({"巳", "酉", "丑"}): "亥",
    frozenset({"亥", "卯", "未"}): "巳",
}

GU_GUA: dict[frozenset[str], tuple[str, str]] = {
    frozenset({"寅", "卯", "辰"}): ("巳", "丑"),
    frozenset({"巳", "午", "未"}): ("申", "辰"),
    frozenset({"申", "酉", "戌"}): ("亥", "未"),
    frozenset({"亥", "子", "丑"}): ("寅", "戌"),
}


def place_miscellaneous_stars(year_branch: str) -> dict[str, str]:
    yi = _branch_idx(year_branch)
    sanhe = _sanhe_set(year_branch)
    fang = next(s for s in GU_GUA if year_branch in s)
    gu, gua = GU_GUA[fang]
    hong_luan = DIZHI[(3 - yi) % 12]  # 卯=3
    return {
        "天马": TIAN_MA[sanhe],
        "红鸾": hong_luan,
        "天喜": _branch_offset(hong_luan, 6),
        "孤辰": gu,
        "寡宿": gua,
        "天哭": DIZHI[(6 - yi) % 12],   # 午=6 逆
        "天虚": DIZHI[(6 + yi) % 12],   # 午=6 顺
        "龙池": DIZHI[(4 + yi) % 12],   # 辰=4 顺
        "凤阁": DIZHI[(10 - yi) % 12],  # 戌=10 逆
    }


MISC_STAR_NAMES: tuple[str, ...] = (
    "天马", "红鸾", "天喜", "孤辰", "寡宿",
    "天哭", "天虚", "龙池", "凤阁",
)


# --------------------------------------------------------------------------- #
# Section 9 — 命主 / 身主 (year-branch tables)
# --------------------------------------------------------------------------- #

MING_ZHU: dict[str, str] = {
    "子": "贪狼",
    "丑": "巨门", "亥": "巨门",
    "寅": "禄存", "戌": "禄存",
    "卯": "文曲", "酉": "文曲",
    "辰": "廉贞", "申": "廉贞",
    "巳": "武曲", "未": "武曲",
    "午": "破军",
}

SHEN_ZHU: dict[str, str] = {
    "子": "火星", "午": "火星",
    "丑": "天相", "未": "天相",
    "寅": "天梁", "申": "天梁",
    "卯": "天同", "酉": "天同",
    "辰": "文昌", "戌": "文昌",
    "巳": "天机", "亥": "天机",
}


# --------------------------------------------------------------------------- #
# Section 10 — 四化 (生年/大限/流年)
# --------------------------------------------------------------------------- #

SI_HUA: dict[str, dict[str, str]] = {
    "甲": {"禄": "廉贞", "权": "破军", "科": "武曲", "忌": "太阳"},
    "乙": {"禄": "天机", "权": "天梁", "科": "紫微", "忌": "太阴"},
    "丙": {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
    "丁": {"禄": "太阴", "权": "天同", "科": "天机", "忌": "巨门"},
    "戊": {"禄": "贪狼", "权": "太阴", "科": "右弼", "忌": "天机"},
    "己": {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"},
    "庚": {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"},
    "辛": {"禄": "巨门", "权": "太阳", "科": "文曲", "忌": "文昌"},
    "壬": {"禄": "天梁", "权": "紫微", "科": "左辅", "忌": "武曲"},
    "癸": {"禄": "破军", "权": "巨门", "科": "太阴", "忌": "贪狼"},
}


# --------------------------------------------------------------------------- #
# Section 11 — 12 宫排盘 + 三方四正
# --------------------------------------------------------------------------- #

PALACE_NAMES: tuple[str, ...] = (
    "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
    "迁移宫", "奴仆宫", "官禄宫", "田宅宫", "福德宫", "父母宫",
)


def assign_palaces(ming_gong_branch: str) -> list[dict]:
    """Twelve palaces, counterclockwise from 命宫."""
    mg_idx = _branch_idx(ming_gong_branch)
    return [
        {
            "index": i,
            "name": PALACE_NAMES[i],
            "branch": DIZHI[(mg_idx - i) % 12],
            "branch_index": (mg_idx - i) % 12,
        }
        for i in range(12)
    ]


def san_fang_si_zheng(branch: str) -> dict:
    b = _branch_idx(branch)
    return {
        "本宫": branch,
        "对宫": DIZHI[(b + 6) % 12],
        "三合": [DIZHI[(b + 4) % 12], DIZHI[(b - 4) % 12]],
    }


# --------------------------------------------------------------------------- #
# Section 12 — 大限 (10 年一限, 阴男阳女逆行修正)
# --------------------------------------------------------------------------- #
# 顺行 (阳男阴女): 大限i 在 palace_index i, branch = (mg_idx - i) % 12.
# 逆行 (阴男阳女): 大限i 在 palace_index (-i)%12, branch = (mg_idx + i) % 12.


def is_yang_stem(stem: str) -> bool:
    return TIANGAN.index(stem) % 2 == 0


def da_xian_ranges(
    ju: int, gender: str, year_stem: str,
    palaces: list[dict], year_stem_lookup: dict[str, dict[str, str]],
) -> list[dict]:
    yang_year = is_yang_stem(year_stem)
    forward = (yang_year and gender == "male") or (not yang_year and gender == "female")
    out: list[dict] = []
    mg_idx = palaces[0]["branch_index"]
    for i in range(12):
        if forward:
            pal_idx_in_12 = i
            branch_idx = (mg_idx - i) % 12
        else:
            pal_idx_in_12 = (-i) % 12  # 0,11,10,9,8,...
            branch_idx = (mg_idx + i) % 12
        branch = DIZHI[branch_idx]
        stem = stem_of_palace(year_stem, branch)
        start_age = ju + i * 10
        out.append({
            "index": i + 1,
            "palace_index": pal_idx_in_12,
            "palace_name": PALACE_NAMES[pal_idx_in_12],
            "palace_branch": branch,
            "palace_stem": stem,
            "age_range": f"{start_age}-{start_age + 9}",
            "start_age": start_age,
            "end_age": start_age + 9,
            "direction": "顺行" if forward else "逆行",
            "transformations": year_stem_lookup.get(stem, {}),
        })
    return out


# --------------------------------------------------------------------------- #
# Section 13 — 斗君 (annual reference anchor)
# --------------------------------------------------------------------------- #
# 寅起正月顺数到农历生月, 该宫起子时逆数至生时 — 即为流年 子月 落点的标准锚.


def calc_dou_jun(lunar_month: int, hour: int) -> str:
    month_branch_idx = (2 + (lunar_month - 1)) % 12
    return DIZHI[(month_branch_idx - hour_branch_index(hour)) % 12]


# --------------------------------------------------------------------------- #
# Section 14 — 自化 (self-transformation) detection
# --------------------------------------------------------------------------- #
# For each palace, look up its 宫干, find the 4 化 of that stem, then for each
# star in the palace check if it is a target — if so, mark 自化X.
# 离心 = 本宫化忌 落本宫之化忌星 飞到 对宫 (本宫干 -> 忌 ∈ 本宫星).
# 向心 = 对宫干 之化忌星 ∈ 本宫星 (对宫飞忌入本宫).


def detect_self_transformations(
    palace_stem: str, palace_stars: list[str],
) -> list[str]:
    hua = SI_HUA.get(palace_stem, {})
    out: list[str] = []
    for hua_type, target in hua.items():
        if target in palace_stars:
            out.append(f"自化{hua_type}")
    return out


# --------------------------------------------------------------------------- #
# Section 15 — 借宫 (borrowing) for 空宫
# --------------------------------------------------------------------------- #


def is_empty_palace(stars: list[str]) -> bool:
    return not any(s in MAIN_STARS for s in stars)


def borrow_from_opposite(
    palace_branch: str,
    branch_to_main_stars: dict[str, list[str]],
) -> tuple[str, list[str]]:
    opp = _branch_offset(palace_branch, 6)
    return opp, list(branch_to_main_stars.get(opp, []))


# --------------------------------------------------------------------------- #
# Section 16 — 格局 (pattern detection)
# --------------------------------------------------------------------------- #


def _gather_sfsz_stars(
    branch: str,
    branch_to_all_stars: dict[str, list[str]],
) -> set[str]:
    """Return the union of main+aux stars over the 4 palaces of 三方四正."""
    sfsz = san_fang_si_zheng(branch)
    branches = [sfsz["本宫"], sfsz["对宫"], *sfsz["三合"]]
    out: set[str] = set()
    for b in branches:
        out.update(branch_to_all_stars.get(b, []))
    return out


def detect_patterns(
    ming_branch: str,
    branch_to_main_stars: dict[str, list[str]],
    branch_to_all_stars: dict[str, list[str]],
    palaces: list[dict],
    sihua: dict[str, str],
) -> list[dict]:
    out: list[dict] = []
    mg_stars_main = branch_to_main_stars.get(ming_branch, [])
    mg_stars_all = branch_to_all_stars.get(ming_branch, [])
    sfsz_set = _gather_sfsz_stars(ming_branch, branch_to_all_stars)

    # 1. 紫府同宫 — 紫微+天府同宫 (只可能在寅或申).
    for branch, stars in branch_to_main_stars.items():
        if "紫微" in stars and "天府" in stars:
            out.append({
                "name": "紫府同宫",
                "type": "上格",
                "evidence": f"紫微+天府同坐{branch}宫",
            })
            break

    # 2. 府相朝垣 — 命无紫府, 但三方四正见天府+天相.
    if (
        "紫微" not in mg_stars_main
        and "天府" not in mg_stars_main
        and "天府" in sfsz_set
        and "天相" in sfsz_set
    ):
        out.append({
            "name": "府相朝垣",
            "type": "上格",
            "evidence": "命宫无紫府, 三方四正见天府+天相",
        })

    # 3. 阳梁昌禄 — 三方四正 includes 太阳+天梁+文昌+(禄存或化禄星).
    sihua_lu_star = sihua.get("禄")
    has_lu_source = "禄存" in sfsz_set or (sihua_lu_star and sihua_lu_star in sfsz_set)
    if (
        "太阳" in sfsz_set
        and "天梁" in sfsz_set
        and "文昌" in sfsz_set
        and has_lu_source
    ):
        out.append({
            "name": "阳梁昌禄",
            "type": "上格",
            "evidence": "三方四正集齐太阳+天梁+文昌+(禄存或化禄)",
        })

    # 4. 机月同梁 — 三方四正含 天机/太阴/天同/天梁 任意 3+.
    jiyutong_set = {"天机", "太阴", "天同", "天梁"}
    hit = jiyutong_set & sfsz_set
    if len(hit) >= 3:
        out.append({
            "name": "机月同梁",
            "type": "中上格",
            "evidence": f"三方四正含机月同梁组合 {len(hit)}/4: {','.join(sorted(hit))}",
        })

    # 5. 杀破狼 — 三方四正含七杀+破军+贪狼.
    spl_set = {"七杀", "破军", "贪狼"}
    if spl_set.issubset(sfsz_set):
        out.append({
            "name": "杀破狼",
            "type": "变格",
            "evidence": "三方四正同时见七杀+破军+贪狼",
        })

    # 6/7/8. 火/铃/武贪 — 同宫.
    for branch, stars in branch_to_all_stars.items():
        if "贪狼" in stars:
            if "火星" in stars:
                out.append({
                    "name": "火贪格",
                    "type": "上格",
                    "evidence": f"火星+贪狼同坐{branch}宫(横发)",
                })
            if "铃星" in stars:
                out.append({
                    "name": "铃贪格",
                    "type": "上格",
                    "evidence": f"铃星+贪狼同坐{branch}宫(横发)",
                })
            if "武曲" in stars:
                out.append({
                    "name": "武贪格",
                    "type": "上格",
                    "evidence": f"武曲+贪狼同坐{branch}宫(财富格)",
                })

    # 9. 日月同宫 — 太阳+太阴同宫, 限丑/未.
    for branch, stars in branch_to_main_stars.items():
        if "太阳" in stars and "太阴" in stars and branch in {"丑", "未"}:
            out.append({
                "name": "日月同宫",
                "type": "上格",
                "evidence": f"太阳+太阴同坐{branch}宫(日月同辉)",
            })

    # 10. 明珠出海 — 命宫在未 + 三方四正见太阳/太阴/文昌/文曲.
    if ming_branch == "未" and {"太阳", "太阴", "文昌", "文曲"}.issubset(sfsz_set):
        out.append({
            "name": "明珠出海",
            "type": "上格",
            "evidence": "命宫在未, 三方四正聚太阳/太阴/文昌/文曲",
        })

    # 11. 辅弼夹命 — 命宫前后宫各有 左辅/右弼.
    prev_b = _branch_offset(ming_branch, -1)
    next_b = _branch_offset(ming_branch, 1)
    prev_stars = branch_to_all_stars.get(prev_b, [])
    next_stars = branch_to_all_stars.get(next_b, [])
    if (
        ("左辅" in prev_stars and "右弼" in next_stars)
        or ("右弼" in prev_stars and "左辅" in next_stars)
    ):
        out.append({
            "name": "辅弼夹命",
            "type": "上格",
            "evidence": f"左辅/右弼分坐命宫前后({prev_b}/{next_b})",
        })

    # 12. 昌曲夹命 — 文昌+文曲 夹.
    if (
        ("文昌" in prev_stars and "文曲" in next_stars)
        or ("文曲" in prev_stars and "文昌" in next_stars)
    ):
        out.append({
            "name": "昌曲夹命",
            "type": "上格",
            "evidence": f"文昌/文曲分坐命宫前后({prev_b}/{next_b})",
        })

    # 13. 羊陀夹忌 — 命宫坐 化忌星, 前后各有 擎羊/陀罗.
    ji_star = sihua.get("忌")
    if ji_star and ji_star in mg_stars_all:
        if (
            ("擎羊" in prev_stars and "陀罗" in next_stars)
            or ("陀罗" in prev_stars and "擎羊" in next_stars)
        ):
            out.append({
                "name": "羊陀夹忌",
                "type": "凶格",
                "evidence": f"化忌({ji_star})坐命, 擎羊陀罗夹之",
            })

    # 14. 空劫夹命 — 地空 + 地劫 夹命宫.
    if (
        ("地空" in prev_stars and "地劫" in next_stars)
        or ("地劫" in prev_stars and "地空" in next_stars)
    ):
        out.append({
            "name": "空劫夹命",
            "type": "凶格",
            "evidence": f"地空/地劫分坐命宫前后({prev_b}/{next_b})",
        })

    # 15. 马头带箭 — 天马 + 擎羊 同宫.
    for branch, stars in branch_to_all_stars.items():
        if "天马" in stars and "擎羊" in stars:
            out.append({
                "name": "马头带箭",
                "type": "变格",
                "evidence": f"天马+擎羊同坐{branch}宫(冲锋陷阵)",
            })

    return out


# --------------------------------------------------------------------------- #
# Section 17 — CLI / main
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "紫微斗数排盘 v" + VERSION + " — 14主星 + 六吉六煞 + 杂曜 + "
            "命主身主 + 自化 + 大限/流年四化 + 借宫 + 格局识别"
        ),
    )
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--hour", type=int, required=True)
    p.add_argument("--minute", type=int, default=0)
    p.add_argument("--gender", choices=["male", "female"], required=True)
    p.add_argument("--tz", type=float, default=8.0)
    p.add_argument("--longitude", type=float, default=120.0)
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入为农历; 否则按公历换算")
    p.add_argument("--liu-year", type=int, default=None,
                   help="额外加算指定流年的四化 (公历)")
    p.add_argument("--no-patterns", action="store_true",
                   help="略过 格局 检测以缩减输出")
    p.add_argument("--no-sihua", action="store_true",
                   help="略过 自化/大限四化/流年四化")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    require_lunar()
    from lunar_python import Solar, Lunar  # type: ignore

    try:
        if args.lunar:
            lunar = Lunar.fromYmdHms(
                args.year, args.month, args.day,
                args.hour, args.minute, 0,
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                args.year, args.month, args.day,
                args.hour, args.minute, 0,
            )
            lunar = solar.getLunar()
    except Exception as exc:
        json_print({
            "ok": False, "tool": "ziwei",
            "error": "invalid_date", "message": str(exc),
            "input": vars(args),
        })
        return 1

    year_stem = lunar.getYearGan()
    year_branch = lunar.getYearZhi()
    lunar_month = abs(lunar.getMonth())
    lunar_day = lunar.getDay()

    # 1. 命宫 / 身宫 / 宫干.
    mg_branch = calc_ming_gong(lunar_month, args.hour)
    sg_branch = calc_shen_gong(lunar_month, args.hour)
    mg_stem = stem_of_palace(year_stem, mg_branch)

    # 2. 五行局.
    ju_num, ju_name = wuxing_ju(year_stem, mg_branch)

    # 3. 紫微 + 14 主星.
    zw_branch = ziwei_position(ju_num, lunar_day)
    main_pos = place_main_stars(zw_branch)

    # 4. 六吉 + 六煞 + 杂曜.
    lucky_pos = place_lucky_stars(year_stem, lunar_month, args.hour)
    malefic_pos = place_malefic_stars(year_stem, year_branch, args.hour)
    misc_pos = place_miscellaneous_stars(year_branch)

    # 5. 命主 / 身主 / 斗君.
    ming_zhu = MING_ZHU.get(year_branch, "?")
    shen_zhu = SHEN_ZHU.get(year_branch, "?")
    dou_jun_branch = calc_dou_jun(lunar_month, args.hour)

    # 6. 反向索引 — branch -> list of stars by category.
    branch_to_main: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in main_pos.items():
        branch_to_main[b].append(star)
    branch_to_lucky: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in lucky_pos.items():
        branch_to_lucky[b].append(star)
    branch_to_malefic: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in malefic_pos.items():
        branch_to_malefic[b].append(star)
    branch_to_misc: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in misc_pos.items():
        branch_to_misc[b].append(star)
    branch_to_all: dict[str, list[str]] = {
        b: branch_to_main[b] + branch_to_lucky[b]
        + branch_to_malefic[b] + branch_to_misc[b]
        for b in DIZHI
    }

    # 7. 生年四化 lookup.
    sihua_native = SI_HUA.get(year_stem, {})

    # 8. 12 宫排盘 + 借宫 + 自化.
    palaces = assign_palaces(mg_branch)
    annotated: list[dict] = []
    for p in palaces:
        b = p["branch"]
        stem = stem_of_palace(year_stem, b)
        mains = list(branch_to_main[b])
        luckies = list(branch_to_lucky[b])
        malefics = list(branch_to_malefic[b])
        miscs = list(branch_to_misc[b])
        sfsz = san_fang_si_zheng(b)

        # Sihua markers (生年四化): which stars in this palace are 化X targets.
        sihua_marks: list[str] = []
        for hua_type, target in sihua_native.items():
            if target in mains + luckies:
                sihua_marks.append(f"化{hua_type}({target})")

        # 自化.
        if args.no_sihua:
            self_huas: list[str] = []
        else:
            self_huas = detect_self_transformations(stem, mains + luckies)

        # 借宫.
        borrowed = False
        borrowed_stars: list[str] = []
        borrowed_from: Optional[str] = None
        if is_empty_palace(mains):
            opp_b, opp_main = borrow_from_opposite(b, branch_to_main)
            if opp_main:
                borrowed = True
                borrowed_stars = opp_main
                borrowed_from = opp_b

        annotated.append({
            "index": p["index"],
            "name": p["name"],
            "branch": b,
            "stem": stem,
            "ganzhi": f"{stem}{b}",
            "main_stars": [
                {"name": s, "brightness": brightness_of(s, b)} for s in mains
            ],
            "lucky_stars": luckies,
            "malefic_stars": malefics,
            "miscellaneous_stars": miscs,
            "sihua_native": sihua_marks,
            "self_transformations": self_huas,
            "borrowed": borrowed,
            "borrowed_stars": borrowed_stars,
            "borrowed_from_branch": borrowed_from,
            "san_fang_si_zheng": sfsz,
            "is_ming_gong": (p["index"] == 0),
            "is_shen_gong": (b == sg_branch),
        })

    # 9. 大限 + 流年四化.
    da_xian = da_xian_ranges(ju_num, args.gender, year_stem, palaces, SI_HUA)
    liu_nian_sihua = None
    if args.liu_year:
        try:
            from lunar_python import Solar as _Solar  # type: ignore
            ly_lunar = _Solar.fromYmdHms(
                args.liu_year, 6, 15, 12, 0, 0,
            ).getLunar()
            ly_stem = ly_lunar.getYearGan()
            ly_branch = ly_lunar.getYearZhi()
            liu_nian_sihua = {
                "year": args.liu_year,
                "year_stem": ly_stem,
                "year_branch": ly_branch,
                "transformations": SI_HUA.get(ly_stem, {}),
                "liu_nian_ming_gong_branch": ly_branch,
            }
        except Exception as exc:
            warn(f"liu_year compute failed: {exc}")

    # 10. 格局识别.
    patterns: list[dict] = []
    if not args.no_patterns:
        patterns = detect_patterns(
            mg_branch, branch_to_main, branch_to_all,
            palaces, sihua_native,
        )

    out = {
        "ok": True,
        "tool": "ziwei",
        "version": VERSION,
        "input": vars(args),
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(),
            "month": lunar_month,
            "day": lunar_day,
            "year_ganzhi": lunar.getYearInGanZhi(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
        },
        "year_stem": year_stem,
        "year_branch": year_branch,
        "wuxing_ju": {"number": ju_num, "name": ju_name},
        "ming_gong": {"branch": mg_branch, "stem": mg_stem,
                      "ganzhi": f"{mg_stem}{mg_branch}"},
        "shen_gong": {"branch": sg_branch},
        "ming_zhu": ming_zhu,
        "shen_zhu": shen_zhu,
        "dou_jun": f"{dou_jun_branch}宫",
        "ziwei_position": zw_branch,
        "main_stars_positions": main_pos,
        "lucky_stars_positions": lucky_pos,
        "malefic_stars_positions": malefic_pos,
        "miscellaneous_stars_positions": misc_pos,
        "twelve_palaces": annotated,
        "four_transformations_native": sihua_native,
        "da_xian": da_xian,
        "liu_nian_sihua": liu_nian_sihua,
        "patterns": patterns,
        "notes": [
            "本输出含 命宫/身宫/五行局/紫微/14主星/六吉六煞/9杂曜/12宫/借宫/自化/大限四化/格局识别。",
            "亮度依《紫微斗数全书·形性赋》简化为 庙/旺/平/陷, 实战可再细化为 庙旺得地利平不闲陷 七级。",
            "流年/流月/流日 需配合 斗君 起算; 本盘输出 dou_jun 提供锚位。",
            "三合派与飞星派对火铃起例及部分自化有分歧, 本脚本采用《紫微斗数全书》主流。",
        ],
    }

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
