"""Ranking must stay boolean, cited, and refuse to invent an order."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classical_search import get_passage  # noqa: E402
from fortune_ranking import (  # noqa: E402
    JIELU_METHOD_SOURCE,
    JIELU_UNRESOLVED_STEMS,
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
    jielu = get_passage(JIELU_METHOD_SOURCE)
    assert '以日取时见之方是' in jielu['text']
    assert '求财主官皆不利' in jielu['text']


def _ren_gui_hour_pairs(day_stem: str) -> list[tuple[str, str]]:
    """Independent 五鼠遁 derivation of the clause's own criterion.

    《渊海子平》c048:p0004 states the test: 遁十二时，见壬癸为水 —— the hours whose
    stem is 壬 or 癸. Derived here from scratch so the test can contradict the
    table it checks.
    """
    stems = '甲乙丙丁戊己庚辛壬癸'
    branches = '子丑寅卯辰巳午未申酉戌亥'
    first = {'甲': '甲', '己': '甲', '乙': '丙', '庚': '丙', '丙': '戊', '辛': '戊',
             '丁': '庚', '壬': '庚', '戊': '壬', '癸': '壬'}[day_stem]
    start = stems.index(first)
    hits = [branches[i] for i in range(12) if stems[(start + i) % 10] in '壬癸']
    return [(hits[i], hits[i + 1]) for i in range(0, len(hits), 2)]


def test_wu_and_gui_are_the_only_stems_the_clauses_own_test_cannot_settle():
    """Overturns the tier-3 example 26-precedence.md once claimed as settled.

    It read: 戊癸日五鼠遁起壬子，子时壬子、丑时癸丑 —— 只有《渊海》的子丑符合该判据.
    That arithmetic is incomplete: the same 遁 also yields 壬戌 and 癸亥, so
    《三命通会》的戌亥 satisfies 二时上俱遇壬癸为水 equally well. 戊/癸 are the only
    two stems with a second pair, which is exactly why the two books diverge
    there and nowhere else. Per 26-precedence.md「判不出来的，回到列分歧」an undecidable case
    goes back to 列分歧.
    """
    pairs = {stem: _ren_gui_hour_pairs(stem) for stem in '甲乙丙丁戊己庚辛壬癸'}
    assert pairs['戊'] == [('子', '丑'), ('戌', '亥')]
    assert pairs['癸'] == pairs['戊']
    assert {s for s, p in pairs.items() if len(p) > 1} == set(JIELU_UNRESOLVED_STEMS)
    # Every settled stem matches the verse 《三命通会》 quotes for it.
    assert pairs['甲'] == [('申', '酉')] and pairs['乙'] == [('午', '未')]
    assert pairs['丙'] == [('辰', '巳')] and pairs['丁'] == [('寅', '卯')]


def test_the_hour_table_matches_the_criterion_it_claims_to_follow():
    """Mutating one row of JIELU_HOURS used to leave all 3000 tests green.

    Worse, the shipped ``derivation`` string is built from whatever the table
    says and ends in 二时上俱遇壬癸为水 regardless, so a wrong row produced a
    citation that contradicted itself while looking checkable.
    """
    from fortune_ranking import JIELU_HOURS, _wu_zi_dun
    for stem in '甲乙丙丁己庚辛壬':
        expected = _ren_gui_hour_pairs(stem)
        assert len(expected) == 1, stem
        assert list(JIELU_HOURS[stem]) == list(expected[0]), stem
        entry = jielu_kongwang(stem)
        dun = _wu_zi_dun(stem)
        # The derivation may only claim 壬癸 for hours that really carry them.
        for hour in entry['forbidden_hours']:
            assert dun[hour] in '壬癸', (stem, hour)
            assert dun[hour] + hour in entry['derivation'], (stem, hour)


def test_an_unresolved_stem_reports_both_readings_and_forbids_nothing():
    """26-precedence.md: 判不出来的，回到列分歧."""
    for stem in ('戊', '癸'):
        entry = jielu_kongwang(stem)
        assert entry['resolved'] is False
        assert entry['forbidden_hours'] == []
        readings = {tuple(r['hours']): r['passage_id'] for r in entry['readings']}
        assert readings == {('子', '丑'): 'yuanhai:c048:p0003',
                            ('戌', '亥'): 'sanming:c003:p0035'}
        for pid in readings.values():
            assert get_passage(pid)['text']


def test_a_settled_stem_cites_a_passage_that_backs_the_hours_it_names():
    """p0004 gives the method and one worked example; the derivation must ship.

    The earlier table cited p0004 for every stem, but p0004 names only 甲己见申酉
    and then says 余皆仿此 —— a reader checking 庚 found nothing to check.
    """
    entry = jielu_kongwang('庚')
    assert entry['resolved'] is True
    assert entry['forbidden_hours'] == ['午', '未']
    assert entry['passage_id'] == JIELU_METHOD_SOURCE
    assert '壬午' in entry['derivation'] and '癸未' in entry['derivation']
    assert 'readings' not in entry


def test_precedence_moved_the_wu_gui_case_into_the_unresolved_table():
    text = (ROOT / 'references' / '26-precedence.md').read_text(encoding='utf-8')
    assert '只有《渊海》的子丑符合该判据' not in text
    unresolved = text.split('## 已知的未决分歧')[1]
    assert '截路空亡戊癸' in unresolved
    assert 'yuanhai:c048:p0003' in unresolved and 'sanming:c003:p0035' in unresolved


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


def test_neither_reading_is_dropped_for_an_unresolved_stem():
    """26-precedence.md forbids dropping the losing reading.

    It used to be carried as a ``dissent`` note beside a chosen winner; the
    winner turned out to be unearned (see the 五鼠遁 test below), so both
    readings now sit side by side and neither is applied.
    """
    entry = jielu_kongwang('戊')
    assert '戌亥' in ''.join(r['text'] for r in entry['readings'])
    assert '子丑' in ''.join(r['text'] for r in entry['readings'])
    assert 'readings' not in jielu_kongwang('丁')


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
    # 庚日忌午未; the 09:00-13:00 window covers 午. Each hit names the day whose
    # stem produced the rule, so a multi-day window cannot borrow the wrong one.
    covered = next(t for t in ranking['tiers'] if t['candidate_id'] == 'oct13')
    assert [(h['day_ganzhi'], h['hour_branch']) for h in covered['forbidden_hours_in_window']] \
        == [('庚申', '午')]
    assert covered['forbidden_hours_in_window'][0]['passage_id'] == JIELU_METHOD_SOURCE
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


_OCT = {'start': '2026-10-13', 'end': '2026-10-17'}


def _slot(cid: str, date: str, start: str = '09:00', end: str = '13:00') -> dict:
    return {'id': cid, 'start': f'{date}T{start}', 'end': f'{date}T{end}'}


def test_every_recommendation_status_renders_instead_of_raising():
    """A ranked travel request used to die in the plain-language path.

    ``render_answer``'s ``reasons`` table never grew the two statuses the
    ranking introduced, and ``main``'s ``except KeyError`` turned the crash into
    「目前还算不了这一部分」—— so the one scenario that ranks produced a false
    「算不了」 on the one output path a person reads. JSON callers saw the real
    answer, which is why 2982 passing tests missed it.
    """
    from fortune_reading import read_request, render_answer
    cases = {
        'ranked': [_slot('oct15', '2026-10-15')],
        'tied_no_clause_separates': [_slot('oct13', '2026-10-13'),
                                     _slot('oct15', '2026-10-15')],
        'excluded_by_clause': [_slot('oct14', '2026-10-14')],
    }
    for expected, candidates in cases.items():
        result = read_request(_travel_request(candidates, _OCT))
        assert result['recommendation']['status'] == expected, expected
        text = render_answer(result)
        lead = text.splitlines()[0]
        assert '算不了' not in lead, (expected, lead)
        assert '还不足以' not in lead, (expected, lead)
        # Every verdict must be re-checkable: the clause that decided it, by id.
        assert 'yuanhai:c052:p0004' in text, expected
    # 庚申 covers 午 in the 09:00-13:00 window, so the tied lead must say so and
    # say which candidate — deleting _hour_caveat used to leave everything green.
    tied = render_answer(read_request(_travel_request(
        cases['tied_no_clause_separates'], _OCT))).splitlines()[0]
    assert 'oct13 的窗口压到 庚申日的午时' in tied
    assert '截路空亡忌时' in tied


def test_a_fully_excluded_window_is_a_verdict_not_a_plea_for_evidence():
    """2026-10-14 is 辛酉 —— the autumn 天转 day, and the only candidate.

    The clause answers the question outright, but ``recommendation`` kept its
    initial ``evidence_needed`` because neither ranking branch covered an empty
    survivor set, so the reading asked for more evidence it did not need.
    """
    from fortune_reading import read_request, render_answer
    result = read_request(_travel_request([_slot('oct14', '2026-10-14')], _OCT))
    rec = result['recommendation']
    assert rec['status'] == 'excluded_by_clause'
    assert rec['first_choice'] is None
    assert rec['excluded'] == ['oct14']
    assert rec['precedence_version'] == PRECEDENCE_VERSION
    assert result['decision_blockers'] == []
    lead = render_answer(result).splitlines()[0]
    assert 'oct14' in lead and '天转' in lead


def test_a_window_crossing_midnight_is_judged_on_every_day_it_covers():
    """Departing 2026-10-13 20:00 and arriving 10-14 14:00 crosses into 辛酉.

    Day and season were read from ``dated[0]`` while the covered hours were
    gathered from every segment, so a window could be cleared on its first
    day's pillar and still sit on a prohibition day for most of its length.
    """
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'night', 'start': '2026-10-13T20:00', 'end': '2026-10-14T14:00'}], _OCT))
    ranking = result['ranking']
    assert [e['candidate_id'] for e in ranking['excluded']] == ['night']
    hit = ranking['excluded'][0]['excluded_by'][0]
    assert hit['kind'] == '天转'
    assert hit['passage_id'] == TIANDI_SOURCE
    assert '2026-10-14' in hit['reason'] or '辛酉' in hit['reason']
    assert ranking['tiers'] == []


def test_forbidden_hours_are_keyed_to_the_day_each_hour_falls_in():
    """Departing 2026-10-15 20:00 and landing 10-16 12:00 spans 壬戌 then 癸亥.

    壬 forbids 寅卯 and the window really does cover 寅 and 卯 — but they fall on
    the 癸亥 day, whose own rule is the unsettled one. Reading the whole window
    off ``dated[0]`` charged 壬's table to 癸's hours: the reported 忌时 belonged
    to neither day.
    """
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}], _OCT))
    entry = result['ranking']['tiers'][0]
    assert [d['day_ganzhi'] for d in entry['days']] == ['壬戌', '癸亥']
    assert [d['resolved'] for d in entry['days']] == [True, False]
    # Guard against the assertion below going vacuous if the calendar shifts:
    # the tempting-but-wrong hours must actually be inside this window.
    segments = result['participants'][0]['target']['segments']
    refs = [s['target_segment_ref'] for row in result['candidate_comparison']
            for w in row['windows'] for p in w['participants'] for s in p['segments']]
    covered = {(segments[i]['facts']['pillars']['day'],
                segments[i]['facts']['pillars']['hour'][1]) for i in refs}
    assert ('癸亥', '寅') in covered and ('癸亥', '卯') in covered
    # Neither day contributes a hit: 壬戌 covers only 戌亥子, and 癸亥's rule is
    # unsettled, so it is named as unsettled instead of borrowing one reading.
    assert entry['forbidden_hours_in_window'] == []
    assert entry['unresolved_hour_rules'] == ['癸亥']


def test_a_day_that_a_solar_term_splits_is_judged_the_same_from_any_start():
    """2034-02-04 is 辛卯 and 立春 turns at 05:41 local; 辛卯 is the spring 地转.

    Keying the day loop on the day pillar alone and taking the first segment's
    month meant a 03:00 start read the day as winter (clear) while a 06:00 start
    read it as spring (excluded) — the same day, opposite verdicts, decided by
    where the window happened to begin.
    """
    from fortune_reading import read_request
    period = {'start': '2034-02-03', 'end': '2034-02-06'}
    verdicts = {}
    for start, end in (('03:00', '09:00'), ('06:00', '09:00'), ('07:00', '12:00')):
        result = read_request(_travel_request(
            [_slot('c', '2034-02-04', start, end)], period))
        verdicts[start] = result['recommendation']['status']
    assert set(verdicts.values()) == {'excluded_by_clause'}, verdicts


def test_a_candidate_with_one_excluded_window_is_not_recommended():
    """A busy block can leave one window clear and push the other onto a 忌日.

    Counting it as a survivor produced 「就定 trip」 for a candidate whose own
    comparison row already read ``excluded_by_clause``.
    """
    from fortune_reading import read_request
    request = _travel_request(
        [{'id': 'trip', 'start': '2026-10-13T09:00', 'end': '2026-10-14T20:00'}], _OCT)
    request['busy'] = [{'start': '2026-10-13T13:00', 'end': '2026-10-14T09:00'}]
    result = read_request(request)
    ranking = result['ranking']
    assert [t['candidate_id'] for t in ranking['tiers']] == ['trip']
    assert [e['candidate_id'] for e in ranking['excluded']] == ['trip']
    rec = result['recommendation']
    assert rec['status'] == 'excluded_by_clause'
    assert rec['first_choice'] is None
    judgment = next(c['judgment'] for c in result['candidate_comparison']
                    if c['candidate_id'] == 'trip')
    assert judgment == 'excluded_by_clause'


def test_an_unresolved_day_publishes_both_readings_with_their_passages():
    """27-direct-answer.md keeps 「另说：《X》作 Y」 as a line that may not be cut.

    The summary announced that two books disagree while the two readings and
    their passage ids appeared nowhere in the rendered answer.
    """
    from fortune_reading import read_request, render_answer
    text = render_answer(read_request(_travel_request(
        [{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}], _OCT)))
    assert '两书相反' not in text.split('\n\n')[0]
    assert '癸亥日忌时两说并列' in text
    assert '《渊海子平》作子丑（yuanhai:c048:p0003）' in text
    assert '《三命通会》作戌亥（sanming:c003:p0035）' in text


def test_the_summary_paragraph_keeps_layer_two_vocabulary_out():
    """The hook that enforces this lives outside the repo and fires after the
    fact; these are the same words, checked before shipping."""
    from fortune_reading import read_request, render_answer
    banned = ['两书相反', '起法分歧', '两说并列', 'passage_id', 'precedence_version',
              'transcription_status', 'facsimile_status', '算不了', '排不出来']
    windows = [
        [_slot('a', '2026-10-15')],
        [_slot('a', '2026-10-13'), _slot('b', '2026-10-15')],
        [_slot('a', '2026-10-14')],
        [{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}],
        [{'id': 'dawn', 'start': '2026-10-15T03:00', 'end': '2026-10-15T08:00'}],
    ]
    for candidates in windows:
        summary = render_answer(read_request(_travel_request(candidates, _OCT))).split('\n\n')[0]
        assert not [w for w in banned if w in summary], (candidates[0]['id'], summary)


def test_forbidden_hours_read_in_time_order_not_code_point_order():
    """壬戌 forbids 寅 and 卯; 卯 sorts before 寅 by code point."""
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'dawn', 'start': '2026-10-15T03:00', 'end': '2026-10-15T08:00'}], _OCT))
    hits = result['ranking']['tiers'][0]['forbidden_hours_in_window']
    assert [h['hour_branch'] for h in hits] == ['寅', '卯']


def test_one_candidate_split_by_a_busy_block_does_not_tie_with_itself():
    """A busy hour splits a candidate into two windows, not two candidates.

    ``ties`` counted window rows, so a lone candidate interrupted by a meeting
    came back as 「没有条款能分出高下」 with itself listed twice.
    """
    from fortune_reading import read_request
    request = _travel_request([_slot('oct15', '2026-10-15', '09:00', '18:00')], _OCT)
    request['busy'] = [{'start': '2026-10-15T12:00', 'end': '2026-10-15T13:00'}]
    result = read_request(request)
    assert len(result['ranking']['tiers']) == 2
    # ``ties`` is published in the JSON and no longer gates the recommendation,
    # so it needs its own assertion or it can drift unnoticed.
    assert result['ranking']['ties'] is False
    rec = result['recommendation']
    assert rec['status'] == 'ranked'
    assert rec['first_choice'] == 'oct15'


def test_result_states_what_it_does_not_cover():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    assert '跨时区班次' in result['not_covered']
    assert any('黄历' in result['scope'] for _ in (0,))
