"""紫微: 五行局 + 紫微星定位表."""
from __future__ import annotations

from utils import (
    DIZHI,
    TIANGAN,
    WUHU_DUN,
    hour_branch,
    hour_branch_index,
    jiazi_index,
)

# Section 0 — micro helpers
# --------------------------------------------------------------------------- #

def _branch_idx(branch: str) -> int:
    return DIZHI.index(branch)


def _branch_offset(branch: str, offset: int) -> str:
    """Return the branch that is ``offset`` steps from ``branch`` (mod 12)."""
    return DIZHI[(_branch_idx(branch) + offset) % 12]


def branch_of_hour(hour: int) -> str:
    """Hour 0-23 -> 时辰地支. 23/0->子, 1-2->丑, 3-4->寅, ..."""
    return hour_branch(hour)


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

# 六十甲子纳音. 与《紫微斗数全书》卷二「六十花甲子纳音歌」逐对核过, 60/60 相符;
# 三处仅是异体写法, 五行不变, 故未动: 剑锋金/剑峰金、井泉水/泉中水、桑柘木/桑拓木
# (lunar_python 作 泉中水, 八字路径的纳音名由它给出, 与本表可能不同字同五行)。
# 本表只被 nayin_wuxing() 取末字使用, 名称本身不出现在紫微输出里。
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

WUXING_JU_NUM: dict[str, int] = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
WUXING_JU_NAME: dict[int, str] = {2: "水二局", 3: "木三局", 4: "金四局",
                                   5: "土五局", 6: "火六局"}


def nayin_wuxing(stem: str, branch: str) -> str:
    """五行 of a pillar's 纳音.

    Every 纳音 name ends with its own 五行 character (海中金 -> 金,
    大林木 -> 木); verified for all 60 pairs, so the reverse keyword table this
    used to scan was redundant.
    """
    return NAYIN_60[jiazi_index(stem, branch)][-1]


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
