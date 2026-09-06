"""Evaluate recorded model answers; never mistake a case list for model execution.

Input: {model, prompt_version, responses: [{case_id, text, tool_calls,
chart?, packet?, review: {reviewer, criteria: {criterion: pass|fail}, notes}}]}.
Missing answers or semantic reviews fail acceptance; raw model transcripts are
provided by the host, not synthesized by this checker.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reading_support import review_claims  # noqa: E402


def evaluate(spec: dict, recording: dict) -> dict:
    if not isinstance(recording, dict):
        return {'ok': False, 'errors': ['recording must be an object'], 'pending': []}
    errors: list[str] = []
    pending: list[str] = []
    rows = recording.get('responses', [])
    if not isinstance(rows, list):
        rows = []
        errors.append('responses must be a list')
    by_id: dict[str, dict] = {}
    known = {c['id'] for c in spec['cases']}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('case_id'), str):
            errors.append('invalid response record')
            continue
        cid = row['case_id']
        if cid not in known or cid in by_id:
            errors.append(f'{cid}: unknown or duplicate case')
        by_id[cid] = row
    if not recording.get('model') or not recording.get('prompt_version'):
        errors.append('model and prompt_version are required')
    reviewed = 0
    dispositions = dict.fromkeys(('answered', 'partial', 'deferred'), 0)
    for case in spec['cases']:
        cid = case['id']
        row = by_id.get(cid)
        if not row or not isinstance(row.get('text'), str) or not row['text'].strip():
            pending.append(cid + ': no actual answer')
            continue
        if not isinstance(row.get('tool_calls'), list):
            errors.append(cid + ': missing tool trace (empty list allowed when no tool needed)')
        if case.get('requires_chart') and (
                not row.get('tool_calls') or not isinstance(row.get('chart'), dict)
                or not row.get('chart', {}).get('ok') or not isinstance(row.get('packet'), dict)):
            errors.append(cid + ': this case requires an actual successful chart, packet and tool trace')
        if 'chart' in row or 'packet' in row:
            if not isinstance(row.get('chart'), dict) or not isinstance(row.get('packet'), dict):
                errors.append(cid + ': chart and packet required together')
            else:
                errors.extend(cid + ': ' + e for e in review_claims(row['chart'], row['packet']))
        review = row.get('review')
        if not isinstance(review, dict) or not review.get('reviewer') or not review.get('notes'):
            pending.append(cid + ': semantic review missing')
            continue
        disposition = review.get('disposition')
        if not isinstance(disposition, str) or disposition not in dispositions:
            pending.append(cid + ': answer disposition missing')
            continue
        dispositions[disposition] += 1
        criteria = review.get('criteria', {})
        if not isinstance(criteria, dict) or any(criteria.get(k) not in ('pass', 'fail') for k in spec['criteria']):
            pending.append(cid + ': incomplete semantic rubric')
            continue
        reviewed += 1
        errors.extend(cid + ': failed ' + k for k in spec['criteria'] if criteria[k] == 'fail')
    return {'ok': not errors and not pending, 'cases': len(spec['cases']),
            'answers': sum(bool(r.get('text')) for r in by_id.values()),
            'reviewed': reviewed, 'errors': errors, 'pending': pending,
            'answer_dispositions': dispositions,
            'limitation': 'Checks recorded reviews; does not independently verify their honesty or predictive validity.'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Score actual model recordings against the reading rubric')
    parser.add_argument('--responses', required=True)
    args = parser.parse_args()
    try:
        spec = json.loads((ROOT / 'evals/reading_cases.json').read_text(encoding='utf-8'))
        recording = json.loads(Path(args.responses).read_text(encoding='utf-8'))
        result = evaluate(spec, recording)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {'ok': False, 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
