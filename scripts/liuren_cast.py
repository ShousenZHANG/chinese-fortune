"""大六壬 (Da Liu Ren) 起课 — classical computation.

Pipeline:
  1. Determine 月将 (sun-sign) from 中气 boundary.
  2. 月将加时 → 天地盘 (heaven plate over fixed earth plate).
  3. 排四课 (four lessons) using 日干寄宫 and 日支.
  4. 发三传 (three transmissions) via 九宗门 (priority chain).
  5. 排十二天将 (twelve heavenly generals) starting from 贵人 day/night.
  6. 用神 hint and 旺相休囚 evaluation for 三传.

Sources (re-derived from classical references):
  《六壬大全》 (明·郭载騋)
  《大六壬指南》 (明·陈公献)
  《六壬粹言》 (清·刘赤江)
  references/07-daliuren.md (in-repo summary)

Usage:
    python liuren_cast.py --date 2026-05-16 --time 14:30 [--question "感情"]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from utils import (
    DIZHI,
    DIZHI_WUXING,
    TIANGAN_WUXING,
    TIANGAN_YIN_YANG,
    WUXING_GEN,
    WUXING_KE,
    json_print,
    require_lunar,
)


__version__ = "1.0.0"


# --------------------------------------------------------------------------- #
# 12 月将: 中气 boundary -> 月将地支 + 神名
# Source: 《六壬大全》 月将章
# --------------------------------------------------------------------------- #

ZHONG_QI_TO_YUE_JIANG: list[tuple[str, str, str]] = [
    # (zhong_qi 中气名, yue_jiang 地支, 月将神名)
    ("雨水", "亥", "登明"),
    ("春分", "戌", "河魁"),
    ("谷雨", "酉", "从魁"),
    ("小满", "申", "传送"),
    ("夏至", "未", "小吉"),
    ("大暑", "午", "胜光"),
    ("处暑", "巳", "太乙"),
    ("秋分", "辰", "天罡"),
    ("霜降", "卯", "太冲"),
    ("小雪", "寅", "功曹"),
    ("冬至", "丑", "大吉"),
    ("大寒", "子", "神后"),
]

YUE_JIANG_NAME: dict[str, str] = {z: n for _, z, n in ZHONG_QI_TO_YUE_JIANG}

# Set of 中气 names (for fast membership)
ZHONG_QI_SET = {z for z, _, _ in ZHONG_QI_TO_YUE_JIANG}


# --------------------------------------------------------------------------- #
# 干寄宫 — 天干在地盘所寄之地支
# 甲寄寅, 乙寄辰, 丙戊寄巳, 丁己寄未, 庚寄申, 辛寄戌, 壬寄亥, 癸寄丑
# --------------------------------------------------------------------------- #

GAN_JI_GONG: dict[str, str] = {
    "甲": "寅", "乙": "辰",
    "丙": "巳", "丁": "未",
    "戊": "巳", "己": "未",
    "庚": "申", "辛": "戌",
    "壬": "亥", "癸": "丑",
}


# --------------------------------------------------------------------------- #
# 时辰: hour (0-23) → 地支
# --------------------------------------------------------------------------- #

def hour_to_zhi(hour: int) -> str:
    """Return 地支 for given 24-h clock hour. 子时 spans 23:00–01:00."""
    if hour == 23:
        return "子"
    return DIZHI[((hour + 1) // 2) % 12]


# --------------------------------------------------------------------------- #
# 12 天将 (heavenly generals) — 12 fixed order, distribute from 贵人
# --------------------------------------------------------------------------- #

TWELVE_GENERALS = [
    "贵人", "螣蛇", "朱雀", "六合", "勾陈", "青龙",
    "天空", "白虎", "太常", "玄武", "太阴", "天后",
]

# 贵人歌诀: 甲戊庚牛羊 / 乙己鼠猴乡 / 丙丁猪鸡位 / 壬癸蛇兔藏 / 六辛逢虎马
GUI_REN_DAY_NIGHT: dict[str, tuple[str, str]] = {
    "甲": ("丑", "未"),
    "戊": ("丑", "未"),
    "庚": ("丑", "未"),
    "乙": ("子", "申"),
    "己": ("子", "申"),
    "丙": ("亥", "酉"),
    "丁": ("亥", "酉"),
    "壬": ("巳", "卯"),
    "癸": ("巳", "卯"),
    "辛": ("午", "寅"),
}

# 顺布 if 贵人 lands on 亥子丑寅卯辰; 逆布 if 巳午未申酉戌
SHUN_BU_BRANCHES = {"亥", "子", "丑", "寅", "卯", "辰"}


def is_day_birth(hour: int) -> bool:
    """昼 = 06:00–17:59 inclusive (sun above horizon); 夜 otherwise.

    Classical rule: 卯-酉 (5-6am sunrise to 5-6pm sunset). Here we use
    06:00–17:59 as a practical proxy that covers the 卯时-酉时 span.
    """
    return 6 <= hour < 18


# --------------------------------------------------------------------------- #
# Step 1 — locate 中气 and 月将
# --------------------------------------------------------------------------- #

def determine_yue_jiang(lunar) -> tuple[str, str, str]:
    """Return (zhong_qi 中气名, yue_jiang 地支, 月将神名).

    Uses lunar_python's JieQi table; finds the most recent 中气 <= current time.
    If none of the 12 中气 is yet reached this year, falls back to the previous
    cycle (大寒/子).
    """
    jq_dict = lunar.getJieQiTable()  # dict[name -> Solar]
    solar = lunar.getSolar()
    current_jd = solar.getJulianDay()

    found: list[tuple[float, str]] = []
    for name, jq_solar in jq_dict.items():
        if name not in ZHONG_QI_SET:
            continue
        if jq_solar.getJulianDay() <= current_jd:
            found.append((jq_solar.getJulianDay(), name))

    if not found:
        # Pre-雨水 of current year → previous 大寒 cycle still applies → 子将.
        zhong_qi = "大寒"
    else:
        found.sort(reverse=True)
        zhong_qi = found[0][1]

    yue_jiang_zhi = next(z for q, z, _ in ZHONG_QI_TO_YUE_JIANG if q == zhong_qi)
    return zhong_qi, yue_jiang_zhi, YUE_JIANG_NAME[yue_jiang_zhi]


# --------------------------------------------------------------------------- #
# Step 2 — 天地盘
# --------------------------------------------------------------------------- #

def build_tian_di_pan(yue_jiang: str, zhan_shi: str) -> dict[str, str]:
    """Return 天盘: dict mapping 地盘地支 -> 天盘地支.

    月将 lands above 占时. From there both wheels turn clockwise together,
    so 地盘[i+k] sits under 天盘[j+k] for all k (mod 12), where i=zhan_shi
    index and j=yue_jiang index.
    """
    j = DIZHI.index(yue_jiang)
    i = DIZHI.index(zhan_shi)
    return {
        DIZHI[(i + k) % 12]: DIZHI[(j + k) % 12]
        for k in range(12)
    }


def tian_above(tian_pan: dict[str, str], di_zhi: str) -> str:
    """Return 天盘 character sitting above a 地盘 branch."""
    return tian_pan[di_zhi]


# --------------------------------------------------------------------------- #
# Step 3 — 四课 (lower 下 sits under upper 上)
# 一课 干上: 日干寄宫 → 天盘字
# 二课 干阴: 一课上 作 地盘 → 再上之天盘字
# 三课 支上: 日支 → 天盘字
# 四课 支阴: 三课上 作 地盘 → 再上之天盘字
# --------------------------------------------------------------------------- #

def build_si_ke(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str) -> list[dict]:
    g_ji = GAN_JI_GONG[ri_gan]
    k1_l, k1_u = g_ji, tian_pan[g_ji]
    k2_l, k2_u = k1_u, tian_pan[k1_u]
    k3_l, k3_u = ri_zhi, tian_pan[ri_zhi]
    k4_l, k4_u = k3_u, tian_pan[k3_u]
    return [
        {"index": 1, "name": "干上 (一课)", "lower": k1_l, "upper": k1_u,
         "note": f"日干 {ri_gan} 寄宫 {g_ji} 之天盘"},
        {"index": 2, "name": "干阴 (二课)", "lower": k2_l, "upper": k2_u,
         "note": "一课上神再上之天盘"},
        {"index": 3, "name": "支上 (三课)", "lower": k3_l, "upper": k3_u,
         "note": f"日支 {ri_zhi} 之天盘"},
        {"index": 4, "name": "支阴 (四课)", "lower": k4_l, "upper": k4_u,
         "note": "三课上神再上之天盘"},
    ]


# --------------------------------------------------------------------------- #
# 五行 clash helpers — used in 贼克 detection.
# 下贼上: 下五行 克 上五行 (lower controls upper) — called "贼"
# 上克下: 上五行 克 下五行 — called "克"
# --------------------------------------------------------------------------- #

def wx_of(zhi: str) -> str:
    return DIZHI_WUXING[zhi]


def lower_controls_upper(lower: str, upper: str) -> bool:
    return WUXING_KE.get(wx_of(lower)) == wx_of(upper)


def upper_controls_lower(lower: str, upper: str) -> bool:
    return WUXING_KE.get(wx_of(upper)) == wx_of(lower)


# --------------------------------------------------------------------------- #
# Step 4 — 三传 (nine-method priority chain)
#
# Order in 《六壬大全》:
#   贼克 → 比用 → 涉害 → 遥克 → 昴星 → 别责 → 八专 → 伏吟 → 反吟
#
# We implement: 贼克, 比用, 遥克, 伏吟, 反吟 with priority-rule fallbacks
# for 涉害 / 昴星 / 别责 / 八专 (rare and best handled by a human master).
# --------------------------------------------------------------------------- #

def detect_zei_ke(si_ke: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (zei_list, ke_list).

    zei = 下贼上 entries; ke = 上克下 entries. Each item is the 四课 dict.
    """
    zei: list[dict] = []
    ke: list[dict] = []
    for k in si_ke:
        if lower_controls_upper(k["lower"], k["upper"]):
            zei.append(k)
        elif upper_controls_lower(k["lower"], k["upper"]):
            ke.append(k)
    return zei, ke


def same_polarity_as_gan(zhi: str, ri_gan: str) -> bool:
    """True iff 地支 阴阳 matches 日干 阴阳."""
    gan_yy = TIANGAN_YIN_YANG[ri_gan]
    branch_yy = "阳" if DIZHI.index(zhi) % 2 == 0 else "阴"
    return gan_yy == branch_yy


def next_two_chuan(tian_pan: dict[str, str], chu: str) -> tuple[str, str]:
    """For most courses: 中传 = 天盘[ 初传 (taken as 地盘) ];
                        末传 = 天盘[ 中传 (taken as 地盘) ]."""
    zhong = tian_above(tian_pan, chu)
    mo = tian_above(tian_pan, zhong)
    return zhong, mo


def _pick_by_polarity(candidates: list[dict], ri_gan: str,
                       multi_label: str, mismatch_label: str
                       ) -> tuple[list[dict], str]:
    """比用 sub-rule: prefer 上神 与 日干 同阴阳 candidate; else fall back."""
    same = [k for k in candidates if same_polarity_as_gan(k["upper"], ri_gan)]
    if len(same) == 1:
        return same, multi_label
    if len(same) >= 2:
        return [same[0]], "比用法 / 涉害法简化 (取首位, 复杂涉害请手排)"
    return [candidates[0]], mismatch_label


def fa_yong_zei_ke(si_ke: list[dict], ri_gan: str,
                    tian_pan: dict[str, str]) -> Optional[dict]:
    """贼克法 + 比用法. 贼 (下贼上) takes priority over 克 (上克下)."""
    zei, ke = detect_zei_ke(si_ke)
    pool: Optional[list[dict]] = None
    label = ""
    if len(zei) == 1:
        pool, label = zei, "贼克法 (重审课, 一贼为用)"
    elif not zei and len(ke) == 1:
        pool, label = ke, "贼克法 (元首课, 一克为用)"
    elif len(zei) >= 1:
        pool, label = _pick_by_polarity(
            zei, ri_gan,
            "比用法 (多贼, 取阴阳同日干者)",
            "比用法 (多贼皆异阴阳, 取首位)",
        )
    elif len(ke) >= 2:
        pool, label = _pick_by_polarity(
            ke, ri_gan,
            "比用法 (多克, 取阴阳同日干者)",
            "比用法 (多克皆异阴阳, 取首位)",
        )

    if not pool:
        return None
    chu = pool[0]["upper"]
    zhong, mo = next_two_chuan(tian_pan, chu)
    return {"method": label, "chu_chuan": chu, "zhong_chuan": zhong,
            "mo_chuan": mo, "from_course": pool[0]["index"]}


def fa_yong_yao_ke(si_ke: list[dict], ri_gan: str,
                    tian_pan: dict[str, str]) -> Optional[dict]:
    """遥克法 — no 上下 克贼 at all → 日干 与 天盘上神 互克.

    弹射课 (上神克日干, priority) → 蒿矢课 (日干克上神).
    """
    gan_wx = TIANGAN_WUXING[ri_gan]
    inward, outward = [], []
    for u in (k["upper"] for k in si_ke):
        u_wx = wx_of(u)
        if WUXING_KE.get(u_wx) == gan_wx:
            inward.append(u)
        elif WUXING_KE.get(gan_wx) == u_wx:
            outward.append(u)

    chosen: Optional[str] = None
    label = ""
    for pool, lbl in [(inward, "遥克法 (弹射课, 上神克日干)"),
                      (outward, "遥克法 (蒿矢课, 日干克上神)")]:
        if pool:
            same = [u for u in pool if same_polarity_as_gan(u, ri_gan)]
            chosen = same[0] if same else pool[0]
            label = lbl
            break

    if not chosen:
        return None
    zhong, mo = next_two_chuan(tian_pan, chosen)
    return {"method": label, "chu_chuan": chosen, "zhong_chuan": zhong,
            "mo_chuan": mo, "from_course": None}


def fa_yong_fu_yin(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str,
                   yue_jiang: str, zhan_shi: str) -> Optional[dict]:
    """伏吟法 — 月将 == 占时 (天地盘 各居本位).

    阳日: 初 = 干寄宫上神; 中 = 支上神; 末 = 中传上神.
    阴日: 初 = 支上神; 中 = 干寄宫上神; 末 = 中传上神.
    """
    if yue_jiang != zhan_shi:
        return None
    gan_ji = GAN_JI_GONG[ri_gan]
    gan_yang = TIANGAN_YIN_YANG[ri_gan] == "阳"
    chu = tian_pan[gan_ji] if gan_yang else tian_pan[ri_zhi]
    zhong = tian_pan[ri_zhi] if gan_yang else tian_pan[gan_ji]
    mo = tian_pan[zhong]
    return {"method": "伏吟法 (天地盘同位)", "chu_chuan": chu,
            "zhong_chuan": zhong, "mo_chuan": mo, "from_course": None}


def chong_zhi(zhi: str) -> str:
    """Return 六冲 partner (子↔午, 丑↔未, ...)."""
    return DIZHI[(DIZHI.index(zhi) + 6) % 12]


def fa_yong_fan_yin(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str,
                    yue_jiang: str, zhan_shi: str) -> Optional[dict]:
    """反吟法 — 月将 与 占时 相冲 (e.g. 子加午, 天地盘逐位相冲)."""
    if chong_zhi(yue_jiang) != zhan_shi:
        return None
    chu = tian_pan[ri_zhi]
    zhong = tian_pan[chu]
    mo = tian_pan[zhong]
    return {"method": "反吟法 (天地盘相冲)", "chu_chuan": chu,
            "zhong_chuan": zhong, "mo_chuan": mo, "from_course": None}


def fa_yong_fallback(tian_pan: dict[str, str]) -> dict:
    """昴星法 / 别责 / 八专 简化 — 取酉宫上神为初 (rare; needs hand-排)."""
    chu = tian_pan["酉"]
    zhong, mo = next_two_chuan(tian_pan, chu)
    return {"method": "昴星 / 别责 / 八专 简化路径 (酉宫为用 — 复杂课式需手排)",
            "chu_chuan": chu, "zhong_chuan": zhong, "mo_chuan": mo,
            "from_course": None}


def fa_yong(si_ke: list[dict], ri_gan: str, ri_zhi: str,
            tian_pan: dict[str, str], yue_jiang: str, zhan_shi: str) -> dict:
    """Master nine-method dispatcher: 伏吟 → 反吟 → 贼克/比用 → 遥克 → fallback.

    伏吟 / 反吟 first because they depend on plate config rather than 四课 clashes.
    """
    for fn in (
        lambda: fa_yong_fu_yin(tian_pan, ri_gan, ri_zhi, yue_jiang, zhan_shi),
        lambda: fa_yong_fan_yin(tian_pan, ri_gan, ri_zhi, yue_jiang, zhan_shi),
        lambda: fa_yong_zei_ke(si_ke, ri_gan, tian_pan),
        lambda: fa_yong_yao_ke(si_ke, ri_gan, tian_pan),
    ):
        result = fn()
        if result:
            return result
    return fa_yong_fallback(tian_pan)


# --------------------------------------------------------------------------- #
# Step 5 — 十二天将
# --------------------------------------------------------------------------- #

def build_shi_er_tian_jiang(ri_gan: str, hour: int,
                            tian_pan: dict[str, str]) -> dict[str, dict]:
    """Return 神名 → {di_pan, tian_pan} for each of the 12 generals.

    Generals attach to 地盘 positions starting from 贵人 (day/night branch).
    顺布 if 贵人 lands on 亥子丑寅卯辰; 逆布 otherwise.
    """
    day_gui, night_gui = GUI_REN_DAY_NIGHT[ri_gan]
    gui_di = day_gui if is_day_birth(hour) else night_gui
    step_sign = 1 if gui_di in SHUN_BU_BRANCHES else -1
    gui_idx = DIZHI.index(gui_di)
    return {
        name: {
            "di_pan": (di_pos := DIZHI[(gui_idx + step_sign * k) % 12]),
            "tian_pan": tian_pan[di_pos],
        }
        for k, name in enumerate(TWELVE_GENERALS)
    }


# --------------------------------------------------------------------------- #
# Step 6 — 用神 hint by question keywords
# --------------------------------------------------------------------------- #

QUESTION_USHIN: list[tuple[tuple[str, ...], str]] = [
    (("求财", "财运", "钱", "投资", "生意"),
     "妻财 + 青龙 — 看青龙所临之宫与三传财气."),
    (("求官", "升职", "考核", "公职"),
     "官鬼 + 朱雀 — 朱雀临三传主文书利, 官鬼旺主任用."),
    (("感情", "婚姻", "恋爱", "桃花"),
     "六合 + 妻财/官鬼 — 男看妻财, 女看官鬼; 六合临三传主和合."),
    (("出行", "旅行", "远行", "出差"),
     "驿马 + 青龙 — 青龙临三传主吉行, 白虎临则有道路阻."),
    (("疾病", "病情", "健康"),
     "官鬼 (病象) + 白虎 (凶象) + 子孙 (医药)."),
    (("寻人", "找人", "失踪"),
     "玄武 — 玄武所临之方为藏身或所在方向."),
    (("官司", "诉讼", "纠纷"),
     "朱雀 (文书) + 勾陈 (缠讼) + 白虎 (败诉)."),
    (("失物", "丢失"),
     "玄武 — 所临宫位为失物方向, 配合天将判断特征."),
]


def yong_shen_hint(question: Optional[str]) -> Optional[str]:
    if not question:
        return None
    for keys, hint in QUESTION_USHIN:
        if any(k in question for k in keys):
            return hint
    return None


# --------------------------------------------------------------------------- #
# Step 7 — 旺相休囚 (relative to 月支)
# --------------------------------------------------------------------------- #

SEASON_BY_BRANCH: dict[str, str] = {
    "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土",
    "亥": "水", "子": "水", "丑": "土",
}


def wang_xiang_state(target_wx: str, season_wx: str) -> str:
    if target_wx == season_wx:
        return "旺"
    if WUXING_GEN.get(season_wx) == target_wx:
        return "相"
    if WUXING_GEN.get(target_wx) == season_wx:
        return "休"
    if WUXING_KE.get(target_wx) == season_wx:
        return "囚"
    if WUXING_KE.get(season_wx) == target_wx:
        return "死"
    return "?"


# --------------------------------------------------------------------------- #
# Step 8 — 课体分类 (九宗门)
# --------------------------------------------------------------------------- #

_COURSE_TAGS: list[tuple[str, str]] = [
    ("元首", "九宗门: 贼克法 — 元首课 (一克为用)"),
    ("重审", "九宗门: 贼克法 — 重审课 (一贼为用)"),
    ("贼克", "九宗门: 贼克法"),
    ("比用", "九宗门: 比用法"),
    ("遥克", "九宗门: 遥克法"),
    ("伏吟", "九宗门: 伏吟法"),
    ("反吟", "九宗门: 反吟法"),
    ("昴星", "九宗门: 昴星/别责/八专 (复杂课式简化处理)"),
    ("别责", "九宗门: 昴星/别责/八专 (复杂课式简化处理)"),
    ("八专", "九宗门: 昴星/别责/八专 (复杂课式简化处理)"),
]


def classify_course(fa_yong_method: str) -> str:
    for tag, label in _COURSE_TAGS:
        if tag in fa_yong_method:
            return label
    return "九宗门: 未明 (请查阅典籍)"


# --------------------------------------------------------------------------- #
# Summary text
# --------------------------------------------------------------------------- #

def build_summary(ri_gan: str, ri_zhi: str, san_chuan: dict,
                  yue_jiang_name: str, zhan_shi: str,
                  classification: str, yong_hint: Optional[str]) -> str:
    chu = san_chuan["chu_chuan"]
    zhong = san_chuan["zhong_chuan"]
    mo = san_chuan["mo_chuan"]
    parts = [
        f"日干支 {ri_gan}{ri_zhi}, 月将 {yue_jiang_name} 加 {zhan_shi} 时.",
        f"三传: 初 {chu} → 中 {zhong} → 末 {mo}.",
        classification + ".",
    ]
    if yong_hint:
        parts.append(f"用神提示: {yong_hint}")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="大六壬起课 (月将加时 → 四课 → 三传 → 十二天将)")
    p.add_argument("--date", required=True, help="占问日期 YYYY-MM-DD")
    p.add_argument("--time", required=True, help="占问时辰 HH:MM")
    p.add_argument("--longitude", type=float, default=None,
                   help="经度 (可选, 仅记录, 不参与时辰换算; 真太阳时需另行调整)")
    p.add_argument("--question", type=str, default=None,
                   help="所问之事 (用于 用神 提示)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dt = datetime.strptime(f"{args.date} {args.time}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        json_print({"error": "invalid_datetime", "message": str(exc)})
        return 1

    require_lunar()
    from lunar_python import Solar  # type: ignore

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    lunar = solar.getLunar()

    ri_gan = lunar.getDayGan()
    ri_zhi = lunar.getDayZhi()
    month_zhi = lunar.getMonthZhi()

    zhong_qi, yue_jiang, yue_jiang_name = determine_yue_jiang(lunar)
    zhan_shi = hour_to_zhi(dt.hour)

    tian_pan = build_tian_di_pan(yue_jiang, zhan_shi)
    si_ke = build_si_ke(tian_pan, ri_gan, ri_zhi)
    san_chuan = fa_yong(si_ke, ri_gan, ri_zhi, tian_pan, yue_jiang, zhan_shi)

    is_day = is_day_birth(dt.hour)
    shi_er = build_shi_er_tian_jiang(ri_gan, dt.hour, tian_pan)

    season_wx = SEASON_BY_BRANCH[month_zhi]
    wang_xiang = {
        "chu": wang_xiang_state(wx_of(san_chuan["chu_chuan"]), season_wx),
        "zhong": wang_xiang_state(wx_of(san_chuan["zhong_chuan"]), season_wx),
        "mo": wang_xiang_state(wx_of(san_chuan["mo_chuan"]), season_wx),
    }

    classification = classify_course(san_chuan["method"])
    yong_hint = yong_shen_hint(args.question)

    out = {
        "ok": True,
        "tool": "daliuren",
        "version": __version__,
        "input": {
            "date": args.date,
            "time": args.time,
            "longitude": args.longitude,
            "question": args.question,
        },
        "ganzhi": {
            "year": lunar.getYearInGanZhi(),
            "month": lunar.getMonthInGanZhi(),
            "day": lunar.getDayInGanZhi(),
            "hour": lunar.getTimeInGanZhi(),
        },
        "ri_gan": ri_gan,
        "ri_zhi": ri_zhi,
        "month_zhi": month_zhi,
        "season_wuxing": season_wx,
        "zhong_qi": zhong_qi,
        "yue_jiang": yue_jiang,
        "yue_jiang_name": yue_jiang_name,
        "zhan_shi": zhan_shi,
        "ri_ye": "昼" if is_day else "夜",
        "tian_pan": tian_pan,
        "di_pan_jian_pan": list(DIZHI),
        "si_ke": si_ke,
        "fa_yong_method": san_chuan["method"],
        "san_chuan": {
            "chu_chuan": san_chuan["chu_chuan"],
            "chu_chuan_wuxing": wx_of(san_chuan["chu_chuan"]),
            "zhong_chuan": san_chuan["zhong_chuan"],
            "zhong_chuan_wuxing": wx_of(san_chuan["zhong_chuan"]),
            "mo_chuan": san_chuan["mo_chuan"],
            "mo_chuan_wuxing": wx_of(san_chuan["mo_chuan"]),
            "from_course": san_chuan.get("from_course"),
        },
        "shi_er_tian_jiang": shi_er,
        "nine_gates_classification": classification,
        "yong_shen": yong_hint,
        "wang_xiang": wang_xiang,
        "summary": build_summary(
            ri_gan, ri_zhi, san_chuan, yue_jiang_name, zhan_shi,
            classification, yong_hint,
        ),
        "boundary": (
            "六壬深奥, 九宗门完整 (涉害 / 昴星 / 别责 / 八专) 与 课体六十四格 "
            "需手工排课配合典籍; 本简版覆盖 贼克 / 比用 / 遥克 / 伏吟 / 反吟 五法, "
            "其余复杂课式回退到酉宫为用, 仅供参考."
        ),
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
