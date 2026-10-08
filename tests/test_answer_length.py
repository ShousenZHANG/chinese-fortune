"""Answers say the conclusion first and stay short: each quote once, the limits kept.

Measured on 2026-10-06: a month of moving dates rendered 4628 characters in 47
paragraphs, a seven-day outlook 1666, the job-loss decision 2108. Ceilings
below lock the shorter form; the JSON packet is unchanged.
"""
import re

import pytest
from fortune_reading import read_request, render_answer
from life_decision import render
from life_guide import decide

PERSON = {'birth': {'year': 1997, 'month': 8, 'day': 20, 'hour': 10, 'minute': 15, 'gender': 'male',
                    'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}
BASE = {'current_timezone': 'Australia/Sydney', 'request_time': '2026-10-06T00:00:00Z',
        'participants': [{'id': 'me', 'confirmed': True, 'person': PERSON}]}
MOVING = {**BASE, 'question': '下个月哪天搬家好', 'intent': 'period', 'period': '下个月',
          'event': {'scenario': 'moving', 'longitude': 151.2}}
WEEK = {**BASE, 'question': '未来七天哪天对我好', 'intent': 'period', 'period': '未来七天',
        'event': {'scenario': 'outlook', 'longitude': 151.2}}


def _classical_quotes(text: str) -> list[str]:
    """Quotes long enough to be passages, not labels such as 「合官」."""
    return [q for q in re.findall(r'「([^」]+)」', text) if len(q) >= 8]


def _for_the_user(text: str) -> str:
    """The draft without its closing notes to the host (「写回答时」), which the user never sees."""
    return '\n'.join(line for line in text.split('\n') if not line.startswith('写回答时：')).rstrip()


@pytest.fixture(scope='module')
def moving():
    return _for_the_user(render_answer(read_request(MOVING)))


@pytest.fixture(scope='module')
def week():
    return _for_the_user(render_answer(read_request(WEEK)))


def test_a_month_of_dates_fits_in_about_two_thousand_characters(moving):
    """2000 before the v5.6 evaluation; the terms line it asked for (术语当场解释) adds about 130."""
    assert len(moving) <= 2150, len(moving)
    assert moving.startswith('按你出生那年的干支（丁丑）看，这段时间搬家对你最好的日子是')


def test_a_week_fits_in_twelve_hundred_characters(week):
    assert len(week) <= 1200, len(week)


@pytest.mark.parametrize('name', ['moving', 'week'])
def test_each_passage_is_quoted_once(name, request):
    text = request.getfixturevalue(name)
    repeated = {q for q in _classical_quotes(text) if text.count(f'「{q}」') > 1}
    assert not repeated, repeated


def test_the_limits_of_this_question_stay(moving, week):
    for text in (moving, week):
        method = next(p for p in text.split('\n\n') if p.startswith('择日看人'))
        assert '（xieji:c033:p0020）' in method and '补龙扶山' in method
    assert '借用' in week          # 阶段运势 borrows 相主: the passage never wrote it for this


def test_days_to_avoid_are_grouped_by_rule_with_their_dates(moving):
    """月破, 往亡, 归忌, 四废: each named once with its dates, the passage once."""
    for rule in ('月破', '往亡'):
        lines = [line for line in moving.split('\n\n') if line.startswith(f'搬家避开{rule}')]
        assert len(lines) == 1, rule
    assert '11月2日' in next(line for line in moving.split('\n\n') if line.startswith('搬家避开月破'))


def test_a_term_day_with_the_same_verdict_on_both_sides_is_one_day(moving):
    lead = moving.split('\n\n')[0]
    assert '立冬前' not in lead and '立冬后' not in lead and '11月7日' in lead


def test_the_detail_flag_brings_back_the_full_method():
    text = render_answer(read_request(MOVING), detail=True)
    assert '吉的条目只看日柱' in text and '宅长之命' in text


def test_the_cycle_years_match_the_chart_answer(week):
    """2021–2030, as the chart answer's da_yun says; 2031 is when the next one starts."""
    assert '乙巳运（2021–2030）' in week


def test_a_decision_draft_quotes_two_sentences_and_points_to_the_rest():
    result = decide('失业了先做什么', {'current_timezone': 'Asia/Shanghai'})
    text = _for_the_user(render(result))
    assert len(text) <= 1500, len(text)
    rows = [r for g in result['do'] for r in g['entries']]
    long_row = next(r for r in rows if r['fields']['说人话'].count('。') > 2)
    assert f"全文见{long_row['citation'].split('（')[0]}" in text
    first_two = '。'.join(long_row['fields']['说人话'].split('。')[:2]) + '。'
    assert first_two in text                      # the words and numbers as the book has them
    assert text.count('——') <= 7 and text.count('术语：') <= 1


# --- 5.8.0: chart, colour and slot answers (v5.6 evaluation: readable 0/12 for A and D) ---

def _chart_text(question: str) -> str:
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading, render_facts
    chart = calculate_bazi(build_parser().parse_args(
        ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--minute', '0', '--gender', 'male',
         '--timezone', 'Asia/Shanghai', '--as-of-year', '2026']))
    return _for_the_user(render_facts(prepare_reading(chart, question)))


def test_a_chart_answer_states_each_route_condition_once():
    """1138 characters before: every route repeated the same two conditions."""
    text = _chart_text('帮我看看八字命局')
    assert len(text) <= 850, len(text)
    assert text.count('不等于它已发挥作用') == 1 and text.count('月令本格') == 1
    assert not text.startswith('就「')


def test_a_colour_answer_leaves_out_the_route_checklist():
    """1707 characters before: the whole chart checklist followed the colours."""
    text = _chart_text('我穿什么颜色的衣服对自己有利？')
    assert len(text) <= 700, len(text)
    assert text.startswith('按《穷通宝鉴》调候') and '前提已见到' not in text and '已可固定的柱' in text


def test_a_slot_answer_merges_hours_that_say_the_same():
    PERSON_1990 = {'birth': {'year': 1990, 'month': 5, 'day': 10, 'hour': 14, 'minute': 0, 'gender': 'male',
                             'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}
    request = {'current_timezone': 'Australia/Sydney', 'request_time': '2026-10-06T01:00:00Z',
               'question': '下周二10点到12点或周三14点到16点能面试，每次60分钟，帮我选首选和备选。', 'period': '下周',
               'event': {'scenario': 'interview', 'longitude': 151.2}, 'duration_minutes': 60,
               'candidates': [{'id': 'tue', 'start': '2026-10-13T10:00', 'end': '2026-10-13T12:00'},
                              {'id': 'wed', 'start': '2026-10-14T14:00', 'end': '2026-10-14T16:00'}],
               'participants': [{'id': 'me', 'confirmed': True, 'person': PERSON_1990}]}
    text = _for_the_user(render_answer(read_request(request)))
    assert len(text) <= 1550, len(text)
    assert '庚申日辛巳、壬午时' in text and text.count('这一年（丙午）') == 1
