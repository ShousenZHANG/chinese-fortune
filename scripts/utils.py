"""Shared utilities for the chinese-fortune skill scripts.

Constants and helpers for:
  * 天干 / 地支 / 五行
  * 五行生克 / 八卦 / 地支藏干
  * 十神 (shi_shen) computation
  * 五虎遁 (year-stem -> month-stem) and 五鼠遁 (day-stem -> hour-stem)
  * Lunar package import guard
  * JSON pretty-print with ensure_ascii=False
  * Longitude-based true-solar-time correction
"""

from __future__ import annotations

import json
import sys
from typing import Optional, Tuple


# --------------------------------------------------------------------------- #
# Core cycles
# --------------------------------------------------------------------------- #

TIANGAN: list[str] = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI: list[str] = [
    "子", "丑", "寅", "卯", "辰", "巳",
    "午", "未", "申", "酉", "戌", "亥",
]

# 阴阳: 0=阳, 1=阴
TIANGAN_YIN_YANG: dict[str, str] = {
    s: ("阳" if i % 2 == 0 else "阴") for i, s in enumerate(TIANGAN)
}
DIZHI_YIN_YANG: dict[str, str] = {
    b: ("阳" if i % 2 == 0 else "阴") for i, b in enumerate(DIZHI)
}

# 五行 of 天干
TIANGAN_WUXING: dict[str, str] = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 五行 of 地支
DIZHI_WUXING: dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

WUXING: dict[str, str] = {**TIANGAN_WUXING, **DIZHI_WUXING}

# 五行相生 (生我者... 我生者: key 生 value)
WUXING_GEN: dict[str, str] = {
    "木": "火", "火": "土", "土": "金", "金": "水", "水": "木",
}
# 五行相克 (key 克 value)
WUXING_KE: dict[str, str] = {
    "木": "土", "土": "水", "水": "火", "火": "金", "金": "木",
}

# 生肖 of 地支
DIZHI_ZODIAC: dict[str, str] = {
    "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
    "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
    "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪",
}
ZODIAC_TO_DIZHI: dict[str, str] = {v: k for k, v in DIZHI_ZODIAC.items()}


# --------------------------------------------------------------------------- #
# 地支藏干 (hidden stems in each branch)
# --------------------------------------------------------------------------- #

HIDDEN_STEMS: dict[str, list[str]] = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}


# --------------------------------------------------------------------------- #
# 八卦
# --------------------------------------------------------------------------- #
# Lines from top to bottom: list of 3 (1=阳, 0=阴)
# Binary index (used for 64 hex) — convention: bottom line is bit-0
# Names in 先天 / 后天 order keyed by binary value.

BAGUA: dict[str, dict] = {
    "乾": {"lines": [1, 1, 1], "binary": 0b111, "wuxing": "金",
            "nature": "天", "attribute": "健", "direction_houtian": "西北",
            "family": "父", "number_xiantian": 1},
    "兑": {"lines": [0, 1, 1], "binary": 0b110, "wuxing": "金",
            "nature": "泽", "attribute": "悦", "direction_houtian": "西",
            "family": "少女", "number_xiantian": 2},
    "离": {"lines": [1, 0, 1], "binary": 0b101, "wuxing": "火",
            "nature": "火", "attribute": "丽", "direction_houtian": "南",
            "family": "中女", "number_xiantian": 3},
    "震": {"lines": [0, 0, 1], "binary": 0b100, "wuxing": "木",
            "nature": "雷", "attribute": "动", "direction_houtian": "东",
            "family": "长男", "number_xiantian": 4},
    "巽": {"lines": [1, 1, 0], "binary": 0b011, "wuxing": "木",
            "nature": "风", "attribute": "入", "direction_houtian": "东南",
            "family": "长女", "number_xiantian": 5},
    "坎": {"lines": [0, 1, 0], "binary": 0b010, "wuxing": "水",
            "nature": "水", "attribute": "陷", "direction_houtian": "北",
            "family": "中男", "number_xiantian": 6},
    "艮": {"lines": [1, 0, 0], "binary": 0b001, "wuxing": "土",
            "nature": "山", "attribute": "止", "direction_houtian": "东北",
            "family": "少男", "number_xiantian": 7},
    "坤": {"lines": [0, 0, 0], "binary": 0b000, "wuxing": "土",
            "nature": "地", "attribute": "顺", "direction_houtian": "西南",
            "family": "母", "number_xiantian": 8},
}

# 先天八卦 number -> name lookup (used for 梅花起卦 number→trigram)
XIANTIAN_NUM_TO_TRIGRAM: dict[int, str] = {
    1: "乾", 2: "兑", 3: "离", 4: "震",
    5: "巽", 6: "坎", 7: "艮", 8: "坤",
}

BINARY_TO_TRIGRAM: dict[int, str] = {v["binary"]: k for k, v in BAGUA.items()}


# --------------------------------------------------------------------------- #
# 五虎遁 — given a 年干, the first 月 (寅月) takes which 天干?
# 甲己起丙寅, 乙庚起戊寅, 丙辛起庚寅, 丁壬起壬寅, 戊癸起甲寅.
# --------------------------------------------------------------------------- #

WUHU_DUN: dict[str, str] = {
    "甲": "丙", "己": "丙",
    "乙": "戊", "庚": "戊",
    "丙": "庚", "辛": "庚",
    "丁": "壬", "壬": "壬",
    "戊": "甲", "癸": "甲",
}

# --------------------------------------------------------------------------- #
# 五鼠遁 — given a 日干, the 子时 takes which 天干?
# 甲己还加甲, 乙庚丙作初, 丙辛从戊起, 丁壬庚子居, 戊癸何方发, 壬子是真途.
# --------------------------------------------------------------------------- #

WUSHU_DUN: dict[str, str] = {
    "甲": "甲", "己": "甲",
    "乙": "丙", "庚": "丙",
    "丙": "戊", "辛": "戊",
    "丁": "庚", "壬": "庚",
    "戊": "壬", "癸": "壬",
}


# --------------------------------------------------------------------------- #
# 十神 lookup
# --------------------------------------------------------------------------- #
# Relationship between two stems given the day-master (日主).
# Rules:
#   same 五行 + same 阴阳 -> 比肩
#   same 五行 + diff 阴阳 -> 劫财
#   day generates other:  same 阴阳 -> 食神 ; diff -> 伤官
#   day controls other:   same 阴阳 -> 偏财 ; diff -> 正财
#   other controls day:   same 阴阳 -> 七杀 ; diff -> 正官
#   other generates day:  same 阴阳 -> 偏印 ; diff -> 正印

def tg_dz_yin_yang(stem_or_branch: str) -> str:
    """Return 阳 / 阴 for a 天干 or 地支."""
    if stem_or_branch in TIANGAN_YIN_YANG:
        return TIANGAN_YIN_YANG[stem_or_branch]
    if stem_or_branch in DIZHI_YIN_YANG:
        return DIZHI_YIN_YANG[stem_or_branch]
    raise ValueError(f"unknown stem/branch: {stem_or_branch}")


def tg_dz_wuxing(stem_or_branch: str) -> str:
    """Return 五行 for a 天干 or 地支."""
    if stem_or_branch in WUXING:
        return WUXING[stem_or_branch]
    raise ValueError(f"unknown stem/branch: {stem_or_branch}")


def shi_shen(day_stem: str, other_stem: str) -> str:
    """Return 十神 name relating ``other_stem`` to ``day_stem`` (日主)."""
    if day_stem not in TIANGAN_WUXING or other_stem not in TIANGAN_WUXING:
        raise ValueError("shi_shen requires two 天干")

    day_wx = TIANGAN_WUXING[day_stem]
    other_wx = TIANGAN_WUXING[other_stem]
    same_polarity = TIANGAN_YIN_YANG[day_stem] == TIANGAN_YIN_YANG[other_stem]

    if day_wx == other_wx:
        return "比肩" if same_polarity else "劫财"
    if WUXING_GEN.get(day_wx) == other_wx:
        # day generates other
        return "食神" if same_polarity else "伤官"
    if WUXING_KE.get(day_wx) == other_wx:
        # day controls other
        return "偏财" if same_polarity else "正财"
    if WUXING_KE.get(other_wx) == day_wx:
        # other controls day
        return "七杀" if same_polarity else "正官"
    if WUXING_GEN.get(other_wx) == day_wx:
        # other generates day
        return "偏印" if same_polarity else "正印"
    return "未知"


# --------------------------------------------------------------------------- #
# 60 甲子 helper
# --------------------------------------------------------------------------- #

def jiazi_index(stem: str, branch: str) -> int:
    """Return 0-59 index of a 甲子 pair."""
    s = TIANGAN.index(stem)
    b = DIZHI.index(branch)
    # The 60-cycle: stems repeat every 10, branches every 12; offset must satisfy
    # both. Walk the cycle until match.
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise ValueError(f"invalid 甲子 pair: {stem}{branch}")


# --------------------------------------------------------------------------- #
# JSON / IO helpers
# --------------------------------------------------------------------------- #

def json_print(obj) -> None:
    """Pretty-print an object as UTF-8 JSON to stdout.

    Forces UTF-8 output regardless of platform console codepage — this lets
    Chinese characters and rare symbols (e.g. trigram lines ✕○) survive
    Windows GBK consoles. Callers can still redirect to files safely.
    """
    payload = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    # Reconfigure stdout to UTF-8 if possible (Python 3.7+); fall back to
    # writing raw bytes via the underlying buffer.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        print(payload)
    except Exception:
        try:
            sys.stdout.buffer.write(payload.encode("utf-8"))
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        except Exception:
            print(payload.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


def warn(msg: str) -> None:
    """Send a warning to stderr without polluting JSON stdout."""
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        print(f"[warn] {msg}", file=sys.stderr)
    except UnicodeEncodeError:
        sys.stderr.buffer.write(f"[warn] {msg}\n".encode("utf-8", errors="replace"))


def require_lunar():
    """Import ``lunar_python``. On failure, print JSON error & exit 1."""
    try:
        import lunar_python  # noqa: F401
        return lunar_python
    except ImportError:
        err = {
            "error": "missing_dependency",
            "package": "lunar_python",
            "install_hint": "pip install lunar_python>=1.4.4",
            "message": (
                "本脚本依赖 lunar_python 处理农历/八字/节气, 未检测到该模块。"
                "请执行 'pip install lunar_python' 后重试。"
            ),
        }
        json_print(err)
        sys.exit(1)


# --------------------------------------------------------------------------- #
# 真太阳时 — longitude correction
# --------------------------------------------------------------------------- #

import math
import calendar


def equation_of_time(day_of_year: int, leap: bool = False) -> float:
    """Equation of Time (EOT) in minutes for a given Julian day of year.

    Uses Spencer's truncated approximation (good to ~±20 s vs JPL Horizons):
        B = 2π (n - 81) / N
        EOT = 9.87 sin(2B) - 7.53 cos(B) - 1.5 sin(B)
    Positive EOT = sundial ahead of clock.
    """
    n_days = 366 if leap else 365
    b = 2.0 * math.pi * (day_of_year - 81) / n_days
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def longitude_correction(
    birth_hour: int,
    birth_minute: int,
    longitude: float,
    tz_offset_hours: float = 8.0,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> Tuple[int, int]:
    """Adjust clock time to local true solar time.

    Combines two corrections:
      (1) Longitude offset: each degree east of the timezone's reference
          meridian (120°E for GMT+8) adds 4 minutes; each degree west subtracts.
      (2) Equation of Time (EOT): orbital eccentricity + axial tilt cause clock
          and sundial to differ by up to ±16 minutes across the year. Applied
          only if year/month/day supplied.

    Returns (hour, minute) in 0..23, 0..59. Date roll-over clamped to same day;
    typical longitude+EOT offsets within China stay inside one day.
    """
    ref_meridian = tz_offset_hours * 15.0  # 120° for GMT+8
    delta_minutes = (longitude - ref_meridian) * 4.0

    if year is not None and month is not None and day is not None:
        day_of_year = (
            (calendar.datetime.date(year, month, day) - calendar.datetime.date(year, 1, 1)).days + 1
        )
        delta_minutes += equation_of_time(day_of_year, leap=calendar.isleap(year))

    total = birth_hour * 60 + birth_minute + delta_minutes
    total = int(round(total))
    total = max(0, min(24 * 60 - 1, total))
    return divmod(total, 60)


def true_solar_time_info(
    longitude: float,
    tz_offset_hours: float,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
) -> dict:
    """Return structured info on the longitude + EOT correction applied."""
    ref_meridian = tz_offset_hours * 15.0
    lon_delta = (longitude - ref_meridian) * 4.0
    day_of_year = (
        (calendar.datetime.date(year, month, day) - calendar.datetime.date(year, 1, 1)).days + 1
    )
    eot = equation_of_time(day_of_year, leap=calendar.isleap(year))
    total_delta = lon_delta + eot
    corrected_total = hour * 60 + minute + total_delta
    corrected_h, corrected_m = divmod(int(round(corrected_total)), 60)
    return {
        "longitude": longitude,
        "ref_meridian": ref_meridian,
        "longitude_offset_min": round(lon_delta, 2),
        "equation_of_time_min": round(eot, 2),
        "total_offset_min": round(total_delta, 2),
        "clock_time": f"{hour:02d}:{minute:02d}",
        "true_solar_time": f"{corrected_h:02d}:{corrected_m:02d}",
    }


# --------------------------------------------------------------------------- #
# 81 数理 - used in name_analyze (lookup table loaded there; mini version here
# for module-level reference; full inline table lives in name_analyze.py).
# --------------------------------------------------------------------------- #

# name_analyze.py owns the full 81 数理 dataset.
