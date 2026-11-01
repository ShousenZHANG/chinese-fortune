"""紫微格局: each rule follows its 全书 definition and cites the line it comes from."""
import re

import pytest
from classical_search import get_passage
from conftest import run_cli
from utils import DIZHI
from ziwei_patterns import MODERN, QUANSHU, READING, SPECS, Chart

NAMES = ('命宫', '兄弟宫', '夫妻宫', '子女宫', '财帛宫', '疾厄宫', '迁移宫', '奴仆宫', '官禄宫', '田宅宫', '福德宫', '父母宫')
MAINS = {'紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门', '天相', '天梁', '七杀', '破军'}


def make(ming, layout, shen=None, sihua=None, year_stem='甲'):
    i = DIZHI.index(ming)
    names = {NAMES[k]: DIZHI[(i - k) % 12] for k in range(12)}
    stars = {b: frozenset(layout.get(b, ())) for b in DIZHI}
    mains = {b: tuple(s for s in layout.get(b, ()) if s in MAINS) for b in DIZHI}
    return Chart(ming=ming, shen=shen or ming, stars=stars, mains=mains, names=names,
                 sihua=sihua or {}, year_stem=year_stem)


def spec(name):
    return next(s for s in SPECS if s.name == name)


def judge(name, chart):
    return spec(name).judge(chart)


def test_every_book_rule_quotes_its_passage_and_extra_sources_exist():
    squash = re.compile(r'\s+')
    for s in SPECS:
        if s.source == MODERN:
            assert s.passage_id is None and s.quote is None and not s.extra, s.name
            continue
        assert s.source in (QUANSHU, READING)
        text = squash.sub('', get_passage(s.passage_id)['text'])
        assert squash.sub('', s.quote) in text, s.name
        assert (s.note is not None) == (s.source == READING), s.name
        for pid in s.extra:
            assert get_passage(pid)['text'], (s.name, pid)


def test_names_are_unique_and_the_split_is_stable():
    names = [s.name for s in SPECS]
    assert len(names) == len(set(names)) >= 40
    assert sum(s.source == MODERN for s in SPECS) == 3
    assert {s.name for s in SPECS if s.source == READING} == {
        '坐贵向贵', '马头带剑', '羊刃入庙', '禄逢两杀', '火贵格', '贪狼遇火铃于四墓', '府相朝垣', '左右夹命'}


def test_ri_yue_jia_ming_needs_every_part_of_its_definition():
    """R6-PAT-05: 不坐空亡 and 本宫有吉星 are in the definition, so they are required."""
    good = make('子', {'亥': ['太阳'], '丑': ['太阴'], '子': ['文昌']})
    assert judge('日月夹命', good)[0] == ['太阳太阴分居命宫前后', '命宫不坐空亡', '命宫有吉星（文昌）']
    assert judge('日月夹命', make('子', {'亥': ['太阳'], '丑': ['太阴'], '子': ['文昌', '旬空']})) is None
    assert judge('日月夹命', make('子', {'亥': ['太阳'], '丑': ['太阴']})) is None


def test_jun_chen_needs_all_three_in_the_life_palace_and_fu_bi_accepts_flanking():
    assert judge('君臣庆会', make('午', {'午': ['紫微', '左辅', '右弼'], '戌': ['武曲']}))[1] == \
        ['更会武曲（原文：更会相武阴妙上）']
    assert judge('君臣庆会', make('午', {'午': ['紫微', '左辅'], '戌': ['右弼']})) is None
    assert judge('辅弼拱主', make('午', {'午': ['紫微'], '巳': ['左辅'], '未': ['右弼']}))[0][1] == '左辅右弼夹命'
    assert judge('辅弼拱主', make('午', {'午': ['紫微'], '寅': ['左辅'], '子': ['右弼']}))[0][1] == \
        '左辅右弼拱命（三方四正）'


def test_brightness_conditions_use_the_seven_level_table():
    # 贪狼 旺 in 子 but 火星 陷 there — the definition needs both 庙旺.
    assert judge('贪火相逢', make('子', {'子': ['贪狼', '火星']})) is None
    assert judge('一生孤贫', make('卯', {'卯': ['破军']}))[0] == ['破军守命落陷']
    assert judge('一生孤贫', make('子', {'子': ['破军']})) is None


def test_ji_yue_tong_liang_follows_the_book_not_three_of_four():
    full = {'寅': ['天机', '太阴'], '午': ['天同'], '戌': ['天梁']}
    assert judge('机月同梁', make('寅', full))[0] == ['命在寅申', '天机太阴天同天梁齐会三方四正']
    assert judge('机月同梁', make('寅', {'寅': ['天机', '太阴'], '午': ['天同']})) is None
    assert judge('机月同梁', make('子', {'子': ['天机', '太阴'], '辰': ['天同'], '申': ['天梁']})) is None
    breaking = judge('机月同梁', make('寅', {**full, '申': ['擎羊']}, sihua={'忌': '太阴'}))[2]
    assert '擎羊' in breaking[0] and '化忌（太阴）' in breaking[0]


def test_fu_xiang_must_face_the_life_palace_from_outside():
    assert judge('府相朝垣', make('寅', {'午': ['天府'], '戌': ['天相']}))
    assert judge('府相朝垣', make('寅', {'寅': ['天相'], '戌': ['天府']})) is None


def test_ma_tou_dai_jian_reads_the_third_volume_and_leaves_ji_duo_open():
    result = judge('马头带剑', make('午', {'午': ['擎羊', '天同', '文昌'], '戌': ['左辅']}))
    assert result[0] == ['擎羊在午守命']
    assert result[1] == [] and '多少为多原文未定' in result[3][0]      # R6-PAT-07
    assert judge('马头带剑', make('子', {'子': ['擎羊']})) is None
    assert '不是居午格' in spec('马头带剑').note


def test_shen_seated_structures_check_the_shen_palace_trines():
    """R6-PAT-02: 日月 in 身宫丑 — the plus/minus list reads 丑's 三方四正, not 命宫's."""
    chart = make('卯', {'丑': ['太阳', '太阴'], '卯': ['文昌', '禄存'], '巳': ['天魁']}, shen='丑')
    required, bonus, breaking, _ = judge('日月同宫', chart)
    assert required == ['太阳太阴同守身宫（丑未）']
    assert bonus == ['身宫三方四正见天魁'] and breaking == []


def test_ke_quan_lu_he_counts_lu_cun_as_lu_and_lists_sha_to_check():
    """R6-PAT-04: 原注「禄存亦是禄」."""
    chart = make('辰', {'戌': ['太阴'], '子': ['巨门', '禄存'], '申': ['擎羊']}, sihua={'科': '太阴', '权': '巨门', '禄': '破军'})
    required, _, _, to_check = judge('科权禄合', chart)
    assert '禄存' in required[2] and '禄存亦是禄' in required[2]
    assert '擎羊' in to_check[0] and '凶多则不美' in to_check[0]


def test_tan_wu_tong_xing_also_in_the_shen_palace():
    assert judge('贪武同行', make('子', {'丑': ['武曲', '贪狼']}, shen='丑'))[0][0].startswith('武曲贪狼同守身宫')


def test_shuang_lu_reports_liang_chong_hua_gai_as_breaking():
    chart = make('辰', {'辰': ['禄存', '武曲'], '申': ['地空']}, sihua={'禄': '武曲'})
    required, _, breaking, _ = judge('双禄守命', chart)
    assert required == ['禄存与生年化禄（武曲）同守命宫'] and '两重华盖' in breaking[0]


def test_shi_zhong_yin_yu_bonus_by_year_stem():
    assert judge('石中隐玉', make('子', {'子': ['巨门']}, year_stem='辛'))[1] == ['辛年生（卷三：辛癸人上格）']


def test_zuo_you_jia_ming_keeps_the_month_clause_in_its_quote_and_note():
    """R6-PAT-06."""
    s = spec('左右夹命')
    assert s.quote.endswith('四七十一月生者是也') and '九月生' in s.note


@pytest.mark.parametrize('birth', [(1977, 11, 2, 22, 'male'), (1990, 5, 10, 14, 'female'), (2000, 1, 15, 10, 'male'),
                                   (1955, 2, 7, 21, 'female'), (1953, 5, 30, 1, 'female')])
def test_chart_output_carries_source_and_four_layers_without_verdict_fields(birth):
    y, m, d, h, g = birth
    result = run_cli('ziwei_calc.py', '--year', y, '--month', m, '--day', d, '--hour', h, '--gender', g)
    for pattern in result['patterns']:
        assert pattern['required'] and pattern['evidence'] == '；'.join(pattern['required'])
        assert pattern['source_status'] in (QUANSHU, READING, MODERN)
        assert (pattern['passage_id'] is None) == (pattern['source_status'] == MODERN)
        assert (pattern['reading_note'] is not None) == (pattern['source_status'] == READING)
        assert {'bonus', 'breaking', 'to_check', 'extra_passage_ids'} <= pattern.keys()
        assert not {'type', 'meaning', 'score', 'level', 'personal_verdict'} & pattern.keys()
