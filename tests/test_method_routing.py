"""Named methods must reach an actionable route without asking unrelated fields."""
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from question_router import route


def test_named_ziwei_exposes_its_own_tool_and_birth_requirements():
    result = route('请用紫微斗数列命宫、身宫、五行局、主星及夫妻宫')
    assert result['flow'] == 'method'
    assert result['method'] == 'ziwei'
    assert result['script'] == 'scripts/ziwei_calc.py'
    assert result['reference'] == 'references/02-ziwei.md'
    assert any('出生' in field for field in result['needs'])
    assert not any('现居' in field for field in result['needs'])


def test_three_requested_methods_keep_separate_tools_and_time_meanings():
    result = route('同时给八字、梅花、紫微的独立结果')
    assert result['flow'] == 'multi_method'
    assert [step['method'] for step in result['steps']] == ['bazi', 'meihua', 'ziwei']
    assert len({step['script'] for step in result['steps']}) == 3
    assert 'meihua_cast.py' in result['steps'][1]['command']
    assert not any('出生' in field for field in result['steps'][1]['needs'])
    assert result['combine_verdicts'] is False


def test_definitions_do_not_collect_birth_or_current_location():
    result = route('只解释正官、伤官、格局、喜用神，不分析我')
    assert result['flow'] == 'knowledge'
    assert result['needs'] == []
    assert result['reference'] == 'references/01-bazi.md'
    assert 'classical_search.py' in result['command']
    assert route('我的八字是什么格局')['flow'] == 'natal'


def test_non_bazi_definitions_do_not_cast_or_collect_birth_data():
    ziwei = route('紫微斗数的命宫是什么意思')
    assert ziwei['flow'] == 'knowledge' and not ziwei['needs'] and ziwei['command'].endswith('--book ziwei')
    liuyao = route('六爻里的世应是什么意思')
    assert liuyao['flow'] == 'knowledge' and not liuyao['needs'] and liuyao['command'].endswith('--book zengshan')
    compare = route('紫微斗数和八字有什么区别')
    assert compare['flow'] == 'knowledge' and '--book' not in compare['command']
    assert compare['references'] == ['references/02-ziwei.md', 'references/01-bazi.md']


@pytest.mark.parametrize('question,method', [
    ('用梅花易数按现在起卦', 'meihua'),
    ('用六爻看这次面试', 'liuyao'),
    ('用周易按时间起卦', 'yijing'),
    ('奇门遁甲看租房合同签不签', 'qimen'),
    ('大六壬问事', 'liuren'),
    ('塔罗看这个选择', 'tarot'),
])
def test_named_methods_are_actionable(question, method):
    result = route(question)
    assert result['flow'] == 'method'
    assert result['method'] == method
    assert result['command'].startswith('python scripts/')


@pytest.mark.parametrize('question', ['紫微排盘', '用梅花时间起卦', '六爻起卦', '周易时间起卦',
                                      '奇门起局', '大六壬起局', '塔罗抽一张牌', '八字大运'])
def test_routed_command_templates_reach_real_clis(question):
    command = route(question)['command'].replace('[--hour H --minute m]', '--hour 10 --minute 30')
    values = {'Y': '2000', 'M': '1', 'D': '15', 'H': '10', 'm': '30', 'G': 'male',
              '出生地': '北京', '现居地时区': 'Asia/Shanghai', '本次UTC': '2026-10-26T00:00:00Z', '<原话>': question}
    args = [values.get(arg, arg) for arg in shlex.split(command)[1:]]
    if 'tarot_draw.py' in args[0] or 'liuyao_cast.py' in args[0]:
        args += ['--seed', '7']
    done = subprocess.run([sys.executable, '-X', 'utf8', *args],
                          cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)['ok'] is True


def test_explicit_luck_cycle_does_not_become_day_selection():
    result = route('请看八字今年的大运和格局')
    assert result['flow'] == 'natal'
    assert 'bazi_reading.py' in result['command']
    assert any('参考年份' in field for field in result['needs'])
    assert route('下周去洛阳紫微城哪天好')['flow'] == 'personal_days'


def test_relationship_route_keeps_two_subjects_and_does_not_invent_a_score():
    result = route('请给我们做八字合婚')
    assert result['flow'] == 'compatibility'
    assert [step['subject'] for step in result['steps']] == ['A', 'B']
    assert result['reference'] == 'references/14-hehun.md'
    assert result['combine_verdicts'] is False
    assert result['pair_facts']['command'] == 'python scripts/pair_facts.py --stdin'
    assert 'pair_facts' not in route('请用紫微斗数给我们合盘')


def test_third_person_birth_questions_are_not_pure_definitions():
    assert route('请解释孩子的八字格局，孩子现在读小学')['flow'] == 'natal'
    assert route('请解释她的四柱')['flow'] == 'natal'
    assert route('1990年5月10日14时出生，解释格局')['flow'] == 'natal'


def test_named_ziwei_or_multiple_birth_methods_keep_both_relationship_subjects():
    one = route('请用紫微斗数给我们合盘')
    assert one['flow'] == 'compatibility'
    assert [(s['subject'], s['method']) for s in one['steps']] == [('A', 'ziwei'), ('B', 'ziwei')]
    multi = route('请用八字和紫微给我们合婚')
    assert [(s['subject'], s['method']) for s in multi['steps']] == [
        ('A', 'bazi'), ('A', 'ziwei'), ('B', 'bazi'), ('B', 'ziwei')]


@pytest.mark.parametrize('question,reference,book', [
    ('世应是什么意思', '04-liuyao.md', 'zengshan'),
    ('体用是什么意思', '05-meihua.md', 'meihua'),
    ('命宫是什么意思', '02-ziwei.md', 'ziwei'),
    ('帮我解释一下紫微斗数的命宫是什么意思', '02-ziwei.md', 'ziwei'),
    ('给我解释一下正官是什么意思', '01-bazi.md', 'ziping'),
    ('周易是什么', '03-yijing.md', None),
    ('易经是什么', '03-yijing.md', None),
    ('小六壬是什么意思', '21-extended-methods.md', None),
])
def test_definition_routing_uses_the_right_system_without_personal_intake(question, reference, book):
    result = route(question)
    assert result['flow'] == 'knowledge' and not result['needs']
    assert result['reference'] == 'references/' + reference
    assert (result['command'].endswith('--book ' + book) if book else '--book' not in result['command'])


@pytest.mark.parametrize('question', ['请解释这张八字的格局', '请解释姐姐的八字格局',
                                      '帮我解释我的八字格局', '解释张先生的四柱'])
def test_a_specific_chart_or_possessor_stays_in_natal_flow(question):
    assert route(question)['flow'] == 'natal'


@pytest.mark.parametrize('question', ['用八字看我们合婚和今年大运',
                                      '用八字和紫微看我们合婚和今年大运', '八字和紫微看今年大运'])
def test_every_birth_method_retains_reference_time_for_luck_questions(question):
    result = route(question)
    assert any('参考年份' in need for need in result['needs'])
    assert all(any('参考年份' in need for need in step['needs']) for step in result['steps'])
