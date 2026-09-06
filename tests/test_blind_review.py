"""Version masking and review binding, with synthetic protocol fixtures only."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evals'))
SPEC = importlib.util.spec_from_file_location('blind_review', ROOT / 'evals/blind_review.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixtures(tmp_path):
    spec = {'criteria': ['completion', 'readability'], 'dispositions': ['answered', 'failed'],
            'cases': [{'id': 'B-fixture', 'group': 'fixture', 'prompt': 'synthetic', 'acceptance': ['synthetic']} ]}
    sources = []
    for version in ('old', 'new'):
        path = tmp_path / (version + '.json')
        row = {'case_id': 'B-fixture', 'repetition': 1, 'text': 'Exact answer\n字节', 'turns': [],
               'host': {'cwd': 'D:\\private\\' + version},
               'tool_calls': [{'type': 'commandExecution', 'id': 'host-id-' + version,
                               'command': 'python D:\\private\\' + version + '\\scripts\\test.py',
                               'aggregatedOutput': '{"version":"4.0.0", "id":"source-passage"}',
                               'exitCode': 0}], 'review': None, 'usage': None}
        path.write_text(json.dumps({'model': 'fixture', 'prompt_version': 'fixture',
                                    'commit': 'abcdef' + version, 'responses': [row]}), encoding='utf-8')
        sources.append((version, path))
    return spec, sources


def test_export_masks_version_metadata_without_changing_answer_or_source_ids(tmp_path):
    spec, sources = fixtures(tmp_path)
    public, private = tmp_path / 'public', tmp_path / 'private'
    module.export_packets(spec, sources, public, private, 67)
    manifest = json.loads((public / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['seed'] == 67 and len(manifest['packets']) == 2
    for item in manifest['packets']:
        packet = json.loads((public / (item['blind_id'] + '.json')).read_text(encoding='utf-8'))
        assert packet['text'] == 'Exact answer\n字节'
        tool = packet['tool_trace_summary'][0]
        evidence = json.loads((public / tool['evidence_file']).read_text(encoding='utf-8'))
        assert 'source-passage' in evidence['aggregatedOutput']
        assert '4.0.0' not in evidence['aggregatedOutput']
        assert '<snapshot>' in tool['command']
        assert 'version' not in packet and 'source' not in packet
    mapping = json.loads((private / 'mapping.json').read_text())
    assert {entry['version'] for entry in mapping['entries']} == {'old', 'new'}
    with pytest.raises(FileExistsError):
        module.export_packets(spec, sources, public, private, 67)


def completed_reviews(public):
    value = json.loads((public / 'reviews-template.json').read_text(encoding='utf-8'))
    for review in value['reviews']:
        review.update(reviewer='fixture reviewer', disposition='answered', notes='Fixture only.')
        review['criteria'] = dict.fromkeys(review['criteria'], 'pass')
        review['comprehension'] = {'main_point': 'fixture point', 'evidence': 'fixture support', 'limits': 'fixture limit'}
    path = public / 'fixture-reviews.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def test_import_writes_new_copies_and_leaves_originals_unchanged(tmp_path):
    spec, sources = fixtures(tmp_path)
    original = [path.read_bytes() for _, path in sources]
    public, private = tmp_path / 'public', tmp_path / 'private'
    module.export_packets(spec, sources, public, private, 67)
    reviews = completed_reviews(public)
    result = module.import_reviews(spec, public, private, reviews, tmp_path / 'imported')
    assert result['imported'] == 2 and result['pending'] == []
    assert all(group['rows'][0]['complete_supported_answer'] for group in result['versions'].values())
    assert [path.read_bytes() for _, path in sources] == original
    assert result['versions']['old']['rows'][0]['observations']['usage_total'] is None


@pytest.mark.parametrize('changed', ['answer', 'trace', 'packet', 'evidence', 'review_hash'])
def test_binding_rejects_changed_answer_trace_or_display(tmp_path, changed):
    spec, sources = fixtures(tmp_path)
    public, private = tmp_path / 'public', tmp_path / 'private'
    module.export_packets(spec, sources, public, private, 67)
    reviews = completed_reviews(public)
    if changed in {'answer', 'trace'}:
        path = sources[0][1]
        record = json.loads(path.read_text())
        if changed == 'answer':
            record['responses'][0]['text'] += 'changed'
        else:
            record['responses'][0]['tool_calls'].append({'type': 'changed'})
        path.write_text(json.dumps(record), encoding='utf-8')
    elif changed == 'packet':
        path = public / 'R001.json'
        packet = json.loads(path.read_text(encoding='utf-8'))
        packet['text'] += 'changed'
        path.write_text(json.dumps(packet), encoding='utf-8')
    elif changed == 'evidence':
        path = public / 'R001-tool-001.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['aggregatedOutput'] = 'changed output'
        path.write_text(json.dumps(value), encoding='utf-8')
    else:
        value = json.loads(reviews.read_text())
        value['reviews'][0]['package_sha256'] = 'changed'
        reviews.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError):
        module.import_reviews(spec, public, private, reviews, tmp_path / 'rejected')


def test_missing_comprehension_is_pending_not_automatic_readability_pass(tmp_path):
    spec, sources = fixtures(tmp_path)
    public, private = tmp_path / 'public', tmp_path / 'private'
    module.export_packets(spec, sources, public, private, 67)
    reviews = completed_reviews(public)
    value = json.loads(reviews.read_text())
    value['reviews'][0]['comprehension']['main_point'] = None
    reviews.write_text(json.dumps(value), encoding='utf-8')
    result = module.import_reviews(spec, public, private, reviews, tmp_path / 'pending')
    assert result['imported'] == 1 and len(result['pending']) == 1
