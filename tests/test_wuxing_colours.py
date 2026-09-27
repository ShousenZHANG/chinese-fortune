"""Colours and things to wear come from the 调候 cell's general choice, every
link cited, and say that the cell's exceptions were not checked on the chart."""
import pytest
from answer_style import style_violations
from classical_search import get_passage
from utils import TIANGAN_WUXING
from wuxing_colours import (
    COLOUR_QUOTES,
    COLOUR_SOURCE,
    HETU,
    HETU_QUOTE,
    HETU_SOURCE,
    SHADE_QUOTE,
    SHADE_SOURCE,
    THINGS,
    asks_colour,
    aspects_asked,
    colour_advice,
    colour_lead,
    colour_lines,
)

STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '寅卯辰巳午未申酉戌亥子丑'


def _chart(stem: str, branch: str) -> dict:
    return {'day_master': {'stem': stem}, 'four_pillars': {'month': {'branch': branch}}}


def test_every_quote_is_verbatim():
    colour_text = get_passage(COLOUR_SOURCE)['text']
    for wuxing, quote in COLOUR_QUOTES.items():
        assert quote in colour_text, wuxing
    assert SHADE_QUOTE in get_passage(SHADE_SOURCE)['text']
    for wuxing, (_, quote, source) in THINGS.items():
        assert quote in get_passage(source)['text'], wuxing


@pytest.mark.parametrize('stem', list(STEMS))
def test_every_cell_follows_its_own_clause(stem):
    for branch in BRANCHES:
        advice = colour_advice(_chart(stem, branch))
        assert advice['status'] == 'ok', (stem, branch)
        first = advice['needed'][0]
        assert advice['wear'][0]['wuxing'] == TIANGAN_WUXING[first['stem']]
        # The quoted words are the clause's own and name the stem they are cited for.
        tiaohou = advice['tiaohou']
        assert tiaohou['quote'] in get_passage(tiaohou['passage_id'])['text']
        assert first['stem'] in tiaohou['quote'], (stem, branch, tiaohou['quote'])
        # Every cell needs the chart's own conditions; none is checked here, and the answer says so.
        assert advice['individual_application'] == 'requires_chart_conditions'
        assert advice['chart_conditions_checked'] is False and 'avoid' not in advice
        lead = colour_lead(advice)
        assert lead.startswith('按《穷通宝鉴》调候，') and '这一格一般先取' in lead
        assert lead.endswith('这是这一格的一般取法，你的盘是不是原文说的例外（见下）还没有逐条核对。')
        assert '按你的八字' not in lead and '少穿' not in lead
        lines = colour_lines(advice)
        assert any(tiaohou['review_note'] in line for line in lines), (stem, branch)
        text = lead + '\n\n' + '\n\n'.join(lines)
        assert not style_violations(text), (stem, branch)


@pytest.mark.parametrize('stem,branch,wear', [
    ('甲', '子', ['火', '金']),   # 「丁先庚後」
    ('庚', '午', ['水']),         # 「專用壬水」
    ('丁', '亥', ['木', '金']),   # 「端用庚甲」
    ('庚', '子', ['火', '木']),
])
def test_known_cells(stem, branch, wear):
    advice = colour_advice(_chart(stem, branch))
    assert [w['wuxing'] for w in advice['wear']] == wear


def test_the_lead_answers_first_and_the_lines_give_every_link():
    advice = colour_advice(_chart('甲', '子'))
    lead = colour_lead(advice)
    assert lead == ('按《穷通宝鉴》调候，甲日主生在子月，这一格一般先取丁（火），其次庚（金）。照这个换算：'
                    '衣服首选红色、紫色（火），其次白色、金银色（金）；佩戴首选红色、紫色的饰物（火），其次金银首饰、金属饰物（金）。'
                    '这是这一格的一般取法，你的盘是不是原文说的例外（见下）还没有逐条核对。')
    lines = '\n'.join(colour_lines(advice))
    for needle in ('qiongtong:c002:p0069', '十一月甲木，木性生寒，丁先庚後，丙火佐之', 'sanming:c007:p0004',
                   '「其色赤」「其色白」', 'meihua:c002:p0118', 'meihua:c003:p0069',
                   '本工具没有逐条核对', '不列「少穿」的颜色', '没有一句说穿某种颜色、戴某样东西'):
        assert needle in lines, needle


def test_the_review_note_is_shown_whole():
    """The audit case: 庚 in 子 month. The note's own caution stays in the answer."""
    lines = '\n'.join(colour_lines(colour_advice(_chart('庚', '子'))))
    assert '审校说明：取丁甲、次丙；丙丁过多与水局另论，不把表名直接变成喜火的现实建议。' in lines
    assert '有条件才取：丙。' in lines


def test_charts_that_share_the_cell_get_the_same_general_answer_and_the_same_caveat():
    """Two 庚-in-子 charts, one with 丙丁 everywhere and a 申子辰 water frame: the
    cell's exceptions (「丙丁过多与水局另论」) are not evaluated, so neither answer
    may read as settled for its chart."""
    plain = {'day_master': {'stem': '庚'}, 'four_pillars': {
        'year': {'stem': '甲', 'branch': '辰'}, 'month': {'stem': '丙', 'branch': '子'},
        'day': {'stem': '庚', 'branch': '寅'}, 'hour': {'stem': '戊', 'branch': '寅'}}}
    fiery = {'day_master': {'stem': '庚'}, 'four_pillars': {
        'year': {'stem': '丙', 'branch': '申'}, 'month': {'stem': '丙', 'branch': '子'},
        'day': {'stem': '庚', 'branch': '辰'}, 'hour': {'stem': '丁', 'branch': '亥'}}}
    leads = [colour_lead(colour_advice(chart, '我穿什么颜色好')) for chart in (plain, fiery)]
    assert leads[0] == leads[1]
    assert '一般取法' in leads[0] and '还没有逐条核对' in leads[0]
    # 甲 in 未 month: 「無癸亦可」, and the old table put 癸 first. Nothing says avoid water.
    jia_wei = colour_lead(colour_advice(_chart('甲', '未')))
    assert '黑色' not in jia_wei and '少穿' not in jia_wei


def test_an_unsettled_day_master_says_why_instead_of_guessing():
    advice = colour_advice({'day_master': {}, 'four_pillars': {'month': {'branch': '子'}}})
    assert advice['status'] == 'unavailable'
    assert colour_lead(advice).startswith('这一问现在给不出，因为')
    assert colour_lines(advice) == []


def test_only_colour_questions_get_colour_answers():
    assert asks_colour('我穿什么颜色的衣服对自己有利？') and asks_colour('戴什么首饰旺我')
    assert not asks_colour('今年财运怎么样') and not asks_colour(None) and not asks_colour('')


def test_bazi_markdown_leads_with_colours_for_a_colour_question():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading, render_facts
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '1997', '--month', '12', '--day', '24', '--hour', '19', '--minute', '30',
        '--gender', 'male', '--as-of-year', '2026']))
    text = render_facts(prepare_reading(chart, '我穿什么颜色的衣服对自己有利？'))
    assert text.startswith('按《穷通宝鉴》调候，')
    assert '衣服首选红色、紫色（火），其次绿色、青色（木）' in text.split('\n')[0]
    assert not style_violations(text)
    plain = prepare_reading(chart, '我适合做什么工作')
    assert 'colour_advice' not in plain and not render_facts(plain).startswith('按《穷通宝鉴》调候')


def test_the_hetu_table_is_the_passage():
    text = get_passage(HETU_SOURCE)['text']
    assert HETU_QUOTE in text
    digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
    places = {'北': '北方', '南': '南方', '東': '东方', '西': '西方', '中': '中央'}
    import re
    for a, b, wuxing, place in re.findall(r'([一二三四五])([六七八九十])為(.)居(.)', HETU_QUOTE):
        assert HETU[wuxing] == (places[place], f'{digits[a]}、{digits[b]}')


@pytest.mark.parametrize('question,aspects', [
    ('我穿什么颜色的衣服对自己有利？', ['colour']),
    ('我的幸运色是什么', ['colour']),
    ('适合戴金还是戴银', ['things']),
    ('戴什么手串旺我', ['things']),
    ('我往哪个方位发展好', ['direction']),
    ('手机号选什么数字好', ['number']),
    ('我的幸运数字是几', ['number']),
    ('我五行缺什么', ['element']),
    ('我喜什么五行', ['element']),
    ('幸运色和幸运数字是什么', ['colour', 'number']),
    ('我适合什么发展方向', []),       # a career question, not a compass point
    ('今年财运怎么样', []),
])
def test_the_question_decides_what_is_answered(question, aspects):
    assert aspects_asked(question) == aspects


@pytest.mark.parametrize('question,lead', [
    ('我往哪个方位发展好', '照这个换算：方位是南方（火），其次西方（金）。'),
    ('我的幸运数字是几', '照这个换算：数字是2、7（火），其次4、9（金）。'),
    ('我五行缺什么', '这一格一般先取丁（火），其次庚（金）。这是'),
])
def test_each_aspect_gets_its_own_first_sentence(question, lead):
    advice = colour_advice(_chart('甲', '子'), question)
    assert lead in colour_lead(advice)
    assert colour_lead(advice).startswith('按《穷通宝鉴》调候，甲日主生在子月，这一格一般先取丁（火），其次庚（金）')
    lines = '\n'.join(colour_lines(advice))
    if advice['aspects'] in (['direction'], ['number']):
        assert HETU_QUOTE in lines and HETU_SOURCE in lines
    if advice['aspects'] == ['element']:
        assert '古法不数哪种五行少' in lines and '《子平真诠》' in lines
