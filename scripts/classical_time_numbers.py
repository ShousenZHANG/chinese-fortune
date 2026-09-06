"""Numerical time-cast profile from 梅花易數 卷一 年月日時起例.

Checked transcription: Wikisource oldid=2690596, 2026-09-06. Not a facsimile audit.
The passage specifies year-branch/month/day/hour counts, not leap-month handling.
"""
from __future__ import annotations

import argparse
from datetime import datetime

from utils import shichen_number

SOURCE = 'https://zh.wikisource.org/w/index.php?oldid=2690596&title=梅花易數/卷一'


def add_calendar_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--calendar-profile', choices=('classical', 'legacy-gregorian'),
                        default='classical', help='时间起卦: 年支+农历月日(默认) / 旧公历简化')
    parser.add_argument('--leap-month-policy', choices=('repeat', 'next'), default=None,
                        help='遇闰月须明示: repeat=按本月数; next=按下一月数(十二后归一)')


def time_numbers(dt: datetime, profile: str = 'classical', leap_policy: str | None = None) -> dict:
    """Return declared calendar operands; no access to any clock."""
    method: dict = {}
    if profile == 'legacy-gregorian':
        y, m, d = dt.year, dt.month, dt.day
        method = {'id': 'legacy-gregorian', 'basis': '旧版公历整数简化，不是所核古籍年月日起例',
                  'year_basis': 'civil_year_integer', 'month_day_basis': 'gregorian'}
    elif profile == 'classical':
        try:
            from lunar_python import Solar
        except ImportError as exc:
            raise ValueError('古法历数需要 lunar_python；请安装 scripts/requirements.txt') from exc
        lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0).getLunar()
        y = (lunar.getYear() - 4) % 12 + 1
        raw_month = lunar.getMonth()
        m, d = abs(raw_month), lunar.getDay()
        if raw_month < 0:
            if leap_policy not in ('repeat', 'next'):
                raise ValueError('目标为农历闰月；原条款未明示算法，请指定 --leap-month-policy repeat/next')
            if leap_policy == 'next':
                m = m % 12 + 1
        method = {'id': 'classical', 'basis': '梅花易數·卷一·年月日時起例',
                  'source_url': SOURCE, 'verification': 'transcription_checked',
                  'year_basis': 'lunar_year_branch_ordinal', 'month_day_basis': 'lunar',
                  'day_boundary': 'civil_midnight', 'time_standard': 'supplied_local_clock',
                  'lunar_year': lunar.getYear(), 'is_leap_month': raw_month < 0,
                  'leap_month_policy': leap_policy,
                  'limits': '闰月、现代时区及子初/子正换日口径为明确实现约定，非该条原文已定'}
    else:
        raise ValueError('未知 calendar-profile')
    h = shichen_number(dt.hour)
    return {'year_number': y, 'month_number': m, 'day_number': d, 'hour_number': h,
            'upper_num': (y + m + d) % 8 or 8,
            'lower_num': (y + m + d + h) % 8 or 8,
            'change_num': (y + m + d + h) % 6 or 6,
            'method_profile': method}
