"""Minute-resolution consensus over a supplied birth interval, never a guessed point."""
from __future__ import annotations

import argparse
from copy import deepcopy

from bazi_calc import calculate_bazi


def interval_minutes(value: dict) -> tuple[int, int]:
    if not isinstance(value, dict) or set(value) != {'start', 'end'}:
        raise ValueError('birth_time_range 需要同一出生日期的 start/end，格式 HH:MM')
    minutes = []
    for key in ('start', 'end'):
        text = value[key]
        if not isinstance(text, str) or len(text) != 5 or text[2] != ':':
            raise ValueError('出生时间范围须为 HH:MM')
        try:
            hour, minute = map(int, text.split(':'))
        except ValueError as exc:
            raise ValueError('出生时间范围须为 HH:MM') from exc
        if not 0 <= hour < 24 or not 0 <= minute < 60:
            raise ValueError('出生时间范围超出当天')
        minutes.append(hour * 60 + minute)
    if minutes[0] > minutes[1]:
        raise ValueError('跨出生日期的范围须先确认日期，不能当作同一天')
    return minutes[0], minutes[1]


def calculate_interval(args: argparse.Namespace, interval: dict) -> dict:
    lo, hi = interval_minutes(interval)
    probes: list[dict] = []
    for minute in range(lo, hi + 1):
        for fold in ((0, 1) if args.timezone and args.fold is None else (args.fold,)):
            values = {**vars(args), 'hour': minute // 60, 'minute': minute % 60, 'fold': fold}
            chart = calculate_bazi(argparse.Namespace(**values))
            if not chart.get('ok'):
                if '不存在 (夏令时跳时)' in chart.get('message', ''):
                    continue
                raise ValueError(chart.get('message', '出生时间范围计算失败'))
            probes.append(chart)
    if not probes:
        raise ValueError('出生范围落在不存在的当地时间内')
    clean = deepcopy(probes[0])
    affected = []
    for key in ('year', 'month', 'day', 'hour'):
        possibilities = sorted({c['four_pillars'][key]['ganzhi'] for c in probes})
        if len(possibilities) > 1:
            affected.append(key)
            clean['four_pillars'][key] = {'status': 'birth_time_range', 'candidate_ganzhi': possibilities}
    clean['hour_known'] = 'hour' not in affected
    if 'day' in affected:
        clean['day_master'] = {'status': 'birth_time_range'}
    for key in ('solar_date', 'lunar_date'):
        dates = sorted({tuple(c[key][k] for k in ('year', 'month', 'day')) for c in probes})
        clean[key] = (dict(zip(('year', 'month', 'day'), dates[0], strict=True)) if len(dates) == 1 else
                      {'status': 'birth_time_range', 'candidate_dates':
                       [dict(zip(('year', 'month', 'day'), d, strict=True)) for d in dates]})
    # An invariant pillar does not establish an exact physical birth instant.
    clean['calendar_context'] = {'status': 'birth_time_range', 'birth_instant_utc': None}
    clean['true_solar_time'] = {'status': 'birth_time_range', 'time_standard': args.time_standard,
                               'longitude': args.longitude}
    clean['timezone'] = {'tz_name': args.timezone, 'status': 'birth_time_range'}
    luck_stable = all(c['qi_yun'] == probes[0]['qi_yun'] and c['da_yun'] == probes[0]['da_yun'] for c in probes)
    if not luck_stable:
        clean['qi_yun'] = None
        clean['da_yun'] = []
        clean['qi_yun_status'] = 'birth_time_range'
    clean['liu_nian'] = []
    clean['birth_time_uncertainty'] = {
        'status': 'interval_verified', 'range': dict(interval), 'end_inclusive': True,
        'candidate_coverage': 'every_valid_clock_minute_and_fold',
        'valid_probes': len(probes), 'affected_pillars': affected, 'luck_stable': luck_stable,
        'meaning': '范围内每个有效钟面分钟均核对；只保留一致的柱和运程，不把端点当作精确生时。'}
    return clean
