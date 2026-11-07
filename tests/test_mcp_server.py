"""The MCP server speaks JSON-RPC over stdio and runs the real CLIs."""
import io
import json
import subprocess
import sys

import mcp_server
from conftest import SCRIPTS

BIRTH = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
         'timezone': 'Asia/Shanghai', 'longitude': 116.4}


def call(name, arguments):
    reply = mcp_server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                               'params': {'name': name, 'arguments': arguments}})
    result = reply['result']
    return result, result['content'][0]['text']


def test_initialize_echoes_a_supported_protocol_and_lists_capabilities():
    reply = mcp_server.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                               'params': {'protocolVersion': '2024-11-05', 'capabilities': {}}})
    assert reply['result']['protocolVersion'] == '2024-11-05'
    assert reply['result']['serverInfo']['name'] == 'chinese-fortune'
    assert 'answer_check' in reply['result']['instructions']
    newer = mcp_server.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': '2099-01-01'}})
    assert newer['result']['protocolVersion'] == mcp_server.PROTOCOLS[0]


def test_tool_list_has_schemas():
    tools = mcp_server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})['result']['tools']
    names = {t['name'] for t in tools}
    assert {'route_question', 'bazi_reading', 'ziwei_chart', 'pair_facts', 'answer_check', 'doctor', 'run_script'} <= names
    assert all(t['inputSchema']['type'] == 'object' for t in tools)


def test_bazi_reading_defaults_to_compact_and_returns_cli_json():
    result, text = call('bazi_reading', {**BIRTH, 'question': '看格局', 'as_of_year': 2026})
    data = json.loads(text)
    assert not result['isError'] and data['view'] == 'compact'
    assert data['chart_facts']['four_pillars']['day']['ganzhi'] == '壬申'


def test_stdin_tools_and_answer_check_with_facts():
    result, text = call('pair_facts', {'a': BIRTH, 'b': {**BIRTH, 'year': 2001, 'gender': 'female'}})
    assert not result['isError'] and json.loads(text)['tool'] == 'pair_facts'
    facts = json.loads(text)
    day = facts['subjects']['A']['four_pillars']['day']
    wrong_day = '甲子' if day != '甲子' else '乙丑'
    result, text = call('answer_check', {'answer': f'A方日柱{wrong_day}。', 'facts': [facts]})
    assert result['isError'] and any(f['code'] == 'pillar_mismatch' for f in json.loads(text)['findings'])
    # A marriage reply must also give the 三元九宫 count (must_cover); with it, the check passes.
    answer = f"A方日柱{day}。" + facts['sanyuan_jiugong']['say']
    result, text = call('answer_check', {'answer': answer, 'facts': [facts]})
    assert not result['isError'] and json.loads(text)['passed']


def test_answer_check_rejects_anonymous_partial_facts():
    facts = {'chart_facts': {'hour_known': True, 'four_pillars': {'day': {'ganzhi': '壬申'}}}}
    result, text = call('answer_check', {'answer': '日柱壬申。', 'facts': [facts]})
    assert result['isError'] and any(f['code'] == 'invalid_facts' for f in json.loads(text)['findings'])


def test_run_script_only_runs_shipped_runtime_scripts():
    result, text = call('run_script', {'script': 'personal_profiles.py', 'args': ['list']})
    assert result['isError'] and 'script must be one of' in text
    result, text = call('run_script', {'script': '../evals/package_smoke.py'})
    assert result['isError']
    result, text = call('run_script', {'script': 'zodiac_compat.py', 'args': ['info', '--zodiac', '马']})
    assert not result['isError'], text


def test_bad_arguments_are_tool_errors_not_crashes():
    result, text = call('bazi_reading', {'year': 2000})
    assert result['isError'] and 'missing arguments' in text
    result, text = call('doctor', {'surprise': 1})
    assert result['isError'] and 'unknown arguments' in text
    result, text = call('nope', {})
    assert result['isError']


def test_protocol_edges_and_resources():
    assert mcp_server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) is None
    assert mcp_server.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'nope'})['error']['code'] == -32601
    listed = mcp_server.handle({'jsonrpc': '2.0', 'id': 4, 'method': 'resources/list'})['result']['resources']
    assert listed[0]['uri'] == 'chinese-fortune://SKILL.md'
    read = mcp_server.handle({'jsonrpc': '2.0', 'id': 5, 'method': 'resources/read',
                              'params': {'uri': 'chinese-fortune://SKILL.md'}})
    assert read['result']['contents'][0]['text'].startswith('---')
    bad = mcp_server.handle({'jsonrpc': '2.0', 'id': 6, 'method': 'resources/read',
                             'params': {'uri': 'chinese-fortune://../.git/config'}})
    assert bad['error']['code'] == -32602


def test_serve_handles_a_session_line_by_line():
    lines = '\n'.join(json.dumps(m) for m in [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'ping'}]) + '\nnot json\n'
    out = io.StringIO()
    mcp_server.serve(io.StringIO(lines), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get('id') for r in replies] == [1, 2, None]
    assert replies[-1]['error']['code'] == -32700


def test_server_process_over_stdio():
    session = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                          'params': {'name': 'route_question', 'arguments': {'question': '用梅花易数起一卦'}}}) + '\n'
    done = subprocess.run([sys.executable, str(SCRIPTS / 'mcp_server.py')], input=session,
                          capture_output=True, text=True, encoding='utf-8', timeout=60)
    reply = json.loads(done.stdout)
    assert json.loads(reply['result']['content'][0]['text'])['method'] == 'meihua'


def test_wrongly_typed_requests_are_errors_and_the_session_continues():
    bad = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'run_script', 'arguments': {'script': 'doctor.py', 'args': None}}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': 'oops'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': {'x': 1}, 'arguments': {}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'answer_check', 'arguments': {'answer': 'x', 'facts': 'no'}}},
        {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'bazi_reading', 'arguments': {**BIRTH, 'year': '2000'}}},
        {'jsonrpc': '2.0', 'id': 6, 'method': 'ping'},
    ]
    out = io.StringIO()
    mcp_server.serve(io.StringIO('\n'.join(json.dumps(m) for m in bad) + '\n'), out)
    replies = {r['id']: r for r in map(json.loads, out.getvalue().splitlines())}
    assert set(replies) == {1, 2, 3, 4, 5, 6}
    assert replies[2]['error']['code'] == -32602
    assert all(replies[i]['result']['isError'] for i in (1, 3, 4, 5))
    assert replies[6]['result'] == {}


def test_failed_facts_serialisation_leaves_no_temp_file(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    result, text = call('answer_check', {'answer': 'x', 'facts': [{'k': 'SYNTHETIC', 'bad': '\ud800'}]})
    assert result['isError']
    assert list(tmp_path.iterdir()) == []


def test_deeply_nested_or_undecodable_input_does_not_end_the_session():
    deep = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"unused":' + '[' * 1200 + ']' * 1200 + '}}'
    session = deep + '\n' + json.dumps({'jsonrpc': '2.0', 'id': 999, 'method': 'ping'}) + '\n'
    done = subprocess.run([sys.executable, str(SCRIPTS / 'mcp_server.py')], input=session.encode('utf-8') + b'\xff\xfe\n'
                          + json.dumps({'jsonrpc': '2.0', 'id': 1000, 'method': 'ping'}).encode() + b'\n',
                          capture_output=True, timeout=60)
    replies = [json.loads(line) for line in done.stdout.decode('utf-8').splitlines()]
    assert done.returncode == 0
    assert [r.get('id') for r in replies][-2:] == [999, 1000] or 999 in [r.get('id') for r in replies]
    assert any(r.get('id') == 1000 for r in replies)


def test_ziwei_tool_accepts_the_school_switches():
    result, text = call('ziwei_chart', {**BIRTH, 'brightness': 'project4', 'geng_sihua': 'yang-wu-fu-tong',
                                        'leap_month': 'next'})
    assert not result['isError'], text
    school = json.loads(text)['school']
    assert {k: school[k] for k in ('brightness', 'geng_sihua', 'leap_month', 'late_zi_sect')} == {
        'brightness': 'project4', 'geng_sihua': 'yang-wu-fu-tong', 'leap_month': 'next', 'late_zi_sect': 2}
    result, text = call('ziwei_chart', {**BIRTH, 'school': 'nihai', 'kui_yue': 'quanshu-1', 'year_divide': 'lichun'})
    assert not result['isError'], text
    assert json.loads(text)['school']['preset'] == 'nihai'


def test_ziwei_school_enums_match_the_cli():
    import ziwei_calc
    assert {k: tuple(v['enum']) for k, v in mcp_server.ZIWEI_SCHOOLS.items()} == ziwei_calc.SCHOOL_CHOICES


def test_pair_facts_relation_passes_through():
    result, text = call('pair_facts', {'a': BIRTH, 'b': {**BIRTH, 'year': 2001, 'gender': 'female'},
                                       'relation': 'partnership'})
    assert not result['isError'] and json.loads(text)['relation']['type'] == 'partnership'
