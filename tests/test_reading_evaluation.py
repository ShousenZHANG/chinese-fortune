"""An empty recording or an unreviewed answer must never receive a passing score."""
import importlib.util
import json
from copy import deepcopy
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


def test_version_two_review_cannot_be_reused_after_answer_or_tools_change():
    one = {**SPEC, 'schema_version': '2.0', 'cases': [SPEC['cases'][7]]}
    row = {'case_id': one['cases'][0]['id'], 'text': 'fixture only', 'tool_calls': [],
           'review': {'reviewer': 'test fixture', 'notes': 'control flow only',
                      'disposition': 'answered', 'criteria': dict.fromkeys(SPEC['criteria'], 'pass')}}
    recording = {'model': 'fixture', 'prompt_version': 'fixture', 'responses': [row]}
    assert not module.evaluate(one, recording)['ok']
    row['review']['answer_sha256'] = module.answer_digest(row)
    assert module.evaluate(one, recording)['ok']
    for key, value in [('text', 'completely unrelated answer'), ('tool_calls', [{'command': 'changed'}])]:
        changed = deepcopy(recording)
        changed['responses'][0][key] = value
        errors = module.evaluate(one, changed)['errors']
        assert any('not bound' in error for error in errors)


V4_SPEC = json.loads((ROOT / 'evals/reading_cases_v4.json').read_text(encoding='utf-8'))


def conversation_fixture():
    case = next(case for case in V4_SPEC['cases'] if case['id'] == 'T01')
    turns = [{'index': index, 'prompt': request['prompt'], 'status': 'completed',
              'text': f'fixture turn {index}', 'thread_id': 'fixture-thread',
              'turn_id': f'fixture-turn-{index}'} for index, request in enumerate(case['turns'], 1)]
    row = {'case_id': case['id'], 'text': 'fixture transcript', 'turns': turns,
           'tool_calls': [{'type': 'fixture'}], 'exit_code': 0, 'execution_error': None,
           'review': {'reviewer': 'fixture only', 'notes': 'tests validator, not actual model quality',
                      'disposition': 'answered', 'criteria': dict.fromkeys(V4_SPEC['criteria'], 'pass')}}
    row['review']['answer_sha256'] = module.answer_digest(row)
    return {**V4_SPEC, 'cases': [case]}, {'model': 'fixture', 'prompt_version': 'fixture', 'responses': [row]}


def test_v4_complete_conversation_and_partial_disposition_are_distinct():
    spec, recording = conversation_fixture()
    assert module.evaluate(spec, recording)['ok']
    recording['responses'][0]['review']['disposition'] = 'partially_answered'
    result = module.evaluate(spec, recording)
    assert not result['ok']
    assert result['answer_dispositions']['partially_answered'] == 1
    assert any('does not complete' in error for error in result['errors'])


def test_v4_cannot_replace_real_followup_with_combined_first_prompt_or_another_thread():
    spec, recording = conversation_fixture()
    for mutation in ('missing', 'duplicate', 'other_thread', 'prompt', 'failed', 'no_tools'):
        changed = deepcopy(recording)
        row = changed['responses'][0]
        if mutation == 'missing':
            row['turns'].pop()
        elif mutation == 'duplicate':
            row['turns'][1]['turn_id'] = row['turns'][0]['turn_id']
        elif mutation == 'other_thread':
            row['turns'][1]['thread_id'] = 'different-thread'
        elif mutation == 'prompt':
            row['turns'][0]['prompt'] += row['turns'][1]['prompt']
        elif mutation == 'failed':
            row['exit_code'] = 1
        else:
            row['tool_calls'] = []
        row['review']['answer_sha256'] = module.answer_digest(row)
        assert not module.evaluate(spec, changed)['ok'], mutation


def test_v4_review_binding_includes_earlier_turn_answer():
    spec, recording = conversation_fixture()
    recording['responses'][0]['turns'][0]['text'] = 'different first answer'
    assert any('not bound' in error for error in module.evaluate(spec, recording)['errors'])


def test_v4_cases_remain_twenty_four_unanswered_designs():
    assert len(V4_SPEC['cases']) == 24
    assert all('text' not in case and 'review' not in case for case in V4_SPEC['cases'])
    assert sum(len(case.get('turns', [])) == 2 for case in V4_SPEC['cases']) == 4
    assert not module.evaluate(V4_SPEC, {'model': 'fixture', 'prompt_version': 'fixture', 'responses': []})['ok']
