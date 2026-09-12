"""Personal identity, actual-time boundaries, source scope and truthful output."""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import chart_facts
from fortune_calendar import (
    active_luck,
    period_facts,
    pillar_facts,
    relation,
    target_facts,
    term_boundaries,
)
from fortune_reading import read_request, render_answer
from fortune_rules import capabilities, evidence, luck_observations, source_audit
from fortune_time import candidate_windows, civil_boundaries, local_instant, resolve_window
from personal_profiles import (
    data_root,
    delete_profile,
    load_profile,
    profile_path,
    save_profile,
    validate_person,
)
from request_time import capture_request_time

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def person():
    # Synthetic example, never a user's actual profile.
    return {'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30,
                      'gender': 'male', 'timezone': 'Asia/Shanghai', 'longitude': 120},
            'time_certainty': 'exact'}


@pytest.fixture
def query(person):
    return {'current_timezone': 'Australia/Sydney', 'request_time': '2026-09-12T00:00:00Z',
            'period': '下周', 'event': {'scenario': 'interview', 'time_standard': 'clock'},
            'participants': [{'id': 'example', 'person': person, 'confirmed': True}],
            'duration_minutes': 60,
            'candidates': [{'id': 'morning', 'start': '2026-09-15T09:00', 'end': '2026-09-15T12:00'},
                           {'id': 'afternoon', 'start': '2026-09-15T14:00', 'end': '2026-09-15T15:00'}]}


@pytest.fixture(scope='module')
def natal():
    chart = calculate_bazi(build_parser(diagnostics=False).parse_args([
        '--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30',
        '--gender', 'male', '--timezone', 'Asia/Shanghai', '--longitude', '120', '--as-of-year', '2026']))
    return chart_facts(chart)


def test_one_request_one_clock_one_known_birth_calculation(query, monkeypatch):
    import fortune_reading
    calls = []
    clocks = []
    real = fortune_reading.calculate_bazi

    def calculate(args):
        calls.append(args)
        return real(args)

    def clock():
        clocks.append(1)
        return datetime(2026, 9, 12, tzinfo=UTC)

    monkeypatch.setattr(fortune_reading, 'calculate_bazi', calculate)
    query.pop('request_time')
    result = read_request(query, clock=clock)
    assert len(calls) == len(clocks) == 1
    assert calls[0].request_time == result['request_time']['utc']
    assert result['participants'][0]['natal']['current_time_context']['utc'] == result['request_time']['utc']


def test_next_week_seven_days_and_current_place_are_distinct():
    now = capture_request_time('Australia/Sydney', '2026-09-13T15:00:00Z')  # Monday in Sydney
    week = resolve_window('下周', now, 'America/Los_Angeles')
    seven = resolve_window('未来七天', now, 'America/Los_Angeles')
    assert week['start'] == '2026-09-21T00:00:00-07:00'
    assert seven['start'] == '2026-09-14T00:00:00-07:00'
    la_now = capture_request_time('America/Los_Angeles', now['utc'])  # still Sunday
    assert resolve_window('下周', la_now, 'America/Los_Angeles')['start'] == '2026-09-14T00:00:00-07:00'


@pytest.mark.parametrize(('period', 'start', 'end'), [
    ('这两天', '2026-12-31', '2027-01-02'), ('下个月', '2027-01-01', '2027-02-01'),
    ('明年', '2027-01-01', '2028-01-01'), ('月底前', '2026-12-31', '2027-01-01')])
def test_relative_rollovers(period, start, end):
    now = capture_request_time('Asia/Shanghai', '2026-12-31T00:00:00Z')
    value = resolve_window(period, now, 'Asia/Shanghai')
    assert value['start'].startswith(start) and value['end'].startswith(end)


def test_dst_gap_fold_offset_and_duration():
    with pytest.raises(ValueError):
        local_instant('2026-10-04T02:30', 'Australia/Sydney')
    with pytest.raises(ValueError):
        local_instant('2026-04-05T02:30', 'Australia/Sydney')
    a = local_instant('2026-04-05T02:30', 'Australia/Sydney', 0)
    b = local_instant('2026-04-05T02:30', 'Australia/Sydney', 1)
    assert b.astimezone(UTC) - a.astimezone(UTC) == timedelta(hours=1)
    assert local_instant('2026-04-05T02:30+10:00', 'Australia/Sydney') == b
    with pytest.raises(ValueError, match='offset'):
        local_instant('2026-04-05T02:30+08:00', 'Australia/Sydney')
    now = capture_request_time('Australia/Sydney', '2026-04-01T00:00:00Z')
    window = resolve_window({'start': '2026-04-05', 'end': '2026-04-06'}, now, 'Australia/Sydney')
    available = candidate_windows([{'start': '2026-04-05T02:30+11:00', 'end': '2026-04-05T02:45+10:00'}], window, duration_minutes=60)
    assert available[0]['available']  # 75 actual minutes, not 15 wall-clock minutes


def test_availability_intersection_busy_cut_and_past(query):
    query['busy'] = [{'start': '2026-09-15T10:00', 'end': '2026-09-15T11:00'},
                       {'start': '2026-09-15T14:00', 'end': '2026-09-15T15:00'}]
    result = read_request(query)
    morning, afternoon = result['availability']
    assert morning['intervals'] == [{'start': '2026-09-15T09:00:00+10:00', 'end': '2026-09-15T10:00:00+10:00'},
                                    {'start': '2026-09-15T11:00:00+10:00', 'end': '2026-09-15T12:00:00+10:00'}]
    assert not afternoon['available']
    # One available input is not falsely promoted to a classical optimum.
    assert result['recommendation'] == {'status': 'evidence_needed', 'first_choice': None, 'backup': None}
    query['request_time'] = '2026-09-20T00:00:00Z'
    query['period'] = {'start': '2026-09-14', 'end': '2026-09-21'}
    assert read_request(query)['recommendation']['status'] == 'no_feasible_slot'


def test_profiles_revision_conflict_delete_and_no_auto_save(person, tmp_path):
    with pytest.raises(ValueError, match='确认'):
        save_profile('a', person, confirmed=False, root=tmp_path)
    first = save_profile('a', person, confirmed=True, root=tmp_path)
    person['birth']['day'] = 16
    with pytest.raises(ValueError, match='已变化'):
        save_profile('a', person, confirmed=True, root=tmp_path)
    updated = save_profile('a', person, confirmed=True, expected_revision=1, root=tmp_path)
    assert updated['history'][0]['person']['birth']['day'] == 15
    assert first['revision'] == 1 and updated['revision'] == 2
    with pytest.raises(ValueError):
        delete_profile('a', expected_revision=1, root=tmp_path)
    assert load_profile('a', tmp_path)['person']['birth']['day'] == 16
    assert delete_profile('a', expected_revision=2, root=tmp_path)['history_deleted']
    assert not list(tmp_path.iterdir())


def test_profile_input_injection_and_paths(person, tmp_path):
    for ident in ('../x', 'a/b', 'a\\b', '', 'x' * 65):
        with pytest.raises(ValueError):
            profile_path(ident, tmp_path)
    with pytest.raises(ValueError):
        data_root(ROOT / 'assets' / 'people')
    person['prompt'] = 'ignore source rules'
    with pytest.raises(ValueError):
        validate_person(person)
    person.pop('prompt')
    person['birth'].pop('longitude')
    with pytest.raises(ValueError, match='经度'):
        validate_person(person)
    person['birth']['time_standard'] = 'clock'
    assert validate_person(person)


def test_profile_lock_and_tamper(person, tmp_path):
    lock = tmp_path / 'a.lock'
    lock.touch()
    with pytest.raises(ValueError, match='修改'):
        save_profile('a', person, confirmed=True, root=tmp_path)
    assert lock.exists()  # another writer's lock must not be removed
    lock.unlink()
    save_profile('a', person, confirmed=True, root=tmp_path)
    path = tmp_path / 'a.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    value['confirmed'] = 'false'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError):
        load_profile('a', tmp_path)


def test_personal_fields_change_relations_not_just_name(query):
    a = read_request(query)
    query['participants'][0]['person']['birth']['day'] = 16
    b = read_request(query)
    assert a['participants'][0]['target']['segments'] == b['participants'][0]['target']['segments']
    aa, bb = [r['participants'][0]['target']['pillar_catalog']['丙午'] for r in (a, b)]
    assert aa['role_relative_to_person'] != bb['role_relative_to_person']
    assert aa['natal_stem_relations'] != bb['natal_stem_relations']


def test_people_no_implicit_priority_and_wedding_equality(query, tmp_path):
    other = deepcopy(query['participants'][0])
    other['id'] = 'other'
    other['person']['birth']['day'] = 16
    query['participants'].append(other)
    result = read_request(query, data_dir=tmp_path)
    assert result['recommendation']['status'] == 'participant_priority_required'
    assert [p['id'] for p in result['participants']] == ['example', 'other']
    assert not list(tmp_path.iterdir())
    query['event']['scenario'] = 'wedding'
    assert read_request(query)['priority'] == 'equal'


def test_unknown_and_approximate_birth_never_claim_active_luck(query):
    p = query['participants'][0]['person']
    p['time_certainty'] = 'approximate'
    result = read_request(query)
    natal = result['participants'][0]['natal']
    assert not natal['hour_known'] and natal['qi_yun'] is None
    assert natal['four_pillars']['hour'] == {'status': '时柱待补'}
    assert result['participants'][0]['target']['luck_catalog'] == [{'status': 'birth_time_required'}]


def test_luck_boundary_exact_not_calendar_year(natal):
    first = datetime.fromisoformat(natal['qi_yun']['start_calendar_datetime'])
    assert active_luck(natal, first - timedelta(seconds=1))['status'] == 'before_first_cycle'
    assert active_luck(natal, first)['ganzhi'] == natal['da_yun'][0]['ganzhi']
    second = datetime.fromisoformat(active_luck(natal, first)['end'])
    assert active_luck(natal, second - timedelta(seconds=1))['ganzhi'] == natal['da_yun'][0]['ganzhi']
    assert active_luck(natal, second)['ganzhi'] == natal['da_yun'][1]['ganzhi']


def test_lichun_reference_and_same_instant_across_cities(natal):
    # Independent reference: HKO Almanac 2026, February solar-terms panel:
    # https://www.hko.gov.hk/tc/gts/astron2026/files/HKO_almanac_2026.pdf
    # 4 February 04:02 HKT, rounded to minute. Never claim HKO second precision.
    a = datetime.fromisoformat('2026-02-04T03:50:00+08:00')
    b = datetime.fromisoformat('2026-02-04T04:10:00+08:00')
    terms = term_boundaries(a, b)
    assert len(terms) == 1
    instant = next(iter(terms))
    assert abs((instant - datetime.fromisoformat('2026-02-04T04:02:00+08:00')).total_seconds()) < 60
    before = target_facts(a, natal, granularity='hour', standard='clock', longitude=None, sect=2)
    after = target_facts(b, natal, granularity='hour', standard='clock', longitude=None, sect=2)
    assert (before['year']['ganzhi'], before['month']['ganzhi']) == ('乙巳', '己丑')
    assert (after['year']['ganzhi'], after['month']['ganzhi']) == ('丙午', '庚寅')
    overseas = target_facts(b.astimezone(ZoneInfo('America/New_York')), natal,
                           granularity='hour', standard='clock', longitude=None, sect=2)
    assert overseas['year'] == after['year'] and overseas['month'] == after['month']
    assert overseas['day'] != after['day']


@pytest.mark.parametrize('standard,longitude', [('clock', None), ('true-solar', 151.2)])
def test_segments_cover_entire_dst_day_with_stable_pillars(natal, standard, longitude):
    now = capture_request_time('Australia/Sydney', '2026-10-01T00:00:00Z')
    window = resolve_window({'start': '2026-10-04', 'end': '2026-10-05'}, now, 'Australia/Sydney')
    result = period_facts(window, natal, granularity='hour', standard=standard, longitude=longitude)
    segments = result['segments']
    assert segments[0]['start'] == window['start'] and segments[-1]['end'] == window['end']
    for left, right in zip(segments, segments[1:], strict=False):
        assert left['end'] == right['start']
    elapsed = 0
    for segment in segments:
        a, b = [datetime.fromisoformat(segment[k]).astimezone(UTC) for k in ('start', 'end')]
        elapsed += (b - a).total_seconds()
        # Check every interior minute, not only a representative midpoint.
        t = a
        while t < b:
            facts = target_facts(t.astimezone(ZoneInfo(window['timezone'])), natal,
                                 granularity='hour', standard=standard, longitude=longitude, sect=2)
            assert {k: v['ganzhi'] for k, v in facts.items()} == segment['facts']['pillars']
            t += timedelta(minutes=1)
    assert elapsed == 23 * 3600


def test_half_hour_dst_transition_cut():
    zone = ZoneInfo('Australia/Lord_Howe')
    start, end = datetime(2026, 10, 4, tzinfo=zone), datetime(2026, 10, 5, tzinfo=zone)
    cuts = civil_boundaries(start, end)
    assert datetime(2026, 10, 3, 15, 30, tzinfo=UTC) in cuts


def test_scope_audit_quotes_valid_but_not_interview_rules():
    audit = source_audit()
    assert {r['chapter'] for r in audit} == {'卷33', '卷34'}
    assert all(r['allowed_use'] == 'scope_audit_only' for r in audit)
    assert all(r['facsimile_status'] == 'not_checked' for r in audit)
    assert '修造以宅長一人之命為主' in audit[0]['text']
    assert '日支衝時支' in audit[1]['text']
    assert '五不遇' in audit[1]['text']
    assert all(c['personal_ranking'] == 'not_implemented' for c in capabilities())
    assert len(evidence(full_audit=True)['scope_audit'][0]['text']) > 0


def test_plain_answer_quote_then_plain_explanation(query):
    result = read_request(query)
    text = render_answer(result)
    first = text.splitlines()[0]
    assert '能排下' in first and '还不足' in first and '《' not in first
    quote = text.index('《子平真诠')
    explanation = text.index('白话说：')
    source = text.index('出处：')
    assert quote < explanation < source
    assert '本次已分别算出' in text[explanation:source]
    assert '首选：' not in text and '成功率' not in text


@pytest.mark.parametrize('change', [
    {'current_timezone': None}, {'participants': []}, {'invented_score': 100},
    {'granularity': 'minute'}, {'period': '随便哪天'}, {'duration_minutes': 0}])
def test_invalid_requests_fail_explicitly(query, change):
    query.update(change)
    with pytest.raises((ValueError, TypeError)):
        read_request(query)


def test_profile_reference_and_specialist_route(query, person, tmp_path):
    save_profile('example', person, confirmed=True, root=tmp_path)
    query['participants'] = [{'id': 'who', 'profile_id': 'example'}]
    result = read_request(query, data_dir=tmp_path)
    assert result['participants'][0]['id'] == 'who'
    assert result['participants'][0]['profile_revision'] == 1
    query['event']['scenario'] = 'naming'
    result = read_request(query)
    assert result['status'] == 'specialist_required' and '字义' in render_answer(result)


def test_cli_stdin_no_private_output_files(query, tmp_path):
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/fortune_reading.py'),
                           '--stdin', '--data-dir', str(tmp_path)], input=json.dumps(query),
                          encoding='utf-8', capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['status'] == 'partial'
    assert not list(tmp_path.iterdir())
    bad = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/fortune_reading.py'), '--stdin'],
                         input='{}', encoding='utf-8', capture_output=True)
    assert bad.returncode == 1 and json.loads(bad.stdout)['ok'] is False


def test_relation_definition_uses_each_person_stem():
    assert relation('甲', '丙') == '本人一方生出对方'
    assert relation('甲', '壬') == '对方生本人一方'
    assert relation('甲', '戊') == '本人一方克制对方'
    assert relation('甲', '庚') == '对方克制本人一方'
    assert relation('甲', '乙') == '同类'
    value = pillar_facts('甲子', {'day_master': {}, 'four_pillars': {'day': {'status': 'unknown'}}})
    assert value['role_relative_to_person'] is None and value['natal_stem_relations'] == []


def test_missing_event_longitude_keeps_month_facts(query):
    query['event'].pop('time_standard')
    query['granularity'] = 'hour'
    result = read_request(query)
    target = result['participants'][0]['target']
    assert target['granularity'] == 'month' and target['requested_granularity'] == 'hour'
    assert '经度' in target['missing_input']
    assert 'hour' not in target['segments'][0]['facts']['pillars']
    assert result['availability'][0]['available']
    assert '还缺' in render_answer(result)


@pytest.mark.parametrize('value,fold', [('2026-04-05T02:30+11:00', 1),
                                      ('2026-09-15T09', None), ('2026-09-15T09:00', True)])
def test_conflicting_or_incomplete_time_input(value, fold):
    with pytest.raises(ValueError):
        local_instant(value, 'Australia/Sydney', fold)


def test_granularity_limits_and_naive_instant(natal):
    window = {'start': '2026-09-01T00:00:00+10:00', 'end': '2026-10-03T00:00:00+10:00',
              'timezone': 'Australia/Sydney'}
    with pytest.raises(ValueError, match='31'):
        period_facts(window, natal, standard='clock')
    with pytest.raises(ValueError):
        period_facts(window, natal, granularity='month', sect=True)
    with pytest.raises(ValueError, match='时区'):
        target_facts(datetime(2026, 9, 15), natal, granularity='day', standard='clock', longitude=None, sect=2)


def test_source_quote_change_fails_instead_of_citing_old_text(query):
    result = read_request(query)
    result['evidence']['principle'][0]['text'] = 'changed text'
    with pytest.raises(ValueError, match='原文'):
        render_answer(result)


def test_optional_natal_interpretation_uses_same_chart(query, monkeypatch):
    import fortune_reading
    real = fortune_reading.calculate_bazi
    calls = []

    def calculate(args):
        calls.append(args)
        return real(args)

    monkeypatch.setattr(fortune_reading, 'calculate_bazi', calculate)
    query['include_natal_reading'] = True
    result = read_request(query)
    assert len(calls) == 1
    assert result['participants'][0]['natal_interpretation']['rule_assessment']['routes']


def test_profile_reserved_device_names_and_other_repository(tmp_path):
    with pytest.raises(ValueError, match='设备'):
        profile_path('CON', tmp_path)
    (tmp_path / '.git').mkdir()
    with pytest.raises(ValueError, match='Git'):
        data_root(tmp_path / 'profiles')


def test_real_natal_example_binds_luck_and_source_not_daily_success():
    # A synthetic but real calendar date satisfying the book's Ding/Hai/Ren example.
    query = {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-12T00:00:00Z',
             'period': {'start': '2032-09-13', 'end': '2032-09-20'},
             'event': {'scenario': 'outlook', 'time_standard': 'clock'},
             'participants': [{'id': 'example', 'confirmed': True,
                               'person': {'birth': {'year': 1982, 'month': 11, 'day': 10,
                                                    'hour': 12, 'gender': 'male', 'city': '北京'}}}]}
    result = read_request(query)
    p = result['participants'][0]
    obs = p['traditional_observations']
    assert len(obs) == 1 and obs[0]['source']['passage_id'] == 'ziping:c025:p0008'
    assert obs[0]['status'] == 'structural_example_matched' and '同类' in obs[0]['plain_observation']
    assert obs[0]['scope'] == 'active_ten_year_cycle_structure_only'
    assert result['recommendation']['first_choice'] is None
    assert '代表自己的字是丁' in render_answer(result) and '与你同属火这一类' in render_answer(result)
    p['natal']['four_pillars']['year']['stem'] = '甲'
    assert luck_observations(p['natal'], p['target']) == []
    query['period'] = {'start': '2042-09-13', 'end': '2042-09-20'}
    later = read_request(query)['participants'][0]['traditional_observations']
    assert len(later) == 1 and '不是在说获得职位' in later[0]['plain_observation']


def test_bing_example_distinguishes_luck_stem_from_branch_and_preserves_exceptions():
    natal = {'four_pillars': {'day': {'stem': '丙'}, 'month': {'branch': '子'}, 'year': {'branch': '亥'}}}
    target = {'luck_catalog': [{'status': 'calculated', 'ganzhi': '丙午'}],
              'segments': [{'start': '2030-01-01', 'end': '2030-01-08', 'facts': {'active_luck_ref': 0}}]}
    observations = luck_observations(natal, target)
    assert len(observations) == 2  # favorable stem relation must not hide branch conflict
    assert {o['source']['passage_id'] for o in observations} == {'ziping:c025:p0006'}
    target['luck_catalog'][0]['ganzhi'] = '己巳'
    assert len(luck_observations(natal, target)) == 1
    target['luck_catalog'][0]['ganzhi'] = '戊辰'
    assert luck_observations(natal, target) == []
    assert {p['passage_id'] for p in evidence()['context_and_exceptions']} == {
        f'ziping:c025:p{i:04}' for i in range(4, 15)}
