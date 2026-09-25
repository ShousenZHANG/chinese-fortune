"""Real selection outputs must match scripts/contracts.py, key for key.

mypy checks the producers against the TypedDicts; this checks the values that
actually come out, so a key added on one path but not declared, or declared
but never written, fails here instead of in a host's parser.
"""
import itertools
import types
from typing import Any, Literal, NotRequired, Union, get_args, get_origin, get_type_hints

import contracts
import pytest
from fortune_ranking import day_prohibitions
from fortune_reading import read_request

_PERSON = {'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                     'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}


def check(value: Any, expected: Any, path: str = '$') -> None:
    """Fail with the path of the first value that does not fit ``expected``."""
    origin = get_origin(expected)
    if expected is Any:
        return
    if origin is NotRequired:
        return check(value, get_args(expected)[0], path)
    if origin is Literal:
        assert value in get_args(expected), f'{path}: {value!r} not in {get_args(expected)}'
        return
    if origin in (Union, types.UnionType):
        errors = []
        for option in get_args(expected):
            try:
                return check(value, option, path)
            except AssertionError as exc:
                errors.append(str(exc))
        raise AssertionError(f'{path}: matches none of {get_args(expected)}: {errors}')
    if expected is type(None):
        assert value is None, f'{path}: expected None, got {value!r}'
        return
    if isinstance(expected, type) and issubclass(expected, dict) and hasattr(expected, '__required_keys__'):
        assert isinstance(value, dict), f'{path}: expected {expected.__name__}, got {type(value).__name__}'
        hints = get_type_hints(expected)
        missing = expected.__required_keys__ - value.keys()
        extra = value.keys() - hints.keys()
        assert not missing, f'{path}: {expected.__name__} missing {sorted(missing)}'
        assert not extra, f'{path}: {expected.__name__} has undeclared {sorted(extra)}'
        for key, item in value.items():
            check(item, hints[key], f'{path}.{key}')
        return
    if origin is list:
        assert isinstance(value, list), f'{path}: expected list, got {type(value).__name__}'
        for i, item in enumerate(value):
            check(item, get_args(expected)[0], f'{path}[{i}]')
        return
    if origin is dict:
        assert isinstance(value, dict), f'{path}: expected dict, got {type(value).__name__}'
        return
    # bool is an int subclass; an int field must not accept True.
    assert isinstance(value, expected) and not (expected is int and isinstance(value, bool)), \
        f'{path}: expected {expected.__name__}, got {value!r}'


def _request(scenario, candidates, *, longitude=True, preferences=None, people=1):
    event = {'scenario': scenario, 'timezone': 'Australia/Sydney', 'time_standard': 'true-solar'}
    if longitude:
        event['longitude'] = 151.2
    participants = [{'id': 'me', 'confirmed': True, 'person': _PERSON}]
    if people == 2:
        event['priority'] = 'equal'
        participants.append({'id': 'you', 'confirmed': True, 'person': {**_PERSON, 'birth': {
            **_PERSON['birth'], 'year': 1995, 'gender': 'female'}}})
    payload = {'current_timezone': 'Australia/Sydney', 'request_time': '2026-09-17T02:00:00Z',
               'period': {'start': '2026-09-20', 'end': '2026-11-01'}, 'event': event,
               'participants': participants, 'duration_minutes': 120, 'candidates': candidates,
               'granularity': 'hour'}
    if preferences:
        payload['preferences'] = preferences
    return payload


def _slot(cid, day, start='09:00', end='13:00'):
    return {'id': cid, 'start': f'{day}T{start}', 'end': f'{day}T{end}'}


# Days that reach each outcome: clear, 天转/地转, 協紀 prohibitions, 截路 hours,
# an unresolved 戊癸 day, a DST change and an overnight window.
_DAYS = ['2026-09-21', '2026-09-26', '2026-10-04', '2026-10-13', '2026-10-14', '2026-10-26', '2026-10-29']
_CANDIDATES = ([[_slot('a', d)] for d in _DAYS]
               + [[_slot('a', a), _slot('b', b)] for a, b in itertools.combinations(_DAYS[::3], 2)]
               + [[{'id': 'night', 'start': '2026-10-15T20:00', 'end': '2026-10-16T12:00'}],
                  [{'id': 'dst', 'start': '2026-10-04T00:30', 'end': '2026-10-04T06:00'}]])
_VARIANTS = [{}, {'preferences': {'prefer': 'earliest'}}, {'preferences': {'prefer': 'latest'}},
             {'longitude': False}, {'people': 2}]


@pytest.mark.parametrize('scenario', ['travel', 'wedding', 'moving', 'business'])
def test_selection_outputs_match_the_contracts(scenario):
    statuses = set()
    for candidates, variant in itertools.product(_CANDIDATES, _VARIANTS):
        result = read_request(_request(scenario, candidates, **variant))
        check(result['recommendation'], contracts.Recommendation, 'recommendation')
        check(result['practical_choice'], contracts.PracticalChoice, 'practical_choice')
        check(result['decision_blockers'], list[contracts.Blocker], 'decision_blockers')
        for key in ('ranking', 'practical_screening'):
            if key in result:
                check(result[key], contracts.Ranking, key)
        statuses.add(result['recommendation']['status'])
    # The grid has to reach the states the contract describes, or it proves little.
    assert {'practical_choice', 'excluded_by_clause', 'clause_conflict', 'preferences_required',
            'screening_incomplete'} <= statuses, statuses


@pytest.mark.parametrize('scenario,ganzhi,month', [
    ('wedding', '辛酉', '酉'), ('travel', '癸酉', '戌'), ('moving', '丙子', '戌'),
    ('wedding', '丙子', '午'), ('business', '甲午', '子')])
def test_day_rule_hits_match_the_contract(scenario, ganzhi, month):
    hits = day_prohibitions(scenario, ganzhi, month)
    assert hits, (scenario, ganzhi, month)
    check(hits, list[contracts.DayRuleHit])


def test_the_checker_rejects_what_it_should():
    with pytest.raises(AssertionError, match='undeclared'):
        check({'code': 'x', 'message': 'y', 'surprise': 1}, contracts.Blocker)
    with pytest.raises(AssertionError, match='missing'):
        check({'code': 'x'}, contracts.Blocker)
    with pytest.raises(AssertionError, match='not in'):
        check({'status': 'maybe', 'first_choice': None, 'backup': None}, contracts.Recommendation)
    with pytest.raises(AssertionError, match='expected int'):
        check(True, int)
    check({'code': 'x', 'message': 'y', 'participant_id': 'me'}, contracts.Blocker)
