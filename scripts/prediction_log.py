"""Private prospective records: frozen methods, immutable forecasts, confirmed outcomes.

This measures recorded forecasts; it neither generates them nor certifies their
accuracy. Storage is local, outside repositories, with no birth data fields.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from classical_search import get_passage
from personal_profiles import data_root
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope


def _now(clock: datetime | None) -> datetime:
    value = clock or datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('时间必须带时区')
    return value.astimezone(UTC)


def _text(value: object, name: str, limit: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} 必须为1–{limit}字符文本')
    return value


def _time(value: object) -> datetime:
    return _now(datetime.fromisoformat(_text(value, '日期时间', 80)))


def _id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('标识必须为匿名32位十六进制编号')
    return value


def _path(root: Path | None) -> Path:
    directory = data_root(root) / 'predictions'
    path = directory / 'records.sqlite3'
    if directory.is_symlink() or path.is_symlink():
        raise ValueError('验证记录不可使用符号链接')
    return path


@contextmanager
def _db(root: Path | None, *, create: bool = False) -> Iterator[sqlite3.Connection]:
    path = _path(root)
    if not path.exists() and not create:
        raise ValueError('尚无验证记录')
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=5)
    try:
        path.chmod(0o600)
        db.execute('PRAGMA secure_delete=ON')
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL)')
        yield db
        db.commit()
    finally:
        db.close()  # Any failed transaction is rolled back.


def _get(db: sqlite3.Connection, ident: str) -> dict:
    row = db.execute('SELECT body FROM records WHERE id=?', (_id(ident),)).fetchone()
    if row is None:
        raise ValueError('记录不存在或已删除')
    return json.loads(row[0])


def _put(db: sqlite3.Connection, value: dict) -> None:
    db.execute('INSERT OR REPLACE INTO records VALUES (?,?)',
               (value['id'], json.dumps(value, ensure_ascii=False, sort_keys=True)))


def begin(payload: dict, *, root: Path | None = None, clock: datetime | None = None) -> dict:
    fields = {'consent', 'subject_id', 'event_definition', 'timezone', 'start', 'end',
              'method', 'method_version', 'input_fingerprint'}
    if not isinstance(payload, dict) or set(payload) != fields or payload['consent'] is not True:
        raise ValueError('请按固定字段提供记录，并确认已有用户保存授权；不接收出生资料或姓名')
    _id(payload['subject_id'])
    zone = ZoneInfo(_text(payload['timezone'], 'timezone', 80))
    start, end, now = _time(payload['start']), _time(payload['end']), _now(clock)
    if not now < start < end:
        raise ValueError('只接收尚未开始的事件窗口，不能事后补录预测')
    for key in ('event_definition', 'method', 'method_version'):
        _text(payload[key], key)
    if not isinstance(payload['input_fingerprint'], str) or not re.fullmatch('[a-f0-9]{64}', payload['input_fingerprint']):
        raise ValueError('input_fingerprint 须为已确认输入的SHA256，不保存原始出生资料')
    value: dict = {'schema_version': '1.0', 'id': uuid4().hex, 'revision': 1,
             'created_at': now.isoformat(), 'state': 'draft',
             'spec': {k: v for k, v in payload.items() if k != 'consent'},
             'forecast': None, 'history': [], 'outcome': None,
             'scope': '预先记录及事后观察；不认证传统解释或现实预测有效性'}
    value['spec'].update(start=start.astimezone(zone).isoformat(), end=end.astimezone(zone).isoformat())
    with _db(root, create=True) as db:
        _put(db, value)
    return value


def _forecast(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != {'prediction', 'reason', 'evidence', 'conflicts'}:
        raise ValueError('判断只接受 prediction/reason/evidence/conflicts')
    if payload['prediction'] not in ('happens', 'not_happens', 'unable'):
        raise ValueError('prediction 必须为 happens/not_happens/unable')
    _text(payload['reason'], '判断理由')
    if not isinstance(payload['evidence'], list) or not isinstance(payload['conflicts'], list):
        raise ValueError('证据和分歧须为列表')
    evidence = []
    for row in payload['evidence']:
        if not isinstance(row, dict) or set(row) != {'passage_id', 'quote', 'condition', 'state', 'personal_fields', 'scope'}:
            raise ValueError('证据须含出处、原文、条件、核对状态、本人字段路径及适用范围')
        if row['state'] not in ('met', 'not_met', 'unknown') or row['scope'] not in ('event', 'background'):
            raise ValueError('条件状态或适用范围无效')
        if not isinstance(row['personal_fields'], list) or not row['personal_fields'] or any(
                not isinstance(p, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', p) for p in row['personal_fields']):
            raise ValueError('需列出实际核对的本人字段路径，不能存入原始值')
        source = get_passage(_text(row['passage_id'], 'passage_id', 100))
        if _text(row['quote'], '古文短句', 500) not in source['text']:
            raise ValueError('引文不在指定冻结原文中')
        _text(row['condition'], '条件核对说明')
        evidence.append({**row, 'source_sha256': source['sha256']})
    conflicts = []
    for conflict in payload['conflicts']:
        if not isinstance(conflict, dict) or set(conflict) != {'issue', 'resolution', 'evidence_indices'}:
            raise ValueError('分歧须含 issue/resolution/evidence_indices')
        _text(conflict['issue'], '分歧')
        if not isinstance(conflict['resolution'], str) or len(conflict['resolution']) > 1200:
            raise ValueError('resolution须为文本；空串表示未解决')
        conflict = {**conflict, 'resolution': conflict['resolution'].strip()}
        indices = conflict['evidence_indices']
        if not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(evidence) for i in indices):
            raise ValueError('分歧依据索引无效')
        if conflict['resolution'] and not indices:
            raise ValueError('解决分歧必须指明原文依据，不能投票或凭偏好')
        conflicts.append(dict(conflict))
    if payload['prediction'] != 'unable':
        if not evidence or any(e['state'] != 'met' for e in evidence) or not any(e['scope'] == 'event' for e in evidence):
            raise ValueError('明确事件判断须有已核条件与事件粒度依据，背景规则不足')
        if any(not c['resolution'] for c in conflicts):
            raise ValueError('分歧未解决时必须记录 unable')
    return {**payload, 'evidence': evidence, 'conflicts': conflicts,
            'validation': 'quote_and_structure_checked_semantics_not_certified'}


def change(ident: str, action: str, payload: dict, *, expected_revision: int,
           root: Path | None = None, clock: datetime | None = None) -> dict:
    now = _now(clock)
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('expected_revision 必须为正整数')
    with _db(root) as db:
        value = _get(db, ident)
        if value['revision'] != expected_revision:
            raise ValueError('记录已变化，请读取最新 revision')
        if action == 'seal':
            if value['state'] != 'draft' or now >= _time(value['spec']['start']):
                raise ValueError('预测已冻结或窗口已开始，不能补填、改写预测')
            forecast = _forecast(payload)
            value.update(state='sealed', forecast=forecast, sealed_at=now.isoformat())
            value['forecast_sha256'] = hashlib.sha256(json.dumps(
                {'spec': value['spec'], 'forecast': forecast}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        elif action == 'observe':
            if value['state'] != 'sealed' or not isinstance(payload, dict) or set(payload) != {'confirmed', 'result', 'occurred_at', 'note'}:
                raise ValueError('先冻结预测；结果须含 confirmed/result/occurred_at/note')
            if payload['confirmed'] is not True or payload['result'] not in ('happened', 'not_happened', 'unknown'):
                raise ValueError('只保存用户确认的真实结果；未确认不能当作失败')
            _text(payload['note'], '结果依据或更正原因')
            if payload['result'] == 'happened':
                occurred = _time(payload['occurred_at'])
                if not _time(value['spec']['start']) <= occurred < _time(value['spec']['end']) or occurred > now:
                    raise ValueError('发生时间必须在原定窗口内，且不能晚于当前时间')
            elif payload['occurred_at'] is not None:
                raise ValueError('未发生或无法核实不能填写发生时间')
            if payload['result'] == 'not_happened' and now < _time(value['spec']['end']):
                raise ValueError('期限尚未结束，不能提前记为未发生')
            value['outcome'] = {**payload, 'recorded_at': now.isoformat()}
        elif action == 'correct':
            if not isinstance(payload, dict) or set(payload) != {'note'}:
                raise ValueError('更正说明只接受 note；原预测和方法不覆盖')
            _text(payload['note'], '更正说明')
        elif action == 'delete':
            if not isinstance(payload, dict) or set(payload) != {'confirmed'} or payload['confirmed'] is not True:
                raise ValueError('删除需用户确认')
            db.execute('DELETE FROM records WHERE id=?', (ident,))
            db.execute("INSERT INTO metadata VALUES ('deleted',1) ON CONFLICT(key) DO UPDATE SET value=value+1")
            return {'deleted': True, 'history_deleted': True, 'anonymous_deletion_count_retained': True}
        else:
            raise ValueError('未知写入操作')
        value['revision'] += 1
        value['history'].append({'action': action, 'at': now.isoformat(), 'payload': payload})
        _put(db, value)
    return value


def status(value: dict, now: datetime) -> str:
    if value['state'] == 'draft':
        return 'unfinished'
    if value['forecast']['prediction'] == 'unable':
        return 'unable'
    if now < _time(value['spec']['end']):
        return 'pending'
    actual = value['outcome']
    if not actual or actual['result'] == 'unknown':
        return 'unverified'
    predicted = 'happened' if value['forecast']['prediction'] == 'happens' else 'not_happened'
    return 'hit' if predicted == actual['result'] else 'miss'


def inspect_records(*, ident: str | None = None, root: Path | None = None,
                    clock: datetime | None = None) -> dict:
    now = _now(clock)
    if ident is not None:
        _id(ident)
    if not _path(root).exists():
        if ident is not None:
            raise ValueError('记录不存在')
        rows, deleted = [], 0
    else:
        with _db(root) as db:
            rows = [_get(db, ident)] if ident else [json.loads(r[0]) for r in db.execute('SELECT body FROM records ORDER BY id')]
            row = db.execute("SELECT value FROM metadata WHERE key='deleted'").fetchone()
            deleted = row[0] if row else 0
    if ident:
        return {**rows[0], 'evaluation_status': status(rows[0], now)}
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = tuple(row['spec'][k] for k in ('method', 'method_version', 'event_definition'))
        groups.setdefault(key, []).append(row)
    return {**_statistics(rows, now), 'deleted_records': deleted,
            'cohorts': [{'method': key[0], 'method_version': key[1], 'event_definition': key[2],
                         **_statistics(group, now)} for key, group in sorted(groups.items())],
            'correction_events': sum(e['action'] in ('correct', 'observe') for r in rows for e in r['history']) - sum(r['outcome'] is not None for r in rows),
            'records': [{'id': r['id'], 'revision': r['revision'], 'status': status(r, now)} for r in rows],
            'limitations': ['自选样本、用户报告结果；不是因果验证或预测有效性证明',
                           '删除记录不在分母，须连同删除数量披露；本机文件不是防篡改公证',
                           '总览命中率仅为描述性汇总；比较使用同方法、版本、事件定义的cohorts',
                           '选中时间成功不能证明优于未尝试的备选时间']}


def _statistics(rows: list[dict], now: datetime) -> dict:
    counts = dict.fromkeys(('unfinished', 'unable', 'pending', 'unverified', 'hit', 'miss'), 0)
    due = [r for r in rows if now >= _time(r['spec']['end'])]
    due_answered = [r for r in due if r['forecast'] and r['forecast']['prediction'] != 'unable']
    for row in rows:
        counts[status(row, now)] += 1
    checked = counts['hit'] + counts['miss']
    return {'total': len(rows), 'counts': counts, 'due_total': len(due), 'due_answered': len(due_answered),
            'answer_coverage': len(due_answered) / len(due) if due else None,
            'outcome_confirmation_coverage': checked / len(due_answered) if due_answered else None,
            'observed_hit_rate': counts['hit'] / checked if checked else None}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, epilog='Top-level JSON keys: ok tool version; begin/show/change: id revision spec forecast history outcome; stats/list: total counts answer_coverage outcome_confirmation_coverage observed_hit_rate deleted_records; errors: error message')
    parser.add_argument('action', choices=('begin', 'seal', 'observe', 'correct', 'show', 'list', 'stats', 'delete'))
    parser.add_argument('--stdin', required=True, action='store_true')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        p = json.load(sys.stdin)
        if not isinstance(p, dict):
            raise ValueError('输入须为JSON对象')
        if args.action == 'begin':
            result = begin(p, root=args.data_dir)
        elif args.action in ('show', 'list', 'stats'):
            if set(p) != ({'id'} if args.action == 'show' else set()):
                raise ValueError('查询字段不匹配')
            result = inspect_records(ident=_id(p['id']) if args.action == 'show' else None, root=args.data_dir)
        else:
            if set(p) != {'id', 'expected_revision', 'payload'}:
                raise ValueError('写入须含 id/expected_revision/payload')
            result = change(p['id'], args.action, p['payload'], expected_revision=p['expected_revision'], root=args.data_dir)
        json_print(ok_envelope('prediction_log', result))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        json_print(error_envelope('prediction_log', 'invalid_record', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
