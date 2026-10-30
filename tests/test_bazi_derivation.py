"""Derivation steps restate chart facts in the order a person checks them."""
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading, render_facts
from reading_views import compact_reading

BASE = ['--year', '1990', '--month', '5', '--day', '10', '--gender', 'male', '--timezone', 'Asia/Shanghai']


def reading(*extra, question='看格局'):
    return prepare_reading(calculate_bazi(build_parser().parse_args([*BASE, *extra])), question)


def test_steps_follow_the_chart_they_explain():
    result = reading('--hour', '14', '--longitude', '120')
    steps = {d['step']: d for d in result['derivation']}
    assert list(steps) == ['出生时刻', '年柱与月柱', '真太阳时', '日柱', '时柱', '大运方向与起运']
    pillars = result['chart_facts']['four_pillars']
    assert steps['日柱']['result'] == pillars['day']['ganzhi'] == '乙亥'
    assert steps['时柱']['result'] == pillars['hour']['ganzhi'] == '癸未'
    assert '立夏' in steps['年柱与月柱']['how'] and '芒种' in steps['年柱与月柱']['how']
    assert '14:00 → 13:04' in steps['真太阳时']['how'] and '夏令时' in steps['真太阳时']['how']
    assert '五鼠遁子时起丙' in steps['时柱']['how'] and '晚子时' not in steps['时柱']['how']
    assert '顺排' in steps['大运方向与起运']['how']


def test_unknown_hour_and_clock_time_are_stated_not_filled():
    unknown = {d['step']: d for d in reading()['derivation']}
    assert unknown['时柱']['result'] == '未定'
    clock = {d['step']: d for d in reading('--hour', '14', '--time-standard', 'clock')['derivation']}
    assert clock['真太阳时']['result'] == '未校正'


def test_compact_keeps_steps_only_when_asked_and_markdown_shows_them():
    plain = reading('--hour', '14', '--longitude', '120')
    asked = reading('--hour', '14', '--longitude', '120', question='日柱怎么算的，起运怎么来的')
    assert 'derivation' in plain and 'derivation' not in compact_reading(plain)
    assert compact_reading(asked)['derivation'] == asked['derivation']
    assert '推算过程：' in render_facts(asked) and '推算过程：' not in render_facts(plain)


def test_clock_standard_uses_the_birth_clock_and_a_fixed_offset_is_stated():
    clock = {d['step']: d for d in reading('--hour', '14', '--minute', '20', '--time-standard', 'clock')['derivation']}
    assert clock['时柱']['how'].startswith('14:20 属未时')
    bare = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '1997', '--month', '8', '--day', '20', '--hour', '14', '--minute', '20', '--gender', 'male',
         '--time-standard', 'clock'])), '时柱怎么算')
    steps = {d['step']: d for d in bare['derivation']}
    assert '固定偏移 UTC+8' in steps['出生时刻']['how'] and 'UTC+0' not in steps['出生时刻']['how']


def test_summer_time_is_named_as_summer_time_not_as_a_longitude_gap():
    steps = {d['step']: d for d in reading('--hour', '14', '--longitude', '120')['derivation']}
    how = steps['真太阳时']['how']
    assert '标准时经线 120°' in how and '差 0 分钟' in how and '夏令时' in how and '14:00 → 13:04' in how


def test_tools_say_offsets_and_candidate_windows_in_words():
    known = reading('--hour', '10', '--minute', '30', '--longitude', '116.4')
    assert known['chart_facts']['true_solar_time']['say'].startswith('真太阳时的读数比钟表少')
    unknown = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2000', '--month', '1', '--day', '15', '--gender', 'male', '--timezone', 'Asia/Shanghai',
         '--longitude', '116.4'])), '看四柱')
    day = unknown['chart_facts']['four_pillars']['day']
    assert [w['ganzhi'] for w in day['candidate_windows']] == ['辛未', '壬申']
    assert day['say'].startswith('钟表 00:00–00:23 出生为辛未日')
    term = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2000', '--month', '2', '--day', '4', '--gender', 'male', '--timezone', 'Asia/Shanghai'])), '看四柱')
    assert '不按农历新年' in term['chart_facts']['four_pillars']['year']['say']


def test_repeated_summer_time_hour_keeps_both_folds_and_clock_basis_is_named():
    chicago = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2024', '--month', '11', '--day', '3', '--gender', 'male', '--timezone', 'America/Chicago',
         '--longitude', '-102.88'])), '看四柱')
    day = chicago['chart_facts']['four_pillars']['day']
    repeated = [w for w in day['candidate_windows'] if not w['ganzhi']]
    assert repeated == [{'ganzhi': None, 'clock': '01:00–01:34', 'repeated_clock': {'first': '庚午', 'second': '辛未'}}]
    assert '重复时段' in day['say']
    clock = prepare_reading(calculate_bazi(build_parser().parse_args(
        ['--year', '2000', '--month', '1', '--day', '15', '--gender', 'male', '--timezone', 'Asia/Shanghai',
         '--longitude', '116.4', '--time-standard', 'clock', '--sect', '1'])), '看四柱')
    say = clock['chart_facts']['four_pillars']['day']['say']
    assert '钟表时间' in say and '真太阳时' not in say


def test_summer_time_hint_says_to_drop_city_as_well():
    result = calculate_bazi(build_parser().parse_args(
        ['--year', '1990', '--month', '5', '--day', '10', '--hour', '13', '--minute', '30', '--gender', 'female',
         '--city', '北京']))
    note = result['timezone']['note']
    assert '--city' in note and '--longitude' in note
    fixed = calculate_bazi(build_parser().parse_args(
        ['--year', '1990', '--month', '5', '--day', '10', '--hour', '13', '--minute', '30', '--gender', 'female',
         '--tz', '8', '--longitude', '116.4']))
    assert fixed['four_pillars']['hour']['ganzhi'] == '癸未'
