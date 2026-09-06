"""Current residence, birth time and explicit replay must not share a clock by accident."""
import argparse
from datetime import UTC, datetime

import pytest
import request_time
from classical_time_numbers import time_numbers
from conftest import run_cli
from request_time import capture_request_time, resolve_time


def args(**values):
    return argparse.Namespace(current_timezone=None, request_time=None,
                              target_timezone=None, fold=None, **values)


def test_capture_samples_once_and_converts_cross_year():
    calls = []

    def clock():
        calls.append(1)
        return datetime(2026, 12, 31, 15, 30, tzinfo=UTC)

    captured = capture_request_time('Australia/Sydney', clock=clock)
    assert calls == [1]
    assert captured['utc'] == '2026-12-31T15:30:00+00:00'
    assert captured['local'] == '2027-01-01T02:30:00+11:00'
    assert captured['source'] == 'system_utc_clock'


def test_injected_request_is_reused_without_any_clock(monkeypatch):
    class NoClock(datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError('shared request must not read the clock again')

    monkeypatch.setattr(request_time, 'datetime', NoClock)
    context = args()
    context.current_timezone = 'Australia/Sydney'
    context.request_time = '2026-12-31T15:30:00Z'
    for host_zone in ('UTC', 'America/Los_Angeles', 'Asia/Shanghai'):
        monkeypatch.setenv('TZ', host_zone)
        first, meta = resolve_time(context)
        second, repeated = resolve_time(context)
        assert first == second and meta == repeated
        assert (first.year, first.month, first.day, first.hour) == (2027, 1, 1, 2)


@pytest.mark.parametrize('zone,instant', [
    (None, '2026-09-06T00:00:00Z'),
    ('Invalid/Zone', '2026-09-06T00:00:00Z'),
    ('Australia/Sydney', '2026-09-06T00:00:00'),
])
def test_request_requires_a_real_location_and_offset(zone, instant):
    with pytest.raises(ValueError):
        capture_request_time(zone, instant)


@pytest.mark.parametrize('value', ['2026-09-06T03', '2026-09-06T03Z', '2026-09-06T03+10:00'])
def test_iso_hour_without_minutes_is_not_silently_completed(value):
    with pytest.raises(ValueError, match='日期和时分'):
        capture_request_time('Australia/Sydney', value)
    with pytest.raises(ValueError, match='日期和时分'):
        resolve_time(args(), datetime_value=value)


def test_same_instant_different_offset_normalizes_to_same_user_time():
    context = args()
    context.current_timezone = 'Australia/Sydney'
    a, _ = resolve_time(context, datetime_value='2026-09-06T00:30:00Z')
    b, _ = resolve_time(context, datetime_value='2026-09-06T10:30:00+10:00')
    assert a.isoformat() == b.isoformat()
    assert time_numbers(a) == time_numbers(b)


def test_target_timezone_is_distinct_from_current_location():
    context = args()
    context.current_timezone = 'Australia/Sydney'
    context.target_timezone = 'Asia/Shanghai'
    context.request_time = '2026-09-06T00:30:00Z'
    dt, meta = resolve_time(context, datetime_value='2000-01-15T10:30')
    assert dt.isoformat() == '2000-01-15T10:30:00+08:00'
    assert meta['request_time']['local'] == '2026-09-06T10:30:00+10:00'


def test_floating_explicit_target_does_not_invent_timezone():
    dt, meta = resolve_time(args(), date_value='2000-01-15', time_value='10:30')
    assert dt.tzinfo is None and meta['utc'] is None
    assert meta['timezone_status'] == 'floating_local'
    assert meta['request_time'] is None


@pytest.mark.parametrize('date_value,time_value', [('2000-01-15', None), (None, '10:30')])
def test_partial_historical_time_does_not_mix_with_now(date_value, time_value):
    with pytest.raises(ValueError, match='同时提供'):
        resolve_time(args(), date_value=date_value, time_value=time_value)


def test_day_query_does_not_claim_an_input_hour():
    _, meta = resolve_time(args(), date_value='2000-01-15', day_only=True)
    assert meta['local'] == '2000-01-15' and meta['precision'] == 'day'
    assert meta['utc'] is None


def test_target_dst_gap_and_fold_are_checked():
    context = args()
    context.target_timezone = 'Australia/Sydney'
    with pytest.raises(ValueError, match='不存在'):
        resolve_time(context, datetime_value='2026-10-04T02:30')
    with pytest.raises(ValueError, match='重复'):
        resolve_time(context, datetime_value='2026-04-05T02:30')
    context.fold = 0
    first, _ = resolve_time(context, datetime_value='2026-04-05T02:30')
    context.fold = 1
    second, _ = resolve_time(context, datetime_value='2026-04-05T02:30')
    assert (second.astimezone(UTC) - first.astimezone(UTC)).total_seconds() == 3600


def test_request_cli_returns_shared_envelope_and_local_time():
    output = run_cli('request_time.py', '--current-timezone', 'Australia/Sydney',
                     '--request-time', '2026-12-31T15:30:00Z')
    assert output['ok'] and output['tool'] == 'request_time' and output['version']
    assert output['local'] == '2027-01-01T02:30:00+11:00'


@pytest.mark.parametrize('script,tail', [
    ('huangli_query.py', []), ('lunar_convert.py', ['today']),
    ('qimen_cast.py', []), ('liuren_cast.py', []),
    ('liuyao_cast.py', ['coins', '--seed', '7']),
    ('xiaoliuren_cast.py', ['solar']), ('meihua_cast.py', ['time']),
    ('yijing_cast.py', ['time']),
])
def test_default_now_cli_never_uses_unknown_host_timezone(script, tail):
    output = run_cli(script, *tail, expect_rc=1)
    assert not output['ok'] and 'current-timezone' in output['message']


@pytest.mark.parametrize('script,tail', [
    ('qimen_cast.py', []), ('liuren_cast.py', []),
    ('liuyao_cast.py', ['coins', '--seed', '7']), ('xiaoliuren_cast.py', ['solar']),
])
def test_hour_based_cli_rejects_missing_historical_hour(script, tail):
    output = run_cli(script, *tail, '--date', '2026-06-01', expect_rc=1)
    assert '时级计算' in output['message']


def test_multiple_engines_share_request_date_across_new_year():
    shared = ['--current-timezone', 'Australia/Sydney', '--request-time', '2026-12-31T15:30:00Z']
    almanac = run_cli('huangli_query.py', *shared)
    lunar = run_cli('lunar_convert.py', 'today', *shared)
    bazi = run_cli('bazi_calc.py', '--year', 2000, '--month', 1, '--day', 15,
                   '--gender', 'male', '--timezone', 'Asia/Shanghai', *shared)
    assert almanac['solar_date']['iso'] == '2027-01-01'
    assert lunar['now_iso'].startswith('2027-01-01T02:30')
    assert bazi['liu_nian'][0]['year'] == 2027
    assert bazi['timezone']['tz_name'] == 'Asia/Shanghai'
    assert bazi['current_time_context']['timezone'] == 'Australia/Sydney'


def test_birth_only_does_not_guess_current_location_year():
    output = run_cli('bazi_calc.py', '--year', 2000, '--month', 1, '--day', 15, '--gender', 'male')
    assert output['ok'] and output['liu_nian'] == []
    assert output['liu_nian_status'] == 'needs_current_timezone'


def test_explicit_year_does_not_discard_shared_request_metadata():
    output = run_cli('bazi_calc.py', '--year', 2000, '--month', 1, '--day', 15,
                     '--gender', 'male', '--as-of-year', 2030,
                     '--current-timezone', 'Australia/Sydney', '--request-time', '2026-09-06T04:00:00Z')
    assert output['liu_nian_status'] == 'explicit_year'
    assert output['liu_nian'][0]['year'] == 2030
    assert output['current_time_context']['utc'] == '2026-09-06T04:00:00+00:00'


def test_explicit_year_still_validates_a_supplied_request_time():
    output = run_cli('bazi_calc.py', '--year', 2000, '--month', 1, '--day', 15,
                     '--gender', 'male', '--as-of-year', 2030,
                     '--current-timezone', 'Australia/Sydney', '--request-time', '2026-09-06T04:00', expect_rc=1)
    assert output['error'] == 'invalid_time_context'


def test_qimen_uses_sydney_offset_instead_of_utc8():
    params = ['--date', '2026-09-06', '--time', '14:30', '--longitude', '151.2']
    rejected = run_cli('qimen_cast.py', *params, expect_rc=1)
    assert rejected['error'] == 'missing_timezone'
    output = run_cli('qimen_cast.py', *params, '--target-timezone', 'Australia/Sydney')
    assert output['input']['time'] == '14:37'
    assert output['time_context']['offset_hours'] == 10


def test_exploration_never_falls_back_to_2026_january_first():
    output = run_cli('explore_cast.py', '--lat', -33.86, '--lon', 151.2, '--seed', 7)
    assert output['huangli_date'] is None and output['huangli_directions'] == {}
    assert output['huangli_status'] == 'needs_current_timezone_or_date'


def test_classical_operands_match_observed_plum_example():
    # 2025-01-16 = 辰年十二月十七; the source's 觀梅占 uses 申時.
    dt = datetime(2025, 1, 16, 16)
    numbers = time_numbers(dt)
    assert [numbers[k] for k in ('year_number', 'month_number', 'day_number', 'hour_number')] == [5, 12, 17, 9]
    assert [numbers[k] for k in ('upper_num', 'lower_num', 'change_num')] == [2, 3, 1]
    meihua = run_cli('meihua_cast.py', '--datetime', dt.isoformat(), 'time')
    yijing = run_cli('yijing_cast.py', 'time', '--datetime', dt.isoformat())
    assert meihua['main_hex']['name'] == yijing['main_hex']['name'] == '泽火革'
    assert meihua['changed_hex']['name'] == yijing['changed_hex']['name'] == '泽山咸'
    assert meihua['ti_yong']['body_strength'] is None
    assert '体卦当季' not in meihua['summary']


def test_classical_peony_example_uses_snake_year_ordinal():
    # Source 牡丹占: 巳年三月十六卯時 => 25 / 29, 乾上巽下、五爻動.
    numbers = time_numbers(datetime(2025, 4, 13, 6))
    assert [numbers[k] for k in ('year_number', 'month_number', 'day_number', 'hour_number')] == [6, 3, 16, 4]
    assert [numbers[k] for k in ('upper_num', 'lower_num', 'change_num')] == [1, 5, 5]


@pytest.mark.parametrize('script', ['meihua_cast.py', 'yijing_cast.py'])
def test_time_cast_cli_normalizes_offset_before_using_hour(script):
    def cast(instant):
        flags = ['--current-timezone', 'Australia/Sydney', '--datetime', instant]
        argv = [*flags, 'time'] if script.startswith('meihua') else ['time', *flags]
        return run_cli(script, *argv)

    utc = cast('2026-09-06T00:30:00Z')
    local = cast('2026-09-06T10:30:00+10:00')
    assert utc['main_hex'] == local['main_hex']
    assert utc['changed_hex'] == local['changed_hex']


def test_qimen_solar_rollover_preserves_raw_local_time():
    output = run_cli('qimen_cast.py', '--date', '2000-02-15', '--time', '00:10',
                     '--longitude', 100, '--target-timezone', 'Asia/Shanghai')
    assert output['input']['date'] == '2000-02-14'
    assert output['input']['time'] == '22:35'
    assert output['time_context']['local'] == '2000-02-15T00:10:00+08:00'


def test_leap_month_requires_an_explicit_profile_choice():
    dt = datetime(2020, 5, 23, 12)  # 闰四月初一
    with pytest.raises(ValueError, match='闰月'):
        time_numbers(dt)
    assert time_numbers(dt, leap_policy='repeat')['month_number'] == 4
    assert time_numbers(dt, leap_policy='next')['month_number'] == 5
    legacy = time_numbers(dt, 'legacy-gregorian')
    assert legacy['year_number'] == 2020 and legacy['month_number'] == 5
    assert legacy['method_profile']['id'] == 'legacy-gregorian'
