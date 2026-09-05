"""八字: weighted 五行, 日主旺衰, 用神 / 喜神 / 忌神."""
from __future__ import annotations

from utils import (
    HIDDEN_STEMS,
    TIANGAN_WUXING,
    WUXING_GEN,
    WUXING_KE,
)

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
    counts: dict[str, float] = dict.fromkeys(["木", "火", "土", "金", "水"], 0.0)
    root_bonus: dict[str, float] = dict.fromkeys(["木", "火", "土", "金", "水"], 0.0)

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


# 月令 状态分。三项都必须能双向推动, 且以 0.5 为中性点 —— 从前三项各自不对称,
# 且都指向同一个方向:
#   月令  +0.45 .. -0.10   得令加 0.45, 失令只扣 0.10
#   通根  +0.00 .. +0.20   只加不减, 无根不扣分
#   党众  中性点定在 0.4 而非 0.5, 于是过半局面都在加分
# 合起来 身旺 只要「得令」一项就够 (0.5+0.45=0.95), 而 身弱 要同时满足
# 死地 + 通根0 + 党众<0.2。实测 400 张随机盘 身旺+偏旺 占 75%, 身弱 3 张 ——
# 一个把四分之三的人判成同一类的字段, 携带的信息接近零。
#
# 旺衰是 00-intake.md 强制每次八字批断必出的字段, 且经 pick_yong_shen 分叉决定
# 用神取「克泄耗」还是取「生扶」—— 极性错则大运流年吉凶、方位、颜色、行业全部
# 反号。所以这不是口味问题。
STATE_SCORE: dict[str, float] = {
    "旺": 0.45, "相": 0.22, "休": -0.10, "囚": -0.30, "死": -0.45,
}


def strength_score(state: str, rooted: int, party_ratio: float) -> float:
    """日主强弱分, 0..1, 0.5 为中性。

    权重按「月令为重, 次通根, 次党众」: 令 ±0.45 > 地 ±0.30 > 势 ±0.20。

    除以 2.4 而非直接加 0.5 后截断: 截断会让分数在 0 与 1 两端堆积 (实测旧式 500
    盘里 34% 被截断), 五档于是退化成近似二分类。缩放后满量程落在 [0.10, 0.90],
    不触边界, 且「单项占优 → 偏旺/偏弱, 两项以上 → 身旺/身弱」—— 合于
    「月令虽旺, 无根则虚」: 仅得令 (raw=0.45) 得 0.69 判偏旺, 得令又得地
    (raw=0.75) 才 0.81 判身旺。
    """
    raw = (STATE_SCORE.get(state, -0.10)
           + (rooted - 2) * 0.15          # 通根 2 处为中性
           + (party_ratio - 0.5) * 0.4)   # 同我+生我 占半为中性
    return 0.5 + raw / 2.4


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

    # 三项都必须能双向推动, 且以 0.5 为中性点 —— 从前三项各自不对称, 且都指向同一
    # 个方向:
    #   月令  +0.45 .. -0.10   得令加 0.45, 失令只扣 0.10
    #   通根  +0.00 .. +0.20   只加不减, 无根不扣分
    #   党众  中性点定在 0.4 而非 0.5, 于是过半局面都在加分
    # 合起来: 身旺 只要「得令」一项就够 (0.5+0.45=0.95), 而 身弱 要同时满足
    # 死地 + 通根0 + 党众<0.2。实测 400 张随机盘 身旺+偏旺 占 75%, 身弱 3 张。
    #
    # 旺衰是 00-intake.md 强制每次八字批断必出的字段, 且经 pick_yong_shen 分叉决定
    # 用神取「克泄耗」还是取「生扶」—— 极性错则大运流年吉凶、方位、颜色、行业全部
    # 反号。所以这不是口味问题。
    #
    # 权重按「月令为重, 次通根, 次党众」: 令 ±0.45 > 地 ±0.30 > 势 ±0.20。
    score = strength_score(state, rooted, party_ratio)

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
    tiaohou_data: dict | None,
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
    tiaohou_primary: str | None = None
    tiaohou_reason = ""
    if tiaohou_data and isinstance(tiaohou_data, dict):
        # Accept either flat top-level keys or nested under "tiaohou"
        nested = tiaohou_data.get("tiaohou") if isinstance(tiaohou_data.get("tiaohou"), dict) else tiaohou_data
        key = f"{day_stem}|{month_branch}"
        entry = nested.get(key) if isinstance(nested, dict) else None
        if isinstance(entry, dict):
            primary = (
                entry.get("primary")
                or entry.get("yong_shen")
                or entry.get("primary_yongshen")
            )
            if isinstance(primary, list):
                primary = primary[0] if primary else None
            if primary:
                tiaohou_primary = primary
                tiaohou_match = True
                tiaohou_reason = str(
                    entry.get("reason") or entry.get("note") or entry.get("notes") or ""
                )

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
