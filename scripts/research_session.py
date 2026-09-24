"""A five-minute host research budget and an external, non-executable candidate library.

The host performs searches with its available browser tools. This tool records
actual sources and progress; starting a session never claims a search happened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from personal_profiles import data_root
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

SOURCE_FIELDS = {'title', 'edition', 'source_url', 'locator', 'quote', 'context',
                 'conditions', 'exceptions', 'modern_mapping', 'verification_notes'}


def _now(clock: datetime | None) -> datetime:
    value = clock or datetime.now(UTC)
    if value.tzinfo is None:
        raise ValueError('研究时间须含时区')
    return value.astimezone(UTC)


def _path(ident: str, root: Path | None) -> Path:
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('无效 research_id')
    directory = data_root(root) / 'research'
    if directory.is_symlink():
        raise ValueError('研究目录不能是链接')
    path = directory / (ident + '.json')
    if path.is_symlink():
        raise ValueError('研究记录不能是链接')
    return path


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='research-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def begin(scenario: str, *, root: Path | None = None, clock: datetime | None = None) -> dict:
    if not isinstance(scenario, str) or not scenario.strip() or len(scenario) > 80:
        raise ValueError('只记录通用事项名称，最多80字符；不保存个人问题或出生资料')
    now = _now(clock)
    value: dict = {'research_id': uuid4().hex, 'schema_version': '1.0', 'scenario': scenario,
             'started_at': now.isoformat(), 'deadline': (now + timedelta(seconds=300)).isoformat(),
             'status': 'in_progress', 'queries': [], 'candidates': [],
             'scope': '候选资料仅用于查阅；不自动成为可执行规则或个人断语'}
    _write(_path(value['research_id'], root), value)
    return value


def load(ident: str, *, root: Path | None = None, clock: datetime | None = None) -> dict:
    value = json.loads(_path(ident, root).read_text(encoding='utf-8'))
    if value['research_id'] != ident:
        raise ValueError('研究记录身份不一致')
    remaining = (datetime.fromisoformat(value['deadline']) - _now(clock)).total_seconds()
    return {**value, 'remaining_seconds': max(0, int(remaining)),
            'may_search': value['status'] == 'in_progress' and remaining > 0}


def record(ident: str, query: str, *, source: dict | None = None,
           root: Path | None = None, clock: datetime | None = None) -> dict:
    value = load(ident, root=root, clock=clock)
    if not value['may_search']:
        raise ValueError('本轮补查已结束或达到5分钟；请结束记录，不重启预算')
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ValueError('query 须为不包含个人资料的古籍检索词，最多200字符')
    value['queries'].append({'query': query, 'at': _now(clock).isoformat(), 'source_found': source is not None})
    if source is not None:
        if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
            raise ValueError('候选资料须含 title/edition/source_url/locator/quote/context/conditions/exceptions/modern_mapping/verification_notes')
        if any(not isinstance(v, str) or len(v) > 16000 for v in source.values()):
            raise ValueError('候选字段须为不超过16000字符的文本')
        if any(not source[k].strip() for k in SOURCE_FIELDS - {'exceptions', 'modern_mapping'}):
            raise ValueError('出处、条件和核对记录不能留空')
        url = urlsplit(source['source_url'])
        if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
            raise ValueError('来源须为无凭据的 HTTP(S) 页面或影像链接')
        if source['quote'] not in source['context']:
            raise ValueError('原文摘句必须包含在保留的上下文中')
        digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if not any(c['source_sha256'] == digest for c in value['candidates']):
            value['candidates'].append({**source, 'source_sha256': digest, 'status': 'candidate',
                                        'executable': False, 'review': None})
    _write(_path(ident, root), value)
    return value


def finish(ident: str, reason: str, *, root: Path | None = None, clock: datetime | None = None) -> dict:
    if reason not in ('sufficient_sources', 'no_applicable_source', 'tools_unavailable', 'budget_expired'):
        raise ValueError('请记录真实停止原因')
    value = load(ident, root=root, clock=clock)
    if value['status'] != 'in_progress':
        return value
    now = _now(clock)
    expired = now >= datetime.fromisoformat(value['deadline'])
    if reason == 'budget_expired' and not expired:
        raise ValueError('尚未到截止时间，不能报告预算已耗尽')
    if reason == 'sufficient_sources' and not value['candidates']:
        raise ValueError('没有候选来源，不能报告已获得足够来源')
    value.update(status='finished', stop_reason='budget_expired' if expired else reason,
                 finished_at=now.isoformat(), may_search=False,
                 elapsed_seconds=(now - datetime.fromisoformat(value['started_at'])).total_seconds())
    _write(_path(ident, root), value)
    return value


def review(ident: str, digest: str, checks: dict, *, root: Path | None = None) -> dict:
    """Persist an attributed review, still requiring explicit implementation for rules."""
    required = {'reviewer', 'source_verification', 'applicability', 'exceptions', 'counterexample', 'conclusion'}
    if not isinstance(checks, dict) or set(checks) != required or any(
            not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in checks.values()):
        raise ValueError('复核须逐项记录核对者、来源、适用条件、例外、反例及结论；布尔勾选无效')
    value = load(ident, root=root)
    match = next((c for c in value['candidates'] if c['source_sha256'] == digest), None)
    if match is None:
        raise ValueError('未找到该候选原文')
    match.update(status='review_recorded', review=checks)
    _write(_path(ident, root), value)
    return value


def search(query: str, *, root: Path | None = None) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ValueError('query 须为1–200字符')
    directory = _path('0' * 32, root).parent
    results = []
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            continue
        value = json.loads(path.read_text(encoding='utf-8'))
        for candidate in value['candidates']:
            if query in value['scenario'] or query in candidate['title'] or query in candidate['context']:
                results.append({'research_id': value['research_id'], 'scenario': value['scenario'], **candidate})
    return {'results': results[:20], 'total_matches': len(results),
            'scope': '外部候选资料；复核记录不等于规则已实现，不自动产生个人结论'}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, epilog='Top-level JSON keys: ok tool version research_id status candidates; errors: error message')
    parser.add_argument('action', choices=('begin', 'status', 'record', 'finish', 'review', 'search'))
    parser.add_argument('--stdin', action='store_true', required=True)
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args(argv)
    import sys
    try:
        p = json.load(sys.stdin)
        root = args.data_dir
        if args.action == 'begin':
            result = begin(p['scenario'], root=root)
        elif args.action == 'search':
            result = search(p['query'], root=root)
        elif args.action == 'status':
            result = load(p['research_id'], root=root)
        elif args.action == 'record':
            result = record(p['research_id'], p['query'], source=p.get('source'), root=root)
        elif args.action == 'review':
            result = review(p['research_id'], p['source_sha256'], p['checks'], root=root)
        else:
            result = finish(p['research_id'], p['reason'], root=root)
        json_print(ok_envelope('research_session', result))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        json_print(error_envelope('research_session', 'invalid_research', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
