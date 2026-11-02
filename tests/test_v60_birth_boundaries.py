"""Fictional births exercise the public comparison, correction, and replay contracts."""
import json
import subprocess
import sys
from datetime import datetime, timedelta

import pytest
from bazi_calc import build_parser, calculate_bazi
from birth_candidates import run
from birth_correction import correct
from conftest import SCRIPTS, run_cli

BASE = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30,
        'gender': 'male', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'}
SETTINGS = {key: BASE[key] for key in ('gender', 'timezone', 'time_standard')}


def cli(script, request):
    done = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / script), '--stdin'],
                          input=json.dumps(request), capture_output=True, text=True, encoding='utf-8')
    return done.returncode, json.loads(done.stdout)


@pytest.mark.parametrize('side', ['before', 'after'])
@pytest.mark.parametrize('field', ['year', 'month', 'day', 'gender'])
def test_required_birth_identity_is_never_filled_from_an_example(side, field):
    request = {'before': BASE, 'after': {**BASE, 'hour': 11}}
    request[side] = {key: value for key, value in request[side].items() if key != field}
    code, result = cli('birth_correction.py', request)
    assert code == 1 and result['ok'] is False
    assert result['error'] == 'invalid_request' and result['field'] == f'{side}.{field}'


@pytest.mark.parametrize(('field', 'value'), [
    ('year', True), ('year', '2000'), ('month', None), ('day', False),
    ('hour', True), ('minute', None), ('gender', None), ('gender', 'unknown'),
    ('lunar', 'yes'), ('leap', 1), ('sect', True), ('sect', 3), ('fold', True),
    ('fold', 2), ('time_standard', None), ('time_standard', 'solar'),
    ('timezone', 8), ('city', []), ('longitude', False), ('longitude', float('nan')),
])
def test_birth_types_and_option_choices_are_validated_before_calculation(field, value):
    with pytest.raises(ValueError):
        correct(BASE, {**BASE, field: value})


def test_unknown_hour_remains_valid_and_replayable():
    result = correct({key: value for key, value in BASE.items() if key not in ('hour', 'minute')}, BASE)
    assert result['before']['hour_known'] is False
    assert result['before']['four_pillars']['hour'] is None
    assert result['before']['qi_yun_start'] is None
    assert result['input']['before']['hour'] is None
    assert correct(**result['input']) == result
    assert result['calculation_context']['before']['calendar_context']['status'] == 'birth_time_required'


@pytest.mark.parametrize('leap_fields', [{'month': 4, 'leap': True}, {'month': -4}, {'month': -4, 'leap': True}])
def test_leap_inputs_select_the_actual_leap_month_and_replay_one_signed_month(leap_fields):
    ordinary = {**BASE, 'year': 2020, 'month': 4, 'day': 1, 'lunar': True}
    result = correct(ordinary, {**ordinary, **leap_fields})
    assert result['changed_fields'] == ['leap']
    assert result['changed_pillars']
    assert result['input']['after']['month'] == -4
    assert 'leap' not in result['input']['after']
    assert result['calculation_context']['before']['solar_date']['month'] == 4
    assert result['calculation_context']['before']['solar_date']['day'] == 23
    assert result['calculation_context']['after']['solar_date']['month'] == 5
    assert result['calculation_context']['after']['solar_date']['day'] == 23
    assert correct(**result['input']) == result


@pytest.mark.parametrize('fields', [
    {'lunar': False, 'leap': True}, {'lunar': False, 'month': -4},
    {'lunar': True, 'month': -4, 'leap': False}, {'lunar': True, 'month': 0},
    {'year': 2021, 'lunar': True, 'month': 4, 'leap': True},
])
def test_conflicting_or_nonexistent_leap_dates_fail(fields):
    with pytest.raises(ValueError):
        correct(BASE, {**BASE, **fields})


def test_positive_lunar_month_with_false_leap_is_an_ordinary_month():
    result = correct(BASE, {**BASE, 'year': 2020, 'month': 4, 'day': 1, 'lunar': True, 'leap': False})
    assert result['input']['after']['month'] == 4
    assert result['calculation_context']['after']['solar_date']['month'] == 4


@pytest.mark.parametrize(('year', 'month', 'lunar', 'expected_day', 'expected_rc'), [
    (2020, 4, True, '2020-04-23', 0), (2020, -4, True, '2020-05-23', 0),
    (2021, -4, True, None, 1), (2020, -4, False, None, 1),
    (2020, 0, True, None, 1),
])
def test_bazi_cli_preserves_signed_lunar_month_contract(year, month, lunar, expected_day, expected_rc):
    result = run_cli('bazi_calc.py', '--year', year, '--month', month, '--day', 1,
                     '--hour', 10, '--gender', 'male', '--time-standard', 'clock',
                     *(['--lunar'] if lunar else []), expect_rc=expected_rc)
    assert result['ok'] is (expected_rc == 0)
    if expected_day:
        solar = result['solar_date']
        assert f"{solar['year']:04d}-{solar['month']:02d}-{solar['day']:02d}" == expected_day


@pytest.mark.parametrize('candidate', [
    '2000-01-15', '20000115T1030', '2000-01-15 10:30', '2000-01-15T10:30:00',
    '2000-01-15T10:30:00.500', '2000-01-15T10:30Z', '2000-01-15T10:30+08:00',
    '2000-01-15T10:30-05:00', ' 2000-01-15T10:30', None, 2000,
])
def test_candidates_accept_only_explicit_local_minutes(candidate):
    with pytest.raises(ValueError, match='YYYY-MM-DDTHH:MM'):
        run({'birth': SETTINGS, 'candidates': [candidate, '2000-01-15T11:30']})


@pytest.mark.parametrize('payload', [
    {'birth': {**SETTINGS, 'fold': True}, 'candidates': ['2000-01-15T10:30', '2000-01-15T11:30']},
    {'birth': {**SETTINGS, 'typo': 1}, 'candidates': ['2000-01-15T10:30', '2000-01-15T11:30']},
    {'birth': SETTINGS, 'candidates': ['2000-01-15T10:30', '2000-01-15T11:30'],
     'range': {'start': '2000-01-15T10:30', 'end': '2000-01-15T11:30'}},
    {'birth': SETTINGS, 'range': {'start': '2000-01-15T10:30', 'end': '2000-01-15T11:30', 'step': 60}},
    {'birth': SETTINGS, 'range': None},
])
def test_candidate_request_shape_never_silently_drops_input(payload):
    with pytest.raises(ValueError):
        run(payload)


@pytest.mark.parametrize(('fold', 'offset', 'utc'), [(0, -4, '2024-11-03T05:15:00+00:00'),
                                                   (1, -5, '2024-11-03T06:15:00+00:00')])
def test_fold_is_preserved_in_each_candidate_calculation_and_replay(fold, offset, utc):
    result = run({'birth': {**SETTINGS, 'timezone': 'America/New_York', 'fold': fold},
                  'candidates': ['2024-11-03T01:15', '2024-11-03T01:45']})
    assert result['input']['birth']['fold'] == fold
    for item in result['segments']:
        assert item['calculation_context']['timezone']['fold'] == fold
        assert item['calculation_context']['offset_hours'] == offset
    assert result['segments'][0]['calculation_context']['calendar_context']['birth_instant_utc'] == utc
    assert run(result['input']) == result


@pytest.mark.parametrize(('start', 'end', 'fold'), [
    ('2024-03-10T01:50', '2024-03-10T03:10', None),
    ('2024-11-03T00:50', '2024-11-03T02:10', 0),
    ('2024-11-03T00:50', '2024-11-03T02:10', 1),
    ('2024-11-03T01:15', '2024-11-03T01:45', None),
])
def test_ranges_require_every_local_minute_and_one_constant_offset(start, end, fold):
    code, result = cli('birth_candidates.py', {
        'birth': {**SETTINGS, 'timezone': 'America/New_York', 'fold': fold},
        'range': {'start': start, 'end': end},
    })
    assert code == 1 and result['error'] == 'invalid_request'
    assert result['field'] == 'range' and '拆分' in result['message']


def test_a_fold_range_with_one_selected_occurrence_is_valid():
    result = run({'birth': {**SETTINGS, 'timezone': 'America/New_York', 'fold': 1},
                  'range': {'start': '2024-11-03T01:15', 'end': '2024-11-03T01:45'}})
    assert result['segments'][0]['calculation_context']['offset_hours'] == -5
    assert run(result['input']) == result


@pytest.mark.parametrize(('start', 'end', 'settings'), [
    ('2000-02-04T20:35', '2000-02-04T21:05', SETTINGS),
    ('2000-02-04T07:35', '2000-02-04T08:05', {**SETTINGS, 'timezone': 'America/New_York'}),
    ('2000-02-04T23:55', '2000-02-05T00:40', {**SETTINGS, 'longitude': 116.4, 'time_standard': 'true-solar'}),
    ('2026-02-16T22:55', '2026-02-17T00:05', {**SETTINGS, 'sect': 1}),
])
def test_segments_match_independent_direct_minute_chart_calls(start, end, settings):
    result = run({'birth': settings, 'range': {'start': start, 'end': end}})
    expected = []
    moment, stop = datetime.fromisoformat(start), datetime.fromisoformat(end)
    while moment <= stop:
        argv = ['--year', str(moment.year), '--month', str(moment.month), '--day', str(moment.day),
                '--hour', str(moment.hour), '--minute', str(moment.minute)]
        for key, value in settings.items():
            argv.extend(['--' + key.replace('_', '-'), str(value)])
        chart = calculate_bazi(build_parser(diagnostics=False).parse_args(argv))
        assert chart['ok']
        pillars = {key: chart['four_pillars'][key]['ganzhi'] for key in ('year', 'month', 'day', 'hour')}
        label = moment.strftime('%Y-%m-%dT%H:%M')
        if expected and expected[-1]['four_pillars'] == pillars:
            expected[-1]['to'] = label
        else:
            expected.append({'from': label, 'to': label, 'four_pillars': pillars})
        moment += timedelta(minutes=1)
    assert [{key: item[key] for key in ('from', 'to', 'four_pillars')} for item in result['segments']] == expected


def test_fixed_pillars_do_not_claim_fixed_interpretation_and_start_luck_is_a_sample():
    code, result = cli('birth_candidates.py', {
        'birth': SETTINGS, 'range': {'start': '2000-01-15T23:59', 'end': '2000-01-16T00:01'},
    })
    assert code == 0 and 'day' in result['varying'] and 'year' in result['fixed']
    text = ' '.join(result['say'])
    assert '这几柱的结论各候选相同' not in text and '十神' in text
    stable = run({'birth': SETTINGS, 'range': {'start': '2000-01-15T10:30', 'end': '2000-01-15T10:35'}})
    assert stable['varying'] == {}
    assert '解读不受出生时间不确定影响' not in ' '.join(stable['say'])
    assert stable['segments'][0]['sampled_at'] == '2000-01-15T10:30'
    assert stable['segments'][0]['qi_yun_basis'] == 'segment_start_only'
    changed = correct(BASE, {**BASE, 'minute': 35})
    assert changed['before']['qi_yun_start'] != changed['after']['qi_yun_start']
    assert '起运时刻、各步大运的起止年龄与年份' in changed['invalidated']


def test_city_resolution_and_effective_options_are_separate_from_canonical_replay():
    code, result = cli('birth_candidates.py', {
        'birth': {'gender': 'female', 'city': '上海', 'time_standard': 'true-solar', 'sect': 1},
        'candidates': ['2000-03-05T22:40', '2000-03-06T00:20'],
    })
    assert code == 0
    context = result['segments'][0]['calculation_context']
    assert context['effective_settings']['timezone'] == 'Asia/Shanghai'
    assert context['effective_settings']['longitude'] == 121.47
    assert context['birthplace']['longitude_source'] == 'city_table'
    assert result['input']['birth']['city'] == '上海' and result['input']['birth']['longitude'] is None
    assert result['method'] and result['time_context']['time_standard'] == 'true-solar'
    assert result['envelope']['replay']['see'] == ['input']
