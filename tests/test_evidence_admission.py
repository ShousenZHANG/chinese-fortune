"""The public checker and recorded-answer evaluator admit the same tool evidence."""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from answer_check import check_answer
from bazi_reading import chart_facts
from conftest import SCRIPTS, run_cli

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evals'))
import check_claude_answers  # noqa: E402

DATA = Path(__file__).parent / 'data'


@pytest.fixture
def chart():
    return json.loads((DATA / 'bazi_snapshot_20000115.json').read_text(encoding='utf-8'))


def _record(*outputs):
    return {'complete': True, 'attempts': [], 'turns': [{'tools': [
        {'command': 'python scripts/bazi_calc.py' if isinstance(value, dict) and value.get('tool') == 'bazi'
                    else 'python scripts/bazi_reading.py', 'output': json.dumps(value, ensure_ascii=False)}
        for value in outputs]}]}


def _evaluate(tmp_path, record, answer='日柱甲子。'):
    folder = tmp_path / 'X1'
    folder.mkdir()
    (folder / f"answer-{len(record['turns'])}.txt").write_text(answer, encoding='utf-8')
    return check_claude_answers.check({'id': 'X1', 'checks': {}}, record, tmp_path)


INVALID = [
    {'ok': True, 'tool': 'bazi_reading', 'chart_facts': {}},
    {'ok': True, 'tool': 'bazi', 'four_pillars': {}},
    {'ok': True, 'tool': 'ziwei', 'twelve_palaces': []},
    {'ok': True, 'tool': 'fortune_reading', 'participants': []},
    {'ok': True, 'tool': 'pair_facts', 'relations': []},
    {'ok': True, 'tool': 'liuyao', 'main_chart': {}},
    {'ok': True, 'tool': []},
    {'ok': True, 'tool': {'name': 'bazi'}},
    {'ok': True, 'tool': 'unknown_tool'},
    {'ok': True},
    {'tool': 'bazi', 'four_pillars': {'day': {'ganzhi': '甲子'}}},
    {'ok': False, 'tool': 'bazi', 'error': 'invalid_input',
     'four_pillars': {'day': {'ganzhi': '甲子'}}},
    {}, None, [], 'ordinary text',
]


@pytest.mark.parametrize('invalid', INVALID)
def test_public_checker_rejects_invalid_facts_without_using_their_pillars(invalid):
    result = check_answer('日柱甲子。', [invalid])
    assert not result['passed'], result
    assert result['checked']['facts_loaded'] == 0
    assert result['checked']['pillars_checked'] == 0
    assert [f['code'] for f in result['findings']] == ['invalid_facts']
    assert '0' in result['findings'][0]['detail']


def test_valid_chart_cannot_hide_an_invalid_sibling(chart):
    result = check_answer('日柱甲子。', [chart, INVALID[0]])
    assert not result['passed']
    assert result['checked']['facts_loaded'] == 1
    assert result['checked']['chart_facts_loaded'] == 1
    assert {f['code'] for f in result['findings']} == {'invalid_facts', 'pillar_mismatch'}


@pytest.mark.parametrize('facts', [None, {}, 'not a batch', 42])
def test_public_checker_rejects_a_malformed_facts_batch(facts):
    result = check_answer('盘面待核。', facts)
    assert not result['passed']
    assert result['checked']['facts_loaded'] == 0
    assert [f['code'] for f in result['findings']] == ['invalid_facts']


@pytest.mark.parametrize('invalid', INVALID[:12])
def test_invalid_recorded_outputs_do_not_count_as_charts_and_remain_visible(tmp_path, invalid):
    result = _evaluate(tmp_path, _record(invalid))
    assert not result['passed'], result
    checks = {c['check']: c['passed'] for c in result['checks']}
    assert checks['tool_facts_recorded'] is False
    assert checks['answer_check:invalid_facts'] is False


def test_recorded_valid_chart_does_not_silence_invalid_sibling(tmp_path, chart):
    result = _evaluate(tmp_path, _record(chart, INVALID[0]), '日柱壬申。')
    checks = {c['check']: c['passed'] for c in result['checks']}
    assert checks['tool_facts_recorded'] is False
    assert checks['answer_check:invalid_facts'] is False
    assert not result['passed']


@pytest.mark.parametrize('transport', ['stdout', 'numbered_read', 'facts_out', 'redirect'])
def test_real_chart_transports_keep_the_same_pillar_check(tmp_path, chart, transport):
    saved = tmp_path / 'chart.json'
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart_facts(chart)}
    text = json.dumps(reading, ensure_ascii=False, indent=1)
    saved.write_text(text, encoding='utf-8')
    command = 'python scripts/bazi_reading.py --year 2000'
    output = text
    if transport == 'facts_out':
        command += f' --facts-out "{saved}"'
        output = '白话草稿'
    elif transport == 'redirect':
        command += f' > "{saved}"'
        output = ''
    elif transport == 'numbered_read':
        output = '\n'.join(f'{i}\t{line}' for i, line in enumerate(text.splitlines(), 1))
    record = {'complete': True, 'attempts': [], 'turns': [{'tools': [{'command': command, 'output': output}]}]}
    result = _evaluate(tmp_path, record)
    checks = {c['check']: c['passed'] for c in result['checks']}
    assert checks['tool_facts_recorded'] is True
    assert checks['answer_check:pillar_mismatch'] is False


@pytest.mark.parametrize('content', [None, 'not json', '[]', '{"ok": false, "tool": "bazi"}'])
def test_explicit_facts_file_failures_are_visible(tmp_path, content):
    saved = tmp_path / 'facts.json'
    if content is not None:
        saved.write_text(content, encoding='utf-8')
    record = _record()
    record['turns'][0]['tools'] = [{'command': f'python scripts/bazi_reading.py --facts-out "{saved}"',
                                  'output': '白话草稿'}]
    result = _evaluate(tmp_path, record)
    failed = {c['check'] for c in result['checks'] if not c['passed']}
    assert {'tool_facts_recorded', 'answer_check:invalid_facts'} <= failed
    if content is None or content == 'not json':
        failure = next(c for c in result['checks'] if c['check'] == 'answer_check:invalid_facts')
        assert 'facts_unavailable' in failure['detail']


def test_latest_failed_chart_turn_cannot_reuse_an_earlier_chart(tmp_path, chart):
    record = _record(chart)
    record['turns'] += _record(INVALID[0])['turns']
    result = _evaluate(tmp_path, record, '日柱壬申。')
    failed = {c['check'] for c in result['checks'] if not c['passed']}
    assert {'tool_facts_recorded', 'answer_check:invalid_facts'} <= failed


def test_unrelated_command_json_does_not_become_rejected_evidence(tmp_path, chart):
    record = _record(chart)
    record['turns'][0]['tools'].append({'command': 'python utility.py', 'output': '{"hello": 1}'})
    result = _evaluate(tmp_path, record, '日柱壬申。')
    assert result['passed'], result


def test_zero_hit_source_output_is_valid_but_never_a_chart():
    facts = run_cli('classical_search.py', '--query', '__no_matching_passage_20261102__')
    assert facts['results'] == [] and facts['total_matches'] == 0
    result = check_answer('暂未找到可用条款。', [facts])
    assert result['passed']
    assert result['checked']['facts_loaded'] == 1
    assert result['checked']['chart_facts_loaded'] == 0


@pytest.mark.parametrize('facts', INVALID[:12])
def test_stdin_cli_returns_a_rejection_without_crashing(facts):
    done = subprocess.run([sys.executable, str(SCRIPTS / 'answer_check.py'), '--stdin'],
                          input=json.dumps({'answer': '日柱甲子。', 'facts': [facts]}, ensure_ascii=False),
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 1, done.stdout
    result = json.loads(done.stdout)
    assert not result['passed']
    assert result['findings'][0]['code'] == 'invalid_facts'


@pytest.mark.parametrize('script,args', [
    ('bazi_calc.py', ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male', '--years', '1']),
    ('bazi_reading.py', ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male', '--years', '1']),
    ('bazi_reading.py', ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male', '--years', '1', '--view', 'compact']),
    ('bazi_reading.py', ['--year', '2000', '--month', '1', '--day', '15', '--gender', 'male', '--years', '1']),
    ('bazi_reading.py', ['--year', '2026', '--month', '2', '--day', '4', '--gender', 'male', '--years', '1']),
    ('bazi_reading.py', ['--year', '2026', '--month', '2', '--day', '4', '--gender', 'male', '--years', '1', '--view', 'compact']),
    ('ziwei_calc.py', ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male', '--brief-palaces']),
    ('liuyao_cast.py', ['coins', '--lines', '7,8,9,6,7,7', '--date', '2026-11-02', '--time', '12:00', '--current-timezone', 'Asia/Shanghai']),
])
def test_real_producer_outputs_are_admitted(script, args):
    facts = run_cli(script, *args)
    result = check_answer('盘面留待结合条件解释。', [facts])
    assert result['passed'], result
    assert result['checked']['chart_facts_loaded'] == 1


@pytest.mark.parametrize('certainty', ['exact', 'unknown', 'approximate'])
def test_real_fortune_participants_preserve_birth_uncertainty(certainty):
    from fortune_reading import read_request

    birth = {'year': 2000, 'month': 1, 'day': 15, 'hour': 19, 'gender': 'male',
             'time_standard': 'clock', 'timezone': 'Asia/Shanghai'}
    person = {'birth': birth, 'time_certainty': certainty}
    if certainty == 'unknown':
        birth.pop('hour')
    if certainty == 'approximate':
        person['birth_time_range'] = {'start': '18:59', 'end': '19:01'}
    payload = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-10-07T07:00:00Z',
               'intent': 'period', 'period': {'start': '2026-10-08', 'end': '2026-10-09'},
               'event': {'scenario': 'outlook', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'},
               'participants': [{'id': 'A', 'confirmed': True, 'person': person}]}
    facts = read_request(payload)
    result = check_answer('保留各出生时段共同的事实。', [facts])
    assert result['passed'], result
    assert result['checked']['chart_facts_loaded'] == 1


def test_full_ziwei_snapshot_is_admitted():
    facts = json.loads((DATA / 'ziwei_snapshot_20000115.json').read_text(encoding='utf-8'))
    result = check_answer('十二宫事实待解释。', [facts])
    assert result['passed'], result
    assert result['checked']['chart_facts_loaded'] == 1


@pytest.mark.parametrize('variant', ['liuyao_rules', 'specialist', 'itinerary', 'birth_candidates', 'birth_correction', 'pillars_to_dates', 'fengshui_measure', 'qimen_select'])
def test_real_source_variants_are_admitted_without_counting_as_charts(variant):
    from answer_evidence import parse_evidence
    from fortune_reading import read_request

    birth = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'gender': 'male',
             'time_standard': 'clock', 'timezone': 'Asia/Shanghai'}
    if variant == 'liuyao_rules':
        facts = run_cli('liuyao_cast.py', 'rules', '--scope', 'timing')
    elif variant == 'birth_candidates':
        from birth_candidates import run

        facts = run({'birth': {'gender': 'male', 'time_standard': 'clock'},
                     'candidates': ['2000-01-15T10:00', '2000-01-15T11:00']})
    elif variant == 'birth_correction':
        from birth_correction import correct

        facts = correct(birth, {**birth, 'hour': 11})
    elif variant == 'pillars_to_dates':
        facts = run_cli('pillars_to_dates.py', '--year-pillar', '己卯', '--month-pillar', '丁丑',
                        '--day-pillar', '壬申', '--from-year', '2000', '--to-year', '2000')
    elif variant == 'fengshui_measure':
        facts = run_cli('fengshui_measure.py', '--bearing', '90', '--of', 'facing', '--reference', 'true', '--error', '1')
    elif variant == 'qimen_select':
        facts = run_cli('qimen_select.py', '--from', '2026-11-02', '--days', '1', '--target-timezone', 'Asia/Shanghai')
    else:
        payload = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-12T00:00:00Z',
                   'period': '下周', 'event': {'scenario': 'naming'},
                   'participants': [{'id': 'A', 'confirmed': True, 'person': {'birth': birth, 'time_certainty': 'exact'}}]}
        if variant == 'itinerary':
            payload['event'] = {'scenario': 'multiple_events', 'time_standard': 'clock'}
            payload['events'] = [
                {'id': 'interview', 'event': {'scenario': 'interview'}, 'duration_minutes': 60,
                 'candidates': [{'start': '2026-09-15T09:00', 'end': '2026-09-15T11:00'}]},
                {'id': 'travel', 'event': {'scenario': 'travel'}, 'duration_minutes': 30,
                 'travel_minutes_from_previous': 45,
                 'candidates': [{'start': '2026-09-15T10:30', 'end': '2026-09-15T12:00'}]}]
        facts = read_request(payload)
    parsed = parse_evidence([facts])
    assert parsed.facts == (facts,), parsed.problems
    assert parsed.chart_count == 0
    result = check_answer('已保留查询结果。', [facts])
    assert result['passed'], result
    assert result['checked']['facts_loaded'] == 1
    assert result['checked']['chart_facts_loaded'] == 0


@pytest.mark.parametrize('facts', [
    {'ok': True, 'tool': 'liuyao', 'rules': []},
    {'ok': True, 'tool': 'fortune_reading', 'status': 'specialist_required', 'capability': {}},
    {'ok': True, 'tool': 'fortune_reading', 'status': 'partial', 'natal_catalog': {}, 'events': [], 'itinerary': {}},
    {'ok': True, 'tool': 'birth_candidates', 'segments': []},
    {'ok': True, 'tool': 'birth_correction', 'before': {}, 'after': {}},
    {'ok': True, 'tool': 'pillars_to_dates', 'pillars': {}, 'candidates': []},
])
def test_empty_source_variants_are_rejected(facts):
    result = check_answer('结果待核。', [facts])
    assert not result['passed']
    assert result['checked']['facts_loaded'] == 0


def test_reference_subcommand_does_not_require_a_recorded_chart(tmp_path):
    facts = run_cli('liuyao_cast.py', 'rules', '--scope', 'timing')
    record = _record()
    record['turns'][0]['tools'] = [{'command': 'python scripts/liuyao_cast.py rules --scope timing',
                                  'output': json.dumps(facts, ensure_ascii=False)}]
    result = _evaluate(tmp_path, record, '已查询相应条款，仍需结合适用条件。')
    assert result['passed'], result
    assert 'tool_facts_recorded' not in {c['check'] for c in result['checks']}


def test_real_pair_with_unknown_subjects_may_have_zero_relations():
    from pair_facts import pair_facts, subject_chart

    birth = {'year': 2000, 'month': 1, 'day': 15, 'gender': 'male'}
    subject = subject_chart(birth)
    for key in subject['four_pillars']:
        subject['four_pillars'][key] = {'status': 'birth_time_required', 'candidate_ganzhi': []}
    facts = pair_facts(subject, deepcopy(subject), 'friendship')
    assert facts['relations'] == []
    result = check_answer('两人的柱位均待补，暂不判断。', [facts])
    assert result['passed'], result
    assert result['checked']['chart_facts_loaded'] == 1


def test_failed_unknown_time_probes_and_repeated_clock_windows_remain_undecided(chart):
    pillars = chart['four_pillars']
    pillars['year'] = {'status': 'birth_time_required', 'candidate_ganzhi': []}
    pillars['day'] = {'status': 'birth_time_required', 'candidate_ganzhi': ['壬申', '辛未'],
                      'candidate_windows': [{'ganzhi': None, 'clock': '01:00–01:59',
                                             'repeated_clock': {'first': '壬申', 'second': '辛未'}}]}
    pillars['hour'] = {'status': '时柱待补'}
    chart['hour_known'] = False
    result = check_answer('日柱可能为壬申或辛未，年柱待补，时柱待补。', [chart])
    assert result['passed'], result
    assert result['checked']['chart_facts_loaded'] == 1


@pytest.mark.parametrize('mutation', ['missing_pillar', 'bad_ganzhi', 'bad_candidates', 'bad_window'])
def test_malformed_pillar_payloads_do_not_count_as_charts(chart, mutation):
    pillars = chart['four_pillars']
    if mutation == 'missing_pillar':
        pillars.pop('month')
    elif mutation == 'bad_ganzhi':
        pillars['month'] = {'ganzhi': '甲丑'}
    elif mutation == 'bad_candidates':
        pillars['month'] = {'status': 'birth_time_required', 'candidate_ganzhi': '庚寅'}
    else:
        pillars['month'] = {'status': 'birth_time_required', 'candidate_ganzhi': ['庚寅'],
                            'candidate_windows': [{'ganzhi': '庚寅'}]}
    result = check_answer('月柱还需核查。', [chart])
    assert not result['passed']
    assert result['checked']['chart_facts_loaded'] == 0


def test_duplicate_palaces_and_line_positions_are_not_charts():
    ziwei = json.loads((DATA / 'ziwei_snapshot_20000115.json').read_text(encoding='utf-8'))
    ziwei['twelve_palaces'][1] = deepcopy(ziwei['twelve_palaces'][0])
    liuyao = {'ok': True, 'tool': 'liuyao', 'main_chart': {'hex_number': 1, 'hex_name': '乾',
               'lines': [{'position': 1} for _ in range(6)]}}
    for value in (ziwei, liuyao):
        result = check_answer('盘面还需核查。', [value])
        assert not result['passed']
        assert result['checked']['chart_facts_loaded'] == 0


@pytest.mark.parametrize('output', ['', 'Traceback: crash before JSON', '{broken json'])
def test_recorded_valid_chart_cannot_hide_missing_json_from_another_call(tmp_path, chart, output):
    record = _record(chart)
    record['turns'][0]['tools'].append({'command': 'python scripts/bazi_reading.py', 'output': output})
    result = _evaluate(tmp_path, record, '盘面待核。')
    assert not result['passed'], result
    failures = [c for c in result['checks'] if c['check'] == 'answer_check:invalid_facts']
    assert failures, result
    assert 'expected_json' in failures[0]['detail']
    if output:
        assert output in failures[0]['detail']


@pytest.mark.parametrize('failed_sibling', [False, True])
def test_recorded_facts_file_completes_only_its_own_call(tmp_path, failed_sibling):
    saved = tmp_path / 'chart.json'
    args = ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male',
            '--years', '1', '--facts-out', str(saved)]
    done = subprocess.run([sys.executable, str(SCRIPTS / 'bazi_reading.py'), *args],
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    record = _record()
    record['turns'][0]['tools'] = [
        {'command': f'python scripts/bazi_reading.py --facts-out "{saved}"', 'output': done.stdout}]
    if failed_sibling:
        record['turns'][0]['tools'].append(
            {'command': 'python scripts/bazi_reading.py', 'output': 'Traceback: crash before JSON'})
    result = _evaluate(tmp_path, record, '日柱壬申。')
    assert result['passed'] is (not failed_sibling), result


@pytest.mark.parametrize('mode', ['--help', '--markdown'])
def test_explicit_prose_modes_do_not_require_json(tmp_path, mode):
    command = ['bazi_reading.py', '--year', '2000', '--month', '1', '--day', '15',
               '--hour', '10', '--gender', 'male', '--years', '1', mode]
    done = subprocess.run([sys.executable, str(SCRIPTS / command[0]), *command[1:]],
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    record = _record()
    record['turns'][0]['tools'] = [{'command': 'python scripts/' + ' '.join(command), 'output': done.stdout}]
    result = _evaluate(tmp_path, record, '已查看工具说明或白话草稿。')
    assert result['passed'], result
    assert 'tool_facts_recorded' not in {c['check'] for c in result['checks']}


def test_explicit_failed_json_is_retained_even_with_valid_facts_file(tmp_path, chart):
    saved = tmp_path / 'chart.json'
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart_facts(chart)}
    saved.write_text(json.dumps(reading, ensure_ascii=False), encoding='utf-8')
    record = _record()
    record['turns'][0]['tools'] = [
        {'command': f'python scripts/bazi_reading.py --facts-out "{saved}"',
         'output': json.dumps({'ok': False, 'tool': 'bazi_reading', 'error': 'render_failed'})}]
    result = _evaluate(tmp_path, record, '盘面待核。')
    assert not result['passed'], result
    assert any('render_failed' in c['detail'] for c in result['checks'])


@pytest.fixture(params=['specialist', 'itinerary'])
def fortune_source(request):
    from fortune_reading import read_request

    birth = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'gender': 'male',
             'time_standard': 'clock', 'timezone': 'Asia/Shanghai'}
    payload = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-12T00:00:00Z',
               'period': '下周', 'event': {'scenario': 'naming'},
               'participants': [{'id': 'A', 'confirmed': True, 'person': {'birth': birth, 'time_certainty': 'exact'}}]}
    if request.param == 'itinerary':
        payload['event'] = {'scenario': 'multiple_events', 'time_standard': 'clock'}
        payload['events'] = [
            {'id': 'interview', 'event': {'scenario': 'interview'}, 'duration_minutes': 60,
             'candidates': [{'start': '2026-09-15T09:00', 'end': '2026-09-15T11:00'}]},
            {'id': 'travel', 'event': {'scenario': 'travel'}, 'duration_minutes': 30,
             'travel_minutes_from_previous': 45,
             'candidates': [{'start': '2026-09-15T10:30', 'end': '2026-09-15T12:00'}]}]
    facts = read_request(payload)
    assert facts['ok'] is True
    assert facts['status'] in ('specialist_required', 'partial')
    return facts


def test_recorded_fortune_source_variant_does_not_require_a_chart(tmp_path, fortune_source):
    record = _record()
    record['turns'][0]['tools'] = [{'command': 'python scripts/fortune_reading.py --stdin',
                                  'output': json.dumps(fortune_source, ensure_ascii=False)}]
    result = _evaluate(tmp_path, record, '请保留结果中的条件，需要时咨询相应专家。')
    assert result['passed'], result


def test_fortune_source_variant_cannot_excuse_another_missing_chart(tmp_path, fortune_source):
    record = _record()
    record['turns'][0]['tools'] = [
        {'command': 'python scripts/fortune_reading.py --stdin', 'output': json.dumps(fortune_source)},
        {'command': 'python scripts/bazi_reading.py', 'output': ''}]
    result = _evaluate(tmp_path, record, '盘面还需补充。')
    assert not result['passed'], result
    assert any(c['check'] == 'tool_facts_recorded' and not c['passed'] for c in result['checks'])
    assert any(c['check'] == 'answer_check:invalid_facts' for c in result['checks'])


def test_fortune_source_variant_cannot_complete_a_different_chart_call(tmp_path, chart, fortune_source):
    record = _record(chart)
    record['turns'][0]['tools'].append(
        {'command': 'python scripts/bazi_reading.py', 'output': json.dumps(fortune_source)})
    result = _evaluate(tmp_path, record, '盘面还需补充。')
    assert not result['passed'], result
    assert any('expected_chart' in c['detail'] for c in result['checks'])


@pytest.mark.parametrize('source_command', ['classical_search', 'bazi_reading'])
def test_recorded_source_completes_only_a_source_call(tmp_path, chart, source_command):
    source = run_cli('classical_search.py', '--query', '__no_matching_passage_20261102__')
    record = _record(chart)
    record['turns'][0]['tools'].append(
        {'command': f'python scripts/{source_command}.py', 'output': json.dumps(source)})
    result = _evaluate(tmp_path, record, '盘面还需补充。')
    assert result['passed'] is (source_command == 'classical_search'), result


@pytest.mark.parametrize('location', ['source', 'input', 'note'])
def test_public_pillar_check_ignores_unrelated_four_pillars(chart, location):
    poison = {'four_pillars': {'day': {'ganzhi': '甲子'}}}
    facts = [chart]
    if location == 'source':
        facts.append({'ok': True, 'tool': 'classical_search', 'results': [], 'total_matches': 0, 'echo': poison})
    else:
        chart[location] = poison
    result = check_answer('日柱甲子。', facts)
    assert not result['passed'], result
    assert [f['code'] for f in result['findings']] == ['pillar_mismatch']


def test_public_pillar_check_keeps_real_pair_subject_labels():
    from pair_facts import pair_facts, subject_chart

    birth = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'gender': 'male',
             'time_standard': 'clock', 'timezone': 'Asia/Shanghai'}
    a, b = subject_chart(birth), subject_chart({**birth, 'day': 16})
    facts = pair_facts(a, b, 'friendship')
    correct = check_answer('A的日柱壬申。B的日柱癸酉。', [facts])
    assert correct['passed'], correct
    assert correct['checked']['pillars_checked'] == 2
    wrong = check_answer('A的日柱癸酉。B的日柱壬申。', [facts])
    assert not wrong['passed'], wrong
    assert wrong['checked']['pillars_checked'] == 2
    assert [f['code'] for f in wrong['findings']] == ['pillar_mismatch', 'pillar_mismatch']


@pytest.mark.parametrize(('answer', 'checked', 'mismatches'), [
    ('| 人 | 日柱 |\n|---|---|\n| A | 壬申 |\n| B | 癸酉 |', 2, []),
    ('| 人 | 日柱 |\n|---|---|\n| A | 癸酉 |\n| B | 癸酉 |', 2, ['| A | 癸酉 |']),
    ('| 人 | 日柱 |\n|---|---|\n| A | 癸酉 |\n| B | 壬申 |', 2,
     ['| A | 癸酉 |', '| B | 壬申 |']),
    ('| 日柱 | 对象 | 备注 |\n|---|---|---|\n| 癸酉 | A方 | B的记录 |\n| 癸酉 | B方 | A的记录 |',
     2, ['| 癸酉 | A方 | B的记录 |']),
    ('| 人 | 日柱 |\n|---|---|\n| A | 壬申 |\n| A | 癸酉 |\n| B | 壬申 |',
     1, ['| B | 壬申 |']),
    ('| 人 | 日柱 |\n|---|---|\n| A | 壬申或癸酉 |\n| B | 壬申 |', 1, ['| B | 壬申 |']),
    ('| 人 | 日柱 | 时柱 |\n|---|---|---|\n| A | 壬申或癸酉 | 甲子 |\n| B | 壬申 | 丁巳 |',
     3, ['| A | 壬申或癸酉 | 甲子 |', '| B | 壬申 | 丁巳 |']),
    ('| 备注 | 日柱 |\n|---|---|\n| B的记录 | 壬申 |', 1, []),
    ('| 人 | 日柱 |\n|---|---|\n| B的记录 | 壬申 |', 1, []),
])
def test_public_pair_tables_bind_each_pillar_to_its_explicit_subject(answer, checked, mismatches):
    from pair_facts import pair_facts, subject_chart

    birth = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'gender': 'male',
             'time_standard': 'clock', 'timezone': 'Asia/Shanghai'}
    facts = pair_facts(subject_chart(birth), subject_chart({**birth, 'day': 16}), 'friendship')
    result = check_answer(answer, [facts])
    assert result['passed'] is (not mismatches), result
    assert result['checked']['pillars_checked'] == checked, result
    assert [(f['code'], f['excerpt']) for f in result['findings']] == [
        ('pillar_mismatch', row) for row in mismatches], result


@pytest.mark.parametrize('answer', [
    '| 时刻 | 日柱 |\n|---|---|\n| 10:00 | 甲子 |\n| 11:00 | 乙丑 |',
    '| 候选 | 日柱 |\n|---|---|\n| A | 甲子 |\n| B | 乙丑 |',
    '| 日柱 |\n|---|\n| 甲子 |\n| 乙丑 |',
])
def test_public_pillar_tables_preserve_moment_and_ambiguous_candidate_skips(chart, answer):
    result = check_answer(answer, [chart])
    assert result['passed'], result
    assert result['checked']['pillars_checked'] == 0


def test_public_pillar_table_rejects_fixed_hour_for_a_real_unknown_birth_hour():
    from pair_facts import pair_facts, subject_chart

    birth = {'year': 2000, 'month': 1, 'day': 15, 'gender': 'male'}
    facts = pair_facts(subject_chart(birth), subject_chart({**birth, 'hour': 10}), 'friendship')
    answer = '| 人 | 时柱 |\n|---|---|\n| A | 乙巳 |\n| B | 乙巳 |'
    result = check_answer(answer, [facts])
    assert not result['passed'], result
    assert result['checked']['pillars_checked'] == 2
    assert [(f['code'], f['excerpt']) for f in result['findings']] == [
        ('unknown_hour_pillar', '| A | 乙巳 |')], result


def test_public_pillar_check_preserves_real_unknown_hour_against_source_metadata():
    facts = run_cli('bazi_reading.py', '--year', '2000', '--month', '1', '--day', '15',
                    '--gender', 'male', '--years', '1')
    source = {'ok': True, 'tool': 'classical_search', 'results': [], 'total_matches': 0,
              'echo': {'four_pillars': {'hour': {'ganzhi': '甲子'}}, 'hour_known': True}}
    result = check_answer('时柱甲子。', [facts, source])
    assert not result['passed'], result
    assert [f['code'] for f in result['findings']] == ['unknown_hour_pillar']
    assert check_answer('时柱待补。', [facts, source])['passed']


def test_public_pillar_check_preserves_real_candidate_status_against_source_metadata():
    facts = run_cli('bazi_reading.py', '--year', '2026', '--month', '2', '--day', '4',
                    '--gender', 'male', '--years', '1', '--view', 'compact')
    assert facts['chart_facts']['four_pillars']['year']['status'] == 'birth_time_required'
    source = {'ok': True, 'tool': 'classical_search', 'results': [], 'total_matches': 0,
              'echo': {'four_pillars': {'year': {'ganzhi': '乙巳'}}}}
    result = check_answer('年柱乙巳。', [facts, source])
    assert not result['passed'], result
    assert [f['code'] for f in result['findings']] == ['undecided_pillar']
    assert check_answer('年柱可能为乙巳或丙午，仍待补时。', [facts, source])['passed']
