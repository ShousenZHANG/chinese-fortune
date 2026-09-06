"""One aware request instant, resolved independently from birth time.

Call this CLI once and pass its utc/current timezone to time-aware calculations.
Explicit historical wall times remain usable without inventing a timezone.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils import (
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    resolve_timezone_offset,
)


def _zone(name: str | None) -> ZoneInfo:
    if not name:
        raise ValueError('当前所在地未知；请提供 --current-timezone IANA 时区，不能以出生地或主机时区代替')
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f'无效 IANA 时区: {name}') from exc


def _iso(value: str) -> datetime:
    try:
        if not re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value):
            raise ValueError('缺少时分')
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'时间需完整 ISO 日期和时分: {value}') from exc


def capture_request_time(
    current_timezone: str | None, instant: str | None = None,
    *, clock: Callable[[], datetime] | None = None,
) -> dict:
    """Sample a clock exactly once, or reuse an injected offset-bearing instant."""
    zone = _zone(current_timezone)
    moment = _iso(instant) if instant is not None else (clock() if clock else datetime.now(UTC))
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('--request-time 必须含 Z 或 UTC offset；不接受无时区时刻')
    utc = moment.astimezone(UTC)
    return {'source': 'provided_instant' if instant is not None else 'system_utc_clock',
            'utc': utc.isoformat(), 'local': utc.astimezone(zone).isoformat(),
            'timezone': zone.key, 'precision': 'second'}


def add_request_arguments(parser: argparse.ArgumentParser, *, target: bool = True) -> None:
    parser.add_argument('--current-timezone', help='用户当前所在地 IANA 时区；与出生时区分开')
    parser.add_argument('--request-time', help='复用请求时刻，ISO 日期时间，必须含 Z/offset')
    if target:
        parser.add_argument('--target-timezone', help='显式目标日期时间所在的 IANA 时区')
        parser.add_argument('--fold', type=int, choices=(0, 1), default=None,
                            help='目标当地时间重复时选 0=第一次 / 1=第二次')


def resolve_time(
    args: argparse.Namespace, *, date_value: str | None = None,
    time_value: str | None = None, datetime_value: str | None = None,
    day_only: bool = False,
) -> tuple[datetime, dict]:
    """Resolve an explicit target or one current request, never mix their parts."""
    current_zone = getattr(args, 'current_timezone', None)
    target_zone = getattr(args, 'target_timezone', None) or current_zone
    instant = getattr(args, 'request_time', None)
    request = capture_request_time(current_zone, instant) if instant is not None else None
    if target_zone:
        _zone(target_zone)
    explicit = datetime_value is not None or date_value is not None or time_value is not None
    if not explicit:
        request = request or capture_request_time(current_zone)
        dt = datetime.fromisoformat(request['utc']).astimezone(_zone(target_zone))
        source = 'request_time'
    elif datetime_value is not None:
        if date_value is not None or time_value is not None:
            raise ValueError('不能同时给 --datetime 与 --date/--time')
        dt = _iso(datetime_value)
        source = 'explicit_target'
    elif day_only and date_value is not None and time_value is None:
        # A day-level query does not assert that the user supplied noon/midnight.
        dt = datetime.strptime(date_value, '%Y-%m-%d').replace(hour=12)
        return dt, {'source': 'explicit_date', 'local': dt.date().isoformat(),
                    'utc': None, 'timezone': target_zone, 'precision': 'day',
                    'request_time': request, 'timezone_status': 'iana' if target_zone else 'unspecified'}
    else:
        if date_value is None or time_value is None:
            raise ValueError('时级计算须同时提供 --date 与 --time；历史日期不能混入当前时分')
        dt = datetime.strptime(f'{date_value} {time_value}', '%Y-%m-%d %H:%M')
        source = 'explicit_target'
    if target_zone:
        zone = _zone(target_zone)
        if dt.tzinfo is None:
            info = resolve_timezone_offset(target_zone, dt.year, dt.month, dt.day,
                                           dt.hour, dt.minute, fold=getattr(args, 'fold', None))
            dt = dt.replace(tzinfo=zone, fold=info['fold'])
        else:
            dt = dt.astimezone(zone)
    offset = dt.utcoffset()
    aware = dt.tzinfo is not None and offset is not None
    context = {'source': source, 'local': dt.isoformat(),
               'utc': dt.astimezone(UTC).isoformat() if aware else None,
               'timezone': target_zone, 'precision': 'day' if day_only else 'minute',
               'offset_hours': offset.total_seconds() / 3600 if offset is not None else None,
               'fold': dt.fold if aware else None, 'request_time': request,
               'timezone_status': 'iana' if target_zone else ('fixed_offset' if aware else 'floating_local')}
    if not aware:
        context['limitation'] = '显式当地时间未指定时区；不能声称 UTC 时刻或应用经度修正'
    return dt, context


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='获取用户所在地时间；一次取时供本次多工具共用',
        epilog='Top-level JSON keys: ok tool version source utc local timezone precision; errors: error message')
    add_request_arguments(parser, target=False)
    args = parser.parse_args(argv)
    try:
        json_print(ok_envelope('request_time', capture_request_time(args.current_timezone, args.request_time)))
        return 0
    except ValueError as exc:
        json_print(error_envelope('request_time', 'invalid_time_context', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
