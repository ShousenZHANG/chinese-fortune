"""Rule-level examples are synthetic structures, not historical birth charts."""
from copy import deepcopy

import pytest
from bazi_reading import build_parser
from bazi_rules import (
    assess_rules,
    evaluate_condition,
    evidence_bundle,
    family_candidates,
    load_rules,
    registered_routes,
)
from classical_search import get_passage
from reading_support import review_claims
from utils import HIDDEN_STEMS


def structure(month, stems, day='甲'):
    branches = ['丑', month, '寅', '巳']
    values = [stems[0], stems[1], day, stems[2]]
    return {'hour_known': True, 'day_master': {'stem': day}, 'four_pillars': {
        key: {'stem': stem, 'branch': branch, 'ganzhi': stem + branch,
              'hidden_stems': HIDDEN_STEMS[branch]}
        for key, stem, branch in zip(('year', 'month', 'day', 'hour'), values, branches, strict=True)}}


@pytest.mark.parametrize('family,month,stems', [
    ('officer', '酉', '辛癸己'), ('wealth', '辰', '戊丙壬'),
    ('seal', '亥', '壬庚丙'), ('food', '巳', '丙戊壬'),
    ('kill', '申', '庚丙壬'), ('hurt', '午', '丁己壬'),
    ('blade', '卯', '庚壬乙'), ('salary', '寅', '丙戊庚'),
])
def test_eight_month_families_with_near_miss_and_missing_input(family, month, stems):
    chart = structure(month, stems)
    assessed = assess_rules(chart)
    assert family in {r['family_id'] for r in assessed['families']}
    routes = [r for r in assessed['routes'] if r['family_id'] == family]
    assert routes and all(r['status'] != 'supported' for r in routes)
    assert all(any(c['kind'] == 'interpretive' and c['state'] == 'unknown'
                   for c in r['conditions']) for r in routes)
    missing = deepcopy(chart)
    missing['day_master'] = {'status': 'birth_time_required'}
    assert family_candidates(missing) == []
    # A different month must not reuse the previous family's eligibility.
    different = structure('子' if family != 'seal' else '酉', '辛癸己')
    assert family not in {r['family_id'] for r in family_candidates(different)}


def test_only_yang_stems_get_the_selected_books_blade_rule():
    assert 'blade' in {r['family_id'] for r in family_candidates(structure('卯', '庚壬乙'))}
    assert 'blade' not in {r['family_id'] for r in family_candidates(structure('辰', '庚壬乙', '乙'))}


def test_absence_requires_complete_input_but_known_presence_survives_missing_hour():
    chart = structure('酉', '辛癸己')
    condition = {'id': 'food', 'label': '食神透出', 'kind': 'computed',
                 'predicate': 'exposed_any', 'roles': ['食神']}
    assert evaluate_condition(chart, condition)['state'] == 'not_met'
    chart['hour_known'] = False
    chart['four_pillars']['hour'] = {'status': '时柱待补'}
    assert evaluate_condition(chart, condition)['state'] == 'unknown'
    condition['roles'] = ['正官']
    assert evaluate_condition(chart, condition)['state'] == 'met'
    condition['predicate'] = 'exposed_none'
    assert evaluate_condition(chart, condition)['state'] == 'not_met'


def test_counterexample_blocks_the_specific_food_wealth_route():
    # 甲日丙食戊财 already exposed, but 辛官 violates the selected 财用食生 branch.
    chart = structure('辰', '戊丙辛')
    route = next(r for r in assess_rules(chart)['routes'] if r['rule_id'] == 'wealth-food')
    assert 'no_officer' in route['failed_premises']
    assert route['status'] == 'premise_not_met'
    # It is not a verdict that all 财 interpretations fail.
    assert any(r['rule_id'] == 'wealth-seal' for r in assess_rules(chart)['routes'])


def test_every_route_quote_and_exception_resolves_to_frozen_source():
    routes = [r for f in load_rules()['families'] for r in f['routes']]
    assert len(routes) == 25
    for route in routes:
        assert route['quote'] in get_passage(route['passage_id'])['text']
        for pid in route['exception_passage_ids']:
            assert get_passage(pid)['text']


def test_bundle_keeps_rescue_and_day_master_combination_exceptions_without_duplicates():
    bundle = evidence_bundle(assess_rules(structure('酉', '辛癸己')), '用神')
    ids = [p['passage_id'] for p in bundle['passages']]
    assert len(ids) == len(set(ids))
    assert {'ziping:c009:p0002', 'ziping:c009:p0003', 'ziping:c009:p0005',
            'ziping:c009:p0006', 'ziping:c005:p0004', 'ziping:c031:p0006'} <= set(ids)
    assert 'ziping:c031' in bundle['chapters']
    assert bundle['chapters']['ziping:c031']['source_url'].endswith('/3744.html')
    assert bundle['chapters']['ziping:c009']['source_url'].endswith('/3722.html')
    assert all('context' not in p and 'edition' not in p for p in bundle['passages'])


def _claim(chart, rule_id):
    route = next(r for r in assess_rules(chart)['routes'] if r['rule_id'] == rule_id)
    registry = next(r for r in registered_routes()[1] if r['id'] == rule_id)
    return {'id': rule_id, 'kind': 'traditional_interpretation', 'status': 'needs_review',
            'text': '本条条件检查', 'facts': [{'path': 'day_master.stem', 'value': '甲'}],
            'source_ids': registry['source_ids'], 'rule_id': rule_id, 'scope': 'natal',
            'conditions': {c['id']: c['state'] for c in route['conditions']}, 'exceptions': []}


def test_machine_condition_cannot_be_promoted_by_model_declaration():
    chart = structure('酉', '辛癸己')
    claim = _claim(chart, 'officer-hurt-seal')
    assert review_claims(chart, {'claims': [claim]}) == []
    claim['conditions']['hurt'] = 'met'
    assert any('computed condition mismatch' in e for e in review_claims(chart, {'claims': [claim]}))


def test_interpretive_condition_requires_real_references_but_not_semantic_certification():
    chart = structure('酉', '辛癸己')
    claim = _claim(chart, 'officer-finance-seal')
    claim['conditions']['position'] = 'met'
    assert any('explicit evidence' in e for e in review_claims(chart, {'claims': [claim]}))
    claim['condition_evidence'] = {'position': {'reason': '分析者需另核此理由是否成立',
        'facts': [{'path': 'four_pillars.year.stem', 'value': '甲'}],
        'passage_ids': ['ziping:c031:p0002']}}
    assert any('condition evidence reference' in e for e in review_claims(chart, {'claims': [claim]}))


def test_a_real_unrelated_book_heading_cannot_support_a_condition():
    chart = structure('酉', '辛癸己')
    claim = _claim(chart, 'officer-finance-seal')
    claim['conditions']['position'] = 'met'
    evidence = {'reason': '此处声称位置有效',
                'facts': [{'path': 'day_master.stem', 'value': '甲'}],
                'passage_ids': ['yuanhai:c001:p0001']}
    claim['condition_evidence'] = {'position': evidence}
    assert get_passage('yuanhai:c001:p0001')['text']
    assert any('outside the rule evidence' in e for e in review_claims(chart, {'claims': [claim]}))
    evidence['passage_ids'] = ['ziping:c031:p0002']
    assert not review_claims(chart, {'claims': [claim]})
    # Valid reference structure does not certify this reason's meaning.


@pytest.mark.parametrize('bad', [None, [], 'yes'])
def test_malformed_condition_details_fail_closed(bad):
    chart = structure('酉', '辛癸己')
    claim = _claim(chart, 'officer-finance-seal')
    claim['condition_evidence'] = bad
    assert review_claims(chart, {'claims': [claim]})


def test_default_parser_has_fixed_diagnostic_policy():
    parser = build_parser()
    for flag in ('--no-shensha', '--no-geju', '--no-yongshen'):
        assert flag not in parser.format_help()
    args = parser.parse_args(['--year', '2000', '--month', '1', '--day', '15', '--gender', 'male'])
    assert args.no_shensha and args.no_geju and args.no_yongshen


def source_chart(pillars):
    """Use the source's four symbols directly, without inventing a birth date."""
    return {'hour_known': True, 'day_master': {'stem': pillars[2][0]}, 'four_pillars': {
        key: {'stem': value[0], 'branch': value[1], 'ganzhi': value,
              'hidden_stems': HIDDEN_STEMS[value[1]]}
        for key, value in zip(('year', 'month', 'day', 'hour'), pillars, strict=True)}}


# Independent examples transcribed from each frozen paragraph, including cases
# whose operative 官/杀/伤/食 occurs in the branches rather than an exposed stem.
@pytest.mark.parametrize('rule_id,pid,pillars', [
    ('officer-finance-seal', 'ziping:c031:p0002', ['甲申', '壬申', '乙巳', '戊寅']),
    ('officer-hurt-seal', 'ziping:c031:p0004', ['己卯', '辛未', '壬寅', '辛亥']),
    ('officer-mixed', 'ziping:c031:p0005', ['庚寅', '乙酉', '甲子', '戊辰']),
    ('wealth-food', 'ziping:c033:p0004', ['壬寅', '壬寅', '庚辰', '辛巳']),
    ('wealth-seal', 'ziping:c033:p0005', ['乙未', '甲申', '丙申', '庚寅']),
    ('wealth-kill', 'ziping:c033:p0008', ['乙酉', '庚辰', '甲午', '戊辰']),
    ('seal-officer', 'ziping:c035:p0002', ['丙寅', '戊戌', '辛酉', '戊子']),
    ('seal-output', 'ziping:c035:p0003', ['戊戌', '乙卯', '丙午', '乙亥']),
    ('seal-wealth', 'ziping:c035:p0006', ['辛酉', '丙申', '壬申', '辛亥']),
    ('food-wealth', 'ziping:c037:p0002', ['丁未', '癸卯', '癸亥', '癸丑']),
    ('food-kill', 'ziping:c037:p0003', ['戊戌', '壬戌', '丙子', '戊戌']),
    ('food-kill', 'ziping:c037:p0008', ['癸酉', '辛酉', '己卯', '乙亥']),
    ('kill-food', 'ziping:c039:p0002', ['乙亥', '乙酉', '乙卯', '丁丑']),
    ('kill-seal', 'ziping:c039:p0003', ['丙寅', '戊戌', '壬戌', '辛丑']),
    ('kill-mixed', 'ziping:c039:p0006', ['癸卯', '丁巳', '庚寅', '庚辰']),
    ('hurt-wealth', 'ziping:c041:p0002', ['壬午', '己酉', '戊午', '庚申']),
    ('hurt-seal', 'ziping:c041:p0005', ['壬申', '丙午', '甲午', '壬申']),
    ('hurt-officer', 'ziping:c041:p0008', ['戊申', '甲子', '庚午', '丁丑']),
    ('blade-control', 'ziping:c043:p0004', ['甲午', '癸酉', '庚寅', '戊寅']),
    ('salary-officer', 'ziping:c045:p0002', ['丁酉', '丙午', '丁巳', '壬寅']),
    ('salary-wealth', 'ziping:c045:p0003', ['庚子', '甲申', '庚子', '甲申']),
    ('salary-kill', 'ziping:c045:p0004', ['丁巳', '壬子', '癸卯', '己未']),
    ('salary-output', 'ziping:c045:p0006', ['甲子', '丙寅', '甲子', '丙寅']),
])
def test_source_examples_are_not_blocked_by_invented_exposure_requirements(rule_id, pid, pillars):
    text = get_passage(pid)['text']
    assert all(pillar in text for pillar in pillars)
    assessed = assess_rules(source_chart(pillars))
    route = next(r for r in assessed['routes'] if r['rule_id'] == rule_id)
    assert route['failed_premises'] == [], (rule_id, route['failed_premises'])
    # Matching source examples do not certify their historical life outcomes or
    # replace review of actual chart strength, position and transformation.
    assert route['status'] == 'needs_interpretation'
    assert next(c for c in route['conditions'] if c['id'] == 'month_resolution')['state'] == 'unknown'


def test_hidden_presence_is_distinct_from_exposure_and_effectiveness():
    chart = source_chart(['庚寅', '乙酉', '甲子', '戊辰'])
    condition = {'id': 'officer', 'label': '官', 'kind': 'computed',
                 'predicate': 'exposed_any', 'roles': ['正官']}
    assert evaluate_condition(chart, condition)['state'] == 'not_met'
    condition['predicate'] = 'present_any'
    observed = evaluate_condition(chart, condition)
    assert observed['state'] == 'met'
    assert any(f.get('hidden_stem') == '辛' and f['path'] == 'four_pillars.month.branch'
               for f in observed['facts'])
    route = next(r for r in assess_rules(chart)['routes'] if r['rule_id'] == 'officer-mixed')
    assert next(c for c in route['conditions'] if c['id'] == 'remove_kill')['state'] == 'unknown'


def test_revealed_secondary_stem_cannot_erase_the_original_month_family():
    # c010:p6 explicitly preserves 官 with 乙生申月、透壬又透戊; c031:p2
    # supplies the complete original example.
    chart = source_chart(['甲申', '壬申', '乙巳', '戊寅'])
    ids = {f['family_id'] for f in family_candidates(chart)}
    assert {'officer', 'seal', 'wealth'} <= ids


def test_salary_month_does_not_hide_source_transformation_routes():
    # Structural reconstruction of c010:p4's 乙寅、透戊、会午戌 example;
    # no invented historical identity or civil date.
    chart = source_chart(['甲午', '戊寅', '乙未', '丙戌'])
    candidates = family_candidates(chart)
    assert {'salary', 'wealth', 'food', 'hurt'} <= {c['family_id'] for c in candidates}
    assert all(c['status'] == 'candidate' for c in candidates)
    assert all(r['status'] != 'supported' for r in assess_rules(chart)['routes'])


def test_incomplete_chart_cannot_prove_a_role_absent_from_storage():
    chart = source_chart(['甲寅', '甲寅', '甲寅', '甲寅'])
    condition = {'id': 'seal', 'label': '印', 'kind': 'computed',
                 'predicate': 'present_any', 'roles': ['正印', '偏印']}
    assert evaluate_condition(chart, condition)['state'] == 'not_met'
    chart['hour_known'] = False
    chart['four_pillars']['hour'] = {'status': 'birth_time_required'}
    assert evaluate_condition(chart, condition)['state'] == 'unknown'


def test_bundle_includes_transformations_and_hidden_control_exception():
    chart = source_chart(['甲午', '癸酉', '庚寅', '戊寅'])
    ids = {p['passage_id'] for p in evidence_bundle(assess_rules(chart))['passages']}
    assert {f'ziping:c010:p{i:04}' for i in range(1, 7)} <= ids
    assert {'ziping:c043:p0003', 'ziping:c043:p0005'} <= ids
    mixed = next(r for f in load_rules()['families'] for r in f['routes']
                 if r['id'] == 'officer-mixed')
    assert 'ziping:c006:p0001' not in mixed['exception_passage_ids']
    assert {'ziping:c005:p0003', 'ziping:c005:p0004', 'ziping:c005:p0005'} <= set(
        mixed['exception_passage_ids'])
