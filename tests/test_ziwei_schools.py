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


def test_kui_yue_schools_differ_only_for_geng_xin_ren_gui():
    for year in range(1984, 1994):   # one of each year stem
        base = chart(year, 6, 15, 10, 'male')
        stem = base['year_stem']
        for school in ('quanshu-1', 'quanshu-2', 'zhong-yiming'):
            other = chart(year, 6, 15, 10, 'male', '--kui-yue', school)['lucky_stars_positions']
            same = (other['天魁'], other['天钺']) == (base['lucky_stars_positions']['天魁'],
                                                    base['lucky_stars_positions']['天钺'])
            assert same or stem in '庚辛壬癸', (year, school)
    xin = chart(1991, 6, 15, 10, 'male', '--kui-yue', 'quanshu-1')     # 辛未年: 六辛逢虎马
    assert (xin['lucky_stars_positions']['天魁'], xin['lucky_stars_positions']['天钺']) == ('寅', '午')


def test_month_tian_ma_follows_the_birth_month_branch():
    result = chart(1990, 5, 10, 14, 'male', '--tian-ma', 'month')    # 四月 = 巳月, 巳酉丑马在亥
    assert result['lunar_date']['month'] == 4
    assert result['miscellaneous_stars_positions']['天马'] == '亥'
    assert chart(1990, 5, 10, 14, 'male')['miscellaneous_stars_positions']['天马'] == '申'  # 午年


def test_zhongzhou_swaps_tianshi_and_tianshang_for_yin_male_and_yang_female():
    yang_male = chart(1990, 5, 10, 14, 'male')                         # 午年阳男: 不换
    assert chart(1990, 5, 10, 14, 'male', '--tianshi-tianshang', 'zhongzhou')['miscellaneous_stars_positions'] \
        == yang_male['miscellaneous_stars_positions']
    default = chart(1990, 5, 10, 14, 'female')['miscellaneous_stars_positions']
    swapped = chart(1990, 5, 10, 14, 'female', '--tianshi-tianshang', 'zhongzhou')['miscellaneous_stars_positions']
    assert (swapped['天伤'], swapped['天使']) == (default['天使'], default['天伤'])


def test_jie_kong_single_and_zhanyan():
    single = chart(1990, 5, 10, 14, 'male', '--jie-kong', 'single')['miscellaneous_stars_positions']
    assert single['截空'] == '未' and '截路' not in single                # 乙庚午未, 庚取阴支
    gui = chart(1993, 6, 15, 10, 'male', '--jie-kong', 'zhanyan')['miscellaneous_stars_positions']
    assert gui['截空'] == '亥'                                           # 癸年占验派取亥, 单星取丑
    assert chart(1993, 6, 15, 10, 'male', '--jie-kong', 'single')['miscellaneous_stars_positions']['截空'] == '丑'


def test_changsheng_variants():
    earth = next(b for b in BIRTHS for r in [chart(*b)] if r['wuxing_ju']['number'] == 5)
    start = {p['twelve_gods']['changsheng']: p['branch']
             for p in chart(*earth, '--changsheng', 'huo-tu')['twelve_palaces']}['长生']
    assert start == '寅'
    female = chart(1991, 5, 10, 14, 'female', '--changsheng-direction', 'gender')   # 阴女: 通行顺, 字面逆
    usual = chart(1991, 5, 10, 14, 'female')
    order = '子丑寅卯辰巳午未申酉戌亥'

    def step(result):
        gods = {p['twelve_gods']['changsheng']: p['branch'] for p in result['twelve_palaces']}
        return (order.index(gods['沐浴']) - order.index(gods['长生'])) % 12
    assert step(usual) == 1 and step(female) == 11


def test_geng_variants_with_tianxiang_ji():
    result = chart(1990, 5, 10, 14, 'male', '--geng-sihua', 'yang-wu-fu-xiang')
    assert result['four_transformations_native'] == {'禄': '太阳', '权': '武曲', '科': '天府', '忌': '天相'}


def test_lichun_year_divide_moves_the_year_between_lichun_and_new_year():
    # 2021-02-05: 立春 (2/3) 之后、春节 (2/12) 之前 —— 农历仍是庚子年, 立春口径已是辛丑年。
    lunar_year = chart(2021, 2, 5, 10, 'male')
    lichun_year = chart(2021, 2, 5, 10, 'male', '--year-divide', 'lichun')
    assert (lunar_year['year_stem'], lunar_year['year_branch']) == ('庚', '子')
    assert (lichun_year['year_stem'], lichun_year['year_branch']) == ('辛', '丑')
    assert lichun_year['four_transformations_native']['禄'] == '巨门'
    assert any('立春' in note for note in lichun_year['notes'])


def test_nihai_preset_and_explicit_override():
    nihai = chart(2020, 6, 10, 16, 'female', '--school', 'nihai')           # 闰四月十九
    assert nihai['school']['leap_month'] == 'next' and nihai['school']['preset'] == 'nihai'
    assert all(not p['self_transformations'] for p in nihai['twelve_palaces'])
    assert all('transformations' not in step for step in nihai['da_xian'])
    assert nihai['four_transformations_native']
    early = chart(2020, 6, 5, 9, 'male', '--school', 'nihai')               # 闰四月十四: 倪派也按五月
    assert early['lunar_date']['month'] == 5
    override = chart(2020, 6, 5, 9, 'male', '--school', 'nihai', '--leap-month', 'split')
    assert override['lunar_date']['month'] == 4
    assert any('倪海厦' in note for note in nihai['notes'])
