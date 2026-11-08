"""Answer-delivery gaps from the v6.0 host runs (R2 N02, N04, N08, N19, S06, S21), each with its fix."""
import json
import subprocess
import sys
from pathlib import Path

from answer_check import check_answer
from conftest import run_cli

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / 'skills/chinese-fortune/SKILL.md').read_text(encoding='utf-8')


def _ziwei_hour() -> dict:
    return run_cli('ziwei_calc.py', '--year', 2000, '--month', 1, '--day', 15, '--hour', 10, '--minute', 30,
                   '--gender', 'male', '--longitude', 116.4, '--timezone', 'Asia/Shanghai',
                   '--horoscope-date', '2026-10-26', '--horoscope-time', '10:00', '--brief-palaces')


def test_each_layer_says_where_its_transformed_stars_sit():
    chart = _ziwei_hour()
    rows = chart['horoscope']['liu_shi']['transformation_palaces']
    assert [(r['kind'], r['star']) for r in rows] == [('化禄', '太阴'), ('化权', '天同'), ('化科', '天机'), ('化忌', '巨门')]
    for row in rows:
        assert chart['main_stars_positions'][row['star']] == row['branch'] and row['natal_palace'].endswith('宫')


def test_listing_the_four_transformations_without_palaces_is_flagged():
    chart = _ziwei_hour()
    bare = '时干为丁，四化如下：\n| 化禄 | 太阴 |\n| 化权 | 天同 |\n| 化科 | 天机 |\n| 化忌 | 巨门 |'
    codes = [f['code'] for f in check_answer(bare, [chart])['findings']]
    assert 'sihua_palace_missing' in codes
    rows = chart['horoscope']['liu_shi']['transformation_palaces']
    full = '\n'.join(f"| {r['kind']} | {r['star']} | {r['branch']}宫（{r['natal_palace']}） |" for r in rows)
    assert 'sihua_palace_missing' not in [f['code'] for f in check_answer(full, [chart])['findings']]


def test_an_absence_is_said_with_the_scope_of_the_search():
    flagged = check_answer('不是《滴天髓》的原句。它出自《子平真诠》。', [])
    assert 'unscoped_absence_claim' in [f['code'] for f in flagged['findings']]
    scoped = check_answer('在随包转录本《子平真詮》里检索不到这句；这只说明转录本里没有。', [])
    assert 'unscoped_absence_claim' not in [f['code'] for f in scoped['findings']]


def test_the_three_yuan_match_shows_its_count_so_it_can_be_redone_by_hand():
    from sanyuan_hehun import match
    say = match({'year_pillar': '壬申', 'birth_year': 1992}, {'year_pillar': '甲戌', 'birth_year': 1994})['say']
    assert '下元男从四宫起甲子，逆数 8 步到壬申，落中五宫，男寄坤二' in say
    assert '下元女从八宫起甲子，顺数 10 步到甲戌，落离九宫' in say and '合成游魂' in say


def test_a_historical_offset_names_the_time_zone_database_that_gave_it():
    chart = run_cli('bazi_calc.py', '--year', 1988, '--month', 7, '--day', 1, '--hour', 12, '--gender', 'male',
                    '--timezone', 'Asia/Shanghai', '--time-standard', 'clock', '--no-shensha', '--no-geju',
                    '--no-yongshen')
    assert chart['timezone']['offset_hours'] == 9.0 and chart['timezone']['source'].startswith('IANA ')


def test_the_skill_asks_for_a_completion_path_and_partial_answers_under_a_time_budget():
    assert '补全路径（缺什么资料、要核哪条原文或哪个工具字段）' in SKILL
    assert '工具累计耗时超过约三分钟时，先答已确认的结论' in SKILL


def test_the_real_n08_answer_is_flagged():
    case = Path(r'D:/suanming/research/v60-finalization-20261102/R2/review-material-v2/packets/real-first-001/'
                r'public/cases/N08/answer-1.txt')
    if not case.is_file():   # the frozen evaluation record lives outside the repository
        return
    done = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'skills/chinese-fortune/scripts/answer_check.py'),
                           '--answer', '-'], input=case.read_text(encoding='utf-8'), capture_output=True,
                          text=True, encoding='utf-8')
    assert 'unscoped_absence_claim' in [f['code'] for f in json.loads(done.stdout)['findings']]


def test_a_bare_absence_is_an_error_and_a_named_denial_a_warning():
    bare = check_answer('这句不是《滴天髓》的原句。', [])['findings']
    assert [(f['code'], f['severity']) for f in bare] == [('unscoped_absence_claim', 'error')]
    named = check_answer('《子平真詮》中没有这句：财多身弱。', [])['findings']
    assert ('unscoped_absence_claim', 'warning') in [(f['code'], f['severity']) for f in named]


def test_a_marriage_answer_must_show_the_three_yuan_count():
    from pair_facts import pair_facts, subject_chart
    # 10:00, not 09:00: a birth on a 时辰 edge adds its own hour:A/hour:B items (R3 N19).
    a = subject_chart({'year': 1992, 'month': 6, 'day': 1, 'hour': 10, 'gender': 'male'})
    b = subject_chart({'year': 1994, 'month': 6, 'day': 1, 'hour': 10, 'gender': 'female'})
    facts = pair_facts(a, b)
    assert {e['id'] for e in facts['must_cover']} == {'sanyuan:male', 'sanyuan:female', 'sanyuan:relation'}
    short = check_answer('两人三元九宫合卦得' + facts['sanyuan_jiugong']['relation'] + '。', [facts])['findings']
    assert sum(f['code'] == 'must_cover_missing' and f['severity'] == 'error' for f in short) == 2
    full = check_answer(facts['sanyuan_jiugong']['say'], [facts])['findings']
    assert not [f for f in full if f['code'] == 'must_cover_missing']


def test_a_geju_question_must_say_the_structure_is_still_a_candidate():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading
    chart = calculate_bazi(build_parser().parse_args(['--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
                                                      '--gender', 'male', '--as-of-year', '2026']))
    reading = prepare_reading(chart, '我是什么格局')
    assert [e['id'] for e in reading['must_cover']] == ['geju:limit']
    assert 'must_cover' not in prepare_reading(chart, '看看八字')
    codes = [f['code'] for f in check_answer('你是正官格。', [reading])['findings']]
    assert 'must_cover_missing' in codes
    codes = [f['code'] for f in check_answer('正官格只是候选，还要核月令透干。', [reading])['findings']]
    assert 'must_cover_missing' not in codes


def test_a_passage_id_the_tools_never_returned_is_flagged_for_checking():
    facts = [{'ok': True, 'tool': 'classical_search', 'results': [{'passage_id': 'ziping:c008:p0001', 'text': '八字用神'}]}]
    findings = check_answer('依据 ziping:c008:p0001 与 ditian:c016:p0001。', facts)['findings']
    flagged = [f for f in findings if f['code'] == 'citation_not_in_facts']
    assert [f['excerpt'] for f in flagged] == ['ditian:c016:p0001'] and flagged[0]['severity'] == 'warning'


def test_several_methods_carry_a_time_budget():
    from question_router import route
    result = route('用八字和紫微一起看看我今年的事业')
    assert result['flow'] == 'multi_method' and result['time_budget_seconds'] == 180 and result['on_budget']


def test_with_the_tools_must_cover_one_missing_palace_is_an_error():
    chart = _ziwei_hour()
    assert chart['must_cover'][0]['check'] == 'sihua_palaces'
    rows = chart['horoscope']['liu_shi']['transformation_palaces']
    lines = [f"| {r['kind']} | {r['star']} | {r['branch']}宫 |" for r in rows]
    lines[0] = f"| {rows[0]['kind']} | {rows[0]['star']} |"
    findings = [f for f in check_answer('\n'.join(lines), [chart])['findings'] if f['code'] == 'sihua_palace_missing']
    assert findings and findings[0]['severity'] == 'error'
