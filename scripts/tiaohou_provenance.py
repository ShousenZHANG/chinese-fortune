"""Per-cell source review of the historical climate candidate table."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / 'assets/tiaohou_provenance.json'


@lru_cache(maxsize=1)
def _registry() -> dict:
    return json.loads(PROVENANCE.read_text(encoding='utf-8'))


def get_tiaohou_audit(key: str) -> dict:
    """Return review candidates, never the unreviewed historical table values.

    ``seasonal_only`` has no month-specific candidate. All other candidates
    still require the chart conditions described in ``review_note``.
    """
    cell = _registry()['cells'].get(key)
    if cell is None:
        raise ValueError(f'unknown climate cell: {key}')
    result = copy.deepcopy({k: cell[k] for k in (
        'status', 'scope', 'review_note', 'source_general_candidates',
        'source_conditional_candidates', 'source_refs', 'facsimile_status',
        'individual_application',
    )})
    result['key'] = key
    result['legacy_candidates_allowed'] = False
    if cell['status'] == 'seasonal_only':
        result['seasonal_context_candidates'] = result['source_general_candidates']
        result['source_general_candidates'] = []
        result['source_conditional_candidates'] = []
    return result


def audit_tiaohou() -> list[str]:
    """Check the location/hash contract; does not certify semantic judgment."""
    registry = _registry()
    cells = registry['cells']
    table = json.loads((ROOT / 'assets/tiaohou.json').read_text(encoding='utf-8'))
    expected = {f'{s}|{b}' for s in '甲乙丙丁戊己庚辛壬癸' for b in '寅卯辰巳午未申酉戌亥子丑'}
    errors = []
    if set(cells) != expected or set(table['tiaohou']) != expected:
        errors.append('expected exactly 120 stem/month cells')
    if registry.get('summary') != dict(Counter(c['status'] for c in cells.values())):
        errors.append('summary differs from per-cell status counts')
    passages = {}
    for n in range(2, 7):
        chapter = json.loads((ROOT / f'knowledge/books/qiongtong/c{n:03d}.json').read_text(encoding='utf-8'))
        passages.update({p['passage_id']: p for p in chapter['passages']})
    for key, cell in cells.items():
        if cell['status'] not in registry['status_definitions']:
            errors.append(key + ': unknown status')
        if not cell['source_refs'] or not cell['review_note']:
            errors.append(key + ': missing source or semantic review')
        for ref in cell['source_refs']:
            passage = passages.get(ref['passage_id'], {})
            digest = hashlib.sha256(passage.get('text', '').encode('utf-8')).hexdigest()
            if (digest != ref['sha256'] or passage.get('sha256') != ref['sha256']
                    or passage.get('section') != ref['section']):
                errors.append(key + ': frozen passage mismatch: ' + ref['passage_id'])
        for field in ('source_general_candidates', 'source_conditional_candidates'):
            if any(s not in '甲乙丙丁戊己庚辛壬癸' or len(s) != 1 for s in cell[field]):
                errors.append(key + ': invalid candidate stem')
        old = table['tiaohou'].get(key, {})
        if (cell['legacy_candidates']['primary'] != old.get('primary_yongshen')
                or cell['legacy_candidates']['secondary'] != old.get('secondary_yongshen')):
            errors.append(key + ': historical candidate table changed without review')
        if 'verified_against_source' in old or 'source_clause' in old:
            errors.append(key + ': obsolete blanket verification remains')
        if old.get('source_status') != cell['status']:
            errors.append(key + ': table and review status differ')
    return errors


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Top-level JSON keys: ok, tool, version; query: review; audit: errors, summary, scope; '
        'failure: error, message. review contains status, source_general_candidates, '
        'source_conditional_candidates, source_refs, review_note, facsimile_status.'))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--key', help='日干|月支, e.g. 甲|未')
    group.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    try:
        if args.audit:
            errors = audit_tiaohou()
            payload = {'errors': errors, 'summary': dict(Counter(c['status'] for c in _registry()['cells'].values())),
                       'scope': 'source_locations_and_review_schema'}
            if errors:
                json_print(error_envelope('tiaohou_provenance', 'invalid_registry', '调候条款来源检查失败', **payload))
            else:
                json_print({'ok': True, 'tool': 'tiaohou_provenance', 'version': __version__, **payload})
            return int(bool(errors))
        result = get_tiaohou_audit(args.key)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        json_print(error_envelope('tiaohou_provenance', 'invalid_request', str(exc)))
        return 1
    json_print({'ok': True, 'tool': 'tiaohou_provenance', 'version': __version__, 'review': result})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
