"""符头三元与实交节定局；来源及现代日界约定见 docs/QIMEN-LIUREN-METHODS.md。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from qimen_tables import YANG_JIE_QI, YIN_JIE_QI
from utils import jiazi_index, require_lunar

SOURCE_URL = "https://zh.wikisource.org/w/index.php?oldid=8259389"
CALENDAR_ZONE = timezone(timedelta(hours=8))


def futou(day_ganzhi: str) -> tuple[str, str]:
    """最近甲/己日起五日一元；符头地支定上中下，不从交节日重新起上元。"""
    if len(day_ganzhi) != 2:
        raise ValueError("日干支须为两个字")
    index = jiazi_index(day_ganzhi[0], day_ganzhi[1])
    head = index - index % 5
    stem = "甲乙丙丁戊己庚辛壬癸"[head % 10]
    branch = "子丑寅卯辰巳午未申酉戌亥"[head % 12]
    yuan = "上元" if branch in "子午卯酉" else "中元" if branch in "寅申巳亥" else "下元"
    return stem + branch, yuan


def determine_ju(jieqi_name: str, day_ganzhi: str) -> tuple[str, str, int]:
    """《元灵经》三元符头、阴阳各局；不用超神接气置闰。"""
    _, yuan = futou(day_ganzhi)
    index = ("上元", "中元", "下元").index(yuan)
    if jieqi_name in YANG_JIE_QI:
        return "阳遁", yuan, YANG_JIE_QI[jieqi_name][index]
    if jieqi_name in YIN_JIE_QI:
        return "阴遁", yuan, YIN_JIE_QI[jieqi_name][index]
    raise ValueError(f"unknown 节气: {jieqi_name}")


def seasonal_context(instant: datetime) -> dict:
    """Select the last solar term at the actual instant, including the year boundary.

    lunar_python's term table uses UTC+08 clock values. An aware input is first
    converted to that clock. A floating input cannot locate an astronomical
    instant and is returned explicitly as an unresolved calendar assumption.
    """
    require_lunar()
    from lunar_python import Solar

    aware = instant.tzinfo is not None and instant.utcoffset() is not None
    clock = instant.astimezone(CALENDAR_ZONE) if aware else instant
    solar = Solar.fromYmdHms(clock.year, clock.month, clock.day,
                            clock.hour, clock.minute, clock.second)
    term = solar.getLunar().getPrevJieQi()
    value = term.getSolar()
    boundary = datetime(value.getYear(), value.getMonth(), value.getDay(),
                        value.getHour(), value.getMinute(), value.getSecond(),
                        tzinfo=CALENDAR_ZONE)
    return {
        "name": term.getName(),
        "boundary_calendar": boundary.isoformat(),
        "boundary_utc": boundary.astimezone(UTC).isoformat() if aware else None,
        "status": "instant_resolved" if aware else "floating_calendar_assumption",
        "note": ("交节表按 UTC+08 比较实际瞬间；地点时钟用于日时干支。" if aware else
                 "未提供目标时区；交节仅按输入钟面与历表比较，不能确认交节两侧的唯一盘，请补目标时区。"),
    }


def zhi_shi_position(origin: int, hour_ganzhi: str, ju_type: str) -> tuple[int, int]:
    """值使自旬首原宫沿一至九宫顺逆计数；只在数完后将中五寄坤二。"""
    if not 1 <= origin <= 9 or ju_type not in {"阳遁", "阴遁"}:
        raise ValueError("invalid 值使起宫或遁法")
    step = jiazi_index(hour_ganzhi[0], hour_ganzhi[1]) % 10
    sign = 1 if ju_type == "阳遁" else -1
    raw = (origin - 1 + sign * step) % 9 + 1
    return raw, 2 if raw == 5 else raw
