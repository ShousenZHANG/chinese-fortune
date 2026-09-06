"""Synthetic protocol fixtures test auditing; they are not actual model readings."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('trace_audit', ROOT / 'evals/audit_model_trace.py')
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def token_values(input_tokens, cached, output, reasoning):
    return {'totalTokens': input_tokens + output, 'inputTokens': input_tokens,
            'cachedInputTokens': cached, 'cacheWriteInputTokens': 0,
            'outputTokens': output, 'reasoningOutputTokens': reasoning}


def fixture_trace():
    events = []

    def emit(method, **params):
        events.append((len(events) + 1, {'method': method, 'params': params}))

    emit('thread/started', thread={'id': 'thread', 'ephemeral': True})
    turns = []
    for index, totals in enumerate([(100, 60, 20, 5), (180, 100, 30, 8)], 1):
        turn_id = f'turn-{index}'
        emit('turn/started', threadId='thread', turn={'id': turn_id, 'status': 'inProgress'})
        output = {'ok': True, 'tool': 'request_time' if index == 1 else 'bazi_reading',
                  'context': {'request_time': {
                      'source': 'system_utc_clock' if index == 1 else 'provided_instant',
                      'utc': '2026-09-06T03:15:00+00:00',
                      'local': '2026-09-06T13:15:00+10:00', 'timezone': 'Australia/Sydney'}}}
        item = {'type': 'commandExecution', 'id': f'cmd-{index}',
                'command': f'python scripts/request_time.py --current-timezone Australia/Sydney {index}',
                'status': 'completed', 'exitCode': 0, 'aggregatedOutput': json.dumps(output)}
        emit('item/started', threadId='thread', turnId=turn_id,
             item={**item, 'status': 'inProgress'})
        emit('item/completed', threadId='thread', turnId=turn_id, item=item)
        usage = {'total': token_values(*totals),
                 'last': token_values(*(totals if index == 1 else (80, 40, 10, 3)))}
        emit('thread/tokenUsage/updated', threadId='thread', turnId=turn_id, tokenUsage=usage)
        emit('turn/completed', threadId='thread', turn={'id': turn_id, 'status': 'completed',
                                                       'items': [{'type': 'agentMessage'}]})
        turns.append({'thread_id': 'thread', 'turn_id': turn_id,
                      'tool_calls': [item], 'usage': usage})
    record = {'case_id': 'fixture', 'repetition': 1, 'exit_code': 0, 'turns': turns,
              'tool_calls': [item for turn in turns for item in turn['tool_calls']],
              'usage': usage}
    return record, events


def test_real_host_items_and_adjacent_turn_usage_are_distinct_from_cli_counts():
    record, events = fixture_trace()
    result = audit_module.audit(record, events)
    assert result['trace_status'] == 'consistent'
    assert result['host_items']['unique_tools'] == 2
    assert result['turn_usage'][0]['delta_from_previous_turn']['totalTokens'] == 120
    second = result['turn_usage'][1]
    assert second['last_total']['totalTokens'] == 210
    assert second['delta_from_previous_turn']['totalTokens'] == 90
    assert second['sum_notification_last']['reasoningOutputTokens'] == 3
    assert all(second['last_sum_matches_delta'].values())
    assert result['record_usage_matches_last_raw'] is True
    assert result['manual_precise_cli_counts'] is None and result['billing_cost'] is None
    assert len(result['manual_time_review']['checks']) == 4
    assert all(check['status'] == 'pending' for check in result['manual_time_review']['checks'])
    first_output = result['tools'][0]['output']
    assert first_output['tool_fields'] == [{'path': '$', 'tool': 'request_time'}]
    assert first_output['time_metadata'][0]['source'] == 'system_utc_clock'
    assert result['tools'][1]['output']['time_metadata'][0]['source'] == 'provided_instant'


def test_modified_record_omitted_tool_and_wrong_turn_identity_are_reported():
    for mutation in ('changed_payload', 'omitted', 'wrong_turn', 'duplicate'):
        record, events = fixture_trace()
        if mutation == 'changed_payload':
            record = deepcopy(record)
            record['turns'][0]['tool_calls'][0]['command'] = 'different command'
        elif mutation == 'omitted':
            record['turns'][0]['tool_calls'] = []
        elif mutation == 'wrong_turn':
            record['turns'][0]['turn_id'] = 'wrong-turn'
        else:
            record['turns'][0]['tool_calls'] *= 2
        result = audit_module.audit(record, events)
        assert result['trace_status'] == 'issues_found', mutation
        assert any('tool' in finding['kind'] for finding in result['findings']), mutation


@pytest.mark.parametrize('reorder_turn', [False, True])
def test_reordered_tools_fail_even_when_top_and_turn_lists_are_reordered_together(reorder_turn):
    original, _ = fixture_trace()
    tools = deepcopy(original['tool_calls'])
    record = {'turns': [{'thread_id': 'thread', 'turn_id': 'turn', 'tool_calls': tools[:]}],
              'tool_calls': tools[:], 'usage': None}
    events = []
    for item in tools:
        for method in ('item/started', 'item/completed'):
            events.append((len(events) + 1, {'method': method, 'params': {
                'threadId': 'thread', 'turnId': 'turn', 'item': item}}))
    assert audit_module.audit(record, events)['trace_status'] == 'consistent'
    record['tool_calls'].reverse()
    if reorder_turn:
        record['turns'][0]['tool_calls'].reverse()
    result = audit_module.audit(record, events)
    kinds = {finding['kind'] for finding in result['findings']}
    expected = ('record_tool_order_differs_from_events' if reorder_turn
                else 'top_tool_list_differs_from_turns')
    assert expected in kinds
    assert result['trace_status'] == 'issues_found'


def test_unfinished_and_duplicate_host_items_cannot_silently_disappear():
    record, events = fixture_trace()
    events.extend([(100, {'method': 'item/started', 'params': {
        'threadId': 'thread', 'turnId': 'turn-2',
        'item': {'id': 'unfinished', 'type': 'commandExecution'}}}), events[3]])
    result = audit_module.audit(record, events)
    kinds = {finding['kind'] for finding in result['findings']}
    assert 'started_without_completion' in kinds
    assert 'duplicate_item_completion' in kinds
    assert result['host_items']['unique_tools'] == 2


def test_missing_usage_and_absent_fresh_thread_proof_remain_unknown():
    record, events = fixture_trace()
    events = [(line, event) for line, event in events
              if event['method'] != 'thread/started'
              and not (event['method'] == 'thread/tokenUsage/updated'
                       and event['params']['turnId'] == 'turn-1')]
    result = audit_module.audit(record, events)
    assert all(value is None for value in result['turn_usage'][0]['last_total'].values())
    assert all(value is None for value in result['turn_usage'][1]['delta_from_previous_turn'].values())
    assert all(value is None for value in result['turn_usage'][1]['last_sum_matches_delta'].values())


def test_partial_fields_duplicate_notifications_and_arithmetic_are_not_hidden():
    record, events = fixture_trace()
    events = deepcopy(events)
    second_usage = next(event['params']['tokenUsage'] for _, event in events
                        if event['method'] == 'thread/tokenUsage/updated'
                        and event['params']['turnId'] == 'turn-2')
    del second_usage['total']['cachedInputTokens']
    second_usage['total']['totalTokens'] += 1
    events.append((100, {'method': 'thread/tokenUsage/updated', 'params': {
        'threadId': 'thread', 'turnId': 'turn-2', 'tokenUsage': deepcopy(second_usage)}}))
    result = audit_module.audit(record, events)
    second = result['turn_usage'][1]
    assert second['last_total']['cachedInputTokens'] is None
    assert second['last_sum_matches_delta']['cachedInputTokens'] is None
    kinds = {finding['kind'] for finding in result['findings']}
    assert {'duplicate_usage_notification', 'total_usage_arithmetic_differs',
            'last_usage_sum_differs_from_turn_delta',
            'record_usage_differs_from_last_raw_notification'} <= kinds


def test_commands_preserve_evidence_without_treating_mentions_or_loops_as_counts():
    item = {'type': 'commandExecution', 'id': 'nested',
            'command': "Get-Content scripts/bazi_reading.py; python scripts/request_time.py --help; "
                       "subprocess.run(['python', 'scripts/bazi_reading.py']) for x in ids",
            'aggregatedOutput': '{"tool":"request_time","source":"provided_instant"}\ntruncated'}
    result = audit_module._tool_evidence(('thread', 'turn', 'nested'), 42, item)
    assert result['event_line'] == 42 and result['command'] == item['command']
    hints = result['command_hints']
    assert hints['script_mentions'] == ['bazi_reading.py', 'request_time.py']
    assert hints['help_flag_seen'] and hints['read_syntax_seen']
    assert hints['dynamic_process_syntax_seen'] and hints['precise_cli_count'] is None
    assert result['output']['json_status'] == 'not_complete_json'
    assert result['output']['time_metadata'] == []


def test_cli_writes_new_external_audit_and_rejects_overwrite_or_repo_output(tmp_path):
    record, events = fixture_trace()
    record_path, events_path = tmp_path / 'record.json', tmp_path / 'events.jsonl'
    record_path.write_text(json.dumps(record), encoding='utf-8')
    events_path.write_text('\n'.join(json.dumps(event) for _, event in events), encoding='utf-8')
    output = tmp_path / 'audit.json'
    args = ['--record', str(record_path), '--events', str(events_path), '--output', str(output)]
    assert audit_module.main(args) == 0
    result = json.loads(output.read_text(encoding='utf-8'))
    assert result['inputs']['record']['path'] == str(record_path.resolve())
    assert len(result['inputs']['events']['sha256']) == 64
    original = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        audit_module.main(args)
    assert error.value.code == 2 and output.read_bytes() == original
    with pytest.raises(SystemExit):
        audit_module.main([*args[:-1], str(ROOT / 'must-not-write-audit.json')])
    assert not (ROOT / 'must-not-write-audit.json').exists()


def test_incomplete_raw_json_is_recorded_as_a_trace_finding(tmp_path):
    record, events = fixture_trace()
    record_path, events_path = tmp_path / 'record.json', tmp_path / 'events.jsonl'
    record_path.write_text(json.dumps(record), encoding='utf-8')
    lines = [json.dumps(event) for _, event in events]
    events_path.write_text('\n'.join([*lines, '{"method":']), encoding='utf-8')
    result = audit_module.audit_paths(record_path, events_path)
    assert result['trace_status'] == 'issues_found'
    assert result['findings'][-1] == {'kind': 'malformed_event_line', 'line': len(lines) + 1}


def test_web_item_and_non_object_record_handling(tmp_path):
    item = {'type': 'webSearch', 'id': 'web', 'action': {'type': 'openPage', 'url': 'https://example.com'}}
    result = audit_module._tool_evidence(('thread', 'turn', 'web'), 1, item)
    assert result['action'] == item['action'] and 'command_hints' not in result
    path = tmp_path / 'array.json'
    path.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='object'):
        audit_module.audit_paths(path, path)
