"""Colours and things to wear come from the 调候 cell's general choice, every
link cited, and say that the cell's exceptions were not checked on the chart."""
import re

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
        # Cells whose note takes the stems in no order say so; every other cell names a first.
        if advice['order'] == 'ranked':
            assert '这一格一般先取' in lead, (stem, branch)
        else:
            assert '先取' not in lead and '其次' not in lead.split('这是这一格')[0], (stem, branch)
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
    # 「或支成水局，不见丙丁者」: this chart shows 丙 and 丁, so that sentence does not apply.
    assert '要不见丙丁' in leads[1] and '不适用' in leads[1] and '要不见丙丁' not in leads[0]
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


def test_a_complete_frame_whose_condition_fails_keeps_the_general_choice():
    """庚 in 子: 「或支成水局，不见丙丁者，此乃伤官格」 (qiongtong:c005:p0116).
    With 丙 and 丁 in the stems the sentence does not apply; the v5.3.0 audit's
    example (丙申 庚子 庚辰 丙子) is this case."""
    advice = colour_advice(_four('丙申', '丙子', '庚辰', '丁亥'))
    checks = {c['condition']: c for c in advice['exception_checks']}
    assert checks['水局']['status'] == 'met' and checks['水局']['effect'] == 'not_applicable'
    assert advice['personal_choice'] is True
    lead = colour_lead(advice)
    assert '衣服首选红色、紫色（火）' in lead and '你的盘天干有丙、丁' in lead


def test_a_complete_frame_whose_condition_holds_withholds_the_personal_choice():
    """The same frame with no 丙丁 among the stems: the passage turns to 伤官格."""
    advice = colour_advice(_four('甲申', '壬子', '庚辰', '戊子'))
    assert advice['personal_choice'] is False and advice['individual_application'] == 'exception_met'
    lead = colour_lead(advice)
    assert lead.startswith('按你的盘，这一问给不出个人首选的颜色')
    assert '首选红色' not in lead and '「或支成水局，不见丙丁者，此乃伤官格' in lead
    assert 'qiongtong:c005:p0116' in lead


def test_a_frame_that_takes_another_stem_withholds_the_personal_choice():
    """甲 in 寅 with 亥卯未: 「支成木局，得庚为贵」 (qiongtong:c002:p0012)."""
    advice = colour_advice(_four('丙亥', '庚寅', '甲卯', '丙未'))
    lead = colour_lead(advice)
    assert advice['personal_choice'] is False and '「支成木局，得庚为贵' in lead and '衣服首选' not in lead


def test_every_frame_a_note_names_has_a_reviewed_effect():
    import re

    from tiaohou_provenance import _registry
    from wuxing_colours import FRAME_RE, FRAME_REVIEW
    pairs = {(k, w) for k, c in _registry()['cells'].items() for w in FRAME_RE.findall(c.get('review_note') or '')
             if w != '土'}
    assert set(FRAME_REVIEW) == pairs
    for (key, wuxing), (effect, condition, stems, passage) in FRAME_REVIEW.items():
        assert effect in ('confirms', 'changes') and condition in ('', 'absent', 'present')
        assert bool(condition) == bool(stems) and all(st in '甲乙丙丁戊己庚辛壬癸' for st in stems)
        text = get_passage(passage)['text']
        # The reviewed sentence speaks of this frame (or of 炎局 for fire), except
        # 庚卯 and 庚亥, whose passages name the branches instead of the frame.
        if key not in ('庚|卯', '庚|亥'):
            assert re.search(f'{wuxing}局' + ('|炎局' if wuxing == '火' else ''), text), (key, wuxing)


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


ORDER_WORDS = r'兼用|並用|并用|皆用|同用|並論|并论|並配|并配|參酌|参酌|隨宜|随宜|酌用|不拘|非拘|先後|先后'


def _cell_texts(key: str) -> str:
    from tiaohou_provenance import get_tiaohou_audit
    audit = get_tiaohou_audit(key)
    return audit['review_note'] + '\n' + '\n'.join(get_passage(r['passage_id'])['text'] for r in audit['source_refs'])


def test_every_cell_whose_note_or_passage_frees_the_order_is_reviewed():
    """Any cell with two or more general stems whose note or cited passage says
    兼用, 并用, 皆用, 并论, 参酌, 随宜, 酌用 or 不拘先后 must be in the reviewed
    table, as unordered or as ordered despite the word, with its evidence
    quoted from the note or the passage."""
    from tiaohou_provenance import get_tiaohou_audit
    from wuxing_colours import ORDERED_DESPITE, UNORDERED
    for stem in STEMS:
        for branch in BRANCHES:
            key = f'{stem}|{branch}'
            general = get_tiaohou_audit(key)['source_general_candidates']
            # One element (庚辛, 丁丙) has one colour: there is no order to get wrong.
            if len({TIANGAN_WUXING[g] for g in general}) > 1 and re.search(ORDER_WORDS, _cell_texts(key)):
                assert key in UNORDERED or key in ORDERED_DESPITE, key
    for key, (_kind, evidence, _phrase) in UNORDERED.items():
        assert evidence in _cell_texts(key), key
    for key, evidence in ORDERED_DESPITE.items():
        assert evidence in _cell_texts(key), key


def test_bing_hai_is_chosen_by_what_is_strong():
    """丙 in 亥: 「木旺宜庚，水旺宜戊，火旺用壬，随宜酌用可也」 (qiongtong:c003:p0133)."""
    lead = colour_lead(colour_advice(_four('甲寅', '乙亥', '丙寅', '戊子')))
    assert '随宜酌用' in lead and '先取' not in lead and '其次' not in lead.split('这是这一格')[0], lead


def test_stems_of_one_element_are_all_named():
    """癸 in 午: 「庚辛壬参酌并用」. 庚 and 辛 are both metal; naming only 庚 drops 辛."""
    lead = colour_lead(colour_advice(_chart('癸', '午')))
    assert '庚、辛（金）' in lead, lead
    jia_you = colour_lead(colour_advice(_chart('甲', '酉')))       # 「丁先、丙次、庚再次」
    assert '先取丁、丙（火），其次庚（金）' in jia_you, jia_you


def test_all_three_used_together_in_ding_you():
    """丁 in 酉: 「八月甲丙庚皆用」 (qiongtong:c003:p0249)."""
    lead = colour_lead(colour_advice(_four('甲寅', '癸酉', '丁卯', '壬寅')))
    assert '甲（木）、丙（火）、庚（金）并用' in lead and '不分先后' in lead and '其次' not in lead, lead
    # Wearables list all three: keeping the first two would rank them after all.
    wearing = lead.split('佩戴')[1].split('；')[0]
    assert all(f'（{w}）' in wearing for w in '木火金'), wearing
    # Layer 2 quotes a source for every wearable it names.
    lines = '\n'.join(colour_lines(colour_advice(_four('甲寅', '癸酉', '丁卯', '壬寅'))))
    assert all(THINGS[w][1] in lines for w in '木火金'), lines


def test_geng_si_is_chosen_by_the_charts_trouble_not_in_order():
    """庚 in 巳: 「須用壬丙戊，但非拘执先後，宜分病用药」 (qiongtong:c005:p0051)."""
    advice = colour_advice(_four('甲寅', '己巳', '庚辰', '丙子'))
    lead = colour_lead(advice)
    assert '不拘先后' in lead and '先取' not in lead and '其次戊' not in lead, lead
    assert '须用壬（水）、戊（土）' in lead and '都可用' not in lead, lead   # 「须用」, not weaker
    assert modality_violations(advice, '这一格一般先取壬（水），其次戊（土）。')


def test_ding_wu_takes_geng_only_on_a_condition():
    """丁 in 午: 庚 comes with a 火局 (「得庚壬两透」) or with 甲 when water shows
    and there is no 火局 (「须用甲木，又要庚劈甲」); neither is the general case."""
    advice = colour_advice(_four('甲寅', '庚午', '丁卯', '庚子'))
    assert [n['stem'] for n in advice['needed']] == ['壬']
    assert '庚' in advice['tiaohou']['conditional_stems']
    assert modality_violations(advice, '这一格一般先取壬（水），其次庚（金）。')
