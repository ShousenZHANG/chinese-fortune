"""Mechanical checks of recorded answers: each case's own checks plus the format rules.

A pass here is the floor, not a review: it says the answer contains what a
correct one must and none of what it must not. Content is judged separately.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DISCLAIMERS = ('仅供参考', '仅作参考', '不构成', '娱乐参考', '文化参考')
NOT_PROSE = re.compile(r'^\s*(\||```|#|---|\*\*\*|>)')


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), '')


def check(case: dict, record: dict, run: Path) -> dict:
    folder = run / case['id']
    answer = (folder / f"answer-{len(record['turns'])}.txt").read_text(encoding='utf-8') if record['turns'] else ''
    commands = ' '.join(str(t.get('command') or '') for turn in record['turns'] for t in turn.get('tools', []))
    first = _first_line(answer)
    rules = case.get('checks', {})
    found: list[dict] = []

    def add(name: str, passed: bool, detail: str = '') -> None:
        found.append({'check': name, 'passed': passed, 'detail': detail})
    add('complete', record['complete'])
    add('first_line_is_prose', bool(first) and not NOT_PROSE.match(first), first[:60])
    add('one_disclaimer_at_most', sum(answer.count(d) for d in DISCLAIMERS) <= 1)
    for words in [rules['contains_any']] if 'contains_any' in rules else []:
        add('contains_any', any(w in answer for w in words), '/'.join(words))
    for word in rules.get('not_contains', []):
        add(f'not_contains:{word}', word not in answer)
    if 'first_line_any' in rules:
        add('first_line_any', any(w in first for w in rules['first_line_any']), first[:60])
    if 'tool_any' in rules:
        add('tool_any', any(w in commands for w in rules['tool_any']), '/'.join(rules['tool_any']))
    usage = [(t.get('result') or {}) for t in record['attempts']]
    return {'id': case['id'], 'group': case['id'][0], 'passed': all(c['passed'] for c in found), 'checks': found,
            'chars': len(answer), 'tool_calls': sum(len(t.get('tools', [])) for t in record['turns']),
            'cost_usd': round(sum(u.get('total_cost_usd') or 0 for u in usage), 4),
            'attempts': len(record['attempts']),
            'output_tokens': sum((u.get('usage') or {}).get('output_tokens') or 0 for u in usage),
            'input_tokens': sum(sum((u.get('usage') or {}).get(k) or 0 for k in
                                    ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
                                for u in usage)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = {c['id']: c for c in json.loads(args.cases.read_text(encoding='utf-8'))['cases']}
    results = []
    for folder in sorted(p for p in args.run.iterdir() if (p / 'record.json').exists()):
        record = json.loads((folder / 'record.json').read_text(encoding='utf-8'))
        results.append(check(cases[record['id']], record, args.run))
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(r['group'], []).append(r)
    summary = {'cases': len(results), 'passed': sum(r['passed'] for r in results),
               'cost_usd': round(sum(r['cost_usd'] for r in results), 2),
               'groups': {g: {'cases': len(rs), 'passed': sum(r['passed'] for r in rs)} for g, rs in sorted(groups.items())},
               'failed_checks': [{'id': r['id'], 'failed': [c for c in r['checks'] if not c['passed']]}
                                 for r in results if not r['passed']],
               'results': results}
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"{summary['passed']}/{summary['cases']} passed the mechanical checks; ${summary['cost_usd']}")
    for row in summary['failed_checks']:
        print(row['id'], [c['check'] for c in row['failed']])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
