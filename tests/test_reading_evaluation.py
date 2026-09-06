"""An empty recording or an unreviewed answer must never receive a passing score."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / 'evals/reading_cases.json').read_text(encoding='utf-8'))
module_spec = importlib.util.spec_from_file_location('reading_eval', ROOT / 'evals/evaluate_readings.py')
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)


def test_thirty_distinct_cases_with_actionable_acceptance():
    assert len(SPEC['cases']) == 30
    assert len({c['id'] for c in SPEC['cases']}) == 30
    assert all(c['prompt'] and c['acceptance'] and c['semantic_review_required'] for c in SPEC['cases'])


def test_no_actual_model_run_is_not_a_pass():
    result = module.evaluate(SPEC, {})
    assert not result['ok']
    assert result['answers'] == 0 and len(result['pending']) == 30


def test_actual_text_without_review_is_pending():
    row = {'case_id': SPEC['cases'][0]['id'], 'text': '测试文本', 'tool_calls': []}
    result = module.evaluate(SPEC, {'model': 'fixture', 'prompt_version': 'fixture', 'responses': [row]})
    assert not result['ok'] and result['reviewed'] == 0


def test_completed_fixture_records_and_failures():
    one = {**SPEC, 'cases': [SPEC['cases'][7]]}
    row = {'case_id': one['cases'][0]['id'], 'text': 'fixture only, not a model run', 'tool_calls': [],
           'review': {'reviewer': 'test fixture', 'notes': 'tests scorer control flow only',
                      'disposition': 'partial',
                      'criteria': dict.fromkeys(SPEC['criteria'], 'pass')}}
    recording = {'model': 'fixture', 'prompt_version': 'fixture', 'responses': [row]}
    assert module.evaluate(one, recording)['ok']
    row['review']['criteria']['source_fidelity'] = 'fail'
    assert not module.evaluate(one, recording)['ok']
    recording['responses'].append(row)
    assert any('duplicate' in e for e in module.evaluate(one, recording)['errors'])


def test_required_chart_cannot_be_replaced_by_a_green_review():
    one = {**SPEC, 'cases': SPEC['cases'][:1]}
    row = {'case_id': one['cases'][0]['id'], 'text': 'fixture', 'tool_calls': [],
           'review': {'reviewer': 'fixture', 'notes': 'fixture', 'disposition': 'deferred',
                      'criteria': dict.fromkeys(SPEC['criteria'], 'pass')}}
    result = module.evaluate(one, {'model': 'fixture', 'prompt_version': 'fixture', 'responses': [row]})
    assert not result['ok']
    assert result['answer_dispositions']['deferred'] == 1
    assert any('actual successful chart' in error for error in result['errors'])
