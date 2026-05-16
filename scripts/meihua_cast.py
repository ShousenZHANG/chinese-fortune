"""梅花易数 (Plum Blossom Numerology).

Subcommands:
    time                                  — 年月日时起卦
    numbers --upper N --lower N           — 二数起卦 (no explicit change line)
    name --text 中文                      — 字数起卦

Output includes 主卦, 变卦, 互卦, 体卦/用卦/体用关系 (生/克/比和) and a brief
体卦旺衰 estimate based on the current solar season.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from utils import (
    BAGUA,
    BINARY_TO_TRIGRAM,
    XIANTIAN_NUM_TO_TRIGRAM,
    WUXING_GEN,
    WUXING_KE,
    json_print,
    warn,
)

from yijing_cast import (
    line_visual, lines_to_trigrams, hex_lookup_by_trigrams,
    nuclear_lines, changed_lines, load_hex_assets,
)


# 时辰 number: 子=1 .. 亥=12 (used for 起卦)
def shichen_num(hour: int) -> int:
    if hour == 23 or hour == 0:
        return 1
    return ((hour + 1) // 2) + 1


# Build 6 raw line values from upper/lower trigram + a 1..6 changing line.
def build_lines(upper_tri: str, lower_tri: str, change_line: int) -> list[int]:
    upper_bin = BAGUA[upper_tri]["binary"]
    lower_bin = BAGUA[lower_tri]["binary"]
    lines: list[int] = []
    for i in range(3):
        lines.append(7 if (lower_bin >> i) & 1 else 8)
    for i in range(3):
        lines.append(7 if (upper_bin >> i) & 1 else 8)
    idx = change_line - 1
    lines[idx] = 9 if lines[idx] == 7 else 6
    return lines


# 体用关系: which trigram contains the 动爻 (changing line) is 用; the other is 体.
def ti_yong(upper_tri: str, lower_tri: str, change_line: int) -> tuple[str, str]:
    if 1 <= change_line <= 3:
        return upper_tri, lower_tri  # 体 = upper, 用 = lower (动在下)
    return lower_tri, upper_tri      # 体 = lower, 用 = upper (动在上)


# Relation between two trigrams' 五行: 生我 (生体), 我生 (体生), 比和, 克我 (克体), 我克 (体克)
def ti_yong_relation(ti_tri: str, yong_tri: str) -> str:
    ti_wx = BAGUA[ti_tri]["wuxing"]
    yong_wx = BAGUA[yong_tri]["wuxing"]
    if ti_wx == yong_wx:
        return "比和"
    if WUXING_GEN.get(yong_wx) == ti_wx:
        return "用生体 (吉)"
    if WUXING_GEN.get(ti_wx) == yong_wx:
        return "体生用 (耗体)"
    if WUXING_KE.get(yong_wx) == ti_wx:
        return "用克体 (凶)"
    if WUXING_KE.get(ti_wx) == yong_wx:
        return "体克用 (吉)"
    return "未知"


# 体卦旺衰 — based on current month (季节五行)
SEASON_WX_BY_MONTH: dict[int, str] = {
    # 公历月 -> 当令五行 (粗略对应)
    2: "木", 3: "木", 4: "木",
    5: "火", 6: "火", 7: "火",
    8: "金", 9: "金", 10: "金",
    11: "水", 12: "水", 1: "水",
}

# 土王四季: 每季末 18 天土旺. For simplicity, treat months 4/7/10/1 with secondary
# 土相 flag.

def ti_state(ti_tri: str, month: int) -> str:
    ti_wx = BAGUA[ti_tri]["wuxing"]
    season_wx = SEASON_WX_BY_MONTH.get(month, "土")
    if ti_wx == season_wx:
        return "旺"
    if WUXING_GEN.get(season_wx) == ti_wx:
        return "相"
    if WUXING_GEN.get(ti_wx) == season_wx:
        return "休"
    if WUXING_KE.get(ti_wx) == season_wx:
        return "囚"
    if WUXING_KE.get(season_wx) == ti_wx:
        return "死"
    return "?"


# --------------------------------------------------------------------------- #
# Cast methods
# --------------------------------------------------------------------------- #

def cast_by_time(now: datetime) -> dict:
    y, m, d = now.year, now.month, now.day
    sc = shichen_num(now.hour)
    upper_num = ((y + m + d) % 8) or 8
    lower_num = ((y + m + d + sc) % 8) or 8
    change = ((y + m + d + sc) % 6) or 6
    return {
        "method": "time",
        "now_iso": now.isoformat(),
        "ymd": [y, m, d],
        "shichen": sc,
        "upper_num": upper_num, "lower_num": lower_num, "change_num": change,
        "upper_tri": XIANTIAN_NUM_TO_TRIGRAM[upper_num],
        "lower_tri": XIANTIAN_NUM_TO_TRIGRAM[lower_num],
    }


def cast_by_numbers(upper: int, lower: int) -> dict:
    upper_n = ((upper - 1) % 8) + 1
    lower_n = ((lower - 1) % 8) + 1
    total = upper + lower
    change = ((total - 1) % 6) + 1
    return {
        "method": "numbers",
        "upper_num": upper_n, "lower_num": lower_n, "change_num": change,
        "input_total": total,
        "upper_tri": XIANTIAN_NUM_TO_TRIGRAM[upper_n],
        "lower_tri": XIANTIAN_NUM_TO_TRIGRAM[lower_n],
    }


def cast_by_text(text: str) -> dict:
    s = "".join(ch for ch in text if not ch.isspace())
    n = len(s)
    half = n // 2
    upper_n = (half % 8) or 8
    lower_n = ((n - half) % 8) or 8
    change = (n % 6) or 6
    return {
        "method": "name",
        "text": text,
        "text_len": n,
        "upper_num": upper_n, "lower_num": lower_n, "change_num": change,
        "upper_tri": XIANTIAN_NUM_TO_TRIGRAM[upper_n],
        "lower_tri": XIANTIAN_NUM_TO_TRIGRAM[lower_n],
    }


# --------------------------------------------------------------------------- #
# Pack output
# --------------------------------------------------------------------------- #

def hex_info(lines: list[int], assets: dict[int, dict]) -> dict:
    upper_bin, lower_bin = lines_to_trigrams(lines)
    num, name = hex_lookup_by_trigrams(upper_bin, lower_bin)
    a = assets.get(num, {})
    return {
        "number": num, "name": name,
        "upper_trigram": BINARY_TO_TRIGRAM.get(upper_bin),
        "lower_trigram": BINARY_TO_TRIGRAM.get(lower_bin),
        "lines": [{"position": i + 1, "value": v, "visual": line_visual(v)}
                  for i, v in enumerate(lines)],
        "judgment": a.get("judgment", "(暂无)"),
    }


def package(cast_meta: dict, question: Optional[str], month: int) -> dict:
    upper_tri = cast_meta["upper_tri"]
    lower_tri = cast_meta["lower_tri"]
    change = cast_meta["change_num"]
    lines = build_lines(upper_tri, lower_tri, change)

    ti_t, yong_t = ti_yong(upper_tri, lower_tri, change)
    relation = ti_yong_relation(ti_t, yong_t)
    state = ti_state(ti_t, month)

    assets = load_hex_assets()
    main_h = hex_info(lines, assets)
    changed_h = hex_info(changed_lines(lines), assets)
    nuclear_h = hex_info(nuclear_lines(lines), assets)

    summary_parts = [
        f"主卦【{main_h['name']}】",
        f"动爻第{change}爻",
        f"变卦【{changed_h['name']}】",
        f"互卦【{nuclear_h['name']}】",
        f"体卦{ti_t}({BAGUA[ti_t]['wuxing']}), 用卦{yong_t}({BAGUA[yong_t]['wuxing']})",
        f"体用: {relation}",
        f"体卦当季: {state}",
    ]

    return {
        **cast_meta,
        "question": question,
        "raw_lines": lines,
        "changing_line": change,
        "main_hex": main_h,
        "changed_hex": changed_h,
        "nuclear_hex": nuclear_h,
        "ti_yong": {
            "body_trigram": ti_t,
            "use_trigram": yong_t,
            "body_wuxing": BAGUA[ti_t]["wuxing"],
            "use_wuxing": BAGUA[yong_t]["wuxing"],
            "relation": relation,
            "body_strength": state,
        },
        "summary": "; ".join(summary_parts),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="梅花易数起卦 (时间/数字/字数)")
    sub = p.add_subparsers(dest="method", required=True)

    pt = sub.add_parser("time", help="年月日时起卦")
    pt.add_argument("--question", type=str, default=None)

    pn = sub.add_parser("numbers", help="两数起卦")
    pn.add_argument("--upper", type=int, required=True)
    pn.add_argument("--lower", type=int, required=True)
    pn.add_argument("--question", type=str, default=None)

    px = sub.add_parser("name", help="字数起卦")
    px.add_argument("--text", type=str, required=True)
    px.add_argument("--question", type=str, default=None)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now()

    if args.method == "time":
        meta = cast_by_time(now)
    elif args.method == "numbers":
        meta = cast_by_numbers(args.upper, args.lower)
    elif args.method == "name":
        meta = cast_by_text(args.text)
    else:
        json_print({"error": "unknown_method"})
        return 2

    out = package(meta, args.question, now.month)
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
