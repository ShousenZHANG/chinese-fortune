"""流年斗君/流月/流日/流时 placement, checked by rule and against iztro-py."""
from datetime import datetime

import pytest
import ziwei_calc
from conftest import run_cli
from ziwei_horoscope import horoscope_layers
from ziwei_palaces import calc_dou_jun

BIRTHS = [(1990, 5, 10, 14, 'male'), (1985, 11, 3, 6, 'female'), (2000, 1, 15, 10, 'male'),
          (1978, 2, 28, 20, 'female'), (1995, 7, 7, 12, 'male'), (1968, 9, 9, 3, 'female'),
          (2020, 6, 5, 9, 'male'), (2020, 6, 10, 16, 'female'), (2004, 3, 21, 1, 'male'),
          (1999, 12, 31, 18, 'female')]
# Leap month halves, both sides of 春节, an ordinary day.
TARGETS = [(2026, 10, 26, 8, 30), (2025, 8, 15, 14, 10), (2025, 7, 30, 10, 0),
           (2026, 2, 16, 6, 0), (2026, 2, 17, 20, 0), (2027, 1, 3, 0, 40)]
PINYIN_STEMS = dict(zip('jia yi bing ding wu ji geng xin ren gui'.split(), '甲乙丙丁戊己庚辛壬癸'))
PINYIN_BRANCHES = dict(zip('zi chou yin mao chen si wu wei shen you xu hai'.split(), '子丑寅卯辰巳午未申酉戌亥'))


def chart(y, m, d, h, gender, *extra):
    args = ['--year', str(y), '--month', str(m), '--day', str(d), '--hour', str(h),
            '--gender', gender, '--time-standard', 'clock', '--brief-palaces', *extra]
    result = ziwei_calc.calculate_ziwei(ziwei_calc.build_parser().parse_args(args))
    assert result['ok'], result
    return result


def test_each_layer_steps_from_the_one_above():
    base = chart(1990, 5, 10, 14, 'male')
    layers = horoscope_layers(datetime(2026, 10, 26, 8, 30), birth_month=4, birth_hour=14,
                              palaces=base['twelve_palaces'])
    order = '子丑寅卯辰巳午未申酉戌亥'
    dou_jun = calc_dou_jun('午', 4, 14)
    assert layers['dou_jun']['branch'] == dou_jun and layers['dou_jun']['passage_id'] == 'ziwei:c002:p0064'
    month_at = order[(order.index(dou_jun) + 9 - 1) % 12]
    day_at = order[(order.index(month_at) + 17 - 1) % 12]
    assert layers['liu_yue']['palace_branch'] == month_at
    assert layers['liu_ri']['palace_branch'] == day_at
    assert layers['liu_shi']['palace_branch'] == order[(order.index(day_at) + 4) % 12]  # 辰时
    assert layers['liu_nian']['transformations']['忌'] == '廉贞'  # 丙年


def test_second_half_of_a_leap_month_counts_as_the_next_month():
    base = chart(1990, 5, 10, 14, 'male', '--horoscope-date', '2025-08-15')
    lunar = base['horoscope']['target']['lunar']
    assert lunar['is_leap_month'] and lunar['month'] == 6 and lunar['effective_month'] == 7
    assert base['horoscope']['liu_yue']['ganzhi'] == '甲申'
    assert base['horoscope']['liu_shi'] is None


def test_late_zi_hour_follows_the_chart_sect():
    late = chart(1990, 5, 10, 14, 'male', '--horoscope-date', '2026-10-26', '--horoscope-time', '23:30')
    rolled = chart(1990, 5, 10, 14, 'male', '--sect', '1', '--horoscope-date', '2026-10-26',
                   '--horoscope-time', '23:30')
    assert late['horoscope']['target']['calendar_day_used'] == '2026-10-26'
    assert rolled['horoscope']['target']['calendar_day_used'] == '2026-10-27'
    assert late['horoscope']['liu_ri']['ganzhi'] != rolled['horoscope']['liu_ri']['ganzhi']


def test_cli_rejects_time_without_date_and_bad_dates():
    base = ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--gender', 'male']
    assert run_cli('ziwei_calc.py', *base, '--horoscope-time', '08:00', expect_rc=1)['ok'] is False
    assert run_cli('ziwei_calc.py', *base, '--horoscope-date', '2026-13-01', expect_rc=1)['ok'] is False
    assert run_cli('ziwei_calc.py', *base)['horoscope'] is None


def _iztro(birth, target):
    astro = pytest.importorskip('iztro_py').astro
    y, m, d, h, gender = birth
    natal = astro.by_solar(f'{y}-{m}-{d}', (h + 1) // 2 % 12, '男' if gender == 'male' else '女')
    ty, tm, td, th, _ = target
    horoscope = natal.horoscope(f'{ty}-{tm}-{td}', (th + 1) // 2 % 12)
    out = {}
    for key, ours in (('yearly', 'liu_nian'), ('monthly', 'liu_yue'), ('daily', 'liu_ri'), ('hourly', 'liu_shi')):
        item = getattr(horoscope, key)
        stem = PINYIN_STEMS[item.heavenly_stem.removesuffix('Heavenly')]
        branch = PINYIN_BRANCHES[item.earthly_branch.removesuffix('Earthly')]
        out[ours] = (stem + branch, natal.palaces[item.index].translate_earthly_branch('zh-CN'))
    return out


@pytest.mark.parametrize('birth', BIRTHS)
def test_layers_agree_with_iztro(birth):
    pytest.importorskip('iztro_py')
    for target in TARGETS:
        ty, tm, td, th, tmin = target
        ours = chart(*birth, '--horoscope-date', f'{ty:04d}-{tm:02d}-{td:02d}',
                     '--horoscope-time', f'{th:02d}:{tmin:02d}')['horoscope']
        expected = _iztro(birth, target)
        got = {k: (ours[k]['ganzhi'], ours[k]['palace_branch']) for k in expected}
        assert got == expected, (birth, target)


def test_layer_stars_and_year_gods_agree_with_iztro_js():
    """Fixture made by iztro (JS) 2.6.1 — iztro-py has no layer stars; see _meta for the generator."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'data' / 'iztro_js_layer_stars.json').read_text(encoding='utf-8'))
    compared = 0
    for case in data['cases']:
        ty, tm, td, th = case['target']
        ours = chart(*case['birth'], '--horoscope-date', f'{ty:04d}-{tm:02d}-{td:02d}',
                     '--horoscope-time', f'{th:02d}:00')['horoscope']
        for key, theirs in case['layers'].items():
            if ours[key] is None:
                assert key == 'da_xian', (case, key)
                continue
            assert ours[key]['ganzhi'] == theirs['ganzhi'], (case['birth'], case['target'], key)
            assert ours[key]['stars'] == theirs['stars'], (case['birth'], case['target'], key)
            compared += 1
        assert ours['liu_nian']['twelve_gods'] == case['layers']['liu_nian']['twelve_gods']
        if ours['da_xian']:
            assert ours['da_xian']['nominal_age'] == case['age']
    assert compared >= 290


def test_decade_layer_before_the_first_decade_is_null_and_nihai_hides_its_transformations():
    young = chart(2020, 6, 5, 9, 'male', '--horoscope-date', '2021-03-01')['horoscope']
    assert young['da_xian'] is None
    nihai = chart(1990, 5, 10, 14, 'male', '--school', 'nihai', '--horoscope-date', '2026-10-26')['horoscope']
    assert nihai['da_xian']['age_range'] and 'transformations' not in nihai['da_xian']
    usual = chart(1990, 5, 10, 14, 'male', '--horoscope-date', '2026-10-26')['horoscope']
    assert usual['da_xian']['transformations']['禄'] == '武曲'    # 己丑大限
