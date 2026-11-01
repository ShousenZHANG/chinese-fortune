"""B3: four pillars back to the dates and true-solar windows they can come from."""
import sys

from conftest import SCRIPTS, run_cli


def lookup(*args, rc=0):
    return run_cli('pillars_to_dates.py', *args, expect_rc=rc)


def test_known_chart_is_found_with_its_sixty_year_twin():
    out = lookup('--year-pillar', '己卯', '--month-pillar', '丁丑', '--day-pillar', '壬申', '--hour-pillar', '乙巳')
    dates = [c['date'] for c in out['candidates']]
    assert dates == ['1940-01-30', '2000-01-15']
    assert out['candidates'][1]['true_solar_from'] == '2000-01-15 09:00'


def test_window_cut_by_lichun_to_the_minute():
    out = lookup('--year-pillar', '庚辰', '--month-pillar', '戊寅', '--day-pillar', '壬辰', '--hour-pillar', '庚戌')
    cut = next(c for c in out['candidates'] if c['date'] == '2000-02-04')
    assert cut['cut_by_solar_term'] and cut['true_solar_from'] == '2000-02-04 20:41'


def test_zi_hour_lists_early_and_late_windows_and_no_hour_gives_the_day():
    out = lookup('--year-pillar', '己卯', '--month-pillar', '丁丑', '--day-pillar', '壬申', '--hour-pillar', '庚子',
                 '--from-year', '1990', '--to-year', '2010')
    assert [c['window_label'] for c in out['candidates']] == ['早子时', '晚子时']
    whole = lookup('--year-pillar', '己卯', '--month-pillar', '丁丑', '--day-pillar', '壬申',
                   '--from-year', '1990', '--to-year', '2010')
    assert whole['candidates'][0]['window_label'] == '全天'


def test_inconsistent_or_malformed_pillars_are_refused():
    bad = lookup('--year-pillar', '己卯', '--month-pillar', '戊寅', '--day-pillar', '壬申', rc=1)
    assert '五虎遁' in bad['message']
    assert '五鼠遁' in lookup('--year-pillar', '己卯', '--month-pillar', '丁丑', '--day-pillar', '壬申',
                             '--hour-pillar', '甲子', rc=1)['message']
    assert lookup('--year-pillar', '甲丑', '--month-pillar', '丁丑', '--day-pillar', '壬申', rc=1)['ok'] is False
    assert lookup('--year-pillar', '己卯', '--month-pillar', '丁丑', '--day-pillar', '壬申',
                  '--from-year', '1000', rc=1)['ok'] is False


def test_router():
    sys.path.insert(0, str(SCRIPTS))
    from question_router import route
    assert route('我只知道八字，能反查出生日期吗')['flow'] == 'pillars_to_dates'


def test_sxtwl_charts_come_back_to_their_own_dates():
    """Independent calendar: pillars from sxtwl on 150 random non-term days must reverse to the same date."""
    import random

    import pytest
    sxtwl = pytest.importorskip('sxtwl')
    from pillars_to_dates import lookup as reverse
    gz = lambda g: '甲乙丙丁戊己庚辛壬癸'[g.tg] + '子丑寅卯辰巳午未申酉戌亥'[g.dz]  # noqa: E731
    rng = random.Random(20261101)
    checked = 0
    while checked < 150:
        y, m, d, h = rng.randint(1901, 2099), rng.randint(1, 12), rng.randint(1, 28), rng.choice(range(2, 22, 2))
        day = sxtwl.fromSolar(y, m, d)
        if day.hasJieQi() or (m == 2 and d <= 6):
            continue
        out = reverse(gz(day.getYearGZ()), gz(day.getMonthGZ()), gz(day.getDayGZ()), gz(day.getHourGZ(h)), y, y)
        assert f'{y:04d}-{m:02d}-{d:02d}' in [c['date'] for c in out['candidates']], (y, m, d, h)
        checked += 1
