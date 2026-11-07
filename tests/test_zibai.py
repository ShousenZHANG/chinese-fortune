"""紫白九星：年、月入中按《协纪辨方书》卷八的表逐格复算，飞布与书中例子一致，坐向接二十四山合同。"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from classical_search import get_passage
from zibai import PALACE_ORDER, STARS, layout, month_center, year_center, zibai

SKILL = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'
STAR = re.compile(r'([一二三四五六七八九])[白黑碧緑绿黄赤紫]')
# 转录里「己丑」「己亥」作「巳丑」「巳亥」；在天干位置的巳按己读。
GANZHI = re.compile(r'([甲乙丙丁戊己巳庚辛壬癸])([子丑寅卯辰巳午未申酉戌亥])')
STEMS, BRANCHES = '甲乙丙丁戊己庚辛壬癸', '子丑寅卯辰巳午未申酉戌亥'
NUMERAL = '一二三四五六七八九'


def _text(pid: str) -> str:
    return get_passage(pid)["text"]


def _index(stem: str, branch: str) -> int:
    stem = '己' if stem == '巳' else stem
    return next(i for i in range(60) if STEMS[i % 10] == stem and BRANCHES[i % 12] == branch)


def test_year_table_in_the_book_is_reproduced_cell_by_cell():
    text = _text('xieji:c008:p0024')
    table = text.split('三元太嵗所在', 1)[1].split('攷原', 1)[0]
    rows, cells = [], 0
    for token in re.finditer(r'[一二三四五六七八九][白黑碧緑黄赤紫]|[甲乙丙丁戊己巳庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]', table):
        star = STAR.fullmatch(token.group())
        if star:
            if not rows or rows[-1][1]:
                rows.append(([], []))
            rows[-1][0].append(NUMERAL.index(star.group(1)) + 1)
        else:
            stem, branch = GANZHI.fullmatch(token.group()).groups()
            rows[-1][1].append(_index(stem, branch))
    assert len(rows) == 9
    for stars, years in rows:
        assert len(stars) == 3
        for yuan, expected in enumerate(stars):
            for index in years:
                assert year_center(yuan, index) == expected, (yuan, index)
                cells += 1
    assert cells == 180  # 三元各六十年


def test_month_table_in_the_book_is_reproduced_cell_by_cell():
    text = _text('xieji:c008:p0025').split('攷原', 1)[0]
    stars = [NUMERAL.index(m.group(1)) + 1 for m in STAR.finditer(text)]
    assert len(stars) == 36
    for month in range(12):
        for group in range(3):  # 子午卯酉、辰戌丑未、寅申巳亥
            assert month_center(group, month) == stars[month * 3 + group], (group, month)


def test_flying_order_matches_the_kangxi_example():
    # 「如康熙二十三年甲子一白入中宫二黑在乾三碧在兌四緑在艮五黄在離六白在坎七赤在坤八白在震九紫在巽」
    assert layout(1) == dict(zip(PALACE_ORDER, STARS))
    assert layout(1)['巽'] == '九紫' and layout(1)['乾'] == '二黑'


def test_month_example_of_the_year_star_in_the_month_chart():
    # xieji:c008:p0038：下元甲子年七赤为太岁一星，子年六月三碧入中，顺寻七赤到离九。
    assert year_center(2, 0) == 7 and month_center(0, 5) == 3
    assert layout(3)['离'] == '七赤'


def test_a_date_gives_year_and_month_with_sources_and_no_star_judgements():
    out = zibai('2026-11-08')
    assert out['calendar']['year_ganzhi'] == '丙午' and out['calendar']['month_branch'] == '亥'
    assert out['year']['yuan'] == '下元' and out['year']['center'] == '一白'
    assert out['month']['center'] == '八白'
    assert out['month']['year_star_palace'] == next(p for p, s in out['month']['palaces'].items() if s == '一白')
    cited = {s['passage_id'] for s in out['sources']}
    assert {'xieji:c008:p0024', 'xieji:c008:p0025', 'xieji:c034:p0024'} <= cited
    for source in out['sources']:
        assert source['quote'] in _text(source['passage_id']), source
    assert '吉' not in json.dumps(out['year'], ensure_ascii=False)
    assert any('日' in item['item'] and '时' in item['item'] for item in out['not_computed'])


def test_year_starts_at_lichun_and_a_boundary_day_without_time_keeps_both():
    before = zibai('2026-02-04', '03:00')
    after = zibai('2026-02-04', '12:00')
    assert before['calendar']['year_ganzhi'] == '乙巳' and after['calendar']['year_ganzhi'] == '丙午'
    assert before['year']['center'] == '二黑' and after['year']['center'] == '一白'
    both = zibai('2026-02-04')
    assert both['boundary']['jie'] == '立春' and 'year' not in both
    assert [c['calendar']['year_ganzhi'] for c in both['candidates']] == ['乙巳', '丙午']


def test_sitting_mountain_gives_both_palaces_and_their_stars():
    out = zibai('2026-11-08', sitting=['子'])
    sit, face = out['directions']
    assert (sit['role'], sit['mountain'], sit['palace']) == ('坐', '子', '坎')
    assert (face['role'], face['mountain'], face['palace']) == ('向', '午', '离')
    assert sit['year_star'] == out['year']['palaces']['坎'] and face['month_star'] == out['month']['palaces']['离']
    assert all(isinstance(d['zibai_to_direction'], bool) for d in out['directions'])


def test_lunar_python_nine_stars_agree_over_two_centuries():
    from lunar_python import Solar
    for year in range(1900, 2101, 7):
        for month, day in ((3, 15), (8, 20), (12, 20)):
            lunar = Solar.fromYmdHms(year, month, day, 12, 0, 0).getLunar()
            out = zibai(f'{year}-{month:02d}-{day:02d}', '12:00')
            assert out['year']['center'][0] == str(lunar.getYearNineStar().getNumber()).translate(
                str.maketrans('123456789', NUMERAL)), (year, month)
            assert out['month']['center'][0] == str(lunar.getMonthNineStar().getNumber()).translate(
                str.maketrans('123456789', NUMERAL)), (year, month)


def test_cli_and_input_errors():
    done = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/zibai.py', '--date', '2026-11-08', '--sitting', '子'],
                          cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out['ok'] and out['tool'] == 'zibai' and '一白' in out['say'] and '坐子' in out['say']
    bad = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/zibai.py', '--date', '2026-11-08', '--sitting', '北'],
                         cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    assert bad.returncode == 1 and json.loads(bad.stdout)['error'] == 'invalid_input'


@pytest.mark.parametrize('date', ['2026-13-01', 'tomorrow', '1500-01-01'])
def test_bad_dates_are_input_errors(date):
    with pytest.raises(ValueError):
        zibai(date)


@pytest.mark.parametrize('question,expected', [
    ('今年五黄在哪个方位', True), ('这个月紫白飞到哪', True), ('2027年流年飞星', True),
    ('奇门九星天蓬在哪宫', False), ('玄空飞星下卦怎么排', False), ('床头朝向怎么摆', False),
])
def test_router_sends_zibai_questions_to_the_tool(question, expected):
    from question_router import route
    assert ('zibai.py' in (route(question).get('command') or '')) is expected
