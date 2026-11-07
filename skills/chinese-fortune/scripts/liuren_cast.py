"""大六壬 (Da Liu Ren) 起课 — classical computation.

Pipeline:
  1. Determine 月将 (sun-sign) from 中气 boundary.
  2. 月将加时 → 天地盘 (heaven plate over fixed earth plate).
  3. 排四课 (four lessons) using 日干寄宫 and 日支.
  4. 发三传：卷一九宗门（贼克、比用、涉害、遥克、昴星、别责、八专、伏吟、反吟）逐条按主本条件分支。
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
from datetime import timedelta, timezone
from typing import Any

from liuren_xingnian import benming_xingnian
from request_time import add_request_arguments, resolve_time
from utils import (
    DIZHI,
    DIZHI_WUXING,
    TIANGAN_WUXING,
    TIANGAN_YIN_YANG,
    WUXING_GEN,
    WUXING_KE,
    __version__,
    chong_branch,
    ensure_utf8_stdio,
    error_envelope,
    hour_branch,
    jiazi_index,
    json_print,
    require_lunar,
)

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
    return hour_branch(hour)


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
    """Compatibility clock proxy: 06:00–17:59, not computed sunrise/sunset."""
    return 6 <= hour < 18


# --------------------------------------------------------------------------- #
# Step 1 — locate 中气 and 月将
# --------------------------------------------------------------------------- #

def determine_yue_jiang(lunar: Any) -> tuple[str, str, str]:
    """Return (zhong_qi 中气名, yue_jiang 地支, 月将神名).

    The caller supplies the real instant on the library's UTC+8 calendar clock,
    or an explicitly labelled floating clock. getPrevQi includes equality and
    normalizes cross-year aliases such as DONG_ZHI; never guess a missing term.
    """
    previous_qi = lunar.getPrevQi()
    if previous_qi is not None:
        zhong_qi = previous_qi.getName()
        for name, branch, general in ZHONG_QI_TO_YUE_JIANG:
            if name == zhong_qi:
                return name, branch, general
    raise ValueError("历库未能定位前一中气，不能确定月将")


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
        # 一课以日干五行判克，寄宫仅表示位置。
        {"index": 1, "name": "干上 (一课)", "lower": k1_l, "upper": k1_u,
         "lower_wuxing": TIANGAN_WUXING[ri_gan],
         "note": f"日干 {ri_gan} 寄宫 {g_ji} 之天盘 (五行以日干 {ri_gan} 论)"},
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


def lower_controls_upper(lower: str, upper: str,
                        lower_wx: str | None = None) -> bool:
    return WUXING_KE.get(lower_wx or wx_of(lower)) == wx_of(upper)


def upper_controls_lower(lower: str, upper: str,
                         lower_wx: str | None = None) -> bool:
    return WUXING_KE.get(wx_of(upper)) == (lower_wx or wx_of(lower))


# --------------------------------------------------------------------------- #
# Step 4 — 固定主法取传；分支与局限见 docs/QIMEN-LIUREN-METHODS.md。
# --------------------------------------------------------------------------- #

def detect_zei_ke(si_ke: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (zei_list, ke_list).

    zei = 下贼上 entries; ke = 上克下 entries. Each item is the 四课 dict.
    """
    zei: list[dict] = []
    ke: list[dict] = []
    for k in si_ke:
        lw = k.get("lower_wuxing")          # 一课以日干五行论, 余课用地支
        if lower_controls_upper(k["lower"], k["upper"], lw):
            zei.append(k)
        elif upper_controls_lower(k["lower"], k["upper"], lw):
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


LIUREN_SOURCE = "https://zh.wikisource.org/w/index.php?oldid=657303"
# 九宗门各取法的主本段落（卷一）及补充段落（卷五、卷七、卷九），供 rule_registry 核链。
BRANCH_SOURCES: dict[str, tuple[str, ...]] = {
    "贼克": ("liuren:c001:p0004",), "比用": ("liuren:c001:p0005",),
    "涉害": ("liuren:c001:p0006", "liuren:c005:p0032", "liuren:c005:p0035"),
    "遥克": ("liuren:c001:p0007", "liuren:c005:p0044"), "昴星": ("liuren:c001:p0007", "liuren:c005:p0062"),
    "别责": ("liuren:c001:p0008", "liuren:c005:p0067", "liuren:c009:p0060"), "八专": ("liuren:c001:p0009",),
    "伏吟": ("liuren:c001:p0010",), "反吟": ("liuren:c001:p0011",),
}


def unsupported_transmissions(method: str, reason: str,
                             candidates: list[str] | None = None) -> dict:
    """Keep the chart usable without inventing any missing transmission."""
    return {"status": "unsupported", "method": method, "reason": reason,
            "chu_chuan": None, "zhong_chuan": None, "mo_chuan": None,
            "from_course": None, "candidates": candidates or []}


MENG, ZHONG = frozenset("寅申巳亥"), frozenset("子午卯酉")
LODGED: dict[str, list[str]] = {}
for _gan, _branch in GAN_JI_GONG.items():
    LODGED.setdefault(_branch, []).append(_gan)


def she_hai_depth(upper: str, lower: str, relation: str) -> int:
    """卷五 c005:p0032：自所临地盘前行到本家，起止两位不计；地支与寄干都算。

    下贼上（zei）数克上神者，上克下（ke）数上神所克者，例「午加庚……历酉辛金二重」。
    """
    target = wx_of(upper)

    def counts(wx: str) -> bool:
        return WUXING_KE[wx] == target if relation == "zei" else WUXING_KE[target] == wx

    depth, i = 0, DIZHI.index(lower)
    while DIZHI[(i := (i + 1) % 12)] != upper:
        branch = DIZHI[i]
        depth += counts(wx_of(branch)) + sum(counts(TIANGAN_WUXING[g]) for g in LODGED.get(branch, []))
    return depth


def she_hai(pool: list[dict], relation: str, ri_gan: str, label: str) -> dict:
    """卷一 c001:p0006「涉害行来本家止，路逢多克为用取，孟深仲浅季当休，复等柔辰刚日宜」。"""
    depths = {course["upper"]: she_hai_depth(course["upper"], course["lower"], relation) for course in pool}
    deepest = max(depths.values())
    tied = [course for course in pool if depths[course["upper"]] == deepest]
    basis = f"涉害深{deepest}重"
    if len(tied) > 1:
        def rank(course: dict) -> int:
            return 0 if course["lower"] in MENG else 1 if course["lower"] in ZHONG else 2
        best = min(rank(course) for course in tied)
        tied = [course for course in tied if rank(course) == best]
        basis += "，深浅相等取孟深仲浅"
    if len(tied) > 1:
        order = (1, 2, 3, 4) if TIANGAN_YIN_YANG[ri_gan] == "阳" else (3, 4, 1, 2)
        tied.sort(key=lambda course: order.index(course["index"]))
        basis += "，复等刚日取干上、柔日取支上先见"
    return {"selected": tied[0], "method": f"涉害法 ({label}, {basis})", "depths": depths}


def _select_candidate(courses: list[dict], ri_gan: str, label: str, relation: str) -> dict | None:
    # Repeated courses naming the same upper god do not create another choice.
    unique = {course["upper"]: course for course in reversed(courses)}
    pool = sorted(unique.values(), key=lambda course: course["index"])
    if not pool:
        return None
    if len(pool) == 1:
        return {"selected": pool[0], "method": f"贼克法 ({label})"}
    same = [course for course in pool if same_polarity_as_gan(course["upper"], ri_gan)]
    if len(same) == 1:
        return {"selected": same[0], "method": f"比用法 ({label}, 唯一同日干阴阳)"}
    return she_hai(same or pool, relation, ri_gan, label)


def fa_yong_zei_ke(si_ke: list[dict], ri_gan: str,
                    tian_pan: dict[str, str]) -> dict | None:
    """四库本卷一：下贼优先，上克次之；比用未决即止于涉害。"""
    zei, ke = detect_zei_ke(si_ke)
    selected = _select_candidate(zei or ke, ri_gan, "重审课" if zei else "元首课", "zei" if zei else "ke")
    if selected is None:
        return None
    course = selected["selected"]
    chu = course["upper"]
    zhong, mo = next_two_chuan(tian_pan, chu)
    return {"status": "supported", "method": selected["method"],
            "chu_chuan": chu, "zhong_chuan": zhong, "mo_chuan": mo,
            "from_course": course["index"]}


def fa_yong_yao_ke(si_ke: list[dict], ri_gan: str,
                    tian_pan: dict[str, str]) -> dict | None:
    """无克贼且非八专：神克日为蒿矢，日克神为弹射，二者勿颠倒。"""
    gan_wx = TIANGAN_WUXING[ri_gan]
    uppers = list(dict.fromkeys(course["upper"] for course in si_ke))
    inward = [u for u in uppers if WUXING_KE[wx_of(u)] == gan_wx]
    outward = [u for u in uppers if WUXING_KE[gan_wx] == wx_of(u)]
    pool = inward or outward
    if not pool:
        return None
    method = "遥克法 (蒿矢课, 神克日)" if inward else "遥克法 (弹射课, 日克神)"
    same = [u for u in pool if same_polarity_as_gan(u, ri_gan)]
    if len(pool) == 1 or len(same) == 1:
        chu = pool[0] if len(pool) == 1 else same[0]
    else:
        # 卷五 c005:p0044「遥克中克多论比，涉害论深」。计克方向比照上克下（蒿矢）、下贼上（弹射），属推定。
        first = {course["upper"]: course for course in reversed(si_ke)}
        picked = she_hai([first[u] for u in (same or pool)], "ke" if inward else "zei", ri_gan,
                         "遥克俱比俱不比")
        chu = picked["selected"]["upper"]
        method += "; " + picked["method"] + "; 计克方向比照上克下/下贼上为推定"
    zhong, mo = next_two_chuan(tian_pan, chu)
    return {"status": "supported", "method": method,
            "chu_chuan": chu, "zhong_chuan": zhong, "mo_chuan": mo,
            "from_course": None}


# 三刑 + 自刑 —— 伏吟课取传全靠它。
# 寅刑巳, 巳刑申, 申刑寅 (无恩之刑); 丑刑戌, 戌刑未, 未刑丑 (恃势之刑);
# 子刑卯, 卯刑子 (无礼之刑); 辰午酉亥 自刑。
XING_MAP: dict[str, str] = {
    "寅": "巳", "巳": "申", "申": "寅",
    "丑": "戌", "戌": "未", "未": "丑",
    "子": "卯", "卯": "子",
    "辰": "辰", "午": "午", "酉": "酉", "亥": "亥",
}

def chong_zhi(zhi: str) -> str:
    """Compatibility alias for the shared six-oppositions table."""
    return chong_branch(zhi)


def fa_yong_fu_yin(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str,
                   yue_jiang: str, zhan_shi: str) -> dict | None:
    """卷一伏吟有克仍用克；自刑换日辰，卷七杜传例补明子卯不再循环。"""
    if yue_jiang != zhan_shi:
        return None
    direct = fa_yong_zei_ke(build_si_ke(tian_pan, ri_gan, ri_zhi), ri_gan, tian_pan)
    if direct and direct.get("status") == "unsupported":
        return direct
    gan_shang, zhi_shang = tian_pan[GAN_JI_GONG[ri_gan]], tian_pan[ri_zhi]
    if direct:
        chu = direct["chu_chuan"]
        from_course = direct["from_course"]
        used_gan = from_course in (1, 2)
        basis = "有克先取克"
    else:
        used_gan = TIANGAN_YIN_YANG[ri_gan] == "阳"
        chu = gan_shang if used_gan else zhi_shang
        from_course = 1 if used_gan else 3
        basis = "无克阳日干上、阴日支上"
    if XING_MAP[chu] == chu:
        zhong = zhi_shang if used_gan else gan_shang
        basis += "; 初自刑则交换日辰"
    else:
        zhong = XING_MAP[chu]
    mo = XING_MAP[zhong]
    if mo == zhong or mo == chu:
        mo = chong_branch(zhong)
        basis += "; 次自刑或刑回初则取冲"
    return {"status": "supported", "method": f"伏吟法 ({basis}, 中末取刑冲)",
            "chu_chuan": chu, "zhong_chuan": zhong, "mo_chuan": mo,
            "from_course": from_course}


def fa_yong_fan_yin(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str,
                    yue_jiang: str, zhan_shi: str) -> dict | None:
    """反吟有克用克（允许初末同）；无克井栏按卷一六日法。"""
    if chong_branch(yue_jiang) != zhan_shi:
        return None
    direct = fa_yong_zei_ke(build_si_ke(tian_pan, ri_gan, ri_zhi), ri_gan, tian_pan)
    if direct:
        return {**direct, "method": "反吟 / " + direct["method"]}
    if ri_gan not in "丁己辛" or ri_zhi not in "丑未":
        return unsupported_transmissions("反吟无克 (未支持)", "不属于所选主法井栏六日。")
    return {"status": "supported", "method": "反吟法 (无克井栏: 丑日亥、未日巳为初)",
            "chu_chuan": "亥" if ri_zhi == "丑" else "巳",
            "zhong_chuan": tian_pan[ri_zhi],
            "mo_chuan": tian_pan[GAN_JI_GONG[ri_gan]], "from_course": None}


def fa_yong_ba_zhuan(tian_pan: dict[str, str], ri_gan: str,
                     ri_zhi: str) -> dict | None:
    """两课无克八专：阳取日阳顺三，阴取辰阴（第四课上神）逆三。"""
    if GAN_JI_GONG[ri_gan] != ri_zhi:
        return None
    lessons = build_si_ke(tian_pan, ri_gan, ri_zhi)
    zei, ke = detect_zei_ke(lessons)
    if zei or ke:
        return None
    yang = TIANGAN_YIN_YANG[ri_gan] == "阳"
    start = lessons[0]["upper"] if yang else lessons[3]["upper"]
    chu = DIZHI[(DIZHI.index(start) + (2 if yang else -2)) % 12]
    gan_shang = lessons[0]["upper"]
    return {"status": "supported",
            "method": "八专法 (两课无克, 论克不论遥; 阳日阳顺三、阴辰阴逆三)",
            "chu_chuan": chu, "zhong_chuan": gan_shang, "mo_chuan": gan_shang,
            "from_course": None}


GAN_HE: dict[str, str] = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛", "辛": "丙",
                          "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}
# 三合局内的下一位：申子辰、亥卯未、寅午戌、巳酉丑，循环。
SAN_HE_NEXT: dict[str, str] = {"申": "子", "子": "辰", "辰": "申", "亥": "卯", "卯": "未", "未": "亥",
                               "寅": "午", "午": "戌", "戌": "寅", "巳": "酉", "酉": "丑", "丑": "巳"}


def fa_yong_mao_xing(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str) -> dict:
    """卷一 c001:p0007「无遥无克昴星穷，阳仰阴俯酉位中，刚日先辰而后日，柔日先日而后辰」。"""
    gan_shang, zhi_shang = tian_pan[GAN_JI_GONG[ri_gan]], tian_pan[ri_zhi]
    if TIANGAN_YIN_YANG[ri_gan] == "阳":
        return {"status": "supported", "method": "昴星法 (刚日仰视地盘酉上神为初, 先辰后日)",
                "chu_chuan": tian_pan["酉"], "zhong_chuan": zhi_shang, "mo_chuan": gan_shang, "from_course": None}
    below = next(branch for branch, upper in tian_pan.items() if upper == "酉")
    return {"status": "supported", "method": "昴星法 (柔日俯视天盘酉所临地盘为初, 先日后辰)",
            "chu_chuan": below, "zhong_chuan": gan_shang, "mo_chuan": zhi_shang, "from_course": None}


def fa_yong_bie_ze(tian_pan: dict[str, str], ri_gan: str, ri_zhi: str) -> dict:
    """卷一 c001:p0008「刚日干合上头神，柔日支前三合取……阴阳中末干中寄」。

    柔日取三合前一辰本身：卷五 c005:p0066、p0067 都这样取，c005:p0067 对卷一「皆以天上作初传」
    存疑；卷九 c009:p0060 辛丑日别责「巳玄加申」也以巳本辰为初。
    """
    gan_shang = tian_pan[GAN_JI_GONG[ri_gan]]
    if TIANGAN_YIN_YANG[ri_gan] == "阳":
        chu = tian_pan[GAN_JI_GONG[GAN_HE[ri_gan]]]
        method = "别责法 (刚日取干合寄宫上神为初, 中末并干上)"
    else:
        chu = SAN_HE_NEXT[ri_zhi]
        method = "别责法 (柔日取支三合前一辰为初, 中末并干上; 卷五存疑天上神之说)"
    return {"status": "supported", "method": method,
            "chu_chuan": chu, "zhong_chuan": gan_shang, "mo_chuan": gan_shang, "from_course": None}


def fa_yong(si_ke: list[dict], ri_gan: str, ri_zhi: str,
            tian_pan: dict[str, str], yue_jiang: str, zhan_shi: str) -> dict:
    """固定主法条件分支；伏反吟内先审克，八专不跳过有克也不审遥。"""
    for method in (fa_yong_fu_yin, fa_yong_fan_yin):
        result = method(tian_pan, ri_gan, ri_zhi, yue_jiang, zhan_shi)
        if result is not None:
            return result
    direct = fa_yong_zei_ke(si_ke, ri_gan, tian_pan)
    if direct is not None:
        return direct
    ba_zhuan = fa_yong_ba_zhuan(tian_pan, ri_gan, ri_zhi)
    if ba_zhuan is not None:
        return ba_zhuan
    remote = fa_yong_yao_ke(si_ke, ri_gan, tian_pan)
    if remote is not None:
        return remote
    # 不备看课本身是否重复（上下皆同），不是只看上神。
    count = len({(course["lower"], course["upper"]) for course in si_ke})
    if count == 4:
        return fa_yong_mao_xing(tian_pan, ri_gan, ri_zhi)
    if count == 3:
        return fa_yong_bie_ze(tian_pan, ri_gan, ri_zhi)
    return unsupported_transmissions("无克无遥 (未支持)",
        f"{count}课且无贼克遥克，又不属八专；主本没有对应取法。")


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

def yong_shen_hint(question: str | None) -> str | None:
    """Question-specific interpretation needs sourced rules, not keyword verdicts."""
    if not question:
        return None
    return "先明确所问事项与取象条款；本工具未登记问事解释规则，不从关键词判结果。"


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

# Most specific first: 「涉害法 (重审课, …)」 and 「比用法 (元首课, …)」 name the 课 they came from, so
# 涉害 and 比用 must win over 元首/重审 (R9-LR-SUMMARY-01).
_COURSE_TAGS: list[tuple[str, str]] = [
    ("伏吟", "九宗门: 伏吟法"),
    ("反吟", "九宗门: 反吟法"),
    ("涉害", "九宗门: 涉害法 (克贼不止一个、俱比或俱不比，以涉害深浅取用)"),
    ("比用", "九宗门: 比用法 (克贼不止一个，取与日干同阴阳者)"),
    ("遥克", "九宗门: 遥克法"),
    ("昴星", "九宗门: 昴星"),
    ("别责", "九宗门: 别责"),
    ("八专", "九宗门: 八专"),
    ("元首", "九宗门: 贼克法 — 元首课 (一克为用)"),
    ("重审", "九宗门: 贼克法 — 重审课 (一贼为用)"),
    ("贼克", "九宗门: 贼克法"),
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
                  classification: str, yong_hint: str | None) -> str:
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
    if san_chuan.get("status") == "unsupported":
        parts[1] = "三传未完成: " + san_chuan["reason"]
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version input ganzhi ri_gan ri_zhi month_zhi season_wuxing
  zhong_qi yue_jiang yue_jiang_name zhan_shi ri_ye tian_pan
  di_pan_jian_pan si_ke fa_yong_method san_chuan shi_er_tian_jiang benming_xingnian
  nine_gates_classification yong_shen wang_xiang summary boundary

On error: {"error": ..., "message": ...} and exit 1."""


def _lichun_year(year_ganzhi: str, civil_year: int) -> int:
    """The Gregorian number of the 立春 year whose ganzhi this is (January before 立春 belongs to the last one)."""
    return civil_year if jiazi_index(year_ganzhi[0], year_ganzhi[1]) == (civil_year - 4) % 60 else civil_year - 1


def _benming(birth_date: str | None, gender: str | None, term_lunar: object, cast_civil_year: int,
             tian_pan: dict, shi_er: dict) -> dict:
    if not birth_date or not gender:
        raise ValueError('本命行年要同时给 --birth-date 和 --gender')
    from datetime import date as _date

    from lunar_python import Solar  # type: ignore
    try:
        born = _date.fromisoformat(birth_date)
    except ValueError:
        raise ValueError(f'出生日期要写成 YYYY-MM-DD：{birth_date!r}') from None
    birth_gz = Solar.fromYmdHms(born.year, born.month, born.day, 12, 0, 0).getLunar().getYearInGanZhiExact()
    cast_gz = term_lunar.getYearInGanZhiExact()  # type: ignore[attr-defined]
    birth_year, cast_year = _lichun_year(birth_gz, born.year), _lichun_year(cast_gz, cast_civil_year)
    if cast_year < birth_year:
        raise ValueError('占问时间早于出生')
    return benming_xingnian(birth_gz, birth_year, cast_gz, cast_year, gender, tian_pan, shi_er)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="大六壬起课 (月将加时 → 四课 → 三传 → 十二天将)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_request_arguments(p)
    p.add_argument("--date", default=None, help="占问日期 YYYY-MM-DD")
    p.add_argument("--time", default=None, help="占问时辰 HH:MM")
    p.add_argument("--longitude", type=float, default=None,
                   help="经度 (可选, 仅记录, 不参与时辰换算; 真太阳时需另行调整)")
    p.add_argument("--birth-date", default=None, metavar="YYYY-MM-DD",
                   help="占者出生日期（公历）：给了就加本命、行年在课里的位置")
    p.add_argument("--gender", choices=("male", "female"), default=None, help="行年男顺女逆，需与 --birth-date 同给")
    p.add_argument("--question", type=str, default=None,
                   help="所问之事 (用于 用神 提示)")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        dt, time_context = resolve_time(args, date_value=args.date, time_value=args.time)
    except ValueError as exc:
        json_print(error_envelope('daliuren', "invalid_datetime", str(exc)))
        return 1

    require_lunar()
    from lunar_python import Solar  # type: ignore

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()
    aware = dt.tzinfo is not None and dt.utcoffset() is not None
    calendar_clock = dt.astimezone(timezone(timedelta(hours=8))) if aware else dt
    term_lunar = Solar.fromYmdHms(
        calendar_clock.year, calendar_clock.month, calendar_clock.day,
        calendar_clock.hour, calendar_clock.minute, calendar_clock.second,
    ).getLunar()

    ri_gan = lunar.getDayGan()
    ri_zhi = lunar.getDayZhi()
    month_zhi = term_lunar.getMonthZhiExact()

    try:
        zhong_qi, yue_jiang, yue_jiang_name = determine_yue_jiang(term_lunar)
    except ValueError as exc:
        json_print(error_envelope('daliuren', 'calendar_unavailable', str(exc)))
        return 1
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
    } if san_chuan["status"] == "supported" else None

    personal = None
    if args.birth_date or args.gender:
        try:
            personal = _benming(args.birth_date, args.gender, term_lunar, calendar_clock.year, tian_pan, shi_er)
        except ValueError as exc:
            json_print(error_envelope('daliuren', 'invalid_input', str(exc)))
            return 1

    classification = classify_course(san_chuan["method"])
    yong_hint = yong_shen_hint(args.question)

    out = {
        "ok": True,
        "tool": "daliuren",
        "completion_status": "complete" if san_chuan["status"] == "supported" else "partial",
        "version": __version__,
        "time_context": time_context,
        "calendar_basis": {
            "year_month_yue_jiang": "real_instant_at_UTC+08:00" if aware else "floating_calendar_assumption",
            "day_hour": "local_clock",
            "day_boundary": "midnight",
            "term_calendar_zone": "UTC+08:00",
            "comparison_clock": calendar_clock.isoformat(),
            "previous_zhong_qi": {
                "name": zhong_qi,
                "calendar_datetime": term_lunar.getPrevQi().getSolar().toYmdHms(),
            },
            "limitation": None if aware else "未给目标时区，交节只能按输入钟面比较；无法保证交中气两侧的唯一月将，需补时区。",
        },
        "method_profile": {
            "id": "liuren-siku-v1", "source": LIUREN_SOURCE,
            "scope": "卷一九宗门；卷五补涉害计克方向与别责柔日取法，卷七课经补明伏吟杜传和同书异说",
            "verification": "transcription_checked_not_facsimile",
            "unsupported": ["反吟无克而非井栏六日", "不备而非三课的无克无遥"],
            "inferred": ["遥克俱比俱不比转涉害时的计克方向（比照上克下/下贼上）"],
            "remaining": "十二天将、昼夜贵人与课体解释尚未逐项校准；昼夜仅采用当地 06:00–17:59 钟面代理，不是日出日落；不作已完整核验声明",
        },
        "input": {
            "date": dt.date().isoformat(),
            "time": dt.strftime("%H:%M"),
            "longitude": args.longitude,
            "question": args.question,
        },
        "ganzhi": {
            "year": term_lunar.getYearInGanZhiExact(),
            "month": term_lunar.getMonthInGanZhiExact(),
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
            "status": san_chuan["status"],
            "reason": san_chuan.get("reason"),
            "candidates": san_chuan.get("candidates", []),
            # 取法从前算出来却没进输出 —— 而「这三传是哪一门排出来的」正是六壬解读
            # 的核心 (贼克/比用/遥克/八专/伏吟/反吟 各有断法), 读者无从分辨。
            "method": san_chuan.get("method", "?"),
            "chu_chuan": san_chuan["chu_chuan"],
            "chu_chuan_wuxing": wx_of(san_chuan["chu_chuan"]) if san_chuan["chu_chuan"] else None,
            "zhong_chuan": san_chuan["zhong_chuan"],
            "zhong_chuan_wuxing": wx_of(san_chuan["zhong_chuan"]) if san_chuan["zhong_chuan"] else None,
            "mo_chuan": san_chuan["mo_chuan"],
            "mo_chuan_wuxing": wx_of(san_chuan["mo_chuan"]) if san_chuan["mo_chuan"] else None,
            "from_course": san_chuan.get("from_course"),
        },
        "shi_er_tian_jiang": shi_er,
        **({"benming_xingnian": personal} if personal else {}),
        "nine_gates_classification": classification,
        "yong_shen": yong_hint,
        "wang_xiang": wang_xiang,
        "summary": build_summary(
            ri_gan, ri_zhi, san_chuan, yue_jiang_name, zhan_shi,
            classification, yong_hint,
        ),
        "boundary": "本版仅按所列主法完成支持分支；未支持的取传返回空值，不能补凑三传。",
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
