"""B6: a deceased person's luck and annual years stop at the year of death."""
from conftest import run_cli

BASE = ['--year', '1940', '--month', '1', '--day', '30', '--hour', '10', '--gender', 'male',
        '--timezone', 'Asia/Shanghai']


def test_luck_and_years_stop_at_death():
    chart = run_cli('bazi_calc.py', *BASE, '--death-date', '1995-06-01', '--as-of-year', '1993',
                    '--no-shensha', '--no-geju', '--no-yongshen')
    assert chart['deceased']['year'] == 1995
    assert [c['start_year'] for c in chart['da_yun']][-1] <= 1995 and chart['da_yun'][-1]['cut_at_death_year'] == 1995
    assert [r['year'] for r in chart['liu_nian']] == [1993, 1994, 1995]
    living = run_cli('bazi_calc.py', *BASE, '--as-of-year', '1993', '--no-shensha', '--no-geju', '--no-yongshen')
    assert living['deceased'] is None and len(living['da_yun']) > len(chart['da_yun'])


def test_reading_gives_age_at_death_not_today():
    out = run_cli('bazi_reading.py', *BASE, '--death-date', '1995-06-01', '--current-timezone', 'Asia/Shanghai',
                  '--request-time', '2026-11-01T02:00:00Z', '--view', 'compact')
    age = out['chart_facts']['age_at_request']
    assert age['deceased'] is True and age['full_years'] == 55 and '享年' in age['say']
    assert out['chart_facts']['da_yun'][-1]['cut_at_death_year'] == 1995


def test_bad_death_dates():
    assert run_cli('bazi_calc.py', *BASE, '--death-date', '1930-01-01', expect_rc=1)['ok'] is False
    assert run_cli('bazi_calc.py', *BASE, '--death-date', 'soon', expect_rc=1)['ok'] is False
