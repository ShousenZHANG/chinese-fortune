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
    modality_violations,
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
        assert lead.startswith('按《穷通宝鉴》调候，')
        # 「兼用」 cells (辛午) use their stems together; every other cell names a first.
        assert ('兼用' in lead) if advice['jointly'] else ('这一格一般先取' in lead), (stem, branch)
        # Every cell reads as the general choice. Cells whose note names a frame or
        # an excess report what the known branches settle; the rest say nothing was checked.
        assert '这是这一格的一般取法' in lead
        if advice['exception_checks']:
            assert '这一格另论的例外，按你的盘：' in lead
        else:
            assert lead.endswith('这是这一格的一般取法，你的盘是不是原文说的例外（见下）还没有逐条核对。')
        # A chart with only a month branch cannot rule a frame out.
        assert all(c['status'] != 'not_met' for c in advice['exception_checks']), (stem, branch)
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


def test_charts_that_share_the_cell_differ_where_the_branches_decide():
    """Two 庚-in-子 charts, one with a 申子辰 water frame. 水局 is read off the
    branches, so the two answers must now differ on it; 丙丁过多 has no stated
    threshold and stays undecided in both, so neither may read as settled."""
    plain = {'day_master': {'stem': '庚'}, 'four_pillars': {
        'year': {'stem': '甲', 'branch': '辰'}, 'month': {'stem': '丙', 'branch': '子'},
        'day': {'stem': '庚', 'branch': '寅'}, 'hour': {'stem': '戊', 'branch': '寅'}}}
    fiery = {'day_master': {'stem': '庚'}, 'four_pillars': {
        'year': {'stem': '丙', 'branch': '申'}, 'month': {'stem': '丙', 'branch': '子'},
        'day': {'stem': '庚', 'branch': '辰'}, 'hour': {'stem': '丁', 'branch': '亥'}}}
    leads = [colour_lead(colour_advice(chart, '我穿什么颜色好')) for chart in (plain, fiery)]
    assert leads[0] != leads[1]
    assert '水局不成立' in leads[0] and '水局成立' in leads[1]
    assert '审校说明' in leads[1] and '审校说明' not in leads[0]
    for lead in leads:
        assert '一般取法' in lead and '丙丁过多' in lead and '没判' in lead
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


def _four(year: str, month: str, day: str, hour: str | None) -> dict:
    pillars = {'year': {'stem': year[0], 'branch': year[1]}, 'month': {'stem': month[0], 'branch': month[1]},
               'day': {'stem': day[0], 'branch': day[1]}}
    if hour:
        pillars['hour'] = {'stem': hour[0], 'branch': hour[1]}
    return {'day_master': {'stem': day[0]}, 'four_pillars': pillars}


def test_the_water_frame_is_decided_from_the_branches():
    """丁丑 壬子 庚子 丙戌: branches 丑子子戌 complete neither 申子辰 nor 亥子丑."""
    advice = colour_advice(_four('丁丑', '壬子', '庚子', '丙戌'))
    checks = {c['condition']: c for c in advice['exception_checks']}
    assert checks['水局']['status'] == 'not_met'
    assert '申子辰' in checks['水局']['basis'] and '亥子丑' in checks['水局']['basis']
    assert checks['丙丁过多']['status'] == 'unknown'
    assert '多少算多' in checks['丙丁过多']['reason']
    lead = colour_lead(advice)
    assert '水局不成立' in lead and '丙丁过多' in lead and '没判' in lead


def test_a_complete_frame_points_to_the_note_without_deciding_its_effect():
    advice = colour_advice(_four('丙申', '丙子', '庚辰', '丁亥'))
    checks = {c['condition']: c for c in advice['exception_checks']}
    assert checks['水局']['status'] == 'met' and '申子辰' in checks['水局']['basis']
    lead = colour_lead(advice)
    assert '水局成立' in lead and '审校说明' in lead and '不能直接套' not in lead
    # The note is the reviewer's paraphrase, and here it says nothing about the
    # effect («丙丁过多与水局另论»): it may not be called the passage.
    assert '原文写在' not in lead and '对照这一格的原文' in lead


@pytest.mark.parametrize('pillars,frame', [
    # 戊 in 午: 「先壬次甲…癸力微，火局不能等同壬的作用」 — the frame keeps 壬 first.
    (('甲寅', '庚午', '戊戌', '丙辰'), '火局'),
    # 辛 in 午: 「壬己兼用…火局癸可能无力」 — again the general choice itself.
    (('甲寅', '庚午', '辛卯', '戊戌'), '火局'),
])
def test_a_met_frame_that_confirms_the_general_choice_is_not_called_an_override(pillars, frame):
    """The note of these cells says what the frame does to 癸, not that 壬 is
    wrong. Saying 「一般取法不能直接套」 would contradict the passage."""
    advice = colour_advice(_four(*pillars))
    assert {c['condition']: c for c in advice['exception_checks']}[frame]['status'] == 'met'
    lead = colour_lead(advice)
    assert f'{frame}成立' in lead and '不能直接套' not in lead and '另有取法' not in lead


def test_a_missing_hour_leaves_a_frame_one_branch_short_undecided():
    """申 子 plus an unknown hour: 辰 could still arrive in the hour pillar."""
    short = colour_advice(_four('丙申', '丙子', '庚寅', None))
    assert {c['condition']: c for c in short['exception_checks']}['水局']['status'] == 'unknown'
    # Two branches short cannot be completed by one hour pillar.
    far = colour_advice(_four('丙午', '丙子', '庚寅', None))
    assert {c['condition']: c for c in far['exception_checks']}['水局']['status'] == 'not_met'


def test_a_cell_without_a_checkable_exception_keeps_the_plain_caveat():
    """甲 in 未 month: its note names no 局 and no 过多."""
    advice = colour_advice(_four('甲子', '辛未', '甲寅', '甲子'))
    assert advice['exception_checks'] == []
    assert '还没有逐条核对' in colour_lead(advice)


def test_stems_the_passage_uses_together_are_not_ranked():
    """辛 in 午: 「壬己兼用」. 「先取壬，其次己」 would demote 己 to second."""
    advice = colour_advice(_four('甲寅', '庚午', '辛卯', '戊戌'))
    lead = colour_lead(advice, ['colour', 'direction'])
    assert '壬（水）、己（土）兼用' in lead and '其次己' not in lead, lead
    assert '不分先后' in lead and '首选' not in lead


def test_no_cell_renders_a_modal_word_stronger_or_weaker_than_its_note():
    """All 120 cells, every aspect: a conditional stem is never a general
    choice, and stems used together are never put in order."""
    aspects = ['colour', 'things', 'direction', 'number']
    for stem in STEMS:
        for branch in BRANCHES:
            advice = colour_advice(_chart(stem, branch))
            if advice['status'] != 'ok':
                continue
            assert modality_violations(advice, colour_lead(advice, aspects)) == [], (stem, branch)


def test_the_modality_check_catches_both_kinds_of_drift():
    joint = colour_advice(_four('甲寅', '庚午', '辛卯', '戊戌'))
    assert modality_violations(joint, '这一格一般先取壬（水），其次己（土）。')
    conditional = colour_advice(_chart('甲', '未'))          # 「无癸亦可」: 癸 is conditional
    assert modality_violations(conditional, '这一格一般先取癸（水）。')
    assert modality_violations(conditional, '这一格一般先取丁（火），其次癸（水）。')
