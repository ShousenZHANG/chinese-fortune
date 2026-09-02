#!/usr/bin/env python3
"""周公解梦 symbol lookup.

assets/jiemeng.json holds 105 dream symbols whose 传统 readings appear in no
reference file, so the data has to stay reachable — but reading the whole
38 KB asset to answer one question costs roughly 10k tokens. This exposes it
the way every other data asset in the project is exposed: a script that prints
one entry as JSON.

Interpretation guidance (dual 传统 + 心理 framing, what not to alarm the user
with) lives in references/15-jiemeng.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from utils import ensure_utf8_stdio, json_print

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  --symbol S    symbol category traditional modern_psychology common_scenarios
  --search Q    query count matches[]
  --categories  categories[] total_symbols

On error: {"error": ..., "message": ...} and exit 1."""


def load_symbols() -> list[dict]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "jiemeng.json"),
        os.path.join(here, "assets", "jiemeng.json"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    symbols = raw.get("symbols") if isinstance(raw, dict) else raw
    return symbols if isinstance(symbols, list) else []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="周公解梦符号查询 (传统 + 现代心理 双解)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--symbol", type=str, help="精确查一个梦境符号, 如 蛇")
    grp.add_argument("--search", type=str, help="模糊搜索符号或类别")
    grp.add_argument("--categories", action="store_true", help="列出全部类别")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    symbols = load_symbols()
    if not symbols:
        json_print({"error": "asset_missing",
                    "message": "assets/jiemeng.json 未找到或为空"})
        return 1

    if args.categories:
        cats = sorted({s.get("category", "") for s in symbols if s.get("category")})
        json_print({"categories": cats, "total_symbols": len(symbols)})
        return 0

    if args.search:
        q = args.search
        matches = [s for s in symbols
                   if q in s.get("symbol", "") or q in s.get("category", "")]
        json_print({"query": q, "count": len(matches), "matches": matches})
        return 0

    exact = next((s for s in symbols if s.get("symbol") == args.symbol), None)
    if exact:
        json_print(exact)
        return 0

    near = [s["symbol"] for s in symbols
            if any(ch in s.get("symbol", "") for ch in args.symbol)]
    json_print({
        "error": "symbol_not_found",
        "message": (f"未收录梦境符号: {args.symbol}。"
                    f"可用 --search 模糊查找, 或按 references/15-jiemeng.md 的"
                    f"分类框架解读。"),
        "suggestions": near[:10],
    })
    return 1


if __name__ == "__main__":
    sys.exit(main())
