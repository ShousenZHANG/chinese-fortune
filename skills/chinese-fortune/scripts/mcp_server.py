"""MCP server over stdio: the same CLIs, callable from any MCP host.

Skill hosts read SKILL.md and run the scripts themselves. Hosts that only speak
the Model Context Protocol (desktop chat apps, editors) get the same tools here,
plus SKILL.md and the references as resources, so the workflow rules travel
with the tools. Pure standard library, newline-delimited JSON-RPC 2.0; every
call runs the real script in a subprocess with an argument list (no shell), so
validation, errors and output are exactly what the CLI gives.

Configure a host with: {"command": "python", "args": ["<skill>/scripts/mcp_server.py"]}
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from utils import __version__, ensure_utf8_stdio

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PROTOCOLS = ('2025-06-18', '2025-03-26', '2024-11-05')
TIMEOUT = 180
JSON_TYPES: dict[str, type | tuple[type, ...]] = {'string': str, 'integer': int, 'number': (int, float),
                                                  'boolean': bool, 'object': dict, 'array': list}
# Maintenance tools are left out, and so are the two that persist personal data
# (profiles, prediction log): saving needs the user's explicit say-so in a host
# that shows what is written, which a generic tool call does not.
PERSONAL_DATA = {'personal_profiles.py', 'prediction_log.py'}
EXCLUDED = {'mcp_server.py', 'build_skill.py', 'build_han_variants.py', 'import_classics.py', 'rule_registry.py',
            'corpus_archive.py',
            *PERSONAL_DATA}
INSTRUCTIONS = ('中国术数工具。先读资源 SKILL.md 的流程：拿不准走哪条流程先调 route_question；'
                '八字本命用 bazi_reading（默认 view=compact）；回答发出前用 answer_check 核对正文；'
                '不给分数，不把条件结论说成确定事件，未判的就说未判。')

BIRTH = {'year': {'type': 'integer'}, 'month': {'type': 'integer'}, 'day': {'type': 'integer'},
         'hour': {'type': 'integer', 'description': '省略表示时辰未知'}, 'minute': {'type': 'integer'},
         'gender': {'type': 'string', 'enum': ['male', 'female']},
         'timezone': {'type': 'string', 'description': '出生地 IANA 时区，如 Asia/Shanghai'},
         'city': {'type': 'string'}, 'longitude': {'type': 'number'},
         'lunar': {'type': 'boolean'}, 'sect': {'type': 'integer', 'enum': [1, 2]},
         'death_date': {'type': 'string', 'description': '已故者卒日 YYYY-MM-DD；大运流年只列到这一年'}}


# Mirrors ziwei_calc.SCHOOL_CHOICES (a test keeps them equal); not imported so the
# server stays a thin stdlib launcher.
ZIWEI_SCHOOLS = {key: {'type': 'string', 'enum': values} for key, values in {
    'school': ['default', 'nihai'],
    'brightness': ['mainstream7', 'project4'],
    'geng_sihua': ['yang-wu-yin-tong', 'yang-wu-tong-yin', 'yang-wu-fu-tong', 'yang-wu-fu-xiang', 'yang-wu-tong-xiang'],
    'leap_month': ['split', 'next', 'prev'],
    'kui_yue': ['tongxing', 'quanshu-1', 'quanshu-2', 'zhong-yiming'],
    'tian_ma': ['year', 'month'],
    'tianshi_tianshang': ['default', 'zhongzhou'],
    'jie_kong': ['split', 'single', 'zhanyan'],
    'changsheng': ['shui-tu', 'huo-tu'],
    'changsheng_direction': ['yinyang', 'gender'],
    'year_divide': ['lunar-new-year', 'lichun'],
}.items()}


def _schema(properties: dict, required: tuple[str, ...] = ()) -> dict:
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


TOOLS: dict[str, dict] = {
    'route_question': {'script': 'question_router.py', 'description': '按用户原话给出流程、命令和所需资料（只路由，不计算）',
                       'schema': _schema({'question': {'type': 'string'}}, ('question',))},
    'bazi_reading': {'script': 'bazi_reading.py', 'description': '八字盘面、格局条件、大运与原文段号；默认 compact',
                     'schema': _schema({**BIRTH, 'question': {'type': 'string'}, 'as_of_year': {'type': 'integer'},
                                        'current_timezone': {'type': 'string'}, 'request_time': {'type': 'string'},
                                        'view': {'type': 'string', 'enum': ['compact', 'full']}},
                                       ('year', 'month', 'day', 'gender')),
                     'defaults': {'view': 'compact'}},
    'ziwei_chart': {'script': 'ziwei_calc.py', 'description': '紫微斗数命盘；给 horoscope_date 时加流年斗君、流月、流日、流时',
                    'schema': _schema({**BIRTH, 'horoscope_date': {'type': 'string'}, 'horoscope_time': {'type': 'string'},
                                       'liu_year': {'type': 'integer'}, 'brief_palaces': {'type': 'boolean'},
                                       'focus_palace': {'type': 'string', 'description': '所问宫位，如 夫妻、事业、财运'},
                                       **ZIWEI_SCHOOLS},
                                      ('year', 'month', 'day', 'hour', 'gender'))},
    'fortune_reading': {'script': 'fortune_reading.py', 'stdin_field': 'request',
                        'description': '个人短期运势、择日择时、行程；request 结构见 references/24-personalized-forecast.md',
                        'schema': _schema({'request': {'type': 'object'}}, ('request',)), 'flags': ['--stdin']},
    'pair_facts': {'script': 'pair_facts.py', 'description': '两人八字逐柱合冲刑害事实，不打分',
                   'stdin_fields': ('a', 'b', 'relation'),
                   'schema': _schema({'a': {'type': 'object', 'properties': BIRTH},
                                      'b': {'type': 'object', 'properties': BIRTH},
                                      'relation': {'type': 'string', 'enum': ['marriage', 'parent_child',
                                                                              'partnership', 'friendship']}},
                                     ('a', 'b')), 'flags': ['--stdin']},
    'classical_search': {'script': 'classical_search.py', 'description': '离线检索随包古籍原文、出处与上下文',
                         'schema': _schema({'query': {'type': 'string'}, 'passage_id': {'type': 'string'},
                                            'chapter_id': {'type': 'string'}, 'book': {'type': 'string'},
                                            'limit': {'type': 'integer'}})},
    'request_time': {'script': 'request_time.py', 'description': '固定本次请求的当前时刻与现居地时区',
                     'schema': _schema({'current_timezone': {'type': 'string'}, 'request_time': {'type': 'string'}})},
    'answer_check': {'script': 'answer_check.py', 'stdin_field': 'answer', 'flags': ['--answer', '-'],
                     'description': '发出前机械核对回答：引文、四柱、分数、确定性断言、未判格局、并列',
                     'schema': _schema({'answer': {'type': 'string'},
                                        'facts': {'type': 'array', 'items': {'type': 'object'}}}, ('answer',))},
    'doctor': {'script': 'doctor.py', 'description': '安装自检，失败时给出下一步', 'schema': _schema({})},
    'run_script': {'script': None, 'description': '运行其他随包脚本（梅花、六爻、周易、奇门、六壬、黄历、生肖等）；'
                                                  'args 为命令行参数列表，先用 route_question 拿到命令',
                   'schema': _schema({'script': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}},
                                      'stdin': {'type': 'string'}}, ('script',))},
}


def runnable_scripts() -> list[str]:
    return sorted(p.name for p in SCRIPTS.glob('*.py') if p.name not in EXCLUDED and not p.name.startswith('_'))


def _flag_args(arguments: dict, skip: set[str]) -> list[str]:
    args: list[str] = []
    for key, value in arguments.items():
        if key in skip or value is None or value is False:
            continue
        flag = '--' + key.replace('_', '-')
        args += [flag] if value is True else [flag, str(value)]
    return args


def _command(name: str, arguments: dict) -> tuple[list[str], str | None]:
    spec = TOOLS[name]
    allowed = set(spec['schema']['properties'])
    extra = set(arguments) - allowed
    if extra:
        raise ValueError('unknown arguments: ' + ', '.join(sorted(extra)))
    missing = [k for k in spec['schema']['required'] if k not in arguments]
    if missing:
        raise ValueError('missing arguments: ' + ', '.join(missing))
    for key, value in arguments.items():
        expected = spec['schema']['properties'][key].get('type')
        if expected and value is not None and not isinstance(value, JSON_TYPES[expected])                 or isinstance(value, bool) and expected in ('integer', 'number'):
            raise ValueError(f'argument {key} must be {expected}')
        if expected == 'array' and not all(isinstance(item, (str, dict)) for item in value or []):
            raise ValueError(f'argument {key} has items of the wrong type')
    if name == 'run_script':
        script = arguments['script']
        args = arguments.get('args', [])
        if script not in runnable_scripts() or not all(isinstance(a, str) for a in args):
            raise ValueError(f'script must be one of {runnable_scripts()} and args a list of strings')
        return [script, *args], arguments.get('stdin')
    stdin: str | None = None
    skip: set[str] = set()
    if 'stdin_field' in spec:
        skip = {spec['stdin_field']}
        value = arguments[spec['stdin_field']]
        stdin = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if 'stdin_fields' in spec:
        skip = set(spec['stdin_fields'])
        stdin = json.dumps({k: arguments[k] for k in spec['stdin_fields'] if k in arguments}, ensure_ascii=False)
    args = list(spec.get('flags', []))
    if name == 'answer_check':
        skip.add('facts')
    args += _flag_args({**spec.get('defaults', {}), **arguments}, skip)
    return [spec['script'], *args], stdin


def call_tool(name: str, arguments: dict) -> dict:
    """Run one tool; the CLI's JSON (or error) comes back as text content."""
    if not isinstance(name, str) or name not in TOOLS:
        raise ValueError(f'unknown tool: {name}')
    if not isinstance(arguments, dict):
        raise ValueError('arguments must be an object')
    command, stdin = _command(name, arguments)
    temp: list[Path] = []
    try:
        if name == 'answer_check':
            import tempfile
            for facts in arguments.get('facts') or []:
                if not isinstance(facts, dict):
                    raise ValueError('facts items must be objects')
                handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
                temp.append(Path(handle.name))
                with handle:
                    json.dump(facts, handle, ensure_ascii=False)
                command += ['--facts', handle.name]
        done = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / command[0]), *command[1:]],
                              cwd=ROOT, input=stdin, capture_output=True, text=True, encoding='utf-8',
                              timeout=TIMEOUT)
    finally:
        for path in temp:
            path.unlink(missing_ok=True)
    text = done.stdout.strip() or done.stderr.strip() or f'exit {done.returncode}'
    return {'content': [{'type': 'text', 'text': text}], 'isError': done.returncode != 0}


def resources() -> list[dict]:
    files = [ROOT / 'SKILL.md', *sorted((ROOT / 'references').glob('*.md'))]
    return [{'uri': 'chinese-fortune://' + p.relative_to(ROOT).as_posix(), 'name': p.relative_to(ROOT).as_posix(),
             'mimeType': 'text/markdown'} for p in files if p.is_file()]


def read_resource(uri: str) -> dict:
    known = {r['uri']: r for r in resources()}
    if uri not in known:
        raise ValueError('unknown resource: ' + uri)
    text = (ROOT / known[uri]['name']).read_text(encoding='utf-8')
    return {'contents': [{'uri': uri, 'mimeType': 'text/markdown', 'text': text}]}


def handle(message: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method, params, mid = message.get('method'), message.get('params') or {}, message.get('id')
    if mid is None:
        return None
    if not isinstance(params, dict):
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'params must be an object'}}
    try:
        result: Any
        if method == 'initialize':
            asked = params.get('protocolVersion')
            result = {'protocolVersion': asked if asked in PROTOCOLS else PROTOCOLS[0],
                      'capabilities': {'tools': {'listChanged': False}, 'resources': {'listChanged': False}},
                      'serverInfo': {'name': 'chinese-fortune', 'version': __version__},
                      'instructions': INSTRUCTIONS}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': [{'name': n, 'description': s['description'], 'inputSchema': s['schema']}
                                for n, s in TOOLS.items()]}
        elif method == 'tools/call':
            try:
                arguments = params.get('arguments')
                result = call_tool(params.get('name', ''), {} if arguments is None else arguments)
            except (ValueError, TypeError, UnicodeError, subprocess.TimeoutExpired) as exc:
                result = {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
        elif method == 'resources/list':
            result = {'resources': resources()}
        elif method == 'resources/read':
            result = read_resource(params.get('uri', ''))
        else:
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'method not found: {method}'}}
    except (ValueError, OSError, TypeError, UnicodeError) as exc:
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': str(exc)}}
    return {'jsonrpc': '2.0', 'id': mid, 'result': result}


def serve(stdin: Any = None, stdout: Any = None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except (ValueError, RecursionError):  # bad JSON, or nesting deep enough to exhaust the parser
            reply: dict | None = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'parse error'}}
        else:
            try:
                reply = handle(message) if isinstance(message, dict) else {
                    'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'invalid request'}}
            except Exception as exc:  # noqa: BLE001 - one bad request must not end the session
                reply = {'jsonrpc': '2.0', 'id': message.get('id') if isinstance(message, dict) else None,
                         'error': {'code': -32603, 'message': f'{type(exc).__name__}: {exc}'}}
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + '\n')
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ensure_utf8_stdio()
    argparse.ArgumentParser(
        description='MCP stdio 服务：随包工具与 SKILL.md/参考文档，供只支持 MCP 的宿主使用',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='JSON-RPC 2.0, one message per line on stdin/stdout.\n'
               'Top-level JSON keys per reply: jsonrpc id result | error').parse_args(argv)
    reconfigure = getattr(sys.stdin, 'reconfigure', None)
    if reconfigure:
        # Undecodable bytes become U+FFFD and fail as a parse error instead of ending the session.
        reconfigure(encoding='utf-8', errors='replace')
    serve()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
