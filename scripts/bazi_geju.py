"""八字 格局 (BaZi pattern) detection.

Given a chart dict produced by ``bazi_calc.py`` — i.e. one that exposes
``four_pillars``, ``ten_gods``, ``wuxing_count`` and (optionally) a
``day_master_strength`` field — this module classifies the chart into one of
the classical 格局 and reports whether the pattern is 纯 (pure), 破 (broken)
or 救应 (saved).

Detection priority (highest first):

  1. 特殊格 — 从财格 / 从杀格 / 从儿格 / 从势格 / 化气格 / 一行得气 / 两气成象
  2. 正格   — 月支本气 (or 月支透干 ten-god) -> 正官 / 七杀 / 正偏财 / 正偏印 /
              食神 / 伤官 / 建禄 / 月刃

For every 正格 the detector additionally examines whether the structural
star is supported, conflicted (e.g. 冲克), or rescued (e.g. 财生官 against
伤官 attack).

Public API:
    detect_geju(chart) -> dict
"""

from __future__ import annotations

import json
from typing import Optional

# Soft import from scripts.utils — when run as a module-relative import fails
# we fall back to re-declaring the constants we need so the file is fully
# standalone for the self-test.
try:
    from utils import (  # type: ignore
        DIZHI,
        DIZHI_WUXING,
        HIDDEN_STEMS,
        TIANGAN,
        TIANGAN_WUXING,
        TIANGAN_YIN_YANG,
        WUXING_GEN,
        WUXING_KE,
        shi_shen,
    )
except Exception:  # pragma: no cover - allow standalone use
    TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    DIZHI = [
        "子", "丑", "寅", "卯", "辰", "巳",
        "午", "未", "申", "酉", "戌", "亥",
    ]
    TIANGAN_WUXING = {
        "甲": "木", "乙": "木", "丙": "火", "丁": "火",
        "戊": "土", "己": "土", "庚": "金", "辛": "金",
        "壬": "水", "癸": "水",
    }
    DIZHI_WUXING = {
        "子": "水", "丑": "土", "寅": "木", "卯": "木",
        "辰": "土", "巳": "火", "午": "火", "未": "土",
        "申": "金", "酉": "金", "戌": "土", "亥": "水",
    }
    TIANGAN_YIN_YANG = {s: ("阳" if i % 2 == 0 else "阴") for i, s in enumerate(TIANGAN)}
    WUXING_GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    HIDDEN_STEMS = {
        "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
        "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
        "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
        "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
    }

    def shi_shen(day_stem: str, other_stem: str) -> str:
        day_wx = TIANGAN_WUXING[day_stem]
        other_wx = TIANGAN_WUXING[other_stem]
        same = TIANGAN_YIN_YANG[day_stem] == TIANGAN_YIN_YANG[other_stem]
        if day_wx == other_wx:
            return "比肩" if same else "劫财"
        if WUXING_GEN.get(day_wx) == other_wx:
            return "食神" if same else "伤官"
        if WUXING_KE.get(day_wx) == other_wx:
            return "偏财" if same else "正财"
        if WUXING_KE.get(other_wx) == day_wx:
            return "七杀" if same else "正官"
        if WUXING_GEN.get(other_wx) == day_wx:
            return "偏印" if same else "正印"
        return "未知"


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# 月支本气 — the dominant hidden stem of each 地支 (used to pick 月令十神).
MONTH_BRANCH_MAIN_STEM: dict[str, str] = {b: HIDDEN_STEMS[b][0] for b in DIZHI}

# 阳刃 (羊刃) — only for 阳干; 阴干不立 月刃格
YANG_REN: dict[str, str] = {
    "甲": "卯",
    "丙": "午", "戊": "午",
    "庚": "酉",
    "壬": "子",
}

# 五合 — 天干合化对照, 化神 = 化出之五行
WU_HE: dict[tuple[str, str], str] = {
    ("甲", "己"): "土", ("己", "甲"): "土",
    ("乙", "庚"): "金", ("庚", "乙"): "金",
    ("丙", "辛"): "水", ("辛", "丙"): "水",
    ("丁", "壬"): "木", ("壬", "丁"): "木",
    ("戊", "癸"): "火", ("癸", "戊"): "火",
}

# 月令 -> 化气五行 旺地 (when 化神 is 旺 in this month, 化气格 stands)
HUA_QI_FAVOR_MONTH: dict[str, list[str]] = {
    "土": ["丑", "辰", "未", "戌"],
    "金": ["申", "酉", "戌", "巳", "丑"],
    "水": ["亥", "子", "丑", "申"],
    "木": ["寅", "卯", "辰", "亥"],
    "火": ["巳", "午", "未", "寅"],
}

# 一行得气 (专旺) — 五行 -> [月支 旺地]
YI_XING_MONTH: dict[str, list[str]] = {
    "木": ["寅", "卯", "辰"],
    "火": ["巳", "午", "未"],
    "土": ["辰", "戌", "丑", "未"],
    "金": ["申", "酉", "戌"],
    "水": ["亥", "子", "丑"],
}

YI_XING_NAME: dict[str, str] = {
    "木": "曲直格",
    "火": "炎上格",
    "土": "稼穑格",
    "金": "从革格",
    "水": "润下格",
}

# 六冲: 地支六冲对
LIU_CHONG: dict[str, str] = {
    "子": "午", "午": "子",
    "丑": "未", "未": "丑",
    "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰",
    "巳": "亥", "亥": "巳",
}


# --------------------------------------------------------------------------- #
# 通根 / wuxing tally helpers
# --------------------------------------------------------------------------- #


def _has_tonggen(day_stem: str, branches: list[str]) -> bool:
    """Check if day-master has 通根: any branch contains a hidden stem of same 五行."""
    day_wx = TIANGAN_WUXING[day_stem]
    for b in branches:
        for hs in HIDDEN_STEMS.get(b, []):
            if TIANGAN_WUXING.get(hs) == day_wx:
                return True
    return False


def _weighted_wuxing_percent(chart: dict) -> dict[str, float]:
    """Return a normalised (%) 五行 distribution including hidden stems."""
    wx = chart.get("wuxing_count") or {}
    # Prefer the with_hidden tally; fall back to surface counts.
    combined = wx.get("with_hidden") or wx.get("surface") or {}
    total = sum(combined.values()) or 1.0
    return {k: (v / total) * 100.0 for k, v in combined.items()}


def _ten_gods_to_wuxing(day_stem: str, ten_god: str) -> str:
    """Map a 十神 name to its target 五行 relative to the day-master."""
    day_wx = TIANGAN_WUXING[day_stem]
    mapping = {
        "比肩": day_wx, "劫财": day_wx,
        "食神": WUXING_GEN[day_wx], "伤官": WUXING_GEN[day_wx],
        "正财": WUXING_KE[day_wx], "偏财": WUXING_KE[day_wx],
        "正官": _wx_controls(day_wx), "七杀": _wx_controls(day_wx),
        "正印": _wx_generates(day_wx), "偏印": _wx_generates(day_wx),
    }
    return mapping.get(ten_god, "")


def _wx_controls(wx: str) -> str:
    """Return the 五行 that controls (克) ``wx``."""
    for k, v in WUXING_KE.items():
        if v == wx:
            return k
    return ""


def _wx_generates(wx: str) -> str:
    """Return the 五行 that generates (生) ``wx``."""
    for k, v in WUXING_GEN.items():
        if v == wx:
            return k
    return ""


def _stems_and_branches(chart: dict) -> tuple[dict, list[str], list[str]]:
    """Return (pillars_dict, stems[year,month,day,hour], branches[same])."""
    pillars = chart.get("four_pillars") or {}
    order = ("year", "month", "day", "hour")
    stems = [pillars.get(k, {}).get("stem", "") for k in order]
    branches = [pillars.get(k, {}).get("branch", "") for k in order]
    return pillars, stems, branches


# --------------------------------------------------------------------------- #
# 特殊格 detectors
# --------------------------------------------------------------------------- #


def _detect_cong_ge(
    day_stem: str,
    stems: list[str],
    branches: list[str],
    pct: dict[str, float],
) -> Optional[dict]:
    """Detect 从财/从杀/从儿/从势 — when 日主 is rootless and overwhelmed."""
    if _has_tonggen(day_stem, branches):
        return None

    day_wx = TIANGAN_WUXING[day_stem]
    yin_pct = pct.get(_wx_generates(day_wx), 0.0)
    bi_pct = pct.get(day_wx, 0.0)
    # 印 + 比 too strong -> not 从
    if yin_pct + bi_pct >= 10.0:
        return None

    cai_wx = WUXING_KE[day_wx]
    shasha_wx = _wx_controls(day_wx)
    shi_wx = WUXING_GEN[day_wx]

    cai_pct = pct.get(cai_wx, 0.0)
    sha_pct = pct.get(shasha_wx, 0.0)
    shi_pct = pct.get(shi_wx, 0.0)

    if cai_pct > 55.0:
        return {
            "primary": "从财格",
            "type": "特殊格",
            "supporting_evidence": [
                f"日主 {day_stem}({day_wx}) 无通根, 印比之力 {yin_pct + bi_pct:.1f}% < 10%",
                f"财星 {cai_wx} 占比 {cai_pct:.1f}% > 55%, 满盘以财为势",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论从格》",
            "interpretation": "从财格主一生富足, 喜行财乡、食伤之运, 忌印比破格, 大利商贾经营.",
            "secondary_patterns": [],
        }

    if sha_pct > 55.0:
        return {
            "primary": "从杀格",
            "type": "特殊格",
            "supporting_evidence": [
                f"日主 {day_stem}({day_wx}) 无通根",
                f"官杀 {shasha_wx} 占比 {sha_pct:.1f}% > 55%, 满盘以官杀为势",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论从格》",
            "interpretation": "从杀格主权威武贵, 喜行官杀、财乡之运, 忌印比比劫破格, 利武职、领导职.",
            "secondary_patterns": [],
        }

    if shi_pct > 55.0:
        return {
            "primary": "从儿格",
            "type": "特殊格",
            "supporting_evidence": [
                f"日主 {day_stem}({day_wx}) 无通根",
                f"食伤 {shi_wx} 占比 {shi_pct:.1f}% > 55%, 满盘以食伤为势",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论从儿格》",
            "interpretation": "从儿格主聪明才秀, 喜行食伤、财乡之运, 利文艺、技艺、自由职业.",
            "secondary_patterns": [],
        }

    # 从势 — 财官食伤皆旺, 取势力最强者
    if (cai_pct + sha_pct + shi_pct) > 70.0:
        dominant = max(
            (("财", cai_pct), ("官杀", sha_pct), ("食伤", shi_pct)),
            key=lambda x: x[1],
        )
        return {
            "primary": "从势格",
            "type": "特殊格",
            "supporting_evidence": [
                f"日主 {day_stem}({day_wx}) 无通根, 印比之力极弱",
                f"财官食伤合计 {cai_pct + sha_pct + shi_pct:.1f}%, 最旺为 {dominant[0]} ({dominant[1]:.1f}%)",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论从势格》",
            "interpretation": f"从势格取最旺者({dominant[0]})为用, 喜行该方向之运, 忌印比逆势.",
            "secondary_patterns": [],
        }

    return None


def _detect_hua_qi(
    day_stem: str,
    stems: list[str],
    branches: list[str],
) -> Optional[dict]:
    """Detect 化气格 — day stem combines with month or hour stem to transform."""
    month_branch = branches[1]
    # 日干 与 月干 OR 时干
    for pair_label, other_stem in (("月干", stems[1]), ("时干", stems[3])):
        if not other_stem:
            continue
        hua_wx = WU_HE.get((day_stem, other_stem))
        if not hua_wx:
            continue
        # 化神 月令 旺
        if month_branch not in HUA_QI_FAVOR_MONTH.get(hua_wx, []):
            continue
        # 透干 — 化神之干 出现在四柱
        hua_stems = [s for s, w in TIANGAN_WUXING.items() if w == hua_wx]
        if not any(s in stems for s in hua_stems):
            continue
        return {
            "primary": f"化气格 ({hua_wx})",
            "type": "特殊格",
            "supporting_evidence": [
                f"日干 {day_stem} 与 {pair_label} {other_stem} 相合化 {hua_wx}",
                f"月支 {month_branch} 为 化神 {hua_wx} 之旺地",
                f"四柱 透出化神之干, 化气真实",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论化气》",
            "interpretation": f"化气格主一生变化非凡, 喜行化神 {hua_wx} 之运, 忌克制 {hua_wx} 之神出现.",
            "secondary_patterns": [],
        }
    return None


def _detect_yi_xing(
    day_stem: str,
    stems: list[str],
    branches: list[str],
    pct: dict[str, float],
) -> Optional[dict]:
    """Detect 一行得气 (专旺): month branch + most pillars share day-master 五行."""
    day_wx = TIANGAN_WUXING[day_stem]
    month_branch = branches[1]
    if month_branch not in YI_XING_MONTH.get(day_wx, []):
        return None
    # 大多数 五行 都是 day master 的 五行 (>= 60%)
    if pct.get(day_wx, 0.0) < 60.0:
        return None
    return {
        "primary": YI_XING_NAME[day_wx],
        "type": "特殊格",
        "supporting_evidence": [
            f"日干 {day_stem}({day_wx}) 月支 {month_branch} 当令",
            f"五行 {day_wx} 占比 {pct.get(day_wx, 0.0):.1f}% (>= 60%)",
            "全局一行独旺, 不见克破",
        ],
        "broken_or_pure": "纯",
        "broken_by": None,
        "saved_by": None,
        "classical_source": "《滴天髓·一行得气》",
        "interpretation": f"{YI_XING_NAME[day_wx]} 主一气专旺, 喜行 {day_wx} 与其生泄之运, 忌冲克破气.",
        "secondary_patterns": [],
    }


def _detect_liang_qi(pct: dict[str, float]) -> Optional[dict]:
    """Detect 两气成象 — only two 五行 each ~50%."""
    nonzero = [(k, v) for k, v in pct.items() if v >= 5.0]
    if len(nonzero) != 2:
        return None
    a, b = nonzero[0][1], nonzero[1][1]
    if a < 30.0 or b < 30.0:
        return None
    wxs = sorted([nonzero[0][0], nonzero[1][0]])
    return {
        "primary": "两气成象",
        "type": "特殊格",
        "supporting_evidence": [
            f"全局仅见 {'/'.join(wxs)} 两种五行, 比例 {a:.1f}% / {b:.1f}%",
        ],
        "broken_or_pure": "纯",
        "broken_by": None,
        "saved_by": None,
        "classical_source": "《滴天髓·两气成象》",
        "interpretation": "两气成象, 主性情专一, 命局有偏锋之美, 喜行不破两气之运, 大忌第三气来破象.",
        "secondary_patterns": [],
    }


# --------------------------------------------------------------------------- #
# 正格 detectors
# --------------------------------------------------------------------------- #


def _detect_jian_lu_yang_ren(
    day_stem: str,
    stems: list[str],
    branches: list[str],
) -> Optional[dict]:
    """建禄格 / 月刃格 — month branch matches day-master 五行 or 阳刃."""
    day_wx = TIANGAN_WUXING[day_stem]
    month_branch = branches[1]
    month_wx = DIZHI_WUXING.get(month_branch, "")

    # 月刃格 — only for 阳干
    if YANG_REN.get(day_stem) == month_branch:
        return {
            "primary": "月刃格",
            "type": "正格",
            "supporting_evidence": [
                f"月支 {month_branch} 为日干 {day_stem} 之 阳刃",
            ],
            "broken_or_pure": "纯",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "《子平真诠·论羊刃》",
            "interpretation": "月刃格主刚烈勇敢, 喜官杀制刃, 利武职、武贵或开创之业, 忌再见羊刃叠加.",
            "secondary_patterns": [],
        }

    # 建禄格 — 月支同 day-master 五行 (e.g. 甲日寅月)
    if month_wx == day_wx and month_branch in HIDDEN_STEMS.get(month_branch, []) + []:
        # 月支本气与日干同五行
        if TIANGAN_WUXING.get(MONTH_BRANCH_MAIN_STEM.get(month_branch, ""), "") == day_wx:
            return {
                "primary": "建禄格",
                "type": "正格",
                "supporting_evidence": [
                    f"月支 {month_branch}({month_wx}) 与日干 {day_stem}({day_wx}) 同气, 为禄神",
                ],
                "broken_or_pure": "纯",
                "broken_by": None,
                "saved_by": None,
                "classical_source": "《子平真诠·论建禄》",
                "interpretation": "建禄格主自立自强, 喜财官两旺, 利白手起家与独立事业, 忌劫财夺财.",
                "secondary_patterns": [],
            }
    return None


def _detect_main_zhenge(
    day_stem: str,
    stems: list[str],
    branches: list[str],
) -> Optional[dict]:
    """正格 by 月支本气透干 to 天干."""
    month_branch = branches[1]
    main_hidden = MONTH_BRANCH_MAIN_STEM.get(month_branch)
    if not main_hidden:
        return None
    main_sg = shi_shen(day_stem, main_hidden)

    # 比肩 / 劫财 -> 建禄/月刃 (handled separately)
    if main_sg in ("比肩", "劫财"):
        return None

    # Check 月支本气 透出 在天干 (年/月/时, not 日干本身)
    transparent_in = [s for s in (stems[0], stems[1], stems[3]) if s == main_hidden]
    if not transparent_in:
        # 不透干, 仍可成格 (以月令气为格) - 我们标记为 半透 / 据月气
        evidence_extra = "月支本气未透干, 以月令气为格"
        pure_strict = False
    else:
        evidence_extra = f"月支本气 {main_hidden} 透出于天干"
        pure_strict = True

    # Map 十神 to 格名
    GE_MAP = {
        "正官": "正官格", "七杀": "七杀格",
        "正财": "正财格", "偏财": "偏财格",
        "正印": "正印格", "偏印": "偏印格",
        "食神": "食神格", "伤官": "伤官格",
    }
    ge_name = GE_MAP.get(main_sg)
    if not ge_name:
        return None

    return {
        "primary": ge_name,
        "type": "正格",
        "supporting_evidence": [
            f"月支 {month_branch} 本气藏干 {main_hidden}, 对日主 {day_stem} 为 {main_sg}",
            evidence_extra,
        ],
        "broken_or_pure": "纯" if pure_strict else "破",
        "broken_by": None if pure_strict else "本气未透干, 格局力减",
        "saved_by": None,
        "classical_source": f"《子平真诠·论{main_sg}》",
        "interpretation": _ge_interpretation(ge_name),
        "secondary_patterns": [],
    }


def _ge_interpretation(ge_name: str) -> str:
    table = {
        "正官格": "正官格主正直守礼, 名声地位, 喜见正财生官, 印星护官, 忌见七杀混杂、伤官见官.",
        "七杀格": "七杀格主权威武贵, 喜见食神制杀或印化杀, 忌见正官混杂、财生杀过旺.",
        "正财格": "正财格主富而稳重, 喜见食伤生财、官星护财, 忌见比劫夺财.",
        "偏财格": "偏财格主豪爽富裕, 财来财去, 喜食伤生财、官护财, 忌比劫夺财.",
        "正印格": "正印格主学问厚重, 性情仁慈, 喜见官生印, 忌见财来破印.",
        "偏印格": "偏印格主偏门技艺, 心思深沉, 喜杀印相生, 忌见正印混杂、食神被夺.",
        "食神格": "食神格主聪明衣食, 性格温和, 喜见财星泄秀, 忌见偏印夺食、七杀克身.",
        "伤官格": "伤官格主才华横溢, 个性独立, 喜见财星或印星(伤官佩印), 忌见正官、官星受伤.",
    }
    return table.get(ge_name, "格局清纯, 主才华独立.")


# --------------------------------------------------------------------------- #
# 破 / 救应 judgement helpers
# --------------------------------------------------------------------------- #


def _judge_purity(
    result: dict,
    day_stem: str,
    stems: list[str],
    branches: list[str],
) -> None:
    """Refine ``broken_or_pure`` based on 冲克 / 救应 for the detected 正格."""
    if result.get("type") != "正格":
        return

    ge = result["primary"]
    month_branch = branches[1]

    # 冲: 月支被其它支冲
    chong_target = LIU_CHONG.get(month_branch)
    if chong_target and chong_target in (branches[0], branches[2], branches[3]):
        result["broken_or_pure"] = "破"
        result["broken_by"] = f"月支 {month_branch} 被 {chong_target} 冲, 格神受伤"
        # 救应: 财生官 (官杀格), 食伤泄秀 (印格)
        rescue = _check_rescue(ge, day_stem, stems)
        if rescue:
            result["broken_or_pure"] = "救应"
            result["saved_by"] = rescue
        return

    # 官杀混杂
    if ge in ("正官格", "七杀格"):
        has_zheng_guan = any(shi_shen(day_stem, s) == "正官" for s in stems if s)
        has_qi_sha = any(shi_shen(day_stem, s) == "七杀" for s in stems if s)
        if has_zheng_guan and has_qi_sha:
            result["broken_or_pure"] = "破"
            result["broken_by"] = "官杀混杂, 格局不清"
            rescue = _check_rescue(ge, day_stem, stems)
            if rescue:
                result["broken_or_pure"] = "救应"
                result["saved_by"] = rescue

    # 伤官见官
    if ge == "正官格":
        if any(shi_shen(day_stem, s) == "伤官" for s in stems if s):
            result["broken_or_pure"] = "破"
            result["broken_by"] = "伤官见官, 官星受伤"
            if any(shi_shen(day_stem, s) in ("正印", "偏印") for s in stems if s):
                result["broken_or_pure"] = "救应"
                result["saved_by"] = "印星护官, 伤官佩印化解"

    # 财坏印
    if ge in ("正印格", "偏印格"):
        if any(shi_shen(day_stem, s) in ("正财", "偏财") for s in stems if s):
            result["broken_or_pure"] = "破"
            result["broken_by"] = "财来坏印, 印星受损"
            if any(shi_shen(day_stem, s) in ("比肩", "劫财") for s in stems if s):
                result["broken_or_pure"] = "救应"
                result["saved_by"] = "比劫护印, 财星被分"


def _check_rescue(ge: str, day_stem: str, stems: list[str]) -> Optional[str]:
    """Common rescue heuristics per 格局."""
    sgs = [shi_shen(day_stem, s) for s in stems if s]
    if ge in ("正官格", "七杀格"):
        if any(s in ("正财", "偏财") for s in sgs):
            return "财星生官杀, 格神得救"
    if ge in ("正财格", "偏财格"):
        if any(s in ("食神", "伤官") for s in sgs):
            return "食伤生财, 财源不竭"
    if ge in ("正印格", "偏印格"):
        if any(s in ("正官", "七杀") for s in sgs):
            return "官杀生印, 印星有源"
    if ge in ("食神格", "伤官格"):
        if any(s in ("正财", "偏财") for s in sgs):
            return "财星引泄秀气, 食伤有出路"
    return None


# --------------------------------------------------------------------------- #
# Secondary patterns (神煞)
# --------------------------------------------------------------------------- #


def _secondary_patterns(chart: dict) -> list[str]:
    """Roll up neat 神煞 hits already detected by bazi_calc into pattern labels."""
    shen_sha = chart.get("shen_sha") or []
    seen: set[str] = set()
    for item in shen_sha:
        name = item.get("name")
        if name in (
            "天乙贵人", "文昌贵人", "桃花", "驿马", "华盖",
            "羊刃", "红艳", "孤辰", "寡宿", "空亡",
        ):
            seen.add(f"{name}入命")
    return sorted(seen)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def detect_geju(chart: dict) -> dict:
    """Detect the dominant 八字 格局 from a chart dict.

    Args:
        chart: BaZi chart as produced by ``bazi_calc.py``.

    Returns:
        A dict with keys: primary, type, supporting_evidence, broken_or_pure,
        broken_by, saved_by, classical_source, interpretation, secondary_patterns.
    """
    pillars, stems, branches = _stems_and_branches(chart)
    if not all(stems) or not all(branches):
        return {
            "primary": "未识别",
            "type": "未知",
            "supporting_evidence": ["四柱不完整, 无法判定格局"],
            "broken_or_pure": "未知",
            "broken_by": None,
            "saved_by": None,
            "classical_source": "",
            "interpretation": "请确认八字四柱完整后再行判断.",
            "secondary_patterns": [],
        }

    day_stem = stems[2]
    pct = _weighted_wuxing_percent(chart)

    # ---- 特殊格 first ----
    for detector in (
        lambda: _detect_cong_ge(day_stem, stems, branches, pct),
        lambda: _detect_hua_qi(day_stem, stems, branches),
        lambda: _detect_yi_xing(day_stem, stems, branches, pct),
        lambda: _detect_liang_qi(pct),
    ):
        try:
            r = detector()
        except Exception:
            r = None
        if r:
            r["secondary_patterns"] = _secondary_patterns(chart)
            return r

    # ---- 正格 — 建禄 / 月刃 first, then 月支透干 ----
    r = _detect_jian_lu_yang_ren(day_stem, stems, branches)
    if r is None:
        r = _detect_main_zhenge(day_stem, stems, branches)
    if r:
        _judge_purity(r, day_stem, stems, branches)
        r["secondary_patterns"] = _secondary_patterns(chart)
        return r

    # ---- Fallback ----
    return {
        "primary": "杂气格",
        "type": "正格",
        "supporting_evidence": [
            f"月支 {branches[1]} 本气未透, 且无明显格局",
        ],
        "broken_or_pure": "破",
        "broken_by": "格神不清",
        "saved_by": None,
        "classical_source": "《子平真诠·论杂气》",
        "interpretation": "杂气格力薄, 富贵难以专一, 需细察月令藏干透出何神以定用神方向.",
        "secondary_patterns": _secondary_patterns(chart),
    }


# --------------------------------------------------------------------------- #
# Inline self-test
# --------------------------------------------------------------------------- #


def _sample_chart_zheng_guan() -> dict:
    """甲日生于酉月, 时干透辛 (正官格) — 1984年农历八月一日酉时."""
    return {
        "four_pillars": {
            "year": {"stem": "甲", "branch": "子"},
            "month": {"stem": "癸", "branch": "酉"},
            "day": {"stem": "甲", "branch": "辰"},
            "hour": {"stem": "辛", "branch": "未"},
        },
        "wuxing_count": {
            "surface": {"木": 2, "火": 0, "土": 2, "金": 2, "水": 2},
            "with_hidden": {"木": 2.5, "火": 0.5, "土": 3.5, "金": 2.5, "水": 3.0},
        },
        "shen_sha": [],
    }


def _sample_chart_cong_cai() -> dict:
    """日主无根 (甲日, 四柱全无木根), 财星(土)占主导 — 从财格示例."""
    return {
        "four_pillars": {
            "year": {"stem": "戊", "branch": "戌"},
            "month": {"stem": "戊", "branch": "午"},
            "day": {"stem": "甲", "branch": "申"},
            "hour": {"stem": "戊", "branch": "戌"},
        },
        # 戌(戊辛丁), 午(丁己), 申(庚壬戊), 戌(戊辛丁) — no 木 hidden anywhere
        "wuxing_count": {
            "with_hidden": {
                "木": 0.0,
                "火": 1.5,
                "土": 9.5,
                "金": 2.5,
                "水": 0.5,
            },
        },
        "shen_sha": [{"name": "华盖", "branch": "戌"}],
    }


if __name__ == "__main__":
    for label, sample in (
        ("zheng_guan_格", _sample_chart_zheng_guan()),
        ("cong_cai_格", _sample_chart_cong_cai()),
    ):
        print(f"=== {label} ===")
        result = detect_geju(sample)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()
