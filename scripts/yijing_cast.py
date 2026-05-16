"""I-Ching (周易) divination casting.

Subcommands:
    coins                                  — 3-coin × 6 throws
    numbers --upper N --lower N --change N — build from 3 numbers
    time                                   — cast by current time
    text --text 中文                       — cast by string length (字数起卦)

Each method produces line values (6/7/8/9), main + changed hexagram, nuclear
hexagram (互卦), and judgments loaded from ``assets/64hex.json`` (with an
embedded fallback table of just hex names if the asset file is missing).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from typing import Optional

from utils import (
    BAGUA,
    BINARY_TO_TRIGRAM,
    XIANTIAN_NUM_TO_TRIGRAM,
    json_print,
    warn,
)


# --------------------------------------------------------------------------- #
# 64 卦 — embedded fallback table (just names + king-wen number)
# Order: King Wen ordering (传统次序).
# Bottom trigram bits in low 3 bits, upper in high 3 bits.
# --------------------------------------------------------------------------- #

KING_WEN_ORDER: list[tuple[int, str, int, int]] = [
    # (number, name, upper_binary, lower_binary)
    (1,  "乾为天",       0b111, 0b111),
    (2,  "坤为地",       0b000, 0b000),
    (3,  "水雷屯",       0b010, 0b100),
    (4,  "山水蒙",       0b001, 0b010),
    (5,  "水天需",       0b010, 0b111),
    (6,  "天水讼",       0b111, 0b010),
    (7,  "地水师",       0b000, 0b010),
    (8,  "水地比",       0b010, 0b000),
    (9,  "风天小畜",     0b011, 0b111),
    (10, "天泽履",       0b111, 0b110),
    (11, "地天泰",       0b000, 0b111),
    (12, "天地否",       0b111, 0b000),
    (13, "天火同人",     0b111, 0b101),
    (14, "火天大有",     0b101, 0b111),
    (15, "地山谦",       0b000, 0b001),
    (16, "雷地豫",       0b100, 0b000),
    (17, "泽雷随",       0b110, 0b100),
    (18, "山风蛊",       0b001, 0b011),
    (19, "地泽临",       0b000, 0b110),
    (20, "风地观",       0b011, 0b000),
    (21, "火雷噬嗑",     0b101, 0b100),
    (22, "山火贲",       0b001, 0b101),
    (23, "山地剥",       0b001, 0b000),
    (24, "地雷复",       0b000, 0b100),
    (25, "天雷无妄",     0b111, 0b100),
    (26, "山天大畜",     0b001, 0b111),
    (27, "山雷颐",       0b001, 0b100),
    (28, "泽风大过",     0b110, 0b011),
    (29, "坎为水",       0b010, 0b010),
    (30, "离为火",       0b101, 0b101),
    (31, "泽山咸",       0b110, 0b001),
    (32, "雷风恒",       0b100, 0b011),
    (33, "天山遁",       0b111, 0b001),
    (34, "雷天大壮",     0b100, 0b111),
    (35, "火地晋",       0b101, 0b000),
    (36, "地火明夷",     0b000, 0b101),
    (37, "风火家人",     0b011, 0b101),
    (38, "火泽睽",       0b101, 0b110),
    (39, "水山蹇",       0b010, 0b001),
    (40, "雷水解",       0b100, 0b010),
    (41, "山泽损",       0b001, 0b110),
    (42, "风雷益",       0b011, 0b100),
    (43, "泽天夬",       0b110, 0b111),
    (44, "天风姤",       0b111, 0b011),
    (45, "泽地萃",       0b110, 0b000),
    (46, "地风升",       0b000, 0b011),
    (47, "泽水困",       0b110, 0b010),
    (48, "水风井",       0b010, 0b011),
    (49, "泽火革",       0b110, 0b101),
    (50, "火风鼎",       0b101, 0b011),
    (51, "震为雷",       0b100, 0b100),
    (52, "艮为山",       0b001, 0b001),
    (53, "风山渐",       0b011, 0b001),
    (54, "雷泽归妹",     0b100, 0b110),
    (55, "雷火丰",       0b100, 0b101),
    (56, "火山旅",       0b101, 0b001),
    (57, "巽为风",       0b011, 0b011),
    (58, "兑为泽",       0b110, 0b110),
    (59, "风水涣",       0b011, 0b010),
    (60, "水泽节",       0b010, 0b110),
    (61, "风泽中孚",     0b011, 0b110),
    (62, "雷山小过",     0b100, 0b001),
    (63, "水火既济",     0b010, 0b101),
    (64, "火水未济",     0b101, 0b010),
]


def hex_lookup_by_trigrams(upper_bin: int, lower_bin: int) -> tuple[int, str]:
    """Look up Kingwen #, name by (upper_binary, lower_binary)."""
    for n, name, u, l in KING_WEN_ORDER:
        if u == upper_bin and l == lower_bin:
            return n, name
    return 0, "未知卦"


# --------------------------------------------------------------------------- #
# Hex assets loading
# --------------------------------------------------------------------------- #

def load_hex_assets() -> dict[int, dict]:
    """Load ``assets/64hex.json`` if available; otherwise minimal fallback.

    Expected schema for each hex entry::

        {"name": "...", "judgment": "...", "image": "...",
         "lines": ["初九 ...", "九二 ...", ...]}

    Detailed commentary should be read from references/64hex-full.md when needed.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "64hex.json"),
        os.path.join(here, "assets", "64hex.json"),
    ]
    asset = next((p for p in candidates if os.path.exists(p)), None)
    if asset:
        try:
            with open(asset, "r", encoding="utf-8") as f:
                raw = json.load(f)
            hexagrams = raw.get("hexagrams") if isinstance(raw, dict) else raw
            if isinstance(hexagrams, list):
                table: dict[int, dict] = {}
                for h in hexagrams:
                    n = int(h["number"])
                    lines_raw = h.get("lines", [])
                    lines_str = [
                        f"{ln.get('type','')}{['初','二','三','四','五','上'][ln.get('position',1)-1]}: {ln.get('text','')}"
                        if isinstance(ln, dict) else str(ln)
                        for ln in lines_raw
                    ]
                    table[n] = {
                        "name": h.get("name_zh") or h.get("name"),
                        "name_en": h.get("name_en"),
                        "judgment": h.get("judgment", ""),
                        "image": h.get("image", ""),
                        "lines": lines_str,
                        "lines_raw": lines_raw,
                        "summary": h.get("summary_zh") or h.get("summary", ""),
                    }
                return table
            if isinstance(raw, dict):
                return {int(k): v for k, v in raw.items() if str(k).isdigit()}
        except Exception as e:
            warn(f"failed to load 64hex.json: {e}")

    # fallback: just names
    fallback: dict[int, dict] = {}
    for n, name, u, l in KING_WEN_ORDER:
        fallback[n] = {
            "name": name,
            "judgment": "(暂无卦辞, 请在 assets/64hex.json 中补充)",
            "image": "(暂无象辞)",
            "lines": [f"第{i+1}爻: (暂无爻辞)" for i in range(6)],
        }
    return fallback


# --------------------------------------------------------------------------- #
# Coin tossing
# --------------------------------------------------------------------------- #
# Convention: heads = 3 (阳/yang), tails = 2 (阴/yin)
# Sum of 3 coins -> line value:
#   6: 老阴 (动)  -- 2+2+2 = 6
#   7: 少阳       -- 3+2+2 = 7 (one head)
#   8: 少阴       -- 3+3+2 = 8 (two heads)
#   9: 老阳 (动)  -- 3+3+3 = 9

def cast_coins(rng: random.Random) -> list[int]:
    """Return list of 6 line values bottom-to-top."""
    lines: list[int] = []
    for _ in range(6):
        total = sum(rng.choice([2, 3]) for _ in range(3))
        lines.append(total)
    return lines


# --------------------------------------------------------------------------- #
# Numbers method (梅花/Plum-Blossom)
# upper, lower in 1..8, changing_line in 1..6 (1=bottom)
# --------------------------------------------------------------------------- #

def from_numbers(upper: int, lower: int, change: int) -> list[int]:
    upper = ((upper - 1) % 8) + 1
    lower = ((lower - 1) % 8) + 1
    change = ((change - 1) % 6) + 1
    upper_tri = XIANTIAN_NUM_TO_TRIGRAM[upper]
    lower_tri = XIANTIAN_NUM_TO_TRIGRAM[lower]

    # Build 6 lines bottom -> top, using static 7/8 then set the changing line.
    upper_bin = BAGUA[upper_tri]["binary"]
    lower_bin = BAGUA[lower_tri]["binary"]
    lines: list[int] = []
    # lower trigram: bits low-to-high are line 1,2,3 (bottom-to-top)
    for i in range(3):
        bit = (lower_bin >> i) & 1
        lines.append(7 if bit == 1 else 8)
    for i in range(3):
        bit = (upper_bin >> i) & 1
        lines.append(7 if bit == 1 else 8)
    # apply changing line: convert static -> moving (7 -> 9, 8 -> 6)
    idx = change - 1
    if lines[idx] == 7:
        lines[idx] = 9
    else:
        lines[idx] = 6
    return lines


# --------------------------------------------------------------------------- #
# Time method
# --------------------------------------------------------------------------- #

# 时辰 mapping for 时 column: 子时=1, 丑=2, ..., 亥=12
def shichen_index(hour: int) -> int:
    # 子 23-1, 丑 1-3, ..., 亥 21-23
    if hour == 23 or hour == 0:
        return 1
    return ((hour + 1) // 2) + 1


def from_time(now: datetime) -> tuple[list[int], dict]:
    # year/month/day numbers
    # 用农历更传统, 但简化: 直接使用公历值作 plum-blossom 数 (常见简化)
    y = now.year
    m = now.month
    d = now.day
    sc = shichen_index(now.hour)

    upper = ((y + m + d) % 8) or 8
    lower = ((y + m + d + sc) % 8) or 8
    change = ((y + m + d + sc) % 6) or 6
    lines = from_numbers(upper, lower, change)
    meta = {"upper_num": upper, "lower_num": lower, "change_num": change,
            "shichen": sc, "ymd": [y, m, d]}
    return lines, meta


# --------------------------------------------------------------------------- #
# Text method — by 字数
# --------------------------------------------------------------------------- #

def from_text(text: str) -> tuple[list[int], dict]:
    # remove whitespace, count characters
    s = "".join(ch for ch in text if not ch.isspace())
    n = len(s)
    half = n // 2
    upper = (half % 8) or 8
    lower = ((n - half) % 8) or 8
    change = (n % 6) or 6
    lines = from_numbers(upper, lower, change)
    meta = {"text_len": n, "upper_num": upper, "lower_num": lower,
            "change_num": change}
    return lines, meta


# --------------------------------------------------------------------------- #
# Build hex info from line values
# --------------------------------------------------------------------------- #

def line_visual(v: int) -> str:
    # 6 (老阴): ━ ━ x   (changing yin)
    # 7 (少阳): ━━━
    # 8 (少阴): ━ ━
    # 9 (老阳): ━━━ o   (changing yang)
    if v == 6:
        return "━  ━  ✕"
    if v == 7:
        return "━━━━━"
    if v == 8:
        return "━  ━"
    if v == 9:
        return "━━━━━  ○"
    return "?"


def lines_to_trigrams(lines: list[int]) -> tuple[int, int]:
    """Return (upper_bin, lower_bin), where each bit pattern represents lines
    bottom-to-top (bit 0 = bottom of the trigram)."""
    lower_bin = 0
    for i in range(3):
        if lines[i] in (7, 9):  # yang
            lower_bin |= 1 << i
    upper_bin = 0
    for i in range(3):
        if lines[3 + i] in (7, 9):
            upper_bin |= 1 << i
    return upper_bin, lower_bin


def changed_lines(lines: list[int]) -> list[int]:
    """Return new line values after applying 老阴/老阳 transforms."""
    out: list[int] = []
    for v in lines:
        if v == 6:
            out.append(7)  # 老阴变少阳
        elif v == 9:
            out.append(8)  # 老阳变少阴
        else:
            out.append(v)
    return out


def nuclear_lines(lines: list[int]) -> list[int]:
    """Compute 互卦 lines (use yin/yang only, ignore changing markers)."""
    yy = [1 if v in (7, 9) else 0 for v in lines]
    # 互卦: 下卦 = 2,3,4 爻; 上卦 = 3,4,5 爻
    new_yy = [yy[1], yy[2], yy[3], yy[2], yy[3], yy[4]]
    return [7 if b == 1 else 8 for b in new_yy]


def hex_info(lines: list[int], assets: dict[int, dict]) -> dict:
    upper_bin, lower_bin = lines_to_trigrams(lines)
    num, name = hex_lookup_by_trigrams(upper_bin, lower_bin)
    a = assets.get(num, {})
    return {
        "number": num,
        "name": name,
        "upper_trigram": BINARY_TO_TRIGRAM.get(upper_bin),
        "lower_trigram": BINARY_TO_TRIGRAM.get(lower_bin),
        "lines": [{"position": i + 1, "value": v, "visual": line_visual(v)}
                  for i, v in enumerate(lines)],
        "lines_visual": "\n".join(line_visual(v) for v in reversed(lines)),
        "judgment": a.get("judgment", "(暂无)"),
        "image": a.get("image", "(暂无)"),
    }


def active_lines(lines: list[int]) -> list[int]:
    return [i + 1 for i, v in enumerate(lines) if v in (6, 9)]


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="周易/六十四卦起卦")
    sub = p.add_subparsers(dest="method", required=True)

    pc = sub.add_parser("coins", help="三枚硬币 6 次")
    pc.add_argument("--seed", type=int, default=None, help="可选随机种子")
    pc.add_argument("--question", type=str, default=None)

    pn = sub.add_parser("numbers", help="三数起卦 (上/下/动爻)")
    pn.add_argument("--upper", type=int, required=True)
    pn.add_argument("--lower", type=int, required=True)
    pn.add_argument("--change", type=int, required=True)
    pn.add_argument("--question", type=str, default=None)

    pt = sub.add_parser("time", help="当下时间起卦")
    pt.add_argument("--question", type=str, default=None)

    px = sub.add_parser("text", help="字数起卦")
    px.add_argument("--text", type=str, required=True)
    px.add_argument("--question", type=str, default=None)

    return p


def summarize(method: str, main: dict, changed: Optional[dict],
              actives: list[int]) -> str:
    if changed is None or not actives:
        return f"得本卦【{main['name']}】, 无动爻, 应以卦辞为主。"
    return (f"本卦【{main['name']}】, 动爻{actives}, "
            f"变卦【{changed['name']}】; 应综合卦辞与动爻爻辞参断。")


def cast(method: str, lines: list[int], meta: dict,
         question: Optional[str]) -> dict:
    assets = load_hex_assets()
    actives = active_lines(lines)
    main = hex_info(lines, assets)
    changed: Optional[dict] = None
    if actives:
        new_lines = changed_lines(lines)
        changed = hex_info(new_lines, assets)
    nuclear = hex_info(nuclear_lines(lines), assets)

    # Active line texts
    active_line_text: list[dict] = []
    for pos in actives:
        a = assets.get(main["number"], {})
        text = a.get("lines", [])
        line_str = text[pos - 1] if pos - 1 < len(text) else "(暂无爻辞)"
        active_line_text.append({"position": pos, "text": line_str})

    return {
        "method": method,
        "question": question,
        "meta": meta,
        "raw_lines": lines,
        "main_hex": main,
        "changed_hex": changed,
        "nuclear_hex": nuclear,
        "active_lines": actives,
        "active_line_text": active_line_text,
        "summary": summarize(method, main, changed, actives),
    }


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.method == "coins":
        rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
        lines = cast_coins(rng)
        meta = {"seed": args.seed}
        out = cast("coins", lines, meta, args.question)
    elif args.method == "numbers":
        lines = from_numbers(args.upper, args.lower, args.change)
        meta = {"upper_num": args.upper, "lower_num": args.lower,
                "change_num": args.change}
        out = cast("numbers", lines, meta, args.question)
    elif args.method == "time":
        now = datetime.now()
        lines, meta = from_time(now)
        meta["now_iso"] = now.isoformat()
        out = cast("time", lines, meta, args.question)
    elif args.method == "text":
        lines, meta = from_text(args.text)
        meta["text"] = args.text
        out = cast("text", lines, meta, args.question)
    else:
        json_print({"error": "unknown_method"})
        return 2

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
