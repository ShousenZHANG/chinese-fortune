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
                       'status': 'failed' if behavior == 'failed_turn' else 'completed'}}})
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
