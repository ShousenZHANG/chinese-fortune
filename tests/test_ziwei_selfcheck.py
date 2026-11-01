"""The chart checks itself against rules that tie its parts together; tampering is caught."""
import copy

import pytest
import ziwei_calc
from ziwei_selfcheck import self_check


def chart(*extra):
    args = ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--gender', 'male',
            '--time-standard', 'clock', *extra]
    result = ziwei_calc.calculate_ziwei(ziwei_calc.build_parser().parse_args(args))
    assert result['ok'], result
    return result


@pytest.mark.parametrize('extra', [(), ('--brief-palaces',), ('--school', 'nihai'), ('--year-divide', 'lichun'),
                                   ('--sect', '1')])
def test_a_fresh_chart_passes(extra):
    check = chart(*extra)['self_check']
    assert check['ok'] and check['failed'] == [], check['failed']
    assert len(check['checked']) == 8


def failing(result):
    return {c['name'] for c in self_check(result)['failed']}


def test_moved_main_star_is_caught():
    result = copy.deepcopy(chart())
    palaces = result['twelve_palaces']
    star = next(p for p in palaces if p['main_stars'])['main_stars'].pop()
    next(p for p in palaces if not p['main_stars'])['main_stars'].append(star)
    assert 'main_stars_complete' not in failing(result)          # still 14, just elsewhere
    result['main_stars_positions']['天府'] = '子' if result['main_stars_positions']['天府'] != '子' else '丑'
    assert 'ziwei_tianfu_mirror' in failing(result)


def test_dropped_star_wrong_stem_and_wrong_life_palace_are_caught():
    result = copy.deepcopy(chart())
    result['twelve_palaces'][3]['main_stars'] = []
    result['twelve_palaces'][5]['stem'] = '甲' if result['twelve_palaces'][5]['stem'] != '甲' else '乙'
    result['lunar_date']['month'] = result['lunar_date']['month'] % 12 + 1
    assert {'palace_stems', 'ming_gong_formula'} <= failing(result)
    if any(p['main_stars'] for p in chart()['twelve_palaces'][3:4]):
        assert 'main_stars_complete' in failing(result)


def test_shifted_qing_yang_and_missing_transformation_star_are_caught():
    result = copy.deepcopy(chart())
    result['malefic_stars_positions']['擎羊'] = result['malefic_stars_positions']['陀罗']
    result['four_transformations_native']['忌'] = '不存在的星'
    assert {'lu_yang_tuo', 'sihua_on_chart'} <= failing(result)
