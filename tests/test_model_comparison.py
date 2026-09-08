"""Protocol fixtures test recording mechanics; they are not model evaluations."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('model_comparison', ROOT / 'evals/run_model_comparison.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def setup_protocol(tmp_path, monkeypatch, behavior='normal'):
    """A subprocess emits real JSON-RPC ordering, including early notifications."""
    script = tmp_path / 'fixture_server.py'
    script.write_text('''import json, sys
behavior = sys.argv[1]
def emit(obj):
    print(json.dumps(obj), flush=True)
for line in sys.stdin:
    value = json.loads(line)
    method = value.get('method')
    if method == 'initialize':
        emit({'id': value['id'], 'result': {'userAgent': 'test fixture'}})
    elif method == 'thread/start':
        emit({'id': value['id'], 'result': {
            'model': 'wrong' if behavior == 'wrong_model' else 'fixture-model',
            'reasoningEffort': 'ultra', 'sandbox': {'type': 'readOnly'},
            'thread': {'id': 'fixture-thread', 'ephemeral': True}}})
    elif method == 'turn/start':
        if behavior == 'malformed':
            print('not JSON', flush=True)
            continue
        if behavior == 'timeout':
            continue
        turn_id = 'turn-' + str(value['id'])
        text = 'fixture answer: ' + value['params']['input'][0]['text']
        item = {'type': 'agentMessage', 'id': turn_id + '-answer',
                'phase': 'final_answer', 'text': text}
        emit({'method': 'item/completed', 'params': {'threadId': 'fixture-thread',
              'turnId': turn_id, 'item': item}})
        emit({'id': value['id'], 'result': {'turn': {'id': turn_id}}})
        emit({'method': 'thread/tokenUsage/updated', 'params': {'threadId': 'fixture-thread',
              'turnId': turn_id, 'tokenUsage': {'total': {'totalTokens': value['id'] * 10}}}})
        emit({'method': 'turn/completed', 'params': {'threadId': 'fixture-thread',
              'turn': {'id': turn_id, 'items': [],
                       'status': 'failed' if behavior == 'failed_turn' or
                           (behavior == 'failed_followup' and 'second' in text) else 'completed'}}})
''', encoding='utf-8')
    real_server = runner.AppServer
    timeline = []

    def launch(command, cwd, folder, timeout):
        server = real_server([sys.executable, str(script), behavior], cwd, folder, timeout)
        original_request, original_completed = server.request, server.completed_turn

        def request(method, params):
            if method == 'turn/start':
                timeline.append('start')
            return original_request(method, params)

        def completed(thread_id, turn_id):
            result = original_completed(thread_id, turn_id)
            timeline.append('completed')
            return result

        server.request, server.completed_turn = request, completed
        return server

    monkeypatch.setattr(runner, 'AppServer', launch)
    return argparse.Namespace(output=tmp_path / 'recordings', snapshot=tmp_path,
                              cli=Path('fixture'), python=Path(sys.executable),
                              timeout=0.3 if behavior == 'timeout' else 5,
                              model='fixture-model', effort='ultra', protocol_timeline=timeline)


def test_real_protocol_records_sequential_followups_in_one_ephemeral_thread(tmp_path, monkeypatch):
    args = setup_protocol(tmp_path, monkeypatch)
    case = {'id': 'T-fixture', 'prompt': 'first only',
            'turns': [{'prompt': 'first only'}, {'prompt': 'follow-up only'}]}
    row = runner.record_case(args, case, 1)
    assert row['exit_code'] == 0 and row['review'] is None
    assert args.protocol_timeline == ['start', 'completed', 'start', 'completed']
    assert [turn['text'] for turn in row['turns']] == [
        'fixture answer: first only', 'fixture answer: follow-up only']
    assert {turn['thread_id'] for turn in row['turns']} == {'fixture-thread'}
    assert len({turn['turn_id'] for turn in row['turns']}) == 2
    requests = [json.loads(line) for line in (args.output / 'T-fixture-run1/requests.jsonl').read_text().splitlines()]
    starts = [r['params'] for r in requests if r['method'] == 'turn/start']
    assert [r['input'] for r in starts] == [[{'type': 'text', 'text': 'first only'}],
                                          [{'type': 'text', 'text': 'follow-up only'}]]
    assert row['usage']['total']['totalTokens'] == 40
    assert row['measurements']['user_input_utf8_bytes'] == len(b'first onlyfollow-up only')
    assert (args.output / 'T-fixture-run1/answer-1.txt').exists()
    with pytest.raises(FileExistsError):
        runner.record_case(args, case, 1)


@pytest.mark.parametrize(('behavior', 'expected'), [
    ('wrong_model', 'model/effort differs'), ('malformed', 'non-JSON'),
    ('failed_turn', 'without a completed answer'), ('timeout', 'timed out')])
def test_protocol_failure_is_recorded_without_retry_or_followup(tmp_path, monkeypatch, behavior, expected):
    args = setup_protocol(tmp_path, monkeypatch, behavior)
    case = {'id': 'failure', 'prompt': 'first', 'turns': [{'prompt': 'first'}, {'prompt': 'second'}]}
    row = runner.record_case(args, case, 1)
    assert row['exit_code'] == 1 and expected in row['execution_error']
    folder = args.output / 'failure-run1'
    assert json.loads((folder / 'record.json').read_text(encoding='utf-8')) == row
    sent = (folder / 'requests.jsonl').read_text(encoding='utf-8')
    assert 'second' not in sent
    if behavior == 'failed_turn':
        assert row['turns'][0]['text'] == 'fixture answer: first'
        assert row['turns'][0]['status'] == 'failed'
    assert (folder / 'events.jsonl').exists()


@pytest.mark.parametrize(('start', 'count', 'expected'), [(1, 2, [1, 2]), (2, 1, [2])])
def test_cli_retry_preserves_original_repetition_numbers_and_prior_failure(
        tmp_path, monkeypatch, start, count, expected):
    """A retry records fresh whole turns, leaving the previous partial failure intact."""
    args = setup_protocol(tmp_path, monkeypatch, behavior='failed_followup')
    case = {'id': 'T-fixture', 'prompt': 'first',
            'turns': [{'prompt': 'first'}, {'prompt': 'second'}]}
    failed = runner.record_case(args, case, 2)
    assert failed['exit_code'] == 1
    assert [turn['status'] for turn in failed['turns']] == ['completed', 'failed']
    old_folder = args.output / 'T-fixture-run2'
    original_bytes = {path.name: path.read_bytes() for path in old_folder.iterdir()}

    # The new run launches a fresh subprocess and resubmits both turns.
    # Undo the first launch wrapper so setup_protocol cannot wrap it twice.
    monkeypatch.undo()
    setup_protocol(tmp_path, monkeypatch)
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    (snapshot / 'SKILL.md').write_text('protocol fixture', encoding='utf-8')
    cases_file = tmp_path / 'cases.json'
    cases_file.write_text(json.dumps({'cases': [case, {'id': 'unselected', 'prompt': 'omit'}]}), encoding='utf-8')
    output = tmp_path / 'retry-campaign'
    monkeypatch.setattr(sys, 'argv', ['runner', '--cli', 'fixture', '--python', sys.executable,
        '--snapshot', str(snapshot), '--commit', 'fixture-commit', '--model', 'fixture-model',
        '--cases', str(cases_file), '--case-id', case['id'], '--output', str(output),
        '--repetitions', str(count), '--repetition-start', str(start), '--workers', '1'])
    assert runner.main() == 0
    metadata = json.loads((output / 'run.json').read_text())
    assert metadata['repetition_start'] == start
    assert metadata['selected_case_ids'] == ['T-fixture']
    assert metadata['snapshot_unchanged'] is True
    assert metadata['execution_failures'] == 0
    assert sorted(path.name for path in output.glob('recording-run*.json')) == [
        f'recording-run{rep}.json' for rep in expected]
    for repetition in expected:
        recording = json.loads((output / f'recording-run{repetition}.json').read_text())
        row, = recording['responses']
        assert row['repetition'] == repetition
        assert [turn['prompt'] for turn in row['turns']] == ['first', 'second']
        assert [turn['status'] for turn in row['turns']] == ['completed', 'completed']
        assert (output / f'T-fixture-run{repetition}' / 'events.jsonl').exists()
    assert {path.name: path.read_bytes() for path in old_folder.iterdir()} == original_bytes
    with pytest.raises(FileExistsError):
        runner.main()


@pytest.mark.parametrize('start', [0, -1])
def test_cli_rejects_invalid_repetition_start_before_creating_output(tmp_path, monkeypatch, start):
    output = tmp_path / 'invalid-run'
    monkeypatch.setattr(sys, 'argv', ['runner', '--cli', 'fixture', '--python', sys.executable,
        '--snapshot', str(tmp_path / 'snapshot'), '--commit', 'fixture-commit',
        '--cases', str(tmp_path / 'unused.json'), '--output', str(output),
        '--repetition-start', str(start)])
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert not output.exists()
