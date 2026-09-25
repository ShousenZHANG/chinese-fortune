"""Colours and things to wear come from the chart's 调候 用神, every link cited."""
import pytest
from answer_style import style_violations
from classical_search import get_passage
from utils import TIANGAN_WUXING
from wuxing_colours import (
    AVOID_SOURCE,
    COLOUR_QUOTES,
    COLOUR_SOURCE,
    HETU,
    HETU_QUOTE,
    HETU_SOURCE,
    KE_BY,
    SHADE_QUOTE,
    SHADE_SOURCE,
    THINGS,
    _conditions,
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
    assert AVOID_SOURCE[1] in get_passage(AVOID_SOURCE[0])['text']


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
        # Never tell someone to avoid what their own clause asks for.
        needed = {n['wuxing'] for n in advice['needed']}
        for avoid in advice['avoid']:
            assert avoid['wuxing'] not in needed and avoid['wuxing'] == KE_BY[first['wuxing']]
        text = colour_lead(advice) + '\n\n' + '\n\n'.join(colour_lines(advice))
        assert not style_violations(text), (stem, branch)


@pytest.mark.parametrize('stem,branch,wear,avoid', [
    ('甲', '子', ['火', '金'], ['水']),   # 「丁先庚後」: water puts out the 丁 it needs
    ('庚', '午', ['水'], ['土']),         # 「專用壬水」: earth dams it
    ('丁', '亥', ['木', '金'], []),       # 「端用庚甲」: metal overcomes 甲 but is itself asked for
    ('庚', '子', ['火', '木'], ['水']),
])
def test_known_cells(stem, branch, wear, avoid):
    advice = colour_advice(_chart(stem, branch))
    assert [w['wuxing'] for w in advice['wear']] == wear
    assert [a['wuxing'] for a in advice['avoid']] == avoid


def test_the_lead_answers_first_and_the_lines_give_every_link():
    advice = colour_advice(_chart('甲', '子'))
    lead = colour_lead(advice)
    assert lead == ('按你的八字，衣服首选红色、紫色（火），其次白色、金银色（金）；少穿黑色、深蓝色（水）；'
                    '佩戴首选红色、紫色的饰物（火），其次金银首饰、金属饰物（金）。')
    lines = '\n'.join(colour_lines(advice))
    for needle in ('qiongtong:c002:p0069', '十一月甲木，木性生寒，丁先庚後，丙火佐之', 'sanming:c007:p0004',
                   '「其色赤」「其色白」', 'meihua:c002:p0118', 'meihua:c003:p0069', 'ziping:c025:p0003',
                   '水克火，会压住你最需要的丁', '没有一句说穿某种颜色、戴某样东西'):
        assert needle in lines, needle


def test_conditions_keep_the_text_and_drop_only_usage_policy():
    assert _conditions('取丁甲、次丙；丙丁过多与水局另论，不把表名直接变成喜火的现实建议。') == \
        '取丁甲、次丙；丙丁过多与水局另论。'
    note = '庚丁为要、丙次；忌壬泛身时才须戊制，不能把戊无条件定为喜神。'
    assert _conditions(note) == note


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
    assert text.startswith('按你的八字，衣服首选红色、紫色（火），其次绿色、青色（木）')
    assert not style_violations(text)
    plain = prepare_reading(chart, '我适合做什么工作')
    assert 'colour_advice' not in plain and not render_facts(plain).startswith('按你的八字，衣服')


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
    ('我往哪个方位发展好', '按你的八字，有利方位是南方（火），其次西方（金）；少往北方（水）。'),
    ('我的幸运数字是几', '按你的八字，幸运数字是2、7（火），其次4、9（金）。'),
    ('我五行缺什么', '按《穷通宝鉴》调候，你的八字最需要火（丁），其次金（庚）。'),
])
def test_each_aspect_gets_its_own_first_sentence(question, lead):
    advice = colour_advice(_chart('甲', '子'), question)
    assert colour_lead(advice) == lead
    lines = '\n'.join(colour_lines(advice))
    if advice['aspects'] in (['direction'], ['number']):
        assert HETU_QUOTE in lines and HETU_SOURCE in lines
    if advice['aspects'] == ['element']:
        assert '古法不数哪种五行少' in lines and '《子平真诠》' in lines
