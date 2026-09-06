"""Audit recorded host events without grading the reading or inventing CLI counts.

Only complete JSON command output is inspected for visible time metadata. Shell
snippets and subprocess loops remain evidence for a human, not a parsed call graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NON_TOOLS = {'agentMessage', 'reasoning', 'userMessage'}
TOKEN_FIELDS = ('totalTokens', 'inputTokens', 'cachedInputTokens',
                'cacheWriteInputTokens', 'outputTokens', 'reasoningOutputTokens')
TIME_FIELDS = ('source', 'utc', 'local', 'timezone')


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _tokens(value: object) -> dict:
    data = value if isinstance(value, dict) else {}
    return {key: data[key] if type(data.get(key)) is int and data[key] >= 0 else None
            for key in TOKEN_FIELDS}


def _output_evidence(output: object) -> dict:
    evidence = {'json_status': 'missing', 'tool_fields': [], 'time_metadata': []}
    if not isinstance(output, str):
        return evidence
    evidence.update(character_count=len(output), sha256=hashlib.sha256(output.encode()).hexdigest())
    try:
        parsed = json.loads(output)
    except ValueError:
        evidence['json_status'] = 'not_complete_json'
        return evidence
    evidence['json_status'] = 'complete_json'

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            if 'tool' in value:
                evidence['tool_fields'].append({'path': path, 'tool': value['tool']})
            if ('utc' in value or 'local' in value
                    or value.get('source') in ('system_utc_clock', 'provided_instant')):
                evidence['time_metadata'].append(
                    {'path': path, **{key: value[key] for key in TIME_FIELDS if key in value}})
            for key, child in value.items():
                visit(child, f'{path}[{json.dumps(key, ensure_ascii=False)}]')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f'{path}[{index}]')

    visit(parsed, '$')
    return evidence


def _tool_evidence(key: tuple, line: int, item: dict) -> dict:
    evidence = {'thread_id': key[0], 'turn_id': key[1], 'item_id': key[2],
                'event_line': line, 'type': item.get('type'), 'status': item.get('status')}
    if item.get('type') == 'commandExecution':
        command = item.get('command')
        text = command if isinstance(command, str) else ''
        evidence.update(command=command, command_actions=item.get('commandActions'),
                        cwd=item.get('cwd'), exit_code=item.get('exitCode'),
                        output=_output_evidence(item.get('aggregatedOutput')),
                        command_hints={
                            'script_mentions': sorted(set(re.findall(r'[\w.-]+\.py\b', text))),
                            'help_flag_seen': bool(re.search(r'(?<!\w)--help\b', text)),
                            'read_syntax_seen': bool(re.search(
                                r'Get-Content|read_text\s*\(|read_bytes\s*\(', text, re.I)),
                            'dynamic_process_syntax_seen': bool(re.search(
                                r'\bsubprocess\b|\bPopen\b|\bStart-Process\b|os\.system', text)),
                            'precise_cli_count': None,
                            'note': 'Hints are mentions only; inspect the full command and output.'})
    else:
        evidence.update(action=item.get('action'), query=item.get('query'))
    return evidence


def audit(record: dict, events: list[tuple[int, dict]]) -> dict:
    """Compare recorded items with events and retain unknowns in usage accounting."""
    findings: list[dict] = []
    started: dict[tuple, list[int]] = {}
    completed: dict[tuple, list[tuple[int, dict]]] = {}
    usage_events: dict[tuple, list[tuple[int, dict]]] = {}
    turn_order: list[tuple] = []
    turn_status: dict[tuple, str] = {}
    fresh_threads: set[str] = set()

    def note(kind: str, **details: object) -> None:
        findings.append({'kind': kind, **details})

    for line, event in events:
        method, params = event.get('method'), event.get('params', {})
        if not isinstance(params, dict):
            note('invalid_event_params', line=line)
            continue
        if method == 'thread/started':
            thread = params.get('thread', {})
            if isinstance(thread, dict) and thread.get('ephemeral') is True and thread.get('id'):
                fresh_threads.add(thread['id'])
        turn = params.get('turn', {})
        turn_id = params.get('turnId') or (turn.get('id') if isinstance(turn, dict) else None)
        turn_key = (params.get('threadId'), turn_id)
        if all(isinstance(part, str) and part for part in turn_key):
            if turn_key not in turn_order:
                turn_order.append(turn_key)
            if method == 'turn/completed':
                turn_status[turn_key] = turn.get('status')
        if method in ('item/started', 'item/completed'):
            item = params.get('item', {})
            item_id = item.get('id') if isinstance(item, dict) else None
            key = (*turn_key, item_id)
            if not all(isinstance(part, str) and part for part in key):
                note('missing_item_identity', line=line)
                continue
            if method == 'item/started':
                started.setdefault(key, []).append(line)
            else:
                completed.setdefault(key, []).append((line, item))
        if method == 'thread/tokenUsage/updated':
            if not all(isinstance(part, str) and part for part in turn_key):
                note('missing_usage_identity', line=line)
                continue
            value = params.get('tokenUsage')
            usage_events.setdefault(turn_key, []).append(
                (line, value if isinstance(value, dict) else {}))

    for key in started.keys() | completed.keys():
        identity = dict(zip(('thread_id', 'turn_id', 'item_id'), key, strict=True))
        if key not in completed:
            note('started_without_completion', **identity, lines=started[key])
        elif key not in started:
            note('completed_without_start', **identity, lines=[r[0] for r in completed[key]])
        if len(started.get(key, [])) > 1:
            note('duplicate_item_start', **identity, lines=started[key])
        if len(completed.get(key, [])) > 1:
            note('duplicate_item_completion', **identity, lines=[r[0] for r in completed[key]])

    raw_tools = {key: rows[-1] for key, rows in completed.items()
                 if rows[-1][1].get('type') not in NON_TOOLS}
    recorded_tools: dict[tuple, dict] = {}
    flattened = []
    turns = record.get('turns', [])
    if not isinstance(turns, list):
        turns = []
        note('invalid_record_turns')
    for turn in turns:
        if not isinstance(turn, dict):
            note('invalid_record_turn')
            continue
        key = (turn.get('thread_id'), turn.get('turn_id'))
        if key not in turn_order:
            turn_order.append(key)
        tools = turn.get('tool_calls')
        if not isinstance(tools, list):
            note('missing_turn_tool_list', thread_id=key[0], turn_id=key[1])
            continue
        flattened.extend(tools)
        for item in tools:
            if not isinstance(item, dict) or not item.get('id'):
                note('invalid_record_tool', thread_id=key[0], turn_id=key[1])
                continue
            item_key = (*key, item['id'])
            if item_key in recorded_tools:
                note('duplicate_record_tool', identity=list(item_key))
            recorded_tools[item_key] = item
    for key in raw_tools.keys() | recorded_tools.keys():
        if key not in raw_tools:
            note('record_tool_missing_in_events', identity=list(key))
        elif key not in recorded_tools:
            note('event_tool_missing_in_record', identity=list(key), line=raw_tools[key][0])
        elif raw_tools[key][1] != recorded_tools[key]:
            note('record_tool_payload_differs', identity=list(key), line=raw_tools[key][0])
    raw_order = sorted(raw_tools, key=lambda key: raw_tools[key][0])
    if raw_tools.keys() == recorded_tools.keys() and raw_order != list(recorded_tools):
        note('record_tool_order_differs_from_events',
             event_order=[list(key) for key in raw_order],
             record_order=[list(key) for key in recorded_tools])
    top_tools = record.get('tool_calls')
    if not isinstance(top_tools, list):
        note('missing_record_tool_list')
    elif top_tools != flattened:
        note('top_tool_list_differs_from_turns')

    usage_rows = []
    previous: dict[str, dict] = {}
    latest_raw_usage = None
    latest_usage_line = -1
    for thread_id, turn_id in turn_order:
        rows = usage_events.get((thread_id, turn_id), [])
        final = rows[-1][1] if rows else {}
        total = _tokens(final.get('total'))
        baseline = previous.get(thread_id, _tokens(dict.fromkeys(TOKEN_FIELDS, 0))
                                if thread_id in fresh_threads else _tokens(None))
        delta = {key: total[key] - baseline[key]
                 if total[key] is not None and baseline[key] is not None else None
                 for key in TOKEN_FIELDS}
        for key, value in delta.items():
            if value is not None and value < 0:
                note('cumulative_usage_decreased', thread_id=thread_id, turn_id=turn_id, field=key)
                delta[key] = None
        previous[thread_id] = total
        last_values = [_tokens(value.get('last')) for _, value in rows]
        sums = {key: sum(value[key] for value in last_values)
                if last_values and all(value[key] is not None for value in last_values) else None
                for key in TOKEN_FIELDS}
        comparisons = {key: sums[key] == delta[key]
                       if sums[key] is not None and delta[key] is not None else None
                       for key in TOKEN_FIELDS}
        if any(value is False for value in comparisons.values()):
            note('last_usage_sum_differs_from_turn_delta', thread_id=thread_id, turn_id=turn_id)
        if all(total[key] is not None for key in ('totalTokens', 'inputTokens', 'outputTokens')):
            if total['totalTokens'] != total['inputTokens'] + total['outputTokens']:
                note('total_usage_arithmetic_differs', thread_id=thread_id, turn_id=turn_id)
        seen_usage: dict[str, int] = {}
        for line, value in rows:
            encoded = _canonical(value)
            if encoded in seen_usage:
                note('duplicate_usage_notification', line=line, previous_line=seen_usage[encoded])
            seen_usage[encoded] = line
        if rows and rows[-1][0] > latest_usage_line:
            latest_usage_line, latest_raw_usage = rows[-1]
        usage_rows.append({'thread_id': thread_id, 'turn_id': turn_id,
                           'raw_turn_status': turn_status.get((thread_id, turn_id)),
                           'event_lines': [line for line, _ in rows],
                           'last_total': total, 'delta_from_previous_turn': delta,
                           'sum_notification_last': sums, 'last_sum_matches_delta': comparisons})
    record_usage_match = (record.get('usage') == latest_raw_usage
                          if latest_raw_usage is not None else None)
    if record_usage_match is False:
        note('record_usage_differs_from_last_raw_notification')
    tools = [_tool_evidence(key, line, item)
             for key, (line, item) in sorted(raw_tools.items(), key=lambda row: row[1][0])]
    return {
        'schema_version': '1.0', 'case_id': record.get('case_id'),
        'repetition': record.get('repetition'), 'record_exit_code': record.get('exit_code'),
        'trace_status': 'issues_found' if findings else 'consistent', 'findings': findings,
        'host_items': {'unique_started': len(started), 'unique_completed': len(completed),
                       'unique_tools': len(tools),
                       'tools_by_type': dict(Counter(tool['type'] for tool in tools))},
        'tools': tools, 'turn_usage': usage_rows,
        'record_usage_matches_last_raw': record_usage_match,
        'manual_precise_cli_counts': None, 'billing_cost': None,
        'limitations': [
            'Trace consistency is not a semantic pass or a complete reading-quality review.',
            'Script mentions are not invocation counts; nested or dynamic commands need review.',
            'Missing usage fields are unknown. Cumulative totals must not be summed across notifications.',
            'Reasoning is reported separately, never added again to outputTokens or totalTokens.',
            'Cache usage and token counts do not establish exact billing or subscription usage.',
            'The first usage delta starts at zero only with an observed ephemeral thread/started event.',
        ],
        'manual_time_review': {'status': 'pending', 'checks': [
            {'id': 'real_clock_call', 'status': 'pending',
             'question': 'Was an actual clock sampled, and was its result used or only observed?'},
            {'id': 'provided_instant_honesty', 'status': 'pending',
             'question': 'Are injected instants described honestly as provided rather than live?'},
            {'id': 'case_utc_propagation', 'status': 'pending',
             'question': 'Did calculation commands preserve the case UTC instant and intended timezone?'},
            {'id': 'answer_time_claims', 'status': 'pending',
             'question': 'Does the actual answer misstate the source, timezone, date, or use of time?'},
        ]},
    }


def audit_paths(record_path: Path, events_path: Path) -> dict:
    record_bytes, event_bytes = record_path.read_bytes(), events_path.read_bytes()
    record = json.loads(record_bytes)
    if not isinstance(record, dict):
        raise ValueError('record must be a JSON object')
    events, malformed = [], []
    for line, content in enumerate(event_bytes.splitlines(), 1):
        try:
            event = json.loads(content)
            if not isinstance(event, dict):
                raise ValueError('event is not an object')
        except (ValueError, UnicodeDecodeError):
            malformed.append({'kind': 'malformed_event_line', 'line': line})
            continue
        events.append((line, event))
    result = audit(record, events)
    result['findings'].extend(malformed)
    if malformed:
        result['trace_status'] = 'issues_found'
    result['inputs'] = {
        name: {'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest(),
               'bytes': len(data)}
        for name, path, data in [('record', record_path, record_bytes),
                                 ('events', events_path, event_bytes)]}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New JSON file outside this repository; existing files are never replaced')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error('--output must be outside this repository')
    try:
        if output.exists():
            raise FileExistsError(f'refusing to overwrite: {output}')
        result = audit_paths(args.record, args.events)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(output), 'trace_status': result['trace_status'],
                      'manual_time_review': 'pending'}, ensure_ascii=False))
    return 1 if result['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
