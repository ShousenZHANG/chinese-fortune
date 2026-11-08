"""JSON output and the result envelope shared by this repository's skills.

Each skill folder installs on its own, so this small module is copied into every
skill that is not chinese-fortune (which keeps the same helpers in utils.py).
tests/test_skill_split.py checks that the copies stay identical and that their
envelopes match chinese-fortune's for the same inputs.
"""
from __future__ import annotations

import json
import sys

__version__ = "6.1.1"
ENVELOPE_VERSION = 'cf-result/1'
ERROR_NEXT_STEP = {
    'input': '按 message 改正这一项输入后重试；不要猜一个值替用户补上',
    'context': '补齐时区、请求时刻等时间语境后重试；不能拿主机时区或出生地代替',
    'choice': '把 candidates 列给用户选定一个，再用选定值重试',
    'unsupported': '如实告诉用户这一项本版不支持或资料不足，不要补造结果',
    'environment': '确认 Python 3.9 以上，且本技能的 assets/ 文件完整；缺文件就重新安装这个技能',
}
_CONTEXT_ERRORS = {'missing_timezone', 'invalid_time_context', 'invalid_timezone'}
_UNSUPPORTED_ERRORS = {'unavailable_reference', 'symbol_not_found'}
_ENVIRONMENT_ERRORS = {'missing_dependency', 'asset_missing'}


def ensure_utf8_stdio() -> None:
    """UTF-8 stdout/stderr/stdin before argparse writes Chinese help or reads a piped request."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:  # pragma: no cover - stream without reconfigure
            pass
    try:
        sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - stdin closed or without reconfigure
        pass


def error_class(error: str) -> str:
    if error in _CONTEXT_ERRORS:
        return 'context'
    if error in _UNSUPPORTED_ERRORS:
        return 'unsupported'
    if error in _ENVIRONMENT_ERRORS:
        return 'environment'
    return 'input'


def error_envelope(tool: str, error: str, message: str, **extra: object) -> dict:
    """The failure envelope: ok/tool/version/error/message/error_class/next_step are always present."""
    kind = error_class(error)
    out = {"ok": False, "tool": tool, "version": __version__, "error": error, "message": message,
           "error_class": kind, "next_step": ERROR_NEXT_STEP[kind], "envelope": {"version": ENVELOPE_VERSION}}
    out.update(extra)
    return out


def ok_envelope(tool: str, payload: dict) -> dict:
    out = {"ok": True, "tool": tool, "version": __version__}
    out.update(payload)
    return out


def result_envelope(out: dict) -> dict:
    """What a caller needs to replay a result; these tools have no time conventions or plate methods."""
    replay = {key: out[key] for key in ('seed', 'raw_lines') if out.get(key) is not None}
    if isinstance(out.get('entropy'), dict):
        replay['entropy'] = {k: out['entropy'][k] for k in ('source', 'seed', 'reproducible') if k in out['entropy']}
    return {'version': ENVELOPE_VERSION, 'method': None, 'conventions': None, 'replay': replay or None,
            'next_step': out.get('next_step')}


def json_print(obj: object, *, compact: bool = False) -> None:
    if isinstance(obj, dict) and obj.get('ok') is True and 'tool' in obj and 'envelope' not in obj:
        obj = {**obj, 'envelope': result_envelope(obj)}
    payload = json.dumps(obj, ensure_ascii=False, indent=None if compact else 2,
                         separators=(',', ':') if compact else None, default=str)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print(payload)
    except Exception:
        sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


def warn(msg: str) -> None:
    """A warning on stderr, keeping stdout pure JSON."""
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    try:
        print(f"[warn] {msg}", file=sys.stderr)
    except UnicodeEncodeError:
        print(f"[warn] {msg}".encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
