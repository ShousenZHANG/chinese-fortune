"""Record Claude Code answers to the v5.6 cases in a clean environment; never grade them.

Each case is a fresh headless session (``claude -p``) in a workspace whose only
customisation is the skill under ``.claude/skills/``: ``--setting-sources
project`` drops the user's CLAUDE.md, hooks and plugins, ``--strict-mcp-config``
drops connectors. Later turns of a case resume the same session. Every attempt,
raw event stream and failure is kept; an overloaded API is retried after a
pause, and the failed attempt stays on record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ALLOWED = ['Bash', 'Read', 'Glob', 'Grep', 'Skill']
DENIED = ['Write', 'Edit', 'NotebookEdit', 'WebFetch', 'WebSearch']
RETRY_WAITS = (60, 180, 420)
# An account usage limit stops the run: later cases would only record the same refusal.
STOP = threading.Event()
LIMIT_WORDS = ('session limit', 'usage limit', 'hit your limit')


def _command(prompt: str, model: str, session: str | None) -> list[str]:
    command = ['claude', '-p', prompt, '--output-format', 'stream-json', '--verbose', '--model', model,
               '--setting-sources', 'project', '--strict-mcp-config', '--max-turns', '40',
               '--allowedTools', *ALLOWED, '--disallowedTools', *DENIED]
    return command + (['--resume', session] if session else [])


def _parse(lines: list[str]) -> dict:
    """The facts of one turn from its event stream."""
    turn: dict = {'model': None, 'tools': [], 'result': None, 'session_id': None, 'retries': 0}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind, sub = event.get('type'), event.get('subtype')
        if kind == 'system' and sub == 'init':
            turn['model'], turn['session_id'] = event.get('model'), event.get('session_id')
            turn['skills'] = event.get('skills', [])
        elif kind == 'system' and sub == 'api_retry':
            turn['retries'] += 1
        elif kind == 'assistant':
            for block in event['message'].get('content', []):
                if block.get('type') == 'tool_use':
                    tool_input = block.get('input', {})
                    turn['tools'].append({'name': block.get('name'),
                                          'command': tool_input.get('command') or tool_input.get('skill')
                                          or tool_input.get('file_path') or tool_input.get('pattern')})
        elif kind == 'result':
            turn['result'] = {k: event.get(k) for k in ('subtype', 'is_error', 'result', 'total_cost_usd',
                                                         'num_turns', 'duration_ms', 'usage', 'session_id')}
            turn['session_id'] = event.get('session_id') or turn['session_id']
    return turn


def _overloaded(turn: dict) -> bool:
    result = turn.get('result') or {}
    return bool(result.get('is_error')) and any(w in (result.get('result') or '') for w in ('529', 'Overloaded', 'overloaded'))


def _limited(turn: dict) -> bool:
    text = ((turn.get('result') or {}).get('result') or '').lower()
    return bool((turn.get('result') or {}).get('is_error')) and any(w in text for w in LIMIT_WORDS)


def run_case(case: dict, workspace: Path, out: Path, model: str, timeout: int) -> dict:
    folder = out / case['id']
    if STOP.is_set():
        return {'id': case['id'], 'turns': [], 'attempts': [], 'complete': False, 'skipped': 'usage_limit'}
    folder.mkdir(parents=True)
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'CHINESE_FORTUNE_DATA_DIR': str(out.parent / 'profiles')}
    record: dict = {'id': case['id'], 'turns': [], 'attempts': []}
    session = None
    for index, prompt in enumerate(case['turns'], 1):
        for attempt, wait in enumerate((0, *RETRY_WAITS), 1):
            time.sleep(wait)
            path = folder / f'turn-{index}-attempt-{attempt}.jsonl'
            started = time.time()
            try:
                done = subprocess.run(_command(prompt, model, session), cwd=workspace, env=env, capture_output=True,
                                      text=True, encoding='utf-8', errors='replace', timeout=timeout)
                stdout, code = done.stdout, done.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b'').decode('utf-8', 'replace')
                code = 'timeout'
            path.write_text(stdout, encoding='utf-8')
            turn = _parse(stdout.splitlines())
            turn.update(turn=index, attempt=attempt, exit=code, seconds=round(time.time() - started, 1),
                        raw=path.name, raw_sha256=hashlib.sha256(stdout.encode('utf-8')).hexdigest())
            record['attempts'].append(turn)
            if _limited(turn):
                STOP.set()
                break
            if not _overloaded(turn) and code != 'timeout':
                break
        record['turns'].append(turn)
        answer = (turn.get('result') or {}).get('result') or ''
        (folder / f'answer-{index}.txt').write_text(answer, encoding='utf-8')
        session = turn.get('session_id')
        if not answer or (turn.get('result') or {}).get('is_error'):
            break
    record['complete'] = len(record['turns']) == len(case['turns']) and all(
        (t.get('result') or {}).get('subtype') == 'success' and not (t.get('result') or {}).get('is_error')
        for t in record['turns'])
    (folder / 'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True, help='目录内只有 .claude/skills/chinese-fortune')
    parser.add_argument('--out', type=Path, required=True, help='新的运行目录，不能已存在')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--parallel', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=1500)
    parser.add_argument('--only', nargs='*', help='只跑这些 case id')
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f'{args.out} 已存在：不覆盖旧记录')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))['cases']
    if args.only:
        cases = [c for c in cases if c['id'] in args.only]
    skill = args.workspace / '.claude' / 'skills' / 'chinese-fortune'
    release = json.loads((skill / 'RELEASE.json').read_text(encoding='utf-8'))
    args.out.mkdir(parents=True)
    (args.out.parent / 'profiles').mkdir(exist_ok=True)
    run = {'started': datetime.now(UTC).isoformat(), 'model_requested': args.model,
           'skill_version': release.get('version'), 'skill_commit': (release.get('build') or {}).get('commit'),
           'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
           'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'flags': _command('<prompt>', args.model, None)[3:], 'case_ids': [c['id'] for c in cases]}
    (args.out / 'run.json').write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding='utf-8')
    records = []
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(run_case, c, args.workspace, args.out, args.model, args.timeout): c['id'] for c in cases}
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            cost = sum((t.get('result') or {}).get('total_cost_usd') or 0 for t in record['attempts'])
            state = 'ok' if record['complete'] else ('SKIPPED (usage limit)' if record.get('skipped') else 'INCOMPLETE')
            print(f"{record['id']}: {state}  ${cost:.2f}", flush=True)
    run['finished'] = datetime.now(UTC).isoformat()
    run['complete'] = sum(r['complete'] for r in records)
    run['stopped_by_usage_limit'] = STOP.is_set()
    (args.out / 'run.json').write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
