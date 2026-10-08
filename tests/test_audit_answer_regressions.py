"""Audit regressions through real request/CLI inputs and the final Markdown answer."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _cli(script: str, *args: str, payload: dict | None = None) -> str:
    run = subprocess.run(
        [sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / script), *args],
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        capture_output=True, encoding='utf-8', cwd=ROOT,
        env={**os.environ, 'PYTHONTZPATH': ''}, timeout=30,
    )
    assert run.returncode == 0, run.stderr or run.stdout
    return run.stdout


def _life_answer(question: str, zone: str = 'Asia/Shanghai') -> tuple[dict, str]:
    routed = json.loads(_cli('question_router.py', '--question', question))
    assert routed['flow'] == 'life_guide', routed
    assert not any('出生' in need for need in routed['needs'])
    answer = _cli('life_guide.py', '--decide', question, '--current-timezone', zone, '--markdown')
    return routed, answer


@pytest.mark.parametrize('question,first', [
    ('我胸痛喘不上气，很危险，怎么办', '先打 '),
    ('同事触电昏迷了，我有保险怎么办', '先打 '),
    ('我不是问保险，我现在胸痛喘不上气', '先打 '),
    ('如果以后再胸痛该怎么办？但我现在喘不上气', '先打 '),
    ('我现在胸痛喘不上气，帮我起卦看一下', '先打 '),
    # 第 13 节第 19 条: everyone out first, then the phone; not back in for the valve.
    ('家里燃气泄漏了，怎么办', '先把人都带到室外'),
])
def test_present_emergency_reaches_the_first_action_in_the_final_answer(question, first):
    routed, answer = _life_answer(question)
    assert routed['stop'] == 'emergency'
    assert answer.startswith(first)
    assert '先做（' not in answer and '6 个月起' not in answer


@pytest.mark.parametrize('question', [
    '火灾险要不要买', '怎么预防心梗', '六爻看我会不会中风',
    '如果被起诉了怎么办', '我没有胸痛也没有呼吸困难，想买保险',
])
def test_prevention_forecasts_and_negated_symptoms_do_not_claim_a_present_emergency(question):
    routed = json.loads(_cli('question_router.py', '--question', question))
    assert 'stop' not in routed
    answer = _cli('life_guide.py', '--decide', question, '--current-timezone', 'Asia/Shanghai', '--markdown')
    assert not answer.startswith('先打 ')


@pytest.mark.parametrize('question,topic', [
    ('我今天被裁了，怎么申请失业保险金', '失业'),
    ('我明天签租房合同，押金要注意什么', '押金'),
    ('下周签租房合同，要检查什么', '合同'),
    ('2026年10月8日被裁了，第一步做什么', '失业'),
])
def test_a_date_in_a_practical_question_reaches_practical_advice(question, topic):
    _, answer = _life_answer(question)
    assert topic in answer and '第 ' in answer
    assert '出生年月日' not in answer and '相主' not in answer


@pytest.mark.parametrize('question', [
    '我下周哪天面试运气最好', '周三签租房合同可以吗', '10月29日搬家可以吗',
])
def test_an_explicit_day_selection_keeps_the_personal_day_flow(question):
    routed = json.loads(_cli('question_router.py', '--question', question))
    assert routed['flow'] == 'personal_days'


def test_mainland_civil_duration_is_a_limit_not_a_minimum_in_the_final_answer():
    _, answer = _life_answer('房东不退押金，我要起诉怎么办')
    assert '6 个月起' not in answer
    assert '6 个月内审结' in answer and '3 个月内审结' in answer
    assert '延长' in answer


@pytest.mark.parametrize('zone', ['Australia/Sydney', 'Asia/Hong_Kong', None])
def test_the_legal_process_note_does_not_apply_mainland_durations_to_another_region(zone):
    args = ['--decide', '公司拖欠工资，我要起诉怎么办', '--markdown']
    if zone:
        args += ['--current-timezone', zone]
    answer = _cli('life_guide.py', *args)
    assert '6 个月起' not in answer
    from life_guide import decide
    result = decide('公司拖欠工资，我要起诉怎么办', {'current_timezone': zone})
    notes = ''.join(result['notes'])
    assert '6 个月' not in notes and '3 个月' not in notes
    assert '管辖' in notes or '所在地' in notes


def test_labour_arbitration_does_not_receive_a_civil_trial_duration():
    _, answer = _life_answer('公司欠薪，我想申请劳动仲裁怎么办')
    from life_guide import decide
    notes = ''.join(decide('公司欠薪，我想申请劳动仲裁怎么办', {'current_timezone': 'Asia/Shanghai'})['notes'])
    assert '6 个月' not in notes and '3 个月' not in notes
    assert '仲裁' in notes and '律师费' in answer


def _term_request(start: str, end: str, zone: str = 'Asia/Shanghai') -> dict:
    return {
        'current_timezone': zone, 'request_time': '2026-10-05T10:00:00Z',
        'question': '这段时间对我好吗', 'intent': 'period',
        'period': {'start': start, 'end': end},
        'event': {'scenario': 'outlook', 'timezone': zone, 'longitude': 120.0},
        'granularity': 'hour',
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 1987, 'month': 6, 'day': 15, 'hour': 10, 'minute': 0,
                      'gender': 'male', 'timezone': 'Asia/Shanghai', 'longitude': 120.0},
            'time_certainty': 'exact'}}],
    }


def test_post_term_request_and_final_answer_use_the_actual_month():
    payload = _term_request('2026-10-08T19:00:00+08:00', '2026-10-08T20:00:00+08:00')
    result = json.loads(_cli('fortune_reading.py', '--stdin', payload=payload))
    assert result['participants'][0]['target']['segments'][0]['facts']['pillars']['month'] == '戊戌'
    calendar = result['personal_calendar']['entries'][0]
    assert calendar['pillars']['month'] == '戊戌'
    assert calendar['grade'] == '平'
    answer = _cli('fortune_reading.py', '--stdin', '--markdown', payload=payload)
    assert '对你是平' in answer
    assert '这个月（丁酉）' not in answer and '月柱天比地冲' not in answer
