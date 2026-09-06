"""Independent minute-level term fixtures; day/hour retain the local clock.

HKO almanacs publish Hong Kong time (UTC+8):
https://www.hko.gov.hk/tc/gts/astron2025/files/HKO_almanac_2025.pdf
  Winter solstice: 2025-12-21 23:03.
https://www.hko.gov.hk/tc/gts/astron2026/files/HKO_almanac_2026.pdf
  Moderate cold: 2026-01-05 16:23; severe cold: 2026-01-20 09:45.
The cases straddle these published minutes; no claim of independent seconds.
"""

import pytest
from conftest import run_cli
from liuren_cast import determine_yue_jiang
from lunar_python import Solar


def cast(date, time, zone=None):
    args = ['--date', date, '--time', time]
    if zone:
        args += ['--target-timezone', zone]
    return run_cli('liuren_cast.py', *args)


@pytest.mark.parametrize(('parts', 'expected'), [
    ((2025, 12, 21, 23, 2), ('小雪', '寅', '功曹')),
    ((2025, 12, 21, 23, 4), ('冬至', '丑', '大吉')),
    ((2025, 12, 31, 12, 0), ('冬至', '丑', '大吉')),
    ((2026, 1, 1, 12, 0), ('冬至', '丑', '大吉')),
    ((2026, 1, 20, 9, 43), ('冬至', '丑', '大吉')),
    ((2026, 1, 20, 9, 46), ('大寒', '子', '神后')),
])
def test_previous_major_term_spans_winter_alias_and_new_year(parts, expected):
    assert determine_yue_jiang(Solar.fromYmdHms(*parts, 0).getLunar()) == expected


def test_missing_term_is_an_error_instead_of_a_guessed_severe_cold():
    class MissingTerm:
        def getPrevQi(self):
            return None

    with pytest.raises(ValueError, match='不能确定月将'):
        determine_yue_jiang(MissingTerm())


@pytest.mark.parametrize(('date', 'before', 'after', 'zone'), [
    ('2025-12-21', '23:02', '23:04', 'Asia/Shanghai'),
    ('2025-12-21', '10:02', '10:04', 'America/New_York'),
    ('2025-12-22', '02:02', '02:04', 'Australia/Sydney'),
])
def test_winter_solstice_changes_general_at_the_same_instant(date, before, after, zone):
    previous = cast(date, before, zone)
    following = cast(date, after, zone)
    assert (previous['zhong_qi'], previous['yue_jiang']) == ('小雪', '寅')
    assert (following['zhong_qi'], following['yue_jiang']) == ('冬至', '丑')
    assert following['calendar_basis']['year_month_yue_jiang'] == 'real_instant_at_UTC+08:00'
    assert following['ganzhi']['month'] == previous['ganzhi']['month'] == '戊子'
    assert following['ganzhi']['day'] == previous['ganzhi']['day']


def test_same_solstice_instant_can_have_different_local_day_and_hour():
    ny = cast('2025-12-21', '10:04', 'America/New_York')
    sy = cast('2025-12-22', '02:04', 'Australia/Sydney')
    assert ny['yue_jiang'] == sy['yue_jiang'] == '丑'
    assert ny['ganzhi']['month'] == sy['ganzhi']['month'] == '戊子'
    assert ny['ganzhi']['day'] != sy['ganzhi']['day']
    assert (ny['zhan_shi'], sy['zhan_shi']) == ('巳', '丑')
    assert ny['calendar_basis']['comparison_clock'] == sy['calendar_basis']['comparison_clock']


@pytest.mark.parametrize(('date', 'before', 'after', 'zone'), [
    ('2026-01-20', '09:43', '09:46', 'Asia/Shanghai'),
    ('2026-01-19', '20:43', '20:46', 'America/New_York'),
    ('2026-01-20', '12:43', '12:46', 'Australia/Sydney'),
])
def test_severe_cold_changes_general_but_not_month(date, before, after, zone):
    previous, following = cast(date, before, zone), cast(date, after, zone)
    assert (previous['zhong_qi'], previous['yue_jiang']) == ('冬至', '丑')
    assert (following['zhong_qi'], following['yue_jiang']) == ('大寒', '子')
    assert previous['ganzhi']['month'] == following['ganzhi']['month'] == '己丑'
    assert previous['month_zhi'] == following['month_zhi'] == '丑'


def test_jie_changes_month_and_season_without_changing_major_term_general():
    before = cast('2026-01-05', '03:22', 'America/New_York')
    after = cast('2026-01-05', '03:24', 'America/New_York')
    assert (before['ganzhi']['month'], after['ganzhi']['month']) == ('戊子', '己丑')
    assert (before['month_zhi'], after['month_zhi']) == ('子', '丑')
    assert (before['season_wuxing'], after['season_wuxing']) == ('水', '土')
    assert before['yue_jiang'] == after['yue_jiang'] == '丑'


def test_lichun_changes_year_and_month_at_the_new_york_instant():
    # HKO February 2026 calendar: 立春 2026-02-04 04:02 UTC+8.
    before = cast('2026-02-03', '15:01', 'America/New_York')
    after = cast('2026-02-03', '15:03', 'America/New_York')
    assert (before['ganzhi']['year'], before['ganzhi']['month']) == ('乙巳', '己丑')
    assert (after['ganzhi']['year'], after['ganzhi']['month']) == ('丙午', '庚寅')
    assert before['ganzhi']['day'] == after['ganzhi']['day']
    assert before['yue_jiang'] == after['yue_jiang'] == '子'


def test_explicit_floating_input_preserves_compatibility_without_claiming_an_instant():
    result = cast('2025-12-21', '23:04')
    assert result['yue_jiang'] == '丑'
    basis = result['calendar_basis']
    assert basis['year_month_yue_jiang'] == 'floating_calendar_assumption'
    assert basis['comparison_clock'] == '2025-12-21T23:04:00'
    assert '无法保证' in basis['limitation']
    assert result['time_context']['utc'] is None


def test_request_timestamp_keeps_seconds_for_major_term_comparison():
    # Pinned-library boundary contract only, not an independently verified second.
    before = run_cli('liuren_cast.py', '--request-time', '2026-01-20T01:44:55Z',
                     '--current-timezone', 'America/New_York')
    exact = run_cli('liuren_cast.py', '--request-time', '2026-01-20T01:44:56Z',
                    '--current-timezone', 'America/New_York')
    assert before['yue_jiang'] == '丑'
    assert exact['yue_jiang'] == '子'
