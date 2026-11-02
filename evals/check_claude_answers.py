"""Mechanical checks of recorded answers against each call's admitted evidence.

Legacy command text supports literal direct Python invocations in POSIX shell
syntax, plus one stdout redirect. Recorded argv avoids shell interpretation.
Dynamic commands and wrappers remain unverified; this module never executes them.
"""

import argparse
import importlib
import json
import re
import shlex
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from answer_check import check_answer  # noqa: E402
from answer_evidence import PRODUCERS, parse_evidence

FACT_COMMANDS = {'bazi_reading': 'bazi_reading', 'bazi_calc': 'bazi', 'ziwei_calc': 'ziwei',
                 'fortune_reading': 'fortune_reading', 'pair_facts': 'pair_facts', 'liuyao_cast': 'liuyao'}
SOURCE_COMMANDS = {
    'classical_search': 'classical_search', 'classical_guidance': 'classical_guidance', 'life_guide': 'life_guide',
    'huangli_query': 'huangli', 'meihua_cast': 'meihua', 'qimen_cast': 'qimen', 'liuren_cast': 'daliuren',
    'yijing_cast': 'yijing', 'xiaoliuren_cast': 'xiaoliuren', 'tiaohou_provenance': 'tiaohou_provenance',
    'method_rules': 'method_rules', 'zodiac_compat': 'zodiac', 'name_analyze': 'name', 'lunar_convert': 'lunar_convert',
    'explore_cast': 'explore', 'tarot_draw': 'tarot', 'jiemeng_lookup': 'jiemeng', 'reading_support': 'reading_review',
    'fortune_rules': 'fortune_rules', 'fengshui_measure': 'fengshui_measure', 'qimen_select': 'qimen_select',
    'birth_candidates': 'birth_candidates', 'birth_correction': 'birth_correction', 'pillars_to_dates': 'pillars_to_dates',
}
COMMANDS = {**FACT_COMMANDS, **SOURCE_COMMANDS}
LINE_NUMBER = re.compile(r'^\s*\d+(?:\t|→)', re.M)
PYTHON = re.compile(r'(?:python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?$', re.I)
READ_MODES = frozenset(('rules', 'lookup', 'read', 'info'))


@dataclass(frozen=True)
class Invocation:
    argv: tuple[str, ...]
    script: str
    producer: str
    options: tuple[tuple[str, Union[str, bool]], ...]
    subcommand: Optional[str]
    saved_paths: tuple[str, ...]

    @property
    def prose(self) -> bool:
        return any(key in ('-h', '--help', '--markdown') for key, _ in self.options)

    @property
    def chart(self) -> bool:
        return self.script in FACT_COMMANDS and self.subcommand not in READ_MODES and not self.prose

    def has_flag(self, flag: str) -> bool:
        return (not any(key in ('-h', '--help') for key, _ in self.options)
                and self.subcommand not in READ_MODES
                and any(key == flag and value is not False for key, value in self.options))


@dataclass(frozen=True)
class RecordedCall:
    command: str
    invocation: Optional[Invocation]
    outputs: tuple[object, ...]
    requires_chart: bool
    chart_recorded: bool


@cache
def _recorded_invocation_parser(script: str) -> argparse.ArgumentParser:
    if script in ('fortune_reading', 'pair_facts'):
        parser = argparse.ArgumentParser(add_help=True)
        parser.add_argument('--stdin', action='store_true')
        if script == 'fortune_reading':
            parser.add_argument('--markdown', action='store_true')
            parser.add_argument('--detail', action='store_true')
            parser.add_argument('--data-dir')
            parser.add_argument('--facts-out')
        return parser
    if script == 'classical_search':
        parser = argparse.ArgumentParser(add_help=True)
        for flag in ('query', 'climate-key', 'passage-id', 'chapter-id', 'book', 'chapter', 'limit', 'offset'):
            parser.add_argument('--' + flag)
        for flag in ('validate', 'list-books'):
            parser.add_argument('--' + flag, action='store_true')
        parser.add_argument('--witnesses', nargs='?')
        return parser
    main_options = {
        'classical_guidance': (('scenario', 'family', 'limit'), ('audit', 'list', 'retrieve')),
        'tiaohou_provenance': (('key',), ('audit',)),
        'method_rules': (('method', 'rule', 'chart', 'applications'), ('audit',)),
        'fortune_rules': (('scenario',), ('capabilities', 'evidence', 'capabilities-markdown')),
        'reading_support': (('chart', 'packet'), ('stdin', 'markdown')),
    }
    if script in main_options:
        parser = argparse.ArgumentParser(add_help=True)
        valued, switches = main_options[script]
        for flag in valued:
            parser.add_argument('--' + flag)
        for flag in switches:
            parser.add_argument('--' + flag, action='store_true')
        return parser
    module = importlib.import_module(script)
    factory = getattr(module, 'build_parser', None) or getattr(module, '_parser', None)
    if factory is None:
        raise ValueError(f'No recorded invocation schema for {script}')
    return factory()


def _tokens(tool: dict) -> tuple[tuple[str, ...], Optional[str]]:
    raw = tool.get('argv', tool.get('command'))
    if isinstance(raw, list) and all(isinstance(arg, str) for arg in raw):
        return tuple(raw), None
    if not isinstance(raw, str):
        return (), 'command must be literal text or an argv list'
    if tool.get('shell', 'posix') not in ('posix', 'bash', 'sh'):
        return (), 'legacy command requires a supported POSIX shell dialect'
    try:
        lexer = shlex.shlex(raw, posix=True, punctuation_chars=';&|<>')
        lexer.whitespace_split = True
        lexer.commenters = ''
        args = tuple(lexer)
    except ValueError as exc:
        return (), str(exc)
    if any(token in (';', '&', '&&', '|', '||', '<', '<<', '>>') for token in args):
        return (), 'shell wrappers and compound commands are unverified'
    if any(mark in raw for mark in ('$(', '${', '`')) or re.search(r'\$[A-Za-z_]', raw):
        return (), 'dynamic shell expansion is unverified'
    return args, None


def _invocation(tool: dict) -> tuple[Optional[Invocation], Optional[str]]:
    argv, problem = _tokens(tool)
    if problem or not argv:
        return None, problem
    executable = argv[0].replace('\\', '/').rsplit('/', 1)[-1]
    if not PYTHON.fullmatch(executable):
        return None, 'not a direct Python invocation'
    at = 1
    while at < len(argv) and argv[at].startswith('-'):
        if argv[at] in ('-B', '-u', '-E', '-I', '-s', '-S') or re.fullmatch(r'-3(?:\.\d+)?', argv[at]):
            at += 1
        elif argv[at] in ('-X', '-W') and at + 1 < len(argv):
            at += 2
        else:
            return None, 'unsupported Python launcher option'
    if at >= len(argv):
        return None, 'Python script is missing'
    script_path = argv[at].replace('\\', '/')
    name = script_path.rsplit('/', 1)[-1]
    script = name[:-3] if name.endswith('.py') else ''
    if script not in COMMANDS or ('/' in script_path and script_path.rsplit('/', 2)[-2] != 'scripts'):
        return None, 'script is not a recognized product entry point'
    try:
        parser = _recorded_invocation_parser(script)
    except (ImportError, ValueError, AttributeError) as exc:
        return None, str(exc)
    options: list[tuple[str, Union[str, bool]]] = []
    saved = []
    subcommand = None
    at += 1
    while at < len(argv):
        token = argv[at]
        if token == '>':
            if isinstance(tool.get('argv', tool.get('command')), list):
                return None, 'argv does not execute shell redirection'
            if at + 2 != len(argv):
                return None, 'stdout redirect must end the literal invocation'
            saved.append(argv[at + 1])
            break
        if token == '--':
            if at + 1 < len(argv):
                return None, 'positional arguments after -- are not supported by this invocation schema'
            break
        actions = {flag: action for action in parser._actions for flag in action.option_strings}
        flag, equal, inline = token.partition('=')
        action = actions.get(flag)
        if action is not None:
            canonical = next((key for key in action.option_strings if key.startswith('--')), action.option_strings[0])
            if action.nargs == 0:
                if equal:
                    return None, f'{flag} does not take a value'
                options.append((canonical, not isinstance(action, argparse._StoreFalseAction)))
            elif action.nargs in (None, 1, '?'):
                if equal:
                    value = inline
                elif at + 1 < len(argv) and (action.nargs != '?' or not argv[at + 1].startswith('-')):
                    at += 1
                    value = argv[at]
                elif action.nargs == '?':
                    value = str(action.const)
                else:
                    return None, f'{flag} is missing its value'
                options.append((canonical, value))
                if canonical == '--facts-out':
                    saved.append(value)
            else:
                return None, f'unsupported option arity for {flag}'
        else:
            subparsers = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
            if subparsers is None or token not in subparsers.choices or subcommand is not None:
                return None, f'unrecognized argument {token!r}'
            subcommand = token
            parser = subparsers.choices[token]
        at += 1
    return Invocation(argv, script, COMMANDS[script], tuple(options), subcommand, tuple(saved)), None


def _json_outputs(text: object, expected: bool) -> list[object]:
    if not isinstance(text, str):
        return []
    for candidate in (text, LINE_NUMBER.sub('', text)):
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        tool = value.get('tool') if isinstance(value, dict) else None
        if expected or (isinstance(tool, str) and tool in PRODUCERS):
            return [value]
    return []


def _native_path(text: str) -> Path:
    """/d/x from an MSYS shell is D:/x for Windows Python (R8-R2-DIAG-01)."""
    drive = re.match(r'^/([a-zA-Z])/(.*)$', text)
    if drive and sys.platform == 'win32':
        return Path(f'{drive.group(1).upper()}:/{drive.group(2)}')
    return Path(text)


def _problem(code: str, message: str) -> dict:
    return {'ok': False, 'tool': 'recorded_call', 'error': code, 'message': message}


def _recorded_call(tool: dict) -> RecordedCall:
    raw = tool.get('command', tool.get('argv', ''))
    command = raw if isinstance(raw, str) else repr(raw)
    invocation, problem = _invocation(tool)
    if tool.get('name') == 'Read':
        invocation, problem = None, 'Read does not execute a product invocation'
    output = tool.get('output') or ''
    if invocation is None:
        is_read = tool.get('name') == 'Read' or (isinstance(raw, str) and bool(re.fullmatch(
            r'(?:[A-Za-z]:[\\/]|/)[^;\n|&<>]*\.json|[^\s;&|<>]+\.json', raw)))
        if is_read:
            return RecordedCall(command, None, tuple(_json_outputs(output, False)), False, False)
        relevant = any(name + '.py' in command for name in COMMANDS) or bool(_json_outputs(output, False))
        outputs = (_problem('unverified_command', problem or 'unresolved invocation'),) if relevant else ()
        return RecordedCall(command, None, outputs, False, False)
    outputs = []
    for saved in invocation.saved_paths:
        path = _native_path(saved)
        try:
            outputs.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError) as exc:
            outputs.append(_problem('facts_unavailable', f'Cannot read or decode requested facts file {path}: {exc}'))
    outputs += _json_outputs(output, not invocation.prose)
    if not invocation.prose and not outputs:
        outputs.append(_problem('expected_json', f'Expected JSON output, got {str(output)[:160]!r} from {command}'))
    parsed = parse_evidence(outputs)
    compatible = [fact for fact in parsed.facts if fact['tool'] == invocation.producer]
    if not invocation.prose and parsed.facts and len(compatible) != len(parsed.facts):
        code = 'expected_chart' if invocation.chart else 'wrong_producer'
        outputs.append(_problem(code, f'Expected compatible {invocation.producer} output from {command}'))
    usable = bool(compatible) and not parsed.problems and len(compatible) == len(parsed.facts)
    source_variant = usable and not parsed.chart_count
    is_fortune_source_variant = source_variant and invocation.producer == 'fortune_reading'
    if invocation.chart and source_variant and not is_fortune_source_variant:
        outputs.append(_problem('expected_chart', f'No usable {invocation.producer} chart for {command}'))
        usable = False
    requires_chart = invocation.chart and not is_fortune_source_variant
    return RecordedCall(command, invocation, tuple(outputs), requires_chart, usable)


def _latest_chart_turn_calls(record: dict) -> list[RecordedCall]:
    per_turn = [[_recorded_call(tool) for tool in turn.get('tools', [])] for turn in record.get('turns', [])]
    for index in range(len(per_turn) - 1, -1, -1):
        calls = per_turn[index]
        if any(call.invocation is not None and call.invocation.chart for call in calls):
            return [call for later in per_turn[index:] for call in later]
    return [call for calls in per_turn for call in calls]


def recorded_evidence(record: dict) -> list[object]:
    return [output for call in _latest_chart_turn_calls(record) for output in call.outputs]


def tool_facts(record: dict) -> list[dict]:
    """Admitted observations; use recorded_evidence to preserve failures too."""
    return list(parse_evidence(recorded_evidence(record)).facts)


DISCLAIMERS = ('仅供参考', '仅作参考', '不构成', '娱乐参考', '文化参考')
MECHANICAL_KEYS = frozenset({'contains_any', 'not_contains', 'first_line_any', 'tool_any', 'contains_all', 'flags',
                             'file_must_not_contain'})
NOT_PROSE = re.compile(r'^\s*(\||```|#|---|\*\*\*|>)')


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), '')


def check(case: dict, record: dict, run: Path) -> dict:
    folder = run / case['id']
    answer = (folder / f"answer-{len(record['turns'])}.txt").read_text(encoding='utf-8') if record['turns'] else ''
    first = _first_line(answer)
    rules = case.get('checks', {})
    found: list[dict] = []

    def add(name: str, passed: bool, detail: str = '') -> None:
        found.append({'check': name, 'passed': passed, 'detail': detail})
    add('complete', record['complete'])
    add('first_line_is_prose', bool(first) and not NOT_PROSE.match(first), first[:60])
    add('one_disclaimer_at_most', sum(answer.count(d) for d in DISCLAIMERS) <= 1)
    for words in [rules['contains_any']] if 'contains_any' in rules else []:
        add('contains_any', any(w in answer for w in words), '/'.join(words))
    for word in rules.get('not_contains', []):
        add(f'not_contains:{word}', word not in answer)
    if 'first_line_any' in rules:
        add('first_line_any', any(w in first for w in rules['first_line_any']), first[:60])
    calls = _latest_chart_turn_calls(record)
    facts = [output for call in calls for output in call.outputs]
    prose = check_answer(answer, facts)
    if any(call.requires_chart for call in calls):
        add('tool_facts_recorded', all(call.chart_recorded for call in calls if call.requires_chart),
            f"{prose['checked']['facts_loaded']} admitted tool outputs")
    for item in prose['findings']:
        if item['severity'] == 'error':
            add(f"answer_check:{item['code']}", False, item['detail'] if item['code'] == 'invalid_facts' else item['excerpt'][:60])
    if 'tool_any' in rules:
        add('tool_any', any(call.invocation is not None and w in (call.invocation.script, call.invocation.script + '.py', call.invocation.producer) for call in calls for w in rules['tool_any']), '/'.join(rules['tool_any']))
    if 'contains_all' in rules:
        missing = [w for w in rules['contains_all'] if w not in answer]
        add('contains_all', not missing, '缺：' + '/'.join(missing) if missing else '')
    for flag in rules.get('flags', []):
        add(f'flag:{flag}', any(call.invocation is not None and call.chart_recorded and call.invocation.has_flag(flag) for call in calls))
    if 'file_must_not_contain' in rules:
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix in ('.html', '.md', '.txt', '.json')
                 and not p.name.startswith('answer-') and p.name != 'record.json']
        leaked = sorted({w for p in files for w in rules['file_must_not_contain']
                         if w in p.read_text(encoding='utf-8', errors='replace')})
        add('file_must_not_contain', bool(files) and not leaked,
            ('泄露：' + '/'.join(leaked)) if leaked else ('' if files else '没有可核的输出文件'))
    for key in sorted(set(rules) - MECHANICAL_KEYS):
        add(f'needs_human_review:{key}', False, str(rules[key])[:60])
    usage = [(t.get('result') or {}) for t in record['attempts']]
    return {'id': case['id'], 'group': case['id'][0], 'passed': all(c['passed'] for c in found), 'checks': found,
            'chars': len(answer), 'tool_calls': sum(len(t.get('tools', [])) for t in record['turns']),
            'cost_usd': round(sum(u.get('total_cost_usd') or 0 for u in usage), 4),
            'attempts': len(record['attempts']),
            'output_tokens': sum((u.get('usage') or {}).get('output_tokens') or 0 for u in usage),
            'input_tokens': sum(sum((u.get('usage') or {}).get(k) or 0 for k in
                                    ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
                                for u in usage)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = {c['id']: c for c in json.loads(args.cases.read_text(encoding='utf-8'))['cases']}
    results = []
    for folder in sorted(p for p in args.run.iterdir() if (p / 'record.json').exists()):
        record = json.loads((folder / 'record.json').read_text(encoding='utf-8'))
        results.append(check(cases[record['id']], record, args.run))
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(r['group'], []).append(r)
    summary = {'cases': len(results), 'passed': sum(r['passed'] for r in results),
               'cost_usd': round(sum(r['cost_usd'] for r in results), 2),
               'groups': {g: {'cases': len(rs), 'passed': sum(r['passed'] for r in rs)} for g, rs in sorted(groups.items())},
               'failed_checks': [{'id': r['id'], 'failed': [c for c in r['checks'] if not c['passed']]}
                                 for r in results if not r['passed']],
               'results': results}
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"{summary['passed']}/{summary['cases']} passed the mechanical checks; ${summary['cost_usd']}")
    for row in summary['failed_checks']:
        print(row['id'], [c['check'] for c in row['failed']])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
