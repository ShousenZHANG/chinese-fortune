"""The blind-review rubric carries the drift categories, their definitions and
calibration examples to the reviewer, not just their names."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evals'))
_SPEC = importlib.util.spec_from_file_location('blind_review', ROOT / 'evals/blind_review.py')
blind_review = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(blind_review)

DRIFT = ('drift_new_number', 'drift_new_fact', 'drift_invented_mechanism',
         'drift_not_self_contained', 'drift_scope_flipped')
V4 = json.loads((ROOT / 'evals/reading_cases_v4.json').read_text(encoding='utf-8'))
EXAMPLES = json.loads((ROOT / 'evals/drift_examples.json').read_text(encoding='utf-8'))


def test_the_v4_suite_scores_every_drift_category_and_defines_it():
    for key in DRIFT:
        assert key in V4['criteria'] and key in V4['review_protocol']['criteria'], key
        assert V4['criteria_definitions'][key], key


def test_every_category_has_a_failing_and_the_set_has_passing_examples():
    """Pass examples guard against a reviewer who flags every paraphrase."""
    assert set(EXAMPLES['categories']) == set(DRIFT)
    for key in DRIFT:
        assert any(e['category'] == key and e['expected'] == 'fail' for e in EXAMPLES['examples']), key
    passing = [e for e in EXAMPLES['examples'] if e['expected'] == 'pass']
    assert len(passing) >= 4
    for example in EXAMPLES['examples']:
        assert example['source'] and example['rendered'] and example['why'], example['id']


def test_the_manifest_hands_reviewers_the_definitions_and_the_examples(tmp_path):
    spec = {'criteria': ['completion', 'drift_scope_flipped'], 'dispositions': ['answered', 'failed'],
            'criteria_definitions': {'drift_scope_flipped': V4['criteria_definitions']['drift_scope_flipped']},
            'cases': [{'id': 'B-fixture', 'group': 'fixture', 'prompt': 'synthetic', 'acceptance': ['synthetic']}]}
    path = tmp_path / 'run.json'
    path.write_text(json.dumps({'model': 'fixture', 'prompt_version': 'fixture', 'commit': 'abc',
                                'responses': [{'case_id': 'B-fixture', 'repetition': 1, 'text': 'answer',
                                               'turns': [], 'tool_calls': [], 'review': None}]}),
                    encoding='utf-8')
    blind_review.export_packets(spec, [('v', path)], tmp_path / 'public', tmp_path / 'private', 7)
    manifest = json.loads((tmp_path / 'public' / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['criteria_definitions']['drift_scope_flipped']
    assert {e['id'] for e in manifest['calibration']['examples']} >= {'D05', 'P01'}
