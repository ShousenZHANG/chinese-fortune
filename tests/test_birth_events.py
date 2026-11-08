"""考时候选对照：把经历年份放到每个候选盘的大运、流年上；明说没有古籍依据，不判哪个候选是真的。"""
import json

import pytest
from birth_candidates import BirthInputError, run


def _request(**extra):
    return {'birth': {'gender': 'male', 'timezone': 'Asia/Shanghai'},
            'candidates': ['1990-05-15T09:30', '1990-05-15T11:30'], **extra}


def test_each_candidate_gets_the_same_years_with_its_own_roles():
    out = run(_request(events=[{'year': 2015, 'what': '结婚'}, {'year': 2018, 'what': '换工作'}]))
    assert '没有古籍依据' in out['events_note'] and '不判哪个候选更准' in out['events_note']
    for segment in out['segments']:
        marry, job = segment['events']
        assert (marry['liu_nian'], job['liu_nian']) == ('乙未', '戊戌')
        assert marry['area'] == 'relationship' and marry['stars'] == ['正财', '偏财']
        assert marry['brings_star']['liu_nian'] == (marry['liu_nian_role'] in marry['stars'])
        assert job['area'] == 'career' and job['da_yun']
    assert out['input']['events'][0] == {'year': 2015, 'what': '结婚'}
    text = json.dumps(out, ensure_ascii=False)
    assert '更像' not in text.replace('不拿「哪张更像」', '').replace('「哪张更像」', '')


def test_without_events_nothing_changes():
    assert 'events_note' not in run(_request()) and 'events' not in run(_request())['segments'][0]


@pytest.mark.parametrize('events', [[{'year': 1800, 'what': '结婚'}], [{'year': 2015}], 'x',
                                    [{'year': 2015, 'what': '事'}] * 11])
def test_bad_events_are_input_errors(events):
    with pytest.raises(BirthInputError):
        run(_request(events=events))
