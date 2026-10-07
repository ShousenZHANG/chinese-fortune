"""流年：太岁与本人日柱、月柱、当步大运的关系，按《渊海子平》《三命通会》《滴天髓》原文。

Year-level passages for a year-level question; each hit carries its quote and
the verdict word of the passage, and conditions the passage leaves open stay
open. No total grade is made up from the hits.
"""
import pytest
from annual_assessment import RULES, annual_paragraph, assess_year, years_asked
from classical_search import get_passage


def _chart(year, month, day, hour, hour_known=True):
    pillars = {'year': {'stem': year[0], 'branch': year[1]}, 'month': {'stem': month[0], 'branch': month[1]},
               'day': {'stem': day[0], 'branch': day[1]}, 'hour': {'stem': hour[0], 'branch': hour[1]}}
    return {'day_master': {'stem': day[0]}, 'four_pillars': pillars, 'hour_known': hour_known}


@pytest.mark.parametrize('rule', RULES.values(), ids=lambda r: r['id'])
def test_every_rule_quotes_the_frozen_text(rule):
    passage = get_passage(rule['passage_id'])
    assert passage['sha256'] == rule['sha256']
    assert rule['quote'] in passage['text'] or rule['quote'] == passage.get('section')


def test_the_day_stem_overcoming_the_year_without_rescue_is_heavy():
    """甲日 in a 戊 year: 「日犯岁君，灾殃必重」; no 庚辛 to check 甲, no 己 to combine it."""
    chart = _chart('丙子', '丙寅', '甲子', '丙寅')
    hits = {h['id']: h for h in assess_year(chart, 2028, '戊申')['hits']}
    assert hits['day_offends_year']['verdict'] == '凶' and hits['day_offends_year']['rescue'] == []


def test_a_rescue_turns_it_into_wealth():
    """「柱中原有庚金制其日……谓五行有救，戊乃甲之偏财，则反招财」."""
    chart = _chart('庚子', '丙寅', '甲子', '丙寅')
    hit = {h['id']: h for h in assess_year(chart, 2028, '戊申')['hits']}['day_offends_year']
    assert hit['rescue'] and hit['verdict'] == '有救'


def test_the_year_overcoming_the_day_stem_is_light():
    chart = _chart('丁丑', '壬子', '庚子', '丙戌')        # 庚日, 丁 year overcomes 庚
    hits = {h['id']: h for h in assess_year(chart, 2027, '丁未')['hits']}
    assert hits['year_hurts_day']['verdict'] == '祸轻'


def test_a_combining_day_stem_is_obscured_heavy_or_light_by_who_combines():
    """「甲合巳災重巳合甲災輕」: 甲日己年 heavy, 己日甲年 light."""
    heavy = {h['id']: h for h in assess_year(_chart('丙子', '丙寅', '甲子', '丙寅'), 2029, '己酉')['hits']}
    light = {h['id']: h for h in assess_year(_chart('丙子', '丙寅', '己亥', '丙寅'), 2024, '甲辰')['hits']}
    assert heavy['obscured']['weight'] == '灾重' and light['obscured']['weight'] == '灾轻'


def test_clashes_with_the_day_and_month_branch():
    chart = _chart('丙子', '丙寅', '甲子', '丙寅')        # 午 year clashes the 子 day and 子? no: month 寅
    hits = {h['id'] for h in assess_year(chart, 2026, '丙午')['hits']}
    assert 'day_branch_clash' in hits and 'month_clash' not in hits
    hits = {h['id'] for h in assess_year(chart, 2030, '庚申')['hits']}
    assert 'month_clash' in hits                          # 申 clashes the 寅 month


def test_the_same_pillar_as_the_day_is_fuyin():
    hits = {h['id'] for h in assess_year(_chart('丙子', '丙寅', '甲子', '丙寅'), 2044, '甲子')['hits']}
    assert 'fuyin' in hits


def test_the_cycle_against_the_year():
    """「嵗衝尅運者吉運衝尅嵗者凶」."""
    chart = _chart('丙子', '丙寅', '甲子', '丙寅')
    cycle_hits = {h['id']: h for h in assess_year(chart, 2027, '丁未', cycle={'ganzhi': '癸巳'})['hits']}
    assert cycle_hits['cycle_overcomes_year']['verdict'] == '凶'
    year_hits = {h['id']: h for h in assess_year(chart, 2027, '丁未', cycle={'ganzhi': '辛卯'})['hits']}
    assert year_hits['year_overcomes_cycle']['verdict'] == '吉'


def test_the_luck_cycle_decides_how_heavy_a_day_offence_is():
    """三命：行好运而日干伤流年天元为祸轻，行不好运为祸重."""
    chart = _chart('丙子', '丙寅', '甲子', '丙寅')
    good = assess_year(chart, 2028, '戊申', luck_stem='favoured')
    hit = {h['id']: h for h in good['hits']}['day_offends_year']
    assert hit['luck_weight'] == '祸轻'


def test_a_missing_hour_still_reads_the_day_pillar_but_says_so():
    reading = assess_year(_chart('丙子', '丙寅', '甲子', '丙寅', hour_known=False), 2028, '戊申')
    assert reading['status'] == 'assessed' and '时辰' in reading['limit']


def test_the_paragraph_names_the_year_the_hits_and_the_limits():
    text = annual_paragraph(assess_year(_chart('丁丑', '壬子', '庚子', '丙戌'), 2027, '丁未'))
    assert text.startswith('2027年（丁未）')
    assert '「歲傷日干有禍必輕」' in text and '一年一个说法' in text


def test_a_quiet_year_says_the_texts_have_nothing_on_it():
    text = annual_paragraph(assess_year(_chart('丙子', '丙寅', '甲子', '丙寅'), 2033, '癸丑'))
    assert '没有原文所说的' in text


@pytest.mark.parametrize('question,years', [
    ('2027年流年运势怎么样', [2027]), ('今年运势怎么样', [2026]), ('明年怎么样', [2027]),
    ('这几年运势', [2026, 2027, 2028]), ('流年怎么样', [2026]), ('我适合做什么工作', []),
    ('2027和2028年哪年好', [2027, 2028]),
])
def test_the_years_a_question_asks(question, years):
    assert years_asked(question, 2026) == years


def test_a_chart_question_about_a_year_gets_the_annual_reading():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import host_notes, prepare_reading, render_facts
    chart = calculate_bazi(build_parser().parse_args(
        ['--year', '1989', '--month', '12', '--day', '26', '--hour', '8', '--minute', '0', '--gender', 'male',
         '--timezone', 'Asia/Shanghai', '--request-time', '2026-10-06T01:00:00Z']))
    result = prepare_reading(chart, '2027年流年运势怎么样')
    assert [(r['year'], r['ganzhi']) for r in result['annual_reading']] == [(2027, '丁未')]
    assert '2027年（丁未）' in render_facts(result)
    assert any('流年只列原文说的冲、克、合关系' in n for n in host_notes(result))


def test_a_relative_year_without_any_time_asks_first():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading
    chart = calculate_bazi(build_parser().parse_args(
        ['--year', '1989', '--month', '12', '--day', '26', '--hour', '8', '--minute', '0', '--gender', 'male',
         '--timezone', 'Asia/Shanghai']))
    reading = prepare_reading(chart, '今年流年怎么样')['annual_reading'][0]
    assert reading['status'] == 'unavailable' and '先问用户现在住在哪里' in reading['reason']


def test_a_period_answer_over_a_year_carries_each_year():
    from fortune_reading import read_request, render_answer
    payload = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-10-06T01:00:00Z',
               'question': '2027年流年运势怎么样', 'intent': 'period', 'period': '明年',
               'event': {'scenario': 'outlook', 'longitude': 121.47},
               'participants': [{'id': 'me', 'confirmed': True, 'person': {
                   'birth': {'year': 1990, 'month': 5, 'day': 10, 'hour': 14, 'minute': 0, 'gender': 'male',
                             'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}}]}
    result = read_request(payload)
    assert [r['year'] for r in result['participants'][0]['annual_reading']] == [2027]
    assert '2027年（丁未）' in render_answer(result)
