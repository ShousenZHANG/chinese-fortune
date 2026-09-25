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


def _autumn(date: str, ganzhi: str, month_branch: str = '酉') -> dict:
    """An autumn day; 酉 month runs 白露 (09-07) to 寒露 (10-08) in 2026."""
    return {'date': date, 'day_stem': ganzhi[0], 'day_branch': ganzhi[1], 'month_branch': month_branch}


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
    Under the clause tiers only sourced prohibitions exclude and the rest tie:
    in 酉 month 往亡 falls on 子 days (09-11 戊子, 09-23 庚子) and 月破 on 卯
    days (09-14 辛卯, 09-26 癸卯), each unlifted by any 吉神 per 《协纪辨方书》 卷十.
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
    assert {e['date']: [h['label'] for h in e['excluded_by']] for e in result['excluded']} == {
        '2026-09-11': ['往亡'], '2026-09-14': ['月破'], '2026-09-23': ['往亡'], '2026-09-26': ['月破']}
    assert len(result['tiers']) == 16
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
        _autumn('2026-10-13', '庚申', '戌'),
        _autumn('2026-10-14', '辛酉', '戌'),
        _autumn('2026-10-26', '癸酉', '戌'),
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
        rank_travel_days([_autumn('2026-09-22', '己亥')], scenario='interview')


def test_ranking_declares_the_precedence_version_it_used():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    assert result['precedence_version'] == PRECEDENCE_VERSION
    assert result['ranking_reference'] == 'references/26-precedence.md'
    travel = next(c for c in capabilities('travel'))
    assert travel['personal_ranking'] == 'not_implemented'
    assert travel['calendar_screening'] == 'rule_based'
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
    assert rec['status'] == 'preferences_required'
    assert rec['first_choice'] is None
    assert sorted({w['candidate_id'] for w in result['practical_choice']['alternatives']}) == ['d21', 'd22']
    assert result['ranking']['precedence_version'] == PRECEDENCE_VERSION


def test_day_screening_does_not_hide_missing_personal_rules():
    from fortune_reading import read_request
    result = read_request(_travel_request(
        [{'id': 'd22', 'start': '2026-09-22T08:00', 'end': '2026-09-22T12:00'}],
        {'start': '2026-09-21', 'end': '2026-09-24'}))
    codes = [b['code'] for b in result['decision_blockers']]
    assert 'ranking_rules_required' in codes


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
        'practical_choice': [_slot('oct15', '2026-10-15')],
        'preferences_required': [_slot('oct13', '2026-10-13'),
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
        cases['preferences_required'], _OCT))).splitlines()[0]
    assert '现有古法' in tied
    assert '个人优劣' in tied
    assert '就定' not in tied


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
    assert {b['code'] for b in result['decision_blockers']} == {'ranking_rules_required'}
    text = render_answer(result)
    assert '需要避开' in text.splitlines()[0]
    assert 'oct14' in text and '辛酉' in text


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
    # The window does reach 壬子 and 癸丑, which one reading names. Under 晚子时
    # the 壬子 hour is 壬戌's night but 癸's 遁, so it is judged as 癸's.
    contested = entry['contested_hours_in_window']
    assert [(h['day_ganzhi'], h['hour_branch'], h['rule_stem']) for h in contested] == [
        ('壬戌', '子', '癸'), ('癸亥', '子', '癸'), ('癸亥', '丑', '癸')]
    assert all(h['readings'] == ['yuanhai:c048:p0003'] for h in contested)


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
    assert verdicts['06:00'] == verdicts['07:00'] == 'excluded_by_clause'
    assert verdicts['03:00'] == 'practical_choice'  # Fits before the actual seasonal boundary.


def test_flexible_candidate_uses_only_a_complete_clear_subwindow():
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
    assert rec['status'] == 'practical_choice'
    assert result['practical_choice']['first_choice']['start'] == '2026-10-13T09:00:00+11:00'
    assert result['practical_choice']['first_choice']['end'] == '2026-10-13T11:00:00+11:00'
    assert result['excluded_segments']
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
    from answer_style import style_violations
    from fortune_reading import read_request, render_answer
    windows = [
        [_slot('a', '2026-10-15')],
        [_slot('a', '2026-10-13'), _slot('b', '2026-10-15')],
        [_slot('a', '2026-10-14')],
        [{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}],
        [{'id': 'dawn', 'start': '2026-10-15T03:00', 'end': '2026-10-15T08:00'}],
    ]
    for candidates in windows:
        text = render_answer(read_request(_travel_request(candidates, _OCT)))
        assert not style_violations(text), (candidates[0]['id'], text.split('\n\n')[0])


def test_the_style_lists_match_the_reference():
    """answer_style carries 27-direct-answer.md's lists verbatim, not a subset."""
    import re

    from answer_style import CLASS_A, CLASS_B, CLASS_B_NEEDS_REASON, style_violations
    md = (ROOT / 'references' / '27-direct-answer.md').read_text(encoding='utf-8')

    def block(title: str) -> set[str]:
        body = re.search(rf'### {title}.*?```\n(.*?)```', md, re.S)
        assert body, title
        words = set()
        for line in body.group(1).splitlines():
            words |= {w.strip() for w in line.split('←')[0].split('|') if w.strip()}
        return words

    assert block('甲类') == set(CLASS_A) | {'我看到的不是……是'}
    assert block('乙类') == set(CLASS_B) | set(CLASS_B_NEEDS_REASON)
    assert style_violations('结论。\n\n两书相反') == []
    assert style_violations('两书相反。\n\n层二') == ['两书相反']
    assert style_violations('算不了因为缺时辰。') == []
    assert style_violations('算不了。') == ['算不了']
    assert style_violations('首句。\n\n我看到的不是运气，是选择') == ['我看到的不是运气，是']


def test_no_class_a_phrase_anywhere_in_a_rendered_answer():
    """27-direct-answer.md 甲类: deleting these loses no information, anywhere."""
    from answer_style import style_violations
    from fortune_reading import render_answer
    results = [_sep21_early(), _read([_slot('oct14', '2026-10-14')], _OCT, '可以吗？'),
               _read([_slot('oct13', '2026-10-13'), _slot('oct14', '2026-10-14')], _OCT,
                     preferences={'prefer': 'earliest'}),
               _read([{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}], _OCT)]
    for result in results:
        text = render_answer(result)
        assert not style_violations(text), text.split('\n\n')[0]


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
    assert rec['status'] == 'preferences_required'
    assert rec['first_choice'] is None
    assert result['practical_choice']['status'] == 'preferences_required'


def test_result_states_what_it_does_not_cover():
    result = rank_travel_days([_autumn('2026-09-22', '己亥')])
    assert '跨时区班次' in result['not_covered']
    assert any('黄历' in result['scope'] for _ in (0,))


# --- v4.6 audit: 戊癸 windows, the first sentence, and no invented minutes ---

_SEP = {'start': '2026-09-21', 'end': '2026-09-24'}


def _read(candidates: list[dict], period: dict, question: str = '', **extra) -> dict:
    from fortune_reading import read_request
    return read_request({**_travel_request(candidates, period), 'question': question, **extra})


def _render(result: dict) -> tuple[str, str]:
    """(summary paragraph, everything after it)."""
    from fortune_reading import render_answer
    lead, _, body = render_answer(result).partition('\n\n')
    return lead, body


def _sep21_early() -> dict:
    return _read([_slot('d21', '2026-09-21', '08:00', '12:00'), _slot('d22', '2026-09-22', '08:00', '12:00')],
                 _SEP, '哪天出发好？', preferences={'prefer': 'earliest'})


def test_an_unresolved_day_does_not_block_a_window_that_avoids_both_readings():
    """2026-09-21 is 戊戌; its 08:00-12:00 window covers 辰巳午 only.

    Both readings of 截路空亡 on a 戊 day name hours outside it (子丑 or 戌亥),
    yet the answer used to say the window 「涉及另一条忌时或版本分歧」 and
    refused to recommend it. That hit every 戊 and 癸 day, about a fifth of all.
    """
    result = _sep21_early()
    d21 = next(t for t in result['ranking']['tiers'] if t['candidate_id'] == 'd21')
    assert d21['unresolved_hour_rules'] == ['戊戌']  # still reported
    assert d21['contested_hours_in_window'] == []    # but nothing is contested
    assert result['recommendation']['status'] == 'practical_choice'
    assert result['recommendation']['first_choice'] == 'd21'
    assert 'clause_conflict' not in {b['code'] for b in result['decision_blockers']}
    lead, body = _render(result)
    assert lead.startswith('首选 d21：2026-09-21 08:00')
    assert '备选 d22' in lead and '不是古法排序' in lead
    assert '版本分歧' not in lead
    # Without a preference the answer asks for one; the blocker list must not
    # still carry a clause conflict that a practical choice would have hidden.
    open_question = _read([_slot('d21', '2026-09-21', '08:00', '12:00'),
                           _slot('d22', '2026-09-22', '08:00', '12:00')], _SEP)
    assert open_question['recommendation']['status'] == 'preferences_required'
    assert 'clause_conflict' not in {b['code'] for b in open_question['decision_blockers']}


def test_an_unresolved_day_is_only_mentioned_where_the_window_reaches_a_named_hour():
    lead, body = _render(_sep21_early())
    assert '戊戌' not in lead + body
    assert '两说并列' not in body
    assert '下面说明原可选大窗口里需要避开的部分' not in body


def test_a_window_inside_one_reading_is_still_blocked():
    """癸亥 00:45-03:40 sits in 子丑, which 《渊海子平》 names; 19:45-22:30 sits in
    戌亥, which 《三命通会》 names. Neither reading may be dropped."""
    for cid, start, end, book, pid in (('gui', '00:45', '03:40', '《渊海子平》', 'yuanhai:c048:p0003'),
                                       ('eve', '19:45', '22:30', '《三命通会》', 'sanming:c003:p0035')):
        result = _read([_slot(cid, '2026-10-16', start, end)], _OCT)
        assert result['recommendation']['status'] == 'clause_conflict', cid
        contested = result['ranking']['tiers'][0]['contested_hours_in_window']
        assert contested and all(h['readings'] == [pid] for h in contested), cid
        assert all(h['day_ganzhi'] == '癸亥' for h in contested), cid
        lead, body = _render(result)
        assert f'只有{book}算作忌时' in lead, cid
        assert '癸亥日忌时两说并列' in body, cid


def test_hour_hits_carry_the_clock_span_the_window_covers():
    result = _read([_slot('oct13', '2026-10-13')], _OCT)
    hit = result['ranking']['tiers'][0]['forbidden_hours_in_window'][0]
    assert (hit['day_ganzhi'], hit['hour_branch']) == ('庚申', '午')
    assert hit['segment_start'] == '2026-10-13T11:41:00+11:00'
    assert hit['segment_end'] == '2026-10-13T13:00:00+11:00'  # clipped to the window


def test_an_excluded_candidate_is_named_in_the_first_sentence():
    result = _read([_slot('oct13', '2026-10-13'), _slot('oct14', '2026-10-14'),
                    _slot('oct15', '2026-10-15')], _OCT, '哪天出发？', preferences={'prefer': 'earliest'})
    lead, _ = _render(result)
    assert lead.startswith('首选 oct13：')
    assert 'oct14 需要避开：覆盖到辛酉日，是秋季的天转日，《渊海子平》说这天忌出行。' in lead


def test_a_yes_no_question_gets_yes_or_no_first():
    from fortune_reading import _question_kind
    assert _question_kind('10月14日出发可以吗？') == 'yes_no'
    assert _question_kind('这样行不行') == 'yes_no'
    assert _question_kind('哪天出发好吗？') == 'choice'
    assert _question_kind('几点出发') == 'choice'
    assert _question_kind('这天怎么样') == 'verdict'
    assert _question_kind('10月14日是不是忌日') == 'yes_no'
    asked = '这天出发可以吗？'
    assert _render(_read([_slot('oct15', '2026-10-15')], _OCT, asked))[0].startswith('可以：oct15，')
    assert _render(_read([_slot('oct14', '2026-10-14')], _OCT, asked))[0].startswith('不行。oct14 需要避开')
    dawn = [{'id': 'dawn', 'start': '2026-10-15T03:00', 'end': '2026-10-15T08:00'}]
    assert _render(_read(dawn, _OCT, asked))[0].startswith('不建议。dawn 的 2026-10-15 03:00–08:00 放不下完整的 120 分钟')
    # The same requests without a yes/no question do not open with one.
    assert not _render(_read([_slot('oct14', '2026-10-14')], _OCT))[0].startswith('不行')


def test_a_conflict_names_the_window_and_the_clock_time():
    """「涉及另一条忌时」 told the reader nothing they could act on."""
    from fortune_reading import read_request
    request = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-24T01:00:00Z',
               'period': {'start': '2026-10-13', 'end': '2026-10-16'},
               'event': {'scenario': 'travel', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'},
               'participants': _travel_request([], _OCT)['participants'],
               'duration_minutes': 120, 'granularity': 'hour',
               'candidates': [{'id': 'oct13', 'start': '2026-10-13T12:00', 'end': '2026-10-13T14:00'}]}
    result = read_request(request)
    assert result['recommendation']['status'] == 'clause_conflict'
    lead, _ = _render(result)
    assert lead.startswith('oct13 的 2026-10-13 12:00–14:00 目前不能推荐')
    assert '12:00–13:00（午时）' in lead and '13:00–14:00（未时）' in lead
    assert '庚申日截路空亡' in lead


def test_the_body_gives_clock_times_for_every_named_hour():
    import re
    _, body = _render(_read([_slot('oct13', '2026-10-13'), _slot('oct15', '2026-10-15')], _OCT))
    line = next(x for x in body.split('\n\n') if x.startswith('oct13 的窗口覆盖到'))
    assert re.search(r'庚申日 2026-10-13 \d{2}:\d{2}–\d{2}:\d{2}（午时）', line), line
    assert 'yuanhai:c048:p0004' in line and '庚日遁 壬午、癸未' in line


def test_an_excluded_row_does_not_claim_its_date_broke_no_rule():
    """The hour line on an excluded window said 「单看日期未触犯一条规则」 —
    two paragraphs after saying the date broke one."""
    lead, body = _render(_read([_slot('oct14', '2026-10-14')], _OCT))
    assert '未触犯' not in lead + body
    assert 'oct14 原可选窗口覆盖到 辛酉 日' in body


def test_a_daily_outlook_says_plainly_that_no_clause_covers_it():
    from fortune_reading import read_request
    request = _travel_request([], _OCT)
    for key in ('candidates', 'duration_minutes', 'granularity'):
        request.pop(key)
    request.update(event={'scenario': 'outlook', 'timezone': 'Australia/Sydney', 'longitude': 151.2},
                   period={'start': '2026-09-18', 'end': '2026-09-19'}, question='明天运势怎么样？')
    result = read_request(request)
    assert result['recommendation']['status'] == 'evidence_needed'
    lead, body = _render(result)
    assert lead.startswith('按日给个人算整体吉凶，本库现有条款里没有这一类')
    assert '补查约5分钟' in body  # evidence_needed still offers the timed search
    # A natal question defaults to a one-day period too; it is not a daily outlook.
    natal = read_request({**request, 'intent': 'natal', 'question': '我的命局怎么样'})
    lead, _ = _render(natal)
    assert lead.startswith('这次按出生盘本身看') and '按日' not in lead


def test_no_minute_is_invented_when_the_person_gave_no_preference():
    """A lone window with no stated preference used to come back as a fixed
    09:00 start the person never chose."""
    clear = _read([_slot('oct15', '2026-10-15')], _OCT)
    choice = clear['practical_choice']['first_choice']
    window = clear['practical_comparison'][0]['windows'][0]
    assert choice['flexible_start'] == window['allowed_start']
    lead, _ = _render(clear)
    assert '2026-10-15 09:00–11:00 之间开始都行，持续 120 分钟（Australia/Sydney，UTC+11）' in lead
    # A stated preference does fix the minute.
    early = _read([_slot('oct15', '2026-10-15')], _OCT, preferences={'prefer': 'earliest'})
    assert 'flexible_start' not in early['practical_choice']['first_choice']


def test_a_window_with_a_named_hour_offers_only_its_clear_starts():
    """oct13 09:00-13:00 reaches 庚申's 午 at 11:41. Offering 「09:00-11:00
    之间开始都行」 would let an 11:00 start run into it; a 120-minute event
    stays clear only if it starts by 09:41."""
    result = _read([_slot('oct13', '2026-10-13')], _OCT)
    choice = result['practical_choice']['first_choice']
    assert choice['flexible_start'] == {'earliest': '2026-10-13T09:00:00+11:00',
                                        'latest': '2026-10-13T09:41:00+11:00', 'latest_inclusive': True}
    assert (choice['start'], choice['end']) == ('2026-10-13T09:00:00+11:00', '2026-10-13T11:00:00+11:00')
    lead, _ = _render(result)
    assert '2026-10-13 09:00–09:41 之间开始都行' in lead
    assert '别把时间挪进 11:41–13:00（午时），这个时辰是庚申日截路空亡的忌时' in lead


def test_a_settled_answer_does_not_end_by_offering_more_research():
    cases = [[_slot('oct15', '2026-10-15')], [_slot('oct14', '2026-10-14')],
             [{'id': 'dawn', 'start': '2026-10-15T03:00', 'end': '2026-10-15T08:00'}],
             [_slot('oct13', '2026-10-13'), _slot('oct15', '2026-10-15')]]
    for candidates in cases:
        result = _read(candidates, _OCT)
        assert result['recommendation']['status'] not in ('evidence_needed', 'screened_only')
        lead, body = _render(result)
        assert '补查约5分钟' not in body, candidates[0]['id']
        assert '收到钱或录用' not in body


def test_a_clear_wu_gui_window_keeps_its_flexible_start():
    """Gating ``flexible_start`` on the day being unsettled, instead of on the
    hours the window reaches, would re-create the 戊癸 bug in a quieter form."""
    result = _read([_slot('d21', '2026-09-21', '08:00', '12:00')], _SEP)
    assert result['ranking']['tiers'][0]['unresolved_hour_rules'] == ['戊戌']
    choice = result['practical_choice']['first_choice']
    assert choice['flexible_start']['earliest'] == '2026-09-21T08:00:00+10:00'
    assert choice['flexible_start']['latest'] == '2026-09-21T10:00:00+10:00'


def test_preferences_are_applied_as_stated_and_never_combined():
    two = [_slot('oct15', '2026-10-15'), _slot('oct16', '2026-10-16')]
    latest = _read(two, _OCT, preferences={'prefer': 'latest'})['practical_choice']
    assert latest['first_choice']['candidate_id'] == 'oct16'
    assert latest['first_choice']['start'] == '2026-10-16T11:00:00+11:00'  # the latest start
    assert latest['backup']['candidate_id'] == 'oct15'
    with pytest.raises(ValueError, match='只指定一种'):
        _read(two, _OCT, preferences={'prefer': 'earliest', 'candidate_order': ['oct15']})


def test_equal_starts_are_a_tie_not_an_input_order_pick():
    same = [_slot('a', '2026-10-15'), _slot('b', '2026-10-15')]
    result = _read(same, _OCT, preferences={'prefer': 'earliest'})
    assert result['practical_choice']['status'] == 'practical_tie'
    assert result['recommendation']['status'] == 'practical_tie'
    assert result['recommendation']['first_choice'] is None


def test_the_backup_is_another_candidate_not_the_same_one_later():
    """A busy hour splits oct15 into two windows; the backup must be oct16."""
    request = _travel_request([_slot('oct15', '2026-10-15', '09:00', '18:00'),
                               _slot('oct16', '2026-10-16', '09:00', '13:00')], _OCT)
    request.update(busy=[{'start': '2026-10-15T12:00', 'end': '2026-10-15T13:00'}],
                   preferences={'prefer': 'earliest'})
    from fortune_reading import read_request
    practical = read_request(request)['practical_choice']
    assert practical['first_choice']['candidate_id'] == 'oct15'
    assert practical['backup']['candidate_id'] == 'oct16'


def test_no_practical_choice_is_made_before_knowing_whom_it_is_for():
    from copy import deepcopy
    request = _travel_request([_slot('oct15', '2026-10-15')], _OCT)
    other = deepcopy(request['participants'][0])
    other['id'] = 'partner'
    request['participants'].append(other)
    from fortune_reading import read_request
    result = read_request(request)
    assert result['practical_choice']['status'] == 'participant_priority_required'
    assert result['practical_choice']['first_choice'] is None


def test_a_night_zi_hour_is_judged_by_the_day_whose_series_gave_its_stem():
    """截路空亡 is read 「以日取时」. Under 晚子时 the 23:00 hour keeps the civil
    day's pillar but takes the next day's stem: 戊戌日夜子 is 甲子 (己's series),
    丁酉日夜子 is 壬子 (戊's). Judging by the civil day flagged the first and
    missed the second."""
    from fortune_ranking import rule_stem
    assert rule_stem('戊', '甲子') == '己' and rule_stem('丁', '壬子') == '戊'
    assert rule_stem('戊', '壬子') == '戊' and rule_stem('庚', '壬午') == '庚'
    with pytest.raises(ValueError):
        rule_stem('甲', '壬子')
    period = {'start': '2026-09-19', 'end': '2026-09-24'}
    nights = {}
    for cid, day in (('wu', '2026-09-21'), ('ding', '2026-09-20')):
        result = _read([_slot(cid, day, '22:50', '23:40')], period, duration_minutes=30)
        nights[cid] = result
    wu = nights['wu']['ranking']['tiers'][0]
    assert wu['day_ganzhi'] == '戊戌' and wu['contested_hours_in_window'] == []
    assert nights['wu']['recommendation']['status'] == 'practical_choice'
    (ding,) = nights['ding']['ranking']['tiers'][0]['contested_hours_in_window']
    assert (ding['day_ganzhi'], ding['rule_stem'], ding['readings']) == ('丁酉', '戊', ['yuanhai:c048:p0003'])
    assert nights['ding']['recommendation']['status'] == 'clause_conflict'
    lead, body = _render(nights['ding'])
    assert '丁酉日夜子（时干按次日戊日起）' in lead
    assert '丁酉日夜子（时干按次日戊日起）忌时两说并列' in body


def test_clean_starts_leave_out_every_start_that_would_touch_a_block():
    from datetime import timedelta

    from fortune_decision import clean_starts
    window = {'allowed_start': {'earliest': '2026-10-13T09:00:00+11:00', 'latest': '2026-10-13T16:00:00+11:00'}}
    row = {'forbidden_hours_in_window': [
        {'segment_start': '2026-10-13T11:00:00+11:00', 'segment_end': '2026-10-13T12:00:00+11:00'}],
        'contested_hours_in_window': [
        {'segment_start': '2026-10-13T12:00:00+11:00', 'segment_end': '2026-10-13T13:00:00+11:00'}]}
    got = [(a.isoformat(), b.isoformat()) for a, b in clean_starts(window, timedelta(hours=1), row)]
    # Ending exactly at a block and starting exactly at its end are both clear.
    assert got == [('2026-10-12T22:00:00+00:00', '2026-10-12T23:00:00+00:00'),
                   ('2026-10-13T02:00:00+00:00', '2026-10-13T05:00:00+00:00')]
    # A three-hour event cannot end before 11:00 when it starts at 09:00 or later.
    assert [(a.isoformat(), b.isoformat()) for a, b in clean_starts(window, timedelta(hours=3), row)] == [
        ('2026-10-13T02:00:00+00:00', '2026-10-13T05:00:00+00:00')]
    assert len(clean_starts(window, timedelta(hours=1), None)) == 1


def test_earliest_moves_past_a_named_hour_instead_of_giving_up():
    """A window whose first slot runs into 庚申's 午未 used to end as a conflict
    even though a clear start existed later the same afternoon."""
    result = _read([_slot('oct13', '2026-10-13', '10:30', '18:30')], _OCT, preferences={'prefer': 'earliest'})
    blocks = result['practical_screening']['tiers'][0]['forbidden_hours_in_window']
    assert [h['hour_branch'] for h in blocks] == ['午', '未']
    choice = result['practical_choice']
    assert choice['status'] == 'practical_choice'
    assert choice['first_choice']['start'] == blocks[-1]['segment_end']  # right after 未 ends
    assert 'flexible_start' not in choice['first_choice']
    lead, _ = _render(result)
    assert lead.startswith('首选 oct13：2026-10-13 15:4')
    assert '别把时间挪进' in lead


def test_two_clear_ranges_in_one_window_are_offered_not_picked():
    """cross runs 20:00-12:00 over 壬子癸丑; the clear starts fall on either side."""
    result = _read([{'id': 'cross', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}], _OCT)
    assert result['recommendation']['status'] == 'preferences_required'
    ranges = [a['flexible_start'] for a in result['practical_choice']['alternatives']]
    assert [r['earliest'][:16] for r in ranges] == ['2026-10-15T20:00', '2026-10-16T03:40']
    lead, _ = _render(result)
    assert '可选：cross 2026-10-15 20:00–21:40 之间开始；cross 2026-10-16 03:40–10:00 之间开始。' in lead


def test_times_read_as_a_local_clock_with_one_offset():
    """ISO pairs like 「2026-09-21 08:00+10:00 至 2026-09-21 10:00+10:00」 were
    exact but hard to read; the date and offset now appear once. Across a
    daylight-saving change each end keeps its own offset."""
    from datetime import datetime

    from fortune_reading import _clock_range, _utc_offset
    assert _clock_range('2026-09-21T08:00:00+10:00', '2026-09-21T10:00:00+10:00', 'Australia/Sydney') == \
        '2026-09-21 08:00–10:00（Australia/Sydney，UTC+10）'
    assert _clock_range('2026-10-04T01:30:00+10:00', '2026-10-04T04:30:00+11:00', 'Australia/Sydney') == \
        '2026-10-04 01:30（UTC+10）至 04:30（UTC+11）（Australia/Sydney）'
    assert _clock_range('2026-10-15T20:00:00+11:00', '2026-10-16T02:00:00+11:00', 'Australia/Sydney') == \
        '2026-10-15 20:00–2026-10-16 02:00（Australia/Sydney，UTC+11）'
    assert _utc_offset(datetime.fromisoformat('2026-01-01T00:00:00+05:30')) == 'UTC+5:30'
    assert _utc_offset(datetime.fromisoformat('2026-01-01T00:00:00-03:00')) == 'UTC-3'
    assert _utc_offset(datetime.fromisoformat('2026-01-01T00:00:00-03:30')) == 'UTC-3:30'
    # Local mean time carries seconds; slicing the ISO string used to misread it.
    assert _utc_offset(datetime.fromisoformat('1900-01-01T00:00:00+08:05:43')) == 'UTC+8:05'
    lead = _render(_sep21_early())[0]
    assert lead.startswith('首选 d21：2026-09-21 08:00–10:00（Australia/Sydney，UTC+10）。')


def test_a_window_without_a_day_pillar_asks_for_the_place_not_a_verdict():
    """Without the event's longitude a true-solar request keeps only year and
    month pillars. The practical choice then reported ``clause_conflict``, the
    answer opened 「不建议」, and the renderer crashed on the row's missing end."""
    request = _travel_request([_slot('a', '2026-10-13')], _OCT)
    del request['event']['longitude']
    from fortune_reading import read_request, render_answer
    result = read_request({**request, 'question': '下周出行可以吗'})
    assert result['ranking']['unrankable'][0]['end'] == '2026-10-13T13:00:00+11:00'
    assert result['practical_choice']['status'] == 'screening_incomplete'
    assert result['conclusion']['status'] == 'screening_incomplete'
    lead = render_answer(result).split('\n\n')[0]
    assert lead == ('现在判断不了，因为还不知道活动地点：日柱按当地真太阳时定，缺经度就定不了，'
                    '所以 a 的 2026-10-13 09:00–13:00 还没有套用忌日条款。告诉我在哪个城市或经度，就能接着核。')
