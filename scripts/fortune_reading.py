"""One request -> personal facts, explicit target periods and honest evidence gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from answer_style import question_kind, rule_detail
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import chart_facts, prepare_reading
from birth_interval import calculate_interval
from classical_guidance import research_sources
from contracts import Recommendation
from fortune_calendar import period_facts
from fortune_decision import choose_practical, conclusion_packet, route_request
from fortune_ranking import (
    EVENT_WORDS,
    JIELU_METHOD_SOURCE,
    SCENARIO_TERMS,
    TIANDI_EVENTS,
    TIANDI_SOURCE,
    day_prohibitions,
    jielu_kongwang,
    personal_people,
    rank_candidates,
    split_eligible_windows,
)
from fortune_rules import capabilities, evidence, luck_observations, research_request
from fortune_selection import compare_candidates, decision_blockers, event_basis
from fortune_time import candidate_windows, resolve_window
from personal_profiles import birth_arguments, load_profile, validate_person
from request_time import capture_request_time
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope
from wuxing_colours import asks_colour, colour_lead, colour_lines
from xiangzhu import PASSAGE as XIANGZHU_PASSAGE
from xiangzhu import birth_years_of, personal_calendar
from xieji_days import RULES as XIEJI_RULES
from xieji_days import SCENARIO_TERMS as XIEJI_TERMS

FIELDS = {'current_timezone', 'request_time', 'period', 'event', 'events', 'participants',
          'candidates', 'duration_minutes', 'busy', 'granularity', 'include_natal_reading', 'include_research',
          'question', 'intent', 'preferences'}
EVENT_FIELDS = {'scenario', 'timezone', 'longitude', 'time_standard', 'sect', 'priority'}


def _people(values: list[dict], data_dir: Path | None) -> list[dict]:
    if not isinstance(values, list) or not 1 <= len(values) <= 4:
        raise ValueError('participants 需要 1–4 位明确的分析对象')
    result = []
    ids = set()
    for item in values:
        if not isinstance(item, dict) or set(item) - {'id', 'person', 'profile_id', 'confirmed'}:
            raise ValueError('参与者只接受 id/person/profile_id/confirmed')
        ident = item.get('id')
        if not isinstance(ident, str) or not ident or len(ident) > 64 or ident in ids:
            raise ValueError('参与者 id 必须明确、唯一且不超过 64 字符')
        ids.add(ident)
        if ('person' in item) == ('profile_id' in item):
            raise ValueError('每位参与者只能提供 person 或 profile_id 其中一个')
        if 'profile_id' in item:
            profile = load_profile(item['profile_id'], data_dir)
            person, revision = profile['person'], profile['revision']
        else:
            if item.get('confirmed') is not True:
                raise ValueError('请先确认当次出生资料；confirmed=true 不会自动保存档案')
            person, revision = item['person'], None
        person = validate_person(person, check_calendar=False)
        fingerprint = hashlib.sha256(json.dumps(person, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        result.append({'id': ident, 'person': person, 'profile_revision': revision,
                       'input_fingerprint': fingerprint})
    return result


def _bounded_event(payload: dict, event: dict, now: dict) -> dict:
    """An explicitly bounded event is its whole interval, not a flexible start.

    Date-only periods remain periods: do not invent a duration or appointment.
    """
    event_period = payload.get('period')
    if not (payload.get('intent') == 'event' and 'candidates' not in payload and isinstance(event_period, dict)
            and all(isinstance(event_period.get(k), str) and 'T' in event_period[k] for k in ('start', 'end'))):
        return payload
    exact_window = resolve_window(event_period, now, event.get('timezone') or now['timezone'])
    start, end = (datetime.fromisoformat(exact_window[k]).astimezone(UTC) for k in ('start', 'end'))
    minutes = (end - start).total_seconds() / 60
    if minutes != int(minutes):
        raise ValueError('整段事件请提供分钟分辨率的起止时间')
    if 'duration_minutes' in payload and payload['duration_minutes'] != minutes:
        raise ValueError('整段事件的持续时间与明确起止时间不一致；灵活安排请使用 candidates')
    return {**payload, 'duration_minutes': int(minutes),
            'candidates': [{'id': 'event', 'start': exact_window['start'], 'end': exact_window['end']}]}


def _with_period(payload: dict, capability: dict, now: dict) -> dict:
    """A natal or research question may omit the period; nothing else may."""
    if 'period' not in payload and capability.get('intent') in ('natal', 'research'):
        local_date = datetime.fromisoformat(now['local']).date()
        payload = {**payload, 'period': {'start': str(local_date), 'end': str(local_date + timedelta(days=1))}}
    if 'period' not in payload:
        raise ValueError('请提供 period，例如 下周 或明确 start/end；不能猜目标日期')
    return payload


def _priority(event: dict, people: list[dict], scenario: str) -> str | None:
    priority = event.get('priority')
    ids = {p['id'] for p in people}
    if priority is not None and priority != 'equal' and priority not in ids:
        raise ValueError('priority 须为 equal 或一位参与者 id')
    if priority is None:
        priority = 'equal' if scenario == 'wedding' else people[0]['id'] if len(people) == 1 else None
    return priority


def _skeleton(payload: dict, now: dict, window: dict, capability: dict, priority: str | None,
              scenario: str, grain: str, people: list[dict]) -> dict:
    """The result before any person is calculated, with the starting status."""
    result: dict = {'schema_version': '1.1', 'status': 'partial', 'request_time': now,
              'question': payload.get('question', ''),
              'window': window, 'capability': capability, 'priority': priority,
              'method': {'primary': 'bazi', 'ranking_rules': [],
                         'chosen_before_calculation': True, 'supplementary_methods': []},
              'participants': [], 'availability': [],
              'recommendation': {'status': 'evidence_needed', 'first_choice': None, 'backup': None},
              'research': research_request(scenario, grain),
              'output_order': ['plain_answer', 'dates_and_conditions', 'short_verified_quote',
                               'plain_meaning_and_personal_application']}
    if scenario in ('interview', 'exam'):
        result['method']['supplementary_methods'] = ['yuanling-core']
    if len(people) > 1 and priority is None:
        result['recommendation']['status'] = 'participant_priority_required'
    if capability['route'] == 'selection':
        if 'candidates' not in payload or 'duration_minutes' not in payload:
            result['recommendation']['status'] = 'availability_required'
        else:
            result['availability'] = candidate_windows(payload['candidates'], window,
                duration_minutes=payload['duration_minutes'], busy=payload.get('busy'), not_before=now['utc'])
            if not any(p['available'] for p in result['availability']):
                result['recommendation']['status'] = 'no_feasible_slot'
    elif any(key in payload for key in ('candidates', 'busy', 'duration_minutes')):
        raise ValueError('比较档期请使用 intent=selection 或带候选的 intent=event，不能把期间查询当择时')
    return result


def _participant(person: dict, payload: dict, event: dict, now: dict, window: dict, *,
                 grain: str, focus: list | None, include: bool, cache: dict) -> dict:
    """One person's natal facts and target-period facts."""
    standard = event.get('time_standard', 'true-solar')
    birth = dict(person['person']['birth'])
    approximate = person['person']['time_certainty'] == 'approximate'
    if approximate:
        # A guessed point is not an uncertainty interval. Reuse the existing
        # whole-date candidate check until a real interval is supplied.
        birth.pop('hour', None)
        birth.pop('minute', None)
    args = build_parser(diagnostics=False).parse_args(birth_arguments(birth) + [
        '--years', '120', '--current-timezone', now['timezone'], '--request-time', now['utc']])
    if person['input_fingerprint'] not in cache:
        interval = person['person'].get('birth_time_range')
        cache[person['input_fingerprint']] = calculate_interval(args, interval) if interval else calculate_bazi(args)
    chart = cache[person['input_fingerprint']]
    if not chart.get('ok'):
        raise ValueError(person['id'] + '：' + chart['message'])
    natal_reading = prepare_reading(chart, payload.get('question', '')) if include else None
    natal = natal_reading['chart_facts'] if natal_reading else chart_facts(chart)
    # Annual reference samples are not active target-year facts.
    natal = {k: v for k, v in natal.items() if k not in ('liu_nian', 'liu_nian_scope', 'liu_nian_note')}
    actual_grain = grain
    missing_event_longitude = standard == 'true-solar' and event.get('longitude') is None and grain in ('day', 'hour')
    if missing_event_longitude:
        actual_grain = 'month'
    target = period_facts(window, natal, granularity=actual_grain, standard=standard,
                          longitude=event.get('longitude'), sect=event.get('sect', 2), focus=focus)
    if missing_event_longitude:
        target['requested_granularity'] = grain
        target['missing_input'] = '事件地点经度；已保留不依赖经度的年、月事实，日时仍待补'
    row = {'id': person['id'], 'profile_revision': person['profile_revision'],
           'input_fingerprint': person['input_fingerprint'], 'natal': natal, 'target': target}
    row['traditional_observations'] = luck_observations(natal, target)
    if approximate:
        interval = person['person'].get('birth_time_range')
        row['time_note'] = (f"已比较出生当天 {interval['start']}–{interval['end']} 范围，只保留各可能时间一致的结论"
                            if interval else '出生时分仅约数；未给上下界，本次保守核对全天共同部分，不以约数确定时柱与大运')
    if natal_reading:
        row['natal_interpretation'] = {k: v for k, v in natal_reading.items() if k != 'chart_facts'}
    return row


def _screen_selection(result: dict, payload: dict, event: dict, scenario: str) -> None:
    """Compare the candidate windows and, where rules exist, screen them."""
    capability, window = result['capability'], result['window']
    duration = payload.get('duration_minutes', 60)
    screened = result['availability']
    people = personal_people(chosen_for(result))
    # Day rules exist for some scenarios; 相主 exists for anyone whose birth year is settled.
    screens = capability.get('calendar_screening') == 'rule_based' or bool(people)
    if screens:
        # Keep the original calendar-only availability; expose excluded parts separately.
        screened, result['excluded_segments'] = split_eligible_windows(
            screened, result['participants'][0], duration, scenario, people)
    result['candidate_comparison'] = compare_candidates(result['availability'], result['participants'],
        duration_minutes=duration, timezone=window['timezone'])
    result['event_method'] = event_basis(result['candidate_comparison'], result['participants'],
        scenario=scenario, timezone=window['timezone'], standard=event.get('time_standard', 'true-solar'),
        longitude=event.get('longitude'))
    # Every exclusion and tier cites a passage. See references/26-precedence.md.
    if screens:
        _rank_selection(result, screened, duration, scenario, people)


def chosen_for(result: dict) -> list[dict]:
    """The people a day is chosen for: the priority person, or everyone when equal."""
    subject = [p for p in result['participants'] if p['id'] == result['priority']]
    return subject or result['participants']


def _rank_selection(result: dict, screened: list[dict], duration: int, scenario: str,
                    people: list[tuple[str, str]]) -> None:
    subject = next((p for p in result['participants'] if p['id'] == result['priority']),
                   result['participants'][0])
    ranking = rank_candidates(result['candidate_comparison'], subject, scenario=scenario, people=people)
    ranking['calendar_participant_id'] = subject['id']
    result['ranking'] = ranking
    result['practical_comparison'] = compare_candidates(screened, result['participants'],
        duration_minutes=duration, timezone=result['window']['timezone'])
    for row in result['candidate_comparison']:
        verdicts = {e['candidate_id'] for e in ranking['excluded']}
        tiers = {t['candidate_id']: t['tier'] for t in ranking['tiers']}
        if row['candidate_id'] in verdicts:
            row['judgment'] = 'excluded_by_clause'
        elif row['candidate_id'] in tiers:
            row['judgment'] = f"tier_{tiers[row['candidate_id']]}"
    # Ties are the honest outcome when no clause separates the survivors.
    # A busy block splits one candidate into several windows, so count
    # candidates, not rows.
    # A candidate with one clear window and one excluded window is not a
    # survivor: recommending it would send the reader into the very
    # window a clause ruled out.
    # Only the best tier survives the ranking; lower tiers are backups.
    struck = {e['candidate_id'] for e in ranking['excluded']}
    best = min((t['tier'] for t in ranking['tiers'] if t['candidate_id'] not in struck), default=None)
    survivors = [c for c in dict.fromkeys(t['candidate_id'] for t in ranking['tiers'] if t['tier'] == best)
                 if c not in struck]
    version = ranking['precedence_version']
    if len(survivors) == 1:
        result['recommendation'] = {'status': 'screened_only', 'first_choice': None,
                                    'remaining': survivors,
                                    'backup': None, 'precedence_version': version}
    elif survivors:
        result['recommendation'] = {'status': 'tied_no_clause_separates',
                                    'first_choice': None, 'backup': None,
                                    'tied': survivors, 'precedence_version': version}
    elif ranking['excluded']:
        # The clause answered outright. Leaving the initial
        # evidence_needed here asked for evidence already in hand.
        result['recommendation'] = {
            'status': 'excluded_by_clause', 'first_choice': None, 'backup': None,
            'excluded': list(dict.fromkeys(e['candidate_id'] for e in ranking['excluded'])),
            'precedence_version': version}
    # Screen the exact subwindows, not their original broader input windows.
    result['practical_screening'] = rank_candidates(result['practical_comparison'], subject, scenario=scenario,
                                                    people=people)


DAY_QUESTION_WORDS = ('哪天', '哪几天', '哪一天', '几号', '吉日', '好日子', '日子')


def _personal_period(result: dict, grain: str) -> None:
    """Which days (or months) of the period are good or bad for the person: 相主."""
    people = personal_people(chosen_for(result))
    if not people:
        result['personal_calendar'] = {'status': 'birth_year_unknown', 'entries': [], 'people': []}
        return
    window = result['window']
    # A question about days gets days even over a long window (up to a year);
    # otherwise a window longer than a month is answered month by month.
    days_asked = any(word in (result.get('question') or '') for word in DAY_QUESTION_WORDS)
    long_ok = (datetime.fromisoformat(window['end']) - datetime.fromisoformat(window['start'])).days <= 366
    unit = 'day' if grain in ('day', 'hour') or (days_asked and long_ok) else 'month'
    calendar = personal_calendar(people, window['start'], window['end'], window['timezone'], unit)
    # 「下个月哪天搬家好」: the event's own day rules bar days before 相主 grades them.
    scenario = result['capability']['scenario']
    if calendar['unit'] == 'day' and scenario in SCENARIO_TERMS:
        calendar['event'] = EVENT_WORDS[scenario]
        for entry in calendar['entries']:
            hits = day_prohibitions(scenario, entry['pillars']['day'], entry['pillars']['month'][1])
            if hits:
                entry['event_hits'] = hits
    result['personal_calendar'] = calendar
    if result['recommendation']['status'] == 'evidence_needed':
        result['recommendation'] = {'status': 'personal_calendar', 'first_choice': None, 'backup': None}


def _settle_practical(result: dict, preferences: dict | None) -> None:
    """The practical choice decides the recommendation where it can."""
    practical = choose_practical(result, preferences)
    result['practical_choice'] = practical
    status, first, backup = practical['status'], practical['first_choice'], practical['backup']
    recommendation: Recommendation | None = None
    if result['priority'] is None:
        recommendation = {'status': 'participant_priority_required', 'first_choice': None, 'backup': None}
    elif status == 'practical_choice' and first is not None:
        recommendation = {'status': 'practical_choice', 'first_choice': first['candidate_id'],
                          'backup': backup['candidate_id'] if backup else None,
                          'basis': 'practical_constraints'}
        result['decision_blockers'] = [b for b in result['decision_blockers'] if b['code'] != 'clause_conflict']
    elif status in ('clause_conflict', 'screening_incomplete', 'preferences_required', 'practical_tie'):
        recommendation = {'status': status, 'first_choice': None, 'backup': None}
    if recommendation is not None:
        result['recommendation'] = recommendation


def read_request(payload: dict, *, data_dir: Path | None = None,
                 clock: Callable[[], datetime] | None = None, _shared: dict | None = None) -> dict:
    """Validate, calculate each person, screen any candidates, then settle."""
    if not isinstance(payload, dict) or set(payload) - FIELDS:
        raise ValueError('请求包含未知字段；见 references/24-personalized-forecast.md')
    # One clock sample before calculations, reused in every natal chart.
    now = (_shared['request_time'] if _shared is not None else
           capture_request_time(payload.get('current_timezone'), payload.get('request_time'), clock=clock))
    event = payload.get('event', {'scenario': 'outlook'})
    if not isinstance(event, dict) or set(event) - EVENT_FIELDS:
        raise ValueError('event 字段无效')
    scenario = event.get('scenario', 'outlook')
    if scenario == 'multiple_events':
        from fortune_itinerary import read_itinerary
        return read_itinerary(payload, now, data_dir=data_dir)
    if 'events' in payload:
        raise ValueError('events仅用于 multiple_events 连续行程')
    payload = _bounded_event(payload, event, now)
    capability = route_request(payload, capabilities(scenario)[0])
    if capability['route'] == 'specialist':
        return ok_envelope('fortune_reading', {'schema_version': '1.0', 'status': 'specialist_required',
                            'request_time': now, 'capability': capability,
                            'message': capability['missing']})
    payload = _with_period(payload, capability, now)
    window = resolve_window(payload['period'], now, event.get('timezone') or now['timezone'])
    people = _people(payload.get('participants', []), data_dir)
    priority = _priority(event, people, scenario)
    length = (datetime.fromisoformat(window['end']) - datetime.fromisoformat(window['start'])).days
    grain = payload.get('granularity', 'hour' if capability['route'] == 'selection' else
                        'month' if length > 31 else 'day')
    result = _skeleton(payload, now, window, capability, priority, scenario, grain, people)
    include = payload.get('include_natal_reading', capability['route'] == 'period')
    include_research = payload.get('include_research', False)
    if type(include) is not bool or type(include_research) is not bool:
        raise ValueError('include_natal_reading / include_research 必须为布尔值')
    focus = ([interval for c in result['availability'] for interval in c['intervals']]
             if capability['route'] == 'selection' else None)
    cache = _shared['natal_charts'] if _shared is not None else {}
    for person in people:
        result['participants'].append(_participant(person, payload, event, now, window, grain=grain,
                                                   focus=focus, include=include, cache=cache))
    result['evidence'] = evidence()
    if capability['route'] == 'selection':
        _screen_selection(result, payload, event, scenario)
    elif capability['route'] == 'period' and capability.get('intent') not in ('natal', 'research'):
        _personal_period(result, grain)
    if include_research:
        result['research']['source_bundle'] = research_sources(scenario, limit=1)
    result['decision_blockers'] = decision_blockers(result)
    if capability['route'] == 'selection':
        _settle_practical(result, payload.get('preferences'))
    result['conclusion'] = conclusion_packet(result)
    return ok_envelope('fortune_reading', result)


def _display_time(value: str) -> str:
    stamp = datetime.fromisoformat(value)
    precision = 'auto' if stamp.second or stamp.microsecond else 'minutes'
    return stamp.isoformat(sep=' ', timespec=precision)


def _window_description(window: dict) -> str:
    start, end = (datetime.fromisoformat(window[k]) for k in ('start', 'end'))
    if not any((stamp.hour, stamp.minute, stamp.second, stamp.microsecond) != (0, 0, 0, 0)
               for stamp in (start, end)):
        return f"日期：{start.date()} 至 {(end - timedelta(days=1)).date()}，按 {window['timezone']} 当地时间。"
    return f"范围：{_display_time(window['start'])} 至 {_display_time(window['end'])}（不含结束时刻），按 {window['timezone']} 当地时间。"


def _candidate_description(candidate: dict, interval: dict) -> str:
    earliest, latest = (datetime.fromisoformat(interval['allowed_start'][key]) for key in ('earliest', 'latest'))
    end = datetime.fromisoformat(interval['end'])

    def clock(stamp: datetime) -> str:
        return stamp.time().isoformat(timespec='auto' if stamp.second or stamp.microsecond else 'minutes')

    def later(stamp: datetime) -> str:
        prefix = str(stamp.date()) + ' ' if stamp.date() != earliest.date() else ''
        offset = f"（UTC{stamp.isoformat()[-6:]}）" if stamp.utcoffset() != earliest.utcoffset() else ''
        return prefix + clock(stamp) + offset

    first = f"{earliest.date()} {clock(earliest)}"
    if end.utcoffset() != earliest.utcoffset():
        first += f"（UTC{earliest.isoformat()[-6:]}）"
    if earliest == latest:
        return f"- {candidate['candidate_id']}：{first} 开始，{later(end)} 结束，实际 {candidate['duration_minutes']} 分钟。"
    return f"- {candidate['candidate_id']}：{first} 至 {later(latest)} 之间开始，持续 {candidate['duration_minutes']} 分钟；最迟 {later(end)} 结束。"


# States that wait on the person. Only these keep fixed wording; every other
# lead is assembled from the candidates, dates and clauses actually in hand.
ASK_LEADS = {
    'availability_required': '请一次告诉我可用日期、每天能参加的时段，以及事情需要多久，我就能继续比较具体安排。',
    'participant_priority_required': '这次安排主要考虑谁，还是同等考虑所有人？已有的档期和通用条款核对可以先看。',
    'no_feasible_slot': '目前没有能排下这件事的时间，需要调整可选窗口或已经占用的行程。',
    'tied_no_clause_separates': '现有条款没有分出这些时间的个人优劣。你更看重尽早、尽晚，还是某个候选？明确这一点后可以给出实用首选和备选。',
    'preferences_required': '这些窗口都排得下这件事，现有古法还没有分出个人优劣。你更想尽早、尽晚，还是优先某个候选？明确这个偏好后就能给出实用首选和备选。',
    'practical_tie': '按你给的条件，这些安排仍然并列。需要再补一个实际偏好，才能选出首选；现有依据不支持硬分高下。',
}
BOOK_NAMES = {'yuanhai': '渊海子平', 'sanming': '三命通会'}
# Only these two states still have evidence worth a timed search; a settled
# answer that ends on 「还可补查」 reads as if it were not settled.
RESEARCH_STATES = ('evidence_needed', 'screened_only')


# Kept under the old name; tests and callers import it from here.
_question_kind = question_kind


def _clock(value: str) -> str:
    stamp = datetime.fromisoformat(value)
    return stamp.time().isoformat(timespec='auto' if stamp.second or stamp.microsecond else 'minutes')


def _span(start: str, end: str) -> str:
    """A civil interval with its date once, both ends on the same date or not."""
    lo, hi = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if lo.date() == hi.date():
        return f'{lo.date()} {_clock(start)}–{_clock(end)}'
    return f'{lo.date()} {_clock(start)} 至 {hi.date()} {_clock(end)}'


def _hour_span(hit: dict, on: str | None = None) -> str:
    """``11:41–13:00（午时）``: the part of the hour the window really covers.

    The date is added only when it differs from ``on``, so a lead about one
    morning stays short while an overnight window still reads unambiguously.
    """
    start, end = hit['segment_start'], hit['segment_end']
    text = f"{_clock(start)}–{_clock(end)}（{hit['hour_branch']}时）"
    day = str(datetime.fromisoformat(start).date())
    return text if day == on else f'{day} {text}'


def _hour_hits(row: dict) -> list[dict]:
    return row.get('forbidden_hours_in_window', []) + row.get('contested_hours_in_window', [])


def _day_label(hit: dict) -> str:
    """「庚申日」, or for a 夜子 hour the day whose 五鼠遁 it belongs to."""
    day = hit['day_ganzhi']
    stem = hit.get('rule_stem', day[0])
    return f'{day}日' if stem == day[0] else f'{day}日夜子（时干按次日{stem}日起）'


def _hour_reason(hits: list[dict]) -> str:
    """Why the listed hours matter, without layer-2 vocabulary."""
    parts = []
    settled = [h for h in hits if 'passage_id' in h]
    if settled:
        days = '、'.join(dict.fromkeys(_day_label(h) for h in settled))
        which = '这个时辰' if len(settled) == 1 else '这些时辰'
        parts.append(f'{which}是{days}截路空亡的忌时，《渊海子平》说这时百事不利')
    contested: dict[str, list[dict]] = {}
    for hit in hits:
        if 'readings' in hit:
            contested.setdefault(_day_label(hit), []).append(hit)
    for day, rows in contested.items():
        books = {BOOK_NAMES[pid.split(':')[0]] for h in rows for pid in h['readings']}
        others = [b for b in BOOK_NAMES.values() if b not in books]
        which = '这个时辰' if len(rows) == 1 else '这些时辰'
        named = '、'.join(f'《{b}》' for b in BOOK_NAMES.values() if b in books)
        rest = ('，' + '、'.join(f'《{b}》' for b in others) + '不算') if others else ''
        parts.append(f'{day}的{which}只有{named}算作忌时{rest}')
    return '；'.join(parts)


def _window_row(ranking: dict, choice: dict) -> dict | None:
    """The screened window a placement was taken from."""
    at = datetime.fromisoformat(choice['start'])
    return next((row for row in ranking.get('tiers', [])
                 if row['candidate_id'] == choice['candidate_id']
                 and datetime.fromisoformat(row['start']) <= at < datetime.fromisoformat(row['end'])), None)


def _avoid_sentence(result: dict, choice: dict) -> str:
    """Warn off the named hours in the chosen window, if it has any.

    A placement with such hours carries no ``flexible_start``, so the dated
    slot is safe as given; this tells the reader how far it may not move.
    """
    row = _window_row(result.get('practical_screening', {}), choice)
    hits = _hour_hits(row) if row else []
    if not hits:
        return ''
    on = str(datetime.fromisoformat(choice['start']).date())
    spans = '、'.join(_hour_span(h, on) for h in hits)
    return f'别把时间挪进 {spans}，{_hour_reason(hits)}。'


def _excluded_sentence(result: dict) -> str:
    """Name each candidate a day clause ruled out, with the day and why."""
    ranking = result.get('ranking', {})
    # A candidate keeps a usable part if a whole window survived, or if the
    # practical split kept a piece of an excluded window (a multi-day window
    # that crosses one barred day).
    survivors = {row['candidate_id'] for row in ranking.get('tiers', [])}
    survivors |= {c['candidate_id'] for c in result.get('practical_comparison', []) if c['windows']}
    counts: dict[str, int] = {}
    for row in ranking.get('excluded', []):
        counts[row['candidate_id']] = counts.get(row['candidate_id'], 0) + 1
    # The barred stretch of each (candidate, day), from the practical split.
    # Pieces are stored in UTC; the reader gets the event's own clock.
    zone = ZoneInfo(result['window']['timezone'])
    cut: dict[tuple[str, str], tuple[str, str]] = {}
    for piece in result.get('excluded_segments', []):
        key = (piece['candidate_id'], piece['day_ganzhi'])
        start, end = (datetime.fromisoformat(piece[k]).astimezone(zone).isoformat() for k in ('start', 'end'))
        lo, hi = cut.get(key, (start, end))
        cut[key] = (min(lo, start, key=datetime.fromisoformat), max(hi, end, key=datetime.fromisoformat))
    sentences = []
    for row in ranking.get('excluded', []):
        by_day: dict[str, list[str]] = {}
        for hit in row['excluded_by']:
            by_day.setdefault(hit['day_ganzhi'], []).append(hit['plain'])
        what = '；'.join(f"覆盖到{day}日，是" + '；也是'.join(plains) for day, plains in by_day.items())
        name = row['candidate_id'] + ' '
        # A candidate that keeps another part must say which part is out.
        if row['candidate_id'] in survivors or counts[row['candidate_id']] > 1:
            spans = [cut[(row['candidate_id'], day)] for day in by_day if (row['candidate_id'], day) in cut]
            lo, hi = ((min((s[0] for s in spans), key=datetime.fromisoformat),
                       max((s[1] for s in spans), key=datetime.fromisoformat)) if spans
                      else (row['start'], row['end']))
            name += f"的 {_span(lo, hi)} 这段"
        sentences.append(f'{name}需要避开：{what}。')
    return ''.join(sentences)


def _conflict_sentence(result: dict, kind: str) -> str:
    """Name the window and the clock time of the hours that stopped it."""
    practical = result.get('practical_choice', {})
    checked = practical.get('checked_options') or []
    rows = (checked[-1]['tiers'] + checked[-1]['excluded']) if checked else [
        row for row in result.get('practical_screening', {}).get('tiers', []) if _hour_hits(row)]
    minutes = next((c['duration_minutes'] for c in result.get('candidate_comparison', [])), None)
    parts = []
    for row in rows:
        on = str(datetime.fromisoformat(row['start']).date())
        hits = _hour_hits(row)
        if hits:
            # Without a checked slot, no start in this window stayed clear.
            fits = '' if checked or minutes is None else f'放不下完整的 {minutes} 分钟而不'
            detail = f"{fits}碰到 {'、'.join(_hour_span(h, on) for h in hits)}，{_hour_reason(hits)}"
        elif row.get('excluded_by'):
            detail = '；'.join(f"覆盖到{h['day_ganzhi']}日，是{h['plain']}" for h in row['excluded_by'])
        else:
            continue
        subject = f"{row['candidate_id']} 的 {_span(row['start'], row['end'])}"
        parts.append(f'{subject} {detail}' if kind == 'yes_no' else f'{subject} 目前不能推荐：它{detail}')
    return '；'.join(parts) + '。' if parts else '已查条款在这些时间上有冲突，目前不能推荐。'


def _incomplete_sentence(result: dict) -> str:
    """A window the day rules never reached: name it and the input that would."""
    checked = result.get('practical_choice', {}).get('checked_options') or []
    rows = checked[-1]['unrankable'] if checked else result.get('ranking', {}).get('unrankable', [])
    spans = '、'.join(dict.fromkeys(f"{row['candidate_id']} 的 {_span(row['start'], row['end'])}" for row in rows))
    if any(b['code'] == 'event_longitude_required' for b in result['decision_blockers']):
        why, ask = '还不知道活动地点：日柱按当地真太阳时定，缺经度就定不了', '告诉我在哪个城市或经度，就能接着核。'
    else:
        why, ask = '这次只算到月，没有细算到日柱', '按日或按时细算后就能接着核。'
    return f'现在判断不了，因为{why}，所以 {spans} 还没有套用忌日条款。{ask}'


def _alternatives_sentence(result: dict, limit: int = 4) -> str:
    """The clear start ranges a preference would choose between."""
    options = result.get('practical_choice', {}).get('alternatives') or []
    if not options:
        return ''
    shown = []
    for option in options[:limit]:
        flexible = option.get('flexible_start')
        span = (_span(flexible['earliest'], flexible['latest']) + ' 之间开始' if flexible
                else _span(option['start'], option['end']))
        shown.append(f"{option['candidate_id']} {span}")
    more = f'，另有 {len(options) - limit} 个' if len(options) > limit else ''
    return '可选：' + '；'.join(shown) + more + '。'


def _day_rule_line(candidate_id: str, hit: dict) -> str:
    """Layer-2 line for one excluded day: the rule, its derivation, its passages."""
    head = f"{candidate_id} 原可选窗口覆盖到 {hit['day_ganzhi']} 日"
    return f"{head}{'，是' if 'sources' not in hit else '：'}{rule_detail(hit)}。"


def _utc_offset(stamp: datetime) -> str:
    """``UTC+10``, ``UTC+5:30``, ``UTC-3``: the offset as people say it."""
    offset = stamp.utcoffset()
    total = int(offset.total_seconds() // 60) if offset is not None else 0
    hours, minutes = divmod(abs(total), 60)
    return f"UTC{'-' if total < 0 else '+'}{hours}" + (f':{minutes:02d}' if minutes else '')


def _clock_range(start: str, end: str, zone: str, middle: str = '') -> str:
    """``2026-09-21 08:00–10:00（Australia/Sydney，UTC+10）``.

    The date is written once and the offset once, since readers plan by the
    local clock. When a daylight-saving change falls between the two ends,
    each end keeps its own offset so the arithmetic still shows.
    """
    lo, hi = datetime.fromisoformat(start), datetime.fromisoformat(end)
    later = ('' if hi.date() == lo.date() else f'{hi.date()} ') + _clock(end)
    if lo.utcoffset() == hi.utcoffset():
        return f'{lo.date()} {_clock(start)}–{later}{middle}（{zone}，{_utc_offset(lo)}）'
    return f'{lo.date()} {_clock(start)}（{_utc_offset(lo)}）至 {later}（{_utc_offset(hi)}）{middle}（{zone}）'


def _placement(choice: dict) -> str:
    flexible = choice.get('flexible_start')
    if flexible:
        minutes = int((datetime.fromisoformat(choice['end']) - datetime.fromisoformat(choice['start'])).total_seconds() // 60)
        return _clock_range(flexible['earliest'], flexible['latest'], choice['timezone'],
                            f' 之间开始都行，持续 {minutes} 分钟')
    return _clock_range(choice['start'], choice['end'], choice['timezone'])


GRADE_ANSWER = {'大吉': '好', '吉': '好', '平': '一般', '小凶': '不太好', '凶': '不好', '大凶': '很不好'}
BAD_GRADES = ('小凶', '凶', '大凶')


def _who(people: list[dict]) -> str:
    return '你' if len({p['participant_id'] for p in people}) <= 1 else '你们'


def _births(people: list[dict]) -> str:
    """「丁丑」, 「己卯或庚辰，按较差的算」 when the year is unsettled, or one per person."""
    years: dict[str, list[str]] = {}
    for p in people:
        years.setdefault(p['participant_id'], []).append(p['birth_year'])
    def one(found: list[str]) -> str:
        return found[0] if len(found) == 1 else '或'.join(found) + '，生在立春前后，按较差的算'
    if len(years) == 1:
        return one(next(iter(years.values())))
    return '；'.join(f'{pid} {one(found)}' for pid, found in years.items())


def _labels(factor_lists: list[list[dict]], grade: str) -> str:
    """The labels that set a grade: the bad ones for a bad grade, else the good."""
    polarity = 'bad' if grade in BAD_GRADES else 'good'
    labels = [f['label'] for factors in factor_lists for f in factors if f['polarity'] == polarity]
    return '、'.join(dict.fromkeys(labels))


def _row_labels(row: dict) -> str:
    personal = row.get('personal')
    if not personal:
        return ''
    return _labels([d['factors'] for p in personal['people'] for d in p['days']], personal['grade'])


def _placement_row(result: dict, option: dict) -> dict | None:
    """The screened window a placement sits in."""
    at = datetime.fromisoformat(option['start'])
    rows = [r for r in result.get('practical_screening', result.get('ranking', {})).get('tiers', [])
            if r['candidate_id'] == option['candidate_id']]
    inside = [r for r in rows if datetime.fromisoformat(r['start']) <= at < datetime.fromisoformat(r['end'])]
    return (inside or rows or [None])[0]


def _graded(result: dict, option: dict) -> str:
    """「大吉：命贵人、三合」 for a placement, or '' when no grade was given."""
    grade = option.get('grade')
    if not grade:
        return ''
    row = _placement_row(result, option)
    why = _row_labels(row) if row else ''
    return grade + (f'：{why}' if why else '')


def _personal_people_of(result: dict) -> list[dict]:
    ids = result.get('ranking', {}).get('personal_participant_ids', [])
    return [{'participant_id': p['id'], 'birth_year': year} for p in result['participants'] if p['id'] in ids
            for year in birth_years_of(p['natal'])]


def _entry_list(entries: list[dict], limit: int = 6, event: str = '') -> str:
    shown = []
    for entry in entries[:limit]:
        why = _labels([p['days'][0]['factors'] if 'days' in p else p['factors'] for p in entry['people']],
                      entry['grade'])
        if entry.get('event_hits'):
            why = '、'.join(dict.fromkeys(h['label'] for h in entry['event_hits'])) + '，忌' + event
        shown.append(f"{entry['label']}（{entry.get('span', entry['ganzhi'])}" + (f'，{why}' if why else '') + '）')
    return '、'.join(shown) + (f'等 {len(entries)} 个' if len(entries) > limit else '')


def _context_sentence(calendar: dict, who: str) -> str:
    """Year and month pillars against the person, which the passage weighs above the day."""
    said, parts = set(), []
    for entry in calendar['entries']:
        for person in entry['people']:
            for day in person.get('days', []):
                for key, context in day['context'].items():
                    if context['grade'] in BAD_GRADES and (key, context['ganzhi']) not in said:
                        said.add((key, context['ganzhi']))
                        word = '这一年' if key == 'year' else '这个月'
                        parts.append(f"{word}（{context['ganzhi']}）本身对{who}是{context['grade']}"
                                     f"（{_labels([context['factors']], context['grade'])}），"
                                     + ('协纪说太岁冲命最凶' if key == 'year' else '协纪说月次于年、重于日'))
    return ('另外，' + '；'.join(parts) + '。') if parts else ''


def _calendar_sentence(result: dict, kind: str) -> str:
    """Period answer: the best and the worst days (or months) for the person."""
    calendar = result['personal_calendar']
    entries, people = calendar['entries'], calendar['people']
    who = _who(people)
    event = calendar.get('event', '')
    basis = f"按{who}出生那年的干支（{_births(people)}）看"
    if len(entries) == 1 and entries[0].get('event_hits'):
        entry = entries[0]
        head = '不行。' if kind == 'yes_no' else ''
        return (f"{head}{entry['label']}（{entry['ganzhi']}）{event}需要避开：是"
                + '；也是'.join(h['plain'] for h in entry['event_hits'])
                + f"。这天对{who}本人是{entry['grade']}。" + _context_sentence(calendar, who))
    if len(entries) == 1:
        entry = entries[0]
        why = _labels([p['days'][0]['factors'] if 'days' in p else p['factors'] for p in entry['people']],
                      entry['grade'])
        head = GRADE_ANSWER[entry['grade']] + '。' if kind == 'yes_no' else ''
        return (f"{head}{basis}，{entry['label']}（{entry.get('span', entry['ganzhi'])}）对{who}是{entry['grade']}"
                + (f"：{why}" if why else '，没有碰到相主里的吉凶条目') + '。'
                + _context_sentence(calendar, who))
    unit = {'day': '日子', 'month': '月份', 'year': '年份'}[calendar['unit']]
    open_days = [e for e in entries if not e.get('event_hits')]
    best = min((e['grade'] for e in open_days), key=('大吉', '吉', '平', '小凶', '凶', '大凶').index, default='平')
    good = [e for e in open_days if e['grade'] == best] if best in ('大吉', '吉') else []
    barred = [e for e in entries if e.get('event_hits')]
    bad = [e for e in open_days if e['grade'] in ('凶', '大凶')]
    light = [e for e in open_days if e['grade'] == '小凶']
    parts = [f"{basis}，这段时间{event}对{who}最好的{unit}是{_entry_list(good)}，{'都' if len(good) > 1 else ''}是{best}" if good
             else f"{basis}，这段时间没有{event}对{who}吉的{unit}"]
    if barred:
        parts.append(f"{event}要避开{_entry_list(barred, event=event)}")
    if bad:
        parts.append(('另外' if barred else '') + f"要避开{_entry_list(bad)}")
    if light and len(entries) > 31:
        parts.append(f"另有 {len(light)} 天略差（冲{who}生年，协纪说略轻）")
    elif light:
        parts.append(f"{_entry_list(light)}略差，协纪说这种冲主要是口舌是非")
    if not bad and not light and not barred:
        parts.append(f"没有冲{who}生年的{unit}")
    return '；'.join(parts) + '。' + _context_sentence(calendar, who)


def _factor_lines(head: str, grade: str, factors: list[dict], quoted: set[str]) -> str:
    """One layer-2 line: the grade, each factor in plain words, each quote once."""
    if not factors:
        return f'{head}：{grade}，没有碰到相主里的吉凶条目。'
    line = f"{head}：{grade}。" + '；'.join(f['plain'] for f in factors) + '。'
    new = [f['quote'] for f in factors if f['quote'] not in quoted]
    quoted.update(new)
    if new:
        line += '原文：' + '、'.join(f'「{q}」' for q in dict.fromkeys(new)) + f'（{XIANGZHU_PASSAGE}）。'
    return line


def _personal_lines(result: dict) -> list[str]:
    """Layer 2 for 相主: the method in the passage's words, then every graded day."""
    calendar = result.get('personal_calendar') or {}
    ranking = result.get('ranking', {})
    if not calendar.get('entries') and not ranking.get('personal_participant_ids'):
        return []
    lines = ['择日看人，《协纪辨方书》卷三十三说「從來皆論生年不論生日有論生日者非古法也」'
             f'（{XIANGZHU_PASSAGE}）。白话说，挑日子看的是出生那一年的干支，不是日主。'
             '禄、贵人、驿马、长生各用一张古表，出处随条列出；吉凶等级按原文用词：天克地冲最凶，'
             '冲命按方向分凶与略轻，命禄、命贵人、食禄最吉，合官贵、合财富，其余为吉。'
             '原文的例子是修造（以宅长之命为主）和安葬（以亡命为主），天克地冲、天比地冲写明是选择家对一切用事的通忌；'
             '这里把同一套相主规则用在这件事上。原文另讲的「补龙扶山」看房屋坐山，没有实现。']
    quoted: set[str] = set()
    rows = calendar.get('people') or [{'participant_id': pid} for pid in ranking.get('personal_participant_ids', [])]
    ids = [p['participant_id'] for p in rows]

    def label(person: dict) -> str:
        # Several people are named; one person with two possible years names the year.
        if len(set(ids)) > 1:
            return f"{person['participant_id']} "
        return f"按{person['birth_year']}年：" if len(ids) > 1 else ''
    entries = calendar.get('entries', [])
    if len(entries) > 31:
        # A long list keeps what the answer turns on: the best days and the days to avoid.
        order = ('大吉', '吉', '平', '小凶', '凶', '大凶')
        best = min((e['grade'] for e in entries if not e.get('event_hits')), key=order.index, default='平')
        entries = [e for e in entries if e.get('event_hits') or e['grade'] in (best, '凶', '大凶')][:60]
    for entry in entries:
        for hit in entry.get('event_hits', []):
            lines.append(f"{entry['label']}（{entry['ganzhi']}）{calendar['event']}：{rule_detail(hit)}。")
        for person in entry['people']:
            who = label(person)
            if 'days' in person:
                lines.append(_factor_lines(f"{who}{entry['label']}（{entry['ganzhi']}）", person['days'][0]['grade'],
                                           person['days'][0]['factors'], quoted))
            else:
                lines.append(_factor_lines(f"{who}{entry['label']}（{entry['span']}）", person['grade'],
                                           person['factors'], quoted))
    for row in ranking.get('tiers', []) + ranking.get('excluded', []):
        for person in row.get('personal', {}).get('people', []):
            who = label(person)
            for day in person['days']:
                lines.append(_factor_lines(f"{row['candidate_id']} {who}覆盖的{day['day_ganzhi']}日",
                                           day['grade'], day['factors'], quoted))
    return list(dict.fromkeys(lines))


def _passed_over_sentence(result: dict) -> str:
    """A better-graded window left out because every start ran into a named hour."""
    practical = result.get('practical_choice', {})
    rows = result.get('practical_screening', result.get('ranking', {})).get('tiers', [])
    minutes = next((c['duration_minutes'] for c in result.get('candidate_comparison', [])), None)
    parts = []
    for item in practical.get('passed_over', []):
        row = next((r for r in rows if (r['candidate_id'], r['start']) == (item['candidate_id'], item['start'])), None)
        hits = _hour_hits(row) if row else []
        if not hits:
            continue
        on = str(datetime.fromisoformat(item['start']).date())
        fits = f'放不下完整的 {minutes} 分钟' if minutes else '排不进去'
        parts.append(f"{item['candidate_id']} 对{_who(_personal_people_of(result))}更吉（{item['grade']}），"
                     f"但 {_span(item['start'], item['end'])} 整段碰到 {'、'.join(_hour_span(h, on) for h in hits)}，"
                     f"{_hour_reason(hits)}，{fits}")
    return '；'.join(parts) + '。' if parts else ''


def _colour_advice(result: dict) -> dict | None:
    """Colour advice for a colour question, from the first person's natal reading."""
    if not asks_colour(result.get('question')):
        return None
    return next((p['natal_interpretation']['colour_advice'] for p in result['participants']
                 if 'colour_advice' in p.get('natal_interpretation', {})), None)


def _lead_sentence(result: dict) -> str:
    """The summary paragraph: the answer first, built from what was computed."""
    advice = _colour_advice(result)
    if advice:
        return colour_lead(advice)
    state = result['conclusion']['status']
    kind = _question_kind(result.get('question', ''))
    excluded = _excluded_sentence(result)
    if state == 'practical_choice':
        practical = result['practical_choice']
        first, backup = practical['first_choice'], practical.get('backup')
        head = (f"可以：{first['candidate_id']}，{_placement(first)}。" if kind == 'yes_no'
                else f"首选 {first['candidate_id']}：{_placement(first)}。")
        graded = _graded(result, first)
        if graded:
            people = _personal_people_of(result)
            who = _who(people)
            basis = f"按协纪相主（看{who}出生那年的干支 {_births(people)}），这天对{who}是{graded}。"
            if '同等的再按' in practical['reason']:
                basis += practical['reason'].split('，', 1)[1] + '。'
        # A stated preference ordered these; say so rather than let the order
        # pass for a classical one. A lone window was not ordered at all.
        elif practical['reason'].startswith('按你'):
            basis = practical['reason'] + '；这是按档期排的，不是古法排序。'
        else:
            basis = practical['reason'] + '；这次没有可用的出生年，没有按相主排吉凶。'
        lead = head + basis + _passed_over_sentence(result)
        if backup:
            lead += (f"备选 {backup['candidate_id']}" + (f"（{_graded(result, backup)}）" if backup.get('grade') else '')
                     + f"：{_placement(backup)}。")
        return lead + excluded + _avoid_sentence(result, first)
    if state == 'excluded_by_clause':
        return ('不行。' if kind == 'yes_no' else '') + excluded + '需要换到其他日子再比。'
    if state == 'clause_conflict':
        return ('不建议。' if kind == 'yes_no' else '') + _conflict_sentence(result, kind) + excluded
    if state == 'screening_incomplete':
        return _incomplete_sentence(result) + excluded
    if state == 'personal_calendar':
        return _calendar_sentence(result, kind)
    options = result.get('practical_choice', {}).get('alternatives') or []
    if state in ('preferences_required', 'practical_tie') and options and options[0].get('grade'):
        who = _who(_personal_people_of(result))
        return (f"这几个时间按协纪相主对{who}同样是{options[0]['grade']}，古法分不出先后，要看{who}的偏好："
                f"更想尽早、尽晚，还是优先某个候选？" + _alternatives_sentence(result) + excluded)
    if state in ('preferences_required', 'practical_tie'):
        return ASK_LEADS[state] + _alternatives_sentence(result) + excluded
    if state in ASK_LEADS:
        return ASK_LEADS[state] + excluded
    if state == 'screened_only':
        remaining = '、'.join(result['recommendation'].get('remaining', []))
        event = EVENT_WORDS.get(result['capability']['scenario'], '')
        return (f'{remaining} 没有碰到本次检查的{event}忌日，但这一项检查还不能说明它整体适合你。' + excluded)
    # evidence_needed: a period or custom question with no dated verdict.
    capability = result['capability']
    observations = [o for p in result['participants'] for o in p['traditional_observations']]
    grain = result['research'].get('requested_granularity')
    intent = capability.get('intent')
    if capability.get('custom'):
        lead = f"「{capability['label']}」和古法事项的对应还没核过，本库现有条款不能直接判断它在这段时间的吉凶。"
    elif intent == 'natal':
        lead = '这次按出生盘本身看，不涉及某一天的吉凶。'
    elif intent == 'research':
        lead = '这次是查古籍依据，不下个人吉凶结论。'
    elif capability.get('route') != 'period':
        lead = '这些候选时间，本库现有条款还没有分出个人吉凶。'
    elif result.get('personal_calendar', {}).get('status') == 'birth_year_unknown':
        lead = ('哪天对你好坏要按你出生那一年的干支看，但你的出生年柱还没定下来，也没有可比较的候选；'
                '补上出生时刻（立春前后尤其要紧）就能逐日给出。')
    elif grain in ('day', 'hour'):
        lead = '按日给个人算整体吉凶，本库现有条款里没有这一类，所以不给哪天好、哪天坏的结论。'
    else:
        lead = '给这段时间下整体吉凶结论，本库现有条款还不够。'
    if observations:
        lead += '已实现的两条十年大运例式里，你对上了一条：' + observations[0]['plain_observation']
    else:
        lead += '已实现的两条十年大运例式，你的盘都没有对上。'
    return lead


def render_answer(result: dict) -> str:
    """Render the same conclusion packet consumed by the host, in everyday Chinese."""
    if result.get('capability', {}).get('route') == 'itinerary':
        from fortune_itinerary import render_itinerary
        return render_itinerary(result)
    if not result.get('ok') or result.get('status') == 'specialist_required':
        return result['message']
    state = result['conclusion']['status']
    advice = _colour_advice(result)
    lines = [_lead_sentence(result), *(colour_lines(advice) if advice else []),
             _window_description(result['window'])]
    comparison = result.get('candidate_comparison', [])
    for candidate in comparison:
        if not candidate['available']:
            lines.append(f"{candidate['candidate_id']}：{candidate['reason']}。")
        elif state != 'practical_choice':
            lines.extend(_candidate_description(candidate, w) for w in candidate['windows'][:3])
    if state == 'no_feasible_slot':
        return '\n\n'.join(lines)
    ranking = result.get('ranking', {})
    if ranking.get('tiers') or ranking.get('excluded'):
        scenario = ranking.get('scenario', result['capability']['scenario'])
        event = EVENT_WORDS.get(scenario, '')
        if scenario in TIANDI_EVENTS:
            lines.append('《渊海子平·论天地转杀》说：“其日最忌，上官受职、出行商贾、造作、嫁娶。”（' + TIANDI_SOURCE + f'）白话说，这条是在指出特定季节需要避开的日子；没有碰到它，不等于其他条件都合适。这项检查只看{event}日期本身；对你个人的吉凶另按相主看，见下文。')
        checked = [r for r in XIEJI_RULES if any(XIEJI_TERMS.get(scenario, '\0') in a['quote'] for a in r['avoid'])]
        if checked:
            names = '、'.join(r['label'] for r in checked)
            ids = '、'.join(dict.fromkeys(a['passage_id'] for r in checked for a in r['avoid']))
            lines.append(f'本次还按《协纪辨方书》卷十核了{names}（{ids}）：书里把{event}列在这几种日子的所忌里，并写明遇到吉神也照样忌。'
                         f'协纪其余按吉凶轻重取舍的宜忌没有实现，所以没碰到这几种日子，不等于这天宜{event}。')
        if state == 'practical_choice' and any(row.get('excluded_by') or _hour_hits(row) for row in ranking.get('tiers', []) + ranking.get('excluded', [])):
            lines.append('下面说明原可选大窗口里需要避开的部分。上面的安排仅指已另行核查的具体子时段，不包含这些部分。')
        for row in ranking.get('excluded', []):
            for hit in row['excluded_by']:
                lines.append(_day_rule_line(row['candidate_id'], hit))
        seen = set()
        for row in ranking.get('tiers', []) + ranking.get('excluded', []):
            hits = row.get('forbidden_hours_in_window', [])
            if hits:
                text = '、'.join(f"{_day_label(h)} {_hour_span(h)}" for h in hits)
                how = '；'.join(dict.fromkeys(h['derivation'] for h in hits))
                lines.append(f"{row['candidate_id']} 的窗口覆盖到 {text}，是截路空亡的忌时（{JIELU_METHOD_SOURCE}：{how}）。该段‘正犯’的限定仍需连同上下文核对。")
            # An unsettled day is worth a line only where the window reaches an
            # hour one of its readings names; elsewhere both books agree it is clear.
            # Keyed by the day whose 遁 gave the hour, which a 夜子 hour does not share
            # with its civil day.
            touched: dict[str, list[dict]] = {}
            for hit in row.get('contested_hours_in_window', []):
                touched.setdefault(_day_label(hit), []).append(hit)
            for label, group in touched.items():
                if label in seen:
                    continue
                seen.add(label)
                rule = jielu_kongwang(group[0]['rule_stem'])
                both = '；'.join(f"《{BOOK_NAMES[r['passage_id'].split(':')[0]]}》作{''.join(r['hours'])}（{r['passage_id']}）" for r in rule['readings'])
                spans = '、'.join(_hour_span(h) for h in group)
                lines.append(f"{label}忌时两说并列：{both}。白话说，{row['candidate_id']} 覆盖到的 {spans} 只在其中一本书里算忌时，两本书指向不同时间，目前无法据此定下这段能不能用。")
    lines.extend(_personal_lines(result))
    for person in result['participants']:
        if person.get('time_note'):
            lines.append(person['time_note'] + '。')
        for observation in person['traditional_observations'][:2]:
            source = observation['source']
            if observation['plain_observation'] not in lines[0]:
                lines.append(observation['plain_observation'])
            lines.append('《子平真诠·论行运》：“' + source['text'] + '”\n白话说：' + observation['plain_meaning'] + observation['plain_application'] + observation['limit'] + '\n出处：' + source['source_url'])
    if not ranking and not any(p['traditional_observations'] for p in result['participants']):
        quote = '而取運則又以運之干支，配八字之喜忌。'
        source = result['evidence']['principle'][0]
        if quote not in source['text']:
            raise ValueError('引文与冻结原文不一致')
        lines.append('《子平真诠·论行运》：“' + quote + '”\n白话说，要看一段运程怎样作用于一个人，得把这段运程和他的整张出生盘一起分析。本次已经算出相关盘面，但已实现的两条运程例式没有给出本题的完整结论。\n出处：' + source['source_url'])
    missing = [b['message'] for b in result['decision_blockers'] if b['code'] == 'event_longitude_required']
    lines.extend(dict.fromkeys(missing))
    if state in RESEARCH_STATES:
        lines.append('以上是已有依据支持的部分。还缺的本题条款可继续补查约5分钟；这份计算结果尚未执行外部检索，不代表古籍里不存在相关内容。')
    return '\n\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='个人未来时段事实与档期核查；从 stdin 读取 JSON，不自动保存',
        epilog='Top-level JSON keys: ok tool version schema_version status request_time window capability '
               'priority method participants availability recommendation research evidence output_order '
               'candidate_comparison decision_blockers. '
               'participants[]: id profile_revision input_fingerprint natal target traditional_observations. '
               'target: segments pillar_catalog luck_catalog; relationships are not event verdicts. '
               'Errors: ok=false error message; specialist routing: message capability.')
    parser.add_argument('--stdin', action='store_true', required=True)
    parser.add_argument('--markdown', action='store_true', help='输出白话事实说明；不代替补查后的完整解读')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        result = read_request(json.load(sys.stdin), data_dir=args.data_dir)
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        result = error_envelope('fortune_reading', 'invalid_request', str(exc))
        if args.markdown:
            print('目前还算不了这一部分：' + result['message'])
        else:
            json_print(result)
        return 1
    # Rendering reads only what read_request produced, so an error here is a
    # defect. Inside the try above, a renderer KeyError once came out as
    # 「目前还算不了这一部分」 on a request that had been answered.
    if args.markdown:
        print(render_answer(result))
    else:
        json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
