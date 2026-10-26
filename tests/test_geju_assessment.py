"""格局核对 reports literal evidence without promoting it to 成格/变格."""
import hashlib

import pytest
from classical_search import get_passage
from geju_assessment import assess_geju, load_geju_rules
from test_luck_assessment import _chart


def _case(result, rule_id):
    return next(r for r in result['cases'] if r['id'] == rule_id)


@pytest.mark.parametrize('rule', load_geju_rules()['rules'], ids=lambda r: r['id'])
def test_rule_quote_and_full_passage_are_independently_verifiable(rule):
    source = get_passage(rule['passage_id'])
    assert rule['quote'] in source['text']
    assert hashlib.sha256(rule['quote'].encode()).hexdigest() == rule['sha256']
    assert source['sha256'] == rule['passage_sha256']
    assert rule['unresolved_conditions']


def test_change_and_preserving_the_original_are_evaluated_together():
    chart = _chart('丙午', '甲寅', '辛亥', '壬辰')
    result = assess_geju(chart)
    assert _case(result, 'G03')['kind'] == 'transformation_clue'
    original = _case(result, 'R01')
    assert original['kind'] == 'preserves_original'
    assert original['literal_state'] == 'met'
    assert original['status'] == 'needs_interpretation'
    assert all(c['state'] == 'unknown' for c in original['unresolved_conditions'])
    assert {'wealth', 'officer'} <= {f['family_id'] for f in result['families']}
    assert {r['kind'] for r in result['cases'] if r.get('family_id') == 'wealth'} == {
        'formation_structure', 'failure_structure', 'taboo_structure', 'rescue_structure'}


def test_unknown_hour_never_proves_no_exposure_or_hides_known_presence():
    result = assess_geju(_chart('丙午', '庚寅', '辛亥', '癸卯', hour_known=False))
    observed = {o['id']: o for o in _case(result, 'G00')['observations']}
    assert observed['not_exposed_甲']['state'] == 'unknown'
    assert observed['exposed_丙']['state'] == 'met'
    assert not any('hour' in f['path'] for c in result['cases'] for o in c['observations']
                   for f in o.get('facts', []))


def test_full_three_branches_are_not_replaced_by_two_branch_retrieval():
    partial = assess_geju(_chart('辛卯', '辛亥', '丁酉', '庚子'))
    observation = _case(partial, 'G01')['observations'][0]
    assert observation['present_members'] == ['亥', '卯']
    assert observation['missing_members'] == ['未']
    assert observation['state'] == 'not_met'
    complete = assess_geju(_chart('辛卯', '辛亥', '丁酉', '丁未'))
    assert _case(complete, 'G01')['observations'][0]['state'] == 'met'
    assert _case(complete, 'G01')['status'] == 'needs_interpretation'


def test_hidden_xin_in_xu_does_not_automatically_satisfy_meeting_xin():
    result = assess_geju(_chart('甲午', '庚戌', '壬子', '丙午'))
    case = _case(result, 'G04')
    observation = case['observations'][0]
    assert observation['hidden'] and not observation['exposed']
    assert observation['state'] == 'unknown'
    assert case['literal_state'] == 'unknown'


def test_an_explicitly_absent_required_alternative_is_not_hidden_by_unknown_combination():
    review = assess_geju(_chart('乙午', '戊寅', '丙戌', '辛酉'))
    original = _case(review, 'R04')
    assert original['literal_state'] == 'not_met'
    assert original['status'] == 'needs_interpretation', '一个例式不符不能判整盘败格'


def test_each_family_has_success_failure_taboo_and_rescue_checks():
    rules = load_geju_rules()['rules']
    for family in ('officer', 'wealth', 'seal', 'food', 'kill', 'hurt', 'blade', 'salary'):
        assert {r['kind'] for r in rules if r.get('family_id') == family} == {
            'formation_structure', 'failure_structure', 'taboo_structure', 'rescue_structure'}


def test_reading_entry_point_includes_geju_and_every_referenced_source():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading, render_facts
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
        '--gender', 'male', '--as-of-year', '2026']))
    reading = prepare_reading(chart, '看格局成败和变化')
    assessment = reading['geju_review']
    ids = {p['passage_id'] for p in reading['evidence_bundle']['passages']}
    assert set(assessment['source_passage_ids']) <= ids
    assert '成败救应' in render_facts(reading)
    assert assessment['verdict'] == 'unresolved'
