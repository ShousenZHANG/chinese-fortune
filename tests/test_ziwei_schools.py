"""Twelve gods, seven-level brightness and school options, checked against iztro-py where it applies."""
import pytest
import ziwei_calc

BIRTHS = [(1990, 5, 10, 14, 'male'), (1985, 11, 3, 6, 'female'), (2000, 1, 15, 10, 'male'),
          (1978, 2, 28, 20, 'female'), (1995, 7, 7, 12, 'male'), (1968, 9, 9, 3, 'female'),
          (2004, 3, 21, 1, 'male'), (1999, 12, 31, 18, 'female'), (2012, 6, 1, 8, 'male'), (1957, 4, 4, 16, 'female')]
# iztro's names that differ from this project's: 飞廉 is written the same; 官府/官符 and 岁驿 match.
ALIASES = {'驿马': '岁驿'}
# iztro-py 0.5.0 differs from iztro (JS) 2.6.3 at three cells; the table follows iztro 2.6.3.
IZTRO_JS = {('太阴', '酉'): '旺', ('太阳', '酉'): '平', ('七杀', '酉'): '旺'}


def chart(y, m, d, h, gender, *extra):
    args = ['--year', str(y), '--month', str(m), '--day', str(d), '--hour', str(h),
            '--gender', gender, '--time-standard', 'clock', *extra]
    result = ziwei_calc.calculate_ziwei(ziwei_calc.build_parser().parse_args(args))
    assert result['ok'], result
    return result


@pytest.mark.parametrize('birth', BIRTHS)
def test_twelve_gods_and_brightness_agree_with_iztro(birth):
    astro = pytest.importorskip('iztro_py').astro
    from iztro_py.data.types import Star
    y, m, d, h, gender = birth
    ours = {p['branch']: p for p in chart(*birth)['twelve_palaces']}
    theirs = astro.by_solar(f'{y}-{m}-{d}', (h + 1) // 2 % 12, '男' if gender == 'male' else '女')
    for palace in theirs.palaces:
        branch = palace.translate_earthly_branch('zh-CN')
        gods = ours[branch]['twelve_gods']
        expected = {'changsheng': palace.changsheng12, 'boshi': palace.boshi12,
                    'jiangqian': ALIASES.get(palace.jiangqian12, palace.jiangqian12), 'suiqian': palace.suiqian12}
        assert gods == expected, (birth, branch)
        for star in palace.major_stars:
            name = Star(name=star.name, type='major', scope='origin').translate_name('zh-CN')
            mine = next(s['brightness'] for s in ours[branch]['main_stars'] if s['name'] == name)
            expected_level = IZTRO_JS.get((name, branch), star.brightness or None)
            assert mine == expected_level, (birth, branch, name)


def test_changsheng_follows_the_bureau_and_direction_in_the_book():
    result = chart(1990, 5, 10, 14, 'male')
    start = {2: '申', 3: '亥', 4: '巳', 5: '申', 6: '寅'}[result['wuxing_ju']['number']]
    palace = next(p for p in result['twelve_palaces'] if p['branch'] == start)
    assert palace['twelve_gods']['changsheng'] == '长生'
    source = result['twelve_gods_sources']['changsheng']
    assert 'ziwei:c002:p0057' in source and '火局命寅起长生' in source and '男命顺数、女命逆数' in source


def test_leap_month_school_moves_the_chart_only_when_it_should():
    early = {s: chart(2020, 6, 5, 9, 'male', '--leap-month', s)['ming_gong']['branch'] for s in ('split', 'next', 'prev')}
    late = {s: chart(2020, 6, 10, 16, 'female', '--leap-month', s)['ming_gong']['branch'] for s in ('split', 'next', 'prev')}
    assert early['split'] == early['prev'] != early['next']     # 闰四月十四: split keeps 四月
    assert late['split'] == late['next'] != late['prev']        # 闰四月十九: split moves to 五月
    assert '闰' in ' '.join(chart(2020, 6, 5, 9, 'male')['notes'])


def test_geng_school_changes_only_the_geng_row_and_is_reported():
    default = chart(1990, 5, 10, 14, 'male')
    variant = chart(1990, 5, 10, 14, 'male', '--geng-sihua', 'yang-wu-tong-yin')
    assert default['four_transformations_native']['忌'] == '天同'
    assert variant['four_transformations_native']['忌'] == '太阴'
    assert variant['school']['geng_sihua'] == 'yang-wu-tong-yin'
    other = chart(2000, 1, 15, 10, 'male', '--geng-sihua', 'yang-wu-tong-yin')
    assert other['four_transformations_native'] == chart(2000, 1, 15, 10, 'male')['four_transformations_native']


def test_project_four_level_brightness_is_still_available():
    old = chart(1990, 5, 10, 14, 'male', '--brightness', 'project4')
    assert old['school']['brightness'] == 'project4'
    assert any('四级' in note for note in old['notes'])
