"""Bind feasible event windows to personal facts without inventing a ranking."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import xiangzhu
from contracts import Blocker
from fortune_calendar import solar_wall, term_boundaries
from fortune_time import civil_boundaries
from qimen_cast import determine_ju, source_core
from qimen_dingju import seasonal_context
from utils import require_lunar


def event_basis(comparisons: list[dict], participants: list[dict], *, scenario: str,
                timezone: str, standard: str, longitude: float | None) -> dict | None:
    """Bind Yuanling's verified anchors to every actual event segment.

    Year-stem lookup is a research fact, not the complete vol. 8 condition,
    nor a full-Bazi ranking. Unresolved cells are never treated as negatives.
    """
    if scenario not in ('interview', 'exam') or not any(c['available'] for c in comparisons):
        return None
    result: dict = {'method': 'yuanling-core', 'status': 'partial', 'charts': [],
                    'source_passage_id': 'yuanling:c008:p0001',
                    'scope': '本人年干落宫核对；不是完整八字排名，科名转用于面试属于现代类比',
                    'remaining': ['三奇、吉门、吉星同临及奇墓、门克、刑迫的完整条件',
                                  '科名与本次事项的适用范围', '完整八字的喜忌与时段选择规则']}
    if standard == 'true-solar' and longitude is None:
        result['status'] = 'event_longitude_required'
        return result
    merged: list[tuple[datetime, datetime]] = []
    for lo, hi in sorted((datetime.fromisoformat(w['start']).astimezone(UTC),
                          datetime.fromisoformat(w['end']).astimezone(UTC))
                         for c in comparisons for w in c['windows']):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    total = sum((hi - lo for lo, hi in merged), timedelta())
    if total > timedelta(days=32):
        result['status'] = 'candidate_span_too_long'
        result['remaining'].insert(0, '候选细算区间合计超过32个实际日，请缩小可选窗口或分批')
        return result
    require_lunar()
    from lunar_python import Solar
    zone = ZoneInfo(timezone)
    chart_refs: dict[tuple, int] = {}
    term_cache: dict[datetime, str] = {}
    for candidate in comparisons:
        for interval in candidate['windows']:
            lo, hi = (datetime.fromisoformat(interval[k]).astimezone(UTC) for k in ('start', 'end'))
            # Bazi may merge a middle solar term or a midnight under sect=1.
            # Qimen needs its own cuts, not just the Bazi segment endpoints.
            cuts = {lo, hi, *term_boundaries(lo, hi)}
            if standard == 'clock':
                cuts.update(civil_boundaries(lo.astimezone(zone), hi.astimezone(zone)))
            else:
                cursor, previous = lo, None
                while cursor < hi:
                    wall = solar_wall(cursor.astimezone(zone), standard, longitude)
                    wall_key = (wall.date(), (wall.hour + 1) // 2)
                    if wall_key != previous:
                        cuts.add(cursor)
                        previous = wall_key
                    cursor = cursor.replace(second=0, microsecond=0) + timedelta(minutes=1)
            interval['event_segments'] = []
            ordered = sorted(cuts)
            for start, end in zip(ordered, ordered[1:], strict=False):
                wall = solar_wall(start.astimezone(zone), standard, longitude)
                lunar = Solar.fromYmdHms(wall.year, wall.month, wall.day,
                                        wall.hour, wall.minute, wall.second).getLunar()
                day, hour = lunar.getDayInGanZhi(), lunar.getTimeInGanZhi()
                if start not in term_cache:
                    term_cache[start] = seasonal_context(start)['name']
                term = term_cache[start]
                dun, yuan, number = determine_ju(term, day)
                key = (dun, number, day, hour, term)
                if key not in chart_refs:
                    core = source_core(dun, number, hour)
                    people = []
                    for person in participants:
                        stem = person['natal']['four_pillars'].get('year', {}).get('stem')
                        palace = next((p for p, v in core['earth'].items() if v == stem), None)
                        people.append({'participant_id': person['id'], 'birth_year_stem': stem,
                            'earth_palace': palace,
                            'status': 'located' if palace else 'year_stem_mapping_required',
                            'known_star': core['zhi_fu']['star'] if palace == core['zhi_fu']['palace'] else None,
                            'known_door': core['zhi_shi']['door'] if palace is not None and palace == core['zhi_shi']['palace'] else None,
                            'verdict': 'not_evaluated'})
                    chart_refs[key] = len(result['charts'])
                    result['charts'].append({'day': day, 'hour': hour, 'solar_term': term,
                        'ju_type': dun, 'ju_number': number, 'yuan': yuan,
                        'core': core, 'participants': people})
                interval['event_segments'].append({'start': start.astimezone(zone).isoformat(),
                    'end': end.astimezone(zone).isoformat(), 'chart_ref': chart_refs[key]})
    return result


def compare_candidates(availability: list[dict], participants: list[dict], *,
                       duration_minutes: int, timezone: str) -> list[dict]:
    """Keep the whole event, including any changes during it, in the comparison.

    Start ranges are inclusive at both ends; event/fact intervals are half-open.
    References always point into the named participant's own target catalogs.
    """
    zone = ZoneInfo(timezone)
    result = []
    for candidate in availability:
        windows = []
        for interval in candidate['intervals']:
            start, end = (datetime.fromisoformat(interval[key]).astimezone(UTC) for key in ('start', 'end'))
            latest = end - timedelta(minutes=duration_minutes)
            if latest < start:
                raise ValueError('候选窗口不能容纳完整事件')
            people = []
            for person in participants:
                segments: list[dict] = []
                for index, segment in enumerate(person['target']['segments']):
                    lo = max(start, datetime.fromisoformat(segment['start']).astimezone(UTC))
                    hi = min(end, datetime.fromisoformat(segment['end']).astimezone(UTC))
                    if lo < hi:
                        segments.append({'target_segment_ref': index,
                                         'start': lo.astimezone(zone).isoformat(),
                                         'end': hi.astimezone(zone).isoformat()})
                # Missing coverage is a calculation defect, never a neutral omen.
                cursor = start
                for segment in segments:
                    if datetime.fromisoformat(segment['start']).astimezone(UTC) != cursor:
                        raise ValueError('候选时间的个人事实存在缺段')
                    cursor = datetime.fromisoformat(segment['end']).astimezone(UTC)
                if cursor != end:
                    raise ValueError('候选时间的个人事实没有覆盖完整事件')
                people.append({'participant_id': person['id'], 'segments': segments})
            windows.append({'start': interval['start'], 'end': interval['end'],
                            'allowed_start': {'earliest': interval['start'],
                                              'latest': latest.astimezone(zone).isoformat(),
                                              'latest_inclusive': True},
                            'participants': people})
        result.append({'candidate_id': candidate['id'], 'available': candidate['available'],
                       'reason': candidate['reason'], 'duration_minutes': duration_minutes,
                       'windows': windows, 'judgment': 'not_ranked'})
    return result


def decision_blockers(result: dict) -> list[Blocker]:
    """Keep independent missing conditions visible instead of overwriting them."""
    blockers: list[Blocker] = []
    method = result.get('event_method') or {}
    if result['priority'] is None:
        blockers.append({'code': 'participant_priority_required', 'message': '需要确认这次主要为谁安排。'})
    if result['capability']['route'] == 'selection':
        if not result['availability']:
            blockers.append({'code': 'availability_required', 'message': '还需要可参加的时间窗口和事件持续多久。'})
        elif not any(c['available'] for c in result['availability']):
            blockers.append({'code': 'no_feasible_slot', 'message': '目前没有时间能排下完整事件，需调整档期。'})
    for person in result['participants']:
        target = person['target']
        if target.get('missing_input'):
            blockers.append({'code': 'event_longitude_required', 'participant_id': person['id'],
                             'message': target['missing_input']})
        if not person['natal'].get('hour_known'):
            blockers.append({'code': 'birth_time_required', 'participant_id': person['id'],
                             'message': '出生时段尚未确定；完整时柱与起运仍需核清。'})
        if (result['capability'].get('personal_ranking') == 'rule_based'
                and not xiangzhu.birth_years_of(person['natal'])):
            blockers.append({'code': 'birth_year_required', 'participant_id': person['id'],
                             'message': '出生年柱还没定（多是生在立春前后又缺时刻），个人吉凶（相主）按出生年看，暂时排不了。'})
    if method.get('status') == 'event_longitude_required' and not any(b['code'] == 'event_longitude_required' for b in blockers):
        blockers.append({'code': 'event_longitude_required', 'message': '事件真太阳时仍缺地点经度，尚未起奇门盘。'})
    if method.get('status') == 'candidate_span_too_long':
        blockers.append({'code': 'candidate_span_too_long', 'message': method['remaining'][0]})
    # A scenario whose ranking is rule_based already produced cited tiers;
    # reporting the rules as missing there would contradict fortune_rules.
    if result['capability'].get('personal_ranking') != 'rule_based':
        blockers.append({'code': 'ranking_rules_required' if result['capability']['route'] == 'selection'
                        else 'interpretation_review_required', 'message': result['research']['missing']})
    if result.get('ranking', {}).get('unrankable'):
        blockers.append({'code': 'day_granularity_required',
                         'message': '部分候选窗口未细算到日柱，忌日条款无法套用。'})
    ranking = result.get('ranking', {})
    if any(r.get('forbidden_hours_in_window') or r.get('contested_hours_in_window') for r in ranking.get('tiers', [])):
        blockers.append({'code': 'clause_conflict',
                         'message': '部分窗口涉及忌时或版本分歧；未被忌日排除不能作为整体推荐。'})
    return blockers
