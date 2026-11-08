"""Fixes from the 16-case regression of 2026-11-08 (reviews in research/optimal-plan-20261107)."""
import json
import subprocess
import sys

from answer_check import check_answer
from bazi_calc import build_parser, calculate_bazi
from bazi_derivation import hour_boundary, offset_sentence
from bazi_reading import prepare_reading
from conftest import SCRIPTS
from pair_facts import pair_facts, subject_chart

ROOT = SCRIPTS.parents[2]
MAN = {'year': 1992, 'month': 6, 'day': 1, 'hour': 10, 'minute': 0, 'gender': 'male', 'city': '北京'}
WOMAN = {'year': 1994, 'month': 9, 'day': 9, 'hour': 9, 'minute': 0, 'gender': 'female', 'city': '北京'}


def _ids(result: dict) -> list[str]:
    return [item['id'] for item in result.get('must_cover', [])]


def test_skill_asks_for_one_direct_call_per_script():
    # 78 of 79 unadmitted tool outputs came from piped, chained or redirected script calls.
    text = (ROOT / 'skills/chinese-fortune/SKILL.md').read_text(encoding='utf-8')
    assert '不接管道' in text and '`--facts-out ' in text and '`2>&1`' in text


def test_true_solar_sentence_names_the_direction():
    # T05 turned 「读数少 23.81 分钟」 into 「晚约 24 分钟」.
    earlier = offset_sentence({'total_offset_min': -23.81, 'clock_time': '10:30', 'true_solar_time': '10:06'})
    later = offset_sentence({'total_offset_min': 12.5, 'clock_time': '10:30', 'true_solar_time': '10:42'})
    assert earlier.startswith('真太阳时 10:06 比钟表 10:30 早 23.81 分钟')
    assert later.startswith('真太阳时 10:42 比钟表 10:30 晚 12.5 分钟')


def test_hour_boundary_is_found_from_the_time_actually_used():
    near = hour_boundary({'applied': True, 'clock_time': '09:00', 'true_solar_time': '08:49'})
    assert near['branch'] == '辰' and near['clock_branch'] == '巳'
    assert near['minutes_to_boundary'] == 11 and near['other_branch'] == '巳'
    assert '巳时' in near['say'] and '11 分钟' in near['say']
    assert hour_boundary({'applied': True, 'clock_time': '10:30', 'true_solar_time': '10:06'}) is None
    clock_only = hour_boundary({'applied': False, 'clock_time': '12:55'})
    assert clock_only['branch'] == '午' and clock_only['other_branch'] == '未'


def test_pair_facts_must_name_the_hour_a_near_boundary_birth_could_take():
    # N19: 女方 09:00 北京 is 08:49 true solar time, 辰时 by 11 minutes; the 辰 relations hold only for 辰.
    result = pair_facts(subject_chart(MAN), subject_chart(WOMAN))
    item = next(i for i in result['must_cover'] if i['id'] == 'hour:B')
    assert any('巳时' in alt for group in item['groups'] for alt in group)
    assert result['subjects']['B']['hour_boundary']['branch'] == '辰'
    assert 'hour:A' not in _ids(result)


def test_bazi_reading_flags_a_near_boundary_hour_only_when_there_is_one():
    near = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '1994', '--month', '9', '--day', '9', '--hour', '9', '--gender', 'female', '--city', '北京'])), '看八字')
    assert 'hour:boundary' in _ids(near) and near['chart_facts']['hour_boundary']['other_branch'] == '巳'
    far = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30', '--gender', 'male',
         '--timezone', 'Asia/Shanghai', '--longitude', '116.4'])), '我是什么格局')
    assert 'hour:boundary' not in _ids(far) and 'geju:limit' in _ids(far)


def _cast(*extra: str) -> dict:
    done = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/liuyao_cast.py', 'coins', '--lines', '6,9,7,8,9,6',
                           '--date', '2026-10-10', '--time', '21:45', '--target-timezone', 'Asia/Shanghai', *extra],
                          cwd=SCRIPTS.parent, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(done.stdout)


def test_a_target_rule_with_a_textual_conflict_must_be_answered_with_both_sides():
    # T31: the 世 line 戌 changes into 旬空 子; 化空 is 化凶 in c029 but 「動而化空…不爲空」 in c027.
    out = _cast('--question', '押金能否退回', '--target-position', '5')
    hit = next(h for h in out['rule_checks']['hits'] if h['id'] == 'liuyao-change-empty')
    assert hit['allowed_interpretation'] and 'zengshan:c027:p0003' in [c['passage_id'] for c in hit['conflicts']]
    item = next(i for i in out['must_cover'] if i['id'] == 'liuyao:liuyao-change-empty:5')
    assert 'zengshan:c027:p0003' in item['groups'][0] and '化空' in item['what']


def test_a_request_to_set_up_the_hexagram_must_list_every_line():
    # T08 left 六神 out of the table it was asked for.
    out = _cast('--question', '请装卦，看押金')
    rows = [i for i in out['must_cover'] if i['id'].startswith('liuyao:line')]
    assert len(rows) == 6
    top = next(i for i in rows if i['id'] == 'liuyao:line6')
    line = next(ln for ln in out['main_chart']['lines'] if ln['position'] == 6)
    assert top['groups'] == [[line['liu_shen']], [line['branch']], [line['liu_qin']]]
    assert not [i for i in _cast('--question', '押金能否退回').get('must_cover', []) if i['id'].startswith('liuyao:line')]


def test_commentary_quoted_as_the_book_itself_is_an_error():
    # N08: ditian:c006:p0002 is 《滴天髓辑要》 commentary, not 《滴天髓》 text.
    wrong = check_answer('《滴天髓》原文说「以刑衝破害論者，亦不可言格也」（ditian:c006:p0002）。', [])
    right = check_answer('《滴天髓辑要》的注文说「以刑衝破害論者，亦不可言格也」（ditian:c006:p0002）。', [])
    base = check_answer('《滴天髓》原文「財官印綬分偏正，兼論食傷格局定」（ditian:c006:p0001）。', [])
    assert 'commentary_cited_as_text' in [f['code'] for f in wrong['findings']]
    assert not [f for f in right['findings'] + base['findings'] if f['code'] == 'commentary_cited_as_text']


def test_a_classical_quote_needs_its_book_or_passage_id():
    # S21 quoted three 《子平真诠》 phrases as 「原文是…」 with neither.
    bare = check_answer('甲戌运按一般句算忌，原文是「不可逢合」。', [])
    named = check_answer('甲戌运按一般句算忌，《子平真诠》原文是「不可逢合」（ziping:c032:p0002）。', [])
    assert [f['code'] for f in bare['findings']] == ['quote_without_source']
    assert not [f for f in named['findings'] if f['code'] == 'quote_without_source']


def test_a_luck_cycle_or_year_brings_a_star_through_its_branch_too():
    # S06: 甲戌 运 for a 壬 day master has 食神 on the stem but 七杀 (戊) as the branch's main qi.
    from life_areas import life_areas
    facts = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30', '--gender', 'male',
         '--timezone', 'Asia/Shanghai', '--longitude', '116.4', '--current-timezone', 'Asia/Shanghai',
         '--request-time', '2026-10-24T04:00:00Z'])), '')['chart_facts']
    career = life_areas(facts, 'male', ['career'])['areas'][0]
    cycle = career['timing']['current_cycle']
    assert cycle['ganzhi'] == '甲戌' and cycle['stem_role'] == '食神' and cycle['brings_star']
    assert ('戌', '戊', '七杀') in [tuple(h) for h in cycle['branch_roles']]
    year = next(y for y in career['timing']['years'] if y['ganzhi'] == '丙午')
    assert year['brings_star'] and ('午', '己', '正官') in [tuple(h) for h in year['branch_roles']]
    assert '地支' in career['say'] and '七杀' in career['say']


def test_a_stem_only_combination_with_the_year_says_the_books_leave_it_open():
    # T21: 辛卯 day, 丙午 year. 丙辛 combine but 卯 and 午 do not; 《渊海子平》 writes 「日干支合太岁干支」.
    from annual_assessment import assess_year
    from must_cover import annual_scope_items

    def chart(day: str) -> dict:
        pillars = {k: {'stem': g[0], 'branch': g[1]} for k, g in
                   (('year', '辛未'), ('month', '辛丑'), ('day', day), ('hour', '丁酉'))}
        return {'day_master': {'stem': day[0]}, 'four_pillars': pillars, 'hour_known': True}
    stem_only = assess_year(chart('辛卯'), 2026, '丙午')
    hit = next(h for h in stem_only['hits'] if h['id'] == 'obscured')
    assert hit['branches_combine'] is False and '日干支合太岁干支' in hit['scope_note']
    assert [i['id'] for i in annual_scope_items([stem_only])] == ['annual:obscured:2026']
    both = assess_year(chart('辛未'), 2026, '丙午')          # 未 and 午 combine as well
    assert 'scope_note' not in next(h for h in both['hits'] if h['id'] == 'obscured')
    assert annual_scope_items([both]) == []
