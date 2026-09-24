"""Prospective records test chronology, evidence gates and honest denominators."""
import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import prediction_log as log
import pytest

NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def spec():
    return {'consent': True, 'subject_id': 'a' * 32, 'event_definition': '收到新邀请',
                'timezone': 'Australia/Sydney', 'start': (NOW + timedelta(days=1)).isoformat(),
                'end': (NOW + timedelta(days=8)).isoformat(), 'method': 'fixture-method',
                'method_version': '1', 'input_fingerprint': 'b' * 64}


@pytest.fixture
def forecast(monkeypatch):
    # Synthetic rule checks storage only, never passed off as an actual classical rule.
    monkeypatch.setattr(log, 'get_passage', lambda _: {'text': '测试条件甲成立', 'sha256': 'c' * 64})
    return {'prediction': 'happens', 'reason': '测试记录', 'evidence': [{
        'passage_id': 'test:p1', 'quote': '测试条件甲', 'condition': '核查测试条件', 'state': 'met',
        'personal_fields': ['birth.day'], 'scope': 'event'}], 'conflicts': []}


def create(root, spec, forecast):
    record = log.begin(spec, root=root, clock=NOW)
    return log.change(record['id'], 'seal', forecast, expected_revision=1, root=root, clock=NOW)


def observe(root, record, result='happened', **kwargs):
    return log.change(record['id'], 'observe', {'confirmed': True, 'result': result,
        'occurred_at': (NOW + timedelta(days=2)).isoformat() if result == 'happened' else None,
        'note': '用户确认测试结果'}, expected_revision=record['revision'], root=root,
        clock=kwargs.get('clock', NOW + timedelta(days=9)))


def test_empty_read_does_not_create_database(tmp_path):
    stats = log.inspect_records(root=tmp_path, clock=NOW)
    assert stats['total'] == 0 and stats['observed_hit_rate'] is None
    assert not (tmp_path / 'predictions').exists()


@pytest.mark.parametrize('change', [{'consent': False}, {'consent': 1}, {'name': 'private'},
    {'subject_id': '../bad'}, {'timezone': 'invalid/zone'}, {'input_fingerprint': 'bad'},
    {'start': NOW.isoformat()}, {'start': '2030-01-02'}, {'end': NOW.isoformat()}])
def test_begin_rejects_bad_or_private_inputs(tmp_path, spec, change):
    with pytest.raises((ValueError, KeyError)):
        log.begin({**spec, **change}, root=tmp_path, clock=NOW)
    assert not (tmp_path / 'predictions').exists()


def test_repository_storage_rejected(spec):
    with pytest.raises(ValueError):
        log.begin(spec, root=Path(__file__).resolve().parents[1], clock=NOW)


@pytest.mark.parametrize('case', ['quote', 'unknown', 'not_met', 'background', 'unresolved', 'no_evidence'])
def test_event_claim_gates(tmp_path, spec, forecast, case):
    if case == 'quote':
        forecast['evidence'][0]['quote'] = '编造引文'
    elif case in ('unknown', 'not_met'):
        forecast['evidence'][0]['state'] = case
    elif case == 'background':
        forecast['evidence'][0]['scope'] = 'background'
    elif case == 'unresolved':
        forecast['conflicts'] = [{'issue': '冲突', 'resolution': '', 'evidence_indices': []}]
    else:
        forecast['evidence'] = []
    with pytest.raises(ValueError):
        create(tmp_path, spec, forecast)
    assert log.inspect_records(root=tmp_path, clock=NOW)['counts']['unfinished'] == 1


def test_sealing_is_immutable_and_revision_checked(tmp_path, spec, forecast):
    r = create(tmp_path, spec, forecast)
    for revision in (1, 2):
        with pytest.raises(ValueError):
            log.change(r['id'], 'seal', forecast, expected_revision=revision, root=tmp_path, clock=NOW)
    with pytest.raises(ValueError):
        log.change(r['id'], 'correct', {'method': 'changed'}, expected_revision=2, root=tmp_path, clock=NOW)
    corrected = log.change(r['id'], 'correct', {'note': '补充说明'}, expected_revision=2, root=tmp_path, clock=NOW)
    assert corrected['forecast_sha256'] == r['forecast_sha256']
    assert corrected['spec'] == r['spec']
    with pytest.raises(ValueError):
        log.change(r['id'], 'correct', {'note': '过期写入'}, expected_revision=2, root=tmp_path, clock=NOW)


def test_cannot_seal_after_start(tmp_path, spec, forecast):
    r = log.begin(spec, root=tmp_path, clock=NOW)
    with pytest.raises(ValueError):
        log.change(r['id'], 'seal', forecast, expected_revision=1, root=tmp_path, clock=NOW + timedelta(days=1))


def test_pending_corrections_and_deletion(tmp_path, spec, forecast):
    r = create(tmp_path, spec, forecast)
    with pytest.raises(ValueError):
        observe(tmp_path, r, 'not_happened', clock=NOW + timedelta(days=3))
    r = observe(tmp_path, r, clock=NOW + timedelta(days=3))
    assert log.inspect_records(root=tmp_path, clock=NOW + timedelta(days=3))['observed_hit_rate'] is None
    assert log.inspect_records(root=tmp_path, clock=NOW + timedelta(days=8))['counts']['hit'] == 1
    r = observe(tmp_path, r, 'not_happened')
    stats = log.inspect_records(root=tmp_path, clock=NOW + timedelta(days=9))
    assert stats['counts']['miss'] == 1 and stats['correction_events'] == 1
    assert r['history'][1]['payload']['result'] == 'happened'
    for bad in (False, 1):
        with pytest.raises(ValueError):
            log.change(r['id'], 'delete', {'confirmed': bad}, expected_revision=r['revision'], root=tmp_path)
    log.change(r['id'], 'delete', {'confirmed': True}, expected_revision=r['revision'], root=tmp_path)
    stats = log.inspect_records(root=tmp_path)
    assert stats['total'] == 0 and stats['deleted_records'] == 1
    with pytest.raises(ValueError):
        log.inspect_records(ident=r['id'], root=tmp_path)


@pytest.mark.parametrize('confirmed,offset', [(False, 2), (True, 0), (True, 8), (True, 10)])
def test_outcome_confirmation_and_boundaries(tmp_path, spec, forecast, confirmed, offset):
    r = create(tmp_path, spec, forecast)
    with pytest.raises(ValueError):
        log.change(r['id'], 'observe', {'confirmed': confirmed, 'result': 'happened',
            'occurred_at': (NOW + timedelta(days=offset)).isoformat(), 'note': '反馈'},
            expected_revision=2, root=tmp_path, clock=NOW + timedelta(days=9))


def test_denominators_and_cohorts(tmp_path, spec, forecast):
    r = create(tmp_path, spec, forecast)
    observe(tmp_path, r)
    create(tmp_path, spec, forecast)  # No outcome: not a failure or a hit.
    create(tmp_path, spec, {'prediction': 'unable', 'reason': '无事件条款', 'evidence': [], 'conflicts': []})
    log.begin(spec, root=tmp_path, clock=NOW)  # Unfinished still counts.
    create(tmp_path, {**spec, 'method_version': '2'}, copy.deepcopy(forecast))
    stats = log.inspect_records(root=tmp_path, clock=NOW + timedelta(days=9))
    assert stats['answer_coverage'] == 3 / 5
    assert stats['outcome_confirmation_coverage'] == 1 / 3
    assert stats['observed_hit_rate'] == 1
    assert stats['counts']['unverified'] == 2
    assert [c['total'] for c in stats['cohorts']] == [4, 1]


@pytest.mark.parametrize('action,payload,expected', [('stats', {}, 0), ('show', {'id': 'bad'}, 1),
    ('show', {'id': None}, 1), ('show', {'id': ''}, 1),
    ('begin', {'birth': {}}, 1), ('correct', {'id': 'a'*32, 'expected_revision': 0, 'payload': {}}, 1)])
def test_cli_json_envelope(tmp_path, action, payload, expected):
    p = subprocess.run([sys.executable, str(Path(log.__file__)), action, '--stdin', '--data-dir', str(tmp_path)],
        input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == expected, p.stderr
    assert json.loads(p.stdout)['ok'] is (expected == 0)
    assert 'Traceback' not in p.stderr


def test_concurrent_revision_cannot_overwrite(tmp_path, spec, forecast):
    r = create(tmp_path, spec, forecast)

    def edit(number):
        try:
            log.change(r['id'], 'correct', {'note': str(number)}, expected_revision=2, root=tmp_path)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, [1, 2])) == [False, True]
    saved = log.inspect_records(ident=r['id'], root=tmp_path)
    assert saved['revision'] == 3 and len(saved['history']) == 2


def test_actual_source_hash_is_preserved_without_certifying_prediction(tmp_path, spec):
    source = log.get_passage('ziping:c008:p0001')
    payload = {'prediction': 'unable', 'reason': '只有命局背景，缺本题事件依据',
               'evidence': [{'passage_id': source['passage_id'], 'quote': source['text'][:12],
                             'condition': '个人适用性未确认', 'state': 'unknown',
                             'personal_fields': ['birth.day'], 'scope': 'background'}], 'conflicts': []}
    r = create(tmp_path, spec, payload)
    assert r['forecast']['evidence'][0]['source_sha256'] == source['sha256']
    assert r['forecast']['validation'] == 'quote_and_structure_checked_semantics_not_certified'


def test_conclusion_preserves_scope_and_fixed_method_contract():
    from fortune_decision import conclusion_packet
    result = conclusion_packet({'participants': [], 'recommendation': {'status': 'screened_only'},
                                'decision_blockers': []})
    assert result['traditional_personal_ranking'] == 'not_established'
    assert result['interpretation_contract']['method_selection'] == 'fix_before_interpretation'
