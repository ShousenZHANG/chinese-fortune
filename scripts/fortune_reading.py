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
from classical_guidance import research_sources
from fortune_calendar import period_facts
from fortune_rules import capabilities, evidence, luck_observations, research_request
from fortune_selection import compare_candidates, decision_blockers, event_basis
from fortune_time import candidate_windows, resolve_window
from personal_profiles import birth_arguments, load_profile, validate_person
from request_time import capture_request_time
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

FIELDS = {'current_timezone', 'request_time', 'period', 'event', 'events', 'participants',
          'candidates', 'duration_minutes', 'busy', 'granularity', 'include_natal_reading', 'include_research'}
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
    capability = capabilities(scenario)[0]
    if capability['route'] == 'specialist':
        return ok_envelope('fortune_reading', {'schema_version': '1.0', 'status': 'specialist_required',
                            'request_time': now, 'capability': capability,
                            'message': capability['missing']})
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
    result: dict = {'schema_version': '1.0', 'status': 'partial', 'request_time': now,
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
    include = payload.get('include_natal_reading', False)
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
            cache[person['input_fingerprint']] = calculate_bazi(args)
        chart = cache[person['input_fingerprint']]
        if not chart.get('ok'):
            raise ValueError(person['id'] + '：' + chart['message'])
        natal_reading = prepare_reading(chart) if include else None
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
            row['time_note'] = '出生时分仅约数；本次保守核对全天共同部分，不以约数确定时柱与大运'
        if natal_reading:
            row['natal_interpretation'] = {k: v for k, v in natal_reading.items() if k != 'chart_facts'}
        result['participants'].append(row)
    result['evidence'] = evidence()
    if capability['route'] == 'selection':
        result['candidate_comparison'] = compare_candidates(result['availability'], result['participants'],
            duration_minutes=payload.get('duration_minutes', 60), timezone=window['timezone'])
        result['event_method'] = event_basis(result['candidate_comparison'], result['participants'],
            scenario=scenario, timezone=window['timezone'], standard=standard,
            longitude=event.get('longitude'))
    if include_research:
        result['research']['source_bundle'] = research_sources(scenario, limit=1)
    result['decision_blockers'] = decision_blockers(result)
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
    if result.get('capability', {}).get('route') == 'itinerary':
        from fortune_itinerary import render_itinerary
        return render_itinerary(result)
    if not result.get('ok') or result.get('status') == 'specialist_required':
        return result['message']
    state = result['recommendation']['status']
    choices = result['availability']
    if choices:
        count = sum(item['available'] for item in choices)
        lead = f'你给的 {len(choices)} 个时间窗口中，{count} 个能排下这件事。'
    else:
        lead = '这段时间的日期、你的出生盘，以及两者对应的关系已经算出。'
    reasons = {
        'evidence_needed': '目前核实的古籍条款还不足以据此断定这段时间的吉凶，或选出最适合你的日期和时段。',
        'availability_required': '还需要你能参加的时间窗口和事情要持续多久，才能比较安排。',
        'participant_priority_required': '还需要确认这次主要为谁安排；不能默认替其中一人优先。',
        'no_feasible_slot': '目前没有能排下这件事的时间，需调整可选窗口或占用安排。',
    }
    if result['capability']['route'] == 'period':
        reasons['evidence_needed'] = '整体顺不顺，还需要核清整张盘和对应的古籍条件；下面先说明已经能核实的部分。'
    window = result['window']
    lines = [lead + reasons[state], '', _window_description(window)]
    comparisons = result.get('candidate_comparison', [])
    if comparisons:
        lines.extend(['', '档期核对如下；可安排不等于吉利。', ''])
        for candidate in comparisons:
            if not candidate['available']:
                lines.append(f"- {candidate['candidate_id']}：{candidate['reason']}。")
            for interval in candidate['windows']:
                lines.append(_candidate_description(candidate, interval))
        if result['priority'] is None and state != 'participant_priority_required':
            lines.append('还需要确认这次主要为谁安排。')
    if state == 'no_feasible_slot':
        lines.extend(['', '先调整可选窗口或已占用的行程，再比较择时依据。'])
        return '\n'.join(lines)
    method = result.get('event_method')
    if method and method['charts']:
        lines.extend(['', '这些候选时间也已按《元灵经》的已核方法计算地盘、值符和值使，'
                      '并核对每个人的出生年干落在哪里。年干只是出生八字的一部分；'
                      '星门的其余条件尚未核全，因此这一步还不能给候选时间排吉凶顺序。'])
    for p in result['participants']:
        natal = p['natal']
        first = p['target']['segments'][0]['facts']
        day = natal.get('day_master', {}).get('stem')
        lines.extend(['', f"{p['id']}：出生盘里代表你自身的日干是{day or '待确认'}；"
                      f"这段时间开始时对应{first['pillars']['year']}年、{first['pillars']['month']}月。"
                      '这些是计算结果，单凭这些字还不能确定事情顺不顺。'])
        if p['target'].get('missing_input'):
            lines.append('还缺：' + p['target']['missing_input'] + '。')
        if p.get('time_note'):
            lines.append(p['time_note'] + '。')
        elif not natal.get('hour_known'):
            lines.append('出生时段尚未确定，完整时柱与起运时间仍需核清。')
        if p['traditional_observations']:
            lines.append('下面解释目标时间内的长期背景。古法把十年划为一段，称为“大运”。')
        for observation in p['traditional_observations'][:3]:
            source = observation['source']
            lines.extend(['', observation['plain_observation'], '',
                          '《子平真诠·论行运》（东里书斋整理本）正文：“' + source['text'] + '”',
                          '白话说：' + observation['plain_meaning'] + observation['plain_application']
                          + observation['limit'], '', '出处：' + source['source_url']])
    quote = '而取運則又以運之干支，配八字之喜忌。'
    if quote not in result['evidence']['principle'][0]['text']:
        raise ValueError('白话示例所引原文与当前固定版本不一致')
    detail_limit = ('但这段原文没有给出本次事项的逐日、逐时排名办法。' if result['capability']['route'] == 'selection'
                    else '这段原文讲的是较长运程，还不足以判断窗口内每天、每个小时怎样。')
    lines.extend(['', '《子平真诠·论行运》（东里书斋整理本）正文：“' + quote + '”', '',
                  '白话说：分析一段运程，要把它与本人的整张出生盘放在一起看，先查清什么条件起作用。'
                  '本次已分别算出每个人的出生盘与目标时间；' + detail_limit +
                  '因此还要补查对应条款，不能把日历上的生克关系直接翻成“这天最好”。', '',
                  '出处：' + result['evidence']['principle'][0]['source_url'], '',
                  '下一步需核对：' + result['research']['missing'] + '。'])
    return '\n'.join(lines)


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
