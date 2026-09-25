"""Explicit half-open civil windows, availability and calendar boundaries."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from utils import resolve_timezone_offset


def local_instant(value: str, zone_name: str, fold: int | None = None) -> datetime:
    if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
        raise ValueError('时间必须为 ISO 日期和时分，例如 2026-09-15T09:00')
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError('fold 必须为 0 或 1')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    zone = ZoneInfo(zone_name)
    if stamp.tzinfo is not None:
        converted = stamp.astimezone(zone)
        if converted.replace(tzinfo=None) != stamp.replace(tzinfo=None):
            raise ValueError('候选时间的 UTC offset 与事件地点时区不一致')
        if fold is not None and converted.fold != fold:
            raise ValueError('fold 与指定 UTC offset 冲突')
        return converted
    info = resolve_timezone_offset(zone_name, stamp.year, stamp.month, stamp.day,
                                   stamp.hour, stamp.minute, fold=fold)
    return stamp.replace(tzinfo=zone, fold=info['fold'])


def _midnight(day: date, zone: str) -> datetime:
    return local_instant(day.isoformat() + 'T00:00', zone)


def _next_month(day: date) -> date:
    return date(day.year + int(day.month == 12), day.month % 12 + 1, 1)


def resolve_window(period: str | dict, request: dict, event_timezone: str) -> dict:
    """Resolve relative words in the user's present zone, then local event dates."""
    ZoneInfo(event_timezone)
    current = datetime.fromisoformat(request['utc']).astimezone(ZoneInfo(request['timezone']))
    today = current.date()
    monday = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    values = {'今天': (today, today + timedelta(days=1)),
              '明天': (today + timedelta(days=1), today + timedelta(days=2)),
              '后天': (today + timedelta(days=2), today + timedelta(days=3)),
              '这两天': (today, today + timedelta(days=2)),
              '未来七天': (today, today + timedelta(days=7)),
              '本周': (monday, monday + timedelta(days=7)),
              '下周': (monday + timedelta(days=7), monday + timedelta(days=14)),
              '这周末': (monday + timedelta(days=5), monday + timedelta(days=7)),
              '本月': (month, _next_month(month)),
              '下个月': (_next_month(month), _next_month(_next_month(month))),
              '今年': (date(today.year, 1, 1), date(today.year + 1, 1, 1)),
              '明年': (date(today.year + 1, 1, 1), date(today.year + 2, 1, 1)),
              '月底前': (today, _next_month(month))}
    aliases = {'today': '今天', 'tomorrow': '明天', 'next_week': '下周',
               'next_seven_days': '未来七天', 'next_month': '下个月', 'this_year': '今年',
               # The everyday words for the same spans.
               '这周': '本周', '这个星期': '本周', '下个星期': '下周', '周末': '这周末',
               '这个月': '本月', '下月': '下个月', '最近一周': '未来七天'}
    if isinstance(period, str):
        label = aliases.get(period, period)
        if label not in values:
            raise ValueError('请提供明确的日期范围；暂不解析此时间说法')
        start_date, end_date = values[label]
        start, end = _midnight(start_date, event_timezone), _midnight(end_date, event_timezone)
    elif isinstance(period, dict) and set(period) <= {'start', 'end'}:
        label = 'explicit_range'
        def parse(value: str) -> datetime:
            return _midnight(date.fromisoformat(value), event_timezone) if 'T' not in value else local_instant(value, event_timezone)
        start, end = parse(period['start']), parse(period['end'])
    else:
        raise ValueError('period 须为相对时段或含 start/end 的对象，end 不包含在范围内')
    duration = end.astimezone(UTC) - start.astimezone(UTC)
    if duration <= timedelta(0) or duration > timedelta(days=3660):
        raise ValueError('日期范围须为正，最多十年；更长范围请分批')
    if start.year < 1900 or end.year > 2100:
        raise ValueError('目标日期须位于 1900–2100 支持范围内')
    return {'label': label, 'start': start.isoformat(), 'end': end.isoformat(),
            'timezone': event_timezone, 'end_exclusive': True,
            'relative_anchor_timezone': request['timezone'],
            'relative_anchor_date': today.isoformat()}


def candidate_windows(candidates: list[dict], window: dict, *, duration_minutes: int,
                      busy: list[dict] | None = None, not_before: str | None = None) -> list[dict]:
    if type(duration_minutes) is not int or not 1 <= duration_minutes <= 1440:
        raise ValueError('事件 duration_minutes 必须为 1–1440 的整数')
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 128:
        raise ValueError('请提供 1–128 个真实可选时间窗口')
    zone = window['timezone']
    first = datetime.fromisoformat(window['start']).astimezone(UTC)
    last = datetime.fromisoformat(window['end']).astimezone(UTC)
    if not_before:
        first = max(first, datetime.fromisoformat(not_before).astimezone(UTC))
    occupied = []
    if busy is not None and (not isinstance(busy, list) or len(busy) > 128):
        raise ValueError('busy 最多接受 128 个已占用窗口')
    for row in busy or []:
        if not isinstance(row, dict) or set(row) - {'start', 'end', 'fold', 'end_fold'}:
            raise ValueError('已占用窗口只接受 start/end/fold/end_fold')
        a, b = local_instant(row['start'], zone, row.get('fold')).astimezone(UTC), local_instant(row['end'], zone, row.get('end_fold')).astimezone(UTC)
        if a >= b:
            raise ValueError('已占用时间窗口必须起点早于终点')
        occupied.append((a, b))
    result = []
    seen: set[str] = set()
    for index, row in enumerate(candidates):
        if not isinstance(row, dict) or set(row) - {'id', 'start', 'end', 'fold', 'end_fold'}:
            raise ValueError('候选窗口只接受 id/start/end/fold/end_fold')
        ident = row.get('id', f'candidate-{index + 1}')
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in seen:
            raise ValueError('候选 id 必须唯一且不超过 80 字符')
        seen.add(ident)
        start = local_instant(row['start'], zone, row.get('fold')).astimezone(UTC)
        end = local_instant(row['end'], zone, row.get('end_fold')).astimezone(UTC)
        if start >= end or end - start > timedelta(days=31):
            raise ValueError('单个候选窗口须为正且不超过 31 天')
        pieces = [(max(start, first), min(end, last))]
        clipped_start, clipped_end = pieces[0]
        if end <= first:
            rejected_reason = ('这个时间已经过去' if not_before and end <= datetime.fromisoformat(not_before).astimezone(UTC)
                               else '这个窗口早于你要比较的日期范围')
        elif start >= last:
            rejected_reason = '这个窗口晚于你要比较的日期范围'
        elif clipped_end - clipped_start < timedelta(minutes=duration_minutes):
            rejected_reason = f'落在目标范围且尚未过期的时间，不足连续 {duration_minutes} 分钟'
        else:
            rejected_reason = f'扣除已占用的行程后，没有连续 {duration_minutes} 分钟可用'
        for a, b in occupied:
            remaining = []
            for x, y in pieces:
                if a >= y or b <= x:
                    remaining.append((x, y))
                else:
                    if x < a:
                        remaining.append((x, a))
                    if b < y:
                        remaining.append((b, y))
            pieces = remaining
        intervals = [(x, y) for x, y in pieces if y - x >= timedelta(minutes=duration_minutes)]
        result.append({'id': ident, 'available': bool(intervals),
                       'reason': None if intervals else rejected_reason,
                       'intervals': [{'start': x.astimezone(ZoneInfo(zone)).isoformat(),
                                      'end': y.astimezone(ZoneInfo(zone)).isoformat()} for x, y in intervals]})
    return result


def civil_boundaries(start: datetime, end: datetime) -> list[datetime]:
    """Split actual instants at local midnight/hour branches and DST transitions."""
    zone = start.tzinfo
    a, b = start.astimezone(UTC), end.astimezone(UTC)
    cuts = {a, b}
    day = start.date() - timedelta(days=1)
    while day <= end.date() + timedelta(days=1):
        for hour in (0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23):
            wall = datetime.combine(day, time(hour))
            for fold in (0, 1):
                aware = wall.replace(tzinfo=zone, fold=fold)
                utc = aware.astimezone(UTC)
                if utc.astimezone(zone).replace(tzinfo=None) == wall and a < utc < b:
                    cuts.add(utc)
        day += timedelta(days=1)
    # Timezone transitions may occur inside a branch, including half-hour DST.
    cursor = a
    while cursor < b:
        probe = min(cursor + timedelta(hours=1), b)
        if cursor.astimezone(zone).utcoffset() != probe.astimezone(zone).utcoffset():
            lo, hi = cursor, probe
            while (hi - lo).total_seconds() > 1:
                mid = lo + timedelta(seconds=int((hi - lo).total_seconds() // 2))
                if lo.astimezone(zone).utcoffset() == mid.astimezone(zone).utcoffset():
                    lo = mid
                else:
                    hi = mid
            cuts.add(hi)
        cursor = probe
    return sorted(cuts)
