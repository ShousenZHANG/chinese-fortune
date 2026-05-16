"""奇门遁甲 时家盘 (Hourly Qi Men Dun Jia chart).

Implements 转盘 (rotating-plate) 时家奇门 — the most widely used
flavor of 奇门遁甲. Output covers:

  * 局数 (1..9) determination via 节气 + 三元 (上/中/下)
  * 地盘 三奇六仪 (固定 9 宫)
  * 天盘 (rotated by 值符 to align with 时干 落宫)
  * 八门 (rotated by 值使 to align with 旬首 落宫)
  * 九星 (天蓬…天禽, 天禽 寄坤二宫)
  * 八神 (值符 螣蛇 太阴 六合 白虎 玄武 九地 九天, 阳顺阴逆)
  * 格局 detection (青龙返首, 飞鸟跌穴, 三诈, 天/地/人遁,
                    击刑, 入墓, 五不遇时, 等)

References:
  * 《奇门遁甲秘笈大全》    (明)
  * 《奇门遁甲统宗》        (明·程道生)
  * references/06-qimen.md  (local primer, 408 lines)

CLI:
    python qimen_cast.py --date 2026-05-16 --time 14:30 [--longitude 120]
    python qimen_cast.py --ju-type yang --ju-number 7  # 手动定局

All algorithms are public-domain — expression here is original.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from utils import (
    DIZHI,
    TIANGAN,
    TIANGAN_WUXING,
    DIZHI_WUXING,
    WUXING_KE,
    json_print,
    longitude_correction,
    require_lunar,
    warn,
)


# --------------------------------------------------------------------------- #
# 九宫 / 后天八卦 constants
# --------------------------------------------------------------------------- #
# Palace indexes 1..9 follow 洛书 numbering — also called 后天九宫.
#
#   ┌─────┬─────┬─────┐
#   │  4  │  9  │  2  │     (上 = 南)
#   │ 巽  │ 离  │ 坤  │
#   ├─────┼─────┼─────┤
#   │  3  │  5  │  7  │
#   │ 震  │ 中  │ 兑  │
#   ├─────┼─────┼─────┤
#   │  8  │  1  │  6  │
#   │ 艮  │ 坎  │ 乾  │     (下 = 北)
#   └─────┴─────┴─────┘

PALACE_INFO: dict[int, dict[str, str]] = {
    1: {"palace": "坎", "direction": "北",   "wuxing": "水"},
    2: {"palace": "坤", "direction": "西南", "wuxing": "土"},
    3: {"palace": "震", "direction": "东",   "wuxing": "木"},
    4: {"palace": "巽", "direction": "东南", "wuxing": "木"},
    5: {"palace": "中", "direction": "中央", "wuxing": "土"},
    6: {"palace": "乾", "direction": "西北", "wuxing": "金"},
    7: {"palace": "兑", "direction": "西",   "wuxing": "金"},
    8: {"palace": "艮", "direction": "东北", "wuxing": "土"},
    9: {"palace": "离", "direction": "南",   "wuxing": "火"},
}

# 阳遁 顺行 sequence of palace indexes (洛书阳遁路径):
# 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
YANG_PALACE_SEQ: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
# 阴遁 逆行 sequence:
# 9 → 8 → 7 → 6 → 5 → 4 → 3 → 2 → 1
YIN_PALACE_SEQ: list[int] = [9, 8, 7, 6, 5, 4, 3, 2, 1]

# Default 八门 mapping to base palace (阳遁一局 reference position).
# 中宫无门, 寄于坤二宫 (or 艮八, 取流派而定; 本程序取传统的寄坤).
MEN_HOME_PALACE: dict[str, int] = {
    "休门": 1, "死门": 2, "伤门": 3, "杜门": 4,
    "开门": 6, "惊门": 7, "生门": 8, "景门": 9,
}
# 八门 顺序 by 后天九宫 (1 8 3 4 9 2 7 6) — 中5 寄2
MEN_ORDER_BY_PALACE: list[tuple[int, str]] = [
    (1, "休门"), (8, "生门"), (3, "伤门"), (4, "杜门"),
    (9, "景门"), (2, "死门"), (7, "惊门"), (6, "开门"),
]
# 九星 顺序 by 后天九宫 (1 8 3 4 9 2 7 6 5).  天禽 居中 5, 寄于坤二宫.
STAR_ORDER_BY_PALACE: list[tuple[int, str]] = [
    (1, "天蓬"), (8, "天任"), (3, "天冲"), (4, "天辅"),
    (9, "天英"), (2, "天芮"), (7, "天柱"), (6, "天心"),
    (5, "天禽"),
]
STAR_HOME_PALACE: dict[str, int] = {name: pal for pal, name in STAR_ORDER_BY_PALACE}

# 八神 sequence — 阳顺
EIGHT_SHEN_ORDER: list[str] = [
    "值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天",
]

# 三奇 六仪
SAN_QI: list[str] = ["乙", "丙", "丁"]
LIU_YI: list[str] = ["戊", "己", "庚", "辛", "壬", "癸"]
# 三奇六仪 完整顺序 (六仪 + 三奇, 三奇逆序排为 丁 丙 乙).
# 阳遁顺布: 戊→己→庚→辛→壬→癸→丁→丙→乙
# 阴遁逆布: 同 sequence 但走逆向 palace path
YIQI_ORDER: list[str] = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]


# --------------------------------------------------------------------------- #
# 节气 → 三元局数 table (transcribed from 《奇门遁甲秘笈大全》)
# --------------------------------------------------------------------------- #

YANG_JIE_QI: dict[str, tuple[int, int, int]] = {
    # (上元局, 中元局, 下元局)
    "冬至": (1, 7, 4),
    "小寒": (2, 8, 5),
    "大寒": (3, 9, 6),
    "立春": (8, 5, 2),
    "雨水": (9, 6, 3),
    "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6),
    "清明": (4, 1, 7),
    "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7),
    "小满": (5, 2, 8),
    "芒种": (6, 3, 9),
}

YIN_JIE_QI: dict[str, tuple[int, int, int]] = {
    "夏至": (9, 3, 6),
    "小暑": (8, 2, 5),
    "大暑": (7, 1, 4),
    "立秋": (2, 5, 8),
    "处暑": (1, 4, 7),
    "白露": (9, 3, 6),
    "秋分": (7, 1, 4),
    "寒露": (6, 9, 3),
    "霜降": (5, 8, 2),
    "立冬": (6, 9, 3),
    "小雪": (5, 8, 2),
    "大雪": (4, 7, 1),
}


def determine_ju(jieqi_name: str, days_since_jieqi: int) -> tuple[str, str, int]:
    """Return (ju_type, san_yuan, ju_number) for given 节气 + 距节气天数.

    days_since_jieqi: 0 = 节气当日 ; 1..14 = 之后. 上元 0-4, 中元 5-9, 下元 10-14.
    """
    if days_since_jieqi < 5:
        yuan_idx, yuan_name = 0, "上元"
    elif days_since_jieqi < 10:
        yuan_idx, yuan_name = 1, "中元"
    else:
        yuan_idx, yuan_name = 2, "下元"

    if jieqi_name in YANG_JIE_QI:
        return "阳遁", yuan_name, YANG_JIE_QI[jieqi_name][yuan_idx]
    if jieqi_name in YIN_JIE_QI:
        return "阴遁", yuan_name, YIN_JIE_QI[jieqi_name][yuan_idx]
    raise ValueError(f"unknown 节气: {jieqi_name}")


# --------------------------------------------------------------------------- #
# 地盘 三奇六仪 placement
# --------------------------------------------------------------------------- #

def earth_plate(ju_type: str, ju_number: int) -> dict[int, str]:
    """Place 三奇六仪 across 9 palaces.

    阳遁 N 局: 戊起 N 宫, 顺布 (按 1..9 palace path) 六仪+三奇.
    阴遁 N 局: 戊起 N 宫, 逆布 (按 9..1 palace path) 六仪+三奇.

    Returns dict mapping palace_index (1..9) -> 干名.
    """
    if not (1 <= ju_number <= 9):
        raise ValueError(f"ju_number out of range: {ju_number}")

    # Build path of 9 palaces starting at ju_number, traversing in 顺/逆 direction.
    if ju_type == "阳遁":
        full_seq = YANG_PALACE_SEQ
    elif ju_type == "阴遁":
        full_seq = YIN_PALACE_SEQ
    else:
        raise ValueError(f"unknown ju_type: {ju_type}")

    start_idx = full_seq.index(ju_number)
    path = [full_seq[(start_idx + k) % 9] for k in range(9)]

    return {palace: YIQI_ORDER[k] for k, palace in enumerate(path)}


# --------------------------------------------------------------------------- #
# 旬首 — given 日干支 (or 时干支), return which of the 6 甲 it belongs to,
# and the 六仪 (戊/己/庚/辛/壬/癸) for that 旬.
# --------------------------------------------------------------------------- #

# 60 甲子 indexed 0..59 with stem cycle (10) + branch cycle (12).
# 旬首 = 甲X日, every 10 days:
#   0: 甲子, 10: 甲戌, 20: 甲申, 30: 甲午, 40: 甲辰, 50: 甲寅
XUN_HEADS: list[tuple[str, str]] = [
    ("甲子", "戊"),   # 戊 represents 甲子旬
    ("甲戌", "己"),
    ("甲申", "庚"),
    ("甲午", "辛"),
    ("甲辰", "壬"),
    ("甲寅", "癸"),
]


def jiazi_index_of(stem: str, branch: str) -> int:
    s = TIANGAN.index(stem)
    b = DIZHI.index(branch)
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise ValueError(f"invalid 干支: {stem}{branch}")


def xun_head(stem: str, branch: str) -> tuple[str, str]:
    """Return (旬首名 e.g. '甲子', 对应六仪 e.g. '戊') for 干支."""
    idx = jiazi_index_of(stem, branch)
    head_idx = idx - (idx % 10)  # 0,10,20,30,40,50
    return XUN_HEADS[head_idx // 10]


# --------------------------------------------------------------------------- #
# Heaven plate — rotate earth plate by 值符
# --------------------------------------------------------------------------- #

def heaven_plate(
    earth: dict[int, str],
    hour_stem: str,
    hour_branch: str,
    ju_type: str,
) -> tuple[dict[int, str], int, int]:
    """Compute 天盘.

    值符宫 = 旬首之六仪 落于地盘的宫位.
    时干宫 = 时干 (或其代位六仪) 落于地盘的宫位.
    旋转: 把 地盘 整体 平移, 使 值符宫(of earth) 的内容 飞到 时干宫.

    Returns (heaven, zhi_fu_palace, shi_gan_palace).
    """
    head_name, head_yi = xun_head(hour_stem, hour_branch)

    # 值符宫: 该旬六仪所在地盘宫位
    zhi_fu_palace = next(p for p, y in earth.items() if y == head_yi)

    # 时干 在地盘的位置: if 时干 是六仪, 直接查 earth; 若是三奇 (乙丙丁), 同样查 earth.
    # 时干本身的位置不变, 只是 "时干宫" 就是当前 hour_stem 在地盘的宫.
    shi_gan_palace = next(p for p, y in earth.items() if y == hour_stem)

    # If 时干 = 该旬旬首所代之甲 (即 时干 = 甲), 则 时干 隐在 六仪 之下,
    # 值符宫 与 时干宫 重合 (即 用神不动, 称为 "伏吟" 之兆).
    # 这种情况下面会再单独处理.

    # 阳遁 顺转, 阴遁 逆转 — 但 旋转方向 实际上 与遁种无关,
    # 转盘式以 "值符宫的元素 飞到 时干宫" 为主, 走的是 1..9 顺时针 palace path.
    # 这里我们 直接求 offset, 让 earth[zhi_fu] -> heaven[shi_gan].
    full_seq = YANG_PALACE_SEQ if ju_type == "阳遁" else YIN_PALACE_SEQ

    # Find offset along path
    from_idx = full_seq.index(zhi_fu_palace)
    to_idx = full_seq.index(shi_gan_palace)
    shift = (to_idx - from_idx) % 9

    heaven: dict[int, str] = {}
    for k, palace in enumerate(full_seq):
        # The element at earth[full_seq[k]] moves to heaven[full_seq[(k+shift)%9]]
        target = full_seq[(k + shift) % 9]
        heaven[target] = earth[palace]

    return heaven, zhi_fu_palace, shi_gan_palace


# --------------------------------------------------------------------------- #
# 八宫环 (8-palace ring excluding 中5) — used for rotating 八门 / 九星.
# Order: 1→8→3→4→9→2→7→6 (洛书 飞行顺序 - 顺九宫 path skipping 5).
# 阳遁 顺布 / 阴遁 逆布 — both use the same ring but traverse in
# opposite direction.
# --------------------------------------------------------------------------- #

EIGHT_RING_YANG: list[int] = [1, 8, 3, 4, 9, 2, 7, 6]
EIGHT_RING_YIN: list[int] = [1, 6, 7, 2, 9, 4, 3, 8]


def _resolve_ring_palace(palace: int) -> int:
    """If palace == 5, fall back to 2 (寄坤). Otherwise return as-is."""
    return 2 if palace == 5 else palace


# --------------------------------------------------------------------------- #
# 九星 rotation — follows 值符
# --------------------------------------------------------------------------- #

def star_plate(zhi_fu_palace: int, shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """Rotate 九星 so that 值符星 (the star native to zhi_fu_palace) 飞到 时干宫.

    Stars at home positions (1=天蓬, 8=天任, 3=天冲, 4=天辅, 9=天英, 2=天芮,
    7=天柱, 6=天心, 5=天禽 寄 2). Rotates along 8-palace ring (中5 stays
    blank but 天禽 is shown as 寄于 the same palace as 天芮).
    """
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN

    # Home map within ring (天禽 寄于 2 — but 天芮 also lives in 2;
    # in 转盘式 they share. We track 天禽 separately and overlay).
    home_ring: dict[int, str] = {
        1: "天蓬", 8: "天任", 3: "天冲", 4: "天辅",
        9: "天英", 2: "天芮", 7: "天柱", 6: "天心",
    }

    from_pal = _resolve_ring_palace(zhi_fu_palace)
    to_pal = _resolve_ring_palace(shi_gan_palace)
    from_idx = ring.index(from_pal)
    to_idx = ring.index(to_pal)
    shift = (to_idx - from_idx) % 8

    star_result: dict[int, str] = {}
    for k, palace in enumerate(ring):
        target = ring[(k + shift) % 8]
        star_result[target] = home_ring[palace]

    # 天禽 always sits with 天芮 in 转盘式 — co-locate them.
    star_result[5] = "天禽"
    return star_result


# --------------------------------------------------------------------------- #
# 八门 rotation — follows 值使 (= 旬首六仪 所对应 之地盘宫位的本门).
# --------------------------------------------------------------------------- #

def men_plate(zhi_fu_palace: int, shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """Rotate 八门. 值使门 = zhi_fu_palace's 本门; 该门飞到 时干宫.

    八门 home positions: 1坎-休门 2坤-死门 3震-伤门 4巽-杜门
                         5中-无门 6乾-开门 7兑-惊门 8艮-生门 9离-景门
    """
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN
    home_ring: dict[int, str] = {
        1: "休门", 8: "生门", 3: "伤门", 4: "杜门",
        9: "景门", 2: "死门", 7: "惊门", 6: "开门",
    }

    from_pal = _resolve_ring_palace(zhi_fu_palace)
    to_pal = _resolve_ring_palace(shi_gan_palace)
    from_idx = ring.index(from_pal)
    to_idx = ring.index(to_pal)
    shift = (to_idx - from_idx) % 8

    men_result: dict[int, str] = {}
    for k, palace in enumerate(ring):
        target = ring[(k + shift) % 8]
        men_result[target] = home_ring[palace]
    # 中5 stays without 八门.
    return men_result


# --------------------------------------------------------------------------- #
# 八神 — starts at 值符宫 (which gets 值符), then 阳顺/阴逆 along palace path.
# --------------------------------------------------------------------------- #

def shen_plate(shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """八神: 值符 起于 时干宫 (即 值符 当前所在宫位),
    阳顺/阴逆 沿 8-palace ring 排布. 中宫 5 无神.
    """
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN
    start = _resolve_ring_palace(shi_gan_palace)
    start_idx = ring.index(start)

    shen_result: dict[int, str] = {}
    for k, name in enumerate(EIGHT_SHEN_ORDER):
        palace = ring[(start_idx + k) % 8]
        shen_result[palace] = name
    return shen_result


# --------------------------------------------------------------------------- #
# 格局 detection
# --------------------------------------------------------------------------- #

# 三吉门
JI_MEN: set[str] = {"开门", "休门", "生门"}
# 凶门
XIONG_MEN: set[str] = {"伤门", "死门", "惊门"}

# 三刑
SAN_XING_PAIRS: list[tuple[str, str]] = [
    ("寅", "巳"), ("巳", "申"), ("申", "寅"),  # 寅巳申 三刑
    ("丑", "戌"), ("戌", "未"), ("未", "丑"),  # 丑戌未 三刑
    ("子", "卯"),                              # 子卯相刑
    ("辰", "辰"), ("午", "午"), ("酉", "酉"), ("亥", "亥"),  # 自刑
]
SAN_XING_LOOKUP: dict[str, set[str]] = {}
for a, b in SAN_XING_PAIRS:
    SAN_XING_LOOKUP.setdefault(a, set()).add(b)
    SAN_XING_LOOKUP.setdefault(b, set()).add(a)

# 天干 五行 之 墓库
MU_KU: dict[str, str] = {
    "甲": "未", "乙": "未",  # 木墓于未
    "丙": "戌", "丁": "戌",  # 火墓于戌
    "戊": "戌", "己": "戌",  # 阳土寄火墓
    "庚": "丑", "辛": "丑",  # 金墓于丑
    "壬": "辰", "癸": "辰",  # 水墓于辰
}

# 地支 -> palace index (after 寄宫 处理)
DIZHI_TO_PALACE: dict[str, int] = {
    "子": 1, "丑": 8, "寅": 8, "卯": 3, "辰": 4, "巳": 4,
    "午": 9, "未": 2, "申": 2, "酉": 7, "戌": 6, "亥": 6,
}


def detect_patterns(
    earth: dict[int, str],
    heaven: dict[int, str],
    men: dict[int, str],
    shen: dict[int, str],
    star: dict[int, str],
    hour_stem: str,
    hour_branch: str,
    day_stem: str,
    zhi_fu_palace: int,
    shi_gan_palace: int,
) -> list[dict[str, str]]:
    """Detect 8+ common 格局, returning list of {name, evidence}."""
    patterns: list[dict[str, str]] = []

    # Helper: which palaces hold 三奇?
    qi_palaces = {q: next((p for p, y in heaven.items() if y == q), None)
                  for q in SAN_QI}

    # 1. 三诈格 (三奇 三个 都 落在 三吉门).
    qi_with_ji_men = []
    for q in SAN_QI:
        p = qi_palaces.get(q)
        if p is not None and men.get(p) in JI_MEN:
            qi_with_ji_men.append((q, p, men.get(p)))
    if len(qi_with_ji_men) >= 3:
        ev = "; ".join(f"{q} 在 {p}宫 + {m}" for q, p, m in qi_with_ji_men)
        patterns.append({"name": "三诈格", "evidence": ev})

    # 2. 天遁: 丙奇 + 生门 + 天上九天 (传统: 丙加生临九天).
    p_bing = qi_palaces.get("丙")
    if p_bing is not None and men.get(p_bing) == "生门" and shen.get(p_bing) == "九天":
        patterns.append({
            "name": "天遁",
            "evidence": f"丙奇 在 {p_bing}宫 + 生门 + 九天 — 主隐密获利",
        })

    # 3. 地遁: 乙奇 + 开门 + 太阴.
    p_yi = qi_palaces.get("乙")
    if p_yi is not None and men.get(p_yi) == "开门" and shen.get(p_yi) == "太阴":
        patterns.append({
            "name": "地遁",
            "evidence": f"乙奇 在 {p_yi}宫 + 开门 + 太阴 — 主稳固得财",
        })

    # 4. 人遁: 丁奇 + 休门 + 太阴 (亦取 开/生门, 与太阴合).
    p_ding = qi_palaces.get("丁")
    if (p_ding is not None
            and men.get(p_ding) in {"休门", "生门", "开门"}
            and shen.get(p_ding) == "太阴"):
        patterns.append({
            "name": "人遁",
            "evidence": f"丁奇 在 {p_ding}宫 + {men.get(p_ding)} + 太阴 — 主和合事成",
        })

    # 5. 青龙返首: 丙加甲 (即 天盘 丙 落于 地盘 戊 之上, 因 戊 代 甲子).
    #    Equivalent: heaven[X] == '丙' and earth[X] == '戊'.
    for p in range(1, 10):
        if heaven.get(p) == "丙" and earth.get(p) == "戊":
            patterns.append({
                "name": "青龙返首",
                "evidence": f"{p}宫 天盘丙 加 地盘戊 — 谋事大成",
            })
            break

    # 6. 飞鸟跌穴: 甲加丙 — 天盘 戊(代甲) 落于 地盘 丙 之上.
    for p in range(1, 10):
        if heaven.get(p) == "戊" and earth.get(p) == "丙":
            patterns.append({
                "name": "飞鸟跌穴",
                "evidence": f"{p}宫 天盘戊(代甲) 加 地盘丙 — 不期之吉",
            })
            break

    # 7. 击刑: 值符宫 之地支 与 时支 形成 三刑.
    #    地支 对应 palace via 后天九宫 (子=1, 寅丑=8, ...).
    p_branch_map: dict[int, list[str]] = {}
    for branch, pal in DIZHI_TO_PALACE.items():
        p_branch_map.setdefault(pal, []).append(branch)

    zf_branches = p_branch_map.get(zhi_fu_palace, [])
    for b in zf_branches:
        if hour_branch in SAN_XING_LOOKUP.get(b, set()):
            patterns.append({
                "name": "击刑",
                "evidence": f"值符宫 {zhi_fu_palace}宫({b}) 与时支 {hour_branch} 相刑",
            })
            break

    # 8. 入墓: 时干 入 该五行 之墓库 — 时干 落宫 包含 时干墓库地支.
    mu_branch = MU_KU.get(hour_stem)
    if mu_branch:
        mu_palace = DIZHI_TO_PALACE.get(mu_branch)
        if mu_palace == shi_gan_palace:
            patterns.append({
                "name": "入墓",
                "evidence": f"时干 {hour_stem} 入 {mu_branch}({mu_palace}宫) 之墓",
            })

    # 9. 五不遇时: 时干 克 日干.
    if (TIANGAN_WUXING.get(hour_stem)
            and WUXING_KE.get(TIANGAN_WUXING[hour_stem])
            == TIANGAN_WUXING.get(day_stem)):
        patterns.append({
            "name": "五不遇时",
            "evidence": f"时干 {hour_stem}({TIANGAN_WUXING[hour_stem]}) 克 "
                        f"日干 {day_stem}({TIANGAN_WUXING[day_stem]}) — 大事不宜",
        })

    # 10. 大格 (庚加癸): 天盘庚 加 地盘癸.
    for p in range(1, 10):
        if heaven.get(p) == "庚" and earth.get(p) == "癸":
            patterns.append({
                "name": "大格",
                "evidence": f"{p}宫 天盘庚 加 地盘癸 — 万事不顺",
            })
            break

    # 11. 伏吟: 天盘 与 地盘 完全相同.
    if all(heaven.get(p) == earth.get(p) for p in range(1, 10)):
        patterns.append({
            "name": "伏吟",
            "evidence": "天盘地盘完全相同 — 主事停滞难前",
        })

    return patterns


# --------------------------------------------------------------------------- #
# 吉凶方位
# --------------------------------------------------------------------------- #

def classify_directions(
    men: dict[int, str],
    star: dict[int, str],
    heaven: dict[int, str],
) -> tuple[list[str], list[str]]:
    """Return (aupicious_directions, inauspicious_directions) — palace 方位."""
    aus: list[str] = []
    inaus: list[str] = []
    for p in range(1, 10):
        if p == 5:
            continue
        info = PALACE_INFO[p]
        direction = info["direction"]
        score = 0
        if men.get(p) in JI_MEN:
            score += 2
        if men.get(p) in XIONG_MEN:
            score -= 2
        if heaven.get(p) in SAN_QI:
            score += 1
        if star.get(p) in {"天心", "天辅", "天任", "天禽"}:
            score += 1
        if star.get(p) in {"天蓬", "天芮", "天柱"}:
            score -= 1
        if score >= 2:
            aus.append(direction)
        elif score <= -2:
            inaus.append(direction)
    return aus, inaus


# --------------------------------------------------------------------------- #
# Build palace records
# --------------------------------------------------------------------------- #

def build_palaces(
    earth: dict[int, str],
    heaven: dict[int, str],
    men: dict[int, str],
    star: dict[int, str],
    shen: dict[int, str],
) -> list[dict]:
    out: list[dict] = []
    for p in range(1, 10):
        info = PALACE_INFO[p]
        notes: list[str] = []
        if p == 5:
            notes.append("中宫: 天禽寄坤二宫, 无门")
        if star.get(p) == "天禽":
            notes.append("天禽 寄此宫")
        if p == 2 and star.get(2) is not None:
            notes.append("坤宫: 天芮+天禽 同宫")
        out.append({
            "index": p,
            "palace": info["palace"],
            "direction": info["direction"],
            "wuxing": info["wuxing"],
            "earth_yi_qi": earth.get(p),
            "heaven_yi_qi": heaven.get(p),
            "men": men.get(p),
            "star": star.get(p),
            "shen": shen.get(p),
            "notes": "; ".join(notes) if notes else "",
        })
    return out


# --------------------------------------------------------------------------- #
# Helper: figure out 节气 + 三元 from lunar_python
# --------------------------------------------------------------------------- #

def jieqi_context(solar_year: int, solar_month: int, solar_day: int) -> tuple[str, int]:
    """Return (current_jieqi_name, days_since_that_jieqi).

    Uses 前节气 (prev) — i.e. the most recent jieqi at-or-before given date.
    """
    require_lunar()
    from lunar_python import Solar  # type: ignore

    s = Solar.fromYmdHms(solar_year, solar_month, solar_day, 12, 0, 0)
    lunar = s.getLunar()

    prev = lunar.getPrevJieQi()
    today_jq = lunar.getJieQi()
    if today_jq:
        # 节气当日
        return today_jq, 0

    prev_name = prev.getName()
    prev_solar = prev.getSolar()
    py, pm, pd = prev_solar.getYear(), prev_solar.getMonth(), prev_solar.getDay()
    from datetime import date
    delta = (date(solar_year, solar_month, solar_day)
             - date(py, pm, pd)).days
    return prev_name, delta


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="奇门遁甲 时家盘 (转盘式) — 计算九宫天地人神四盘 + 格局",
    )
    p.add_argument("--date", type=str, default=None,
                   help="公历日期 YYYY-MM-DD (默认今日)")
    p.add_argument("--time", type=str, default=None,
                   help="时间 HH:MM (默认当前)")
    p.add_argument("--longitude", type=float, default=None,
                   help="经度 (用于真太阳时修正, 可选)")
    p.add_argument("--ju-type", type=str, choices=["yang", "yin"], default=None,
                   help="手动指定 阳遁/阴遁 (覆盖自动算法)")
    p.add_argument("--ju-number", type=int, default=None,
                   help="手动指定 局数 1..9 (与 --ju-type 配合)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    # Determine input datetime
    now = datetime.now()
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            y, m, d = dt.year, dt.month, dt.day
        except ValueError as e:
            json_print({"ok": False, "error": "invalid_date",
                        "message": str(e), "expected": "YYYY-MM-DD"})
            return 1
    else:
        y, m, d = now.year, now.month, now.day

    if args.time:
        try:
            hh, mm = map(int, args.time.split(":"))
        except Exception:
            json_print({"ok": False, "error": "invalid_time",
                        "expected": "HH:MM"})
            return 1
    else:
        hh, mm = now.hour, now.minute

    # Longitude correction
    if args.longitude is not None:
        hh, mm = longitude_correction(hh, mm, args.longitude,
                                      tz_offset_hours=8.0,
                                      year=y, month=m, day=d)

    # Compute ganzhi via lunar_python
    require_lunar()
    from lunar_python import Solar  # type: ignore
    solar = Solar.fromYmdHms(y, m, d, hh, mm, 0)
    lunar = solar.getLunar()
    year_gz = lunar.getYearInGanZhi()
    month_gz = lunar.getMonthInGanZhi()
    day_gz = lunar.getDayInGanZhi()
    hour_gz = lunar.getTimeInGanZhi()
    day_stem = lunar.getDayGan()
    day_branch = lunar.getDayZhi()
    hour_stem = lunar.getTimeGan()
    hour_branch = lunar.getTimeZhi()

    # 1. 局数 determination
    if args.ju_type and args.ju_number:
        ju_type = "阳遁" if args.ju_type == "yang" else "阴遁"
        ju_number = args.ju_number
        san_yuan = "手动"
        jq_name = "(手动)"
    else:
        try:
            jq_name, days_since = jieqi_context(y, m, d)
            ju_type, san_yuan, ju_number = determine_ju(jq_name, days_since)
        except (ValueError, KeyError) as e:
            json_print({"ok": False, "error": "ju_determination_failed",
                        "message": str(e)})
            return 1

    # 2. 地盘
    earth = earth_plate(ju_type, ju_number)

    # 3. 旬首 + 值符宫 + 时干宫 + 天盘
    head_name, head_yi = xun_head(hour_stem, hour_branch)

    # 时干 可能 是 甲: 甲 隐在 旬首六仪 之下. 处理 时干=甲 的情形.
    effective_shi_gan = hour_stem
    if hour_stem == "甲":
        effective_shi_gan = head_yi  # 甲 遁于 六仪
    # Re-derive heaven plate with effective stem
    head_name2, head_yi2 = xun_head(hour_stem, hour_branch)
    zhi_fu_palace = next(p for p, yq in earth.items() if yq == head_yi2)
    shi_gan_palace = next(p for p, yq in earth.items() if yq == effective_shi_gan)

    # heaven
    full_seq = YANG_PALACE_SEQ if ju_type == "阳遁" else YIN_PALACE_SEQ
    from_idx = full_seq.index(zhi_fu_palace)
    to_idx = full_seq.index(shi_gan_palace)
    shift = (to_idx - from_idx) % 9
    heaven: dict[int, str] = {}
    for k, palace in enumerate(full_seq):
        target = full_seq[(k + shift) % 9]
        heaven[target] = earth[palace]

    # 4. 九星 (rotates with 值符)
    star = star_plate(zhi_fu_palace, shi_gan_palace, ju_type)
    # 值符星: 时干宫 (5 寄 2) 上 当前 九星
    zhi_fu_star = star.get(_resolve_ring_palace(shi_gan_palace), "?")

    # 5. 八门 (rotates with 值使)
    men = men_plate(zhi_fu_palace, shi_gan_palace, ju_type)
    zhi_shi_men = men.get(_resolve_ring_palace(shi_gan_palace), "?")

    # 6. 八神 — 值符 起于 时干宫 (即 当前 值符 所在)
    shen = shen_plate(shi_gan_palace, ju_type)

    # 7. Build palace records
    palaces = build_palaces(earth, heaven, men, star, shen)

    # 8. 格局 detection
    patterns = detect_patterns(
        earth, heaven, men, shen, star,
        hour_stem, hour_branch, day_stem,
        zhi_fu_palace, shi_gan_palace,
    )

    # 9. 方位 吉凶
    aus_dirs, inaus_dirs = classify_directions(men, star, heaven)

    # 10. Summary
    summary_parts = [
        f"{ju_type}{ju_number}局({san_yuan})",
        f"节气: {jq_name}",
        f"时干 {hour_stem} 落于 {shi_gan_palace}宫({PALACE_INFO[shi_gan_palace]['palace']})",
        f"值符 {zhi_fu_star} 居 {shi_gan_palace}宫",
        f"值使 {zhi_shi_men}",
    ]
    if patterns:
        names = ", ".join(pp["name"] for pp in patterns)
        summary_parts.append(f"格局: {names}")

    out = {
        "ok": True,
        "tool": "qimen",
        "version": "1.0.0",
        "input": {
            "date": f"{y:04d}-{m:02d}-{d:02d}",
            "time": f"{hh:02d}:{mm:02d}",
            "longitude": args.longitude,
        },
        "ganzhi": {
            "year": year_gz,
            "month": month_gz,
            "day": day_gz,
            "hour": hour_gz,
        },
        "jieqi": jq_name,
        "san_yuan": san_yuan,
        "ju_type": ju_type,
        "ju_number": ju_number,
        "shi_gan": hour_stem,
        "shi_zhi": hour_branch,
        "xun_head": head_name,
        "xun_yi": head_yi,
        "zhi_fu_star": zhi_fu_star,
        "zhi_fu_palace": shi_gan_palace,
        "zhi_fu_origin_palace": zhi_fu_palace,
        "zhi_shi_men": zhi_shi_men,
        "zhi_shi_palace": shi_gan_palace,
        "palaces": palaces,
        "patterns": patterns,
        "auspicious_directions": sorted(set(aus_dirs)),
        "inauspicious_directions": sorted(set(inaus_dirs)),
        "summary": "; ".join(summary_parts),
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
