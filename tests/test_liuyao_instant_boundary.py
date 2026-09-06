"""月建 must use real solar-term instants, without moving the local 日建."""
from conftest import run_cli


def cast(date, time, zone):
    return run_cli('liuyao_cast.py', 'coins', '--seed', 7, '--date', date,
                   '--time', time, '--target-timezone', zone)


def test_lichun_in_new_york_changes_month_during_the_previous_local_date():
    # lunar_python 1.4.8 立春: 2026-02-04 04:02:08 UTC+8 = Feb 3 15:02:08 NYC.
    before = cast('2026-02-03', '15:02', 'America/New_York')
    after = cast('2026-02-03', '15:03', 'America/New_York')
    assert before['cast_time']['month_ganzhi'] == '己丑'
    assert after['cast_time']['month_ganzhi'] == '庚寅'
    assert before['cast_time']['year_ganzhi'] == '乙巳'
    assert after['cast_time']['year_ganzhi'] == '丙午'
    assert before['cast_time']['day_ganzhi'] == after['cast_time']['day_ganzhi']
    assert before['raw_lines'] == after['raw_lines']
    assert after['cast_time']['calendar_basis']['year_month'] == 'real_instant_at_UTC+08:00'


def test_same_instant_uses_same_month_from_china_and_new_york():
    ny = cast('2026-02-03', '15:03', 'America/New_York')
    cn = cast('2026-02-04', '04:03', 'Asia/Shanghai')
    assert ny['cast_time']['month_ganzhi'] == cn['cast_time']['month_ganzhi'] == '庚寅'
    assert ny['cast_time']['day_ganzhi'] != cn['cast_time']['day_ganzhi']
    packet = ny['reading_support']['method_rules']
    assert packet['method'] == 'liuyao'
    assert all(r['id'].startswith('liuyao-') for r in packet['rules'])


def test_floating_target_does_not_claim_an_absolute_term_instant():
    chart = run_cli('liuyao_cast.py', 'coins', '--seed', 7,
                    '--date', '2026-02-04', '--time', '04:03')
    assert chart['cast_time']['calendar_basis']['year_month'] == 'floating_calendar_assumption'
    assert chart['cast_time']['calendar_basis']['limitation']
