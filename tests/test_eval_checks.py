"""The recorder keeps tool outputs and the mechanical check uses them."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evals'))
import check_claude_answers  # noqa: E402
import run_claude_cases  # noqa: E402

CHART = {'ok': True, 'tool': 'bazi_reading',
         'chart_facts': {'hour_known': True, 'four_pillars': {'day': {'ganzhi': '壬申', 'stem': '壬'}}}}


def test_recorder_attaches_tool_results_to_their_calls():
    events = [
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 't1', 'name': 'Bash', 'input': {'command': 'python scripts/bazi_reading.py'}}]}},
        {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 't1', 'content': [{'type': 'text', 'text': json.dumps(CHART)}]}]}},
    ]
    turn = run_claude_cases._parse([json.dumps(e) for e in events])
    assert json.loads(turn['tools'][0]['output'])['tool'] == 'bazi_reading'


def _run(tmp_path, answer, tools):
    folder = tmp_path / 'X1'
    folder.mkdir()
    (folder / 'answer-1.txt').write_text(answer, encoding='utf-8')
    record = {'id': 'X1', 'complete': True, 'attempts': [], 'turns': [{'tools': tools}]}
    return check_claude_answers.check({'id': 'X1', 'checks': {}}, record, tmp_path)


def test_wrong_pillar_fails_when_tool_output_was_recorded(tmp_path):
    tools = [{'command': 'python scripts/bazi_reading.py', 'output': json.dumps(CHART)}]
    result = _run(tmp_path, '日柱甲子。', tools)
    failed = [c['check'] for c in result['checks'] if not c['passed']]
    assert 'answer_check:pillar_mismatch' in failed


def test_missing_tool_output_is_reported_not_passed(tmp_path):
    result = _run(tmp_path, '日柱甲子。', [{'command': 'python scripts/bazi_reading.py'}])
    assert not result['passed']
    assert any(c['check'] == 'tool_facts_recorded' and not c['passed'] for c in result['checks'])
