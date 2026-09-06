"""Evaluate observable premises and retrieve complete classical rule evidence.

Interpretive premises remain unknown until an explicitly evidenced review.
The module never turns a matched label into a personal prediction.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from classical_search import get_passage
from utils import HIDDEN_STEMS, TIANGAN_WUXING, shi_shen

RULES_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'bazi_rules.json'
PILLARS = ('year', 'month', 'day', 'hour')
BLADE_MONTH = {'甲': '卯', '丙': '午', '戊': '午', '庚': '酉', '壬': '子'}


def load_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding='utf-8'))


def _pillars(chart: dict) -> dict:
    return chart.get('four_pillars', {})


def _complete(chart: dict) -> bool:
    return bool(chart.get('hour_known')) and all(
        _pillars(chart).get(p, {}).get('stem') and _pillars(chart).get(p, {}).get('branch')
        for p in PILLARS)


def _exposed(chart: dict, roles: list[str]) -> list[dict]:
    day = chart.get('day_master', {}).get('stem')
    if day not in TIANGAN_WUXING:
        return []
    return [{'path': f'four_pillars.{key}.stem', 'value': p['stem']}
            for key, p in _pillars(chart).items()
            if key != 'day' and p.get('stem') in TIANGAN_WUXING
            and shi_shen(day, p['stem']) in roles]


def _present(chart: dict, roles: list[str]) -> list[dict]:
    """Observe a role in exposed stems or branch storage, without calling it effective."""
    day = chart.get('day_master', {}).get('stem')
    if day not in TIANGAN_WUXING:
        return []
    facts = _exposed(chart, roles)
    for key, pillar in _pillars(chart).items():
        branch = pillar.get('branch')
        for stem in HIDDEN_STEMS.get(branch, []):
            if shi_shen(day, stem) in roles:
                facts.append({'path': f'four_pillars.{key}.branch', 'value': branch,
                              'hidden_stem': stem,
                              'meaning': '本支藏干可见；有效根气、透干或合化另核'})
    return facts


def family_candidates(chart: dict, registry: dict | None = None) -> list[dict]:
    """Retain the month baseline alongside possible exposure/combination changes.

    A candidate is a retrieval route, never an automatically settled 格局. A
    revealed secondary stem must not erase the original month family: c010:p6
    explicitly records transformations which still preserve the original 格.
    """
    registry = registry or load_rules()
    day = chart.get('day_master', {}).get('stem')
    month = _pillars(chart).get('month', {})
    branch = month.get('branch')
    if day not in TIANGAN_WUXING or branch not in HIDDEN_STEMS:
        return []
    hidden = HIDDEN_STEMS[branch]
    exposed = {f['value'] for family in registry['families']
               for f in _exposed(chart, family['roles'])}
    blade = BLADE_MONTH.get(day) == branch
    same_month = shi_shen(day, hidden[0]) in ('比肩', '劫财')
    # These are clues to examine, including partial combinations seen in the
    # source examples. Mere simultaneous presence never proves transformation.
    observed_branches = {p.get('branch') for p in _pillars(chart).values()}
    combinations = [(group, element) for group, element in
                    [('亥卯未', '木'), ('寅午戌', '火'), ('巳酉丑', '金'), ('申子辰', '水')]
                    if branch in group and len(set(group) & observed_branches) >= 2]
    candidates = []
    for family in registry['families']:
        fid = family['id']
        bases = []
        if fid == 'blade':
            if blade:
                bases.append('月令阳刃专章')
        elif fid == 'salary':
            if same_month and not blade:
                bases.append('月令建禄月劫专章')
        else:
            if not same_month and shi_shen(day, hidden[0]) in family['roles']:
                bases.append('月令本气；是否变化或仍存本格待核')
            if any(shi_shen(day, stem) in family['roles'] and stem in exposed for stem in hidden):
                bases.append('月藏干透出；不自动排除本气或专章')
            for group, element in combinations:
                if any(shi_shen(day, stem) in family['roles'] for stem, wx in TIANGAN_WUXING.items()
                       if wx == element):
                    bases.append(f'{group}会支线索；只是检索候选，合化未定')
        if bases:
            candidates.append({'family_id': fid, 'title': family['title'],
                               'basis': '；'.join(bases),
                               'facts': [{'path': 'day_master.stem', 'value': day},
                                         {'path': 'four_pillars.month.branch', 'value': branch}],
                               'status': 'candidate',
                               'limit': '先核月令主次、透藏、会支和变化能否成立；不得把候选当定格'})
    return candidates


def evaluate_condition(chart: dict, condition: dict) -> dict:
    """Return three-state evidence; a missing hour cannot prove absence."""
    result: dict[str, Any] = {k: condition[k] for k in ('id', 'label', 'kind')}
    result.update(state='unknown', facts=[])
    if condition['kind'] != 'computed':
        return result
    predicate = condition.get('predicate')
    if predicate == 'full_chart':
        result['state'] = 'met' if _complete(chart) else 'not_met'
        result['facts'] = [{'path': 'hour_known', 'value': chart.get('hour_known')}]
    elif predicate in ('exposed_any', 'exposed_none', 'present_any'):
        day = chart.get('day_master', {}).get('stem')
        if day not in TIANGAN_WUXING:
            return result
        found = (_present(chart, condition['roles']) if predicate == 'present_any'
                 else _exposed(chart, condition['roles']))
        if found:
            result['state'] = 'met' if predicate != 'exposed_none' else 'not_met'
            result['facts'] = [{'path': 'day_master.stem', 'value': day}, *found]
        elif _complete(chart):
            result['state'] = 'not_met' if predicate != 'exposed_none' else 'met'
            result['facts'] = [{'path': 'day_master.stem', 'value': day}, *[
                {'path': f'four_pillars.{p}.stem', 'value': _pillars(chart)[p]['stem']}
                for p in PILLARS if p != 'day']]
            if predicate == 'present_any':
                result['facts'].extend({'path': f'four_pillars.{p}.branch',
                                        'value': _pillars(chart)[p]['branch']} for p in PILLARS)
    else:
        raise ValueError('unknown rule predicate: ' + str(predicate))
    return result


def assess_rules(chart: dict, registry: dict | None = None) -> dict:
    registry = registry or load_rules()
    candidates = family_candidates(chart, registry)
    selected = {f['family_id'] for f in candidates}
    routes = []
    for family in registry['families']:
        if family['id'] not in selected:
            continue
        for route in family['routes']:
            conditions = [evaluate_condition(chart, c) for c in route['conditions']]
            blocked = [c['id'] for c in conditions if c['state'] == 'not_met']
            routes.append({'rule_id': route['id'], 'family_id': family['id'],
                           'title': route['title'], 'status': 'premise_not_met' if blocked else 'needs_interpretation',
                           'conditions': conditions, 'failed_premises': blocked,
                           'passage_id': route['passage_id'],
                           'exception_passage_ids': route['exception_passage_ids'],
                           'family_resolution': '月令候选尚须原文复核，不由前提齐全自动定格',
                           'scope': route['scope']})
    return {'schema_version': '1.0', 'families': candidates, 'routes': routes,
            'meaning': '程序核实可计算前提；未核解释条件保持unknown，不等于格局已成立'}


def _evidence_ids(assessment: dict, question: str = '',
                  extra_passage_ids: list[str] | None = None) -> list[str]:
    """One source boundary shared by retrieval and condition review."""
    registry = load_rules()
    ids = list(registry['common_passage_ids'])
    ids.extend(extra_passage_ids or [])
    selected = {family['family_id'] for family in assessment['families']}
    ids.extend(f"ziping:{family['chapter']}:p0001" for family in registry['families']
               if family['id'] in selected)
    for route in assessment['routes']:
        ids.extend([route['passage_id'], *route['exception_passage_ids']])
    ids.extend(f'ziping:c005:p{i:04}' for i in range(1, 7))
    ids.extend(['ziping:c006:p0002', 'ziping:c006:p0003'])
    if any(word in question for word in ('调候', '寒暖', '用神', '五行')):
        ids.extend(f'ziping:c014:p{i:04}' for i in range(1, 8))
    families = {f['family_id'] for f in assessment['families']}
    if 'hurt' in families or 'officer' in families:
        ids.extend(['ditian:c006:p0007', 'ditian:c006:p0008'])
    return list(dict.fromkeys(ids))


def evidence_bundle(assessment: dict, question: str = '', *, getter: Any = None,
                    extra_passage_ids: list[str] | None = None) -> dict:
    """Deduplicate passages, preserving all referenced conditions and exceptions."""
    getter = getter or get_passage
    books: dict[str, dict] = {}
    chapters: dict[str, dict] = {}
    passages = []
    for pid in _evidence_ids(assessment, question, extra_passage_ids):
        p = getter(pid)
        bid = p['book_id']
        cid = bid + ':' + p['chapter_id']
        books.setdefault(bid, {k: p[k] for k in
                              ('book_title', 'edition', 'license', 'transcription_status', 'facsimile_status')})
        chapters.setdefault(cid, {k: p[k] for k in ('chapter_title', 'source_url', 'revision')})
        passages.append({k: p[k] for k in ('passage_id', 'section', 'layer', 'text', 'issues')})
    return {'schema_version': '2.0', 'books': books, 'chapters': chapters, 'passages': passages,
            'scope': '本次规则所需完整段落及例外；书章信息复用，原文字句未删减'}


@lru_cache(maxsize=1)
def registered_routes() -> tuple[list[dict], list[dict]]:
    """Adapt executable routes to the shared claim review interface."""
    sources: dict[str, dict] = {}
    rules = []
    for family in load_rules()['families']:
        evidence_ids = _evidence_ids({'families': [{'family_id': family['id']}],
                                     'routes': family['routes']}, '用神')
        for route in family['routes']:
            pid = route['passage_id']
            source_id = 'passage:' + pid
            p = get_passage(pid)
            if route['quote'] not in p['text']:
                raise ValueError('rule quote absent from source: ' + route['id'])
            sources[source_id] = {'id': source_id, 'title': p['book_title'], 'quote': p['text'],
                                  'chapter': p['chapter_title'],
                                  'passage_id': pid, 'layer': p['layer'],
                                  'verification': 'transcription_checked', 'url': p['source_url']}
            rules.append({'id': route['id'], 'scope': 'natal', 'family_id': family['id'],
                          'source_ids': [source_id], 'evaluation': 'bazi_rules_v1',
                          'condition_passage_ids': evidence_ids,
                          'required_conditions': [c['id'] for c in route['conditions']],
                          'condition_definitions': route['conditions']})
    return list(sources.values()), rules


def review_computed_conditions(chart: dict, claim: dict, rule: dict) -> list[str]:
    errors = []
    candidates = {r['family_id'] for r in family_candidates(chart)}
    if rule['family_id'] not in candidates:
        errors.append('rule family is not supported by month evidence')
    declared = claim.get('conditions', {})
    if not isinstance(declared, dict):
        return [*errors, 'invalid declared conditions']
    details = claim.get('condition_evidence', {})
    if not isinstance(details, dict):
        return [*errors, 'invalid condition evidence']
    allowed_passages = set(rule['condition_passage_ids'])
    stem = chart.get('day_master', {}).get('stem')
    month = chart.get('four_pillars', {}).get('month', {}).get('branch')
    if stem and month:
        from tiaohou_provenance import get_tiaohou_audit
        for source in get_tiaohou_audit(stem + '|' + month)['source_refs']:
            paragraph = get_passage(source['passage_id'])
            allowed_passages.add(paragraph['passage_id'])
            allowed_passages.update(p['passage_id'] for p in paragraph['context'])
    for condition in rule['condition_definitions']:
        actual = evaluate_condition(chart, condition)
        if condition['kind'] == 'computed' and declared.get(condition['id']) != actual['state']:
            errors.append('computed condition mismatch: ' + condition['id'])
        if condition['kind'] == 'interpretive' and declared.get(condition['id']) != 'unknown':
            evidence = details.get(condition['id'], {})
            if (not isinstance(evidence, dict) or not isinstance(evidence.get('reason'), str)
                    or not evidence['reason'].strip() or not isinstance(evidence.get('facts'), list)
                    or not evidence['facts'] or not isinstance(evidence.get('passage_ids'), list)
                    or not evidence['passage_ids']):
                errors.append('interpretive condition requires explicit evidence: ' + condition['id'])
            elif any(pid not in allowed_passages for pid in evidence['passage_ids']):
                errors.append('condition source is outside the rule evidence: ' + condition['id'])
    return errors
