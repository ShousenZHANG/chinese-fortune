"""Source identity and actual application boundaries of optional-method rules."""
import copy
import json

import pytest
from conftest import run_cli
from method_rules import (
    RULES_PATH,
    audit_rules,
    get_rules,
    method_reading_packet,
    review_applications,
)
from tiaohou_provenance import audit_tiaohou, get_tiaohou_audit


def test_selected_excerpts_have_independent_method_identities():
    assert not audit_rules()
    for method, title in [('ziwei', '紫微斗數全書'), ('liuyao', '增刪卜易')]:
        rules = get_rules(method)
        assert len(rules) == 4
        for rule in rules:
            assert all(title in source['title'] for source in rule['sources'])
            assert all(source['facsimile_status'] == 'not_checked' for source in rule['sources'])
            assert all('bazi' not in sid for sid in rule['source_ids'])
    with pytest.raises(ValueError, match='wrong-method'):
        get_rules('ziwei', ['liuyao-support-roles'])


def test_excerpt_tampering_and_wrong_method_source_are_detected():
    data = json.loads(RULES_PATH.read_text(encoding='utf-8'))
    data['sources'][0]['text'] += '凭空加字'
    data['rules'][0]['source_ids'] = ['liuyao-zengshan-relatives']
    errors = audit_rules(data)
    assert any('hash mismatch' in e for e in errors)
    assert any('wrong-method source' in e for e in errors)


def test_real_ziwei_output_carries_reviewable_facts_without_filling_conditions():
    chart = run_cli('ziwei_calc.py', '--year', 2000, '--month', 1, '--day', 15,
                    '--hour', 10, '--gender', 'male')
    packet = chart['reading_support']['method_rules']
    assert len(packet['applications']) == 4
    assert not review_applications('ziwei', chart, packet['applications'])
    assert all(app['status'] == 'needs_review' for app in packet['applications'])
    assert any('unknown' in app['conditions'].values() for app in packet['applications'])
    forged = copy.deepcopy(packet['applications'])
    forged[0]['facts'][0]['value'] = 99
    forged[0]['status'] = 'supported'
    errors = review_applications('ziwei', chart, forged)
    assert any('chart fact mismatch' in e for e in errors)
    assert any('unresolved conditions' in e for e in errors)
    all_met = copy.deepcopy(packet['applications'][0])
    all_met['status'] = 'supported'
    all_met['conditions'] = dict.fromkeys(all_met['conditions'], 'met')
    errors = review_applications('ziwei', chart, [all_met])
    assert any('condition reason' in e for e in errors)
    assert any('condition chart evidence' in e for e in errors)
    assert any('condition source evidence' in e for e in errors)


def test_leap_month_does_not_claim_the_frozen_nonleap_rule_was_satisfied():
    chart = {'input': {'is_leap_month': True}, 'lunar_date': {'month': 2},
             'ming_gong': {'branch': '卯'}, 'shen_gong': {'branch': '丑'}}
    packet = method_reading_packet('ziwei', chart)
    app = next(a for a in packet['applications'] if a['rule_id'] == 'ziwei-ming-shen')
    assert app['status'] == 'not_applicable'
    assert app['conditions']['non_leap_month'] == 'not_met'
    app['conditions']['non_leap_month'] = 'met'
    assert any('leap-month' in e for e in review_applications('ziwei', chart, [app]))


def test_liuyao_can_review_relations_without_claiming_support_is_effective():
    from liuyao_cast import dress_chart
    chart = {'main_chart': dress_chart([7] * 6, '甲', '子', '寅'),
             'yongshen_hint': None, 'cast_time': {'day_ganzhi': '甲子', 'month_branch': '寅'},
             'active_lines': []}
    packet = method_reading_packet('liuyao', chart)
    assert not review_applications('liuyao', chart, packet['applications'])
    app = next(a for a in packet['applications'] if a['rule_id'] == 'liuyao-support-effective')
    assert app['conditions']['use_root_reviewed'] == 'unknown'
    app['status'] = 'supported'
    assert review_applications('liuyao', chart, [app])
    assert '旺相' in next(r for r in packet['rules'] if r['id'] == app['rule_id'])['quote']


def test_shi_ying_condition_is_recomputed_even_with_matching_facts():
    chart = {'main_chart': {'shi_position': 6, 'ying_position': 4}}
    app = next(a for a in method_reading_packet('liuyao', chart)['applications']
               if a['rule_id'] == 'liuyao-shi-ying')
    app['conditions']['two_between'] = 'met'
    assert any('computed condition mismatch' in e
               for e in review_applications('liuyao', chart, [app]))


def test_tiaohou_month_specific_conflicts_and_missing_text_are_visible():
    assert not audit_tiaohou()
    jia_wei = get_tiaohou_audit('甲|未')
    assert jia_wei['status'] == 'conflicts_with_text'
    assert jia_wei['source_general_candidates'] == ['丁', '庚']
    assert '无癸亦可' in jia_wei['review_note']
    xin_zi = get_tiaohou_audit('辛|子')
    assert '戊' not in xin_zi['source_general_candidates']
    assert '戊' in xin_zi['source_conditional_candidates']
    yi_chou = get_tiaohou_audit('乙|丑')
    assert yi_chou['status'] == 'seasonal_only'
    assert yi_chou['source_general_candidates'] == []
    assert yi_chou['source_conditional_candidates'] == []
    assert yi_chou['seasonal_context_candidates'] == ['丙']


def test_reviewed_tiaohou_keeps_month_and_chart_branches_separate():
    # 丙卯: 己 is an absence-of-壬 alternative, not a second general first choice.
    bing_mao = get_tiaohou_audit('丙|卯')
    assert bing_mao['source_general_candidates'] == ['壬']
    assert '己' in bing_mao['source_conditional_candidates']
    assert '无壬' in bing_mao['review_note']
    # 乙酉 distinguishes the autumn-equinox boundary instead of one month slogan.
    yi_you = get_tiaohou_audit('乙|酉')
    assert '秋分' in yi_you['review_note']
    assert yi_you['facsimile_status'] == 'not_checked'
    yi_you['source_refs'].clear()
    assert get_tiaohou_audit('乙|酉')['source_refs']  # callers cannot corrupt cache


def test_tiaohou_summary_cannot_disagree_with_individual_reviews(monkeypatch):
    import tiaohou_provenance
    data = copy.deepcopy(tiaohou_provenance._registry())
    data['summary']['supported_with_conditions'] += 1
    monkeypatch.setattr(tiaohou_provenance, '_registry', lambda: data)
    assert 'summary differs from per-cell status counts' in audit_tiaohou()
