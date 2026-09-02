"""八字: 干支 interaction reference tables + 旬空."""
from __future__ import annotations

from utils import xun_kong

# 干支 互动 reference tables (classical: 五合, 六合, 三合, 三会, 六冲, 六害, 三刑)
# --------------------------------------------------------------------------- #

# 天干五合 — 化气
TIANGAN_HE: dict[frozenset[str], str] = {
    frozenset(["甲", "己"]): "土",
    frozenset(["乙", "庚"]): "金",
    frozenset(["丙", "辛"]): "水",
    frozenset(["丁", "壬"]): "木",
    frozenset(["戊", "癸"]): "火",
}

# 地支六合
DIZHI_LIU_HE: dict[frozenset[str], str] = {
    frozenset(["子", "丑"]): "土",
    frozenset(["寅", "亥"]): "木",
    frozenset(["卯", "戌"]): "火",
    frozenset(["辰", "酉"]): "金",
    frozenset(["巳", "申"]): "水",
    frozenset(["午", "未"]): "土",
}

# 地支三合局 (申子辰/亥卯未/寅午戌/巳酉丑 → 五行)
SAN_HE_GROUPS: list[tuple[tuple[str, str, str], str]] = [
    (("申", "子", "辰"), "水"),
    (("亥", "卯", "未"), "木"),
    (("寅", "午", "戌"), "火"),
    (("巳", "酉", "丑"), "金"),
]

# 地支三会方 (寅卯辰/巳午未/申酉戌/亥子丑 → 五行)
SAN_HUI_GROUPS: list[tuple[tuple[str, str, str], str]] = [
    (("寅", "卯", "辰"), "木"),
    (("巳", "午", "未"), "火"),
    (("申", "酉", "戌"), "金"),
    (("亥", "子", "丑"), "水"),
]

# 地支六冲 (相对位)
DIZHI_CHONG: list[frozenset[str]] = [
    frozenset(["子", "午"]),
    frozenset(["丑", "未"]),
    frozenset(["寅", "申"]),
    frozenset(["卯", "酉"]),
    frozenset(["辰", "戌"]),
    frozenset(["巳", "亥"]),
]

# 地支六害
DIZHI_HAI: list[frozenset[str]] = [
    frozenset(["子", "未"]),
    frozenset(["丑", "午"]),
    frozenset(["寅", "巳"]),
    frozenset(["卯", "辰"]),
    frozenset(["申", "亥"]),
    frozenset(["酉", "戌"]),
]

# 三刑 — 寅巳申、丑戌未为三刑; 子卯相刑; 辰午酉亥自刑
SAN_XING_TRIPLES: list[tuple[str, str, str]] = [
    ("寅", "巳", "申"),
    ("丑", "戌", "未"),
]
SAN_XING_PAIRS: list[frozenset[str]] = [
    frozenset(["子", "卯"]),  # 无礼之刑
]
SAN_XING_SELF: list[str] = ["辰", "午", "酉", "亥"]  # 自刑

PILLAR_LABELS_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


# --------------------------------------------------------------------------- #
# 空亡 (旬空)
# --------------------------------------------------------------------------- #

def xun_kong_of_day(day_stem: str, day_branch: str) -> list[str]:
    """Return the two 地支 in 旬空 for the given day pillar."""
    return xun_kong(day_stem, day_branch)


# --------------------------------------------------------------------------- #
