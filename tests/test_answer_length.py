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

PERSON = {'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                    'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}
BASE = {'current_timezone': 'Australia/Sydney', 'request_time': '2026-10-06T00:00:00Z',
        'participants': [{'id': 'me', 'confirmed': True, 'person': PERSON}]}
MOVING = {**BASE, 'question': '下个月哪天搬家好', 'intent': 'period', 'period': '下个月',
          'event': {'scenario': 'moving', 'longitude': 151.2}}
WEEK = {**BASE, 'question': '未来七天哪天对我好', 'intent': 'period', 'period': '未来七天',
        'event': {'scenario': 'outlook', 'longitude': 151.2}}


def _classical_quotes(text: str) -> list[str]:
    """Quotes long enough to be passages, not labels such as 「合官」."""
    return [q for q in re.findall(r'「([^」]+)」', text) if len(q) >= 8]


@pytest.fixture(scope='module')
def moving():
    return render_answer(read_request(MOVING))


@pytest.fixture(scope='module')
def week():
    return render_answer(read_request(WEEK))


def test_a_month_of_dates_fits_in_two_thousand_characters(moving):
    assert len(moving) <= 2000, len(moving)
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
    """2023–2032, as the chart answer's da_yun says; 2033 is when the next one starts."""
    assert '己酉运（2023–2032）' in week


def test_a_decision_draft_quotes_two_sentences_and_points_to_the_rest():
    result = decide('失业了先做什么', {'current_timezone': 'Asia/Shanghai'})
    text = render(result)
    assert len(text) <= 1500, len(text)
    rows = [r for g in result['do'] for r in g['entries']]
    long_row = next(r for r in rows if r['fields']['说人话'].count('。') > 2)
    assert f"全文见{long_row['citation'].split('（')[0]}" in text
    first_two = '。'.join(long_row['fields']['说人话'].split('。')[:2]) + '。'
    assert first_two in text                      # the words and numbers as the book has them
    assert text.count('——') <= 7 and text.count('术语：') <= 1
