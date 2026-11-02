"""Fixed external computations check fictional target dates and all active layer gods."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from conftest import run_cli
from ziwei_calc import build_parser, calculate_ziwei
from ziwei_gods import year_gods

DATA = Path(__file__).parent / 'data'
RENHUAI = json.loads((DATA / 'v60_ziwei_renhuai_gods.json').read_text(encoding='utf-8'))
IZTRO = json.loads((DATA / 'v60_ziwei_iztro_layers.json').read_text(encoding='utf-8'))
CALENDAR = json.loads((DATA / 'v60_ziwei_calendar.json').read_text(encoding='utf-8'))
LAYERS = ('da_xian', 'liu_nian', 'liu_yue', 'liu_ri', 'liu_shi')


def chart(target, clock=None, *, divide='lunar-new-year', sect=2, birth=(2000, 1, 15, 10, 'male'), extra=()):
    year, month, day, hour, gender = birth
    argv = ['--year', str(year), '--month', str(month), '--day', str(day), '--hour', str(hour),
            '--gender', gender, '--time-standard', 'clock', '--sect', str(sect), '--year-divide', divide,
            '--horoscope-date', target, '--no-patterns', *extra]
    if clock:
        argv += ['--horoscope-time', clock]
    result = calculate_ziwei(build_parser().parse_args(argv))
    assert result['ok'], result
    return result['horoscope']


@pytest.mark.parametrize('case', CALENDAR['cases'], ids=lambda case: case['target'] + f"-sect{case['sect']}")
def test_selected_annual_pair_uses_original_target_clock_and_keeps_actual_lunar_facts(case):
    target, clock = case['target'].split('T')
    result = chart(target, clock, divide='lichun', sect=case['sect'])
    assert result['liu_nian']['ganzhi'] == case['selected_year']
    assert result['target']['year_divide'] == 'lichun'
    lunar = result['target']['lunar']
    assert lunar['year'] == case['lunar_year']
    assert lunar['year_ganzhi'] == case['lunar_year_ganzhi']
    assert (lunar['month'], lunar['day'], lunar['is_leap_month']) == (
        case['lunar_month'], case['lunar_day'], case['is_leap_month'])


@pytest.mark.parametrize('case', IZTRO['cases'], ids=lambda case: f"{case['birth'][0]}-{case['target']}-{case['year_divide']}")
def test_year_and_dependent_palace_anchors_match_executed_iztro_263(case):
    result = chart(case['target'], case['clock'], divide=case['year_divide'], birth=tuple(case['birth']))
    for key in LAYERS:
        ours, theirs = result[key], case['layers'][key]
        assert ours['palace_branch'] == theirs['palace_branch'], key
        if key != 'liu_yue' or case['year_divide'] == 'lunar-new-year':
            assert ours['ganzhi'] == theirs['ganzhi'], key
            assert ours['transformations'] == theirs['transformations'], key
            assert ours['stars'] == theirs['stars'], key
    assert result['liu_nian']['twelve_gods'] == case['layers']['liu_nian']['twelve_gods']
    assert result['da_xian']['nominal_age'] == case['nominal_age']
    assert result['target']['age_basis'] == result['da_xian']['age_basis'] == 'lunar-new-year'


def test_annual_switch_changes_month_stem_with_lunar_month_and_age_held_fixed():
    lunar = chart('2026-02-10', '10:30')
    lichun = chart('2026-02-10', '10:30', divide='lichun')
    assert lunar['liu_nian']['ganzhi'] == '乙巳'
    assert lichun['liu_nian']['ganzhi'] == '丙午'
    assert lunar['target']['lunar'] == lichun['target']['lunar']
    assert lichun['target']['lunar']['year_ganzhi'] == '乙巳'
    assert lunar['liu_yue']['ganzhi'] == '己丑'
    assert lichun['liu_yue']['ganzhi'] == '辛丑'
    assert lichun['liu_yue']['transformations'] == {'禄': '巨门', '权': '太阳', '科': '文曲', '忌': '文昌'}
    assert lichun['liu_nian']['stars']['年解'] == '辰'
    assert lunar['da_xian'] == lichun['da_xian']
    assert lichun['da_xian']['nominal_age'] == 27
    assert lunar['liu_ri']['ganzhi'] == lichun['liu_ri']['ganzhi']
    assert lunar['liu_shi']['ganzhi'] == lichun['liu_shi']['ganzhi']
    assert lunar['dou_jun']['branch'] != lichun['dou_jun']['branch']


def test_date_only_target_discloses_noon_on_the_boundary_date():
    result = run_cli('ziwei_calc.py', '--year', 2000, '--month', 1, '--day', 15, '--hour', 10,
                     '--gender', 'male', '--time-standard', 'clock', '--year-divide', 'lichun',
                     '--horoscope-date', '2000-02-04')['horoscope']
    assert result['target']['clock'] == '2000-02-04'
    assert result['target']['clock_used'] == '2000-02-04T12:00'
    assert result['target']['clock_representative'] == '12:00'
    assert result['liu_nian']['ganzhi'] == '己卯'
    assert result['liu_shi'] is None
    assert any('12:00' in value for value in result['conventions'])


@pytest.mark.parametrize('case', RENHUAI['cases'], ids=lambda case: case['branch'])
def test_existing_god_placement_matches_fixed_renhuai_positions_with_explicit_naming_difference(case):
    actual = year_gods(case['branch'])
    assert actual['jiangqian'] == case['jiangqian']
    for palace, god in case['suiqian'].items():
        assert actual['suiqian'][palace] == ('大耗' if god == '岁破' else god)


def test_each_active_layer_anchors_gods_on_its_own_branch_and_discloses_exact_source():
    expected = {case['branch']: case for case in RENHUAI['cases']}
    used_day_branches = set()
    for offset in range(12):
        day = date(2026, 10, 20) + timedelta(days=offset)
        result = chart(day.isoformat(), '10:30')
        for key in LAYERS:
            layer = result[key]
            branch = layer['ganzhi'][1]
            assert layer['twelve_gods']['jiangqian'] == expected[branch]['jiangqian']
            for palace, god in expected[branch]['suiqian'].items():
                assert layer['twelve_gods']['suiqian'][palace] == ('大耗' if god == '岁破' else god)
            basis = layer['twelve_gods_basis']
            assert basis['branch'] == branch and basis['anchor'] == 'layer_ganzhi_branch'
            assert basis['source']['commit'] == RENHUAI['source']['commit']
            assert basis['source']['file'] == RENHUAI['source']['file']
            assert basis['naming_difference']['position'] == 7
            assert basis['naming_difference']['project'] == '大耗'
            assert basis['naming_difference']['source'] == '岁破'
        used_day_branches.add(result['liu_ri']['ganzhi'][1])
    assert len(used_day_branches) == 12


def test_absent_layers_stay_null_and_nihai_keeps_its_transformations_policy():
    young = chart('2021-03-01', birth=(2020, 6, 5, 9, 'male'))
    assert young['da_xian'] is None and young['liu_shi'] is None
    nihai = chart('2026-10-26', extra=('--school', 'nihai'))
    assert nihai['da_xian']['twelve_gods'] and 'transformations' not in nihai['da_xian']


def test_explicit_target_clock_at_late_zi_does_not_synthesize_the_lichun_year():
    for sect in (1, 2):
        result = chart('2009-02-03', '23:55', divide='lichun', sect=sect)
        assert result['liu_nian']['ganzhi'] == '戊子'
        assert result['target']['lunar']['year_ganzhi'] == '己丑'
        assert result['target']['clock_used'] == datetime(2009, 2, 3, 23, 55).isoformat(timespec='minutes')


@pytest.mark.parametrize(('day', 'clock', 'term', 'annual'), [
    ('2024-02-04', '16:27', '2024-02-04 16:27:07', '癸卯'),
    ('2024-02-04', '16:28', '2024-02-04 16:27:07', '甲辰'),
    ('2026-02-04', '04:02', '2026-02-04 04:02:08', '乙巳'),
    ('2026-02-04', '04:03', '2026-02-04 04:02:08', '丙午'),
])
def test_fixed_calendar_contract_discloses_minutes_where_independent_models_disagree(day, clock, term, annual):
    """These are pinned lunar_python 1.4.8 policy facts, not independent astronomical agreement."""
    result = chart(day, clock, divide='lichun')
    assert result['liu_nian']['ganzhi'] == annual
    assert result['target']['lichun_clock'] == term
    assert 'lunar_python' in result['target']['year_boundary_provider']
    assert any('不同历算在交节附近可能跨分钟' in item for item in result['conventions'])
