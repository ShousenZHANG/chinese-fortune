"""Compute a full BaZi (八字) chart — v1.1.

Outputs four pillars, hidden stems, 十神, weighted 五行 distribution, 日主旺衰,
35 神煞 (driven by assets/shensha.json), 用神/喜神/忌神 (扶抑 + 调候 combined),
格局 detection (special-format priority then 月令本气透干), 干支互动
(合冲刑害三合三会), 纳音, 大运 sequence with 起运岁, and 流年 hints.

Backed by lunar_python for the calendrical math; assets/shensha.json for 神煞
qi-fa tables; assets/tiaohou.json (if present) for 调候用神 climate balance.

Usage:
    python bazi_calc.py --year 1990 --month 5 --day 10 --hour 14 --minute 30 \\
        --gender male --tz 8 --longitude 116.4

Optional flags:
    --no-shensha    skip 神煞 detection
    --no-yongshen   skip 用神/喜神/忌神
    --no-geju       skip 格局 detection
    --lunar         treat input as 农历

Output: pretty UTF-8 JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from utils import (
    DIZHI,
    DIZHI_WUXING,
    DIZHI_YIN_YANG,
    DIZHI_ZODIAC,
    HIDDEN_STEMS,
    TIANGAN,
    TIANGAN_WUXING,
    TIANGAN_YIN_YANG,
    WUXING_GEN,
    WUXING_KE,
    json_print,
    longitude_correction,
    require_lunar,
    shi_shen,
    true_solar_time_info,
    warn,
)


VERSION = "1.1.0"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


# --------------------------------------------------------------------------- #
# Asset loading (graceful degradation if files absent)
# --------------------------------------------------------------------------- #

def _load_json(name: str) -> Optional[dict]:
    path = ASSETS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(f"failed to load {name}: {e}")
        return None


# --------------------------------------------------------------------------- #
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

XUN_KONG_BY_OFFSET: dict[int, list[str]] = {
    0: ["戌", "亥"],   # 甲子旬
    1: ["申", "酉"],   # 甲戌旬
    2: ["午", "未"],   # 甲申旬
    3: ["辰", "巳"],   # 甲午旬
    4: ["寅", "卯"],   # 甲辰旬
    5: ["子", "丑"],   # 甲寅旬
}


def xun_kong_of_day(day_stem: str, day_branch: str) -> list[str]:
    """Return the two 地支 in 旬空 for the given day pillar."""
    ts = TIANGAN.index(day_stem)
    db = DIZHI.index(day_branch)
    diff = (db - ts) % 12
    mapping = {0: 0, 10: 1, 8: 2, 6: 3, 4: 4, 2: 5}
    idx = mapping.get(diff, 0)
    return XUN_KONG_BY_OFFSET[idx]


# --------------------------------------------------------------------------- #
# 神煞 detection — driven by assets/shensha.json + classical fallbacks
# --------------------------------------------------------------------------- #

# Classification by 起法 type — determines which pillar's stem/branch to query.
# "day_stem" = use 日干, scan all 4 branches
# "day_branch" = use 日支 specific
# "year_stem" = use 年干
# "year_branch_sanhe" = use 年支 三合 group (look up by trio key like "申子辰")
# "year_branch_single" = use 年支 (single-branch key)
# "year_branch_season" = use 年支 季节 (亥子丑/寅卯辰/...)
# "month_branch" = use 月支
# "day_pillar" = use 日柱 ganzhi (魁罡 etc.)
# "xun_kong" = 旬空 by 日柱
SHENSHA_CATEGORY: dict[str, str] = {
    "天乙贵人": "day_stem",
    "太极贵人": "day_stem",
    "文昌贵人": "day_stem",
    "福星贵人": "day_stem",
    "国印贵人": "day_stem",
    "学堂": "day_stem",
    "词馆": "day_stem",
    "天厨贵人": "day_stem",
    "金舆": "day_stem",
    "红艳": "day_stem",
    "红艳煞": "day_stem",
    "羊刃": "day_stem",
    "飞刃": "day_stem",
    "桃花咸池": "year_branch_sanhe",
    "驿马": "year_branch_sanhe",
    "华盖": "year_branch_sanhe",
    "将星": "year_branch_sanhe",
    "劫煞": "year_branch_sanhe",
    "灾煞": "year_branch_sanhe",
    "亡神": "year_branch_sanhe",
    "孤辰": "year_branch_season",
    "寡宿": "year_branch_season",
    "红鸾": "year_branch_single",
    "天喜": "year_branch_single",
    "大耗": "year_branch_single",
    "小耗": "year_branch_single",
    "天德贵人": "month_branch",
    "月德贵人": "month_branch_sanhe",
    "天德合": "month_branch",
    "月德合": "month_branch_sanhe",
    "魁罡": "day_pillar",
    "阴差阳错": "day_pillar",
    "十恶大败": "day_pillar",
    "空亡": "xun_kong",
    "三奇贵人": "year_stem_triple",
    "天罗地网": "year_branch_special",
}

# 月柱 -> 三合 group key for 月德/月德合
MONTH_BRANCH_TO_SANHE: dict[str, str] = {
    "寅": "寅午戌", "午": "寅午戌", "戌": "寅午戌",
    "申": "申子辰", "子": "申子辰", "辰": "申子辰",
    "巳": "巳酉丑", "酉": "巳酉丑", "丑": "巳酉丑",
    "亥": "亥卯未", "卯": "亥卯未", "未": "亥卯未",
}

# 年支 -> 三合 group key (申子辰, 寅午戌, 巳酉丑, 亥卯未)
YEAR_BRANCH_TO_SANHE: dict[str, str] = MONTH_BRANCH_TO_SANHE.copy()

# 年支 -> 季节 group key (亥子丑/寅卯辰/巳午未/申酉戌)
YEAR_BRANCH_TO_SEASON: dict[str, str] = {
    "亥": "亥子丑", "子": "亥子丑", "丑": "亥子丑",
    "寅": "寅卯辰", "卯": "寅卯辰", "辰": "寅卯辰",
    "巳": "巳午未", "午": "巳午未", "未": "巳午未",
    "申": "申酉戌", "酉": "申酉戌", "戌": "申酉戌",
}

# 月支 -> 月柱键 (寅月, 卯月, ...)
def _month_branch_key(branch: str) -> str:
    return f"{branch}月"

# 三奇贵人 三组
SAN_QI_GROUPS: list[tuple[set[str], str]] = [
    ({"甲", "戊", "庚"}, "天上三奇"),
    ({"乙", "丙", "丁"}, "地下三奇"),
    ({"壬", "癸", "辛"}, "人中三奇"),
]


def _scan_day_stem(
    name: str,
    qi_fa: Any,
    day_stem: str,
    branches: dict[str, str],
    meaning: str,
) -> list[dict]:
    """qi_fa: day_stem -> branch (str) or list[str]. Scan all 4 branches."""
    if not isinstance(qi_fa, dict):
        return []
    targets = qi_fa.get(day_stem)
    if targets is None:
        return []
    if isinstance(targets, str):
        targets = [targets]
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if b in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "日干",
                "meaning": meaning,
            })
    return hits


def _scan_year_branch_sanhe(
    name: str,
    qi_fa: dict,
    year_branch: str,
    branches: dict[str, str],
    meaning: str,
) -> list[dict]:
    """qi_fa keys like '申子辰' -> target branch."""
    sanhe_key = YEAR_BRANCH_TO_SANHE.get(year_branch)
    if sanhe_key is None:
        return []
    target = qi_fa.get(sanhe_key)
    if not target:
        return []
    targets = [target] if isinstance(target, str) else list(target)
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if b in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "年支三合",
                "meaning": meaning,
            })
    return hits


def _scan_year_branch_season(
    name: str,
    qi_fa: dict,
    year_branch: str,
    branches: dict[str, str],
    meaning: str,
) -> list[dict]:
    season_key = YEAR_BRANCH_TO_SEASON.get(year_branch)
    if season_key is None:
        return []
    target = qi_fa.get(season_key)
    if not target:
        return []
    targets = [target] if isinstance(target, str) else list(target)
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if b in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "年支季节",
                "meaning": meaning,
            })
    return hits


def _scan_year_branch_single(
    name: str,
    qi_fa: dict,
    year_branch: str,
    branches: dict[str, str],
    meaning: str,
) -> list[dict]:
    target = qi_fa.get(year_branch)
    if not target:
        return []
    targets = [target] if isinstance(target, str) else list(target)
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if b in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "年支",
                "meaning": meaning,
            })
    return hits


def _scan_month_branch_stem(
    name: str,
    qi_fa: dict,
    month_branch: str,
    stems: dict[str, str],
    meaning: str,
) -> list[dict]:
    """月柱 keys like '寅月' -> target stem. Scan all 4 stems."""
    key = _month_branch_key(month_branch)
    target = qi_fa.get(key)
    if not target:
        return []
    # Special: 天德贵人 qi_fa_table sometimes lists a branch instead of stem
    # (e.g. 卯月 -> 申). Try both stems and branches.
    targets = [target] if isinstance(target, str) else list(target)
    hits: list[dict] = []
    for pillar_label, s in stems.items():
        if s in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "干",
                "source_pillar": pillar_label,
                "hit": s,
                "trigger": "月支",
                "meaning": meaning,
            })
    return hits


def _scan_month_branch_sanhe_stem(
    name: str,
    qi_fa: dict,
    month_branch: str,
    stems: dict[str, str],
    meaning: str,
) -> list[dict]:
    sanhe_key = MONTH_BRANCH_TO_SANHE.get(month_branch)
    if sanhe_key is None:
        return []
    target = qi_fa.get(sanhe_key)
    if not target:
        return []
    targets = [target] if isinstance(target, str) else list(target)
    hits: list[dict] = []
    for pillar_label, s in stems.items():
        if s in targets:
            hits.append({
                "name": name,
                "position": PILLAR_LABELS_CN[pillar_label] + "干",
                "source_pillar": pillar_label,
                "hit": s,
                "trigger": "月支三合",
                "meaning": meaning,
            })
    return hits


def _scan_day_pillar(
    name: str,
    qi_fa_list: list[str],
    day_ganzhi: str,
    meaning: str,
) -> list[dict]:
    if day_ganzhi in qi_fa_list:
        return [{
            "name": name,
            "position": "日柱",
            "source_pillar": "day",
            "hit": day_ganzhi,
            "trigger": "日柱",
            "meaning": meaning,
        }]
    return []


def _scan_xun_kong(
    day_stem: str,
    day_branch: str,
    branches: dict[str, str],
    meaning: str,
) -> list[dict]:
    kong = xun_kong_of_day(day_stem, day_branch)
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if pillar_label == "day":
            continue
        if b in kong:
            hits.append({
                "name": "空亡",
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "日柱旬空",
                "meaning": meaning,
            })
    return hits


def _scan_san_qi(stems: list[str], meaning: str) -> list[dict]:
    stem_set = set(stems)
    hits: list[dict] = []
    for group, label in SAN_QI_GROUPS:
        if group.issubset(stem_set):
            hits.append({
                "name": "三奇贵人",
                "position": "三干齐全",
                "source_pillar": None,
                "hit": "".join(sorted(group)),
                "trigger": label,
                "meaning": meaning,
            })
    return hits


def _scan_tian_luo_di_wang(
    branches: dict[str, str],
    gender: str,
    meaning: str,
) -> list[dict]:
    # 戌亥为天罗 (男忌), 辰巳为地网 (女忌)
    hits: list[dict] = []
    for pillar_label, b in branches.items():
        if b in ("戌", "亥") and gender == "male":
            hits.append({
                "name": "天罗",
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "男命戌亥",
                "meaning": meaning,
            })
        if b in ("辰", "巳") and gender == "female":
            hits.append({
                "name": "地网",
                "position": PILLAR_LABELS_CN[pillar_label] + "支",
                "source_pillar": pillar_label,
                "hit": b,
                "trigger": "女命辰巳",
                "meaning": meaning,
            })
    return hits


# Inline classical 起法 used when shensha.json entry has no qi_fa_table
# (kept here for robustness — values cross-checked against 19-shensha.md).
INLINE_QI_FA: dict[str, dict] = {
    "羊刃": {
        "甲": "卯", "乙": "寅", "丙": "午", "丁": "巳",
        "戊": "午", "己": "巳", "庚": "酉", "辛": "申",
        "壬": "子", "癸": "亥",
    },
    "飞刃": {
        "甲": "酉", "乙": "申", "丙": "子", "丁": "亥",
        "戊": "子", "己": "亥", "庚": "卯", "辛": "寅",
        "壬": "午", "癸": "巳",
    },
    "天乙贵人": {
        "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
        "乙": ["子", "申"], "己": ["子", "申"],
        "丙": ["亥", "酉"], "丁": ["亥", "酉"],
        "壬": ["卯", "巳"], "癸": ["卯", "巳"],
        "辛": ["寅", "午"],
    },
}

# Inline 日柱-based classical sets (these are typically not in shensha.json's
# qi_fa_table when there's only prose qi_fa).
KUI_GANG = ["庚辰", "庚戌", "壬辰", "戊戌"]
YIN_CHA_YANG_CUO = [
    "丙子", "丁丑", "戊寅", "辛卯", "壬辰", "癸巳",
    "丙午", "丁未", "戊申", "辛酉", "壬戌", "癸亥",
]
SHI_E_DA_BAI = [
    "甲辰", "乙巳", "丙申", "丁亥", "戊戌",
    "己丑", "庚辰", "辛巳", "壬申", "癸亥",
]


def _find_entry(shensha_data: dict, name: str) -> Optional[dict]:
    """Locate a shensha entry by name across all top-level categories."""
    if not isinstance(shensha_data, dict):
        return None
    for category, entries in shensha_data.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("name") == name:
                return e
    return None


def detect_all_shensha(
    shensha_data: Optional[dict],
    day_stem: str,
    day_branch: str,
    day_ganzhi: str,
    year_stem: str,
    year_branch: str,
    month_branch: str,
    stems_map: dict[str, str],
    branches_map: dict[str, str],
    gender: str,
) -> list[dict]:
    """Detect all 35 神煞 across the four pillars.

    Returns a deduped list of dicts: {name, position, source_pillar, hit,
    trigger, meaning}. Uses ``shensha_data`` from assets/shensha.json when
    available; falls back to classical INLINE_QI_FA for any entry missing a
    qi_fa_table.
    """
    triggered: list[dict] = []

    for name, category in SHENSHA_CATEGORY.items():
        entry = _find_entry(shensha_data, name) if shensha_data else None
        meaning = (entry or {}).get("meaning", "")
        qi_fa = (entry or {}).get("qi_fa_table")

        if category == "day_stem":
            # Some names (红艳 vs 红艳煞) appear in either category list.
            if qi_fa is None and name in ("红艳",):
                # alias
                alt = _find_entry(shensha_data, "红艳煞")
                if alt:
                    qi_fa = alt.get("qi_fa_table")
                    if not meaning:
                        meaning = alt.get("meaning", "")
            if qi_fa is None:
                qi_fa = INLINE_QI_FA.get(name)
            display_name = "红艳" if name in ("红艳", "红艳煞") else name
            triggered.extend(_scan_day_stem(
                display_name, qi_fa, day_stem, branches_map, meaning
            ))

        elif category == "year_branch_sanhe":
            if qi_fa is None:
                continue
            triggered.extend(_scan_year_branch_sanhe(
                name, qi_fa, year_branch, branches_map, meaning
            ))

        elif category == "year_branch_season":
            if qi_fa is None:
                continue
            triggered.extend(_scan_year_branch_season(
                name, qi_fa, year_branch, branches_map, meaning
            ))

        elif category == "year_branch_single":
            if qi_fa is None:
                continue
            triggered.extend(_scan_year_branch_single(
                name, qi_fa, year_branch, branches_map, meaning
            ))

        elif category == "month_branch":
            if qi_fa is None:
                continue
            # 天德贵人 entries: key like "卯月", value sometimes a branch (申)
            # not a stem. Inspect both stems and branches.
            key = _month_branch_key(month_branch)
            target = qi_fa.get(key)
            if not target:
                continue
            targets = [target] if isinstance(target, str) else list(target)
            for pillar_label, s in stems_map.items():
                if s in targets:
                    triggered.append({
                        "name": name,
                        "position": PILLAR_LABELS_CN[pillar_label] + "干",
                        "source_pillar": pillar_label,
                        "hit": s,
                        "trigger": "月支",
                        "meaning": meaning,
                    })
            for pillar_label, b in branches_map.items():
                if b in targets:
                    triggered.append({
                        "name": name,
                        "position": PILLAR_LABELS_CN[pillar_label] + "支",
                        "source_pillar": pillar_label,
                        "hit": b,
                        "trigger": "月支",
                        "meaning": meaning,
                    })

        elif category == "month_branch_sanhe":
            if qi_fa is None:
                continue
            triggered.extend(_scan_month_branch_sanhe_stem(
                name, qi_fa, month_branch, stems_map, meaning
            ))

        elif category == "day_pillar":
            if name == "魁罡":
                hits = _scan_day_pillar(name, KUI_GANG, day_ganzhi, meaning)
            elif name == "阴差阳错":
                hits = _scan_day_pillar(name, YIN_CHA_YANG_CUO, day_ganzhi, meaning)
            elif name == "十恶大败":
                hits = _scan_day_pillar(name, SHI_E_DA_BAI, day_ganzhi, meaning)
            else:
                hits = []
            triggered.extend(hits)

        elif category == "xun_kong":
            triggered.extend(_scan_xun_kong(day_stem, day_branch, branches_map, meaning))

        elif category == "year_stem_triple":
            stems_list = list(stems_map.values())
            triggered.extend(_scan_san_qi(stems_list, meaning))

        elif category == "year_branch_special":
            # 天罗地网
            triggered.extend(_scan_tian_luo_di_wang(branches_map, gender, meaning))

    # Dedupe identical hits (same name+position+hit)
    seen = set()
    deduped: list[dict] = []
    for h in triggered:
        key = (h["name"], h.get("position"), h.get("hit"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    return deduped


# --------------------------------------------------------------------------- #
# Weighted 五行 strength + day-master strength
# --------------------------------------------------------------------------- #

# Month branch -> ordered hidden stems with weights (本气, 中气, 余气).
# Order in HIDDEN_STEMS already follows 本气→中气→余气 by convention; classical
# weights: 本气 ≈ 1.0, 中气 ≈ 0.5, 余气 ≈ 0.3. We use the 月支 multipliers
# specified in the spec (本气×3, 中气×1.5, 余气×0.8) by selecting positionally.
MONTH_HIDDEN_WEIGHTS: tuple[float, ...] = (3.0, 1.5, 0.8)
OTHER_BRANCH_HIDDEN_WEIGHTS: tuple[float, ...] = (1.0, 0.5, 0.3)


def _hidden_with_weights(branch: str, is_month: bool) -> list[tuple[str, float]]:
    hs = HIDDEN_STEMS.get(branch, [])
    weights = MONTH_HIDDEN_WEIGHTS if is_month else OTHER_BRANCH_HIDDEN_WEIGHTS
    out: list[tuple[str, float]] = []
    for i, stem in enumerate(hs):
        w = weights[i] if i < len(weights) else weights[-1] * 0.5
        out.append((stem, w))
    return out


# Branch overall multiplier (applies after hidden-stem weight selection):
# 月支 × 1.0 (already heavily weighted via hidden weights), 日支 × 1.5,
# 年支 × 1.0, 时支 × 1.0. Plus each 天干 × 1.0.
BRANCH_WEIGHT: dict[str, float] = {
    "year": 1.0, "month": 1.0, "day": 1.5, "hour": 1.0,
}
STEM_WEIGHT = 1.0


def weighted_wuxing(
    pillars: dict[str, dict],
    day_stem: str,
) -> tuple[dict[str, float], dict[str, float]]:
    """Return (per-wuxing weighted score, root_bonus per wuxing).

    Root bonus: if day-stem's 五行 appears as a hidden stem of any branch,
    we add 0.5 per such branch into the day-stem's own 五行 score (通根加权).
    """
    counts: dict[str, float] = {w: 0.0 for w in ["木", "火", "土", "金", "水"]}
    root_bonus: dict[str, float] = {w: 0.0 for w in ["木", "火", "土", "金", "水"]}

    day_wx = TIANGAN_WUXING.get(day_stem, "")

    for label, p in pillars.items():
        # 天干
        s_wx = TIANGAN_WUXING.get(p["stem"])
        if s_wx:
            counts[s_wx] += STEM_WEIGHT
        # 地支 hidden stems with positional weights
        branch_w = BRANCH_WEIGHT[label]
        is_month = label == "month"
        for hs, hw in _hidden_with_weights(p["branch"], is_month):
            hs_wx = TIANGAN_WUXING.get(hs)
            if hs_wx:
                contribution = hw * branch_w
                counts[hs_wx] += contribution
                # 通根 bonus: day stem rooted here
                if hs_wx == day_wx:
                    root_bonus[day_wx] += 0.5

    # 通根 加权 ->  add into counts as final adjustment
    for wx, bonus in root_bonus.items():
        counts[wx] += bonus

    return counts, root_bonus


# Season -> day-master 旺相休囚死 (classical 五行四时表)
SEASON_STATE: dict[tuple[str, str], str] = {}
# 春 (寅卯辰): 木旺 火相 水休 金囚 土死
# 夏 (巳午未): 火旺 土相 木休 水囚 金死
# 秋 (申酉戌): 金旺 水相 土休 火囚 木死
# 冬 (亥子丑): 水旺 木相 金休 土囚 火死
_SEASON_STATES: list[tuple[tuple[str, str, str], dict[str, str]]] = [
    (("寅", "卯", "辰"), {"木": "旺", "火": "相", "水": "休", "金": "囚", "土": "死"}),
    (("巳", "午", "未"), {"火": "旺", "土": "相", "木": "休", "水": "囚", "金": "死"}),
    (("申", "酉", "戌"), {"金": "旺", "水": "相", "土": "休", "火": "囚", "木": "死"}),
    (("亥", "子", "丑"), {"水": "旺", "木": "相", "金": "休", "土": "囚", "火": "死"}),
]
for branches, mapping in _SEASON_STATES:
    for b in branches:
        for wx, state in mapping.items():
            SEASON_STATE[(b, wx)] = state
# 四季月 土旺 (辰戌丑未): overlay 土旺
for b in ("辰", "戌", "丑", "未"):
    SEASON_STATE[(b, "土")] = "旺"


def day_master_strength(
    day_stem: str,
    month_branch: str,
    weighted_counts: dict[str, float],
    pillars: dict[str, dict],
) -> dict:
    """Heuristic day-master strength: 旺 / 相 / 休 / 囚 / 死.

    Combines:
      * 月令 state via SEASON_STATE
      * 通根 count (day-stem 五行 rooted in branches)
      * 党众 share (day-stem 五行 + 印星 五行) vs total
    Returns dict {label, score, state_from_yueling, party_ratio, rooted_count,
    explanation}.
    """
    day_wx = TIANGAN_WUXING.get(day_stem, "")
    state = SEASON_STATE.get((month_branch, day_wx), "休")

    total = sum(weighted_counts.values()) or 1.0
    # 党众: 同我 (day_wx) + 生我 (印 — 哪个五行生day_wx?)
    sheng_me = None
    for src, tgt in WUXING_GEN.items():
        if tgt == day_wx:
            sheng_me = src
            break
    party_score = weighted_counts.get(day_wx, 0.0) + weighted_counts.get(sheng_me or "", 0.0)
    party_ratio = party_score / total

    # 通根 count: how many branches host day_wx as a hidden stem
    rooted = 0
    for p in pillars.values():
        for hs in p["hidden_stems"]:
            if TIANGAN_WUXING.get(hs) == day_wx:
                rooted += 1
                break

    # Base score from 月令 state
    state_score = {"旺": 0.45, "相": 0.30, "休": 0.10, "囚": 0.00, "死": -0.10}.get(state, 0.10)
    score = state_score + (rooted * 0.05) + (party_ratio - 0.4) * 0.5
    # Normalize roughly to 0..1 (clamped)
    score = max(0.0, min(1.0, 0.5 + score))

    if score >= 0.7:
        label = "身旺"
    elif score >= 0.55:
        label = "偏旺"
    elif score >= 0.45:
        label = "中和"
    elif score >= 0.3:
        label = "偏弱"
    else:
        label = "身弱"

    parts = [
        f"日主{day_stem}({day_wx})生于{month_branch}月,处于'{state}'地",
        f"通根{rooted}处",
        f"党众占比{party_ratio*100:.1f}%",
    ]
    explanation = "; ".join(parts) + f". 综合判定:{label}."

    return {
        "label": label,
        "score": round(score, 3),
        "state_from_yueling": state,
        "party_ratio": round(party_ratio, 3),
        "rooted_count": rooted,
        "explanation": explanation,
    }


# --------------------------------------------------------------------------- #
# 用神 / 喜神 / 忌神 (扶抑 + 调候)
# --------------------------------------------------------------------------- #

# Each 五行's 生克 helpers
def _ke_me(day_wx: str) -> str:
    """Return the 五行 that controls day_wx (克我者)."""
    for src, tgt in WUXING_KE.items():
        if tgt == day_wx:
            return src
    return ""


def _me_ke(day_wx: str) -> str:
    return WUXING_KE.get(day_wx, "")


def _xie_me(day_wx: str) -> str:
    """Day_wx 生 xie_wx (我生者, 泄秀)."""
    return WUXING_GEN.get(day_wx, "")


def _sheng_me(day_wx: str) -> str:
    """生我者 (印)."""
    for src, tgt in WUXING_GEN.items():
        if tgt == day_wx:
            return src
    return ""


WUXING_TO_STEM_REPRESENTATIVE: dict[str, str] = {
    "木": "甲", "火": "丙", "土": "戊", "金": "庚", "水": "壬",
}


def select_yong_shen(
    day_stem: str,
    month_branch: str,
    strength: dict,
    weighted_counts: dict[str, float],
    tiaohou_data: Optional[dict],
) -> dict:
    """Choose 用神 / 喜神 / 忌神 by 扶抑 + 调候 combined.

    身旺 → 克泄耗 (官杀/食伤/财) among weakest of these three to balance.
    身弱 → 比劫/印 among stronger of these two to support.
    调候 lookup at "{day_stem}|{month_branch}" overrides/boosts when present.
    """
    day_wx = TIANGAN_WUXING.get(day_stem, "")
    label = strength.get("label", "中和")

    # 调候 candidate
    tiaohou_match = False
    tiaohou_primary: Optional[str] = None
    tiaohou_reason = ""
    if tiaohou_data and isinstance(tiaohou_data, dict):
        # Accept either flat top-level keys or nested under "tiaohou"
        nested = tiaohou_data.get("tiaohou") if isinstance(tiaohou_data.get("tiaohou"), dict) else tiaohou_data
        key = f"{day_stem}|{month_branch}"
        entry = nested.get(key) if isinstance(nested, dict) else None
        if isinstance(entry, dict):
            primary = entry.get("primary") or entry.get("yong_shen")
            if primary:
                tiaohou_primary = primary
                tiaohou_match = True
                tiaohou_reason = entry.get("reason", entry.get("note", ""))

    # 扶抑 candidate
    candidates_strong = [_ke_me(day_wx), _me_ke(day_wx), _xie_me(day_wx)]
    candidates_weak = [day_wx, _sheng_me(day_wx)]

    if label in ("身旺", "偏旺"):
        # Want to balance via weakest of the three counter forces
        weighted = [(c, weighted_counts.get(c, 0.0)) for c in candidates_strong if c]
        if not weighted:
            fuyi_wx = _ke_me(day_wx) or _me_ke(day_wx) or _xie_me(day_wx)
        else:
            # Pick the weakest counter-force (most in need of activation)
            fuyi_wx = min(weighted, key=lambda x: x[1])[0]
        fuyi_explain = f"身旺需克/泄/耗调和, 取{fuyi_wx}为扶抑用神(其在命局力量最弱, 需被激活)"
    elif label in ("身弱", "偏弱"):
        weighted = [(c, weighted_counts.get(c, 0.0)) for c in candidates_weak if c]
        if not weighted:
            fuyi_wx = _sheng_me(day_wx) or day_wx
        else:
            # Pick the stronger of 比劫/印 to lean on
            fuyi_wx = max(weighted, key=lambda x: x[1])[0]
        fuyi_explain = f"身弱需扶身, 取{fuyi_wx}为扶抑用神(同党或印星中力量较强者助身)"
    else:
        # 中和: prefer 调候; default to lightest unfilled 五行
        all_wx = list(weighted_counts.keys())
        fuyi_wx = min(all_wx, key=lambda w: weighted_counts.get(w, 0.0))
        fuyi_explain = f"中和之局, 取最弱五行{fuyi_wx}调和五行"

    # Combine: if 调候 says X and 扶抑 says X → strong consensus; otherwise
    # 调候 takes precedence for boundary climates (冬火 / 夏水 / 春木需金 etc.).
    fuyi_match = True
    if tiaohou_match and tiaohou_primary:
        primary_wx = TIANGAN_WUXING.get(tiaohou_primary, "")
        if primary_wx and primary_wx != fuyi_wx:
            # 调候 wins for climate balance
            chosen_wx = primary_wx
            chosen_stem = tiaohou_primary
            reason = (
                f"调候优先: {tiaohou_reason or f'生于{month_branch}月需{primary_wx}调和寒暖燥湿'}; "
                f"扶抑次之取{fuyi_wx}({fuyi_explain})"
            )
            fuyi_match = False
        else:
            chosen_wx = fuyi_wx
            chosen_stem = tiaohou_primary or WUXING_TO_STEM_REPRESENTATIVE.get(fuyi_wx, "")
            reason = (
                f"扶抑与调候一致: {fuyi_explain}; 调候: {tiaohou_reason or f'{day_stem}日生于{month_branch}月,'+primary_wx+'为暖局/润局之神'}"
            )
    else:
        chosen_wx = fuyi_wx
        chosen_stem = WUXING_TO_STEM_REPRESENTATIVE.get(fuyi_wx, "")
        reason = fuyi_explain
        if not tiaohou_match:
            reason += " (调候表缺失, 仅以扶抑取用)"

    # 喜神 = 生用神之神
    xi_wx = ""
    for src, tgt in WUXING_GEN.items():
        if tgt == chosen_wx:
            xi_wx = src
            break

    # 忌神 = 克用神之神
    ji_wx = ""
    for src, tgt in WUXING_KE.items():
        if tgt == chosen_wx:
            ji_wx = src
            break

    return {
        "yong_shen": {
            "primary": chosen_stem,
            "wuxing": chosen_wx,
            "reason": reason,
            "tiaohou_match": tiaohou_match,
            "fuyi_match": fuyi_match,
        },
        "xi_shen": {
            "primary": WUXING_TO_STEM_REPRESENTATIVE.get(xi_wx, ""),
            "wuxing": xi_wx,
            "reason": f"生{chosen_wx}({chosen_stem})之神, 辅助用神",
        },
        "ji_shen": {
            "primary": WUXING_TO_STEM_REPRESENTATIVE.get(ji_wx, ""),
            "wuxing": ji_wx,
            "reason": f"克{chosen_wx}({chosen_stem}), 损用为忌",
        },
    }


# --------------------------------------------------------------------------- #
# 格局 detection
# --------------------------------------------------------------------------- #

# 月支本气 (本气藏干): first entry of HIDDEN_STEMS
def _main_hidden(branch: str) -> str:
    hs = HIDDEN_STEMS.get(branch, [])
    return hs[0] if hs else ""


def _shi_shen_safe(day_stem: str, other: str) -> str:
    try:
        return shi_shen(day_stem, other)
    except Exception:
        return ""


def detect_ge_ju(
    day_stem: str,
    pillars: dict[str, dict],
    weighted_counts: dict[str, float],
    strength: dict,
) -> dict:
    """Detect 格局 with priority: 特殊格 → 化气格 → 正格 (月令本气透干)."""
    day_wx = TIANGAN_WUXING.get(day_stem, "")
    month_branch = pillars["month"]["branch"]
    month_stem = pillars["month"]["stem"]
    hour_stem = pillars["hour"]["stem"]

    total_wx = sum(weighted_counts.values()) or 1.0
    rooted = strength.get("rooted_count", 0)

    # --- 1. 特殊格 (从格 / 化气格) ---
    # 从财格: 财五行 > 60% + day-master no root + 印比 very weak
    cai_wx = _me_ke(day_wx)
    sha_wx = _ke_me(day_wx)
    er_wx = _xie_me(day_wx)
    yin_wx = _sheng_me(day_wx)

    cai_share = weighted_counts.get(cai_wx, 0.0) / total_wx
    sha_share = weighted_counts.get(sha_wx, 0.0) / total_wx
    er_share = weighted_counts.get(er_wx, 0.0) / total_wx
    yin_share = (weighted_counts.get(yin_wx, 0.0) + weighted_counts.get(day_wx, 0.0)) / total_wx

    if rooted == 0 and yin_share < 0.15:
        if cai_share > 0.60:
            return {
                "primary": "从财格",
                "type": "特殊格",
                "month_origin": "日主无根",
                "supporting_evidence": [
                    f"日主{day_stem}无通根",
                    f"财星{cai_wx}占{cai_share*100:.1f}%",
                    f"印比合计仅{yin_share*100:.1f}%",
                ],
                "broken_or_pure": "纯" if yin_share < 0.08 else "破",
                "notes": "从财者富, 最忌印比劫财. 行食伤生财, 财官旺地大发.",
            }
        if sha_share > 0.60:
            return {
                "primary": "从杀格",
                "type": "特殊格",
                "month_origin": "日主无根",
                "supporting_evidence": [
                    f"日主{day_stem}无通根",
                    f"官杀{sha_wx}占{sha_share*100:.1f}%",
                    f"印比合计仅{yin_share*100:.1f}%",
                ],
                "broken_or_pure": "纯" if yin_share < 0.08 else "破",
                "notes": "从杀者贵, 喜行财杀之地, 最忌食伤克杀及印星化杀.",
            }
        if er_share > 0.60:
            return {
                "primary": "从儿格",
                "type": "特殊格",
                "month_origin": "日主无根",
                "supporting_evidence": [
                    f"日主{day_stem}无通根",
                    f"食伤{er_wx}占{er_share*100:.1f}%",
                    f"印比合计仅{yin_share*100:.1f}%",
                ],
                "broken_or_pure": "纯" if yin_share < 0.08 else "破",
                "notes": "从儿者贵, 喜行食伤财地, 忌印星夺食.",
            }

    # --- 化气格 ---
    for adjacent_stem in (month_stem, hour_stem):
        if not adjacent_stem:
            continue
        pair = frozenset([day_stem, adjacent_stem])
        if pair in TIANGAN_HE:
            hua_wx = TIANGAN_HE[pair]
            # 化神得令: month branch's 本气 五行 == hua_wx
            main_hs = _main_hidden(month_branch)
            main_wx = TIANGAN_WUXING.get(main_hs, DIZHI_WUXING.get(month_branch, ""))
            if main_wx == hua_wx:
                return {
                    "primary": f"化{hua_wx}格",
                    "type": "特殊格",
                    "month_origin": "化神得月令",
                    "supporting_evidence": [
                        f"日干{day_stem}与{adjacent_stem}合化{hua_wx}",
                        f"月支{month_branch}本气属{hua_wx}",
                    ],
                    "broken_or_pure": "纯",
                    "notes": f"化气格成立需化神得令且无破化之神; 行化神旺地为吉.",
                }

    # --- 2. 正格: 月令本气透干 ---
    main_hs = _main_hidden(month_branch)
    if main_hs:
        # If 月支本气 == day stem (or same 五行 + same yin-yang) → 建禄/月刃
        main_shi = _shi_shen_safe(day_stem, main_hs)
        if main_shi == "比肩":
            return {
                "primary": "建禄格",
                "type": "正格",
                "month_origin": "月支为日主之禄",
                "supporting_evidence": [
                    f"月支{month_branch}本气{main_hs}与日干{day_stem}同气同阴阳",
                ],
                "broken_or_pure": "纯",
                "notes": "建禄格喜见财官, 财官两旺则贵; 比劫不能成格, 故以财官为用.",
            }
        if main_shi == "劫财" and TIANGAN_YIN_YANG.get(day_stem) == "阳":
            return {
                "primary": "羊刃格",
                "type": "正格",
                "month_origin": "月支为日主羊刃",
                "supporting_evidence": [
                    f"月支{month_branch}本气{main_hs}为阳干日主之刃",
                ],
                "broken_or_pure": "纯",
                "notes": "羊刃格喜官杀制刃, 制化得宜成武贵; 忌再见羊刃叠透.",
            }

        # Otherwise, see if month-pillar's 月支本气 is transparent in 干 (本气透干)
        transparent_pillars: list[str] = []
        for label, p in pillars.items():
            if label == "day":
                continue
            if p["stem"] == main_hs:
                transparent_pillars.append(PILLAR_LABELS_CN[label] + "干透" + main_hs)
        # If transparent, that 十神 sets the 格 name; otherwise fall back to 月支本气 itself.
        if transparent_pillars:
            ge_name = _ge_name_from_shi_shen(main_shi)
            if ge_name:
                pure = _check_purity(day_stem, pillars, main_hs, main_shi)
                return {
                    "primary": ge_name,
                    "type": "正格",
                    "month_origin": "月令本气透出",
                    "supporting_evidence": [
                        f"月支{month_branch}本气藏{main_hs}",
                        *transparent_pillars,
                    ],
                    "broken_or_pure": "纯" if pure else "破",
                    "notes": _ge_ju_note(ge_name),
                }
        else:
            ge_name = _ge_name_from_shi_shen(main_shi)
            if ge_name:
                return {
                    "primary": ge_name,
                    "type": "正格",
                    "month_origin": "月令本气未透(以月支本气论)",
                    "supporting_evidence": [
                        f"月支{month_branch}本气藏{main_hs}({main_shi})",
                    ],
                    "broken_or_pure": "弱",
                    "notes": _ge_ju_note(ge_name),
                }

    return {
        "primary": "杂气格",
        "type": "正格",
        "month_origin": "无明显本气透干",
        "supporting_evidence": [],
        "broken_or_pure": "杂",
        "notes": "无明显主格, 以中气或余气透干者论, 或参考调候/扶抑取用.",
    }


def _ge_name_from_shi_shen(shi: str) -> str:
    mapping = {
        "正官": "正官格", "七杀": "七杀格",
        "正财": "正财格", "偏财": "偏财格",
        "正印": "正印格", "偏印": "偏印格",
        "食神": "食神格", "伤官": "伤官格",
    }
    return mapping.get(shi, "")


_GE_JU_NOTES: dict[str, str] = {
    "正官格": "正官格喜见正财生官, 忌见七杀混杂. 身旺官弱以财生官, 身弱官旺以印化官.",
    "七杀格": "七杀格喜食神制杀或印星化杀, 忌见正官混杂. 杀印相生为大贵.",
    "正财格": "正财格喜身旺胜财, 食伤生财; 忌比劫夺财、印星化财.",
    "偏财格": "偏财格主财源广进, 喜食伤生财, 忌比劫劫财. 男命偏财亦为父星.",
    "正印格": "正印格喜官生印, 忌财坏印. 印旺身强宜行食伤泄秀.",
    "偏印格": "偏印格喜杀印相生, 忌食神被夺. 多偏门技艺.",
    "食神格": "食神格喜财星泄秀, 忌偏印夺食. 食神制杀为大贵.",
    "伤官格": "伤官格喜佩印或生财, 忌见正官(伤官见官为祸百端).",
}


def _ge_ju_note(name: str) -> str:
    return _GE_JU_NOTES.get(name, "")


def _check_purity(
    day_stem: str,
    pillars: dict[str, dict],
    main_hidden: str,
    main_shi: str,
) -> bool:
    """格 is 纯 if no opposing 十神 透干 on same pillar. Rough purity check."""
    if main_shi == "正官":
        opposites = ["七杀"]
    elif main_shi == "七杀":
        opposites = ["正官"]
    elif main_shi == "正财":
        opposites = ["偏财"]
    elif main_shi == "偏财":
        opposites = ["正财"]
    elif main_shi == "正印":
        opposites = ["偏印"]
    elif main_shi == "偏印":
        opposites = ["正印"]
    elif main_shi == "食神":
        opposites = ["伤官"]
    elif main_shi == "伤官":
        opposites = ["食神"]
    else:
        return True
    for label, p in pillars.items():
        if label == "day":
            continue
        if _shi_shen_safe(day_stem, p["stem"]) in opposites:
            return False
    return True


# --------------------------------------------------------------------------- #
# 干支 互动 detection
# --------------------------------------------------------------------------- #

PILLAR_ORDER: list[str] = ["year", "month", "day", "hour"]


def detect_interactions(pillars: dict[str, dict]) -> dict:
    stems = [pillars[p]["stem"] for p in PILLAR_ORDER]
    branches = [pillars[p]["branch"] for p in PILLAR_ORDER]
    stem_positions = {p: pillars[p]["stem"] for p in PILLAR_ORDER}
    branch_positions = {p: pillars[p]["branch"] for p in PILLAR_ORDER}

    out: dict[str, list] = {
        "tiangan_he": [],
        "dizhi_liu_he": [],
        "san_he": [],
        "san_hui": [],
        "dizhi_chong": [],
        "dizhi_hai": [],
        "dizhi_xing": [],
    }

    # 天干五合
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            pair = frozenset([stems[i], stems[j]])
            if pair in TIANGAN_HE:
                out["tiangan_he"].append({
                    "pair": [stems[i], stems[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "干",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "干",
                    ],
                    "transforms_to": TIANGAN_HE[pair],
                })

    # 地支六合
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_LIU_HE:
                out["dizhi_liu_he"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                    "transforms_to": DIZHI_LIU_HE[pair],
                })

    # 地支三合 (全合 or 半合: 三合首字+中字, 中字+末字, 首字+末字)
    bset = set(branches)
    for trio, wx in SAN_HE_GROUPS:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["san_he"].append({
                "branches": present,
                "type": "全合" if len(present) == 3 else "半合",
                "transforms_to": wx,
            })

    # 地支三会
    for trio, wx in SAN_HUI_GROUPS:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["san_hui"].append({
                "branches": present,
                "type": "全会" if len(present) == 3 else "半会",
                "transforms_to": wx,
            })

    # 地支六冲
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_CHONG and branches[i] != branches[j]:
                out["dizhi_chong"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                })

    # 地支六害
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_HAI and branches[i] != branches[j]:
                out["dizhi_hai"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                })

    # 三刑 (三字)
    for trio in SAN_XING_TRIPLES:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["dizhi_xing"].append({
                "branches": present,
                "type": "三刑" if len(present) == 3 else "半刑",
            })
    for pair in SAN_XING_PAIRS:
        if pair.issubset(bset):
            out["dizhi_xing"].append({
                "branches": list(pair),
                "type": "互刑",
            })
    for self_b in SAN_XING_SELF:
        if branches.count(self_b) >= 2:
            out["dizhi_xing"].append({
                "branches": [self_b, self_b],
                "type": "自刑",
            })

    return out


# --------------------------------------------------------------------------- #
# Pillar helpers
# --------------------------------------------------------------------------- #

def pillar_dict(stem: str, branch: str, nayin: str) -> dict:
    return {
        "stem": stem,
        "branch": branch,
        "ganzhi": f"{stem}{branch}",
        "stem_wuxing": TIANGAN_WUXING.get(stem),
        "branch_wuxing": DIZHI_WUXING.get(branch),
        "stem_yin_yang": TIANGAN_YIN_YANG.get(stem),
        "branch_yin_yang": DIZHI_YIN_YANG.get(branch),
        "hidden_stems": HIDDEN_STEMS.get(branch, []),
        "nayin": nayin,
        "zodiac": DIZHI_ZODIAC.get(branch),
    }


def ten_gods_per_pillar(day_stem: str, pillars: dict) -> dict:
    out: dict = {}
    for label, p in pillars.items():
        entry: dict = {"stem": None, "hidden": []}
        if label == "day":
            entry["stem"] = "日主"
        else:
            entry["stem"] = _shi_shen_safe(day_stem, p["stem"])
        for hs in p["hidden_stems"]:
            entry["hidden"].append({"stem": hs, "shi_shen": _shi_shen_safe(day_stem, hs)})
        out[label] = entry
    return out


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="八字排盘 v1.1 — 公历/农历, 含 35 神煞 / 用神 / 格局 / 干支互动"
    )
    p.add_argument("--year", type=int, required=True, help="出生年 (公历或农历)")
    p.add_argument("--month", type=int, required=True, help="出生月 1-12")
    p.add_argument("--day", type=int, required=True, help="出生日 1-31")
    p.add_argument("--hour", type=int, required=True, help="出生时 0-23")
    p.add_argument("--minute", type=int, default=0, help="出生分 0-59")
    p.add_argument("--gender", choices=["male", "female"], required=True,
                   help="性别 (用于排大运 + 天罗地网)")
    p.add_argument("--tz", type=float, default=8.0,
                   help="时区偏移小时 (默认 8 即 GMT+8)")
    p.add_argument("--longitude", type=float, default=120.0,
                   help="出生地经度 (E°, 默认 120, 用于真太阳时)")
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入日期为农历")
    p.add_argument("--years", type=int, default=80,
                   help="大运覆盖年数 (默认 80)")
    p.add_argument("--no-shensha", action="store_true",
                   help="跳过 35 神煞 检测")
    p.add_argument("--no-yongshen", action="store_true",
                   help="跳过 用神/喜神/忌神 计算")
    p.add_argument("--no-geju", action="store_true",
                   help="跳过 格局 判定")
    return p


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    require_lunar()
    from lunar_python import Solar, Lunar  # type: ignore

    # 真太阳时 info (informational + applied)
    try:
        tst_info = true_solar_time_info(
            longitude=args.longitude,
            tz_offset_hours=args.tz,
            year=args.year,
            month=args.month,
            day=args.day,
            hour=args.hour,
            minute=args.minute,
        )
        tst_info["applied"] = True
    except Exception as e:
        warn(f"true_solar_time_info failed: {e}")
        tst_info = {"applied": False, "error": str(e)}

    # Apply correction for pillar computation
    corr_hour, corr_minute = longitude_correction(
        args.hour, args.minute, args.longitude, args.tz,
        year=args.year, month=args.month, day=args.day,
    )

    try:
        if args.lunar:
            lunar = Lunar.fromYmdHms(
                args.year, args.month, args.day, corr_hour, corr_minute, 0
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                args.year, args.month, args.day, corr_hour, corr_minute, 0
            )
            lunar = solar.getLunar()
    except Exception as e:
        json_print({
            "ok": False,
            "tool": "bazi",
            "version": VERSION,
            "error": "invalid_date",
            "message": str(e),
            "input": vars(args),
        })
        return 1

    try:
        eight = lunar.getEightChar()
    except Exception as e:
        json_print({
            "ok": False,
            "tool": "bazi",
            "version": VERSION,
            "error": "bazi_failed",
            "message": str(e),
            "input": vars(args),
        })
        return 1

    try:
        eight.setSect(2)
    except Exception:
        pass

    year_gz = (eight.getYearGan(), eight.getYearZhi())
    month_gz = (eight.getMonthGan(), eight.getMonthZhi())
    day_gz = (eight.getDayGan(), eight.getDayZhi())
    hour_gz = (eight.getTimeGan(), eight.getTimeZhi())

    year_nayin = eight.getYearNaYin()
    month_nayin = eight.getMonthNaYin()
    day_nayin = eight.getDayNaYin()
    hour_nayin = eight.getTimeNaYin()

    pillars = {
        "year":  pillar_dict(*year_gz,  year_nayin),
        "month": pillar_dict(*month_gz, month_nayin),
        "day":   pillar_dict(*day_gz,   day_nayin),
        "hour":  pillar_dict(*hour_gz,  hour_nayin),
    }

    day_stem = day_gz[0]
    day_branch = day_gz[1]
    day_ganzhi = day_stem + day_branch
    year_stem = year_gz[0]
    year_branch = year_gz[1]
    month_branch = month_gz[1]

    stems_map = {p: pillars[p]["stem"] for p in PILLAR_ORDER}
    branches_map = {p: pillars[p]["branch"] for p in PILLAR_ORDER}

    # 十神
    ten_gods = ten_gods_per_pillar(day_stem, pillars)

    # Weighted 五行
    weighted_counts, root_bonus = weighted_wuxing(pillars, day_stem)

    # Day-master strength
    strength = day_master_strength(day_stem, month_branch, weighted_counts, pillars)

    # 神煞
    shensha_list: list[dict] = []
    if not args.no_shensha:
        shensha_data = _load_json("shensha.json")
        shensha_list = detect_all_shensha(
            shensha_data,
            day_stem=day_stem,
            day_branch=day_branch,
            day_ganzhi=day_ganzhi,
            year_stem=year_stem,
            year_branch=year_branch,
            month_branch=month_branch,
            stems_map=stems_map,
            branches_map=branches_map,
            gender=args.gender,
        )

    # 干支 互动
    interactions = detect_interactions(pillars)

    # 用神 / 喜神 / 忌神
    yong_shen = xi_shen = ji_shen = None
    if not args.no_yongshen:
        tiaohou_data = _load_json("tiaohou.json")
        yj = select_yong_shen(
            day_stem, month_branch, strength, weighted_counts, tiaohou_data
        )
        yong_shen = yj["yong_shen"]
        xi_shen = yj["xi_shen"]
        ji_shen = yj["ji_shen"]

    # 格局
    ge_ju = None
    if not args.no_geju:
        ge_ju = detect_ge_ju(day_stem, pillars, weighted_counts, strength)

    # 大运
    da_yun_list: list[dict] = []
    qi_yun: Optional[dict] = None
    try:
        yun = eight.getYun(1 if args.gender == "male" else 0)
        start_solar = yun.getStartSolar()
        cycles = yun.getDaYun(args.years // 10 + 2)
        for d in cycles:
            ganzhi = d.getGanZhi()
            if not ganzhi:
                continue
            stem = ganzhi[0]
            branch = ganzhi[1] if len(ganzhi) > 1 else ""
            da_yun_list.append({
                "start_age": d.getStartAge(),
                "start_year": d.getStartYear(),
                "end_year": d.getEndYear(),
                "ganzhi": ganzhi,
                "stem": stem,
                "branch": branch,
                "shi_shen": _shi_shen_safe(day_stem, stem) if stem in TIANGAN_WUXING else "",
                "branch_wuxing": DIZHI_WUXING.get(branch),
            })
        qi_yun = {
            "start_year": start_solar.getYear(),
            "start_month": start_solar.getMonth(),
            "start_day": start_solar.getDay(),
            "start_age": yun.getStartYear(),
        }
    except Exception as e:
        warn(f"da_yun unavailable: {e}")

    # 流年 — current solar year + next 5
    liu_nian: list[dict] = []
    try:
        from datetime import datetime
        now_year = datetime.now().year
        for y in range(now_year, now_year + 6):
            ly = Solar.fromYmdHms(y, 6, 1, 12, 0, 0).getLunar()
            gz = ly.getYearInGanZhi()
            year_stem_y = gz[0] if gz else ""
            liu_nian.append({
                "year": y,
                "ganzhi": gz,
                "zodiac": ly.getYearShengXiao(),
                "shi_shen": _shi_shen_safe(day_stem, year_stem_y) if year_stem_y in TIANGAN_WUXING else "",
            })
    except Exception as e:
        warn(f"liu_nian failed: {e}")

    result: dict[str, Any] = {
        "ok": True,
        "tool": "bazi",
        "version": VERSION,
        "input": vars(args),
        "true_solar_time": tst_info,
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(),
            "day": lunar.getDay(),
            "year_in_ganzhi": lunar.getYearInGanZhi(),
            "month_in_ganzhi": lunar.getMonthInGanZhi(),
            "day_in_ganzhi": lunar.getDayInGanZhi(),
            "time_in_ganzhi": lunar.getTimeInGanZhi(),
            "year_in_chinese": lunar.getYearInChinese(),
            "month_in_chinese": lunar.getMonthInChinese(),
            "day_in_chinese": lunar.getDayInChinese(),
            "zodiac": lunar.getYearShengXiao(),
        },
        "four_pillars": pillars,
        "day_master": {
            "stem": day_stem,
            "wuxing": TIANGAN_WUXING.get(day_stem),
            "yin_yang": TIANGAN_YIN_YANG.get(day_stem),
        },
        "ten_gods": ten_gods,
        "wuxing_count": {
            "weighted": {k: round(v, 3) for k, v in weighted_counts.items()},
            "root_bonus": {k: round(v, 3) for k, v in root_bonus.items()},
        },
        "day_master_strength": strength,
        "interactions": interactions,
        "shen_sha": shensha_list,
        "yong_shen": yong_shen,
        "xi_shen": xi_shen,
        "ji_shen": ji_shen,
        "ge_ju": ge_ju,
        "na_yin": {
            "year": year_nayin, "month": month_nayin,
            "day": day_nayin, "hour": hour_nayin,
        },
        "qi_yun": qi_yun,
        "da_yun": da_yun_list,
        "liu_nian": liu_nian,
    }

    json_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
