"""八字: 神煞 detection, driven by assets/shensha.json."""
from __future__ import annotations

from typing import Any

from bazi_tables import PILLAR_LABELS_CN, xun_kong_of_day

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
# Tables live in assets/shensha.json; a missing table must not silently select
# a second, independently maintained implementation.

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


def _find_entry(shensha_data: dict | None, name: str) -> dict | None:
    """Locate a shensha entry by name across all top-level categories."""
    if not isinstance(shensha_data, dict):
        return None
    for _category, entries in shensha_data.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("name") == name:
                return e
    return None


def detect_all_shensha(
    shensha_data: dict | None,
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
    trigger}. Uses the tables in assets/shensha.json. Missing tables produce
    no inferred hit; the caller must supply the complete reference asset.
    """
    triggered: list[dict] = []

    for name, category in SHENSHA_CATEGORY.items():
        entry = _find_entry(shensha_data, name) if shensha_data else None
        meaning = ""
        qi_fa = (entry or {}).get("qi_fa_table")

        if category == "day_stem":
            # Some names (红艳 vs 红艳煞) appear in either category list.
            if qi_fa is None and name in ("红艳",):
                # alias
                alt = _find_entry(shensha_data, "红艳煞")
                if alt:
                    qi_fa = alt.get("qi_fa_table")
            if qi_fa is None:
                raise ValueError(f'神煞起法表缺失: {name}')
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
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for h in triggered:
        dedup_key = (h["name"], h.get("position"), h.get("hit"))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        h.pop('meaning', None)
        h['interpretation_status'] = 'trigger_only'
        deduped.append(h)
    return deduped


# --------------------------------------------------------------------------- #
