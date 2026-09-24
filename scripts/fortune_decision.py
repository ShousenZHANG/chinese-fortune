"""Request routing and practical choices, separate from traditional interpretation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

INTENTS = {'period', 'selection', 'natal', 'event', 'research'}


def route_request(payload: dict, capability: dict) -> dict:
    intent = payload.get('intent')
    if intent is not None and intent not in INTENTS:
        raise ValueError('intent 必须为 period/selection/natal/event/research')
    question = payload.get('question', '')
    if not isinstance(question, str) or len(question) > 2000:
        raise ValueError('question 必须为不超过 2000 字符的文本')
    result = dict(capability)
    if intent == 'event' and 'candidates' in payload:
        result['route'] = 'selection'
    elif intent:
        result['route'] = 'selection' if intent == 'selection' else 'period'
    elif result.get('custom'):
        result['route'] = 'selection' if 'candidates' in payload else 'period'
    result['intent'] = intent or result['route']
    return result


def choose_practical(result: dict, preferences: dict | None) -> dict:
    """Return a dated arrangement only from feasible windows and explicit priorities.

    Exclusion screening does not establish equal personal auspiciousness. With no
    preference, several feasible alternatives remain unordered. Equal instants
    are not broken by input order.
    """
    preferences = {} if preferences is None else preferences
    if not isinstance(preferences, dict) or set(preferences) - {'prefer', 'candidate_order'}:
        raise ValueError('preferences 只接受 prefer 或 candidate_order')
    prefer = preferences.get('prefer')
    order = preferences.get('candidate_order')
    if prefer is not None and prefer not in ('earliest', 'latest'):
        raise ValueError('prefer 必须为 earliest/latest')
    if prefer is not None and order is not None:
        raise ValueError('请只指定一种实际选择优先条件')
    comparison = result.get('practical_comparison', result.get('candidate_comparison', []))
    ids = {c['candidate_id'] for c in comparison}
    if order is not None and (not isinstance(order, list) or not order or
            any(not isinstance(k, str) or k not in ids for k in order) or len(set(order)) != len(order)):
        raise ValueError('candidate_order 必须为不重复的现有候选 id 列表')
    base = {'status': 'no_practical_choice', 'first_choice': None, 'backup': None,
            'basis': 'practical_constraints', 'personal_auspicious_ranking': False}
    if result['priority'] is None:
        return {**base, 'status': 'participant_priority_required'}
    ranking = result.get('practical_screening', result.get('ranking', {}))
    excluded = {(e['candidate_id'], e['start'], e['end']) for e in ranking.get('excluded', [])}
    cautions = {(e['candidate_id'], e['start'], e['end']) for e in ranking.get('tiers', [])
                if e.get('forbidden_hours_in_window') or e.get('unresolved_hour_rules')}
    windows = []
    for candidate in comparison:
        for window in candidate['windows']:
            key = (candidate['candidate_id'], window['start'], window['end'])
            if key in excluded:
                continue
            edge = 'latest' if prefer == 'latest' else 'earliest'
            start = datetime.fromisoformat(window['allowed_start'][edge])
            end = (start.astimezone(UTC) + timedelta(minutes=candidate['duration_minutes'])).astimezone(ZoneInfo(result['window']['timezone']))
            windows.append({'candidate_id': candidate['candidate_id'], 'start': start.isoformat(),
                            'end': end.isoformat(), 'timezone': result['window']['timezone'],
                            'start_is_practical_boundary': True})
    if not windows:
        return {**base, 'status': 'clause_conflict' if cautions else 'no_practical_choice'}
    if order is not None:
        windows = [w for w in windows if w['candidate_id'] in order]
        windows.sort(key=lambda w: (order.index(w['candidate_id']), datetime.fromisoformat(w['start']).astimezone(UTC)))
        reason = '按你指定的候选优先顺序，选择能容纳完整事件的时间'
    elif prefer:
        windows.sort(key=lambda w: datetime.fromisoformat(w['start']).astimezone(UTC), reverse=prefer == 'latest')
        reason = '按你希望' + ('尽早' if prefer == 'earliest' else '尽晚') + '安排的条件选择'
        if len(windows) > 1 and datetime.fromisoformat(windows[0]['start']) == datetime.fromisoformat(windows[1]['start']):
            return {**base, 'status': 'practical_tie', 'alternatives': windows}
    elif len(windows) == 1:
        reason = ('这是目前唯一能容纳完整事件、且未被已查条款排除的窗口' if ranking else
                  '这是你提供的档期中唯一能容纳完整事件的窗口')
    else:
        return {**base, 'status': 'preferences_required', 'alternatives': windows}
    if not windows:
        return base
    first = windows[0]
    backup = next((w for w in windows[1:] if w['candidate_id'] != first['candidate_id']), None)
    checked = []
    if ranking:
        from fortune_ranking import rank_candidates
        from fortune_selection import compare_candidates
        for option in (first, backup):
            if option is None:
                continue
            start, end = (datetime.fromisoformat(option[k]).astimezone(UTC) for k in ('start', 'end'))
            exact = compare_candidates([{'id': option['candidate_id'], 'available': True, 'reason': None,
                                        'intervals': [{'start': option['start'], 'end': option['end']}]}],
                                       result['participants'], duration_minutes=int((end - start).total_seconds() / 60),
                                       timezone=result['window']['timezone'])
            screen = rank_candidates(exact, result['participants'][0], scenario=result['capability']['scenario'])
            checked.append(screen)
            if screen['excluded'] or screen['unrankable'] or any(
                    r['forbidden_hours_in_window'] or r['unresolved_hour_rules'] for r in screen['tiers']):
                if option is first:
                    return {**base, 'status': 'clause_conflict', 'checked_options': checked}
                backup = None
    return {**base, 'status': 'practical_choice', 'first_choice': first, 'backup': backup, 'reason': reason,
            'checked_options': checked,
            'scope': '具体分钟来自可用档期与实际偏好；现有古法未完成个人吉凶排序。'}


def conclusion_packet(result: dict) -> dict:
    """One shared evidence state for the host and deterministic renderer."""
    observations = [o for p in result['participants'] for o in p['traditional_observations']]
    return {'schema_version': '1.0', 'question': result.get('question', ''),
            'status': result['recommendation']['status'],
            'personal_facts_used': [p['id'] for p in result['participants']],
            'traditional_personal_ranking': 'not_established',
            'interpretation_contract': {
                'method_selection': 'fix_before_interpretation',
                'claim_requirements': ['actual_personal_fields', 'source_conditions',
                                       'exceptions_checked', 'matching_time_scope'],
                'unresolved_conflict': 'state_conflict_do_not_vote_or_recast',
                'certainty_scope': 'supported_conclusion_not_guaranteed_event',
                'validation_record': 'explicit_consent_external_prediction_log'},
            'calendar_screening_scope': result.get('ranking', {}).get('rule_scope'),
            'traditional_observations': observations,
            'practical_choice': result.get('practical_choice'),
            'conditions': result['decision_blockers'],
            'research': {'status': 'not_started', 'budget_seconds': 300,
                         'first_response': 'answer_supported_parts_before_research'},
            'output': {'target_characters': [300, 600], 'register': '自然、直白的日常中文',
                       'order': ['本题结果', '必要短引文', '紧跟白话原义与个人对应', '实际影响结论的分歧']}}
