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


def test_verified_quote_cannot_promote_a_legacy_framework_to_an_applied_rule(chart):
    packet = deepcopy(chart['reading_support'])
    claim = packet['claims'][1]
    claim['conditions'] = dict.fromkeys(claim['conditions'], 'met')
    claim['status'] = 'supported'
    source = next(s for s in load_evidence()['sources'] if s['id'] == 'ziping-month')
    claim['quotes'] = [{'source_id': source['id'], 'text': source['quote']}]
    assert any('framework rule' in e for e in review_claims(chart, packet))
    claim['status'] = 'needs_review'
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


@pytest.mark.parametrize('mutation', ['forged', 'wrong_layer', 'missing', 'malformed'])
def test_frozen_passage_quotes_reject_false_text_or_layer(chart, mutation):
    from classical_search import get_passage
    paragraph = get_passage('ziping:c008:p0001')
    packet = deepcopy(chart['reading_support'])
    quote = {'passage_id': paragraph['passage_id'], 'text': paragraph['text'][:12],
             'layer': paragraph['layer']}
    packet['claims'][0]['passage_quotes'] = [quote]
    assert review_claims(chart, packet) == []
    if mutation == 'forged':
        quote['text'] = '今年三月必定升职'
    elif mutation == 'wrong_layer':
        quote['layer'] = 'modern_commentary'
    elif mutation == 'missing':
        quote['passage_id'] = 'ziping:c999:p9999'
    else:
        packet['claims'][0]['passage_quotes'] = [None]
    assert any('quotation' in error for error in review_claims(chart, packet))


def test_registered_quote_must_still_match_frozen_source(chart, monkeypatch):
    import reading_support
    monkeypatch.setattr(reading_support, 'get_passage', lambda _: {'text': 'unrelated'})
    assert any('registered quote absent' in error
               for error in review_claims(chart, chart['reading_support']))


def test_default_reading_envelope_can_be_reviewed_without_fabricating_a_chart(chart):
    from bazi_reading import prepare_reading
    reading = prepare_reading(chart)
    assert review_claims(reading, reading['reading_support']) == []
    broken = deepcopy(reading)
    broken['chart_facts']['four_pillars']['year']['ganzhi'] = '甲子'
    assert any('mismatch' in e for e in review_claims(broken, broken['reading_support']))
    broken['ok'] = False
    assert review_claims(broken, broken['reading_support'])


def test_reading_cli_accepts_the_default_envelope(chart):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from bazi_reading import prepare_reading
    reading = prepare_reading(chart)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] /
                            'scripts/reading_support.py'), '--stdin'],
                            input=json.dumps({'chart': reading}, ensure_ascii=False),
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['packet'] == reading['reading_support']
