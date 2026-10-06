"""大运取运判断：审定数据与判断逻辑（spec docs/superpowers/specs/2026-10-06-luck-assessment-design.md）。"""
import json
from pathlib import Path

import pytest
from classical_search import get_passage

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / 'assets' / 'luck_rules.json').read_text(encoding='utf-8'))
ROLES = {'比肩', '劫财', '食神', '伤官', '偏财', '正财', '七杀', '正官', '偏印', '正印'}
VERDICTS = {'favoured', 'avoided', 'harmless', 'unpromising'}
PREDICATES = {'present_any', 'exposed_any', 'exposed_none', 'combines', 'exposed_count_at_least'}


def _scenarios():
    return [s for f in RULES['families'] for s in f['scenarios']]


def _effects(s):
    return s.get('effects', []) + [e for b in s.get('branches', []) for e in b['effects']]


def test_only_the_first_batch_is_connected():
    assert [f['family_id'] for f in RULES['families']] == ['officer', 'wealth', 'hurt']
    assert [f['chapter'] for f in RULES['families']] == ['ziping:c032', 'ziping:c034', 'ziping:c042']


@pytest.mark.parametrize('scenario', _scenarios(), ids=lambda s: s['id'])
def test_every_quote_is_the_frozen_text_and_every_verdict_is_in_it(scenario):
    passage = get_passage(scenario['passage_id'])
    assert passage['sha256'] == scenario['sha256']
    assert scenario['quote'] in passage['text']
    for effect in _effects(scenario):
        assert effect['verdict'] in VERDICTS
        assert effect['words'] in scenario['quote'], (scenario['id'], effect['words'])
        assert set(effect.get('roles', [])) <= ROLES and set(effect.get('combines_natal', [])) <= ROLES
        assert effect.get('roles') or effect.get('combines_natal')
    for premise in scenario['premises'] + [b for b in scenario.get('branches', []) if b.get('predicate')]:
        assert premise['predicate'] in PREDICATES
        assert set(premise.get('roles', [])) <= ROLES and set(premise.get('with', [])) <= ROLES
    for branch in scenario.get('branches', []):
        assert branch['kind'] in ('computed', 'interpretive')
        assert branch['kind'] == 'interpretive' or branch.get('predicate')


def test_every_luck_paragraph_of_the_three_chapters_has_a_scenario():
    """All but each chapter's general remarks (c032 p0001 p0007, c034 p0001, c042 p0001)."""
    used = {s['passage_id'] for s in _scenarios()}
    expected = ({f'ziping:c032:p{i:04}' for i in range(2, 7)} | {f'ziping:c034:p{i:04}' for i in range(2, 9)}
                | {f'ziping:c042:p{i:04}' for i in range(2, 8)})
    assert used == expected


@pytest.mark.parametrize('note', RULES['notes'], ids=lambda n: n['id'])
def test_every_general_note_is_the_frozen_text(note):
    passage = get_passage(note['passage_id'])
    assert passage['sha256'] == note['sha256'] and note['quote'] in passage['text']
