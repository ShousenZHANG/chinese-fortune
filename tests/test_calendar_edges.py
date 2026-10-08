"""Three edges a real period reading hit (5.9.1); every person here is fictional.

A month calendar that starts on a 节 day had a few hours of the old month as
its first entry and named it a best month. The library's solar-term table
names some of next year's terms in pinyin, and DA_XUE reached the boundary
list. A birth time given as a range dropped the luck cycle whenever the
起运 moment moved with the minute, even though every minute gave the same
cycles.
"""
from datetime import datetime, timedelta, timezone

from fortune_calendar import CALENDAR_ZONE, active_luck, term_boundaries
from fortune_reading import host_notes, read_request, render_answer

PERSON = {'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'female',
                    'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}


def _period(start: str, end: str, person: dict = PERSON, question: str = '这段时间运势怎么样') -> dict:
    return {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-10-07T07:00:00Z', 'question': question,
            'intent': 'period', 'period': {'start': start, 'end': end},
            'event': {'scenario': 'outlook', 'timezone': 'Asia/Shanghai', 'longitude': 121.47},
            'participants': [{'id': 'me', 'confirmed': True, 'person': person}]}


def test_every_solar_term_name_is_chinese():
    lo = datetime(2026, 11, 1, tzinfo=timezone.utc)
    names = set(term_boundaries(lo, lo + timedelta(days=140)).values())
    assert {'大雪', '冬至', '小寒', '大寒', '立春', '雨水', '惊蛰'} <= names
    assert not [n for n in names if n.isascii()]
    target = read_request(_period('2026-11-20', '2026-12-20'))['participants'][0]['target']
    assert '大雪' in {b['solar_term'] for b in target['boundaries']}


def test_a_few_hours_of_a_month_at_the_window_edge_are_not_ranked():
    """寒露 falls at 14:29 on 2026-10-08: the morning is still 丁酉月, a sliver, not a month to recommend."""
    result = read_request(_period('2026-10-08', '2027-01-05'))
    entries = result['personal_calendar']['entries']
    sliver = entries[0]
    assert sliver['ganzhi'] == '丁酉' and sliver['partial'] is True
    assert '00:00–14:29' in sliver['span'] and not any(e.get('partial') for e in entries[1:])
    lead = render_answer(result).split('\n\n')[0]
    assert '丁酉月' not in lead
    assert not any('丁酉月' in note for note in host_notes(result))


def test_a_birth_range_keeps_the_cycle_when_every_minute_gives_the_same_one():
    """19:30–20:30 at 121.47 in January is 戌 throughout (true solar time is a few minutes earlier)."""
    person = {**PERSON, 'time_certainty': 'approximate', 'birth_time_range': {'start': '19:30', 'end': '20:30'}}
    row = read_request(_period('2026-10-08', '2026-11-07', person))['participants'][0]
    natal = row['natal']
    assert natal['da_yun'] and natal['qi_yun']['status'] == 'birth_time_range'
    assert natal['birth_time_uncertainty']['luck_sequence_stable'] is True
    assert row['luck_reading'] and row['target']['luck_catalog'][0]['status'] == 'calculated'


def test_a_birth_range_across_a_term_gives_no_cycle():
    """小寒 2000-01-06 09:00: 08:00–10:00 straddles it, so the month pillar and every cycle differ."""
    person = {'birth': {**PERSON['birth'], 'day': 6, 'hour': 8, 'minute': 0}, 'time_certainty': 'approximate',
              'birth_time_range': {'start': '08:00', 'end': '10:00'}}
    row = read_request(_period('2026-10-08', '2026-11-07', person))['participants'][0]
    assert row['natal']['da_yun'] == [] and row['luck_reading'] == []
    assert row['natal']['birth_time_uncertainty']['luck_sequence_stable'] is False


def test_a_moment_between_the_earliest_and_the_latest_change_is_left_open():
    natal = {'hour_known': True, 'da_yun': [{'ganzhi': '丙子'}, {'ganzhi': '乙亥'}],
             'qi_yun': {'status': 'birth_time_range', 'source': 'test',
                        'start_calendar_datetime': '2003-03-01T00:00:00',
                        'start_calendar_datetime_latest': '2003-03-20T00:00:00'}}
    inside = datetime(2008, 6, 1, tzinfo=CALENDAR_ZONE)
    edge = datetime(2013, 3, 10, tzinfo=CALENDAR_ZONE)     # one origin is past its tenth year, the other not
    assert active_luck(natal, inside)['ganzhi'] == '丙子'
    assert active_luck(natal, edge) == {'status': 'birth_time_range', 'candidates': ['丙子', '乙亥']}
