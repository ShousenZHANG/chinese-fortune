"""Target-period calendar facts; no natal verdict is projected onto a future day."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fortune_time import civil_boundaries
from lunar_python import Solar
from utils import (
    HIDDEN_STEMS,
    TIANGAN_WUXING,
    WUXING_GEN,
    WUXING_KE,
    longitude_correction,
    shi_shen,
)

CALENDAR_ZONE = timezone(timedelta(hours=8))


def _solar(moment: datetime) -> Solar:
    return Solar.fromYmdHms(moment.year, moment.month, moment.day,
                            moment.hour, moment.minute, moment.second)


def solar_wall(moment: datetime, standard: str, longitude: float | None) -> datetime:
    if standard == 'clock':
        return moment.replace(tzinfo=None)
    if longitude is None:
        raise ValueError('事件真太阳时需要事件地点经度；不能借用出生地经度')
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError('目标瞬间必须带时区')
    days, h, m = longitude_correction(moment.hour, moment.minute, longitude,
                                     offset.total_seconds() / 3600,
                                     moment.year, moment.month, moment.day)
    return (moment.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
            + timedelta(days=days, hours=h, minutes=m))


def term_boundaries(start: datetime, end: datetime) -> dict[datetime, str]:
    """Exact table instants, converted from the library's fixed UTC+8 coordinate."""
    terms = {}
    for year in range(start.year - 1, end.year + 2):
        for name, solar in Solar.fromYmd(year, 6, 1).getLunar().getJieQiTable().items():
            moment = datetime.fromisoformat(solar.toYmdHms()).replace(tzinfo=CALENDAR_ZONE).astimezone(UTC)
            if start.astimezone(UTC) < moment < end.astimezone(UTC):
                terms[moment] = name
    return terms


def relation(person_stem: str, target_stem: str) -> str:
    mine, other = TIANGAN_WUXING[person_stem], TIANGAN_WUXING[target_stem]
    if mine == other:
        return '同类'
    if WUXING_GEN[mine] == other:
        return '本人一方生出对方'
    if WUXING_GEN[other] == mine:
        return '对方生本人一方'
    if WUXING_KE[mine] == other:
        return '本人一方克制对方'
    return '对方克制本人一方'


def pillar_facts(ganzhi: str, natal: dict) -> dict:
    day = natal.get('day_master', {}).get('stem')
    result: dict = {'ganzhi': ganzhi, 'stem': ganzhi[0], 'branch': ganzhi[1],
              'hidden_stems': HIDDEN_STEMS[ganzhi[1]],
              'role_relative_to_person': shi_shen(day, ganzhi[0]) if day else None}
    result['natal_stem_relations'] = [
        {'pillar': key, 'person_stem': value['stem'], 'target_stem': ganzhi[0],
         'relation': relation(value['stem'], ganzhi[0])}
        for key, value in natal['four_pillars'].items() if value.get('stem')]
    return result


def target_facts(moment: datetime, natal: dict, *, granularity: str,
                 standard: str, longitude: float | None, sect: int) -> dict:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('目标瞬间必须带时区')
    calendar = _solar(moment.astimezone(CALENDAR_ZONE)).getLunar().getEightChar()
    result = {'year': pillar_facts(calendar.getYear(), natal),
              'month': pillar_facts(calendar.getMonth(), natal)}
    if granularity in ('day', 'hour'):
        wall = _solar(solar_wall(moment, standard, longitude)).getLunar().getEightChar()
        wall.setSect(sect)
        result['day'] = pillar_facts(wall.getDay(), natal)
        if granularity == 'hour':
            result['hour'] = pillar_facts(wall.getTime(), natal)
    return result


def active_luck(natal: dict, instant: datetime) -> dict:
    """Resolve an active ten-year cycle with an explicit anniversary convention."""
    qi = natal.get('qi_yun')
    if not qi or not natal.get('hour_known'):
        return {'status': 'birth_time_required'}
    origin = _solar(datetime.fromisoformat(qi['start_calendar_datetime']))
    for i, cycle in enumerate(natal['da_yun']):
        start = datetime.fromisoformat(origin.nextYear(i * 10).toYmdHms()).replace(tzinfo=CALENDAR_ZONE)
        end = datetime.fromisoformat(origin.nextYear((i + 1) * 10).toYmdHms()).replace(tzinfo=CALENDAR_ZONE)
        if start <= instant < end:
            return {'status': 'calculated', 'ganzhi': cycle['ganzhi'],
                    'start': start.isoformat(), 'end': end.isoformat(),
                    'convention': '起运瞬间起每十个公历周年；闰日按 lunar_python nextYear 调整',
                    'source': qi['source']}
    first = datetime.fromisoformat(qi['start_calendar_datetime'])
    return {'status': 'before_first_cycle' if instant < first else 'outside_calculated_cycles'}


def _focus_intervals(focus: list[dict] | None, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Merge actual intervals so overlapping candidates are calculated only once."""
    if focus is None:
        return [(start, end)]
    pieces = []
    for row in focus:
        lo, hi = datetime.fromisoformat(row['start']), datetime.fromisoformat(row['end'])
        if lo.tzinfo is None or hi.tzinfo is None:
            raise ValueError('候选事实区间必须带时区')
        lo, hi = lo.astimezone(UTC), hi.astimezone(UTC)
        if not start <= lo < hi <= end:
            raise ValueError('候选事实区间必须完整位于目标范围内')
        pieces.append((lo, hi))
    merged: list[tuple[datetime, datetime]] = []
    for lo, hi in sorted(pieces):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged


def period_facts(window: dict, natal: dict, *, granularity: str = 'day',
                 standard: str = 'true-solar', longitude: float | None = None,
                 sect: int = 2, focus: list[dict] | None = None) -> dict:
    import math
    if granularity not in ('month', 'day', 'hour') or standard not in ('clock', 'true-solar') or type(sect) is not int or sect not in (1, 2):
        raise ValueError('granularity/month/day/hour、time_standard 或 sect 无效')
    if longitude is not None and (type(longitude) not in (int, float) or not math.isfinite(longitude) or not -180 <= longitude <= 180):
        raise ValueError('事件经度须为 -180–180 的有限数值')
    if standard == 'true-solar' and granularity != 'month' and longitude is None:
        raise ValueError('日、时事实按真太阳时需要事件经度，或明确选择 clock 口径')
    zone = ZoneInfo(window['timezone'])
    start = datetime.fromisoformat(window['start']).astimezone(zone)
    end = datetime.fromisoformat(window['end']).astimezone(zone)
    a, b = start.astimezone(UTC), end.astimezone(UTC)
    if b <= a or b - a > timedelta(days=3660):
        raise ValueError('目标范围必须为正且不超过十年')
    ranges = _focus_intervals(focus, a, b)
    civil_length = sum((hi.astimezone(zone).replace(tzinfo=None) - lo.astimezone(zone).replace(tzinfo=None)
                        for lo, hi in ranges), timedelta())
    actual_length = sum((hi - lo for lo, hi in ranges), timedelta())
    if granularity != 'month' and (civil_length > timedelta(days=31) or actual_length > timedelta(days=32)):
        raise ValueError('日、时事实一次最多 31 个当地日；更长范围先用 month 或分批')
    terms = term_boundaries(start, end)
    cuts = {a, b, *terms}
    if granularity != 'month':
        for focus_start, focus_end in ranges:
            cuts.update((focus_start, focus_end))
            if standard == 'clock':
                cuts.update(civil_boundaries(focus_start.astimezone(zone), focus_end.astimezone(zone)))
                continue
            # The existing solar-clock engine rounds to whole minutes. Examine
            # each actual minute, covering both DST folds without guessed walls.
            cursor = focus_start
            previous = None
            while cursor < focus_end:
                wall = solar_wall(cursor.astimezone(zone), standard, longitude)
                key = (wall.date(), (wall.hour + 1) // 2, wall.hour == 23)
                if key != previous:
                    cuts.add(cursor)
                    previous = key
                cursor = cursor.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Luck changes can happen inside a day or solar month.
    qi = natal.get('qi_yun')
    if qi:
        origin = _solar(datetime.fromisoformat(qi['start_calendar_datetime']))
        for i in range(len(natal['da_yun']) + 1):
            boundary = datetime.fromisoformat(origin.nextYear(i * 10).toYmdHms()).replace(tzinfo=CALENDAR_ZONE).astimezone(UTC)
            if a < boundary < b:
                cuts.add(boundary)
    segments: list[dict] = []
    pillar_catalog: dict[str, dict] = {}
    luck_catalog: list[dict] = []
    ordered = sorted(cuts)
    for lo, hi in zip(ordered, ordered[1:], strict=False):
        detail_grain = granularity if any(x <= lo < y for x, y in ranges) else 'month'
        facts = target_facts(lo.astimezone(zone), natal, granularity=detail_grain,
                             standard=standard, longitude=longitude, sect=sect)
        luck = active_luck(natal, lo)
        for value in facts.values():
            pillar_catalog[value['ganzhi']] = value
        if luck not in luck_catalog:
            luck_catalog.append(luck)
        payload = {'pillars': {key: value['ganzhi'] for key, value in facts.items()},
                   'active_luck_ref': luck_catalog.index(luck)}
        if segments and segments[-1]['facts'] == payload:
            segments[-1]['end'] = hi.astimezone(zone).isoformat()
        else:
            segments.append({'start': lo.astimezone(zone).isoformat(),
                             'end': hi.astimezone(zone).isoformat(), 'facts': payload})
    return {'scope': 'calendar_and_personal_relations_only', 'granularity': granularity,
            'time_standard': standard, 'sect': sect, 'event_longitude': longitude,
            'calendar_zone': 'UTC+08:00', 'timezone': window['timezone'],
            'day_hour_precision': 'minute; existing rounded solar-clock algorithm',
            'focus_intervals': None if focus is None else [
                {'start': x.astimezone(zone).isoformat(), 'end': y.astimezone(zone).isoformat()} for x, y in ranges],
            'outside_focus_granularity': 'month' if focus is not None else None,
            'boundaries': [{'instant': t.astimezone(zone).isoformat(), 'solar_term': name}
                           for t, name in sorted(terms.items())],
            'segments': segments, 'pillar_catalog': pillar_catalog, 'luck_catalog': luck_catalog,
            'meaning': '这些是历法及与你出生盘的生克关系；尚未判喜忌，不是每日吉凶或择时排名'}
