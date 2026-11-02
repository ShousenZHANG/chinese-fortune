"""第九轮外部核验的 26 项发现，各留一条回归：判定条件照核验方给的判据写。"""
import json
import re
from pathlib import Path

import pytest
from answer_check import check_answer
from conftest import run_cli

BAZI = ['--gender', 'male', '--timezone', 'Asia/Shanghai', '--time-standard', 'clock']


def test_r1_qm_001_flawed_use_without_zhi_fu_is_not_an_auspicious_hour():
    got = run_cli('qimen_select.py', '--from', '2026-11-03', '--days', '1', '--target-timezone', 'Asia/Shanghai')
    windows = [c['window'] for c in got['candidates']]
    assert '00:00–01:00' not in windows and '05:00–07:00' not in windows
    for c in got['candidates']:
        assert all(a['name'] != '三奇得使' or 'flaw' not in a for a in c['auspicious'])


def test_r9_feng_01_say_keeps_the_input_north_and_the_converted_bearing():
    got = run_cli('fengshui_measure.py', '--bearing', 80, '--of', 'facing', '--reference', 'magnetic',
                  '--declination', 15, '--error', 1)
    assert '按磁北' in got['say'] and '真北 95°' in got['say'] and '按真北' not in got['say']
    assert got['tradition']['facing']['bearing'] == 95


def test_r9_name_01_layers_say_which_strokes_are_estimated():
    got = run_cli('name_analyze.py', '--name', '王𠮷')
    layer = next(x for x in got['layers']['computed'] if x['aspect'] == '逐字笔画')
    assert layer['estimated'] == ['𠮷'] and '估算' in layer['system']
    assert run_cli('name_analyze.py', '--name', '王𠮷', '--strict', expect_rc=1)['error'] == 'missing_strokes'
    known = run_cli('name_analyze.py', '--name', '张子涵')
    assert next(x for x in known['layers']['computed'] if x['aspect'] == '逐字笔画')['estimated'] == []


@pytest.mark.parametrize('quote_fact', [{'ok': False, 'tool': 'bazi_reading', 'text': '官星得禄，富贵双全，必主大吉'},
                                        {'ok': False, 'tool': 'bazi_reading', 'message': '官星得禄，富贵双全，必主大吉'},
                                        {'ok': True, 'tool': 'classical_search', 'results': [],
                                         'note': '官星得禄，富贵双全，必主大吉'}])
def test_r9_checker_facts_01_error_envelopes_and_notes_do_not_launder_quotes(quote_fact):
    answer = '《子平真诠》：「官星得禄，富贵双全，必主大吉」。这里只核对所引原文。'
    assert check_answer(answer, [quote_fact])['passed'] is False
    assert check_answer('《遁甲演义》：「如遇本旬直符同臨其上方可用之而吉也」。', [])['passed'] is True


@pytest.mark.parametrize('answer,flag', [
    ('《子平真詮》原文：「若以兩合一……，則全無爭妬。」', True),           # 删去条件「而隔位」
    ('《子平真詮》原文：「若以兩合一而隔位，則全無爭妬。」', False),
    ('《增刪卜易》原文：「元神𨿽生用神，……方可生得用神。」', True),       # 删去「須要旺相」
    ('《增刪卜易》原文：「但宜吉事逢之，事必就，……宜凶事逢之，事之難結。」', True),  # 删去「不」
    ('《欽定協紀辨方書》原文：「廣聖厯曰歲破者太歲所衝之辰也其地……可興造移徙嫁娶逺行」', True),
])
def test_r9_checker_elision_01_dropped_conditions_and_negators(answer, flag):
    assert (check_answer(answer, [])['passed'] is False) is flag


def test_r2_checker_negation_01_denied_guarantee_is_not_a_certainty_claim():
    assert check_answer('这条规则并没有作出任何保证合同顺利的承诺。', [])['passed'] is True
    assert check_answer('这条规则保证合同顺利。', [])['passed'] is False


def test_r2_checker_new_fields_01_new_check_fields_are_enforced(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('checker', Path(__file__).resolve().parents[1] / 'evals' /
                                                  'check_claude_answers.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    (tmp_path / 'P').mkdir()
    (tmp_path / 'P' / 'answer-1.txt').write_text('这里只提供无关文字。', encoding='utf-8')
    (tmp_path / 'P' / 'report.html').write_text('<p>PRIVATE</p>', encoding='utf-8')
    record = {'id': 'P', 'complete': True, 'turns': [{'tools': [], 'result': {}}], 'attempts': [{'result': {}}]}
    for checks in ({'contains_all': ['缺']}, {'flags': ['--report-redact']}, {'file_must_not_contain': ['PRIVATE']},
                   {'must_ask': '问关系'}):
        assert checker.check({'id': 'P', 'checks': checks}, record, tmp_path)['passed'] is False, checks
    assert checker.check({'id': 'P', 'checks': {'contains_all': ['无关']}}, record, tmp_path)['passed'] is True


def test_r9_lbh_02_a_moved_qi_yun_invalidates_the_old_start():
    from birth_correction import correct
    base = {'year': 2000, 'month': 1, 'day': 1, 'hour': 12, 'minute': 0, 'gender': 'male', 'time_standard': 'clock'}
    got = correct({**base, 'timezone': 'Asia/Shanghai'}, {**base, 'timezone': 'America/New_York'})
    assert got['before']['qi_yun_start'] != got['after']['qi_yun_start']
    assert got['invalidated'] == ['起运时刻、各步大运的起止年龄与年份']
    assert '原先关于起运时刻' in got['say'][-1]


def test_r9_lbh_04_and_age_01_death_date_checks_and_age_at_death():
    early = run_cli('bazi_calc.py', '--year', 2000, '--month', 6, '--day', 1, '--hour', 12, *BAZI,
                    '--death-date', '2000-01-01', expect_rc=1)
    assert early['error'] == 'invalid_input'
    got = run_cli('bazi_reading.py', '--year', 1940, '--month', 1, '--day', 30, '--hour', 12, *BAZI,
                  '--death-date', '1995-06-01')
    assert got['chart_facts']['age_at_request']['full_years'] == 55


def test_r9_lad02_no_personal_reading_after_death():
    got = run_cli('bazi_reading.py', '--year', 1940, '--month', 1, '--day', 30, '--hour', 12, *BAZI,
                  '--death-date', '1995-06-01', '--question', '2026年运势', '--as-of-year', '2026')
    assert [r['status'] for r in got['annual_reading']] == ['after_death']
    assert got['annual_reading'][0]['hits'] == []
    assert all(r['status'] == 'after_death' for r in got['luck_reading'])
    unknown = run_cli('bazi_reading.py', '--year', 1940, '--month', 1, '--day', 30, '--gender', 'male',
                      '--timezone', 'Asia/Shanghai', '--death-date', '1995-06-01', '--question', '2026年运势',
                      '--as-of-year', '2026')
    assert [r['status'] for r in unknown['annual_reading']] == ['after_death']


def test_r9_lad03_report_table_marks_the_death_cut(tmp_path):
    report = tmp_path / 'r.md'
    run_cli('bazi_reading.py', '--year', 1940, '--month', 1, '--day', 30, '--hour', 12, *BAZI,
            '--death-date', '1995-06-01', '--report', report, '--report-style', 'professional')
    text = report.read_text(encoding='utf-8')
    assert '1987–1995（卒年截止；原周期至 1996）' in text and '（卒年截止；原周期至 57）' in text


def test_r9_report_01_unknown_hour_reports_keep_candidates(tmp_path):
    args = ['--year', 2000, '--month', 2, '--day', 4, '--gender', 'male', '--timezone', 'Asia/Shanghai']
    pro, share = tmp_path / 'p.html', tmp_path / 's.html'
    run_cli('bazi_reading.py', *args, '--report', pro, '--report-style', 'professional')
    run_cli('bazi_reading.py', *args, '--report', share, '--report-redact')
    assert '候选 己卯/庚辰' in pro.read_text(encoding='utf-8')
    shared = share.read_text(encoding='utf-8')
    assert '己卯' not in shared and '庚辰' not in shared


def test_r9_priv_01_02_share_preview_drops_the_birth_walkthrough(tmp_path):
    report = tmp_path / 's.md'
    run_cli('bazi_reading.py', '--year', 2000, '--month', 1, '--day', 15, '--hour', 10, '--minute', 30,
            '--gender', 'male', '--longitude', 116.4, '--timezone', 'Asia/Shanghai', '--city', '北京',
            '--current-timezone', 'Asia/Shanghai', '--request-time', '2026-11-08T02:00:00Z',
            '--question', '请讲大运，列推算过程、真太阳时和起运换算', '--report', report, '--report-style', 'professional',
            '--report-redact')
    text = report.read_text(encoding='utf-8')
    assert 'Asia/' not in text and not re.search(r'UTC\s*[+-]\s*\d', text)
    assert not re.search(r'\d{3,}', re.sub(r'[a-z]+:c\d{3}:p\d{4}', '', text))  # 没有日差之类的长数字
    assert 'ziping:c025:p0010' in text and ':c□' not in text  # 段号是公开古籍的位置，照常可查


def test_r9_st02_broken_registry_uses_the_failure_envelope(monkeypatch, capsys):
    import rule_registry
    fake = rule_registry.Family('fake', '假族', 'no_such:thing', ('tests/no_such.py',), lambda: [])
    monkeypatch.setattr(rule_registry, 'FAMILIES', [fake])
    assert rule_registry.main(['--family', 'fake']) == 1
    out = json.loads(capsys.readouterr().out)
    assert out['ok'] is False and out['error'] == 'broken_chain' and out['broken'] and out['error_class'] == 'integrity'


def test_r9_st03_overlapping_values_are_masked_in_a_stable_order():
    from report_views import sensitive_values
    result = {'question': '', 'chart_facts': {'four_pillars': {}, 'solar_date': {'a': '12-34', 'b': '23-45'}}}
    assert sensitive_values(result) == ['12-34', '23-45']


def test_r9_lr_summary_01_she_hai_is_not_called_one_zei():
    got = run_cli('liuren_cast.py', '--date', '2026-11-06', '--time', '14:00', '--target-timezone', 'Asia/Shanghai')
    assert '涉害' in got['nine_gates_classification'] and '一贼为用' not in got['summary']
    assert [got['san_chuan'][k] for k in ('chu_chuan', 'zhong_chuan', 'mo_chuan')] == ['子', '申', '辰']


def test_r1_yilin_01_02_03_04_split_fixes():
    from yilin_lookup import lin
    texts = {(b, z): {v['book']: v for v in lin(b, z)['versions']} for b, z in
             [('井', '恆'), ('乾', '巽'), ('乾', '兌'), ('復', '鼎'), ('復', '震'), ('豐', '晉')]}
    assert texts[('井', '恆')]['yilin_siku']['text'].endswith('安泰')
    assert '兑' not in texts[('乾', '巽')]['yilin_siku']['text'] and texts[('乾', '兌')]['yilin_siku']['text']
    assert texts[('復', '鼎')]['yilin']['text'] and texts[('復', '震')]['yilin']['text']
    feng = texts[('豐', '晉')]['yilin']
    assert feng['text'] is None and feng['unplaced_in_this_ben'] and '归属未定' in feng['reason']


def test_r9_fort_scope_01_borrowed_method_is_said_as_a_comparison():
    from fortune_reading import read_request, render_answer
    request = {'intent': 'period', 'request_time': '2026-11-02T09:00:00+08:00', 'current_timezone': 'Asia/Shanghai',
               'question': '这两周事业怎么样',
               'period': {'start': '2026-11-02T00:00:00+08:00', 'end': '2026-11-16T00:00:00+08:00'},
               'event': {'scenario': 'career', 'timezone': 'Asia/Shanghai'},
               'participants': [{'id': 'me', 'confirmed': True, 'person': {
                   'birth': {'year': 1995, 'month': 9, 'day': 21, 'hour': 14, 'minute': 30, 'gender': 'male',
                             'timezone': 'Asia/Shanghai', 'time_standard': 'clock'}, 'time_certainty': 'exact'}}]}
    result = read_request(request)
    lead = render_answer(result).split('\n')[0]
    assert '借用协纪相主比较' in lead and '相主等级最高的' in lead and 'career' not in lead
    assert result['conclusion']['method_scope']['scenario_mapping'] == 'unverified'


def test_r9_st01_reverse_lookup_without_the_calendar_library_uses_the_failure_envelope(monkeypatch, capsys):
    import sys

    import pillars_to_dates
    monkeypatch.setitem(sys.modules, 'lunar_python', None)
    assert pillars_to_dates.main(['--year-pillar', '庚辰', '--month-pillar', '戊寅', '--day-pillar', '壬辰']) == 1
    out = json.loads(capsys.readouterr().out)
    assert out['ok'] is False and out['error'] == 'missing_dependency' and out['error_class'] == 'environment'


def test_sbck_variant_notes_running_on_from_the_verse_are_commentary():
    from yilin_lookup import lin
    sbck = {v['book']: v for v in lin('乾', '蹇')['versions']}['yilin']
    assert sbck['text'].endswith('亡羊失羔') and '一本云' not in sbck['text']
    assert '末句云' not in {v['book']: v for v in lin('渙', '漸')['versions']}['yilin']['text']
