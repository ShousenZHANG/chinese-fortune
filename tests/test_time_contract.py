"""Regression tests at the CLI and shared civil-time interface."""
import pytest

from conftest import run_cli
from utils import resolve_timezone_offset, true_solar_time_info


def test_reference_meridian_still_applies_equation_of_time():
    args = ('--year', 2000, '--month', 2, '--day', 15, '--hour', 1,
            '--minute', 5, '--gender', 'male', '--longitude', 120)
    bazi = run_cli('bazi_calc.py', *args)
    ziwei = run_cli('ziwei_calc.py', *args)
    expected = dict(year=2000, month=2, day=15, hour=0, minute=50)
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
