"""紫微格局: each rule follows its 全书 definition and cites the line it comes from."""
import re

import pytest
from classical_search import get_passage
from conftest import run_cli
from utils import DIZHI
from ziwei_patterns import MODERN, QUANSHU, SPECS, Chart

NAMES = ('命宫', '兄弟宫', '夫妻宫', '子女宫', '财帛宫', '疾厄宫', '迁移宫', '奴仆宫', '官禄宫', '田宅宫', '福德宫', '父母宫')
MAINS = {'紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门', '天相', '天梁', '七杀', '破军'}


def make(ming, layout, shen=None, sihua=None, year_stem='甲'):
    i = DIZHI.index(ming)
    names = {NAMES[k]: DIZHI[(i - k) % 12] for k in range(12)}
    stars = {b: frozenset(layout.get(b, ())) for b in DIZHI}
    mains = {b: tuple(s for s in layout.get(b, ()) if s in MAINS) for b in DIZHI}
    return Chart(ming=ming, shen=shen or ming, stars=stars, mains=mains, names=names,
                 sihua=sihua or {}, year_stem=year_stem)


def judge(name, chart):
    return next(spec[4] for spec in SPECS if spec[0] == name)(chart)


def test_every_book_rule_quotes_its_passage():
    squash = re.compile(r'\s+')
    for name, source, passage_id, quote, _ in SPECS:
        if source == MODERN:
            assert passage_id is None and quote is None, name
            continue
        assert source == QUANSHU
        text = squash.sub('', get_passage(passage_id)['text'])
        assert squash.sub('', quote) in text, name


def test_names_are_unique_and_modern_ones_are_few():
    names = [spec[0] for spec in SPECS]
    assert len(names) == len(set(names)) >= 40
    assert sum(spec[1] == MODERN for spec in SPECS) == 3


def test_ri_yue_jia_ming_splits_required_bonus_and_breaking():
    chart = make('子', {'亥': ['太阳'], '丑': ['太阴'], '子': ['文昌', '旬空']})
    required, bonus, breaking = judge('日月夹命', chart)
    assert required == ['太阳太阴分居命宫前后']
    assert bonus and '文昌' in bonus[0]
    assert breaking and '旬空' in breaking[0] and '不坐空亡' in breaking[0]
    assert judge('日月夹命', make('子', {'亥': ['太阳'], '寅': ['太阴']})) is None


def test_jun_chen_needs_all_three_in_the_life_palace_and_fu_bi_accepts_flanking():
    assert judge('君臣庆会', make('午', {'午': ['紫微', '左辅', '右弼'], '戌': ['武曲']}))[1] == \
        ['更会武曲（原文：更会相武阴妙上）']
    assert judge('君臣庆会', make('午', {'午': ['紫微', '左辅'], '戌': ['右弼']})) is None
    assert judge('辅弼拱主', make('午', {'午': ['紫微'], '巳': ['左辅'], '未': ['右弼']}))[0][1] == '左辅右弼夹命'
    assert judge('辅弼拱主', make('午', {'午': ['紫微'], '寅': ['左辅'], '子': ['右弼']}))[0][1] == \
        '左辅右弼拱命（三方四正）'


def test_brightness_conditions_use_the_seven_level_table():
    # 贪狼 庙 in 辰; 火星 庙 in 午 but 陷 in 子 — the definition needs both 庙旺 in the same palace.
    assert judge('贪火相逢', make('子', {'子': ['贪狼', '火星']})) is None
    assert judge('一生孤贫', make('卯', {'卯': ['破军']}))[0] == ['破军守命落陷']
    assert judge('一生孤贫', make('子', {'子': ['破军']})) is None


def test_ji_yue_tong_liang_follows_the_book_not_three_of_four():
    full = {'寅': ['天机', '太阴'], '午': ['天同'], '戌': ['天梁']}
    assert judge('机月同梁', make('寅', full))[0] == ['命在寅申', '天机太阴天同天梁齐会三方四正']
    assert judge('机月同梁', make('寅', {'寅': ['天机', '太阴'], '午': ['天同']})) is None
    assert judge('机月同梁', make('子', {'子': ['天机', '太阴'], '辰': ['天同'], '申': ['天梁']})) is None
    _, _, breaking = judge('机月同梁', make('寅', {**full, '申': ['擎羊']}, sihua={'忌': '太阴'}))
    assert '擎羊' in breaking[0] and '化忌（太阴）' in breaking[0]


def test_fu_xiang_must_face_the_life_palace_from_outside():
    assert judge('府相朝垣', make('寅', {'午': ['天府'], '戌': ['天相']}))
    assert judge('府相朝垣', make('寅', {'寅': ['天相'], '戌': ['天府']})) is None


def test_ma_tou_dai_jian_uses_the_third_volume_reading():
    assert judge('马头带剑', make('午', {'午': ['擎羊', '天同']}))[0] == ['擎羊在午守命']
    assert judge('马头带剑', make('子', {'子': ['擎羊']})) is None


def test_shuang_lu_reports_liang_chong_hua_gai_as_breaking():
    chart = make('辰', {'辰': ['禄存', '武曲'], '申': ['地空']}, sihua={'禄': '武曲'})
    required, _, breaking = judge('双禄守命', chart)
    assert required == ['禄存与生年化禄（武曲）同守命宫'] and '两重华盖' in breaking[0]


def test_shi_zhong_yin_yu_bonus_by_year_stem():
    _, bonus, _ = judge('石中隐玉', make('子', {'子': ['巨门']}, year_stem='辛'))
    assert bonus == ['辛年生（卷三：辛癸人上格）']


@pytest.mark.parametrize('birth', [(1977, 11, 2, 22, 'male'), (1990, 5, 10, 14, 'female'), (2000, 1, 15, 10, 'male')])
def test_chart_output_carries_source_and_three_layers_without_verdict_fields(birth):
    y, m, d, h, g = birth
    result = run_cli('ziwei_calc.py', '--year', y, '--month', m, '--day', d, '--hour', h, '--gender', g)
    for pattern in result['patterns']:
        assert pattern['required'] and pattern['evidence'] == '；'.join(pattern['required'])
        assert pattern['source_status'] in (QUANSHU, MODERN)
        assert (pattern['passage_id'] is None) == (pattern['source_status'] == MODERN)
        assert not {'type', 'meaning', 'score', 'level', 'personal_verdict'} & pattern.keys()
