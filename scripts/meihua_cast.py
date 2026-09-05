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

from utils import (
    BAGUA,
    BINARY_TO_TRIGRAM,
    WUXING_GEN,
    WUXING_KE,
    XIANTIAN_NUM_TO_TRIGRAM,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    parse_datetime_arg,
    shichen_number,
)
from yijing_cast import (
    changed_lines,
    hex_lookup_by_trigrams,
    line_visual,
    lines_to_trigrams,
    load_hex_assets,
    nuclear_lines,
)


# 时辰 number: 子=1 .. 亥=12 (used for 起卦)
def shichen_num(hour: int) -> int:
    return shichen_number(hour)


# Build 6 raw line values from upper/lower trigram + a 1..6 changing line.
def build_lines(upper_tri: str, lower_tri: str, change_line: int) -> list[int]:
    upper_bin = BAGUA[upper_tri]["binary"]
    lower_bin = BAGUA[lower_tri]["binary"]
    lines: list[int] = []
    # BAGUA["binary"] is top-to-bottom, so 初爻 is bit 2 (see yijing_cast).
    for i in range(3):
        lines.append(7 if (lower_bin >> (2 - i)) & 1 else 8)
    for i in range(3):
        lines.append(7 if (upper_bin >> (2 - i)) & 1 else 8)
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


# 体卦旺衰 — 按月令五行。
#
# 土王四季: 辰未戌丑四个季末月土旺 (严格说是每季末 18 天), 对应公历约 4/7/10/1 月。
# 这四个月从前被并进了木/火/金/水, 于是 SEASON_WX_BY_MONTH 十二个月里没有一个是
# 土, `.get(month, "土")` 的默认分支对任何合法月份都不可达 —— 体卦为 艮 或 坤
# (五行属土) 时, ti_state 结构性地永远拿不到「旺」, 八个卦里有两个的旺衰判断被
# 系统性压低, 而输出照样把它当确定结论交给用户。
#
# 月粒度模型必须在「辰月算木还是算土」之间二选一; 这里取通行的四季月归土, 与本
# 文件原有注释声明的意图一致, references/05-meihua.md §5.2 已同步对齐。
# 真正的 18 天分界需要节气, 本引擎不提供 —— 输出的 body_strength 因此在
# package() 里带 granularity 标注, 供解读时如实说明其精度。
SEASON_WX_BY_MONTH: dict[int, str] = {
    # 公历月 -> 当令五行 (对应 寅卯/巳午/申酉/亥子 四组 + 辰未戌丑 四季月)
    2: "木", 3: "木",
    5: "火", 6: "火",
    8: "金", 9: "金",
    11: "水", 12: "水",
    4: "土", 7: "土", 10: "土", 1: "土",
}


def ti_state(ti_tri: str, month: int) -> str:
    ti_wx = BAGUA[ti_tri]["wuxing"]
    season_wx = SEASON_WX_BY_MONTH[month]
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


def package(cast_meta: dict, question: str | None, month: int) -> dict:
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
            # 旺衰按 公历月 粗略取值。土王四季严格说是每季末 18 天, 定 18 天分界
            # 需要节气, 本引擎不提供 —— 落在月初/月末的盘可能实际处在相邻状态。
            "body_strength_granularity": "月令粗略 (未按节气细分, 四季月整月作土)",
        },
        "summary": "; ".join(summary_parts),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  method now_iso ymd shichen upper_num lower_num change_num upper_tri
  lower_tri question raw_lines changing_line main_hex changed_hex
  nuclear_hex ti_yong summary

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="梅花易数起卦 (时间/数字/字数)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Top-level, not on `time` alone: 当下月令 feeds 体用旺衰 for every method.
    p.add_argument("--datetime", dest="dt", type=str, default=None,
                   help="ISO 时间 (如 2026-06-24T13:05), 默认当下; 用于可复现起卦")
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


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        now = parse_datetime_arg(args.dt)
    except ValueError as e:
        json_print(error_envelope('meihua', "bad_datetime", str(e)))
        return 1

    if args.method == "time":
        meta = cast_by_time(now)
    elif args.method == "numbers":
        meta = cast_by_numbers(args.upper, args.lower)
    elif args.method == "name":
        meta = cast_by_text(args.text)
    else:
        json_print(error_envelope('meihua', "unknown_method", '输入无效'))
        return 2

    out = package(meta, args.question, now.month)
    json_print(ok_envelope("meihua", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
