"""The default reading input must expose facts, never quietly reintroduce diagnostic verdicts."""
from copy import deepcopy

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import observed_structure, prepare_reading, render_facts
from reading_support import review_claims


@pytest.fixture
def chart():
    return calculate_bazi(build_parser().parse_args([
        '--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
        '--minute', '30', '--gender', 'male', '--as-of-year', '2026']))


def test_reading_facts_are_valid_without_diagnostic_claims(chart):
    before = deepcopy(chart)
    result = prepare_reading(chart, '用神怎么判断')
    assert chart == before
    assert review_claims(chart, result['reading_support']) == []
    assert not {'day_master_strength', 'wuxing_count', 'shen_sha', 'ge_ju',
                'yong_shen', 'xi_shen', 'ji_shen'} & result['chart_facts'].keys()
    assert result['method_profile']['primary_book'] == 'ziping'
    assert result['evidence_bundle']['passages']
    assert all(p['passage_id'] for p in result['evidence_bundle']['passages'])
    assert any('成败救应' in p['chapter_title'] or '成敗救應' in p['chapter_title']
               for p in result['evidence_bundle']['chapters'].values())
    assert any('正官' in p['chapter_title'] for p in result['evidence_bundle']['chapters'].values())


def test_actual_exposure_and_hidden_positions_are_reported(chart):
    structure = observed_structure(chart)
    ji = next(s for s in structure['month_hidden_stems'] if s['stem'] == '己')
    assert ji['role'] == '正官' and ji['exposed_at'] == ['year']
    gui = next(s for s in structure['month_hidden_stems'] if s['stem'] == '癸')
    assert gui['exposed_at'] == []
    assert next(s for s in structure['exposed_stems'] if s['stem'] == '己')['same_stem_hidden_at']


def test_unknown_hour_does_not_invent_exposure(chart):
    chart['four_pillars']['hour'] = {'status': '时柱待补'}
    chart['hour_known'] = False
    result = prepare_reading(chart)
    assert all(s['pillar'] != 'hour' for s in result['observed_structure']['exposed_stems'])
    assert '时柱暂缺' in render_facts(result)
    assert review_claims(chart, result['reading_support']) == []


def test_bad_chart_and_missing_primary_source_fail_closed(chart, monkeypatch):
    with pytest.raises(ValueError, match='成功'):
        prepare_reading({'ok': False})
    def missing(*args, **kwargs):
        raise ValueError('主体系原文检索失败')
    monkeypatch.setattr('bazi_reading.get_passage', missing)
    with pytest.raises(ValueError, match='原文检索'):
        prepare_reading(chart)


def test_reader_text_explains_terms_and_specific_route_conditions(chart):
    text = render_facts(prepare_reading(chart))
    assert '这里的“藏”' in text and '“透”' in text
    assert '遇伤检查佩印' in text and '未满足' in text
    assert all(word not in text for word in ('必定', '事业天花板', '富贵', '分数', 'JSON'))


def _unknown_chart(month=1, day=15, **options):
    params = ['--year', '2026', '--month', str(month), '--day', str(day),
              '--gender', 'male', '--city', '北京', '--time-standard', 'clock']
    for key, value in options.items():
        params.extend(['--' + key.replace('_', '-'), str(value)])
    return calculate_bazi(build_parser().parse_args(params))


def test_unknown_hour_removes_all_placeholder_precision_and_keeps_stable_pillars():
    chart = _unknown_chart()
    before = deepcopy(chart)
    result = prepare_reading(chart)
    facts = result['chart_facts']
    assert chart == before
    assert 'hour' not in facts['solar_date'] and 'minute' not in facts['solar_date']
    assert 'time_in_ganzhi' not in facts['lunar_date']
    assert not {'clock_time', 'true_solar_time', 'effective_date'} & facts['true_solar_time'].keys()
    assert facts['qi_yun'] is None and facts['da_yun'] == []
    assert facts['qi_yun_status'] == 'birth_time_required'
    assert facts['birth_time_uncertainty']['affected_pillars'] == []
    assert facts['birth_time_uncertainty']['checked_clock_times'] == ['00:00', '12:00', '23:59']
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'minute_grid_verified'
    assert all(facts['four_pillars'][k] == chart['four_pillars'][k] for k in ('year', 'month', 'day'))
    assert review_claims(facts, result['reading_support']) == []


def test_lichun_day_without_hour_cannot_assert_one_year_or_month():
    result = prepare_reading(_unknown_chart(2, 4))
    facts = result['chart_facts']
    assert facts['four_pillars']['year']['candidate_ganzhi'] == ['丙午', '乙巳']
    assert facts['four_pillars']['month']['candidate_ganzhi'] == ['己丑', '庚寅']
    assert facts['four_pillars']['day']['ganzhi'] == '己酉'
    assert result['observed_structure']['month_hidden_stems'] == []
    assert result['observed_structure']['exposed_stems'] == []
    assert review_claims(facts, result['reading_support']) == []
    assert '年柱、月柱存在时间边界' in render_facts(result)


@pytest.mark.parametrize('options', [{'sect': 1}, {'time_standard': 'true-solar'}])
def test_unknown_hour_day_boundary_suppresses_day_master_roles(options):
    result = prepare_reading(_unknown_chart(**options))
    facts = result['chart_facts']
    assert 'day' in facts['birth_time_uncertainty']['affected_pillars']
    assert 'stem' not in facts['day_master']
    assert result['observed_structure']['exposed_stems'] == []
    assert review_claims(facts, result['reading_support']) == []


def test_unknown_hour_boundary_probes_do_not_read_current_clock(monkeypatch):
    from datetime import datetime

    import request_time

    chart = _unknown_chart(current_timezone='Australia/Sydney', request_time='2026-09-06T04:00:00Z')
    class NoClock(datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError('natal boundary probe must not sample the clock')
    monkeypatch.setattr(request_time, 'datetime', NoClock)
    result = prepare_reading(chart)
    assert result['chart_facts']['current_time_context']['utc'] == '2026-09-06T04:00:00+00:00'


def test_unknown_hour_true_solar_dates_do_not_retain_the_internal_noon_date():
    facts = prepare_reading(_unknown_chart(time_standard='true-solar'))['chart_facts']
    assert facts['solar_date']['candidate_dates'] == [
        {'year': 2026, 'month': 1, 'day': 14}, {'year': 2026, 'month': 1, 'day': 15}]
    assert facts['lunar_date']['status'] == 'birth_time_required'
    assert len(facts['lunar_date']['candidate_dates']) == 2
    assert 'day' not in facts['lunar_date']


def test_fall_back_day_keeps_all_three_true_solar_dates_and_day_pillars():
    # The 25-hour New York civil day spans three solar dates. Endpoints alone
    # see Nov 2/4 and 庚午/壬申; the actual middle date/day cannot be discarded.
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '2024', '--month', '11', '--day', '3', '--gender', 'male',
        '--timezone', 'America/New_York', '--longitude', '-74.006',
        '--time-standard', 'true-solar', '--sect', '2']))
    facts = prepare_reading(chart)['chart_facts']
    assert facts['solar_date']['candidate_dates'] == [
        {'year': 2024, 'month': 11, 'day': 2},
        {'year': 2024, 'month': 11, 'day': 3},
        {'year': 2024, 'month': 11, 'day': 4}]
    assert facts['lunar_date']['candidate_dates'] == [
        {'year': 2024, 'month': 10, 'day': 2},
        {'year': 2024, 'month': 10, 'day': 3},
        {'year': 2024, 'month': 10, 'day': 4}]
    assert set(facts['four_pillars']['day']['candidate_ganzhi']) == {'庚午', '辛未', '壬申'}
    assert facts['birth_time_uncertainty']['status'] == 'day_samples_verified'
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'minute_grid_verified'
    assert facts['birth_time_uncertainty']['checked_clock_times'] == ['00:00', '12:00', '23:59']
    assert facts['day_master'] == {'status': 'birth_time_required'}
    assert 'birth_instant_utc' not in facts['calendar_context']
    assert 'hour' not in facts['solar_date'] and facts['qi_yun'] is None


def test_unknown_hour_failed_endpoint_does_not_certify_remaining_samples(monkeypatch):
    chart = _unknown_chart()

    def fail_midnight(args):
        return {'ok': False, 'error': 'invalid_time'} if args.hour == 0 else calculate_bazi(args)

    monkeypatch.setattr('bazi_reading.calculate_bazi', fail_midnight)
    facts = prepare_reading(chart)['chart_facts']
    uncertainty = facts['birth_time_uncertainty']
    assert uncertainty['status'] == 'boundary_check_unavailable'
    assert uncertainty['candidate_coverage'] == 'incomplete'
    assert uncertainty['checked_clock_times'] == ['12:00', '23:59']
    assert uncertainty['failed_clock_times'] == ['00:00']
    assert uncertainty['affected_pillars'] == ['year', 'month', 'day']
    assert all('ganzhi' not in facts['four_pillars'][key] for key in ('year', 'month', 'day'))
    assert facts['solar_date']['status'] == 'birth_time_required'
    assert facts['lunar_date']['status'] == 'birth_time_required'


def test_unknown_hour_three_matching_samples_do_not_hide_uncovered_minutes(monkeypatch):
    from bazi_reading import normalize_birth_time

    chart = _unknown_chart()

    def unsampled_date(year, month, day, hour, minute, *args):
        normalized = normalize_birth_time(year, month, day, hour, minute, *args)
        if (hour, minute) == (7, 13):
            normalized['solar_date']['day'] = 16
        return normalized

    monkeypatch.setattr('bazi_reading.normalize_birth_time', unsampled_date)
    facts = prepare_reading(chart)['chart_facts']
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'incomplete'
    assert facts['birth_time_uncertainty']['affected_pillars'] == ['year', 'month', 'day']
    assert 'ganzhi' not in facts['four_pillars']['day']


def test_unknown_hour_normalization_error_is_not_silently_treated_as_a_dst_gap(monkeypatch):
    from bazi_reading import normalize_birth_time

    chart = _unknown_chart()

    def fail_minute(year, month, day, hour, minute, *args):
        if (hour, minute) == (7, 13):
            raise ValueError('时区解析失败')
        return normalize_birth_time(year, month, day, hour, minute, *args)

    monkeypatch.setattr('bazi_reading.normalize_birth_time', fail_minute)
    facts = prepare_reading(chart)['chart_facts']
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'incomplete'
    assert 'stem' not in facts['day_master']


def test_unknown_hour_spring_forward_gap_is_not_a_birth_candidate():
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '2024', '--month', '3', '--day', '10', '--gender', 'male',
        '--timezone', 'America/New_York', '--longitude', '-74.006',
        '--time-standard', 'clock', '--sect', '2']))
    facts = prepare_reading(chart)['chart_facts']
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'minute_grid_verified'
    assert facts['birth_time_uncertainty']['affected_pillars'] == []
    assert facts['solar_date'] == {'year': 2024, 'month': 3, 'day': 10}


def test_stable_corrected_date_and_day_master_replace_provisional_noon_together():
    # With the explicit longitude and timezone, Auckland's 23-hour spring
    # day maps entirely onto Sept 28. The uncorrected placeholder was Sept 29.
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '2024', '--month', '9', '--day', '29', '--gender', 'male',
        '--timezone', 'Pacific/Auckland', '--longitude', '-179',
        '--time-standard', 'true-solar', '--sect', '2', '--as-of-year', '2026']))
    assert chart['day_master']['stem'] == '丙'
    facts = prepare_reading(chart)['chart_facts']
    assert facts['birth_time_uncertainty']['candidate_coverage'] == 'minute_grid_verified'
    assert facts['solar_date'] == {'year': 2024, 'month': 9, 'day': 28}
    assert facts['lunar_date']['day'] == 26
    assert facts['four_pillars']['day']['ganzhi'] == '乙未'
    assert facts['day_master']['stem'] == '乙'
    assert facts['liu_nian'][0]['ganzhi'] == '丙午'
    assert facts['liu_nian'][0]['shi_shen'] == '伤官'


def test_explicit_year_and_missing_current_zone_status_survive_adapter():
    implicit = prepare_reading(_unknown_chart())['chart_facts']
    explicit = prepare_reading(_unknown_chart(as_of_year=2027))['chart_facts']
    assert implicit['liu_nian_status'] == 'needs_current_timezone'
    assert explicit['liu_nian_status'] == 'explicit_year'
    assert explicit['liu_nian'][0]['year'] == 2027


def test_january_year_list_is_not_claimed_to_be_the_active_lichun_year():
    result = prepare_reading(_unknown_chart(current_timezone='Australia/Sydney',
                                           request_time='2026-12-31T14:00:00Z'))['chart_facts']
    assert result['liu_nian'][0]['year'] == 2027
    assert result['liu_nian_scope'] == 'calendar_year_reference_list'
    assert '立春' in result['liu_nian_note']
