"""Which jurisdiction a real-world reference applies to, from the request alone.

Order: where the matter happens (for matters bound to a place), where the user
says they are, a profile the user confirmed. Never the host's clock zone: a
machine set to China time can belong to someone living in Sydney, and a cloud
session reports UTC. When nothing is known the answer is 未知, and callers
then attach no region-bound entry rather than assume 中国大陆.

港澳台 is its own region: mainland statutes do not apply there, and it is not
where the book's 境外 advice (overseas advisories, the 12308 consular line)
is aimed either.
"""
from __future__ import annotations

import zoneinfo
from functools import cache
from importlib import resources
from pathlib import Path

MAINLAND = frozenset({'Asia/Shanghai', 'Asia/Urumqi', 'Asia/Chongqing', 'Asia/Chungking',
                      'Asia/Harbin', 'Asia/Kashgar', 'PRC'})
HK_MO_TW = frozenset({'Asia/Hong_Kong', 'Hongkong', 'Asia/Macau', 'Asia/Macao', 'Asia/Taipei', 'ROC'})
NOT_A_PLACE = frozenset({'UTC', 'GMT', 'UCT', 'Universal', 'Zulu', 'Greenwich', 'GMT0', 'GMT+0', 'GMT-0'})
# Our own tables name link zones that zone.tab (canonical zones only) omits.
OWN_COUNTRIES = {**dict.fromkeys(MAINLAND, 'CN'), 'Asia/Hong_Kong': 'HK', 'Hongkong': 'HK',
                 'Asia/Macau': 'MO', 'Asia/Macao': 'MO', 'Asia/Taipei': 'TW', 'ROC': 'TW'}


@cache
def _known_zones() -> frozenset[str]:
    # Our own table names count even where a distribution ships legacy links
    # such as PRC separately (Debian's tzdata-legacy).
    return frozenset(zoneinfo.available_timezones()) | MAINLAND | HK_MO_TW | NOT_A_PLACE


def is_zone(zone: object) -> bool:
    """A real IANA name. Windows' ZoneInfo also opens 'Asia/Shanghai ' and
    'Asia\\Shanghai' as files, so opening one proves nothing."""
    return isinstance(zone, str) and zone in _known_zones()


@cache
def _zone_countries() -> dict[str, str]:
    """zone.tab from wherever zoneinfo reads its zones: TZPATH, then tzdata."""
    sources: list = [Path(p) / 'zone.tab' for p in zoneinfo.TZPATH]
    try:
        sources.append(resources.files('tzdata').joinpath('zoneinfo', 'zone.tab'))
    except ModuleNotFoundError:
        pass
    for source in sources:
        try:
            text = source.read_text(encoding='utf-8')
        except OSError:
            continue
        rows = (line.split('\t') for line in text.splitlines() if line and not line.startswith('#'))
        return {cols[2]: cols[0] for cols in rows if len(cols) >= 3}
    return {}


def country_of(zone: str | None) -> str | None:
    """ISO country code of a zone, or None when it names no country or is unknown."""
    if zone is None or not is_zone(zone):
        return None
    return OWN_COUNTRIES.get(zone) or _zone_countries().get(zone)


# Matters whose rules follow where they take place: the flat, the job, the
# shop, the contract, the marriage registry, the exam hall.
PLACE_BOUND = frozenset({'moving', 'work_conversation', 'interview', 'business', 'billing',
                         'wedding', 'exam'})


def region_of(zone: str | None) -> str:
    """中国大陆, 港澳台, 境外 or 未知 for one IANA zone name."""
    if not zone or not is_zone(zone):
        return '未知'
    if zone in MAINLAND:
        return '中国大陆'
    if zone in HK_MO_TW:
        return '港澳台'
    if zone in NOT_A_PLACE or zone.startswith('Etc/'):
        return '未知'
    return '境外'


def _profile_zone(payload: dict) -> str | None:
    for participant in payload.get('participants') or []:
        zone = ((participant or {}).get('person') or {}).get('current_timezone')
        if zone:
            return zone
    return None


def resolve_region(payload: dict) -> dict:
    """The region whose rules apply, with what decided it."""
    event = payload.get('event') or {}
    candidates = []
    if event.get('scenario') in PLACE_BOUND:
        candidates.append(('matter_location', event.get('timezone')))
    candidates += [('current_location', payload.get('current_timezone')),
                   ('profile', _profile_zone(payload))]
    for basis, zone in candidates:
        if zone and region_of(zone) != '未知':
            return {'region': region_of(zone), 'basis': basis, 'timezone': zone}
    return {'region': '未知', 'basis': 'unknown', 'timezone': None}


def resolve_destination(payload: dict) -> str | None:
    """Region of a trip's destination, or None when the request does not say."""
    zone = (payload.get('event') or {}).get('destination_timezone')
    return region_of(zone) if zone else None


def crosses_border(payload: dict) -> bool:
    """A trip from one country into another, both known.

    Sydney to Melbourne is 境外 at both ends and crosses nothing; an unknown
    origin cannot be said to cross anything either.
    """
    origin = country_of(resolve_region(payload)['timezone'])
    destination = country_of((payload.get('event') or {}).get('destination_timezone'))
    return bool(origin and destination and origin != destination)
