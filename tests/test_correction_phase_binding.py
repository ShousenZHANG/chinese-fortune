"""Correction claims use actual old and current charts without losing candidates or people."""
import pytest
from answer_assertions import pillar_findings
from answer_check import check_answer
from bazi_calc import calculate_bazi
from birth_candidates import birth_arguments, run
from birth_correction import correct
from pair_facts import pair_facts, subject_chart

BIRTH = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30,
         'gender': 'male', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'}


@pytest.fixture(scope='module')
def correction():
    result = correct(BIRTH, {**BIRTH, 'day': 16})
    assert result['ok'] is True
    assert result['before']['four_pillars']['day'] != result['after']['four_pillars']['day']
    return result


@pytest.mark.parametrize('phase,side,passed', [
    ('更正后，', 'before', False), ('更正后，', 'after', True),
    ('更正前，', 'before', True), ('更正前，', 'after', False),
    ('原来，', 'before', True), ('原来，', 'after', False),
    ('', 'before', False), ('', 'after', True),
])
def test_explicit_phase_and_current_claim(correction, phase, side, passed):
    day = correction[side]['four_pillars']['day']
    result = check_answer(f'{phase}你的日柱为{day}。', [correction])
    assert result['passed'] is passed, result
    assert result['checked']['pillars_checked'] == 1
    if not passed:
        assert [f['code'] for f in result['findings']] == ['pillar_mismatch']


@pytest.mark.parametrize('swapped', [False, True])
@pytest.mark.parametrize('table', [False, True])
def test_history_keeps_both_phases(correction, swapped, table):
    before = correction['after' if swapped else 'before']['four_pillars']['day']
    after = correction['before' if swapped else 'after']['four_pillars']['day']
    answer = (f'| 阶段 | 日柱 |\n| --- | --- |\n| 更正前 | {before} |\n| 更正后 | {after} |'
              if table else f'更正前日柱为{before}，更正后日柱为{after}。')
    result = check_answer(answer, [correction])
    assert result['passed'] is not swapped, result
    assert result['checked']['pillars_checked'] == 2


@pytest.mark.parametrize('phase,side,passed', [
    ('更正后', 'before', False), ('更正后', 'after', True),
    ('更正前', 'before', True), ('原来', 'after', False),
])
@pytest.mark.parametrize('kind', ['sequence', 'day_master'])
def test_phase_also_binds_sequence_and_day_master(correction, phase, side, passed, kind):
    pillars = correction[side]['four_pillars']
    claim = ('四柱为' + ' '.join(pillars.values()) if kind == 'sequence'
             else '日主为' + pillars['day'][0])
    result = check_answer(f'{phase}，你的{claim}。', [correction])
    assert result['passed'] is passed, result


def test_last_correction_after_overrides_prior_charts(correction):
    newer = correct({**BIRTH, 'day': 16}, {**BIRTH, 'day': 17})
    old_chart = calculate_bazi(birth_arguments(BIRTH, 'birth'))
    assert old_chart['ok'] is True
    facts = [old_chart, correction, newer]
    for day in (15, 16, 17):
        source = subject_chart({**BIRTH, 'day': day})
        result = check_answer(f"你的日柱为{source['four_pillars']['day']['ganzhi']}。", facts)
        assert result['passed'] is (day == 17), result


@pytest.mark.parametrize('current', ['现在', '当前', '目前', '最新'])
@pytest.mark.parametrize('stale', [False, True])
def test_current_marker_resets_a_historical_prefix(correction, current, stale):
    before = correction['before']['four_pillars']['day']
    day = correction['before' if stale else 'after']['four_pillars']['day']
    result = check_answer(f'原来日柱为{before}，{current}日柱为{day}。', [correction])
    assert result['passed'] is not stale, result
    assert result['checked']['pillars_checked'] == 2


def test_legacy_assertion_entry_point_also_keeps_correction_phase(correction):
    before = correction['before']['four_pillars']['day']
    checked = {'pillars_checked': 0}
    findings = pillar_findings(f'更正后日柱为{before}。', [correction], checked)
    assert [f['code'] for f in findings] == ['pillar_mismatch']
    assert checked['pillars_checked'] == 1


def test_unknown_hour_is_local_to_correction_phase():
    result = correct(BIRTH, {**BIRTH, 'hour': None})
    hour = result['before']['four_pillars']['hour']
    assert check_answer(f'更正前时柱为{hour}。', [result])['passed']
    checked = check_answer(f'更正后时柱为{hour}。', [result])
    assert [f['code'] for f in checked['findings']] == ['unknown_hour_pillar']
    checked = check_answer('更正后出生时间就是上午10点。', [result])
    assert [f['code'] for f in checked['findings']] == ['unknown_hour_pillar']


@pytest.mark.parametrize('swapped', [False, True])
@pytest.mark.parametrize('table', [False, True])
def test_pair_subject_binding_survives(swapped, table):
    pair = pair_facts(subject_chart(BIRTH), subject_chart({**BIRTH, 'day': 16}))
    a = pair['subjects']['B' if swapped else 'A']['four_pillars']['day']
    b = pair['subjects']['A' if swapped else 'B']['four_pillars']['day']
    answer = (f'| 对象 | 日柱 |\n| --- | --- |\n| A | {a} |\n| B | {b} |'
              if table else f'A的日柱为{a}，B的日柱为{b}。')
    result = check_answer(answer, [pair])
    assert result['passed'] is not swapped, result
    assert result['checked']['pillars_checked'] == 2


def test_actual_birth_candidates_remain_unordered_alternatives():
    facts = run({'birth': {'gender': 'male', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'},
                 'candidates': ['2000-01-15T10:30', '2000-01-16T10:30']})
    assert facts['ok'] is True
    for segment in facts['segments']:
        day = segment['four_pillars']['day']
        assert check_answer(f'日柱为{day}。', [facts])['passed']
    rows = '\n'.join(f"| {s['from']} | {s['four_pillars']['day']} |" for s in facts['segments'])
    result = check_answer('| 候选时刻 | 日柱 |\n| --- | --- |\n' + rows, [facts])
    assert result['passed'], result
    assert result['checked']['pillars_checked'] == 0
