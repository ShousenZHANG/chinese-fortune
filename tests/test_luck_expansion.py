"""Source-backed regressions for all five newly connected luck chapters."""
import pytest
from luck_assessment import assess_luck, luck_paragraph
from test_luck_assessment import _chart


@pytest.mark.parametrize('family,pillars,expected', [
    ('seal', ('辛酉', '癸子', '甲寅', '庚申'),
     ['seal-officer-heavy', 'seal-officer-output', 'seal-output', 'seal-kill', 'seal-kill-output', 'seal-wealth', 'seal-mixed']),
    ('food', ('庚申', '甲寅', '壬辰', '丙午'),
     ['food-wealth', 'food-kill-seal', 'food-kill', 'food-heavy-seal', 'food-seal-wealth-rescue']),
    ('kill', ('癸卯', '庚申', '甲戌', '丙午'),
     ['kill-food', 'kill-seal', 'kill-hurt', 'kill-wealth-preserve-food', 'kill-wealth-support-insufficient', 'kill-mixed', 'kill-blade']),
    ('blade', ('庚申', '丁卯', '甲辰', '辛酉'), ['blade-officer', 'blade-kill', 'blade-mixed']),
    ('salary', ('辛酉', '甲寅', '甲子', '庚午'),
     ['salary-officer-seal', 'salary-officer-wealth', 'salary-wealth-output', 'salary-kill-food',
      'salary-kill-wealth-keep-wealth', 'salary-kill-wealth-keep-kill', 'salary-output', 'salary-mixed']),
])
def test_all_new_scenarios_are_reachable_from_explicit_fictional_pillars(family, pillars, expected):
    """Manually chosen role inventories exercise all 30 candidates, not prediction truth."""
    reading = assess_luck(_chart(*pillars), {'ganzhi': '己酉'})
    actual = [s for s in reading['scenarios'] if s['family_id'] == family]
    assert [s['id'] for s in actual] == expected
    for scenario in actual:
        assert all(p['state'] == 'met' for p in scenario['premises'])
        assert scenario['unresolved_conditions']


@pytest.mark.parametrize('family,pillars', [
    ('seal', ('甲子', '癸子', '甲寅', '丙寅')),
    ('food', ('戊子', '甲寅', '壬子', '庚申')),
    ('kill', ('癸子', '庚申', '甲寅', '丙寅')),
    ('blade', ('辛酉', '丁卯', '甲子', '庚午')),
    ('salary', ('丙子', '甲寅', '甲子', '辛未')),
])
def test_new_families_have_sourced_candidates_but_do_not_settle_the_pattern(family, pillars):
    chart = _chart(*pillars)
    reading = assess_luck(chart, {'ganzhi': '己酉'})
    assert next(f for f in reading['families'] if f['family_id'] == family)['connected']
    scenarios = [s for s in reading['scenarios'] if s['family_id'] == family]
    assert scenarios
    for scenario in scenarios:
        assert scenario['unresolved_conditions']
        assert scenario['source_passage_ids']
        for part in ('stem', 'branch'):
            assert all(v['state'] == 'interpretive' and v['passage_id'] for v in scenario[part]['verdicts'])
    assert assess_luck(_chart(*pillars, hour_known=False), {'ganzhi': '己酉'})['status'] == 'unavailable'


def test_light_seal_counterexample_survives_across_paragraphs():
    reading = assess_luck(_chart('甲子', '癸子', '甲寅', '丙寅'), {'ganzhi': '己酉'})
    scenario = next(s for s in reading['scenarios'] if s['id'] == 'seal-output')
    assert {v['verdict'] for v in scenario['stem']['verdicts']} == {'favoured', 'avoided'}
    assert {v['passage_id'] for v in scenario['stem']['verdicts']} == {'ziping:c036:p0004', 'ziping:c036:p0009'}
    exception = next(v for v in scenario['stem']['verdicts'] if v['verdict'] == 'avoided')
    assert '身强印旺' not in exception['condition'], '印轻反例不能继承相反的印旺前提'
    assert reading['summary']['stem'] == 'conditional'
    assert '印輕' in luck_paragraph(reading)


def test_food_heavy_kill_light_reverses_wealth_without_settling_strength():
    reading = assess_luck(_chart('戊子', '甲寅', '壬子', '庚申'), {'ganzhi': '丙午'})
    scenario = next(s for s in reading['scenarios'] if s['id'] == 'food-kill')
    assert {v['verdict'] for v in scenario['stem']['verdicts']} == {'favoured', 'avoided'}
    assert '食太重而煞輕' in luck_paragraph(reading)


def test_salary_output_keeps_reverse_exception_and_exposed_officer_scope():
    chart = _chart('丙子', '甲寅', '甲子', '辛未')
    reading = assess_luck(chart, {'ganzhi': '癸酉'})
    scenario = next(s for s in reading['scenarios'] if s['id'] == 'salary-output')
    assert {v['verdict'] for v in scenario['stem']['verdicts']} == {'avoided', 'harmless'}
    assert not scenario['branch']['verdicts'], '酉本气为官，不等于运干透官'
    stem = assess_luck(chart, {'ganzhi': '辛未'})
    scenario = next(s for s in stem['scenarios'] if s['id'] == 'salary-output')
    assert any(v['words'] == '透官不美' for v in scenario['stem']['verdicts'])


def test_kill_can_use_a_blade_outside_the_month_but_not_an_absent_blade():
    present = assess_luck(_chart('癸卯', '庚申', '甲子', '壬辰'), {'ganzhi': '庚午'})
    assert any(s['id'] == 'kill-blade' for s in present['scenarios'])
    absent = assess_luck(_chart('癸子', '庚申', '甲子', '壬辰'), {'ganzhi': '庚午'})
    assert all(s['id'] != 'kill-blade' for s in absent['scenarios'])


def test_missing_applicable_route_is_explicit_not_a_favourable_default():
    reading = assess_luck(_chart('甲子', '癸子', '甲子', '甲子'), {'ganzhi': '甲子'})
    assert not reading['scenarios']
    assert reading['summary'] == {'stem': 'not_mentioned', 'branch': 'not_mentioned'}
    assert '喜忌未判' in luck_paragraph(reading)


def test_action_constraints_and_ambiguous_source_scope_reach_the_answer():
    reading = assess_luck(_chart('辛酉', '丙申', '甲子', '庚午'), {'ganzhi': '甲子'})
    mixed = next(s for s in reading['scenarios'] if s['id'] == 'kill-mixed')
    assert {a['words'] for a in mixed['pending_actions']} == {'莫去取清之物', '無傷制煞之神'}
    assert '莫去取清之物' in luck_paragraph(reading)
    ambiguous = assess_luck(_chart('壬申', '戊辰', '丙寅', '甲午'), {'ganzhi': '丙寅'})
    scenario = next(s for s in ambiguous['scenarios'] if s['id'] == 'food-kill-seal')
    assert any(v.get('review', {}).get('scope_interpretation') == 'unresolved' for v in scenario['stem']['verdicts'])
    assert '句法范围' in luck_paragraph(ambiguous) or '未独立校勘' in luck_paragraph(ambiguous)
