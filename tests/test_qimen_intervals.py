"""Civil-date coverage, independent DST dates, and exact provider-boundary behavior."""
import copy
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import qimen_select
from conftest import run_cli
from qimen_cast import dunjia_futou
from qimen_select import judge, select

UTC = timezone.utc
SXTWL = json.loads((Path(__file__).parent / 'data/qimen_sxtwl_2_0_7_terms.json').read_text(encoding='utf-8'))


@cache
def selection(day, zone='Asia/Shanghai', days=1):
    return select(date.fromisoformat(day), days, ZoneInfo(zone))


def intervals(result):
    return sorted(result['candidates'] + result['excluded_windows'],
                  key=lambda row: datetime.fromisoformat(row['start']).astimezone(UTC))


def assert_partition(result, expected_start, expected_end):
    rows = intervals(result)
    expected_left = datetime.fromisoformat(expected_start).astimezone(UTC)
    expected_right = datetime.fromisoformat(expected_end).astimezone(UTC)
    cursor = expected_left
    for row in rows:
        left, right = (datetime.fromisoformat(row[key]).astimezone(UTC) for key in ('start', 'end'))
        assert left == cursor, 'gap or overlap'
        assert right > left, 'empty or reversed interval'
        assert datetime.fromisoformat(row['sampled_at']).astimezone(UTC) == left
        cursor = right
    assert cursor == expected_right, 'incomplete coverage'
    assert Counter(row['reason'] for row in result['excluded_windows']) == result['excluded']
    candidate_starts = [datetime.fromisoformat(row['start']).astimezone(UTC) for row in result['candidates']]
    assert candidate_starts == sorted(candidate_starts)


def test_ordinary_day_includes_both_early_and_late_zi():
    result = selection('2026-11-06')
    assert_partition(result, '2026-11-06T00:00:00+08:00', '2026-11-07T00:00:00+08:00')
    assert len(intervals(result)) == 13
    assert intervals(result)[-1]['window'] == '23:00–24:00'
    assert result['skipped_dates'] == []


def test_previously_missing_late_zi_is_returned_as_a_candidate():
    assert '23:00–24:00' in [row['window'] for row in selection('2026-11-06')['candidates']]


@pytest.mark.parametrize('zone,day,start,end,hours', [
    ('America/New_York', '2026-03-08', '2026-03-08T00:00:00-05:00', '2026-03-09T00:00:00-04:00', 23),
    ('America/New_York', '2026-11-01', '2026-11-01T00:00:00-04:00', '2026-11-02T00:00:00-05:00', 25),
    ('America/Chicago', '2026-03-08', '2026-03-08T00:00:00-06:00', '2026-03-09T00:00:00-05:00', 23),
    ('America/Chicago', '2026-11-01', '2026-11-01T00:00:00-05:00', '2026-11-02T00:00:00-06:00', 25),
    ('Europe/London', '2026-03-29', '2026-03-29T00:00:00+00:00', '2026-03-30T00:00:00+01:00', 23),
    ('Europe/London', '2026-10-25', '2026-10-25T00:00:00+01:00', '2026-10-26T00:00:00+00:00', 25),
    ('Australia/Sydney', '2026-04-05', '2026-04-05T00:00:00+11:00', '2026-04-06T00:00:00+10:00', 25),
    ('Australia/Sydney', '2026-10-04', '2026-10-04T00:00:00+10:00', '2026-10-05T00:00:00+11:00', 23),
    ('Australia/Lord_Howe', '2026-04-05', '2026-04-05T00:00:00+11:00', '2026-04-06T00:00:00+10:30', 24.5),
    ('America/Sao_Paulo', '2018-11-04', '2018-11-04T01:00:00-02:00', '2018-11-05T00:00:00-02:00', 23),
])
def test_dst_days_cover_actual_instants_exactly_once(zone, day, start, end, hours):
    result = selection(day, zone)
    assert_partition(result, start, end)
    rows = intervals(result)
    duration = sum((datetime.fromisoformat(r['end']) - datetime.fromisoformat(r['start'])).total_seconds()
                   for r in rows)
    assert duration == hours * 3600
    assert any('timezone_transition' in r['boundary_reasons'] for r in rows)
    for row in rows:
        for key in ('start', 'end'):
            instant = datetime.fromisoformat(row[key])
            assert instant.astimezone(ZoneInfo(zone)).isoformat() == row[key]


def test_fold_has_two_distinct_one_oclock_starts_and_gap_has_no_imaginary_two():
    folded = intervals(selection('2026-11-01', 'America/New_York'))
    assert [r['start'] for r in folded if r['start'][11:16] == '01:00'] == [
        '2026-11-01T01:00:00-04:00', '2026-11-01T01:00:00-05:00']
    spring = intervals(selection('2026-03-08', 'America/New_York'))
    assert not any(r['start'][11:13] == '02' for r in spring)


def test_skipped_civil_date_has_no_fabricated_midnight_or_chart():
    empty = selection('2011-12-30', 'Pacific/Apia')
    assert empty['candidates'] == empty['excluded_windows'] == []
    assert empty['excluded'] == {} and empty['skipped_dates'] == ['2011-12-30']
    surrounding = selection('2011-12-29', 'Pacific/Apia', 3)
    assert_partition(surrounding, '2011-12-29T00:00:00-10:00', '2012-01-01T00:00:00+14:00')
    assert surrounding['skipped_dates'] == ['2011-12-30']


@pytest.mark.parametrize('damage', ['drop', 'duplicate', 'reverse'])
def test_union_checker_detects_missing_or_multiply_counted_instants(damage):
    broken = copy.deepcopy(selection('2026-11-06'))
    if damage == 'drop':
        broken['candidates'].pop()
    elif damage == 'duplicate':
        broken['candidates'].append(broken['candidates'][0])
    else:
        row = broken['candidates'][0]
        row['start'], row['end'] = row['end'], row['start']
    with pytest.raises(AssertionError, match='gap or overlap|empty or reversed|incomplete coverage'):
        assert_partition(broken, '2026-11-06T00:00:00+08:00', '2026-11-07T00:00:00+08:00')


def test_late_zi_matches_explicit_futou_dunjia_cast_at_2330():
    late = next(row for row in selection('2026-11-06')['candidates'] if row['window'] == '23:00–24:00')
    cast = run_cli('qimen_cast.py', '--date', '2026-11-06', '--time', '23:30',
                   '--target-timezone', 'Asia/Shanghai', '--plate-method', 'dunjia-zhuanpan',
                   '--ju-method', 'futou')
    assert cast['method_profile']['plate_method'] == 'dunjia-zhuanpan'
    assert cast['method_profile']['ding_ju'] == 'futou'
    assert late['ganzhi'] == {key: cast['ganzhi'][key] for key in ('day', 'hour')} == {'day': '甲申', 'hour': '丙子'}
    expected = judge(dict(late, patterns=cast['patterns']))
    assert isinstance(expected, dict) and expected['auspicious'] == late['auspicious']


@pytest.mark.parametrize('zone,day,time,fold', [
    ('America/New_York', '2026-11-01', '01:30', '0'),
    ('America/New_York', '2026-11-01', '01:30', '1'),
    ('America/Chicago', '2026-03-08', '03:30', '0'),
    ('Europe/London', '2026-10-25', '01:30', '1'),
    ('Australia/Sydney', '2026-04-05', '02:30', '1'),
])
def test_timezone_samples_use_the_same_explicit_cast_method(zone, day, time, fold):
    cast = run_cli('qimen_cast.py', '--date', day, '--time', time, '--fold', fold,
                   '--target-timezone', zone, '--plate-method', 'dunjia-zhuanpan', '--ju-method', 'futou')
    instant = datetime.fromisoformat(cast['time_context']['local']).astimezone(UTC)
    row = next(r for r in intervals(selection(day, zone))
               if datetime.fromisoformat(r['start']).astimezone(UTC) <= instant
               < datetime.fromisoformat(r['end']).astimezone(UTC))
    classified = judge(dict(row, patterns=cast['patterns'], ganzhi=cast['ganzhi'],
                           ju=f'{cast["ju_type"]}{cast["ju_number"]}局（{cast["jieqi"]}{cast["san_yuan"]}）'))
    if 'reason' in row:
        assert classified == row['reason']
    else:
        assert isinstance(classified, dict)
        assert classified['auspicious'] == row['auspicious']
        assert classified['ju'] == row['ju']


def test_original_n22_veto_remains_an_exclusion():
    result = selection('2026-11-11')
    row = next(r for r in result['excluded_windows'] if r['window'] == '15:00–17:00')
    assert row['reason'] == '只有本旬直符未同临的三奇得使'
    assert not any(r['window'] == '15:00–17:00' for r in result['candidates'])


@pytest.mark.parametrize('oracle,previous', [(SXTWL['terms'][0], '芒种'), (SXTWL['terms'][1], '霜降')])
def test_independent_sxtwl_brackets_term_and_exact_provider_cut(oracle, previous):
    independent = datetime.fromisoformat(oracle['utc'])
    local = independent.astimezone(ZoneInfo('Asia/Shanghai'))
    result = selection(local.date().isoformat())
    rows = intervals(result)
    cut_row = next(row for row in rows if 'solar_term' in row['boundary_reasons'])
    boundary = datetime.fromisoformat(cut_row['start'])
    # SXTWL 2.0.7 extrapolates an obsolete delta-T. Preserve its raw difference
    # separately from the TT-to-UTC correction, which is scoped to these fixtures.
    assert 10 < abs((boundary.astimezone(UTC) - independent).total_seconds()) < 30
    corrected = datetime.fromisoformat(oracle['timescale_corrected_utc'])
    assert abs((boundary.astimezone(UTC) - corrected).total_seconds()) < 1
    assert dunjia_futou((corrected - timedelta(seconds=1)).astimezone(ZoneInfo('Asia/Shanghai')))['solar_term']['name'] == previous
    assert dunjia_futou((corrected + timedelta(seconds=1)).astimezone(ZoneInfo('Asia/Shanghai')))['solar_term']['name'] == oracle['name']
    assert boundary.second != 0
    before = dunjia_futou(boundary - timedelta(seconds=1))
    after = dunjia_futou(boundary)
    assert before['solar_term']['name'] == previous
    assert after['solar_term']['name'] == oracle['name']
    assert before['ju_number'] != after['ju_number'] or before['ju_type'] != after['ju_type']
    index = rows.index(cut_row)
    assert rows[index - 1]['end'] == cut_row['start']
    for row, chart in ((rows[index - 1], before), (cut_row, after)):
        classified = judge(dict(row, patterns=chart['patterns'], ganzhi=chart['ganzhi'],
                               ju=f'{chart["ju_type"]}{chart["ju_number"]}局（{chart["solar_term"]["name"]}{chart["san_yuan"]}）'))
        assert classified == row['reason'] if 'reason' in row else classified['auspicious'] == row['auspicious']


def test_boundary_provider_failure_is_not_a_partial_success(monkeypatch, capsys):
    def broken_provider(start, end):
        raise ValueError('fixture term table is incomplete')
    monkeypatch.setattr(qimen_select, 'solar_term_boundaries', broken_provider)
    assert qimen_select.main(['--from', '2026-11-06', '--days', '1', '--target-timezone', 'Asia/Shanghai']) == 1
    output = json.loads(capsys.readouterr().out)
    assert output['ok'] is False and output['error'] == 'interval_calculation_failed'
    assert 'candidates' not in output
