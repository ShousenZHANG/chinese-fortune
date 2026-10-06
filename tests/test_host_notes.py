"""What the v5.6 real-answer evaluation found (evals/v56/REPORT.md), locked in the tools.

The host added conclusions the tools did not give; the drafts now close with
「写回答时」 notes that say what must be said as the tool says it, and the
tools no longer leave gaps the host filled on its own.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading, render_facts

ROOT = Path(__file__).resolve().parents[1]


def _chart(year, month, day, hour, *extra):
    return calculate_bazi(build_parser().parse_args(
        ['--year', str(year), '--month', str(month), '--day', str(day), '--hour', str(hour), '--minute', '0',
         '--gender', 'male', '--timezone', 'Asia/Shanghai', *extra]))


def test_tied_best_days_are_said_to_be_tied():
    from fortune_reading import host_notes, read_request
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_answer_length import MOVING
    notes = host_notes(read_request(MOVING))
    assert any('工具没排先后' in n and '不要说其中哪天最好' in n for n in notes)
    assert any('不要自己写代码另算' in n for n in notes)


def test_the_json_packet_carries_the_notes():
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_answer_length import WEEK
    run = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'fortune_reading.py'), '--stdin'],
                         input=json.dumps(WEEK, ensure_ascii=False), capture_output=True, encoding='utf-8')
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['host_notes']


def test_a_withheld_colour_tells_the_host_not_to_recommend_it():
    """1980-12-23 08:00: 庚 in 子, 申子辰 water frame, no 丙丁 among the stems."""
    from bazi_reading import host_notes
    result = prepare_reading(_chart(1980, 12, 23, 8, '--as-of-year', '2026'), '我适合穿什么颜色？')
    assert any('不要把一般取法说成个人建议' in n for n in host_notes(result))
    assert '写回答时：' in render_facts(result)


def test_an_unconnected_cycle_and_the_missing_annual_layer_are_said():
    from bazi_reading import host_notes
    result = prepare_reading(_chart(1980, 1, 8, 2, '--as-of-year', '2026'), '我现在这步大运是喜是忌？')
    notes = host_notes(result)
    assert any('大运工具没判喜忌' in n for n in notes)
    assert any('流年' in n and '不要给逐年判断' in n for n in notes)


def test_a_replay_instant_alone_fixes_the_year_for_the_cycle():
    """E2 and E3 passed --request-time without --current-timezone and got an error."""
    chart = _chart(1980, 2, 26, 2, '--request-time', '2026-10-06T01:00:00Z')
    assert chart['ok'] and chart['liu_nian_status'] == 'instant_year_utc'
    result = prepare_reading(chart, '我现在走的大运好不好')
    assert result['luck_reading'][0]['status'] == 'assessed' and result['luck_reading'][0]['luck']['ganzhi'] == '癸未'


def test_without_any_time_the_cycle_asks_where_the_user_lives():
    result = prepare_reading(_chart(1980, 2, 26, 2), '我现在走的大运好不好')
    assert result['luck_reading'][0]['status'] == 'unavailable' and '先问用户现在住在哪里' in result['luck_reading'][0]['reason']


def test_a_zodiac_question_is_answered_from_the_lunar_year():
    """1991-02-04 morning is 腊月 of 1990: 马, not 羊 (A4)."""
    from bazi_reading import host_notes
    result = prepare_reading(_chart(1991, 2, 4, 8, '--as-of-year', '2026'), '我属什么，年柱是什么？')
    assert any('属马' in n for n in host_notes(result))


def test_the_json_of_a_chart_and_a_decision_carries_the_notes():
    """39 of 61 bazi_reading calls in the second evaluation run read the JSON, not the draft."""
    from life_guide import decide
    result = prepare_reading(_chart(1980, 1, 8, 2, '--as-of-year', '2026'), '我现在这步大运是喜是忌？')
    assert any('大运工具没判喜忌' in n for n in result['host_notes'])
    assert decide('失业了先做什么', {'current_timezone': 'Asia/Shanghai'})['host_notes']


def test_a_decision_draft_closes_with_the_number_rule():
    from life_decision import render
    from life_guide import decide
    assert render(decide('失业了先做什么', {'current_timezone': 'Asia/Shanghai'})).endswith(
        '书里没写的部分标明是常识。')


@pytest.mark.parametrize('question', ['火灾险要不要买？我在上海。', '意外险值不值'])
def test_an_insurance_question_is_not_about_the_hazard(question):
    from life_guide import decide
    result = decide(question, {'current_timezone': 'Asia/Shanghai'})
    shown = [(r['section'], r['number']) for g in result['do'] for r in g['entries']]
    assert 'stop' not in result and (13, 24) not in shown


def test_the_skill_says_tool_conclusions_come_first_and_takes_life_questions():
    text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
    assert '## 工具结论优先（硬规则）' in text and '不写 `python -c`' in text
    description = next(line for line in text.splitlines() if line.startswith('description: '))
    assert '燃气泄漏' in description and '收到传票' in description and len(description) <= 1024 + len('description: ')


def test_the_period_draft_explains_its_terms():
    from fortune_reading import read_request, render_answer
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_answer_length import MOVING
    assert '术语：命禄——' in render_answer(read_request(MOVING))
