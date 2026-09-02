"""Convert between solar (公历) and lunar (农历) calendars.

Subcommands:
    solar2lunar  --year --month --day [--hour --minute]
    lunar2solar  --year --month --day [--leap]
    today

All output is structured JSON on stdout.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from utils import ensure_utf8_stdio, json_print, require_lunar

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _serialize(solar, lunar, hour_known: bool = True) -> dict:
    """Build a uniform info dict from a Solar + Lunar pair.

    ``hour_known=False`` blanks every hour-derived field and labels it 待补.
    A 时柱 computed from an assumed clock time is a fabricated pillar:
    references/00-intake.md says 时辰未知 → 时柱缺如, 标注"时柱待补", 不揣测时辰.
    Only the two 时柱 fields depend on the hour — 日柱, 28宿 and 节气 are
    hour-invariant — so blanking them costs nothing else.
    """
    # 24 节气 (nearest jieqi)
    jieqi_info: dict = {}
    try:
        jq_today = lunar.getJieQi()
        if jq_today:
            nearest_name = jq_today
        else:
            cur = lunar.getCurrentJieQi()
            nearest_name = cur.getName() if cur else None
    except Exception:
        nearest_name = None
    try:
        prev = lunar.getPrevJieQi()
        nxt = lunar.getNextJieQi()
        jieqi_info = {
            "current_or_today": lunar.getJieQi() or None,
            "prev": {"name": prev.getName(), "solar": str(prev.getSolar())} if prev else None,
            "next": {"name": nxt.getName(), "solar": str(nxt.getSolar())} if nxt else None,
        }
    except Exception:
        jieqi_info = {"current_or_today": nearest_name}

    # 28 宿
    try:
        xiu = lunar.getXiu()
        xiu_full = f"{lunar.getXiu()}{lunar.getZheng()}{lunar.getAnimal()}"
    except Exception:
        xiu = None
        xiu_full = None

    # weekday
    try:
        wk = solar.getWeek()  # 0 = 周日, 1 = 周一, ... in lunar_python
        weekday_cn = ["星期日", "星期一", "星期二", "星期三",
                      "星期四", "星期五", "星期六"][wk]
    except Exception:
        weekday_cn = None

    return {
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
            "weekday_cn": weekday_cn,
            "iso": f"{solar.getYear():04d}-{solar.getMonth():02d}-{solar.getDay():02d}",
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(),
            "day": lunar.getDay(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
            "is_leap_month": lunar.getMonth() < 0,
            "year_in_ganzhi": lunar.getYearInGanZhi(),
            "month_in_ganzhi": lunar.getMonthInGanZhi(),
            "day_in_ganzhi": lunar.getDayInGanZhi(),
            "time_in_ganzhi": lunar.getTimeInGanZhi() if hour_known else None,
            "time_note": None if hour_known else "时辰未知, 时柱待补 (不揣测时辰)",
            "zodiac": lunar.getYearShengXiao(),
            "year_chinese": lunar.getYearInChinese(),
        },
        "ganzhi": {
            "year": lunar.getYearInGanZhi(),
            "month": lunar.getMonthInGanZhi(),
            "day": lunar.getDayInGanZhi(),
            "hour": lunar.getTimeInGanZhi() if hour_known else None,
        },
        "jieqi": jieqi_info,
        "xiu_28": {
            "xiu": xiu,
            "full": xiu_full,
        },
    }


# --------------------------------------------------------------------------- #
# Subcommand handlers
# --------------------------------------------------------------------------- #

def cmd_solar2lunar(args, Solar, Lunar) -> int:
    try:
        solar = Solar.fromYmdHms(
            args.year, args.month, args.day,
            args.hour or 0, args.minute or 0, 0,
        )
        lunar = solar.getLunar()
    except Exception as e:
        json_print({"error": "invalid_date", "message": str(e),
                    "input": vars(args)})
        return 1

    json_print({"mode": "solar2lunar", "input": vars(args),
                **_serialize(solar, lunar, hour_known=args.hour is not None)})
    return 0


def cmd_lunar2solar(args, Solar, Lunar) -> int:
    try:
        # lunar_python uses negative month for 闰月.
        m = -args.month if args.leap else args.month
        # Noon when the hour is unknown: it cannot cross a day boundary, so the
        # date conversion stays correct. The 时柱 it would imply is suppressed
        # below rather than published.
        hour = args.hour if args.hour is not None else 12
        lunar = Lunar.fromYmdHms(args.year, m, args.day, hour, 0, 0)
        solar = lunar.getSolar()
    except Exception as e:
        json_print({"error": "invalid_date", "message": str(e),
                    "input": vars(args)})
        return 1

    json_print({"mode": "lunar2solar", "input": vars(args),
                **_serialize(solar, lunar, hour_known=args.hour is not None)})
    return 0


def cmd_today(args, Solar, Lunar) -> int:
    now = datetime.now()
    solar = Solar.fromYmdHms(now.year, now.month, now.day, now.hour, now.minute, 0)
    lunar = solar.getLunar()
    json_print({"mode": "today", "now_iso": now.isoformat(),
                **_serialize(solar, lunar, hour_known=True)})
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  mode input solar_date lunar_date ganzhi jieqi xiu_28

  time_in_ganzhi / ganzhi.hour are null when --hour is omitted;
  lunar_date.time_note then reads 时柱待补 (不揣测时辰).

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="公历 / 农历 互转 / 今日万年历查询",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("solar2lunar", help="公历转农历")
    p1.add_argument("--year", type=int, required=True)
    p1.add_argument("--month", type=int, required=True)
    p1.add_argument("--day", type=int, required=True)
    p1.add_argument("--hour", type=int, default=None,
                    help="出生时 0-23; 省略则不输出时柱 (不揣测时辰)")
    p1.add_argument("--minute", type=int, default=0)

    p2 = sub.add_parser("lunar2solar", help="农历转公历")
    p2.add_argument("--year", type=int, required=True)
    p2.add_argument("--month", type=int, required=True)
    p2.add_argument("--day", type=int, required=True)
    p2.add_argument("--hour", type=int, default=None,
                    help="出生时 0-23; 省略则不输出时柱 (不揣测时辰)")
    p2.add_argument("--leap", action="store_true", help="是否闰月")

    sub.add_parser("today", help="查询今日万年历")

    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    require_lunar()
    from lunar_python import Lunar, Solar  # type: ignore

    if args.cmd == "solar2lunar":
        return cmd_solar2lunar(args, Solar, Lunar)
    if args.cmd == "lunar2solar":
        return cmd_lunar2solar(args, Solar, Lunar)
    if args.cmd == "today":
        return cmd_today(args, Solar, Lunar)
    return 2


if __name__ == "__main__":
    sys.exit(main())
