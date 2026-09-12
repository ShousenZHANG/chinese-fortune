"""Cross-event constraints, shared birth inputs, truthful search completeness."""
from copy import deepcopy
from datetime import UTC, datetime

import fortune_reading
import pytest
from fortune_itinerary import feasible_plans
from fortune_reading import read_request, render_answer


@pytest.fixture
def query():
    return {'current_timezone': 'Australia/Sydney', 'request_time': '2026-09-12T00:00:00Z',
        'period': '下周', 'event': {'scenario': 'multiple_events', 'time_standard': 'clock'},
        'participants': [{'id': 'p', 'confirmed': True, 'person': {
            'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'gender': 'male',
                      'timezone': 'Asia/Shanghai', 'longitude': 120}, 'time_certainty': 'exact'}}],
        'events': [
            {'id': '面试', 'event': {'scenario': 'interview'}, 'duration_minutes': 60,
             'candidates': [{'start': '2026-09-15T09:00', 'end': '2026-09-15T11:00'}]},
            {'id': '出发', 'event': {'scenario': 'travel'}, 'duration_minutes': 30,
             'travel_minutes_from_previous': 45,
             'candidates': [{'start': '2026-09-15T10:30', 'end': '2026-09-15T12:00'}]}]}


def test_joint_plan_uses_elapsed_travel_and_one_birth_calculation(query, monkeypatch):
    calls = []
    original = fortune_reading.calculate_bazi

    def record(args):
        calls.append(args)
        return original(args)

    monkeypatch.setattr(fortune_reading, 'calculate_bazi', record)
    times = []

    def clock():
        times.append(True)
        return datetime(2026, 9, 12, tzinfo=UTC)

    query.pop('request_time')
    result = read_request(query, clock=clock)
    assert len(calls) == len(times) == 1
    plan = result['itinerary']['plans'][0]
    assert plan[0]['end'][11:16] == '10:00'
    assert plan[1]['start'][11:16] == '10:45'
    assert result['itinerary']['exhaustive']
    assert result['recommendation']['first_choice'] is None
    assert len(result['natal_catalog']) == 1
    assert all('natal' not in e['result']['participants'][0] for e in result['events'])
    assert '可行安排' in render_answer(result)


def test_individually_available_events_may_have_no_joint_plan(query):
    query['events'][1]['candidates'][0]['end'] = '2026-09-15T11:00'
    result = read_request(query)
    assert all(e['result']['availability'][0]['available'] for e in result['events'])
    assert result['itinerary']['status'] == 'no_feasible_itinerary'
    assert '无法' in render_answer(result)


def test_cross_zone_transfer_compares_instants_not_wall_clocks(query):
    query['events'][0]['candidates'] = [{'start': '2026-09-15T09:00', 'end': '2026-09-15T10:00'}]
    item = query['events'][1]
    item['event']['timezone'] = 'Asia/Shanghai'
    item['travel_minutes_from_previous'] = 60
    item['candidates'] = [{'start': '2026-09-15T09:00', 'end': '2026-09-15T10:00'}]
    result = read_request(query)
    plan = result['itinerary']['plans'][0]
    assert plan[1]['start'] == '2026-09-15T09:00:00+08:00'
    assert datetime.fromisoformat(plan[1]['start']) > datetime.fromisoformat(plan[0]['end'])


@pytest.mark.parametrize('bad', ['missing_travel', 'negative_travel', 'duplicate_event', 'nested', 'duplicate_person', 'bad_person', 'top_busy'])
def test_invalid_or_ambiguous_itineraries_are_not_silently_repaired(query, bad):
    if bad == 'missing_travel':
        query['events'][1].pop('travel_minutes_from_previous')
    elif bad == 'negative_travel':
        query['events'][1]['travel_minutes_from_previous'] = -1
    elif bad == 'duplicate_event':
        query['events'][1]['id'] = query['events'][0]['id']
    elif bad == 'nested':
        query['events'][1]['event']['scenario'] = 'multiple_events'
    elif bad == 'duplicate_person':
        query['participants'].append(deepcopy(query['participants'][0]))
    elif bad == 'bad_person':
        query['events'][1]['participant_ids'] = ['unknown']
    else:
        query['busy'] = []
    with pytest.raises(ValueError):
        read_request(query)


def test_return_limit_does_not_claim_all_combinations_were_returned():
    result = {'window': {'timezone': 'UTC'}, 'availability': [{'id': str(i),
        'intervals': [{'start': '2026-09-15T09:00:00+00:00', 'end': '2026-09-15T10:00:00+00:00'}]} for i in range(21)]}
    events = [{'id': 'e', 'result': result, 'duration_minutes': 30, 'travel_minutes_from_previous': 0}]
    got = feasible_plans(events)
    assert len(got['plans']) == 20
    assert got['exhaustive'] is False
    got = feasible_plans(events, node_limit=1)
    assert got['status'] == 'search_incomplete' and not got['plans']
