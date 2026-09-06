"""Record fresh host sessions against a fixed snapshot; never manufacture reviews.

Use an explicitly supplied Codex CLI and Python environment. Each case/repetition
gets a new ephemeral session. Raw events and first failures are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class AppServer:
    """Capture stdio JSON-RPC; one ephemeral session supports real follow-ups."""

    def __init__(self, command: list[str], cwd: Path, folder: Path, timeout: float) -> None:
        self.timeout, self.counter = timeout, 0
        self.pending: list[dict] = []
        self.events: queue.Queue = queue.Queue()
        self.raw = (folder / 'events.jsonl').open('w', encoding='utf-8')
        self.sent = (folder / 'requests.jsonl').open('w', encoding='utf-8')
        self.stderr = (folder / 'stderr.txt').open('w', encoding='utf-8')
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONTZPATH': ''}
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr, text=True,
                                        encoding='utf-8', errors='replace', bufsize=1, creationflags=flags)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                self.raw.write(line)
                self.raw.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    event = {'transport_error': 'non-JSON stdout'}
                self.events.put(event)
        finally:
            self.events.put(None)

    def send(self, value: dict) -> None:
        assert self.process.stdin is not None
        line = json.dumps(value, ensure_ascii=False) + '\n'
        self.sent.write(line)
        self.sent.flush()
        self.process.stdin.write(line)
        self.process.stdin.flush()

    def _next(self, deadline: float) -> dict:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('app-server timed out')
        try:
            event = self.events.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError('app-server timed out') from exc
        if event is None:
            raise RuntimeError('app-server closed stdout before completion')
        if event.get('transport_error'):
            raise RuntimeError(event['transport_error'])
        if 'method' in event and 'id' in event:
            self.send({'id': event['id'], 'error': {'code': -32601, 'message': 'No interactive approval/input adapter in frozen evaluation'}})
            raise RuntimeError('unexpected server request: ' + event['method'])
        return event

    def request(self, method: str, params: dict) -> dict:
        self.counter += 1
        identifier = self.counter
        self.send({'id': identifier, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while True:
            event = self._next(deadline)
            if event.get('id') == identifier:
                if 'error' in event:
                    raise RuntimeError(method + ': ' + json.dumps(event['error'], ensure_ascii=False))
                return event['result']
            self.pending.append(event)

    def completed_turn(self, thread_id: str, turn_id: str) -> dict:
        items: dict[str, dict] = {}
        usage = None
        deadline = time.monotonic() + self.timeout
        while True:
            event = self.pending.pop(0) if self.pending else self._next(deadline)
            params = event.get('params', {})
            if params.get('threadId') != thread_id:
                continue
            if event.get('method') == 'item/completed' and params.get('turnId') == turn_id:
                item = params['item']
                items[item['id']] = item
            elif event.get('method') == 'thread/tokenUsage/updated' and params.get('turnId') == turn_id:
                usage = params['tokenUsage']
            elif event.get('method') == 'turn/completed' and params.get('turn', {}).get('id') == turn_id:
                turn = params['turn']
                for item in turn.get('items', []):
                    items[item['id']] = item
                messages = [i for i in items.values() if i.get('type') == 'agentMessage']
                final = [i for i in messages if i.get('phase') == 'final_answer']
                chosen = final or messages[-1:]
                return {'thread_id': thread_id, 'turn_id': turn_id, 'status': turn['status'],
                        'text': '\n\n'.join(i.get('text', '') for i in chosen),
                        'assistant_messages': messages, 'usage': usage, 'error': turn.get('error'),
                        'tool_calls': [i for i in items.values() if i.get('type') not in {'agentMessage', 'reasoning', 'userMessage'}]}

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.reader.join(timeout=5)
        for handle in (self.raw, self.sent, self.stderr, self.process.stdout):
            if handle:
                handle.close()


def digest_snapshot(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(p in {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'} for p in path.relative_to(root).parts):
            continue
        digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def record_case(args: argparse.Namespace, case: dict, repetition: int) -> dict:
    folder = args.output / f"{case['id']}-run{repetition}"
    folder.mkdir(parents=True, exist_ok=False)
    requests = case.get('turns', [{'prompt': case['prompt']}])
    (folder / 'inputs.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2), encoding='utf-8')
    developer = (
        'Perform the actual user skill request. Apply SKILL.md from the current working directory, '
        'not a globally installed copy. Use tools required by that skill and answer naturally in Chinese. '
        'Use this Python executable for project scripts: ' + str(args.python) + '. '
        'Do not edit files, publish, read personal memories, inspect other snapshots or evaluation records, '
        'or delegate to other agents/threads. Ask necessary questions in your final answer as ordinary text, '
        'not interactive input/approval tools. A follow-up may arrive after your answer. '
        'Keep explicit replay instants distinct from live clock samples. Give the user answer, not a test report.'
    )
    start = time.monotonic()
    server = None
    turns = []
    host = None
    failure = None
    try:
        server = AppServer([str(args.cli), 'app-server', '--stdio'], args.snapshot, folder, args.timeout)
        initialization = server.request('initialize', {
            'clientInfo': {'name': 'fortune_eval', 'title': 'Frozen skill comparison', 'version': '1.0'},
            'capabilities': {'experimentalApi': True}})
        server.send({'method': 'initialized', 'params': {}})
        host = server.request('thread/start', {
            'model': args.model, 'allowProviderModelFallback': False,
            'cwd': str(args.snapshot), 'ephemeral': True, 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'developerInstructions': developer,
            'config': {'model_reasoning_effort': args.effort}})
        (folder / 'host.json').write_text(json.dumps({'initialize': initialization, 'thread_start': host},
                                                   ensure_ascii=False, indent=2), encoding='utf-8')
        if host['model'] != args.model or host.get('reasoningEffort') != args.effort:
            raise RuntimeError('observed model/effort differs from requested configuration')
        if host['thread'].get('ephemeral') is not True or host.get('sandbox', {}).get('type') != 'readOnly':
            raise RuntimeError('host did not establish an ephemeral read-only thread')
        thread_id = host['thread']['id']
        for index, request in enumerate(requests, 1):
            result = server.request('turn/start', {
                'threadId': thread_id, 'model': args.model, 'effort': args.effort,
                'input': [{'type': 'text', 'text': request['prompt']}]})
            turn = server.completed_turn(thread_id, result['turn']['id'])
            turn.update(index=index, prompt=request['prompt'])
            turns.append(turn)
            (folder / f'turn-{index}.json').write_text(json.dumps(turn, ensure_ascii=False, indent=2), encoding='utf-8')
            (folder / f'answer-{index}.txt').write_text(turn['text'], encoding='utf-8')
            if turn['status'] != 'completed' or not turn['text'].strip():
                raise RuntimeError('turn ended without a completed answer: ' + turn['status'])
    except (OSError, ValueError, KeyError, RuntimeError, TimeoutError) as exc:
        failure = str(exc)
    finally:
        if server:
            try:
                server.close()
            except OSError as exc:
                failure = (failure + '; ' if failure else '') + 'transport shutdown: ' + str(exc)
    answer = '\n\n'.join(f"[第{turn['index']}轮回答]\n{turn['text']}" for turn in turns)
    tool_calls = [item for turn in turns for item in turn['tool_calls']]
    value = {'case_id': case['id'], 'repetition': repetition, 'text': answer, 'turns': turns,
             'tool_calls': tool_calls,
             'exit_code': int(failure is not None), 'execution_error': failure,
             'usage': turns[-1]['usage'] if turns else None,
             'measurements': {
                 'user_input_utf8_bytes': sum(len(request['prompt'].encode('utf-8')) for request in requests),
                 'developer_input_utf8_bytes': len(developer.encode('utf-8')),
                 'answer_utf8_bytes': sum(len(turn['text'].encode('utf-8')) for turn in turns),
                 'serialized_tool_trace_utf8_bytes': len(json.dumps(tool_calls, ensure_ascii=False).encode('utf-8')),
                 'tool_call_count': len(tool_calls),
                 'usage_source': 'app-server thread/tokenUsage/updated; final cumulative total',
                 'tokenizer': 'not disclosed by host',
                 'byte_scope': 'authored prompts and serialized tool trace; excludes hidden host instructions'},
             'elapsed_seconds': round(time.monotonic() - start, 3), 'host': host,
             'raw_events': str(folder / 'events.jsonl'), 'review': None}
    (folder / 'record.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return value

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--model-label', help='Display label; actual configuration is checked independently')
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--effort', default='ultra')
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--case-id', action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    args.snapshot, args.output = args.snapshot.resolve(), args.output.resolve()
    if args.output.is_relative_to(args.snapshot):
        parser.error('recordings must be outside the tested snapshot')
    if args.repetitions < 1 or args.workers < 1:
        parser.error('repetitions/workers must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(args.cases.read_text(encoding='utf-8'))
    cases = [case for case in spec['cases'] if not args.case_id or case['id'] in args.case_id]
    if not cases:
        parser.error('no selected cases')
    before = digest_snapshot(args.snapshot)
    metadata = {'schema_version': '2.0', 'model': args.model, 'reasoning_effort': args.effort, 'commit': args.commit,
                'snapshot_sha256': before, 'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                'cli': str(args.cli), 'python': str(args.python), 'repetitions': args.repetitions,
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'execution': 'app-server stdio; ephemeral read-only thread per case/repetition; sequential real turns; no semantic review yet'}
    (args.output / 'run.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    failures = 0
    responses: dict[int, list] = {rep: [] for rep in range(1, args.repetitions + 1)}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(record_case, args, case, rep)
                   for rep in range(1, args.repetitions + 1) for case in cases]
        for future in as_completed(futures):
            result = future.result()
            responses[result['repetition']].append(result)
            failures += result['exit_code'] != 0 or not result['text']
            print(json.dumps({k: result[k] for k in ('case_id', 'repetition', 'exit_code', 'elapsed_seconds', 'execution_error', 'usage')}, ensure_ascii=False), flush=True)
            recording = {'schema_version': '2.0', 'model': args.model, 'prompt_version': metadata['cases_sha256'],
                         'commit': args.commit, 'responses': sorted(responses[result['repetition']], key=lambda row: row['case_id'])}
            (args.output / f"recording-run{result['repetition']}.json").write_text(
                json.dumps(recording, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    after = digest_snapshot(args.snapshot)
    metadata.update(snapshot_unchanged=before == after, snapshot_after_sha256=after,
                    execution_failures=failures)
    (args.output / 'run.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return int(bool(failures) or before != after)


if __name__ == '__main__':
    raise SystemExit(main())
