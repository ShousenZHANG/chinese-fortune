#!/usr/bin/env python
"""Freeze a simplified-form lookup for every Han character in the library.

Search folds the frozen (traditional) text and the user's query to one form so a
simplified query reaches traditional text. That fold used to be two hand-written
strings in ``classical_search``; characters nobody had thought of were simply
unreachable, and a miss looked exactly like a subject the books never cover —
``聋哑`` returned zero while ``聾啞`` returned matches.

This is a maintenance tool, not part of the runtime. It needs ``opencc`` (see
``scripts/requirements-dev.txt``); the runtime reads only the JSON it writes, so
the shipped package keeps its two dependencies.

    python scripts/build_han_variants.py

Rewrites ``assets/han-variants.json``. Re-run after adding a book, then run
``pytest tests/test_classical_library.py`` — the gate there fails if any
character in the corpus is missing from the table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from utils import ensure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'knowledge'
TABLE = ROOT / 'assets' / 'han-variants.json'


def corpus_characters() -> set[str]:
    """Every Han character appearing anywhere in the frozen library."""
    found: set[str] = set()
    for path in sorted(LIBRARY.rglob('*.json')):
        for char in path.read_text(encoding='utf-8'):
            if unicodedata.category(char) == 'Lo' and '㐀' <= char <= '鿿':
                found.add(char)
    return found


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='生成检索用的繁简折叠表；维护工具，不进运行包',
        epilog='Writes assets/han-variants.json. Top-level JSON keys: '
               'schema_version purpose generator converter corpus_characters '
               'corpus_character_sha256 folds note mapping')
    parser.add_argument('--check', action='store_true',
                        help='只比对现有表是否仍覆盖全库，不写文件')
    args = parser.parse_args(argv)

    chars = corpus_characters()
    digest = hashlib.sha256(''.join(sorted(chars)).encode('utf-8')).hexdigest()
    if args.check:
        from opencc import OpenCC
        table = json.loads(TABLE.read_text(encoding='utf-8'))
        convert = OpenCC('t2s').convert
        regenerated = {c: convert(c) for c in chars}
        regenerated = {k: v for k, v in regenerated.items() if len(v) == 1 and v != k}
        stale = (table['corpus_characters'] != len(chars) or
                 table['corpus_character_sha256'] != digest or table['mapping'] != regenerated)
        print(f'表内 {table["corpus_characters"]} 字，库内 {len(chars)} 字：'
              + ('过期，请重新生成' if stale else '一致'))
        return 1 if stale else 0

    try:
        from opencc import OpenCC
    except ImportError:
        print('需要 opencc：pip install -r scripts/requirements-dev.txt', file=sys.stderr)
        return 2

    convert = OpenCC('t2s').convert
    # Only single-character folds belong here. A multi-character expansion would
    # change the text length and break the substring match the index relies on.
    mapping = {char: convert(char) for char in sorted(chars)}
    mapping = {k: v for k, v in mapping.items() if len(v) == 1 and v != k}

    digest = hashlib.sha256(''.join(sorted(chars)).encode('utf-8')).hexdigest()
    payload = {
        'schema_version': '1.0',
        'purpose': '检索归一：把库内繁体正文与用户查询折到同一形，使简体查询能命中繁体原文。'
                   '返回与引用仍用各版本原字，本表只用于匹配。',
        'generator': 'scripts/build_han_variants.py',
        'converter': 'opencc t2s',
        'corpus_characters': len(chars),
        'corpus_character_sha256': digest,
        'folds': len(mapping),
        'note': '多对一是检索取召回的代价（如 幹/乾 同折为 干）；匹配为整段子串 AND，'
                '宁可多召回也不可静默零命中。',
        'mapping': mapping,
    }
    TABLE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                     encoding='utf-8', newline='\n')
    print(f'{TABLE.relative_to(ROOT)}: {len(chars)} 字，{len(mapping)} 条折叠，'
          f'字集 sha256 {digest[:16]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
