#!/usr/bin/env python
"""Real-world references from the frozen 《高性价比人生指南》, gated by region.

Attached only after a divination answer, in its own section, never used to
rank dates or colours. An entry is attached when it is mapped to the matter,
is not marked TODO (the book's own rule: do not use those as conclusions),
and applies where the matter takes place — see ``region.py``. At most three.

    python scripts/life_guide.py --scenario travel --current-timezone Australia/Sydney \\
        --destination-timezone Asia/Singapore
    python scripts/life_guide.py --entry 15:1 --current-timezone Australia/Sydney
    python scripts/life_guide.py --query 押金 --current-timezone Australia/Sydney
    python scripts/life_guide.py --article marriage --current-timezone Asia/Shanghai
"""
from __future__ import annotations

import argparse
import json
import re
from functools import cache
from pathlib import Path

from region import crosses_border, is_zone, resolve_destination, resolve_region
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

DATA_FILE = Path(__file__).resolve().parents[1] / 'assets' / 'life_guide.json'
LIMIT = 3

# Reviewed by hand against each entry's text; keyword matching finds none of
# 面试, 出行 or 开业 in any title, so it cannot be relied on. A string names
# one of the book's long articles. Entries in QUESTION_PATTERNS fit only
# part of the matter and come first, so the limit does not cut them when the
# question does ask about that part.
Ref = tuple[int, int] | str
SCENARIO_ENTRIES: dict[str, list[Ref]] = {
    'travel': [(13, 33), (13, 35), (21, 1), (21, 2), (21, 3), (21, 4)],
    'moving': [(15, 1), (15, 3), (15, 5)],
    'interview': [(31, 14), (31, 7), (19, 3)],
    'work_conversation': [(31, 15), (19, 1), (19, 3), (19, 4)],
    'wedding': ['marriage', (10, 9), (10, 10), (10, 11)],
    'relationship_conversation': [(10, 3), (10, 5), (10, 2)],
    # 合婚 is a specialist workflow with no fortune_reading answer to ride
    # after; its own flow calls ``--scenario compatibility``. 10:1 and 10:4
    # say compatibility cannot be predicted beforehand, a verdict on the
    # method itself, so they are not attached to it.
    'compatibility': ['marriage', (10, 18), (10, 17)],
    'business': [(12, 1), (12, 3), (12, 7)],
    'billing': [(9, 15), (12, 15), (8, 18)],
    'exam': [(23, 8), (31, 7)],
}
# Entries that fit only part of their scenario: attached when the question
# names that part. 23:8 is about paying for a 考证 course, not 高考 or 考研;
# 准考证 is an exam ticket and 毕业证书 a diploma, neither a course to pay for.
QUESTION_PATTERNS: dict[tuple[int, int], re.Pattern] = {
    (23, 8): re.compile(r'(?<!准)考证|考个证|资格证|职业证书|技能证书|证书培训'),
    (13, 33): re.compile(r'高原|西藏|拉萨|青藏|海拔|川西|稻城|珠峰'),
    (13, 35): re.compile(r'野外|徒步|露营|户外|登山|爬山'),
    (31, 14): re.compile(r'出国打工|劳务|海外工作|出国工作|境外工作'),
    (31, 7): re.compile(r'考公|公务员|考编|事业编|体制内'),
    (31, 15): re.compile(r'境外公司|外国公司|海外公司|远程'),
    (9, 15): re.compile(r'催款|要债|讨债|追债|欠款|欠钱|讨薪'),
}
FOREIGN_NOTE = '中国大陆口径：你所在地的规定、机构和电话可能不同'
TODO_NOTE = '原书把这条标为待核实（TODO），按原书的规矩不能当结论用'


@cache
def _data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding='utf-8'))


@cache
def _index() -> dict[tuple[int, int], dict]:
    return {(e['section'], e['number']): e for e in _data()['entries']}


@cache
def _articles() -> dict[str, dict]:
    """Long articles, shaped like entries for the gate and the renderer."""
    return {a['id']: {**a, 'kind': 'article', 'todo': False, 'disputed': False, 'dispute': None}
            for a in _data().get('articles', [])}


def _lookup(ref: Ref) -> dict | None:
    return _articles().get(ref) if isinstance(ref, str) else _index().get(ref)


def library_source() -> dict:
    """Where the frozen text comes from, for citing beside the references."""
    source = _data()['source']
    return {k: source[k] for k in ('repo', 'commit', 'snapshot_date', 'license')}


def _applies(entry: dict, payload: dict) -> bool:
    if entry['region'] == '通用':
        return True
    if entry['region'] == '中国公民在境外':
        # Advice for leaving the country: a trip abroad that crosses a border,
        # not Sydney to Melbourne.
        return resolve_destination(payload) == '境外' and crosses_border(payload)
    return resolve_region(payload)['region'] == entry['region']


def _asked(key: Ref, payload: dict) -> bool:
    pattern = QUESTION_PATTERNS.get(key) if isinstance(key, tuple) else None
    return not pattern or bool(pattern.search(str(payload.get('question') or '')))


def entries_for(payload: dict) -> list[dict]:
    """Entries (and articles) to attach to an answer about this matter, in mapped order."""
    scenario = str((payload.get('event') or {}).get('scenario') or '')
    rows = []
    for key in SCENARIO_ENTRIES.get(scenario, []):
        entry = _lookup(key)
        if entry and not entry['todo'] and _applies(entry, payload) and _asked(key, payload):
            rows.append(entry)
    return rows[:LIMIT]


def _annotated(entry: dict, payload: dict) -> dict:
    """A copy saying when the rules are not the user's, or the book doubts it."""
    row = dict(entry)
    if entry['region'] == '中国大陆' and resolve_region(payload)['region'] != '中国大陆':
        row['region_note'] = FOREIGN_NOTE
    if entry['todo']:
        row['todo_note'] = TODO_NOTE
    return row


def get_entry(section: int, number: int, payload: dict) -> dict | None:
    """One entry on explicit request, noting when its rules are not the user's."""
    entry = _index().get((section, number))
    return None if entry is None else _annotated(entry, payload)


def get_article(key: str, payload: dict) -> dict | None:
    """A long article, whole, with the same region note."""
    article = _articles().get(key)
    return None if article is None else _annotated(article, payload)


def search(query: str, payload: dict | None = None, limit: int = 5) -> list[dict]:
    """Whole entries whose title or text contains every word of the query.

    TODO entries are left out, as in ``entries_for``: a search is how the
    host answers a practical question, and the book says not to conclude
    from those. Each hit carries the same notes as an explicit lookup.
    """
    words = [w for w in query.split() if w]
    if not words:
        return []
    hits = [e for e in _data()['entries'] if not e['todo']
            and all(w in e['title'] or any(w in v for v in e['fields'].values()) for w in words)]
    return [_annotated(e, payload or {}) for e in hits[:limit]]


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='按事项与地区取《高性价比人生指南》的现实参考条目（整条原文，不参与术数排序）',
        epilog='Top-level JSON keys: ok tool version source region entries. '
               'entries[]: section number title fields grade cost_tags todo disputed dispute region region_note '
               'todo_note; an article row has kind id path title text region instead of section/number/fields')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--scenario')
    mode.add_argument('--entry', help='节:条，例如 15:1')
    mode.add_argument('--query')
    mode.add_argument('--article', help='长文编号，例如 marriage')
    parser.add_argument('--current-timezone')
    parser.add_argument('--event-timezone')
    parser.add_argument('--destination-timezone')
    parser.add_argument('--question', help='用户原话；只适合一部分问法的条目要靠它判断')
    args = parser.parse_args(argv)
    event = {k: v for k, v in {'scenario': args.scenario, 'timezone': args.event_timezone,
                               'destination_timezone': args.destination_timezone}.items() if v}
    payload = {'current_timezone': args.current_timezone, 'event': event, 'question': args.question}
    try:
        # An unknown zone name must not quietly count as 境外.
        for zone in (args.current_timezone, args.event_timezone, args.destination_timezone):
            if zone and not is_zone(zone):
                raise ValueError(f'不是 IANA 时区名：{zone!r}（例如 Australia/Sydney）')
        if args.entry:
            parts = args.entry.split(':')
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError('--entry 须为「节:条」，例如 15:1')
            found = get_entry(int(parts[0]), int(parts[1]), payload)
            if found is None:
                raise ValueError(f'本库没有第 {parts[0]} 节第 {parts[1]} 条')
            rows = [found]
        elif args.query:
            rows = search(args.query, payload)
        elif args.article:
            article = get_article(args.article, payload)
            if article is None:
                raise ValueError(f'本库没有长文 {args.article!r}')
            rows = [article]
        else:
            rows = entries_for(payload)
    except (ValueError, OSError) as exc:
        json_print(error_envelope('life_guide', 'invalid_input', str(exc)))
        return 1
    source = _data()['source']
    json_print(ok_envelope('life_guide', {
        'source': {k: source[k] for k in ('repo', 'commit', 'snapshot_date', 'license')},
        'region': resolve_region(payload), 'entries': rows}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
