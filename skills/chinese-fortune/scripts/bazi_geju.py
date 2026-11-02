"""八字: 格局判定 (正格 / 特殊格)."""
from __future__ import annotations

from bazi_strength import _ke_me, _me_ke, _sheng_me, _xie_me
from bazi_tables import PILLAR_LABELS_CN, TIANGAN_HE
from utils import (
    DIZHI_WUXING,
    HIDDEN_STEMS,
    TIANGAN_WUXING,
    TIANGAN_YIN_YANG,
    WUXING_KE,
    shi_shen,
)

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
    hour_stem = pillars.get("hour", {}).get("stem", "")  # absent in three-pillar mode

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

    # --- 从势格 / 从印格(从强) ---
    # references/01-bazi.md §6.2 列了五种从格, 引擎从前只认三种 (从财/从杀/从儿),
    # 且都要求单一五行 > 60%。真实的从势格往往是 财 40% + 官 30% 这种合力压制,
    # 任一单项都够不到 60%, 于是静默落回正格 —— 而两者的用神方向正好相反。
    # 实测 400 张随机盘: 37 张无根, 4 张党众 < 15%, 从格命中 0 张。
    if rooted == 0 and yin_share < 0.15:
        others = cai_share + sha_share + er_share
        if others > 0.75:
            strongest_wx, strongest_share = max(
                ((cai_wx, cai_share), (sha_wx, sha_share), (er_wx, er_share)),
                key=lambda kv: kv[1])
            return {
                "primary": "从势格",
                "type": "特殊格",
                "month_origin": "日主无根",
                "supporting_evidence": [
                    f"日主{day_stem}无通根",
                    f"财官食伤合计{others*100:.1f}% (财{cai_share*100:.0f}%/"
                    f"杀{sha_share*100:.0f}%/儿{er_share*100:.0f}%)",
                    f"印比合计仅{yin_share*100:.1f}%",
                    f"势力最强者为{strongest_wx}({strongest_share*100:.0f}%)",
                ],
                "broken_or_pure": "纯" if yin_share < 0.08 else "破",
                "notes": ("从势格: 财官食伤皆旺而日主无根, 用神看势力最强者 "
                          f"({strongest_wx}). 忌印比帮身。"),
            }

    # 从印格(从强): 满盘印比而日主极旺 —— 与从财/从杀方向相反, 从前完全不检测。
    # 阈值 0.70 时 400 盘出 26 张 (6.5%), 远高于 references/01-bazi.md:344 自称的
    # 「千万命中难得一二」。「满盘印比」须字面成立 —— 财官食伤近乎绝迹, 且日主得令。
    if (yin_share > 0.88 and strength.get("label") == "身旺"
            and strength.get("state_from_yueling") in ("旺", "相")):
        return {
            "primary": "从印格",
            "type": "特殊格",
            "month_origin": "印比满盘",
            "supporting_evidence": [
                f"印比合计{yin_share*100:.1f}%",
                f"日主{strength.get('label')}",
                f"财官食伤合计仅{(cai_share + sha_share + er_share)*100:.1f}%",
            ],
            "broken_or_pure": "纯" if yin_share > 0.93 else "破",
            "notes": "从印格(从强): 满盘印比, 顺其旺势, 用印与比劫; 忌财星破印.",
        }

    # --- 一行得气格 ---
    # references/01-bazi.md §6.2: 全局只有一种五行旺盛, 且月令属该五行。
    YIXING = {
        "木": ("曲直格", {"寅", "卯", "辰"}),
        "火": ("炎上格", {"巳", "午", "未"}),
        "土": ("稼穑格", {"辰", "戌", "丑", "未"}),
        "金": ("从革格", {"申", "酉", "戌"}),
        "水": ("润下格", {"亥", "子", "丑"}),
    }
    if day_wx in YIXING:
        name, months = YIXING[day_wx]
        share = weighted_counts.get(day_wx, 0.0) / total_wx
        if month_branch in months and share > 0.70 and rooted >= 2:
            return {
                "primary": name,
                "type": "特殊格",
                "month_origin": f"月支{month_branch}属{day_wx}",
                "supporting_evidence": [
                    f"{day_wx}占全局{share*100:.1f}%",
                    f"月支{month_branch}属{day_wx}",
                    f"日主通根{rooted}处",
                ],
                "broken_or_pure": "纯",
                "notes": f"{name}: 一行得气, 顺其旺势; 最忌克战之神冲破格局.",
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
            if main_wx != hua_wx:
                continue
            # 从前到此为止就返回了, 只查「合」与「化神得令」两条, 而同一段自己的
            # notes 写着「需化神得令且无破化之神」, broken_or_pure 还硬编码成「纯」。
            # 实测 300 张随机盘出 11 张化气格 (3.7%), 而 references/01-bazi.md:344
            # 白纸黑字「特殊格局极少见, 千万命中难得一二。判断时务必严格, 勿勉强
            # 套用」—— 发生率差了几个数量级。ge_ju 是 00-intake.md 强制必出字段,
            # 01-bazi.md:282 称格局「决定一个人的事业天花板和人生主轴」。
            #
            # 补齐经典三条:
            #   1. 日主无根 —— 「有根不化」, 日主自身有气则不肯从合
            #   2. 化神透干 —— 化神须在天干得见, 否则合而不化
            #   3. 无破化之神 —— 有克化神之干则「化神被破」
            if rooted > 0:
                continue                       # 有根不化
            stems = [p_["stem"] for p_ in pillars.values() if p_.get("stem")]
            hua_transparent = any(TIANGAN_WUXING.get(s) == hua_wx for s in stems)
            if not hua_transparent:
                continue                       # 合而不化
            po_wx = next((src for src, tgt in WUXING_KE.items() if tgt == hua_wx), "")
            po_stems = [s for s in stems
                        if TIANGAN_WUXING.get(s) == po_wx and s != day_stem]
            evidence = [
                f"日干{day_stem}与{adjacent_stem}合化{hua_wx}",
                f"月支{month_branch}本气属{hua_wx} (化神得令)",
                "日主无通根 (有根不化)",
                f"化神{hua_wx}透干",
            ]
            if po_stems:
                evidence.append(f"但有破化之神 {''.join(po_stems)} 克{hua_wx}")
            return {
                "primary": f"化{hua_wx}格",
                "type": "特殊格",
                "month_origin": "化神得月令",
                "supporting_evidence": evidence,
                "broken_or_pure": "破" if po_stems else "纯",
                "notes": ("化气格成立需 合化 + 化神得令 + 日主无根 + 化神透干 + "
                          "无破化之神; 行化神旺地为吉. 此格极罕见, 若与其他条件"
                          "冲突应以正格论."),
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
