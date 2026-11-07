"""六爻应期：《增删卜易》应期总注章每条的书中例子逐条复算，「餘仿此」推到其他地支；错卦、综卦。"""
from classical_search import get_passage
from liuyao_timing import PASSAGE, QUOTES, cuo_zong, line_timing


def _rules(branch, moving=False, changed=None, month='寅', day='寅', markers=()):
    line = {'branch': branch, 'markers': list(markers)}
    out = line_timing(line, {'branch': changed} if changed else None, moving, month, day)
    return {r['rule']: r['branches'] for r in out}


def test_every_quote_is_in_the_chapter():
    text = get_passage(PASSAGE)['text']
    for quote in QUOTES.values():
        assert quote in text, quote


def test_the_books_own_examples():
    # 靜而逢值逢沖：主事爻臨子水不動，後逢子日午日而應之
    assert _rules('子')['static'] == ['子', '午']
    # 動而逢合逢值：主事爻臨子水發動，後遇丑日子日而應之
    assert _rules('子', moving=True, changed='亥')['moving'] == ['丑', '子']
    # 入三墓俱喜沖開：主事爻臨午火，假使火墓於戌，後逢辰日則應之
    assert _rules('午', day='戌')['tomb'] == ['辰']
    # 遇六合亦宜相擊：主象臨子，與丑作合，後逢午未日應之
    assert _rules('子', month='丑')['harmony'] == ['午', '未']
    # 月破喜塡：子月占，主事爻臨午火，後逢未日應之，又有逢午月應之
    assert _rules('午', month='子')['month_break'] == ['未', '午']
    # 化進神：申動酉，有應申月日者，有應巳月日者
    assert _rules('申', moving=True, changed='酉')['advance'] == ['申', '巳']
    # 化退神：酉化申，有應申月日者，有應寅日月者
    assert _rules('酉', moving=True, changed='申')['retreat'] == ['申', '寅']
    # 爻臨戌土，變出酉金，有戌日應者，有酉日應者
    assert _rules('戌', moving=True, changed='酉')['changed'] == ['戌', '酉']


def test_the_rules_carry_over_to_other_branches_and_only_when_their_condition_holds():
    assert _rules('卯')['static'] == ['卯', '酉']
    assert 'moving' not in _rules('卯') and 'tomb' not in _rules('卯', day='子')
    assert _rules('卯', day='未')['tomb'] == ['丑']                  # 木墓未，冲开逢丑
    assert _rules('巳', markers=['旬空'])['empty'] == ['巳', '亥']
    earth = line_timing({'branch': '丑', 'markers': []}, None, False, '寅', '辰')
    tomb = next(r for r in earth if r['rule'] == 'tomb')
    assert tomb['branches'] == ['戌'] and '推出' in tomb['note']


def test_cast_output_and_cuo_zong():
    import json
    import subprocess
    import sys
    from pathlib import Path
    skill = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'
    done = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/liuyao_cast.py', 'coins', '--lines', '7,8,9,7,6,8',
                           '--date', '2026-11-08', '--time', '10:00', '--question', '求财'],
                          cwd=skill, capture_output=True, text=True, encoding='utf-8')
    out = json.loads(done.stdout)
    assert out['main_chart']['hex_name'] == '雷火丰'
    assert (out['cuo_zong']['cuo']['name'], out['cuo_zong']['zong']['name']) == ('风水涣', '火山旅')
    target = out['timing']['targets'][0]
    assert target['position'] in out['rule_checks']['targets'] and target['candidates']
    assert out['timing']['not_computed']
    assert cuo_zong([7, 7, 7, 7, 7, 7])['cuo']['name'] == '坤为地'
