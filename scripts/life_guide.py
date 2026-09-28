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
"""
from __future__ import annotations

import argparse
import json
from functools import cache
from pathlib import Path

from region import crosses_border, is_zone, resolve_destination, resolve_region
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

DATA_FILE = Path(__file__).resolve().parents[1] / 'assets' / 'life_guide.json'
LIMIT = 3

# Reviewed by hand against each entry's text; keyword matching finds none of
# 面试, 出行 or 开业 in any title, so it cannot be relied on.
SCENARIO_ENTRIES: dict[str, list[tuple[int, int]]] = {
    'travel': [(21, 1), (21, 2), (21, 3), (21, 4)],
    'moving': [(15, 1), (15, 3), (15, 5)],
    'interview': [(19, 3)],
    'work_conversation': [(19, 1), (19, 3), (19, 4)],
    'wedding': [(10, 9), (10, 10), (10, 11)],
    'relationship_conversation': [(10, 3), (10, 5), (10, 2)],
    'business': [(12, 1), (12, 3), (12, 7)],
    'billing': [(12, 15), (8, 18)],
    'exam': [(23, 8)],
}
# Entries that fit only part of their scenario: attached when the question
# names that part. 23:8 is about paying for a 考证 course, not 高考 or 考研.
QUESTION_WORDS: dict[tuple[int, int], tuple[str, ...]] = {(23, 8): ('考证', '证书', '资格证')}
FOREIGN_NOTE = '这是中国大陆的规定；你所在地的规定可能不同'
TODO_NOTE = '原书把这条标为待核实（TODO），按原书的规矩不能当结论用'


@cache
def _data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding='utf-8'))


@cache
def _index() -> dict[tuple[int, int], dict]:
    return {(e['section'], e['number']): e for e in _data()['entries']}


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


def _asked(key: tuple[int, int], payload: dict) -> bool:
    words = QUESTION_WORDS.get(key)
    return not words or any(w in str(payload.get('question') or '') for w in words)


def entries_for(payload: dict) -> list[dict]:
    """Entries to attach to an answer about this matter, in mapped order."""
    scenario = str((payload.get('event') or {}).get('scenario') or '')
    rows = []
    for key in SCENARIO_ENTRIES.get(scenario, []):
        entry = _index().get(key)
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
               'entries[]: section number title fields grade cost_tags todo disputed region region_note todo_note')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--scenario')
    mode.add_argument('--entry', help='节:条，例如 15:1')
    mode.add_argument('--query')
    parser.add_argument('--current-timezone')
    parser.add_argument('--event-timezone')
    parser.add_argument('--destination-timezone')
    args = parser.parse_args(argv)
    event = {k: v for k, v in {'scenario': args.scenario, 'timezone': args.event_timezone,
                               'destination_timezone': args.destination_timezone}.items() if v}
    payload = {'current_timezone': args.current_timezone, 'event': event}
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
