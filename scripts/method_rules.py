"""Selected Ziwei/Liuyao rules with their own frozen source paragraphs.

The reviewer validates provenance, chart references and explicit conditions.
It does not decide textual meaning or certify real-world prediction.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

RULES_PATH = Path(__file__).resolve().parents[1] / 'assets/method_rules.json'
METHODS = ('ziwei', 'liuyao')


@lru_cache(maxsize=1)
def _registry() -> dict:
    return json.loads(RULES_PATH.read_text(encoding='utf-8'))


def get_rules(method: str, rule_ids: list[str] | None = None) -> list[dict]:
    """Return only this method's rules and compact source metadata."""
    if method not in METHODS:
        raise ValueError('method must be ziwei or liuyao')
    registry = _registry()
    selected = [r for r in registry['rules'] if r['method'] == method]
    if rule_ids is not None:
        unknown = set(rule_ids) - {r['id'] for r in selected}
        if unknown:
            raise ValueError('unknown or wrong-method rule: ' + ', '.join(sorted(unknown)))
        selected = [r for r in selected if r['id'] in rule_ids]
    sources = {s['id']: s for s in registry['sources']}
    result = copy.deepcopy(selected)
    for rule in result:
        rule['sources'] = [{k: sources[sid][k] for k in (
            'id', 'title', 'section', 'source_url', 'revision', 'sha256',
            'verification', 'facsimile_status', 'scope', 'editorial_notes',
        )} for sid in rule['source_ids']]
    return result


def audit_rules(registry: dict | None = None) -> list[str]:
    """Check the finite excerpt registry, not entire books or prose truth."""
    registry = registry if registry is not None else _registry()
    errors = []
    sources = {}
    for source in registry['sources']:
        sid = source['id']
        if sid in sources:
            errors.append('duplicate source: ' + sid)
        sources[sid] = source
        digest = hashlib.sha256(source['text'].encode('utf-8')).hexdigest()
        if digest != source['sha256']:
            errors.append(sid + ': excerpt hash mismatch')
        if 'oldid=' + source['revision'] not in source['source_url']:
            errors.append(sid + ': source revision mismatch')
        if source['facsimile_status'] != 'not_checked' or source['scope'] != 'selected_paragraphs_only':
            errors.append(sid + ': unsupported verification scope')
    ids = set()
    for rule in registry['rules']:
        rid = rule['id']
        if rid in ids:
            errors.append('duplicate rule: ' + rid)
        ids.add(rid)
        if rule['method'] not in METHODS or not rid.startswith(rule['method'] + '-'):
            errors.append(rid + ': wrong method identity')
        if not rule['required_conditions'] or not rule['exceptions'] or not rule['chart_paths']:
            errors.append(rid + ': missing application conditions')
        if not rule['allowed_interpretation'] or not rule['forbidden_inferences']:
            errors.append(rid + ': missing interpretation boundary')
        for sid in rule['source_ids']:
            source = sources.get(sid)
            if source is None or not sid.startswith(rule['method'] + '-'):
                errors.append(rid + ': wrong-method source')
            elif rule['quote'] not in source['text']:
                errors.append(rid + ': quote absent from frozen excerpt')
    return errors


def _resolve(chart: dict, path: str) -> Any:
    value: Any = chart
    for part in path.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def method_reading_packet(method: str, chart: dict, *, brief: bool = False) -> dict:
    """Bind available chart facts; leave interpretation conditions unfilled."""
    if not isinstance(chart, dict):
        raise ValueError('chart must be an object')
    rules = get_rules(method)
    if brief:
        return {'schema_version': '1.0', 'method': method, 'review_scope': 'not_applied',
                'rule_ids': [rule['id'] for rule in rules],
                'lookup_command': f'python scripts/method_rules.py --method {method}',
                'note': '仅查盘面骨架；完整条款及来源按需查询，未输出条件应用记录。'}
    applications = []
    for rule in rules:
        facts, missing = [], []
        for path in rule['chart_paths']:
            try:
                facts.append({'path': path, 'value': _resolve(chart, path)})
            except (KeyError, IndexError, TypeError, ValueError):
                missing.append(path)
        conditions = dict.fromkeys(rule['required_conditions'], 'unknown')
        status = 'insufficient' if missing else 'needs_review'
        if rule['id'] == 'ziwei-ming-shen':
            leap = chart.get('input', {}).get('is_leap_month')
            if isinstance(leap, bool):
                conditions['non_leap_month'] = 'not_met' if leap else 'met'
                if leap:
                    status = 'not_applicable'
        applications.append({'rule_id': rule['id'], 'status': status,
                             'scope': rule['scope'], 'conditions': conditions,
                             'facts': facts, 'missing_paths': missing,
                             'source_ids': rule['source_ids']})
    # Full registry queries retain every field. The chart packet deduplicates
    # edition metadata and uses applications as the sole chart-path/state copy.
    editions, sources = [], []
    for rule in rules:
        for source in rule['sources']:
            edition = {k: source[k] for k in ('title', 'source_url', 'revision', 'facsimile_status')}
            if edition not in editions:
                editions.append(edition)
            sources.append({'id': source['id'], 'section': source['section'],
                            'edition': editions.index(edition)})
    brief_rules = [{k: rule[k] for k in ('id', 'quote', 'required_conditions', 'exceptions',
                                        'allowed_interpretation', 'forbidden_inferences')}
                   for rule in rules]
    return {'schema_version': '1.0', 'method': method,
            'review_scope': 'structural_only',
            'rules': brief_rules, 'sources': sources, 'editions': editions,
            'applications': applications,
            'limits': list(_registry()['limits'])}


def _computed_conditions(rule_id: str, chart: dict) -> dict[str, str]:
    """Only mechanically decidable preconditions; no strength interpretation."""
    if rule_id == 'ziwei-ming-shen':
        leap = chart.get('input', {}).get('is_leap_month')
        return {'non_leap_month': ('not_met' if leap else 'met')
                if isinstance(leap, bool) else 'unknown'}
    if rule_id == 'liuyao-shi-ying':
        main = chart.get('main_chart', {})
        shi, ying = main.get('shi_position'), main.get('ying_position')
        known = type(shi) is int and type(ying) is int and 1 <= shi <= 6 and 1 <= ying <= 6
        return {'two_between': ('met' if abs(shi - ying) == 3 else 'not_met') if known else 'unknown'}
    return {}


def review_applications(method: str, chart: dict, applications: list) -> list[str]:
    """Reject forged identities, chart facts and unfilled supported claims."""
    if not isinstance(chart, dict):
        return ['chart must be an object']
    rules = {r['id']: r for r in get_rules(method)}
    if not isinstance(applications, list) or not applications:
        return ['applications must be a nonempty list']
    errors = []
    for i, claim in enumerate(applications):
        prefix = f'application[{i}]'
        if not isinstance(claim, dict):
            errors.append(prefix + ': invalid application')
            continue
        rule = rules.get(claim.get('rule_id'))
        if rule is None:
            errors.append(prefix + ': unknown or wrong-method rule')
            continue
        if claim.get('scope') != rule['scope']:
            errors.append(prefix + ': wrong scope')
        if claim.get('status') not in ('supported', 'needs_review', 'insufficient', 'not_applicable'):
            errors.append(prefix + ': invalid status')
        source_ids = claim.get('source_ids')
        if not isinstance(source_ids, list) or set(source_ids) != set(rule['source_ids']):
            errors.append(prefix + ': wrong source evidence')
        conditions = claim.get('conditions')
        if not isinstance(conditions, dict):
            conditions = {}
        if set(conditions) != set(rule['required_conditions']):
            errors.append(prefix + ': missing or unknown conditions')
        if any(v not in ('met', 'not_met', 'unknown') for v in conditions.values()):
            errors.append(prefix + ': invalid condition value')
        if claim.get('status') == 'supported' and any(v != 'met' for v in conditions.values()):
            errors.append(prefix + ': supported application has unresolved conditions')
        computed = _computed_conditions(rule['id'], chart)
        for key, expected in computed.items():
            declared = conditions.get(key)
            if declared != 'unknown' and declared != expected:
                errors.append(prefix + ': computed condition mismatch: ' + key)
        if (rule['id'] == 'ziwei-ming-shen' and computed.get('non_leap_month') == 'not_met'
                and conditions.get('non_leap_month') != 'not_met'):
            errors.append(prefix + ': frozen rule does not cover project leap-month method')
        facts = claim.get('facts')
        if not isinstance(facts, list) or not facts:
            errors.append(prefix + ': missing chart facts')
            continue
        paths = set()
        for fact in facts:
            try:
                path = fact['path']
                if path not in rule['chart_paths'] or _resolve(chart, path) != fact['value']:
                    errors.append(prefix + ': chart fact mismatch')
                paths.add(path)
            except (KeyError, IndexError, TypeError, ValueError):
                errors.append(prefix + ': invalid chart fact')
        if claim.get('status') == 'supported' and paths != set(rule['chart_paths']):
            errors.append(prefix + ': incomplete chart facts')
        if claim.get('status') == 'supported':
            # A declaration that all conditions are met must carry reviewable
            # reasoning for each semantic condition. This checks the linkage,
            # not whether the supplied reasoning is persuasive or correct.
            evidence = claim.get('condition_evidence', {})
            if not isinstance(evidence, dict):
                evidence = {}
            for key in rule['required_conditions']:
                if key in computed:
                    continue
                detail = evidence.get(key, {})
                if not isinstance(detail, dict):
                    detail = {}
                reason = detail.get('reason')
                refs = detail.get('fact_paths')
                ids = detail.get('source_ids')
                if not isinstance(reason, str) or not reason.strip():
                    errors.append(prefix + ': missing condition reason: ' + key)
                if (not isinstance(refs, list) or not refs
                        or any(not isinstance(ref, str) or ref not in paths for ref in refs)):
                    errors.append(prefix + ': missing condition chart evidence: ' + key)
                if (not isinstance(ids, list) or not ids
                        or any(not isinstance(sid, str) or sid not in rule['source_ids'] for sid in ids)):
                    errors.append(prefix + ': missing condition source evidence: ' + key)
    return errors


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Top-level JSON keys: ok, tool, version; query: rules; chart: method, rules, applications, limits; '
        'audit/review: errors, scope, counts (audit); failure: error, message. '
        'Rule source status and unresolved conditions do not certify personal outcomes.'))
    parser.add_argument('--method', choices=METHODS)
    parser.add_argument('--rule', action='append', dest='rules')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--chart', type=Path, help='排盘 JSON 文件')
    parser.add_argument('--applications', type=Path, help='待核应用列表 JSON 文件，须同时给 --chart')
    args = parser.parse_args()
    try:
        if args.audit:
            errors = audit_rules()
            payload: dict = {'errors': errors, 'scope': 'frozen_excerpt_and_rule_schema',
                       'counts': {m: len(get_rules(m)) for m in METHODS}}
            if errors:
                json_print(error_envelope('method_rules', 'invalid_registry', '条款来源结构检查失败', **payload))
            else:
                json_print(ok_envelope('method_rules', payload))
            return int(bool(errors))
        if args.method is None:
            raise ValueError('--method is required unless --audit is used')
        if args.applications:
            if args.chart is None:
                raise ValueError('--applications requires --chart')
            chart = json.loads(args.chart.read_text(encoding='utf-8'))
            applications = json.loads(args.applications.read_text(encoding='utf-8'))
            errors = review_applications(args.method, chart, applications)
            if errors:
                json_print(error_envelope('method_rules', 'invalid_application', '条款应用结构检查失败', errors=errors))
            else:
                json_print(ok_envelope('method_rules', {'errors': [], 'scope': 'structural_only'}))
            return int(bool(errors))
        payload = method_reading_packet(args.method, json.loads(args.chart.read_text(encoding='utf-8'))) if args.chart else {'rules': get_rules(args.method, args.rules)}
        json_print(ok_envelope('method_rules', payload))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        json_print(error_envelope('method_rules', 'invalid_request', str(exc)))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
