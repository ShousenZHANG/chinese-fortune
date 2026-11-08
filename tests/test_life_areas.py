"""人生领域速读：每个领域看哪颗星、原局在哪、哪年透出，引文逐字在原文里，不判好坏、不碰健康。"""
import json

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading, render_facts
from classical_search import get_passage
from life_areas import SOURCES, areas_asked, life_areas

BIRTH = ['--year', '1990', '--month', '5', '--day', '15', '--hour', '10', '--gender', 'male', '--as-of-year', '2026']


@pytest.fixture(scope='module')
def chart():
    return calculate_bazi(build_parser().parse_args(BIRTH))


def test_every_quote_is_in_its_passage():
    for rows in SOURCES.values():
        for pid, quote, _ in rows:
            assert quote in get_passage(pid)['text'], (pid, quote)


@pytest.mark.parametrize('question,expected', [
    ('我今年事业怎么样', ['career']), ('财运如何', ['wealth']), ('我的婚姻感情', ['relationship']),
    ('考研能不能上岸，学业如何', ['study']), ('人生领域速读', ['career', 'wealth', 'relationship', 'study']),
    ('看看八字', []), ('我身体健康吗', []),
])
def test_areas_are_read_from_the_question(question, expected):
    assert areas_asked(question) == expected


def test_reading_lists_positions_years_and_sources_without_verdicts(chart):
    reading = prepare_reading(chart, '人生领域速读')
    areas = {a['area']: a for a in reading['life_areas']['areas']}
    assert set(areas) == {'career', 'wealth', 'relationship', 'study'}
    # 庚日主，巳中丙为七杀。
    assert any('七杀' in place for place in areas['career']['natal'])
    years = areas['career']['timing']['years']
    assert [y['year'] for y in years] == [2026, 2027, 2028]
    assert {y['ganzhi'] for y in years} == {'丙午', '丁未', '戊申'}
    assert all(y['brings_star'] == any(r in ('正官', '七杀') for r in [y['stem_role'], *(h[2] for h in y['branch_roles'])])
               for y in years)
    assert areas['relationship']['palace']['branch'] == reading['chart_facts']['four_pillars']['day']['branch']
    assert '妻宫' in areas['relationship']['say']
    text = json.dumps(reading['life_areas'], ensure_ascii=False)
    for word in ('健康', '疾病', '大吉', '大凶', '必定'):
        assert word not in text.replace('不做健康断语', '')
    assert '不说好坏' in areas['career']['say']
    cited = {s['passage_id'] for a in areas.values() for s in a['sources']}
    assert cited <= {p['passage_id'] for p in reading['evidence_bundle']['passages']}
    draft = render_facts(reading)
    assert '事业：' in draft and '学业：' in draft


def test_female_relationship_reads_the_husband_star_and_keeps_the_books_caveat(chart):
    facts = prepare_reading(chart, '')['chart_facts']
    out = life_areas(facts, 'female', ['relationship'])['areas'][0]
    assert out['stars'] == ['正官', '七杀'] and '夫宫' in out['say'] and '不专以夫星定之' in out['say']
    unknown = life_areas(facts, None, ['relationship'])['areas'][0]
    assert unknown['status'] == 'gender_required'


def test_study_follows_the_xuetang_rule():
    # 甲日生，月支亥：甲长生在亥，月上见之即为学堂。
    facts = {'day_master': {'stem': '甲'}, 'four_pillars': {
        'year': {'branch': '子'}, 'month': {'branch': '亥'}, 'day': {'branch': '午'}, 'hour': {'branch': '寅'}}}
    out = life_areas(facts, 'male', ['study'])['areas'][0]
    assert out['changsheng'] == '亥' and out['hits'] == ['月柱'] and not out['clashed']
    clashed = {**facts, 'four_pillars': {**facts['four_pillars'], 'hour': {'branch': '巳'}}}
    out = life_areas(clashed, 'male', ['study'])['areas'][0]
    assert out['clashed'] and '刑衝破損' in out['say']
