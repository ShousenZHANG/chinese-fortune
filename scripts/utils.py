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

import calendar
import json
import math
import sys
from datetime import date as _date
from datetime import datetime as _datetime

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
# Package version — the single source of truth.
# build_skill.py reads it from here to name the release zip, and every CLI
# echoes it in its JSON envelope.
# --------------------------------------------------------------------------- #

__version__ = "1.7.4"


# --------------------------------------------------------------------------- #
# 八卦
# --------------------------------------------------------------------------- #
# Lines from top to bottom: list of 3 (1=阳, 0=阴)
# Binary index (used for 64 hex) — same top-to-bottom order, so the
# bottom line (初爻) is bit-2 and the top line is bit-0.
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

XUN_KONG_BY_OFFSET: dict[int, list[str]] = {
    0: ["戌", "亥"],   # 甲子旬
    1: ["申", "酉"],   # 甲戌旬
    2: ["午", "未"],   # 甲申旬
    3: ["辰", "巳"],   # 甲午旬
    4: ["寅", "卯"],   # 甲辰旬
    5: ["子", "丑"],   # 甲寅旬
}

# (地支 index - 天干 index) % 12 -> which 旬 the pillar belongs to.
_XUN_DIFF_TO_OFFSET: dict[int, int] = {0: 0, 10: 1, 8: 2, 6: 3, 4: 4, 2: 5}


def xun_kong(stem: str, branch: str) -> list[str]:
    """The two 地支 that are 旬空 for a given 干支 pillar.

    Every 旬 covers 10 of the 12 branches; the two left over are 空亡. bazi and
    liuyao carried identical copies of this table, verified equal across all 60
    pillars before merging.
    """
    diff = (DIZHI.index(branch) - TIANGAN.index(stem)) % 12
    offset = _XUN_DIFF_TO_OFFSET.get(diff)
    return XUN_KONG_BY_OFFSET[offset] if offset is not None else []


def chong_branch(branch: str) -> str:
    """六冲 partner: the branch directly opposite on the 12-branch circle."""
    return DIZHI[(DIZHI.index(branch) + 6) % 12]


def hour_branch_index(hour: int) -> int:
    """0-11 index of the 时辰 containing ``hour`` (子=0).

    子时 spans 23:00-01:00, so both 23 and 0 map to 子. Five engines carried
    byte-identical copies of this arithmetic; they now share this one, which is
    verified against all 24 hours in tests/test_utils.py.
    """
    if hour == 23 or hour == 0:
        return 0
    return ((hour + 1) // 2) % 12


def hour_branch(hour: int) -> str:
    """地支 of the 时辰 containing ``hour``."""
    return DIZHI[hour_branch_index(hour)]


def shichen_number(hour: int) -> int:
    """1-based 时辰 ordinal (子=1 … 亥=12), as 梅花/周易 起卦 expects."""
    return hour_branch_index(hour) + 1


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

def parse_datetime_arg(value: str | None) -> _datetime:
    """Return the caller-supplied ISO datetime, or now() when omitted.

    Time-based casts are otherwise unreproducible and untestable: the wall
    clock feeds both the hexagram and 体用旺衰, so the same question yields a
    different reading on every run and no golden assertion is possible.

    Raises ValueError on a malformed value; callers emit the standard error
    envelope and return 1.
    """
    if value is None:
        return _datetime.now()
    try:
        return _datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"--datetime 需 ISO 格式 (如 2026-06-24T13:05), 收到: {value}"
        ) from None


def ensure_utf8_stdio() -> None:
    """Force stdout/stderr to UTF-8 before argparse can write to them.

    The scripts carry Chinese help text. When stdout is a pipe (how an agent
    invokes them) or the console is non-CJK (cp1252/cp437), Python falls back
    to the ANSI codepage and argparse's --help raises UnicodeEncodeError,
    exiting 1 with no output. Reconfiguring here — before parse_args — fixes
    --help, error messages, and warnings in one place.

    errors="replace" keeps a degraded console from turning into a crash.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:  # pragma: no cover - stream without reconfigure
            pass


def json_print(obj: object) -> None:
    """Pretty-print an object as UTF-8 JSON to stdout.

    Forces UTF-8 output regardless of platform console codepage — this lets
    Chinese characters and rare symbols (e.g. trigram lines ✕○) survive
    Windows GBK consoles. Callers can still redirect to files safely.
    """
    payload = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    # Reconfigure stdout to UTF-8 if possible (Python 3.7+); fall back to
    # writing raw bytes via the underlying buffer.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print(payload)
    except Exception:
        try:
            sys.stdout.buffer.write(payload.encode("utf-8"))
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        except Exception:
            print(payload.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


# --------------------------------------------------------------------------- #
# CLI 契约 — 统一的错误信封与边界校验
# --------------------------------------------------------------------------- #
#
# 从前 16 个 CLI 各自手搓错误 dict (全仓 54 处 "error" 字面量), 键不齐、语义不一,
# 而边界校验只有 bazi_calc 一家做。实测出的洞: ziwei_calc 收到 1990-02-31 会返回
# ok:true 加一张凭空归一化出来的命盘; zodiac_compat --year 99999 与 qimen_cast
# --time 99:99 直接崩栈, stdout 无 JSON、stderr 是带绝对路径的 traceback。
#
# 调用方 (Claude) 无法从 traceback 或一张编造的盘里分辨对错, 所以这两种失败模式
# 都必须收敛成一个信封。

# lunar_python 的历表范围。
YEAR_MIN, YEAR_MAX = 1900, 2100


def error_envelope(tool: str, error: str, message: str, **extra: object) -> dict:
    """所有 CLI 的统一失败信封。

    ok/tool/version/error/message 五个键恒定存在, 调用方可无条件读取。
    """
    out = {
        "ok": False,
        "tool": tool,
        "version": __version__,
        "error": error,
        "message": message,
    }
    out.update(extra)
    return out


def ok_envelope(tool: str, payload: dict) -> dict:
    """给成功载荷补上 ok/tool/version 三个恒定键。

    实测 16 个引擎里只有 4 个在成功时输出完整信封, 8 个一个键都没有 —— 调用方
    (Claude) 因此无法统一判断一次调用是成功还是失败, 只能逐引擎特判。三个键放在
    最前面, 载荷原有键一律保留且优先 (引擎已自带 ok 时不覆盖)。
    """
    out = {"ok": True, "tool": tool, "version": __version__}
    out.update(payload)
    return out


def validate_birth_input(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int | None = None,
    minute: int | None = None,
    *,
    year_range: tuple[int, int] = (YEAR_MIN, YEAR_MAX),
    lunar: bool = False,
) -> str | None:
    """校验公历/农历生辰分量。返回错误信息字符串, 合法则返回 None。

    ``lunar=True`` 时只做分量范围检查 —— 农历月大小与闰月由 lunar_python 决定,
    这里不能用 calendar.monthrange 判。公历则连"这个月有没有这一天"一并验:
    Solar.fromYmdHms 会接受 1990-02-31 并给出一个农历转换, argparse 的 1-31 也
    放行, 所以必须自己用 date() 验一次。
    """
    lo, hi = year_range
    if year is not None and not lo <= year <= hi:
        return f"year 超出支持范围 {lo}-{hi}, 收到 {year}"
    if month is not None and not 1 <= month <= 12:
        return f"month 必须在 1-12, 收到 {month}"
    if day is not None and not 1 <= day <= 31:
        return f"day 必须在 1-31, 收到 {day}"
    if hour is not None and not 0 <= hour <= 23:
        return f"hour 必须在 0-23, 收到 {hour}"
    if minute is not None and not 0 <= minute <= 59:
        return f"minute 必须在 0-59, 收到 {minute}"
    if not lunar and year is not None and month is not None and day is not None:
        try:
            _date(year, month, day)
        except ValueError as exc:
            return f"{year}-{month:02d}-{day:02d} 不是真实存在的公历日期 ({exc})"
    return None


def warn(msg: str) -> None:
    """Send a warning to stderr without polluting JSON stdout."""
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    try:
        print(f"[warn] {msg}", file=sys.stderr)
    except UnicodeEncodeError:
        sys.stderr.buffer.write(f"[warn] {msg}\n".encode("utf-8", errors="replace"))


def require_lunar() -> None:
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


_CITY_INDEX: dict[str, dict] | None = None


def _load_city_index() -> dict[str, dict]:
    """name / alias -> city row, built once from assets/cities_cn.json."""
    global _CITY_INDEX
    if _CITY_INDEX is not None:
        return _CITY_INDEX
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "assets", "cities_cn.json"),
                 os.path.join(here, "assets", "cities_cn.json")):
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                rows = json.load(f).get("cities", [])
            break
    else:
        rows = []
    index: dict[str, dict] = {}
    for row in rows:
        for key in [row["name"], *row.get("aliases", [])]:
            index.setdefault(key, row)
            index.setdefault(key + "市", row)
    _CITY_INDEX = index
    return index


def lookup_city(name: str) -> dict | None:
    """Resolve a 出生地 (省市 name, alias, or pinyin) to its table row.

    The intake protocol collects 出生地 but, until this table existed, nothing
    mapped it to a longitude — the LLM had to know that 成都 is 104°E itself.
    1° of longitude is 4 minutes of true solar time and 时辰 boundaries fall on
    the hour, so a birth anywhere off the 120°E meridian can change 时柱; the
    Chengdu eval case flipped 丙辰 -> 乙卯 on exactly this correction.
    """
    if not name:
        return None
    key = name.strip()
    index = _load_city_index()
    return index.get(key) or index.get(key.rstrip("市")) or None


def resolve_timezone_offset(
    tz_name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
) -> dict:
    """Actual UTC offset of a clock reading, DST and history included.

    A birth time is given as it read on the clock, but 时辰 boundaries are
    defined against standard time — and China's clocks have not always been
    UTC+8. tzdata records 30 offset changes for Asia/Shanghai between 1900 and
    1995, of which 14 windows sit at UTC+9: 1919, 1940-1949, and the 夏令时 of
    1986-1991. A clock reading inside one of those is an hour ahead of standard
    time, so anything in the hour after a 时辰 boundary lands in the previous
    时辰 once corrected.

    Returns ``{offset_hours, dst_hours, tz_name, abbrev, note}``. Pass
    ``offset_hours`` to :func:`longitude_correction` as ``tz_offset_hours``:
    its reference meridian is ``tz * 15``, so a +9 offset moves the meridian to
    135°E and the extra hour is subtracted by the existing arithmetic.
    """
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:  # pragma: no cover - Python < 3.9
        raise ValueError(f"无法解析时区 (zoneinfo 不可用): {exc}") from exc

    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, ModuleNotFoundError) as exc:
        raise ValueError(
            f"未知时区 {tz_name!r}; 请用 IANA 名称, 如 Asia/Shanghai"
        ) from exc

    moment = _datetime(year, month, day, hour, minute, tzinfo=zone)
    utcoff = moment.utcoffset()
    dst = moment.dst()
    if utcoff is None:
        raise ValueError(f"时区 {tz_name!r} 未能给出偏移")

    offset_hours = utcoff.total_seconds() / 3600.0
    dst_hours = (dst.total_seconds() / 3600.0) if dst else 0.0

    note = ""
    if dst_hours:
        note = (
            f"出生时该地行夏令时 (UTC{offset_hours:+g}, 快 {dst_hours:g} 小时); "
            f"时柱按标准时折算, 未按钟表时直接取时辰。"
        )
    return {
        "tz_name": tz_name,
        "offset_hours": offset_hours,
        "dst_hours": dst_hours,
        "abbrev": moment.tzname(),
        "note": note,
    }


def longitude_correction(
    birth_hour: int,
    birth_minute: int,
    longitude: float,
    tz_offset_hours: float = 8.0,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> tuple[int, int, int]:
    """Adjust clock time to local true solar time.

    Combines two corrections:
      (1) Longitude offset: each degree east of the timezone's reference
          meridian (120°E for GMT+8) adds 4 minutes; each degree west subtracts.
      (2) Equation of Time (EOT): orbital eccentricity + axial tilt cause clock
          and sundial to differ by up to ±16 minutes across the year. Applied
          only if year/month/day supplied.

    Returns (day_offset, hour, minute) where ``day_offset`` ∈ {-1, 0, +1}
    indicates that the corrected instant rolled into the previous (-1) or next
    (+1) calendar day. Callers MUST apply ``day_offset`` to the birth date
    *before* deriving the day pillar (日柱); otherwise near-midnight births at
    western/eastern longitudes are assigned the wrong 日柱 and 子时.
    """
    ref_meridian = tz_offset_hours * 15.0  # 120° for GMT+8
    delta_minutes = (longitude - ref_meridian) * 4.0

    if year is not None and month is not None and day is not None:
        day_of_year = (
            (_date(year, month, day) - _date(year, 1, 1)).days + 1
        )
        delta_minutes += equation_of_time(day_of_year, leap=calendar.isleap(year))

    total = int(round(birth_hour * 60 + birth_minute + delta_minutes))
    # divmod handles negative totals correctly: -9 -> (-1, 1431) i.e. prev day 23:51
    day_offset, minutes_in_day = divmod(total, 24 * 60)
    hour, minute = divmod(minutes_in_day, 60)
    return day_offset, hour, minute


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
        (_date(year, month, day) - _date(year, 1, 1)).days + 1
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
