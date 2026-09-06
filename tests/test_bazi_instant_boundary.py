"""Independent term fixtures plus invariance of an astronomical instant.

HKO's 2026 calendar gives 立春 Feb 4 04:02 HKT and 惊蛰 Mar 5
21:59 HKT. Tests bracket by minutes, not falsely claiming that the printed
minute authenticates lunar_python's second-level approximation.
https://www.hko.gov.hk/tc/gts/astron2026/files/2026cal02.pdf
https://www.hko.gov.hk/tc/gts/astron2026/files/2026cal03.pdf

Year 2025 is 乙巳, 2026 is 丙午. 五虎遁 gives the preceding 己丑,
then 庚寅 and 辛卯. Expected branches and stems are literal fixtures;
the oracle does not import production lookup tables or recompute the chart.
"""
from datetime import datetime

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading


def chart(**options):
    values = {'year': 2026, 'month': 2, 'day': 4, 'hour': 7, 'minute': 3,
                  'gender': 'male', 'timezone': 'Australia/Sydney', 'longitude': 151.21,
                  'time_standard': 'clock'}
    values.update(options)
    args = ['--no-geju', '--no-shensha', '--no-yongshen']
    for key, value in values.items():
        if value is True:
            args.append('--' + key.replace('_', '-'))
        elif value is not None:
            args.extend(['--' + key.replace('_', '-'), str(value)])
    result = calculate_bazi(build_parser().parse_args(args))
    assert result['ok'], result
    return result


def year_month(result):
    return tuple(result['four_pillars'][k]['ganzhi'] for k in ('year', 'month'))


@pytest.mark.parametrize('location', [
    {'day': 4, 'hour': 7, 'timezone': 'Australia/Sydney', 'longitude': 151.21},
    {'day': 3, 'hour': 15, 'timezone': 'America/New_York', 'longitude': -74},
    {'day': 3, 'hour': 20, 'timezone': 'UTC', 'longitude': 0},
    {'day': 3, 'hour': 15, 'timezone': None, 'tz': -5, 'longitude': -74},
    {'day': 4, 'hour': 4, 'timezone': 'Asia/Shanghai', 'longitude': 120},
])
@pytest.mark.parametrize(('minute', 'expected'), [(1, ('乙巳', '己丑')), (3, ('丙午', '庚寅'))])
def test_lichun_same_instant_in_positive_negative_and_numeric_zones(location, minute, expected):
    result = chart(**location, minute=minute)
    assert year_month(result) == expected
    assert result['calendar_context']['birth_instant_utc'] == f'2026-02-03T20:0{minute}:00+00:00'
    assert result['calendar_context']['birth_calendar_datetime'] == f'2026-02-04T04:0{minute}:00+08:00'


@pytest.mark.parametrize(('hour', 'minute', 'expected'), [(0, 58, '庚寅'), (1, 0, '辛卯')])
def test_jingzhe_after_local_date_rollover(hour, minute, expected):
    result = chart(month=3, day=6, hour=hour, minute=minute)
    assert year_month(result) == ('丙午', expected)


def test_true_solar_clock_crosses_term_wall_time_without_moving_term_instant():
    clock = chart(hour=4, timezone='Asia/Shanghai', longitude=75)
    solar = chart(hour=4, timezone='Asia/Shanghai', longitude=75, time_standard='true-solar')
    assert solar['solar_date']['hour'] < 4  # corrected wall clock is before 04:02
    assert year_month(clock) == year_month(solar) == ('丙午', '庚寅')
    assert clock['calendar_context']['birth_instant_utc'] == solar['calendar_context']['birth_instant_utc']
    assert clock['qi_yun'] == solar['qi_yun']
    assert clock['four_pillars']['hour']['ganzhi'] != solar['four_pillars']['hour']['ganzhi']


def test_local_day_and_sect_are_not_replaced_by_calendar_coordinate():
    # The same instant is Feb 3 in New York and Feb 4 in UTC+8.
    new_york = chart(day=3, hour=15, timezone='America/New_York', longitude=-74)
    assert new_york['four_pillars']['day']['ganzhi'] == '戊申'
    assert chart()['four_pillars']['day']['ganzhi'] == '己酉'
    late = chart(day=3, hour=23, minute=30, timezone='America/New_York', longitude=-74)
    late_sect1 = chart(day=3, hour=23, minute=30, timezone='America/New_York', longitude=-74, sect=1)
    assert late['four_pillars']['day']['ganzhi'] == '戊申'
    assert late_sect1['four_pillars']['day']['ganzhi'] == '己酉'
    assert year_month(late) == year_month(late_sect1) == ('丙午', '庚寅')
    assert late['qi_yun']['algorithm_sect'] == late_sect1['qi_yun']['algorithm_sect'] == 1
    assert late['qi_yun']['start_calendar_datetime'] == late_sect1['qi_yun']['start_calendar_datetime']


@pytest.mark.parametrize(('minute', 'direction', 'duration', 'first_cycle'), [
    (1, 'backward', (9, 10, 0), '戊子'),
    (3, 'forward', (9, 11, 0), '辛卯'),
])
def test_yun_uses_real_year_polarity_month_and_term_interval(minute, direction, duration, first_cycle):
    # Before 立春: reverse from Feb 4 寅 to Jan 5 申 = 29 days + 6
    # two-hour units => 118 months. After: forward to Mar 5 亥 = 29
    # days + 9 units => 119 months. Sect=1 counts 4 months per day,
    # 10 days per two-hour unit; these expectations were calculated by hand.
    result = chart(day=3, hour=15, minute=minute, timezone='America/New_York', longitude=-74)
    q = result['qi_yun']
    assert q['direction'] == direction
    assert tuple(q[k] for k in ('years', 'months', 'days')) == duration
    assert result['da_yun'][0]['ganzhi'] == first_cycle
    assert q['interval_calendar_zone'] == 'UTC+08:00'
    assert q['date_timezone'] == 'America/New_York'
    assert datetime.fromisoformat(q['start_local_datetime']) == datetime.fromisoformat(q['start_calendar_datetime'])
    assert q['start_day'] == 3  # displayed date is New York, not the UTC+8 fourth


def test_same_instant_yun_duration_and_order_are_location_invariant():
    sydney = chart()
    ny = chart(day=3, hour=15, timezone='America/New_York', longitude=-74)
    for key in ('years', 'months', 'days', 'direction', 'start_calendar_datetime'):
        assert sydney['qi_yun'][key] == ny['qi_yun'][key]
    assert [d['ganzhi'] for d in sydney['da_yun']] == [d['ganzhi'] for d in ny['da_yun']]


def test_lunar_input_converts_date_before_resolving_the_instant():
    # HKO Feb 4 2026 is lunar 2025-12-17. It names a local civil date
    # before applying the explicitly supplied birth timezone.
    lunar = chart(year=2025, month=12, day=17, lunar=True)
    solar = chart()
    assert year_month(lunar) == year_month(solar) == ('丙午', '庚寅')
    assert lunar['calendar_context'] == solar['calendar_context']


def test_unknown_hour_uses_local_lichun_date_and_emits_no_noon_instant():
    # New York crosses 立春 on Feb 3, not the Chinese calendar's Feb 4.
    raw = chart(day=3, hour=None, timezone='America/New_York', longitude=-74)
    assert raw['qi_yun'] is None and raw['da_yun'] == []
    assert raw['calendar_context']['status'] == 'birth_time_required'
    assert 'birth_instant_utc' not in raw['calendar_context']
    facts = prepare_reading(raw)['chart_facts']
    assert facts['four_pillars']['year']['candidate_ganzhi'] == ['丙午', '乙巳']
    assert facts['four_pillars']['month']['candidate_ganzhi'] == ['己丑', '庚寅']
    assert facts['four_pillars']['day']['ganzhi'] == '戊申'
    assert facts['qi_yun'] is None


def test_regular_domestic_chart_remains_unchanged():
    result = chart(year=1990, month=5, day=10, hour=14, minute=0,
                   timezone='Asia/Shanghai', longitude=120, time_standard='clock')
    assert tuple(result['four_pillars'][k]['ganzhi'] for k in ('year', 'month', 'day', 'hour')) == (
        '庚午', '辛巳', '乙亥', '癸未')


def test_domestic_yun_duration_date_and_sequence_keep_the_fixed_regression_value():
    result = chart(year=1995, month=3, day=8, hour=7, minute=30,
                   gender='female', timezone='Asia/Shanghai', longitude=120)
    # A pre-existing domestic fixture, with the interval worked separately:
    # Mar 8 辰 to Apr 5 未 is 28 days + 3 two-hour units = 113 months.
    q = result['qi_yun']
    assert (q['years'], q['months'], q['days']) == (9, 5, 0)
    assert (q['start_year'], q['start_month'], q['start_day']) == (2004, 8, 8)
    assert [d['ganzhi'] for d in result['da_yun'][:3]] == ['庚辰', '辛巳', '壬午']


@pytest.mark.parametrize(('minute', 'expected'), [(46, ('乙巳', '己丑')), (48, ('丙午', '庚寅'))])
def test_non_integer_utc_offset_keeps_the_same_lichun_boundary(minute, expected):
    result = chart(hour=1, minute=minute, timezone='Asia/Kathmandu', longitude=85.32)
    assert year_month(result) == expected
    assert result['timezone']['offset_hours'] == 5.75


def test_birth_dst_offset_and_yun_calendar_coordinates_are_explicit():
    # Shanghai was UTC+9 in May 1990. Clock 14:00 = UTC+8 13:00;
    # preserving the selected local day/hour does not lose that one hour
    # when computing the astronomical interval.
    result = chart(year=1990, month=5, day=10, hour=14, minute=0,
                   timezone='Asia/Shanghai', longitude=120)
    assert result['timezone']['offset_hours'] == 9
    assert result['calendar_context']['birth_calendar_datetime'] == '1990-05-10T13:00:00+08:00'
    assert result['calendar_context']['birth_instant_utc'] == '1990-05-10T05:00:00+00:00'
