"""Common phrasings must land on the flow that computes their answer."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from question_router import route

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('question,flow,scenario,period', [
    # Which days (months) are good or bad for me: 相主 by the birth year.
    ('这周哪天对我好？', 'personal_days', 'outlook', '这周'),
    ('下周哪几天运气好', 'personal_days', 'outlook', '下周'),
    ('我今天运气怎么样', 'personal_days', 'outlook', '今天'),
    ('明天对我来说是吉日吗', 'personal_days', 'outlook', '明天'),
    ('后天适合出门吗', 'personal_days', 'travel', '后天'),
    ('这个月哪天是我的好日子', 'personal_days', 'outlook', '这个月'),
    ('下个月哪几天要避开', 'personal_days', 'outlook', '下个月'),
    ('明年哪几个月好', 'personal_days', 'outlook', '明年'),
    ('今年运势怎么样', 'personal_days', 'outlook', '今年'),
    ('周末出去旅行顺不顺', 'personal_days', 'travel', '周末'),
    # The same with an event: the event's day rules first, then 相主.
    ('下个月哪天搬家好？', 'personal_days', 'moving', '下个月'),
    ('今年哪天结婚好', 'personal_days', 'wedding', '今年'),
    ('本月哪天开业吉利', 'personal_days', 'business', '本月'),
    ('10月29日搬家可以吗', 'personal_days', 'moving', None),
    ('下周面试哪天好', 'personal_days', 'interview', '下周'),
    # Clock times or durations: compare concrete slots.
    ('下周三上午十点面试和下午两点面试哪个好', 'event_slots', 'interview', '下周'),
    ('明天9点出发还是14点出发好', 'event_slots', 'travel', '明天'),
])
def test_day_questions_reach_the_personal_grades(question, flow, scenario, period):
    result = route(question)
    assert result['flow'] == flow
    assert result['request']['event']['scenario'] == scenario
    assert result['request'].get('period') == period
    assert result['request']['intent'] == ('selection' if flow == 'event_slots' else 'period')
    assert 'fortune_reading.py --stdin' in result['command']


@pytest.mark.parametrize('question,aspects', [
    ('我穿什么颜色的衣服对自己有利', ['colour']),
    ('我的幸运色是什么', ['colour']),
    ('什么颜色旺我', ['colour']),
    ('适合买什么颜色的车', ['colour']),
    ('戴什么首饰对我好', ['things']),
    ('适合戴金还是戴银', ['things']),
    ('我适合戴玉吗', ['things']),
    ('我的幸运数字是几', ['number']),
    ('手机号选什么数字好', ['number']),
    ('我往哪个方位发展好', ['direction']),
    ('我五行缺什么', ['element']),
    ('我喜什么五行', ['element']),
    ('幸运色和幸运数字是什么', ['colour', 'number']),
])
def test_wearing_and_element_questions_reach_the_tiaohou_answer(question, aspects):
    result = route(question)
    assert result['flow'] == 'wear_advice' and result['aspects'] == aspects
    assert 'bazi_reading.py' in result['command'] and '--question' in result['command']


@pytest.mark.parametrize('question,flow', [
    ('今天黄历宜什么', 'almanac'),
    ('这天老黄历忌什么', 'almanac'),
    ('我的八字怎么样', 'natal'),
    ('我适合什么工作', 'natal'),
    ('办公桌朝哪个方向好', 'specialist'),   # 风水, even though it says 方向
    ('卧室床头朝向', 'specialist'),
    ('下个月做手术哪天好', 'boundary'),
    ('帮我起个卦', 'other'),
])
def test_other_questions_are_not_pulled_into_the_new_flows(question, flow):
    assert route(question)['flow'] == flow


def test_the_router_names_what_is_still_needed():
    dated = route('10月29日搬家可以吗')
    assert any('period' in need for need in dated['needs'])
    open_ended = route('哪天对我好')
    assert any('时间范围' in need for need in open_ended['needs'])
    slots = route('明天9点出发还是14点出发好')
    assert any('candidates' in need for need in slots['needs'])


def test_the_cli_prints_the_route_as_json():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'question_router.py'),
                           '--question', '下个月哪天搬家好？'], capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out['ok'] and out['flow'] == 'personal_days' and out['request']['event'] == {'scenario': 'moving'}


def test_every_period_word_the_router_emits_is_one_the_request_accepts():
    """A route whose period the calculation then rejects would strand the host."""
    from fortune_time import resolve_window
    from question_router import PERIOD_WORDS
    now = {'utc': '2026-09-17T02:00:00+00:00', 'timezone': 'Asia/Shanghai'}
    for word in PERIOD_WORDS:
        window = resolve_window(word, now, 'Asia/Shanghai')
        assert window['start'] < window['end'], word


@pytest.mark.parametrize('question,lead', [
    ('下个月哪天搬家好？', '按你出生那年的干支（丁丑）看，这段时间搬家对你最好的日子是'),
    ('这周哪天对我好？', '按你出生那年的干支（丁丑）看，这段时间对你最好的日子是'),
])
def test_a_routed_request_answers_first(question, lead):
    """Follow the route end to end with a real person: the answer opens with days."""
    from answer_style import style_violations
    from fortune_reading import read_request, render_answer
    request = {**route(question)['request'], 'current_timezone': 'Asia/Shanghai',
               'request_time': '2026-09-17T02:00:00Z',
               'participants': [{'id': 'me', 'confirmed': True, 'person': {
                   'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                             'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}}]}
    request['event'] = {**request['event'], 'longitude': 121.47}
    text = render_answer(read_request(request))
    assert text.startswith(lead), text.split('\n\n')[0]
    assert not style_violations(text)


def test_a_day_question_over_a_year_is_answered_by_day_and_a_month_question_by_month():
    from fortune_reading import read_request, render_answer
    person = [{'id': 'me', 'confirmed': True, 'person': {
        'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                  'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}}]
    base = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-17T02:00:00Z', 'participants': person}
    days = read_request({**base, **route('明年哪天结婚好？')['request']})
    assert days['personal_calendar']['unit'] == 'day' and len(days['personal_calendar']['entries']) == 365
    lead = render_answer(days).split('\n\n')[0]
    assert lead.startswith('按你出生那年的干支（丁丑）看，这段时间嫁娶对你最好的日子是') and '嫁娶要避开' in lead
    months = read_request({**base, **route('明年哪几个月好')['request']})
    assert months['personal_calendar']['unit'] == 'month'
    assert render_answer(months).startswith('按你出生那年的干支（丁丑）看，这段时间对你最好的月份是')
