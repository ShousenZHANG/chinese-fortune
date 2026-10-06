"""大运取运判断：审定数据与判断逻辑（spec docs/superpowers/specs/2026-10-06-luck-assessment-design.md）。"""
import json
from pathlib import Path

import pytest
from classical_search import get_passage
from luck_assessment import assess_luck

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / 'assets' / 'luck_rules.json').read_text(encoding='utf-8'))
ROLES = {'比肩', '劫财', '食神', '伤官', '偏财', '正财', '七杀', '正官', '偏印', '正印'}
VERDICTS = {'favoured', 'avoided', 'harmless', 'unpromising'}
PREDICATES = {'present_any', 'exposed_any', 'exposed_none', 'combines', 'exposed_count_at_least'}


def _scenarios():
    return [s for f in RULES['families'] for s in f['scenarios']]


def _effects(s):
    return s.get('effects', []) + [e for b in s.get('branches', []) for e in b['effects']]


def test_only_the_first_batch_is_connected():
    assert [f['family_id'] for f in RULES['families']] == ['officer', 'wealth', 'hurt']
    assert [f['chapter'] for f in RULES['families']] == ['ziping:c032', 'ziping:c034', 'ziping:c042']


@pytest.mark.parametrize('scenario', _scenarios(), ids=lambda s: s['id'])
def test_every_quote_is_the_frozen_text_and_every_verdict_is_in_it(scenario):
    passage = get_passage(scenario['passage_id'])
    assert passage['sha256'] == scenario['sha256']
    assert scenario['quote'] in passage['text']
    for effect in _effects(scenario):
        assert effect['verdict'] in VERDICTS
        assert effect['words'] in scenario['quote'], (scenario['id'], effect['words'])
        assert set(effect.get('roles', [])) <= ROLES and set(effect.get('combines_natal', [])) <= ROLES
        assert effect.get('roles') or effect.get('combines_natal')
    for premise in scenario['premises'] + [b for b in scenario.get('branches', []) if b.get('predicate')]:
        assert premise['predicate'] in PREDICATES
        assert set(premise.get('roles', [])) <= ROLES and set(premise.get('with', [])) <= ROLES
    for branch in scenario.get('branches', []):
        assert branch['kind'] in ('computed', 'interpretive')
        assert branch['kind'] == 'interpretive' or branch.get('predicate')


def test_every_luck_paragraph_of_the_three_chapters_has_a_scenario():
    """All but each chapter's general remarks (c032 p0001 p0007, c034 p0001, c042 p0001)."""
    used = {s['passage_id'] for s in _scenarios()}
    expected = ({f'ziping:c032:p{i:04}' for i in range(2, 7)} | {f'ziping:c034:p{i:04}' for i in range(2, 9)}
                | {f'ziping:c042:p{i:04}' for i in range(2, 8)})
    assert used == expected


@pytest.mark.parametrize('note', RULES['notes'], ids=lambda n: n['id'])
def test_every_general_note_is_the_frozen_text(note):
    passage = get_passage(note['passage_id'])
    assert passage['sha256'] == note['sha256'] and note['quote'] in passage['text']



def _chart(year, month, day, hour, hour_known=True):
    pillars = {'year': {'stem': year[0], 'branch': year[1]}, 'month': {'stem': month[0], 'branch': month[1]},
               'day': {'stem': day[0], 'branch': day[1]}, 'hour': {'stem': hour[0], 'branch': hour[1]}}
    return {'day_master': {'stem': day[0]}, 'four_pillars': pillars, 'hour_known': hour_known}


USER = _chart('丁丑', '壬子', '庚子', '丙戌')
JI_YOU = {'ganzhi': '己酉', 'start_year': 2023, 'end_year': 2032}


def test_the_users_own_chart_in_the_ji_you_cycle():
    """庚 in 子 (伤官): 佩印, 用煞印, 带煞, 用官 all stand by the stems and storage."""
    reading = assess_luck(USER, JI_YOU)
    assert reading['status'] == 'assessed'
    assert {s['id'] for s in reading['scenarios']} == {'hurt-seal', 'hurt-kill-seal', 'hurt-kill', 'hurt-officer'}
    assert reading['summary'] == {'stem': 'favoured', 'branch': 'conditional'}
    assert reading['scenarios'][0]['branch']['via'] == '本气辛'
    assert {f['family_id']: f['connected'] for f in reading['families']} == {'hurt': True}


def test_a_missing_hour_or_cycle_gives_no_verdict():
    assert assess_luck(_chart('丁丑', '壬子', '庚子', '丙戌', hour_known=False), JI_YOU)['status'] == 'unavailable'
    assert assess_luck(USER, {'status': 'birth_time_required'})['status'] == 'unavailable'


def test_a_family_not_yet_connected_is_said_so():
    """甲 in 子: 癸 is 正印, the seal family, whose chapter is not in this batch."""
    reading = assess_luck(_chart('甲子', '丙子', '甲寅', '甲子'), {'ganzhi': '丁丑', 'start_year': 2020, 'end_year': 2029})
    assert reading['status'] == 'assessed' and not reading['scenarios']
    assert reading['families'][0]['connected'] is False


def test_a_computed_branch_overrides_the_general_sentence():
    """财旺生官带食破局: 「逢煞反吉」 replaces 「不利七煞」 (c034 p0002)."""
    # 甲 in 辰 (戊 偏财 本气), 辛 正官 exposed, 丙 食神 exposed; 七杀 庚 cycle.
    chart = _chart('辛酉', '丙辰', '甲子', '丙寅')
    reading = assess_luck(chart, {'ganzhi': '庚午', 'start_year': 2020, 'end_year': 2029})
    w1 = next(s for s in reading['scenarios'] if s['id'] == 'wealth-officer')
    assert [v['verdict'] for v in w1['stem']['verdicts']] == ['favoured']
    assert w1['stem']['verdicts'][0]['words'] == '逢煞反吉'


def test_a_cycle_stem_combining_the_exposed_officer_is_avoided():
    """《论行运》p0008 「丁生亥月，而年透壬官……逢丁則合官」: 丁 combines the 壬 officer, 「不可逢合」 (c032 p0002)."""
    chart = _chart('壬寅', '辛亥', '丁卯', '庚子')
    reading = assess_luck(chart, {'ganzhi': '丁未', 'start_year': 2020, 'end_year': 2029})
    general = next(s for s in reading['scenarios'] if s['id'] == 'officer-exposed')
    assert [v['words'] for v in general['stem']['verdicts']] == ['不可逢合']


def test_robbery_combining_the_killer_is_computed():
    """正官带煞, 用劫合煞 (c032 p0006): 乙 劫财 and 庚 七杀 both exposed for 甲, 乙庚 combine."""
    chart = _chart('乙卯', '辛酉', '甲子', '庚午')
    reading = assess_luck(chart, {'ganzhi': '戊申', 'start_year': 2020, 'end_year': 2029})
    o5 = next(s for s in reading['scenarios'] if s['id'] == 'officer-kill')
    assert any(v['words'] == '財運可行' and v['state'] == 'met' for v in o5['stem']['verdicts'])


def test_conflicting_candidates_are_mixed_not_chosen():
    """伤官佩印 says 「財地則凶」, 伤官用财's strong-body branch 「喜財運」: a wealth cycle is
    avoided in one and only conditional in the other, so the summary keeps the definite one;
    two definite opposite verdicts would be mixed."""
    from luck_assessment import _summarise
    assert _summarise([['favoured'], ['avoided']], []) == 'mixed'
    assert _summarise([['favoured'], ['favoured']], [['avoided']]) == 'favoured'
    assert _summarise([], [['favoured']]) == 'conditional'
    assert _summarise([], []) == 'not_mentioned'


def test_a_clash_with_the_year_or_month_is_urgent_with_the_day_or_hour_mild():
    """《论行运》p0006 丙生子月亥年：巳 clashes 亥 (year), 午 clashes 子 (month); p0010 年月则急。"""
    chart = _chart('辛亥', '庚子', '丙寅', '戊戌')
    si = assess_luck(chart, {'ganzhi': '丁巳', 'start_year': 2020, 'end_year': 2029})
    n3 = next(n for n in si['notes'] if n['id'] == 'N3')
    assert '冲年支亥' in n3['text'] and '急' in n3['text']
    shen = assess_luck(chart, {'ganzhi': '丙申', 'start_year': 2030, 'end_year': 2039})
    assert '冲日支寅' in next(n for n in shen['notes'] if n['id'] == 'N3')['text']
    assert '缓' in next(n for n in shen['notes'] if n['id'] == 'N3')['text']


def test_an_officer_cycle_of_hurt_with_a_seal_exposed_seems_bad_but_is_not():
    """p0005 「官逢傷運，而命透印」."""
    chart = _chart('癸酉', '辛酉', '甲子', '癸酉')     # 甲 in 酉: 辛 正官 本气; 癸 正印 exposed
    reading = assess_luck(chart, {'ganzhi': '丁卯', 'start_year': 2020, 'end_year': 2029})
    assert any(n['id'] == 'N2' for n in reading['notes'])


def test_no_note_when_nothing_clashes():
    reading = assess_luck(USER, JI_YOU)        # 酉 clashes 卯; the user's branches are 丑子子戌
    assert not any(n['id'] == 'N3' for n in reading['notes'])


def test_a_note_quotes_the_frozen_text_not_a_paraphrase():
    chart = _chart('辛亥', '庚子', '丙寅', '戊戌')
    reading = assess_luck(chart, {'ganzhi': '丁巳', 'start_year': 2020, 'end_year': 2029})
    for note in reading['notes']:
        assert note['quote'] in get_passage(note['passage_id'])['text'] and '原文' not in note['text'][:2]


def test_the_paragraph_says_the_cycle_the_agreement_and_the_limits():
    from luck_assessment import luck_paragraph
    text = luck_paragraph(assess_luck(USER, JI_YOU))
    assert text.startswith('你现在走的己酉运（2023–2032）')
    assert '几种可能的配法都算喜' in text and '「印運亦吉」' in text
    assert '看条件' in text and '按本气辛' in text
    assert '十年一个说法，不细到每天' in text and '逐日吉凶仍按出生年相主' in text


def test_the_paragraph_for_an_unconnected_family_or_missing_hour():
    from luck_assessment import luck_paragraph
    seal = assess_luck(_chart('甲子', '丙子', '甲寅', '甲子'), {'ganzhi': '丁丑', 'start_year': 2020, 'end_year': 2029})
    assert '取运章还没接入' in luck_paragraph(seal)
    gone = assess_luck(_chart('丁丑', '壬子', '庚子', '丙戌', hour_known=False), JI_YOU)
    assert luck_paragraph(gone).startswith('这步大运的喜忌这次给不出：出生时辰未知')


def _period(start, end):
    return {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-10-05T10:00:00Z',
            'question': '未来七天哪天对我好', 'intent': 'period', 'period': {'start': start, 'end': end},
            'event': {'scenario': 'outlook', 'timezone': 'Asia/Shanghai', 'longitude': 120.64},
            'participants': [{'id': 'me', 'confirmed': True, 'person': {
                'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                          'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}}]}


def test_a_period_answer_carries_the_cycle_and_keeps_the_daily_grades():
    from fortune_reading import read_request, render_answer
    result = read_request(_period('2026-10-06T00:00:00+08:00', '2026-10-13T00:00:00+08:00'))
    readings = result['participants'][0]['luck_reading']
    assert [r['luck']['ganzhi'] for r in readings] == ['己酉'] and readings[0]['status'] == 'assessed'
    grades = [e['grade'] for e in result['personal_calendar']['entries']]
    text = render_answer(result)
    assert '你现在走的己酉运' in text and '逐日吉凶仍按出生年相主' in text
    assert '已实现的两条运程例式没有给出本题的完整结论' not in text
    assert grades == [e['grade'] for e in read_request(_period('2026-10-06T00:00:00+08:00',
                                                               '2026-10-13T00:00:00+08:00'))['personal_calendar']['entries']]
