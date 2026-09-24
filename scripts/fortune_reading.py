"""One request -> personal facts, explicit target periods and honest evidence gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from bazi_calc import build_parser, calculate_bazi
from bazi_reading import chart_facts, prepare_reading
from birth_interval import calculate_interval
from classical_guidance import research_sources
from fortune_calendar import period_facts
from fortune_decision import choose_practical, conclusion_packet, route_request
from fortune_ranking import (
    JIELU_METHOD_SOURCE,
    TIANDI_SOURCE,
    rank_candidates,
    split_eligible_windows,
)
from fortune_rules import capabilities, evidence, luck_observations, research_request
from fortune_selection import compare_candidates, decision_blockers, event_basis
from fortune_time import candidate_windows, resolve_window
from personal_profiles import birth_arguments, load_profile, validate_person
from request_time import capture_request_time
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

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


def read_request(payload: dict, *, data_dir: Path | None = None,
                 clock: Callable[[], datetime] | None = None, _shared: dict | None = None) -> dict:
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
    capability = route_request(payload, capabilities(scenario)[0])
    if capability['route'] == 'specialist':
        return ok_envelope('fortune_reading', {'schema_version': '1.0', 'status': 'specialist_required',
                            'request_time': now, 'capability': capability,
                            'message': capability['missing']})
    if 'period' not in payload and capability.get('intent') in ('natal', 'research'):
        local_date = datetime.fromisoformat(now['local']).date()
        payload = {**payload, 'period': {'start': str(local_date), 'end': str(local_date + timedelta(days=1))}}
    if 'period' not in payload:
        raise ValueError('请提供 period，例如 下周 或明确 start/end；不能猜目标日期')
    window = resolve_window(payload['period'], now, event.get('timezone') or now['timezone'])
    people = _people(payload.get('participants', []), data_dir)
    priority = event.get('priority')
    ids = {p['id'] for p in people}
    if priority is not None and priority != 'equal' and priority not in ids:
        raise ValueError('priority 须为 equal 或一位参与者 id')
    if priority is None:
        priority = 'equal' if scenario == 'wedding' else people[0]['id'] if len(people) == 1 else None
    length = (datetime.fromisoformat(window['end']) - datetime.fromisoformat(window['start'])).days
    grain = payload.get('granularity', 'hour' if capability['route'] == 'selection' else
                        'month' if length > 31 else 'day')
    standard = event.get('time_standard', 'true-solar')
    sect = event.get('sect', 2)
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
        raise ValueError('比较档期请给出具体事件 scenario，不能把运势查询当择时')
    include = payload.get('include_natal_reading', capability['route'] == 'period')
    include_research = payload.get('include_research', False)
    if type(include) is not bool or type(include_research) is not bool:
        raise ValueError('include_natal_reading / include_research 必须为布尔值')
    focus = ([interval for c in result['availability'] for interval in c['intervals']]
             if capability['route'] == 'selection' else None)
    for person in people:
        birth = dict(person['person']['birth'])
        approximate = person['person']['time_certainty'] == 'approximate'
        if approximate:
            # A guessed point is not an uncertainty interval. Reuse the existing
            # whole-date candidate check until a real interval is supplied.
            birth.pop('hour', None)
            birth.pop('minute', None)
        args = build_parser(diagnostics=False).parse_args(birth_arguments(birth) + [
            '--years', '120', '--current-timezone', now['timezone'], '--request-time', now['utc']])
        cache = _shared['natal_charts'] if _shared is not None else {}
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
                              longitude=event.get('longitude'), sect=sect, focus=focus)
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
        result['participants'].append(row)
    result['evidence'] = evidence()
    if capability['route'] == 'selection':
        screened = result['availability']
        if capability.get('calendar_screening') == 'rule_based':
            # Keep the original calendar-only availability; expose excluded parts separately.
            screened, result['excluded_segments'] = split_eligible_windows(
                screened, result['participants'][0], payload.get('duration_minutes', 60))
        result['candidate_comparison'] = compare_candidates(result['availability'], result['participants'],
            duration_minutes=payload.get('duration_minutes', 60), timezone=window['timezone'])
        result['event_method'] = event_basis(result['candidate_comparison'], result['participants'],
            scenario=scenario, timezone=window['timezone'], standard=standard,
            longitude=event.get('longitude'))
        # Ranking runs only where fortune_rules declares rule_based; every tier
        # it produces cites a passage. See references/26-precedence.md.
        if capability.get('calendar_screening') == 'rule_based':
            subject = next((p for p in result['participants'] if p['id'] == priority),
                           result['participants'][0])
            ranking = rank_candidates(result['candidate_comparison'], subject, scenario=scenario)
            ranking['calendar_participant_id'] = subject['id']
            result['ranking'] = ranking
            result['practical_comparison'] = compare_candidates(screened, result['participants'],
                duration_minutes=payload.get('duration_minutes', 60), timezone=window['timezone'])
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
            struck = {e['candidate_id'] for e in ranking['excluded']}
            survivors = [c for c in dict.fromkeys(t['candidate_id'] for t in ranking['tiers'])
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
            result['practical_screening'] = rank_candidates(result['practical_comparison'], subject, scenario=scenario)
    if include_research:
        result['research']['source_bundle'] = research_sources(scenario, limit=1)
    result['decision_blockers'] = decision_blockers(result)
    if capability['route'] == 'selection':
        practical = choose_practical(result, payload.get('preferences'))
        result['practical_choice'] = practical
        if result['priority'] is None:
            result['recommendation'] = {'status': 'participant_priority_required', 'first_choice': None, 'backup': None}
        elif practical['status'] == 'practical_choice':
            result['recommendation'] = {'status': 'practical_choice',
                                       'first_choice': practical['first_choice']['candidate_id'],
                                       'backup': practical['backup']['candidate_id'] if practical['backup'] else None,
                                       'basis': 'practical_constraints'}
            result['decision_blockers'] = [b for b in result['decision_blockers'] if b['code'] != 'clause_conflict']
        elif practical['status'] == 'clause_conflict':
            result['recommendation'] = {'status': 'clause_conflict', 'first_choice': None, 'backup': None}
        elif practical['status'] in ('preferences_required', 'practical_tie'):
            result['recommendation'] = {'status': practical['status'], 'first_choice': None, 'backup': None}
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


def render_answer(result: dict) -> str:
    """Render the same conclusion packet consumed by the host, in everyday Chinese."""
    if result.get('capability', {}).get('route') == 'itinerary':
        from fortune_itinerary import render_itinerary
        return render_itinerary(result)
    if not result.get('ok') or result.get('status') == 'specialist_required':
        return result['message']
    state = result['conclusion']['status']
    practical = result.get('practical_choice', {})
    leads = {
        'evidence_needed': '目前有依据的分析见下文；现有规则还不能判断这段时间会发生哪些具体事情。',
        'availability_required': '请一次告诉我可用日期、每天能参加的时段，以及事情需要多久，我就能继续比较具体安排。',
        'participant_priority_required': '这次安排主要考虑谁，还是同等考虑所有人？已有的档期和通用条款核对可以先看。',
        'no_feasible_slot': '目前没有能排下这件事的时间，需要调整可选窗口或已经占用的行程。',
        'screened_only': '这个窗口没有命中本次检查的出行忌日条款，但这一项检查还不能说明它整体适合你。',
        'tied_no_clause_separates': '现有条款没有分出这些时间的个人优劣。你更看重尽早、尽晚，还是某个候选？明确这一点后可以给出实用首选和备选。',
        'excluded_by_clause': '按本次核对的出行忌日条款，这些窗口需要避开；具体命中的日期和依据在下面。',
        'clause_conflict': '这个窗口虽没有命中已查的忌日，但涉及另一条忌时或版本分歧，目前不能把它当作整体合适的时间来推荐。',
        'preferences_required': '这些窗口都排得下这件事，现有古法还没有分出个人优劣。你更想尽早、尽晚，还是优先某个候选？明确这个偏好后就能给出实用首选和备选。',
        'practical_tie': '按你给的条件，这些安排仍然并列。需要再补一个实际偏好，才能选出首选；现有依据不支持硬分高下。',
    }
    if state == 'practical_choice':
        first = practical['first_choice']
        lead = f"按你的实际安排，首选 {first['candidate_id']}：{_display_time(first['start'])} 至 {_display_time(first['end'])}（{first['timezone']}）。" + practical['reason'] + '。这是档期选择，现有古法尚未分出个人吉凶高下。'
        if practical.get('backup'):
            backup = practical['backup']
            lead += f"备选 {backup['candidate_id']}：{_display_time(backup['start'])} 至 {_display_time(backup['end'])}（{backup['timezone']}）。"
    else:
        lead = leads[state]
    lines = [lead, _window_description(result['window'])]
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
        lines.append('《渊海子平·论天地转杀》说：“其日最忌，上官受职、出行商贾、造作、嫁娶。”（' + TIANDI_SOURCE + '）白话说，这条是在指出特定季节需要避开的日子；没有碰到它，不等于其他条件都合适。这项检查按出行日期计算，没有用完整八字给你排名。')
        if state == 'practical_choice' and any(row.get('excluded_by') or row.get('forbidden_hours_in_window') or row.get('unresolved_hour_rules') for row in ranking.get('tiers', []) + ranking.get('excluded', [])):
            lines.append('下面说明原可选大窗口里需要避开的部分。上面的安排仅指已另行核查的具体子时段，不包含这些部分。')
        for row in ranking.get('excluded', []):
            for hit in row['excluded_by']:
                lines.append(f"{row['candidate_id']} 原可选窗口覆盖到 {hit['day_ganzhi']} 日，命中这条忌日规则。")
        seen = set()
        for row in ranking.get('tiers', []) + ranking.get('excluded', []):
            hits = row.get('forbidden_hours_in_window', [])
            if hits:
                text = '、'.join(dict.fromkeys(f"{h['day_ganzhi']}日的{h['hour_branch']}时" for h in hits))
                lines.append(f"{row['candidate_id']} 涉及 {text} 的忌时说法（{JIELU_METHOD_SOURCE}）。也就是说，单看日期未触犯一条规则，并不能消除时段上的疑问；该段‘正犯’的限定仍需连同上下文核对。")
            for day in row.get('days', []):
                rule = day['hour_rule']
                if rule['resolved'] or day['day_ganzhi'] in seen:
                    continue
                seen.add(day['day_ganzhi'])
                both = '；'.join(f"《{'渊海子平' if r['passage_id'].startswith('yuanhai') else '三命通会'}》作{''.join(r['hours'])}（{r['passage_id']}）" for r in rule['readings'])
                lines.append(f"{day['day_ganzhi']}日忌时两说并列：{both}。白话说，两本书指向不同时间，目前无法据此选出更好的时段。")
    for person in result['participants']:
        if person.get('time_note'):
            lines.append(person['time_note'] + '。')
        for observation in person['traditional_observations'][:2]:
            source = observation['source']
            lines.append(observation['plain_observation'])
            lines.append('《子平真诠·论行运》：“' + source['text'] + '”\n白话说：' + observation['plain_meaning'] + observation['plain_application'] + observation['limit'] + '\n出处：' + source['source_url'])
    if not ranking and not any(p['traditional_observations'] for p in result['participants']):
        quote = '而取運則又以運之干支，配八字之喜忌。'
        source = result['evidence']['principle'][0]
        if quote not in source['text']:
            raise ValueError('引文与冻结原文不一致')
        lines.append('《子平真诠·论行运》：“' + quote + '”\n白话说，要看一段运程怎样作用于一个人，得把这段运程和他的整张出生盘一起分析。本次已经算出相关盘面，但已实现的两条运程例式没有给出本题的完整结论；不能只看到“财”“官”就认定会收到钱或录用。\n出处：' + source['source_url'])
    missing = [b['message'] for b in result['decision_blockers'] if b['code'] == 'event_longitude_required']
    lines.extend(dict.fromkeys(missing))
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
        if args.markdown:
            print(render_answer(result))
        else:
            json_print(result)
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        result = error_envelope('fortune_reading', 'invalid_request', str(exc))
        if args.markdown:
            print('目前还算不了这一部分：' + result['message'])
        else:
            json_print(result)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
