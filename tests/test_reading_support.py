"""The content gate must reject false evidence, not just find prompt keywords."""
from copy import deepcopy

import pytest
from bazi_calc import build_parser, calculate_bazi
from reading_support import load_evidence, render_packet, review_claims


@pytest.fixture
def chart():
    return calculate_bazi(build_parser().parse_args([
        '--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
        '--minute', '30', '--gender', 'male', '--as-of-year', '2026']))


def test_calculation_has_no_stdout_and_preserves_request(capsys):
    args = build_parser().parse_args(['--year', '2000', '--month', '1', '--day', '15',
                                     '--gender', 'male'])
    before = vars(args).copy()
    result = calculate_bazi(args)
    assert result['ok']
    assert vars(args) == before
    assert capsys.readouterr().out == ''


def test_candidates_are_not_verdicts_or_raw_fortune_prose(chart):
    ys = chart['yong_shen']
    assert ys['primary'] is None and ys['status'] == 'needs_review'
    assert chart['xi_shen']['primary'] is None
    assert chart['ji_shen']['primary'] is None
    assert ys['views']['fuyi']['kind'] == 'heuristic'
    assert len(ys['views']['tiaohou']['candidates']) >= 1
    assert all(phrase not in ys['reason'] for phrase in ('富贵', '夭折', '刑妻', '名臣'))
    assert chart['ge_ju']['status'] == 'candidate_only'


def test_generated_packet_is_structurally_valid_but_not_semantically_certified(chart):
    packet = chart['reading_support']
    assert review_claims(chart, packet) == []
    assert packet['review_status'] == 'structural_only'
    assert '四柱' in render_packet(packet)


@pytest.mark.parametrize('mutation,expected', [
    ('wrong_fact', 'mismatch'), ('missing_path', 'invalid chart path'),
    ('unknown_source', 'unknown source'), ('certainty', 'unsupported certainty'),
    ('precision', 'unsupported time precision'), ('probability', 'uncalibrated'),
    ('missing_condition', 'missing conditions'), ('false_quote', 'unverified quotation'),
])
def test_gate_rejects_bad_claims(chart, mutation, expected):
    packet = deepcopy(chart['reading_support'])
    claim = packet['claims'][1]
    if mutation == 'wrong_fact':
        claim['facts'][0]['value'] = '甲子'
    elif mutation == 'missing_path':
        claim['facts'][0]['path'] = 'four_pillars.nonexistent.ganzhi'
    elif mutation == 'unknown_source':
        claim['source_ids'].append('invented-book')
    elif mutation == 'certainty':
        claim['status'] = 'supported'
    elif mutation == 'precision':
        claim['scope'] = 'day'
    elif mutation == 'probability':
        claim['probability'] = 0.9
    elif mutation == 'missing_condition':
        claim['conditions'] = {}
    elif mutation == 'false_quote':
        claim['quotes'] = [{'source_id': 'ziping-month', 'text': '必定升职'}]
    assert any(expected in err for err in review_claims(chart, packet))


def test_verified_quote_and_declared_conditions_are_accepted(chart):
    packet = deepcopy(chart['reading_support'])
    claim = packet['claims'][1]
    claim['conditions'] = dict.fromkeys(claim['conditions'], 'met')
    claim['status'] = 'supported'
    source = next(s for s in load_evidence()['sources'] if s['id'] == 'ziping-month')
    claim['quotes'] = [{'source_id': source['id'], 'text': source['quote']}]
    # Deliberately structural only: marking a condition met still needs semantic review.
    assert review_claims(chart, packet) == []


def test_pending_source_cannot_certify_a_conclusion(chart):
    packet = deepcopy(chart['reading_support'])
    claim = packet['claims'][2]
    claim['conditions'] = dict.fromkeys(claim['conditions'], 'met')
    claim['status'] = 'supported'
    assert any('unverified source' in e for e in review_claims(chart, packet))


@pytest.mark.parametrize('packet', [{}, {'claims': []}, {'claims': [None]},
                                    {'claims': [{'id': [], 'kind': 'x'}]}, None,
                                    {'claims': [{'id': 'bad', 'facts': [{'path': None}],
                                                 'quotes': [{'source_id': []}]}]}])
def test_malformed_packet_fails_closed(chart, packet):
    assert review_claims(chart, packet)
