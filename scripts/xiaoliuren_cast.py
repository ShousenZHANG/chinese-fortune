"""小六壬 quick cast.

Usage:
    python xiaoliuren_cast.py lunar --month 3 --day 15 --hour-branch 午
    python xiaoliuren_cast.py solar --date 2026-06-01 --time 10:00
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from utils import json_print, require_lunar


PALACES = [
    {
        "name": "大安",
        "tone": "吉",
        "keywords": ["稳定", "守成", "缓成", "安定"],
        "meaning": "事情偏稳，宜守不宜急，慢中有成。",
    },
    {
        "name": "留连",
        "tone": "平",
        "keywords": ["拖延", "反复", "滞留", "信息不畅"],
        "meaning": "进展较慢，容易反复，需要补信息或耐心等待。",
    },
    {
        "name": "速喜",
        "tone": "吉",
        "keywords": ["快讯", "喜信", "顺利", "短期有利"],
        "meaning": "短期有消息或转机，适合主动推进。",
    },
    {
        "name": "赤口",
        "tone": "凶",
        "keywords": ["口舌", "争执", "误会", "冲突"],
        "meaning": "易有争执误会，先稳住沟通，不宜硬碰硬。",
    },
    {
        "name": "小吉",
        "tone": "吉",
        "keywords": ["小成", "助力", "可行", "渐进"],
        "meaning": "有小利和助力，可稳步推进，别贪大求快。",
    },
    {
        "name": "空亡",
        "tone": "凶",
        "keywords": ["落空", "虚耗", "暂缓", "不实"],
        "meaning": "当前信息虚或时机空，宜暂缓、复核、少投入。",
    },
]

HOUR_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]


def hour_branch_from_hour(hour: int) -> str:
    if hour == 23:
        return "子"
    return HOUR_BRANCHES[((hour + 1) // 2) % 12]


def cast(month: int, day: int, hour_branch: str) -> dict:
    if not 1 <= month <= 12:
        raise ValueError("lunar month must be 1..12")
    if not 1 <= day <= 30:
        raise ValueError("lunar day must be 1..30")
    if hour_branch not in HOUR_BRANCHES:
        raise ValueError("hour branch must be one of 子丑寅卯辰巳午未申酉戌亥")

    month_index = (month - 1) % 6
    day_index = (month_index + day - 1) % 6
    hour_index = HOUR_BRANCHES.index(hour_branch)
    result_index = (day_index + hour_index) % 6
    palace = PALACES[result_index]
    return {
        "method": "小六壬",
        "input": {
            "lunar_month": month,
            "lunar_day": day,
            "hour_branch": hour_branch,
        },
        "calculation": {
            "month_palace": PALACES[month_index]["name"],
            "day_palace": PALACES[day_index]["name"],
            "hour_index": hour_index + 1,
            "formula": "(month_index + day - 1 + hour_branch_index) mod 6",
        },
        "result": {
            "palace": palace["name"],
            "tone": palace["tone"],
            "keywords": palace["keywords"],
            "meaning": palace["meaning"],
        },
        "summary": f"小六壬落【{palace['name']}】, {palace['meaning']}",
        "boundary": "小六壬适合小事快占和短期参考，不作长期命运或高风险决策依据。",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小六壬起课")
    sub = parser.add_subparsers(dest="cmd", required=True)

    lunar = sub.add_parser("lunar", help="直接输入农历月日和时辰")
    lunar.add_argument("--month", type=int, required=True, help="农历月 1-12")
    lunar.add_argument("--day", type=int, required=True, help="农历日 1-30")
    lunar.add_argument("--hour-branch", required=True, choices=HOUR_BRANCHES)

    solar = sub.add_parser("solar", help="输入公历日期时间自动换算农历")
    solar.add_argument("--date", required=True, help="YYYY-MM-DD")
    solar.add_argument("--time", default="12:00", help="HH:MM")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "lunar":
            out = cast(args.month, args.day, args.hour_branch)
        elif args.cmd == "solar":
            require_lunar()
            from lunar_python import Solar  # type: ignore

            dt = datetime.strptime(f"{args.date} {args.time}", "%Y-%m-%d %H:%M")
            lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0).getLunar()
            hour_branch = hour_branch_from_hour(dt.hour)
            out = cast(lunar.getMonth(), lunar.getDay(), hour_branch)
            out["input"]["solar"] = args.date
            out["input"]["time"] = args.time
            out["input"]["lunar_year"] = lunar.getYear()
            out["input"]["lunar_month_chinese"] = lunar.getMonthInChinese()
            out["input"]["lunar_day_chinese"] = lunar.getDayInChinese()
        else:
            json_print({"error": "unknown_cmd"})
            return 1
    except ValueError as exc:
        json_print({"error": "invalid_input", "message": str(exc), "input": vars(args)})
        return 1

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
