"""Ranking must stay boolean, cited, and refuse to invent an order."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classical_search import get_passage  # noqa: E402
from fortune_ranking import (  # noqa: E402
    JIELU_SOURCE,
    TIANDI_SOURCE,
    jielu_kongwang,
    rank_travel_days,
    tiandi_zhuan,
    zodiac_clash,
)
from fortune_rules import PRECEDENCE_VERSION, capabilities  # noqa: E402


def _autumn(date: str, ganzhi: str) -> dict:
    return {'date': date, 'day_stem': ganzhi[0], 'day_branch': ganzhi[1], 'season': 'autumn'}


def test_cited_passages_resolve_and_contain_the_quoted_words():
    """A tier source that cannot be re-read is an invented rule."""
    tiandi = get_passage(TIANDI_SOURCE)
    assert '出行商贾' in tiandi['text']
    assert '秋乃金旺，见辛酉为天转，见癸酉为地转' in tiandi['text']
    jielu = get_passage(JIELU_SOURCE)
    assert '以日取时见之方是' in jielu['text']
    assert '求财主官皆不利' in jielu['text']


def test_tiandi_zhuan_hits_only_the_two_autumn_days():
    assert tiandi_zhuan('辛', '酉', 'autumn')['kind'] == '天转'
    assert tiandi_zhuan('癸', '酉', 'autumn')['kind'] == '地转'
    # Right stem, wrong branch; right branch, wrong stem; right pair, wrong season.
    assert tiandi_zhuan('辛', '卯', 'autumn') is None
    assert tiandi_zhuan('丁', '酉', 'autumn') is None
    assert tiandi_zhuan('辛', '酉', 'spring') is None


def test_jielu_is_an_hour_rule_keyed_on_the_day_stem():
    assert jielu_kongwang('己')['forbidden_hours'] == ['申', '酉']
    assert jielu_kongwang('丁')['forbidden_hours'] == ['寅', '卯']
    # Same pair for the paired stem, per the verse.
    assert jielu_kongwang('甲')['forbidden_hours'] == jielu_kongwang('己')['forbidden_hours']


def test_wu_gui_dissent_is_carried_not_hidden():
    """26-precedence.md forbids dropping the losing reading."""
    entry = jielu_kongwang('戊')
    assert entry['forbidden_hours'] == ['子', '丑']
    assert entry['dissent']['passage_id'] == 'sanming:c003:p0035'
    assert '戌亥' in entry['dissent']['text']
    assert 'dissent' not in jielu_kongwang('丁')


def test_zodiac_clash_is_folk_layer_and_never_cites_a_passage():
    hit = zodiac_clash('未', '丑')
    assert hit['layer'] == 'folk'
    assert hit['passage_id'] is None
    assert zodiac_clash('午', '丑') is None


def test_september_window_has_no_clause_ordering():
    """Regression on a real question this repo previously answered wrongly.

    A 2026-09-11..09-30 Sydney departure window was once ranked 09-22 first and
    09-27 second, with 09-18 and 09-30 excluded. That order came from almanac
    verdicts, which 24-personalized-forecast.md forbids as a ranking input.
    Under the clause tiers the whole window ties.
    """
    window = [
        _autumn('2026-09-11', '戊子'), _autumn('2026-09-12', '己丑'),
        _autumn('2026-09-13', '庚寅'), _autumn('2026-09-14', '辛卯'),
        _autumn('2026-09-15', '壬辰'), _autumn('2026-09-16', '癸巳'),
        _autumn('2026-09-17', '甲午'), _autumn('2026-09-18', '乙未'),
        _autumn('2026-09-19', '丙申'), _autumn('2026-09-20', '丁酉'),
        _autumn('2026-09-21', '戊戌'), _autumn('2026-09-22', '己亥'),
        _autumn('2026-09-23', '庚子'), _autumn('2026-09-24', '辛丑'),
        _autumn('2026-09-25', '壬寅'), _autumn('2026-09-26', '癸卯'),
        _autumn('2026-09-27', '甲辰'), _autumn('2026-09-28', '乙巳'),
        _autumn('2026-09-29', '丙午'), _autumn('2026-09-30', '丁未'),
    ]
    result = rank_travel_days(window, natal_year_branch='丑')
    assert result['excluded'] == []
    assert len(result['tiers']) == 20
    assert {t['tier'] for t in result['tiers']} == {1}
    assert result['ties'] is True
    # The two clash days stay in tier 1; they surface only as folk context.
    clash = {t['date'] for t in result['tiers'] if t['folk_context']}
    assert clash == {'2026-09-18', '2026-09-30'}


def test_a_real_autumn_prohibition_day_is_excluded():
    """辛酉 in autumn is the 天转 day the clause names.

    Dates are the real calendar ones: 2026-10-14 is 辛酉 and 2026-10-26 is 癸酉,
    the only two prohibition days in that autumn.
    """
    result = rank_travel_days([
        _autumn('2026-10-13', '庚申'),
        _autumn('2026-10-14', '辛酉'),
        _autumn('2026-10-26', '癸酉'),
    ])
    assert [e['date'] for e in result['excluded']] == ['2026-10-14', '2026-10-26']
    kinds = [e['excluded_by'][0]['kind'] for e in result['excluded']]
    assert kinds == ['天转', '地转']
    assert all(e['excluded_by'][0]['passage_id'] == TIANDI_SOURCE for e in result['excluded'])
    assert [t['date'] for t in result['tiers']] == ['2026-10-13']


def test_every_tier_carries_a_resolvable_source():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    for tier in result['tiers']:
        assert tier['sources']
        for pid in tier['sources']:
            assert get_passage(pid)['text']


def test_unmapped_scenario_refuses_to_borrow_travel_clauses():
    with pytest.raises(ValueError, match='未映射到古法名目'):
        rank_travel_days([_autumn('2026-09-22', '己亥')], scenario='wedding')


def test_ranking_declares_the_precedence_version_it_used():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    assert result['precedence_version'] == PRECEDENCE_VERSION
    assert result['ranking_reference'] == 'references/26-precedence.md'
    travel = next(c for c in capabilities('travel'))
    assert travel['personal_ranking'] == 'rule_based'
    assert travel['precedence_version'] == PRECEDENCE_VERSION


def _travel_request(candidates: list[dict], period: dict) -> dict:
    return {
        'current_timezone': 'Australia/Sydney', 'request_time': '2026-09-17T02:00:00Z',
        'period': period,
        'event': {'scenario': 'travel', 'timezone': 'Australia/Sydney',
                  'longitude': 151.2, 'time_standard': 'true-solar'},
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30,
                      'gender': 'male', 'timezone': 'Asia/Shanghai', 'longitude': 120.64},
            'time_certainty': 'exact'}}],
        'duration_minutes': 120, 'candidates': candidates, 'granularity': 'hour',
    }


def test_ranking_reaches_the_reading_output():
    """A rule_based scenario must actually rank; declaring it is not enough."""
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'oct13', 'start': '2026-10-13T09:00', 'end': '2026-10-13T13:00'},
         {'id': 'oct14', 'start': '2026-10-14T09:00', 'end': '2026-10-14T13:00'},
         {'id': 'oct15', 'start': '2026-10-15T09:00', 'end': '2026-10-15T13:00'}],
        {'start': '2026-10-13', 'end': '2026-10-16'}))
    ranking = result['ranking']
    # 2026-10-14 is 辛酉 — the autumn 天转 day the clause names.
    assert [e['candidate_id'] for e in ranking['excluded']] == ['oct14']
    excluded = ranking['excluded'][0]['excluded_by'][0]
    assert excluded['passage_id'] == TIANDI_SOURCE
    assert '出行商贾' in excluded['quote']
    judgments = {c['candidate_id']: c['judgment'] for c in result['candidate_comparison']}
    assert judgments == {'oct13': 'tier_1', 'oct14': 'excluded_by_clause', 'oct15': 'tier_1'}
    # 庚日忌午未; the 09:00-13:00 window covers 午.
    covered = next(t for t in ranking['tiers'] if t['candidate_id'] == 'oct13')
    assert covered['forbidden_hours_in_window'] == ['午']
    uncovered = next(t for t in ranking['tiers'] if t['candidate_id'] == 'oct15')
    assert uncovered['forbidden_hours_in_window'] == []


def test_survivors_tie_instead_of_getting_an_invented_first_choice():
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'd21', 'start': '2026-09-21T08:00', 'end': '2026-09-21T12:00'},
         {'id': 'd22', 'start': '2026-09-22T08:00', 'end': '2026-09-22T12:00'}],
        {'start': '2026-09-21', 'end': '2026-09-24'}))
    rec = result['recommendation']
    assert rec['status'] == 'tied_no_clause_separates'
    assert rec['first_choice'] is None
    assert sorted(rec['tied']) == ['d21', 'd22']
    assert rec['precedence_version'] == PRECEDENCE_VERSION


def test_rule_based_scenario_drops_the_missing_rules_blocker():
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'd22', 'start': '2026-09-22T08:00', 'end': '2026-09-22T12:00'}],
        {'start': '2026-09-21', 'end': '2026-09-24'}))
    codes = [b['code'] for b in result['decision_blockers']]
    assert 'ranking_rules_required' not in codes


def test_climate_colors_name_every_stem_the_clause_takes():
    """庚 born in 子 month: the clause takes 丁 and 甲, then 丙 conditionally.

    An earlier answer reported only the fire colour and dropped 甲 (wood)
    entirely, which narrowed a two-phase clause to one.
    """
    from fortune_ranking import climate_colors
    result = climate_colors('庚', '子')
    general = {row['wuxing']: row for row in result['general']}
    assert set(general) == {'火', '木'}
    assert general['火']['color'] == '红' and general['火']['from_stems'] == ['丁']
    assert general['木']['color'] == '青/绿' and general['木']['from_stems'] == ['甲']
    assert [r['wuxing'] for r in result['conditional']] == ['火']
    assert 'qiongtong:c005:p0114' in result['sources']


def test_climate_colors_carry_the_clauses_own_warning():
    """The audit already warns against turning the table into advice."""
    from fortune_ranking import climate_colors
    result = climate_colors('庚', '子')
    assert '不把表名直接变成喜火的现实建议' in result['clause_note']
    assert '不证明方位、颜色能改变结果' in result['color_table']['caveat']
    assert '没有任何出处' in result['broken_link']
    assert result['facsimile_status'] == 'not_checked'


def test_every_cited_climate_passage_resolves():
    from fortune_ranking import climate_colors
    for pid in climate_colors('庚', '子')['sources']:
        assert get_passage(pid)['text']


def test_result_states_what_it_does_not_cover():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    assert '跨时区班次' in result['not_covered']
    assert any('黄历' in result['scope'] for _ in (0,))
