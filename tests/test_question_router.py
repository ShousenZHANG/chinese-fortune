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


@pytest.mark.parametrize('question', ['失业了先做什么', '工伤怎么赔偿', '替朋友担保签不签', '每天通勤两小时值不值',
                                      '保健品值不值得买', '公司欠薪要不要去仲裁', '买基金划不划算'])
def test_a_real_life_decision_goes_to_the_books_decision_workflow(question):
    """The questions the book's own workflow is triggered by; GPT's audit found
    失业、工伤、担保 returning 'other'."""
    result = route(question)
    assert result['flow'] == 'life_guide' and '--decide' in result['command'], question
    assert result['reference'] == 'references/29-life-decision.md'


def test_every_question_the_book_says_it_answers_reaches_the_workflow():
    """The 34 questions of the book's README, verbatim."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
    missed = [q['question'] for q in data['guide']['questions'] if route(q['question'])['flow'] != 'life_guide']
    assert not missed


@pytest.mark.parametrize('question', ['公司拖欠工资三个月怎么办', '孩子发烧怎么办', '老板不发工资', '被车撞了对方不赔',
                                      '网购退款不给退', '邻居噪音太大怎么办', '老人摔倒了扶不扶', '手机丢了怎么办',
                                      '怎么戒掉拖延', '被网暴了怎么办'])
def test_everyday_wording_of_the_books_topics_reaches_the_workflow(question):
    assert route(question)['flow'] == 'life_guide', question


@pytest.mark.parametrize('question', ['我和他合不合', '本命年要注意什么', '桃花什么时候来', '帮我解梦梦见蛇',
                                      '面相看我能不能发财', '帮孩子取个名字', '解释一下这个卦', '属龙和属狗配吗',
                                      '我的正缘什么时候出现', '姻缘在哪里'])
def test_folk_divination_without_a_method_name_stays_out_of_the_workflow(question):
    assert route(question)['flow'] != 'life_guide', question


@pytest.mark.parametrize('question,flow', [
    ('我下周哪天出行好', 'personal_days'),        # a day question stays a day question
    ('我的婚姻怎么样', 'natal'),                  # 命理优先
    ('八字缺火怎么办', 'natal'),
    ('结婚可以吗', 'personal_days'),              # the day flows' event words are not life words
    ('穿什么颜色旺我', 'wear_advice'),
    ('用六爻看看试用期能不能转正', 'other'),       # a named method still wins
])
def test_divination_keeps_priority_over_the_decision_workflow(question, flow):
    assert route(question)['flow'] == flow


@pytest.mark.parametrize('question,stop', [('有人倒地没呼吸怎么办', 'emergency'), ('我不想活了', 'crisis'),
                                           ('下周哪天搬家好，我真的不想活了', 'crisis'), ('我想去死', 'crisis'),
                                           ('家里着火了', 'emergency'), ('收到法院传票了', 'legal')])
def test_an_emergency_a_crisis_or_a_legal_process_comes_before_everything(question, stop):
    result = route(question)
    assert result['flow'] == 'life_guide' and result['stop'] == stop
    assert result['reference'] == 'references/20-disclaimer.md'


@pytest.mark.parametrize('question', ['中风险理财值不值得买', '火灾险要不要买', '怎么预防心梗', '如果被起诉了怎么办'])
def test_insurance_prevention_and_hypotheticals_are_not_a_stop(question):
    assert 'stop' not in route(question)


@pytest.mark.parametrize('question', ['算一下我该不该辞职', '流年看我该不该离婚', '我命里适合创业吗',
                                      '六爻看我会不会中风', '帮我算算要不要换工作'])
def test_a_divination_question_phrased_as_a_decision_stays_with_divination(question):
    result = route(question)
    assert result['flow'] != 'life_guide' and 'stop' not in result, question


@pytest.mark.parametrize('question', ['租房押金要注意什么', '试用期工资最低多少', '出国前领事保护能做什么',
                                      '借钱给朋友要写借条吗'])
def test_practical_questions_reach_the_reference_library(question):
    result = route(question)
    assert result['flow'] == 'life_guide'
    assert 'life_guide.py' in result['command']
    assert any('现居地' in need for need in result['needs'])


@pytest.mark.parametrize('question', ['15号交定金可以吗', '周三签租房合同可以吗', '初八送彩礼好不好',
                                      '国庆节交定金行不行', '星期六签租房合同好不好'])
def test_a_named_day_keeps_a_practical_question_a_day_question(question):
    """A weekday, 「N号」, a lunar day or a festival is a date the question names."""
    result = route(question)
    assert result['flow'] == 'personal_days', question
    assert any('period' in need for need in result['needs'])


@pytest.mark.parametrize('question', ['帮我起一卦，押金能要回来吗', '用六爻看看试用期能不能转正',
                                      '塔罗牌看裁员会不会轮到我', '奇门遁甲看租房合同签不签', '紫微斗数看明年运势',
                                      '用周易算算押金能不能要回来', '摇个卦看看试用期能不能转正', '问卦：押金能要回来吗',
                                      '求个签看裁员会不会轮到我', '星座看试用期能不能转正', '测字看看借条'])
def test_a_named_divination_method_goes_to_that_method_not_a_new_flow(question):
    """The asker chose the method; neither the reference library nor 相主 answers it."""
    assert route(question)['flow'] == 'other'


@pytest.mark.parametrize('question', ['房东不退押金可以吗', '试用期不交社保行不行', '借条这样写合适吗'])
def test_a_practical_yes_no_question_is_not_a_day_question(question):
    """「可以吗」 asks whether something is allowed, not which day is good."""
    assert route(question)['flow'] == 'life_guide'


@pytest.mark.parametrize('question,flow', [
    ('下个月哪天搬家好', 'personal_days'),      # divination first, even with a practical word nearby
    ('租房那天是吉日吗', 'personal_days'),
    ('明天去要押金可以吗', 'personal_days'),    # a period still makes it a day question
    ('下周去洛阳紫微城哪天好', 'personal_days'),  # a place name, not 紫微斗数
])
def test_divination_questions_are_never_taken_by_the_reference_flow(question, flow):
    assert route(question)['flow'] == flow


def test_a_trip_question_asks_for_the_destination():
    needs = route('下周哪天出发去新加坡好')['needs']
    assert any('destination_timezone' in need for need in needs)


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
    entries = days['personal_calendar']['entries']
    # 365 dates; the twelve days a 节 falls on come in two pieces, before and after it.
    assert days['personal_calendar']['unit'] == 'day' and len({e['date'] for e in entries}) == 365
    assert len(entries) == 365 + sum(1 for e in entries if e.get('term', {}).get('side') == 'after')
    lead = render_answer(days).split('\n\n')[0]
    assert lead.startswith('按你出生那年的干支（丁丑）看，这段时间嫁娶对你最好的日子是') and '嫁娶要避开' in lead
    months = read_request({**base, **route('明年哪几个月好')['request']})
    assert months['personal_calendar']['unit'] == 'month'
    assert render_answer(months).startswith('按你出生那年的干支（丁丑）看，这段时间对你最好的月份是')


@pytest.mark.parametrize('question,flow', [
    ('我今天被裁了，怎么申请失业保险金', 'life_guide'),   # the date says when, not which day is good
    ('下周去医院体检要注意什么', 'life_guide'),
    ('10月8日被公司辞退了怎么办', 'life_guide'),
    ('我下周哪天面试运气最好', 'personal_days'),           # asks which day is good
    ('明天签合同运气好吗', 'personal_days'),
    ('15号交定金可以吗', 'personal_days'),
])
def test_a_date_in_a_how_question_does_not_make_it_a_day_question(question, flow):
    assert route(question)['flow'] == flow
