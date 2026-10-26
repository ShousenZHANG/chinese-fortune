"""Literal evidence for 成败救应 and 变化; never an automatic settled 格局."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from bazi_rules import family_candidates
from utils import HIDDEN_STEMS, TIANGAN_WUXING, shi_shen

RULES_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'geju_rules.json'
PILLARS = ('year', 'month', 'day', 'hour')
KINDS = {'formation_structure': '成格条件', 'failure_structure': '败格条件',
         'taboo_structure': '成中带忌', 'rescue_structure': '败中救应',
         'transformation_clue': '变化线索', 'preserves_original': '保留本格的例式'}


@lru_cache(maxsize=1)
def load_geju_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding='utf-8'))


def _complete(chart: dict) -> bool:
    return bool(chart.get('hour_known')) and all(
        chart['four_pillars'].get(p, {}).get('stem') in TIANGAN_WUXING
        and chart['four_pillars'].get(p, {}).get('branch') in HIDDEN_STEMS for p in PILLARS)


def _locations(chart: dict, stems: list[str]) -> tuple[list[dict], list[dict]]:
    exposed, hidden = [], []
    for key in PILLARS:
        pillar = chart['four_pillars'].get(key, {})
        if key != 'day' and pillar.get('stem') in stems:
            exposed.append({'path': f'four_pillars.{key}.stem', 'value': pillar['stem']})
        for stem in HIDDEN_STEMS.get(pillar.get('branch'), []):
            if stem in stems:
                hidden.append({'path': f'four_pillars.{key}.branch', 'value': pillar['branch'], 'hidden_stem': stem})
    return exposed, hidden


def _presence(found: list, complete: bool, expected: bool = True) -> str:
    if found:
        return 'met' if expected else 'not_met'
    return ('not_met' if expected else 'met') if complete else 'unknown'


def _observe(chart: dict, condition: dict) -> dict:
    result = {'id': condition['id'], 'label': condition['source_fragment'],
              'predicate': condition['predicate'], 'state': 'unknown', 'facts': []}
    predicate = condition['predicate']
    complete = _complete(chart)
    if predicate in ('observe_exposed_stem', 'observe_stem_locations'):
        exposed, hidden = _locations(chart, [condition['stem']])
        if predicate == 'observe_exposed_stem':
            result.update(state=_presence(exposed, complete, condition.get('expected_presence', True)), facts=exposed)
        else:
            # 逢 is not automatically synonymous with the month's own storage.
            result.update(exposed=exposed, hidden=hidden, facts=exposed + hidden,
                          meaning='明干与藏干分别记录；原文“逢”的取用和作用范围未判')
    elif predicate == 'observe_month_hidden_stem':
        month = chart['four_pillars'].get('month', {})
        branch = month.get('branch')
        found = ([{'path': 'four_pillars.month.branch', 'value': branch, 'hidden_stem': condition['stem']}]
                 if condition['stem'] in HIDDEN_STEMS.get(branch, []) else [])
        result.update(state=_presence(found, branch in HIDDEN_STEMS), facts=found)
    elif predicate == 'observe_branch_group_members':
        group = condition['group']
        branches = [p.get('branch') for p in chart['four_pillars'].values()]
        present = [b for b in group if b in branches]
        missing = [b for b in group if b not in branches]
        all_seen = not missing
        # 支全 is explicit. 会午会戌 requires a separate interpretation of scope.
        state = ('met' if all_seen else 'not_met' if complete else 'unknown') if condition[
            'source_explicitly_requires_all'] else 'unknown'
        result.update(state=state, present_members=present, missing_members=missing,
                      unknown_pillars=[p for p in PILLARS if chart['four_pillars'].get(p, {}).get('branch') not in HIDDEN_STEMS],
                      all_members_observed=all_seen, meaning='只核成员，不证明会化或变格',
                      facts=[{'path': f'four_pillars.{p}.branch', 'value': chart['four_pillars'][p]['branch']}
                             for p in PILLARS if chart['four_pillars'].get(p, {}).get('branch') in group])
    elif predicate in ('observe_role_locations', 'observe_exposed_role_group'):
        groups = condition.get('role_groups', [condition.get('roles', [])])
        day = chart['day_master']['stem']
        inventories = []
        for roles in groups:
            stems = [stem for stem in TIANGAN_WUXING if shi_shen(day, stem) in roles]
            exposed, hidden = _locations(chart, stems)
            inventories.append({'roles': roles, 'exposed': exposed, 'hidden': hidden,
                                'presence_state': _presence(exposed + hidden, complete)})
        if predicate == 'observe_exposed_role_group':
            result.update(state=_presence(inventories[0]['exposed'], complete), facts=inventories[0]['exposed'])
        else:
            result.update(groups=inventories, meaning='各组分别观察；原文的“或”路线不合取，不以共现判成败')
    else:
        raise ValueError('unknown geju observation: ' + predicate)
    return result


def _literal_state(rule: dict, observations: list[dict]) -> str:
    if rule.get('family_id'):
        return 'unknown'  # Summaries with alternative clauses are not a Boolean conjunction.
    states = {o['id']: o['state'] for o in observations}
    logic = rule.get('explicit_observation_logic', {})
    if 'any' in logic:
        selected = [states[key] for key in logic['any']]
        if all(state == 'not_met' for state in selected):
            return 'not_met'
        # A partial OR does not settle a separate combination observation.
        separate = logic.get('separate_combination_observation')
        if separate and states[separate] == 'not_met':
            return 'not_met'
        if separate and states[separate] != 'met':
            return 'unknown'
        return 'met' if 'met' in selected else 'unknown' if 'unknown' in selected else 'not_met'
    selected = [states[key] for key in logic.get('all', states)]
    return 'not_met' if 'not_met' in selected else 'unknown' if 'unknown' in selected else 'met'


def assess_geju(chart: dict, registry: dict | None = None) -> dict:
    """Return independently observed conditions, original-preserving cases and sources."""
    clean = deepcopy(chart)
    if not clean.get('hour_known'):
        clean.get('four_pillars', {}).pop('hour', None)
    registry = registry or load_geju_rules()
    day = clean.get('day_master', {}).get('stem')
    month = clean.get('four_pillars', {}).get('month', {})
    result: dict = {'schema_version': '1.0', 'status': 'needs_interpretation', 'verdict': 'unresolved',
              'families': [], 'cases': [], 'source_passage_ids': [],
              'meaning': '已见事实、明确不符与未决条件分开；成败救应和变化都不能由字面形态直接定案',
              'next_step': '核月令主次与透藏，再核位置、轻重、有效制化及反例；缺出生时辰时先补资料或分别排候选盘'}
    if day not in TIANGAN_WUXING or month.get('branch') not in HIDDEN_STEMS or month.get('candidate_ganzhi'):
        result.update(status='birth_time_required', reason='日主或月令未固定，先核出生时间及交节候选盘')
        return result
    families = family_candidates(clean)
    selected = {f['family_id'] for f in families}
    cases = []
    for rule in registry['rules']:
        if rule.get('family_id'):
            if rule['family_id'] not in selected:
                continue
        elif rule.get('month') != month['branch'] or rule.get('day') not in (None, day):
            continue
        observations = [_observe(clean, c) for c in rule['conditions']]
        cases.append({**{k: rule[k] for k in ('id', 'kind', 'passage_id', 'quote')},
                      'family_id': rule.get('family_id'), 'title': KINDS[rule['kind']],
                      'status': 'needs_interpretation', 'literal_state': _literal_state(rule, observations),
                      'observations': observations, 'unresolved_conditions': deepcopy(rule['unresolved_conditions'])})
    result.update(families=families, cases=cases,
                  source_passage_ids=list(dict.fromkeys(['ziping:c009:p0001', 'ziping:c010:p0007',
                                                       *(c['passage_id'] for c in cases)])))
    return result


def geju_paragraph(review: dict) -> str:
    if review['status'] == 'birth_time_required':
        return '成败救应与变化：未判。' + review['reason'] + '。'
    changes = [c for c in review['cases'] if c['kind'] in ('transformation_clue', 'preserves_original')]
    matched = [c for c in changes if c['literal_state'] == 'met']
    text = '成败救应：已逐项列出成格、败格、成中带忌、败中救应的事实与条件；作用是否成立仍未判。'
    if matched:
        text += '字面条件已齐的例式：' + '；'.join(f"{c['title']}「{c['quote']}」（{c['passage_id']}）" for c in matched) + '。'
    elif changes:
        text += '变化或保留本格的相关例式仍有不符或未决条件，不能只看透出一字就宣布变格。'
    return text + review['next_step'] + '。'
