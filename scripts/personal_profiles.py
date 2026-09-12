"""Confirmed, revisioned personal inputs stored outside the skill and repository."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

ROOT = Path(__file__).resolve().parents[1]
BIRTH_FIELDS = {'year', 'month', 'day', 'hour', 'minute', 'gender', 'timezone', 'city',
                'longitude', 'time_standard', 'fold', 'sect', 'lunar'}


def validate_person(person: dict, *, check_calendar: bool = True) -> dict:
    """Reject ambiguous provenance and silently ignored input fields."""
    if not isinstance(person, dict) or set(person) - {'birth', 'current_timezone', 'label', 'time_certainty'}:
        raise ValueError('档案只接受 birth、current_timezone、label、time_certainty')
    birth = person.get('birth')
    if not isinstance(birth, dict) or set(birth) - BIRTH_FIELDS:
        raise ValueError('出生字段无效；请使用文档中列出的字段')
    for key in ('year', 'month', 'day'):
        if type(birth.get(key)) is not int:
            raise ValueError(f'出生 {key} 必须为整数')
    if birth.get('gender') not in ('male', 'female'):
        raise ValueError('请确认排大运所用的 gender: male / female')
    if not birth.get('timezone') and not birth.get('city'):
        raise ValueError('请提供出生地 IANA 时区或可解析的 city')
    if birth.get('time_standard', 'true-solar') == 'true-solar' and not birth.get('city') and birth.get('longitude') is None:
        raise ValueError('真太阳时需要出生经度或已收录城市，不能默用东经120度')
    for key, lower, upper in (('hour', 0, 23), ('minute', 0, 59), ('fold', 0, 1), ('sect', 1, 2)):
        value = birth.get(key)
        if value is not None and (type(value) is not int or not lower <= value <= upper):
            raise ValueError(f'{key} 必须为 {lower}–{upper} 的整数')
    if birth.get('time_standard', 'true-solar') not in ('true-solar', 'clock'):
        raise ValueError('time_standard 必须为 true-solar / clock')
    if birth.get('longitude') is not None:
        import math
        value = birth['longitude']
        if type(value) not in (int, float) or not math.isfinite(value) or not -180 <= value <= 180:
            raise ValueError('longitude 必须为 -180–180 的有限数值')
    if birth.get('timezone'):
        ZoneInfo(birth['timezone'])
    if person.get('current_timezone'):
        ZoneInfo(person['current_timezone'])
    certainty = person.get('time_certainty', 'exact' if birth.get('hour') is not None else 'unknown')
    if certainty not in ('exact', 'approximate', 'unknown'):
        raise ValueError('time_certainty 必须为 exact / approximate / unknown')
    if certainty == 'exact' and birth.get('hour') is None:
        raise ValueError('时辰未知不能标记 exact')
    if certainty == 'unknown' and birth.get('hour') is not None:
        raise ValueError('unknown 时请省略 hour，不保存占位时辰')
    if birth.get('hour') is None and birth.get('minute') not in (0, None):
        raise ValueError('出生时辰未知时不能单独提供分钟数')
    if len(str(person.get('label', ''))) > 80:
        raise ValueError('档案标签过长')
    # The chart validator checks lunar dates, historical folds, and true-solar inputs.
    from bazi_calc import build_parser, calculate_bazi
    argv = birth_arguments(birth)
    if check_calendar:
        chart = calculate_bazi(build_parser(diagnostics=False).parse_args(argv))
        if not chart['ok']:
            raise ValueError(chart['message'])
    return {**person, 'birth': dict(birth), 'time_certainty': certainty}


def birth_arguments(birth: dict) -> list[str]:
    if not isinstance(birth, dict) or set(birth) - BIRTH_FIELDS:
        raise ValueError('未知出生字段')
    args: list[str] = []
    for key, value in birth.items():
        if value is None:
            continue
        if key == 'lunar':
            if type(value) is not bool:
                raise ValueError('lunar 必须为布尔值')
            if value:
                args.append('--lunar')
        else:
            args.extend(['--' + key.replace('_', '-'), str(value)])
    return args


def data_root(root: Path | str | None = None) -> Path:
    base = Path(root or os.environ.get('CHINESE_FORTUNE_DATA_DIR') or
                Path.home() / '.local' / 'share' / 'chinese-fortune').expanduser().resolve()
    if base == ROOT or base.is_relative_to(ROOT):
        raise ValueError('个人档案必须位于仓库或技能目录之外')
    if any((parent / '.git').exists() for parent in (base, *base.parents)):
        raise ValueError('个人档案不能放在 Git 仓库内')
    return base


def profile_path(profile_id: str, root: Path | str | None = None) -> Path:
    if not isinstance(profile_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', profile_id):
        raise ValueError('profile_id 只接受 1–64 位字母、数字、下划线和连字符')
    if profile_id.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}:
        raise ValueError('profile_id 不能使用系统保留设备名')
    base = data_root(root)
    path = base / (profile_id + '.json')
    if path.is_symlink() or path.resolve().parent != base:
        raise ValueError('档案路径不可使用链接或越界')
    return path


def load_profile(profile_id: str, root: Path | str | None = None) -> dict:
    path = profile_path(profile_id, root)
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('档案必须为对象')
    if value.get('schema_version') != '1.0' or value.get('profile_id') != profile_id:
        raise ValueError('档案格式或身份不匹配')
    if value.get('confirmed') is not True or type(value.get('revision')) is not int or value['revision'] < 1:
        raise ValueError('档案尚未确认或修订号无效')
    validate_person(value.get('person', {}), check_calendar=False)
    return value


def save_profile(profile_id: str, person: dict, *, confirmed: bool,
                 expected_revision: int = 0, root: Path | str | None = None) -> dict:
    if confirmed is not True:
        raise ValueError('只有用户确认保存的资料才可写入档案')
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('expected_revision 必须为非负整数')
    person = validate_person(person)
    path = profile_path(profile_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('档案正在修改；请稍后重试') from exc
    temporary: str | None = None
    try:
        os.close(descriptor)
        previous = load_profile(profile_id, root) if path.exists() else None
        revision = previous['revision'] if previous else 0
        if revision != expected_revision:
            raise ValueError('档案已变化；请读取最新 revision 后再确认修改')
        history = list(previous.get('history', [])) if previous else []
        if previous:
            history.append({k: previous[k] for k in ('revision', 'confirmed_at', 'person')})
        value = {'schema_version': '1.0', 'profile_id': profile_id, 'revision': revision + 1,
                 'confirmed': True, 'confirmed_at': datetime.now(UTC).isoformat(),
                 'person': person, 'history': history}
        fd, temporary = tempfile.mkstemp(prefix='profile-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        return value
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def delete_profile(profile_id: str, *, expected_revision: int,
                   root: Path | str | None = None) -> dict:
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('删除时请确认正整数 expected_revision')
    path = profile_path(profile_id, root)
    lock = path.with_suffix('.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('档案正在修改；请稍后重试') from exc
    try:
        os.close(descriptor)
        if load_profile(profile_id, root)['revision'] != expected_revision:
            raise ValueError('档案已变化；请确认最新 revision')
        path.unlink()
        return {'profile_id': profile_id, 'deleted': True, 'history_deleted': True}
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='本机确认档案；save 从 stdin 读取 person JSON',
        epilog='Top-level JSON keys: ok tool version; list: profiles (profile_id, revision, label only); '
               'show/save: schema_version profile_id revision confirmed confirmed_at person history; '
               'delete: profile_id deleted history_deleted. Errors: error message. '
               'save requires explicit confirmation and the current revision; it does not store conversations.')
    parser.add_argument('action', choices=('list', 'show', 'save', 'delete'))
    parser.add_argument('--profile-id')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--confirmed', action='store_true')
    parser.add_argument('--expected-revision', type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.action == 'list':
            values = [load_profile(p.stem, args.data_dir) for p in data_root(args.data_dir).glob('*.json')]
            result = {'profiles': [{'profile_id': p['profile_id'], 'revision': p['revision'],
                                    'label': p['person'].get('label', '')} for p in values]}
        elif not args.profile_id:
            raise ValueError('请提供 --profile-id')
        elif args.action == 'show':
            result = load_profile(args.profile_id, args.data_dir)
        elif args.action == 'save':
            import sys
            result = save_profile(args.profile_id, json.load(sys.stdin), confirmed=args.confirmed,
                                  expected_revision=args.expected_revision, root=args.data_dir)
        else:
            result = delete_profile(args.profile_id, expected_revision=args.expected_revision,
                                    root=args.data_dir)
        json_print(ok_envelope('personal_profiles', result))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        json_print(error_envelope('personal_profiles', 'invalid_profile', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
