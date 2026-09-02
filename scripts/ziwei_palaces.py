"""紫微: 命主身主 / 四化 / 十二宫 / 大限 / 斗君 / 自化 / 借宫."""
from __future__ import annotations

from utils import DIZHI, TIANGAN, hour_branch_index
from ziwei_stars import MAIN_STARS
from ziwei_tables import _branch_idx, _branch_offset, stem_of_palace

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
