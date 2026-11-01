"""The 39 miscellaneous stars, checked against iztro-py and against the 全书 rules they cite."""
import pytest
import ziwei_calc
from classical_search import get_passage
from ziwei_minor import COMMON_TABLE, SOURCES, xun_kong

BIRTHS = [(1990, 5, 10, 14, 'male'), (1985, 11, 3, 6, 'female'), (2000, 1, 15, 10, 'male'),
          (1978, 2, 28, 20, 'female'), (1995, 7, 7, 12, 'male'), (1968, 9, 9, 3, 'female'),
          (2004, 3, 21, 1, 'male'), (1999, 12, 31, 18, 'female'), (2012, 6, 1, 8, 'male'),
          (1957, 4, 4, 16, 'female'), (2020, 6, 5, 9, 'male'), (2020, 6, 10, 16, 'female'),
          (1983, 8, 30, 22, 'male'), (1971, 1, 26, 4, 'female')]


def chart(y, m, d, h, gender, *extra):
    args = ['--year', str(y), '--month', str(m), '--day', str(d), '--hour', str(h),
            '--gender', gender, '--time-standard', 'clock', *extra]
    result = ziwei_calc.calculate_ziwei(ziwei_calc.build_parser().parse_args(args))
    assert result['ok'], result
    return result


@pytest.mark.parametrize('birth', BIRTHS)
def test_every_miscellaneous_star_sits_where_iztro_puts_it(birth):
    astro = pytest.importorskip('iztro_py').astro
    from iztro_py.data.types import Star
    y, m, d, h, gender = birth
    ours = chart(*birth)['miscellaneous_stars_positions']
    theirs = astro.by_solar(f'{y}-{m}-{d}', (h + 1) // 2 % 12, '男' if gender == 'male' else '女')
    expected = {}
    for palace in theirs.palaces:
        branch = palace.translate_earthly_branch('zh-CN')
        for star in palace.adjective_stars + [s for s in palace.minor_stars if s.type == 'tianma']:
            expected[Star(name=star.name, type=star.type, scope='origin').translate_name('zh-CN')] = branch
    assert len(expected) == 39
    assert ours == expected, birth


def test_every_cited_passage_states_the_rule_it_backs():
    # 全书把年解叫解神 (戌上起子逆数), 截路空亡合为一诀。
    book_name = {'年解': '解神', '截路': '甲己申酉', '空亡': '甲己申酉', '截空': '甲己申酉'}
    for star, passage_id in SOURCES.items():
        number = int(passage_id[-4:])
        heading = get_passage(f'{passage_id[:-4]}{number - 1:04d}')['text']   # 诀名有时独占上一段
        assert book_name.get(star, star) in heading + get_passage(passage_id)['text'], star


def test_basis_marks_stars_without_a_verse_as_the_common_table():
    basis = chart(1990, 5, 10, 14, 'male')['miscellaneous_stars_basis']
    assert basis['三台'] == 'ziwei:c002:p0047'
    assert basis['天巫'] == COMMON_TABLE
    assert len(basis) == 39


def test_book_rules_by_hand():
    result = chart(1990, 5, 10, 14, 'male')          # 庚午年 四月 十六 未时
    stars, lucky = result['miscellaneous_stars_positions'], result['lucky_stars_positions']
    order = '子丑寅卯辰巳午未申酉戌亥'
    month, day = result['lunar_date']['month'], result['lunar_date']['day']
    assert stars['天刑'] == order[(order.index('酉') + month - 1) % 12]   # 酉上起正月顺数
    assert stars['三台'] == order[(order.index(lucky['左辅']) + day - 1) % 12]
    assert stars['八座'] == order[(order.index(lucky['右弼']) - day + 1) % 12]
    assert stars['台辅'] == '丑' and stars['封诰'] == '酉'               # 午/寅起子顺至未时
    assert stars['截路'] == '午' and stars['空亡'] == '未'               # 乙庚午未
    palaces = {p['name']: p['branch'] for p in result['twelve_palaces']}
    assert stars['天伤'] == palaces['奴仆宫'] and stars['天使'] == palaces['疾厄宫']


@pytest.mark.parametrize('stem,branch,expected', [('甲', '子', '戌'), ('乙', '丑', '亥'),
                                                  ('庚', '午', '戌'), ('癸', '亥', '丑')])
def test_xun_kong_takes_the_empty_branch_with_the_year_polarity(stem, branch, expected):
    assert xun_kong(stem, branch) == expected
