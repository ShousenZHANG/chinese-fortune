"""Regression tests at the CLI and shared civil-time interface."""
import pytest
from conftest import run_cli
from utils import normalize_birth_time, resolve_timezone_offset, true_solar_time_info


def test_reference_meridian_still_applies_equation_of_time():
    args = ('--year', 2000, '--month', 2, '--day', 15, '--hour', 1,
            '--minute', 5, '--gender', 'male', '--longitude', 120)
    bazi = run_cli('bazi_calc.py', *args)
    ziwei = run_cli('ziwei_calc.py', *args)
    expected = {'year': 2000, 'month': 2, 'day': 15, 'hour': 0, 'minute': 50}
    assert bazi['solar_date'] == ziwei['solar_date'] == expected


def test_cross_day_explanation_matches_effective_date():
    info = true_solar_time_info(100, 8, 2000, 2, 15, 0, 10)
    assert info['true_solar_time'] == '22:35'
    assert info['day_offset'] == -1
    assert info['effective_date'] == '2000-02-14'


def test_nonexistent_wall_time_is_rejected():
    with pytest.raises(ValueError, match='不存在'):
        resolve_timezone_offset('Australia/Sydney', 2026, 10, 4, 2, 30)


def test_repeated_wall_time_requires_explicit_fold():
    with pytest.raises(ValueError, match='重复'):
        resolve_timezone_offset('Australia/Sydney', 2026, 4, 5, 2, 30)


def test_explicit_fold_resolves_two_distinct_instants():
    first = resolve_timezone_offset('Australia/Sydney', 2026, 4, 5, 2, 30, fold=0)
    second = resolve_timezone_offset('Australia/Sydney', 2026, 4, 5, 2, 30, fold=1)
    assert (first['offset_hours'], second['offset_hours']) == (11, 10)
    assert first['ambiguous'] and second['ambiguous']


@pytest.mark.parametrize('script', ['bazi_calc.py', 'ziwei_calc.py'])
def test_clock_school_is_explicit(script):
    chart = run_cli(script, '--year', 2000, '--month', 2, '--day', 15,
                    '--hour', 1, '--minute', 5, '--gender', 'male', '--time-standard', 'clock')
    assert chart['solar_date']['hour'] == 1
    assert not chart['true_solar_time']['applied']


@pytest.mark.parametrize('script', ['bazi_calc.py', 'ziwei_calc.py'])
def test_dst_gap_reaches_cli_error_contract(script):
    chart = run_cli(script, '--year', 2026, '--month', 10, '--day', 4,
                    '--hour', 2, '--minute', 30, '--gender', 'male',
                    '--timezone', 'Australia/Sydney', expect_rc=1)
    assert not chart['ok'] and '不存在' in chart['message']


@pytest.mark.parametrize('year,month,day,hour,minute,lon,date_expected', [
    (2000, 1, 1, 0, 0, 100, '1999-12-31'),
    (2000, 2, 29, 23, 55, 130, '2000-03-01'),
    (2000, 12, 31, 23, 55, 130, '2001-01-01'),
])
def test_normalization_reports_calendar_rollovers(year, month, day, hour, minute, lon, date_expected):
    normalized = normalize_birth_time(year, month, day, hour, minute, lon)
    info = normalized['true_solar_time']
    effective = normalized['solar_date']
    assert info['effective_date'] == date_expected
    assert f"{effective['year']:04d}-{effective['month']:02d}-{effective['day']:02d}" == date_expected
    assert f"{effective['hour']:02d}:{effective['minute']:02d}" == info['true_solar_time']


def test_clock_mode_does_not_claim_dst_was_subtracted():
    result = normalize_birth_time(1988, 7, 1, 7, 30, 120,
                                  timezone='Asia/Shanghai', time_standard='clock')
    assert result['solar_date']['hour'] == 7
    assert result['timezone']['dst_hours'] == 1
    assert '按标准时折算' not in result['timezone']['note']
