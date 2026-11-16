"""Fixes from the tenth external review (research/gpt-results-20261115/C4/fixes.json, FIX-01 to FIX-04)."""
from answer_check import check_answer
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading
from conftest import SCRIPTS
from fortune_reading import host_notes, read_request, render_answer
from ziwei_calc import build_parser as ziwei_parser
from ziwei_calc import calculate_ziwei

ROOT = SCRIPTS.parents[2]
REFS = SCRIPTS.parent / 'references'


def test_ziwei_focus_leads_with_the_answer_and_keeps_limits_in_one_place():
    # FIX-01, T41: 夫妻宫 in 午 with 七杀; 地空 and the minor stars were explained away paragraph after paragraph.
    args = ['--year', '1996', '--month', '2', '--day', '18', '--hour', '9', '--minute', '25', '--gender', 'female',
            '--time-standard', 'clock', '--focus-palace', '夫妻']
    focus = calculate_ziwei(ziwei_parser().parse_args(args))['focus']
    assert focus['palace'] == '夫妻宫' and focus['branch'] == '午'
    assert focus['answer_order'][0].startswith('开头') and focus['answer_order'][-1].startswith('补查记录')
    assert '地空' in focus['held_back'] and '七杀' not in focus['held_back']
    assert '说一次' in focus['note_once']
    guide = (REFS / '02-ziwei.md').read_text(encoding='utf-8')
    for heading in ('### 交付骨架', '**按宫问相处', '**按宫问事业', '**核对某个格局**', '补查记录'):
        assert heading in guide


def _t10():
    args = ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30', '--gender', 'male',
            '--timezone', 'Asia/Shanghai', '--longitude', '116.4']
    return prepare_reading(calculate_bazi(build_parser().parse_args(args)), '看看我最近的事业运')


def test_a_career_question_must_state_the_natal_positions_before_asking_for_the_time_zone():
    # FIX-02, T10: the reply listed the pillars and asked for the current time zone twice, and nothing else.
    reading = _t10()
    item = next(i for i in reading['must_cover'] if i['id'] == 'life:career')
    assert '正官' in item['groups'][0] and '年柱' in item['groups'][1]
    pillars_only = '四柱是己卯、丁丑、壬申、乙巳。这次“最近”按你现在所在地的哪个时区计算？'
    delivered = ('四柱是己卯、丁丑、壬申、乙巳。事业看正官、七杀：年柱天干己是正官，月柱丑藏己（正官）。'
                 '好坏这次没判。“最近”按你现在住的时区算，请告诉我在哪个时区。')
    assert 'must_cover_missing' in [f['code'] for f in check_answer(pillars_only, [reading])['findings']]
    assert not [f for f in check_answer(delivered, [reading])['findings'] if f['code'] == 'must_cover_missing']
    assert '工具已列进 `must_cover`' in (REFS / '00-intake.md').read_text(encoding='utf-8')


PERSON = {'birth': {'year': 1990, 'month': 5, 'day': 15, 'hour': 10, 'minute': 0, 'gender': 'male',
                    'timezone': 'Asia/Shanghai', 'longitude': 120.16}, 'time_certainty': 'exact'}


def _period(question: str) -> dict:
    return read_request({'current_timezone': 'Asia/Shanghai', 'request_time': '2026-11-15T04:00:00Z',
                         'participants': [{'id': 'me', 'confirmed': True, 'person': PERSON}],
                         'question': question, 'intent': 'period', 'period': '最近',
                         'event': {'scenario': 'outlook', 'longitude': 120.16}})


def test_a_career_outlook_opens_with_what_is_judged_and_puts_day_grades_in_an_appendix():
    # FIX-03, C2 FIRST: five readers took the borrowed 大吉/凶 month grades for a career forecast.
    result = _period('帮我看看八字，最近事业怎么样')
    notes = '\n'.join(host_notes(result))
    assert '附：传统择日等级（借用相主，不是事业预测）' in notes and '首句和结论都要保留' not in notes
    draft = render_answer(result)
    assert draft.startswith('事业看正官、七杀')
    assert draft.index('事业好坏本次没判') < draft.index('附：传统择日等级') < draft.index('大吉')
    other = '\n'.join(host_notes(_period('未来七天哪天对我好')))
    assert '首句和结论都要保留「借用相主比较」' in other and '附：传统择日等级' not in other


def _first_screen(name: str) -> str:
    text = (ROOT / name).read_text(encoding='utf-8')
    return text[:text.index('\n## ')]


def test_the_readme_first_screen_says_where_to_install_what_it_needs_and_how():
    # FIX-04, C2 README: 0 of 5 readers could pull an install command out of the first screen.
    for name, needs in (('README.md', 'Python 3.9'), ('README.en.md', 'Python 3.9')):
        screen = _first_screen(name)
        assert needs in screen and 'releases/latest' in screen
        assert '~/.claude/skills/' in screen and '~/.codex/skills/' in screen
        assert '1. ' in screen and '3. ' in screen and 'chinese-fortune/SKILL.md' in screen
