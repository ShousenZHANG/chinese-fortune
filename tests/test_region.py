"""Where the user's rules come from: the matter's place, then where the user is.

Never the computer's clock zone — this project's own maintainer runs a machine
set to China Standard Time while living in Sydney, and a cloud session reports
UTC. Unknown stays unknown: region-bound entries are then simply not attached.
"""
import pytest
from region import region_of, resolve_destination, resolve_region


@pytest.mark.parametrize('zone,region', [
    ('Asia/Shanghai', '中国大陆'), ('Asia/Urumqi', '中国大陆'), ('Asia/Chongqing', '中国大陆'),
    ('Asia/Harbin', '中国大陆'), ('PRC', '中国大陆'),
    ('Asia/Hong_Kong', '港澳台'), ('Asia/Macau', '港澳台'), ('Asia/Taipei', '港澳台'),
    ('Australia/Sydney', '境外'), ('Asia/Singapore', '境外'), ('America/New_York', '境外'),
    ('UTC', '未知'), ('Etc/UTC', '未知'), ('Etc/GMT+8', '未知'), ('GMT', '未知'),
    (None, '未知'), ('', '未知'),
])
def test_zone_to_region(zone, region):
    assert region_of(zone) == region


def _payload(scenario='moving', event_tz=None, current='Australia/Sydney', **event):
    body = {'event': {'scenario': scenario, **({'timezone': event_tz} if event_tz else {}), **event}}
    if current:
        body['current_timezone'] = current
    return body


def test_where_the_user_is_decides_when_the_matter_has_no_place():
    got = resolve_region(_payload('relationship_conversation', event_tz='Asia/Shanghai'))
    assert got == {'region': '境外', 'basis': 'current_location', 'timezone': 'Australia/Sydney'}


def test_the_matters_place_wins_for_place_bound_matters():
    """In Sydney, renting a flat in 苏州: mainland rules apply to the flat."""
    got = resolve_region(_payload('moving', event_tz='Asia/Shanghai'))
    assert got == {'region': '中国大陆', 'basis': 'matter_location', 'timezone': 'Asia/Shanghai'}


def test_a_confirmed_profile_is_the_last_resort():
    body = _payload('moving', current=None)
    body['participants'] = [{'id': 'me', 'person': {'current_timezone': 'Asia/Hong_Kong'}}]
    assert resolve_region(body) == {'region': '港澳台', 'basis': 'profile', 'timezone': 'Asia/Hong_Kong'}


def test_nothing_known_is_unknown_not_mainland():
    assert resolve_region({'event': {'scenario': 'moving'}})['region'] == '未知'
    assert resolve_region(_payload('moving', current='UTC'))['region'] == '未知'


def test_the_destination_decides_abroad_for_travel():
    assert resolve_destination(_payload('travel', destination_timezone='Asia/Singapore')) == '境外'
    assert resolve_destination(_payload('travel', destination_timezone='Asia/Hong_Kong')) == '港澳台'
    assert resolve_destination(_payload('travel', destination_timezone='Asia/Shanghai')) == '中国大陆'
    assert resolve_destination(_payload('travel')) is None


def test_the_resolver_never_reads_the_host_clock_zone(monkeypatch):
    """A machine set to China time must not turn a request into a mainland one."""
    monkeypatch.setenv('TZ', 'Asia/Shanghai')
    assert resolve_region({'event': {'scenario': 'moving'}})['region'] == '未知'
