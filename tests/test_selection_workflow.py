"""Event duration, personal references and non-adjacent classical exceptions."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import classical_guidance as guidance
import fortune_calendar
import pytest
from classical_search import search_classics
from fortune_calendar import period_facts
from fortune_reading import read_request, render_answer
from fortune_selection import compare_candidates


@pytest.fixture
def query():
    return {'current_timezone': 'Australia/Sydney', 'request_time': '2026-09-12T00:00:00Z',
            'period': '下周', 'event': {'scenario': 'interview', 'time_standard': 'clock'},
            'participants': [{'id': 'applicant', 'confirmed': True, 'person': {
                'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30,
                          'gender': 'male', 'timezone': 'Asia/Shanghai', 'longitude': 120},
                'time_certainty': 'exact'}}],
            'duration_minutes': 60, 'candidates': [
                {'id': 'morning', 'start': '2026-09-15T09:00', 'end': '2026-09-15T12:00'}]}


def test_starts_allow_full_duration_and_keep_mid_event_calendar_change(query):
    query['duration_minutes'] = 180
    result = read_request(query)
    window = result['candidate_comparison'][0]['windows'][0]
    assert window['allowed_start']['earliest'] == window['allowed_start']['latest']
    assert window['allowed_start']['latest_inclusive']
    refs = window['participants'][0]
    assert refs['participant_id'] == 'applicant'
    segments = refs['segments']
    assert [(s['start'][11:16], s['end'][11:16]) for s in segments] == [('09:00', '11:00'), ('11:00', '12:00')]
    person = result['participants'][0]
    for s in segments:
        facts = person['target']['segments'][s['target_segment_ref']]['facts']
        assert 'hour' in facts['pillars']
        hour = person['target']['pillar_catalog'][facts['pillars']['hour']]
        assert {r['pillar'] for r in hour['natal_stem_relations']} == {'year', 'month', 'day', 'hour'}
    assert result['recommendation']['basis'] == 'practical_constraints'
    # The personal grade comes from 相主 (birth year), not from these pillar relations.
    assert result['conclusion']['traditional_personal_ranking'] == 'xiangzhu_birth_year'


def test_personal_qimen_basis_covers_whole_candidate_without_claiming_a_ranking(query):
    result = read_request(query)
    assert result['method']['supplementary_methods'] == ['yuanling-core']
    method = result['event_method']
    segments = result['candidate_comparison'][0]['windows'][0]['event_segments']
    assert [(s['start'][11:16], s['end'][11:16]) for s in segments] == [('09:00', '11:00'), ('11:00', '12:00')]
    stem = result['participants'][0]['natal']['four_pillars']['year']['stem']
    for segment in segments:
        chart = method['charts'][segment['chart_ref']]
        person = chart['participants'][0]
        assert person['birth_year_stem'] == stem
        assert chart['core']['earth'][person['earth_palace']] == stem
        assert person['verdict'] == 'not_evaluated'  # 奇门 still grades nothing
    assert result['recommendation']['basis'] == 'practical_constraints'
    assert result['conclusion']['traditional_personal_ranking'] == 'xiangzhu_birth_year'
    assert result['ranking']['personal_basis']['passage_id'] == 'xieji:c033:p0020'


def test_qimen_retains_middle_solar_term_even_when_bazi_month_does_not_change(query):
    query.update(current_timezone='Asia/Shanghai', request_time='2026-06-20T00:00:00Z',
                 period={'start': '2026-06-21', 'end': '2026-06-22'},
                 candidates=[{'start': '2026-06-21T16:00', 'end': '2026-06-21T17:00'}])
    result = read_request(query)
    segments = result['candidate_comparison'][0]['windows'][0]['event_segments']
    assert [s['start'][11:19] for s in segments] == ['16:00:00', '16:24:30']
    charts = result['event_method']['charts']
    assert [charts[s['chart_ref']]['ju_type'] for s in segments] == ['阳遁', '阴遁']


def test_qimen_missing_longitude_does_not_guess_event_clock(query):
    query['event']['time_standard'] = 'true-solar'
    result = read_request(query)
    assert result['event_method']['status'] == 'event_longitude_required'
    assert result['event_method']['charts'] == []


def test_month_grain_does_not_hide_missing_event_method_longitude(query):
    query['event']['time_standard'] = 'true-solar'
    query['granularity'] = 'month'
    result = read_request(query)
    assert any(b['code'] == 'event_longitude_required' for b in result['decision_blockers'])


def test_qimen_uses_each_person_year_and_does_not_invent_hidden_jia_mapping(query):
    second = deepcopy(query['participants'][0])
    second['id'] = 'second'
    second['person']['birth'].update(year=1994, month=5)
    query['participants'].append(second)
    query['event']['priority'] = 'equal'
    result = read_request(query)
    people = result['event_method']['charts'][0]['participants']
    assert people[0]['birth_year_stem'] != people[1]['birth_year_stem']
    assert people[1]['birth_year_stem'] == '甲'
    assert people[1]['earth_palace'] is None
    assert people[1]['status'] == 'year_stem_mapping_required'
    # 相主 weighs both people: 2026-09-15 壬辰 is in 协纪's 納音 table against 甲戌 (1994).
    assert result['recommendation']['status'] == 'excluded_by_clause'
    (hit,) = result['ranking']['excluded'][0]['excluded_by']
    assert (hit['participant_id'], hit['birth_year'], hit['label']) == ('second', '甲戌', '纳音克冲')
    assert result['conclusion']['traditional_personal_ranking'] == 'xiangzhu_birth_year'


def test_qimen_true_solar_basis_agrees_with_explicit_cli_clock_correction(query):
    import json
    import subprocess
    import sys
    from pathlib import Path

    query['event'].update(time_standard='true-solar', longitude=140)
    result = read_request(query)
    chart = result['event_method']['charts'][0]
    proc = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/qimen_cast.py'),
                           '--date', '2026-09-15', '--time', '09:00', '--longitude', '140',
                           '--target-timezone', 'Australia/Sydney'], capture_output=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    cli = json.loads(proc.stdout)
    assert chart['hour'] == cli['ganzhi']['hour']
    assert chart['core']['zhi_fu'] == cli['source_core']['zhi_fu']
    segments = result['candidate_comparison'][0]['windows'][0]['event_segments']
    assert len(segments) >= 2
    assert segments[0]['end'] == segments[1]['start']


def test_qimen_midnight_is_retained_even_with_bazi_sect_one(query):
    query['period'] = {'start': '2026-09-15', 'end': '2026-09-17'}
    query['event']['sect'] = 1
    query['candidates'] = [{'start': '2026-09-15T23:30', 'end': '2026-09-16T00:30'}]
    result = read_request(query)
    segments = result['candidate_comparison'][0]['windows'][0]['event_segments']
    assert [s['start'][11:16] for s in segments] == ['23:30', '00:00']
    charts = result['event_method']['charts']
    assert charts[segments[0]['chart_ref']]['day'] != charts[segments[1]['chart_ref']]['day']


def test_qimen_dst_segments_cover_actual_duration(query):
    query['period'] = {'start': '2026-10-04', 'end': '2026-10-05'}
    query['candidates'] = [{'start': '2026-10-04T01:30', 'end': '2026-10-04T03:30'}]
    result = read_request(query)
    segments = result['candidate_comparison'][0]['windows'][0]['event_segments']
    durations = [(datetime.fromisoformat(s['end']).astimezone(UTC)
                  - datetime.fromisoformat(s['start']).astimezone(UTC)).total_seconds() for s in segments]
    assert all(d > 0 for d in durations)
    assert sum(durations) == 3600


def test_only_feasible_hours_are_calculated_and_overlaps_are_deduplicated(query, monkeypatch):
    query['candidates'].append({'id': 'overlap', 'start': '2026-09-15T10:00', 'end': '2026-09-15T12:00'})
    calls = []
    original = fortune_calendar.target_facts

    def record(moment, natal, **kwargs):
        calls.append((moment, kwargs['granularity']))
        return original(moment, natal, **kwargs)

    monkeypatch.setattr(fortune_calendar, 'target_facts', record)
    result = read_request(query)
    hourly = [stamp for stamp, grain in calls if grain == 'hour']
    assert [(stamp.day, stamp.hour) for stamp in hourly] == [(15, 9), (15, 11)]
    target = result['participants'][0]['target']
    assert len(target['focus_intervals']) == 1
    assert target['outside_focus_granularity'] == 'month'
    assert all('day' not in s['facts']['pillars'] for s in target['segments']
               if s['start'] < '2026-09-15' or s['start'] >= '2026-09-16')


def test_year_window_can_compare_sparse_actual_appointments(query):
    query['period'] = {'start': '2026-01-01', 'end': '2027-01-01'}
    result = read_request(query)
    assert result['candidate_comparison'][0]['available']
    assert result['participants'][0]['target']['granularity'] == 'hour'


def test_latest_start_uses_elapsed_minutes_across_dst_jump(query):
    query['period'] = {'start': '2026-10-04', 'end': '2026-10-05'}
    query['candidates'] = [{'start': '2026-10-04T01:30', 'end': '2026-10-04T03:30'}]
    result = read_request(query)
    interval = result['candidate_comparison'][0]['windows'][0]
    assert interval['allowed_start']['latest'] == '2026-10-04T01:30:00+10:00'
    assert interval['end'] == '2026-10-04T03:30:00+11:00'
    assert '01:30' in render_answer(result)


def test_display_does_not_round_start_before_actual_availability(query):
    query['candidates'] = [{'start': '2026-09-15T09:00:59', 'end': '2026-09-15T10:00:59'}]
    result = read_request(query)
    assert '2026-09-15 09:00:59–10:00:59' in render_answer(result)  # seconds kept, not rounded
    assert result['practical_choice']['first_choice']['start'].endswith('09:00:59+10:00')


def test_blockers_do_not_hide_each_other(query):
    second = deepcopy(query['participants'][0])
    second['id'] = 'second'
    second['person']['birth'].pop('hour')
    second['person']['birth'].pop('minute')
    second['person']['time_certainty'] = 'unknown'
    query['participants'].append(second)
    query['event'].pop('time_standard')
    query['candidates'][0]['end'] = '2026-09-15T09:30'
    result = read_request(query)
    assert {b['code'] for b in result['decision_blockers']} == {
        'participant_priority_required', 'event_longitude_required', 'birth_time_required',
        'no_feasible_slot'}
    assert '主要考虑谁' in render_answer(result)


def test_same_request_is_stable_and_personal_catalogs_do_not_mix(query):
    second = deepcopy(query['participants'][0])
    second['id'] = 'second'
    second['person']['birth']['day'] = 16
    query['participants'].append(second)
    query['event']['priority'] = 'equal'
    first = read_request(query)
    assert first == read_request(query)
    refs = first['candidate_comparison'][0]['windows'][0]['participants']
    assert [p['participant_id'] for p in refs] == ['applicant', 'second']
    people = first['participants']
    assert people[0]['target']['pillar_catalog'] != people[1]['target']['pillar_catalog']


def test_candidate_calendar_gap_is_rejected(query):
    result = read_request(query)
    result['participants'][0]['target']['segments'] = []
    with pytest.raises(ValueError, match='完整事件'):
        compare_candidates(result['availability'], result['participants'], duration_minutes=60,
                           timezone='Australia/Sydney')
    with pytest.raises(ValueError, match='容纳'):
        compare_candidates(result['availability'], result['participants'], duration_minutes=200,
                           timezone='Australia/Sydney')


@pytest.mark.parametrize('start,end', [('2026-09-15T09:00', '2026-09-15T12:00'),
    ('2026-09-01T09:00+10:00', '2026-09-15T12:00+10:00')])
def test_invalid_focus_is_not_silently_clipped(query, start, end):
    result = read_request(query)
    with pytest.raises(ValueError, match='候选事实区间'):
        period_facts(result['window'], result['participants'][0]['natal'], standard='clock',
                     focus=[{'start': start, 'end': end}])


def _all_context(group):
    return {p['passage_id']: p['text'] for p in [
        *group['results'], *group.get('required_context', []),
        *(p for result in group['results'] for p in result['context'])]}


@pytest.mark.parametrize('scenario,pid,phrase', [
    ('billing', 'xuanze:c003:p0327', '又納財忌'),
    ('business', 'xuanze:c003:p0327', '開市忌'),
    ('travel', 'xuanze:c003:p0333', '又出行忌'),
    ('moving', 'xuanze:c003:p0349', '家主本命日'),
    ('moving', 'xuanze:c003:p0352', '前二條俱忌'),
    ('wedding', 'xuanze:c003:p0110', '女命'),
])
def test_nonadjacent_conditions_are_retrieved_and_verified(scenario, pid, phrase):
    result = guidance.research_sources(scenario, limit=1)
    group = next(g for g in result['groups'] if g['book'] == 'xuanze')
    assert phrase in _all_context(group)[pid]
    assert pid in group['context_review']['verified_passage_ids']
    assert group['context_review']['remaining_review']


def test_tampered_distant_exception_fails_audit(monkeypatch):
    data = guidance._catalog()
    data['context_sections']['billing']['passage_hashes']['xuanze:c003:p0327'] = 'bad'
    monkeypatch.setattr(guidance, '_catalog', lambda: data)
    with pytest.raises(ValueError, match='required context'):
        guidance.research_sources('billing')
    assert not guidance.audit_guidance()['ok']


def test_one_request_can_return_verified_sources_without_recasting(query, monkeypatch):
    import fortune_reading
    actual = fortune_reading.calculate_bazi
    calls = []

    def count(args):
        calls.append(args)
        return actual(args)

    monkeypatch.setattr(fortune_reading, 'calculate_bazi', count)
    query['include_research'] = True
    result = read_request(query)
    assert len(calls) == 1
    bundle = result['research']['source_bundle']
    assert bundle['retrieval_only']
    same_work = next(g for g in bundle['groups'] if g['book'] == 'yuanling')
    assert '本人年干' in same_work['results'][0]['text']
    assert 'source_bundle' not in read_request({**query, 'include_research': False})['research']
    assert datetime.fromisoformat(result['request_time']['utc']).astimezone(UTC).hour == 0


def test_source_flag_is_not_truthy_string(query):
    query['include_research'] = 'true'
    with pytest.raises(ValueError, match='布尔值'):
        read_request(query)


def test_rejected_candidate_has_specific_reason_and_no_unrelated_quotation(query):
    query['busy'] = [{'start': '2026-09-15T09:00', 'end': '2026-09-15T12:00'}]
    result = read_request(query)
    assert result['availability'][0]['reason'] == '扣除已占用的行程后，没有连续 60 分钟可用'
    text = render_answer(result)
    assert '扣除已占用的行程' in text and '《子平真诠' not in text
    assert '2026-09-14 至 2026-09-20' in text


@pytest.mark.parametrize('simplified,traditional,book', [('天盘', '天盤', 'yuanling'),
    ('动爻', '動爻', 'zengshan'), ('谒贵', '謁貴', 'dunjia')])
def test_actual_search_handles_method_terms_in_both_scripts(simplified, traditional, book):
    first = search_classics(simplified, book=book, limit=1)
    second = search_classics(traditional, book=book, limit=1)
    assert first and first == second
