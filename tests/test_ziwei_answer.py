"""ziwei say lines and the per-palace focus block."""
import ziwei_calc
from conftest import run_cli


def chart(*extra):
    args = ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--gender', 'male',
            '--time-standard', 'clock', *extra]
    result = ziwei_calc.calculate_ziwei(ziwei_calc.build_parser().parse_args(args))
    assert result['ok'], result
    return result


def test_say_lines_state_life_palace_transformations_and_school():
    say = chart('--brief-palaces')['say']
    assert say[0].startswith('命宫在戌（丙戌），主星巨门（陷）')
    assert '太阳化禄在财帛宫' in say[2] and '天同化忌在迁移宫' in say[2]
    assert say[-1].startswith('排盘口径：闰月十五日前后分月')
    assert '倪海厦派预设' in chart('--school', 'nihai')['say'][-1]


def test_patterns_in_say_carry_source_and_breaking():
    for birth in [(1977, 11, 2, 22), (2000, 1, 15, 10), (1985, 11, 3, 6)]:
        result = run_cli('ziwei_calc.py', '--year', birth[0], '--month', birth[1], '--day', birth[2],
                         '--hour', birth[3], '--gender', 'male')
        for pattern in result['patterns']:
            line = next(x for x in result['say'] if x.startswith(pattern['name'] + '：'))
            assert (pattern['passage_id'] or '现代通行') in line
            assert ('减力条件' in line) == bool(pattern['breaking'])


def test_focus_palace_accepts_everyday_words_and_lays_out_the_palace():
    focus = chart('--focus-palace', '婚姻')['focus']
    assert focus['palace'] == '夫妻宫' and focus['branch'] == '申'
    assert focus['opposite']['palace'] == '官禄宫'
    assert [t['palace'] for t in focus['trines']] == ['福德宫', '迁移宫']
    assert focus['sihua_here'] == ['太阴化科'] and focus['search_queries'] == ['天机 夫妻', '太阴 夫妻']
    assert chart('--focus-palace', '事业', '--brief-palaces')['focus']['palace'] == '官禄宫'
    assert chart()['focus'] is None


def test_unknown_focus_palace_is_an_input_error():
    bad = run_cli('ziwei_calc.py', '--year', 1990, '--month', 5, '--day', 10, '--hour', 14, '--gender', 'male',
                  '--focus-palace', '桃花', expect_rc=1)
    assert bad['ok'] is False and '桃花' in bad['message']
