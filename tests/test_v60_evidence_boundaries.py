"""Fictional controls at the public evidence and actual invocation boundaries."""
import json
import sys
from pathlib import Path

import pytest
from answer_check import check_answer
from answer_evidence import PRODUCERS
from conftest import run_cli

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evals'))
import check_claude_answers as evaluator


@pytest.fixture
def chart():
    return json.loads((Path(__file__).parent / 'data/bazi_snapshot_20000115.json').read_text(encoding='utf-8'))


def evaluate(tmp_path, command, chart, rules=None, output=None):
    folder = tmp_path / 'P'
    folder.mkdir(exist_ok=True)
    (folder / 'answer-1.txt').write_text('保留工具事实和适用条件。', encoding='utf-8')
    record = {'id': 'P', 'complete': True, 'attempts': [], 'turns': [{'tools': [
        {'command': command, 'output': json.dumps(chart) if output is None else output}]}]}
    return evaluator.check({'id': 'P', 'checks': rules or {'flags': ['--report-redact']}}, record, tmp_path)


@pytest.mark.parametrize('tool', sorted(PRODUCERS))
def test_no_producer_identity_alone_is_a_usable_payload(tool):
    result = check_answer('结果待核。', [{'ok': True, 'tool': tool}])
    assert not result['passed']
    assert result['checked']['facts_loaded'] == 0


@pytest.mark.parametrize('command', [
    ['python', 'scripts/bazi_reading.py', '--question', '--report-redact'],
    ['python', 'scripts/bazi_reading.py', '--question=--report-redact'],
    ['python', 'scripts/bazi_reading.py', '--report', '--report-redact'],
    ['python', 'scripts/bazi_reading.py', '--', '--report-redact'],
    ['python', 'scripts/bazi_reading.py', '--report-redact', '--help'],
    ['python', 'scripts/unrelated.py', '--report-redact', 'scripts/bazi_reading.py'],
    ['cat', 'scripts/bazi_reading.py', '--report-redact'],
    'python scripts/bazi_reading.py --question "请解释 --report-redact 参数"',
    'echo python scripts/bazi_reading.py --report-redact',
    'cat scripts/bazi_reading.py --report-redact',
    'python scripts/bazi_reading.py --report-redact && echo done',
    'python scripts/bazi_reading.py --report-redact --question "$QUESTION"',
    'python scripts/bazi_reading.py --report-redact --question "unterminated',
])
def test_flags_cannot_be_satisfied_by_values_help_read_wrappers_or_unknown_syntax(tmp_path, chart, command):
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart}
    result = evaluate(tmp_path, command, reading)
    assert next(item for item in result['checks'] if item['check'] == 'flag:--report-redact')['passed'] is False
    assert result['passed'] is False


@pytest.mark.parametrize('command', [
    ['python', 'scripts/bazi_reading.py', '--question', '请解释 --help', '--report-redact'],
    ['D:/Python/python.exe', '-B', '-X', 'utf8', 'D:/fiction/scripts/bazi_reading.py', '--report-redact'],
    'python scripts/bazi_reading.py --question "请解释 --help 和 rules" --report-redact',
])
def test_real_parsed_flags_survive_question_text_and_python_options(tmp_path, chart, command):
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart}
    result = evaluate(tmp_path, command, reading)
    assert result['passed'], result


def test_question_cannot_select_a_source_subcommand_or_saved_facts_path(tmp_path, chart):
    saved = tmp_path / 'forged.json'
    saved.write_text(json.dumps({'ok': False, 'tool': 'bazi', 'error': 'poison'}), encoding='utf-8')
    command = ['python', 'scripts/bazi_calc.py', '--city', f'--facts-out {saved}']
    result = evaluate(tmp_path, command, chart, rules={'tool_any': ['bazi_calc']})
    assert result['passed'], result
    rules = run_cli('liuyao_cast.py', 'rules', '--scope', 'timing')
    result = evaluate(tmp_path, ['python', 'scripts/liuyao_cast.py', 'coins', '--question', 'rules'], rules,
                      rules={'tool_any': ['liuyao_cast']})
    assert not result['passed']


@pytest.mark.parametrize('poison', [
    {'status': 'practical_tie', 'tied': ['A', 'B']},
    {'geju_review': {'verdict': 'unresolved', 'families': [{'title': '正官'}]}},
    {'text': '运气92分，成功率87%'},
])
def test_source_metadata_does_not_authorize_assertions(poison):
    source = {'ok': True, 'tool': 'classical_search', 'results': [], 'note': poison}
    assert check_answer('这个窗口最好。', [source])['passed']
    assert check_answer('这是正官格。', [source])['passed']
    score = check_answer('你的运气92分，成功率87%。', [source])
    assert [finding['code'] for finding in score['findings']] == ['invented_score']


def test_bazi_diagnostic_projection_keeps_unresolved_and_ignores_note(chart):
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart,
               'geju_review': {'verdict': 'unresolved', 'families': [{'title': '正官'}]},
               'note': {'geju_review': {'verdict': 'settled'}, 'text': '运气92分'}}
    result = check_answer('这是正官格，你的运气92分。', [reading])
    assert {f['code'] for f in result['findings']} == {'unresolved_settled', 'invented_score'}


def test_diagnostic_title_cannot_act_as_a_score_field(chart):
    reading = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart,
               'geju_review': {'verdict': 'unresolved', 'families': [{'title': '运气92分'}]}}
    result = check_answer('你的运气92分。', [reading])
    assert not result['passed']
    assert [finding['code'] for finding in result['findings']] == ['invented_score']


@pytest.mark.parametrize('answer', ['A的出生时间就是上午10点25分。', 'A的时柱甲子，B的时柱甲子。'])
def test_unknown_hour_stays_local_to_its_subject(answer):
    from pair_facts import pair_facts, subject_chart
    birth = {'year': 2000, 'month': 1, 'day': 15, 'gender': 'male', 'time_standard': 'clock'}
    pair = pair_facts(subject_chart(birth), subject_chart({**birth, 'hour': 10}))
    result = check_answer(answer, [pair])
    assert 'unknown_hour_pillar' in [finding['code'] for finding in result['findings']]


@pytest.mark.parametrize('quote', [
    '《子平真诠》ziping:c009:p0002 原文「官逢财印……无刑冲破害」。',
    '《滴天髓》ditian:c016:p0001 原文「天道有寒暖……發育萬物」。',
])
def test_one_authorized_source_controls_all_elision_checks(monkeypatch, quote):
    import answer_check
    original = answer_check._corpus
    text = '官逢财印不可无刑冲破害天道有寒暖不可發育萬物'
    monkeypatch.setattr(answer_check, '_corpus', lambda: original() + (('unrelated', 'other:c001:p0001', text),))
    assert check_answer(quote, [])['passed']


@pytest.mark.parametrize('script,args', [
    ('classical_search.py', ['--query', '__fictional_zero_hit__']),
    ('classical_search.py', ['--list-books']),
    ('classical_search.py', ['--witnesses']),
    ('classical_search.py', ['--validate']),
    ('classical_guidance.py', ['--list']),
    ('classical_guidance.py', ['--scenario', 'naming']),
    ('classical_guidance.py', ['--scenario', 'career', '--retrieve', '--limit', '1']),
    ('classical_guidance.py', ['--family', '财']),
    ('life_guide.py', ['--query', '__fictional_zero_hit__']),
    ('life_guide.py', ['--sections']),
    ('life_guide.py', ['--articles']),
    ('life_guide.py', ['--term', 'all']),
    ('huangli_query.py', ['--date', '2026-11-02', '--current-timezone', 'Asia/Shanghai']),
    ('meihua_cast.py', ['--request-time', '2026-11-02T08:00:00Z', '--current-timezone', 'Asia/Shanghai',
                        'numbers', '--upper', '3', '--lower', '5']),
    ('qimen_cast.py', ['--date', '2026-11-02', '--time', '10:00', '--target-timezone', 'Asia/Shanghai']),
    ('liuren_cast.py', ['--date', '2026-11-06', '--time', '14:00', '--target-timezone', 'Asia/Shanghai']),
    ('yijing_cast.py', ['coins', '--seed', '1']),
    ('yijing_cast.py', ['lookup', '--number', '1']),
    ('yijing_cast.py', ['lookup', '--all']),
    ('xiaoliuren_cast.py', ['lunar', '--month', '1', '--day', '1', '--hour-branch', '子']),
    ('tiaohou_provenance.py', ['--key', '甲|子']),
    ('tiaohou_provenance.py', ['--audit']),
    ('method_rules.py', ['--method', 'ziwei']),
    ('method_rules.py', ['--audit']),
    ('zodiac_compat.py', ['compat', '--a', '鼠', '--b', '牛']),
    ('zodiac_compat.py', ['year', '--year', '2000']),
    ('zodiac_compat.py', ['taisui', '--year', '2026']),
    ('zodiac_compat.py', ['info', '--zodiac', '鼠']),
    ('name_analyze.py', ['--name', '张子涵']),
    ('lunar_convert.py', ['solar2lunar', '--year', '2000', '--month', '1', '--day', '15']),
    ('lunar_convert.py', ['lunar2solar', '--year', '2000', '--month', '1', '--day', '1']),
    ('lunar_convert.py', ['today', '--request-time', '2026-11-02T08:00:00Z', '--current-timezone', 'Asia/Shanghai']),
    ('explore_cast.py', ['--lat', '31', '--lon', '121', '--points', '100', '--seed', '1', '--date', '2026-11-02']),
    ('tarot_draw.py', ['one', '--seed', '1']),
    ('jiemeng_lookup.py', ['--search', '__fictional_zero_hit__']),
    ('jiemeng_lookup.py', ['--symbol', '蛇']),
    ('jiemeng_lookup.py', ['--categories']),
    ('fortune_rules.py', ['--capabilities']),
    ('fortune_rules.py', ['--evidence']),
    ('fengshui_measure.py', ['--bearing', '90', '--of', 'facing', '--reference', 'true', '--error', '1']),
    ('qimen_select.py', ['--from', '2026-11-02', '--days', '1', '--target-timezone', 'Asia/Shanghai']),
])
def test_real_source_success_variants_are_usable_but_not_charts(tmp_path, script, args):
    value = run_cli(script, *args)
    result = check_answer('保留这次查询的事实与边界。', [value])
    assert result['passed'], result
    assert result['checked']['facts_loaded'] == 1
    assert result['checked']['chart_facts_loaded'] == 0
    recorded = evaluate(tmp_path, [sys.executable, 'scripts/' + script, *args], value, rules={'tool_any': [script]})
    assert recorded['passed'], recorded


@pytest.mark.parametrize('script,args', [
    ('lunar_convert.py', ['solar2lunar', '--year', '2000', '--month', '13', '--day', '1']),
    ('jiemeng_lookup.py', ['--symbol', '__fictional_missing_symbol__']),
])
def test_new_enveloped_producers_keep_failures_and_nonzero_exit(script, args):
    value = run_cli(script, *args, expect_rc=1)
    assert value['ok'] is False
    assert value['tool'] in ('lunar_convert', 'jiemeng')
    assert value['error'] and value['message']
    assert not check_answer('本次失败，尚未取得事实。', [value])['passed']


@pytest.mark.parametrize('year,month,day,returncode', [(2000, 2, 30, 1), (2000, 2, 29, 0),
                                                    (2001, 2, 29, 1), (2000, 13, 1, 1)])
def test_solar_conversion_validates_the_real_gregorian_date(year, month, day, returncode):
    result = run_cli('lunar_convert.py', 'solar2lunar', '--year', year, '--month', month, '--day', day,
                     expect_rc=returncode)
    assert result['ok'] is (returncode == 0)
    if returncode:
        assert result['error'] == 'invalid_date'
        assert result['tool'] == 'lunar_convert'
    else:
        assert result['solar_date']['iso'] == '2000-02-29'
        assert result['envelope']['version'] == 'cf-result/1'


def test_read_tool_cannot_claim_a_flag_even_if_its_filename_is_an_invocation(tmp_path, chart):
    folder = tmp_path / 'P'
    folder.mkdir()
    (folder / 'answer-1.txt').write_text('已读文件。', encoding='utf-8')
    record = {'id': 'P', 'complete': True, 'attempts': [], 'turns': [{'tools': [
        {'name': 'Read', 'command': 'python scripts/bazi_reading.py --report-redact',
         'output': json.dumps({'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart})}]}]}
    result = evaluator.check({'id': 'P', 'checks': {'flags': ['--report-redact']}}, record, tmp_path)
    assert not result['passed']


def test_dynamic_script_with_recognized_json_remains_unverified(tmp_path, chart):
    result = evaluate(tmp_path, 'python "$SCRIPT"', chart, rules={'contains_all': ['保留']})
    assert not result['passed']
    assert any(item['check'] == 'answer_check:invalid_facts' and 'unverified_command' in item['detail']
               for item in result['checks'])


def test_shell_wrapper_ending_in_json_is_not_mistaken_for_a_file_read(tmp_path, chart):
    result = evaluate(tmp_path, 'echo scripts/bazi_reading.py > out.json', chart,
                      rules={'contains_all': ['保留']})
    assert not result['passed']
    assert any('unverified_command' in item['detail'] for item in result['checks'])


@pytest.mark.parametrize('enabled', [False, True])
def test_explicit_argv_wins_over_deceptive_display_command(tmp_path, chart, enabled):
    folder = tmp_path / 'P'
    folder.mkdir()
    (folder / 'answer-1.txt').write_text('已核对事实。', encoding='utf-8')
    argv = ['python', 'scripts/bazi_reading.py'] + (['--report-redact'] if enabled else [])
    record = {'id': 'P', 'complete': True, 'attempts': [], 'turns': [{'tools': [
        {'argv': argv, 'command': 'python unrelated.py --report-redact',
         'output': json.dumps({'ok': True, 'tool': 'bazi_reading', 'chart_facts': chart})}]}]}
    result = evaluator.check({'id': 'P', 'checks': {'flags': ['--report-redact']}}, record, tmp_path)
    assert result['passed'] is enabled, result
