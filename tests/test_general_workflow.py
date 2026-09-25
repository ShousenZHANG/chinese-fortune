"""Independent regression scenarios for the agreed common workflow."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from classical_search import climate_passages, get_passage
from fortune_reading import read_request, render_answer
from research_session import begin, finish, load, record, review, search


@pytest.fixture
def request_data():
    return {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-24T01:00:00Z',
            'period': {'start': '2026-10-13', 'end': '2026-10-16'},
            'event': {'scenario': 'travel', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'},
            'participants': [{'id': 'A', 'confirmed': True, 'person': {
                'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30,
                          'gender': 'male', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock'},
                'time_certainty': 'exact'}}],
            'duration_minutes': 120,
            'candidates': [{'id': 'oct13', 'start': '2026-10-13T12:00', 'end': '2026-10-13T14:00'}],
            'granularity': 'hour'}


def test_entire_event_in_conflicting_hours_never_becomes_recommendation(request_data):
    result = read_request(request_data)
    assert result['recommendation']['status'] == 'clause_conflict'
    assert result['recommendation']['first_choice'] is None
    assert any(b['code'] == 'clause_conflict' for b in result['decision_blockers'])
    lead = render_answer(result).splitlines()[0]
    assert '推荐' in lead and '不能' in lead
    assert '就定' not in lead


def test_single_event_checks_existing_calendar_rules_for_the_whole_interval(request_data):
    request_data['intent'] = 'event'
    by_candidate = read_request(request_data)
    request_data.pop('candidates')
    request_data['period'] = {'start': '2026-10-13T12:00', 'end': '2026-10-13T14:00'}
    by_interval = read_request(request_data)
    for result in (by_candidate, by_interval):
        assert result['recommendation']['status'] == 'clause_conflict'
        assert result['conclusion']['calendar_screening_scope'] == 'generic_calendar_filter'
    request_data['duration_minutes'] = 60
    with pytest.raises(ValueError, match='不一致'):
        read_request(request_data)


def test_unknown_lichun_birth_retains_year_candidates_without_crashing(request_data):
    person = request_data['participants'][0]['person']
    person['birth'].update(month=2, day=4)
    person['birth'].pop('hour')
    person['birth'].pop('minute')
    person['time_certainty'] = 'unknown'
    result = read_request(request_data)
    assert set(result['participants'][0]['natal']['four_pillars']['year']['candidate_ganzhi']) == {'己卯', '庚辰'}
    assert result['ranking']['rule_scope'] == 'generic_calendar_filter'


def test_multiple_people_do_not_default_to_first_for_recommendation(request_data):
    other = deepcopy(request_data['participants'][0])
    other['id'] = 'B'
    other['person']['birth'].update(year=1991, month=5, day=9)
    request_data['participants'].append(other)
    result = read_request(request_data)
    assert result['recommendation']['status'] == 'participant_priority_required'
    assert result['conclusion']['status'] == 'participant_priority_required'
    assert result['practical_choice']['first_choice'] is None


def test_new_scenario_and_explicit_real_preference_produce_dated_choices(request_data):
    request_data['event']['scenario'] = '讨论社团活动'
    request_data['intent'] = 'selection'
    request_data['question'] = '我希望尽早安排，哪天能讨论两小时？'
    request_data['preferences'] = {'prefer': 'earliest'}
    request_data['candidates'].append({'id': 'backup', 'start': '2026-10-15T12:00', 'end': '2026-10-15T15:00'})
    result = read_request(request_data)
    assert result['capability']['custom']
    assert result['recommendation']['basis'] == 'practical_constraints'
    assert result['practical_choice']['first_choice']['start'] == '2026-10-13T12:00:00+08:00'
    assert result['practical_choice']['backup']['end'] == '2026-10-15T14:00:00+08:00'
    assert result['conclusion']['traditional_personal_ranking'] == 'not_established'
    lead = render_answer(result).splitlines()[0]
    assert 'Asia/Shanghai' in lead and '档期' in lead and '备选' in lead


def test_natal_change_cannot_turn_generic_screen_into_personal_ranking(request_data):
    first = read_request(request_data)
    request_data['participants'][0]['person']['birth'].update(year=1990, month=5, day=10)
    second = read_request(request_data)
    assert first['ranking']['tiers'] == second['ranking']['tiers']
    for result in (first, second):
        assert result['ranking']['uses_complete_natal_chart'] is False
        assert '没有用完整八字' in render_answer(result)


def test_two_available_windows_without_preference_do_not_get_arbitrary_choice(request_data):
    request_data['event']['scenario'] = '讨论社团活动'
    request_data['intent'] = 'selection'
    request_data['candidates'].append({'id': 'B', 'start': '2026-10-15T12:00', 'end': '2026-10-15T15:00'})
    result = read_request(request_data)
    assert result['practical_choice']['status'] == 'preferences_required'
    assert result['conclusion']['status'] == 'preferences_required'
    assert '偏好' in render_answer(result).splitlines()[0]
    assert result['recommendation']['first_choice'] is None


def test_practical_event_end_uses_actual_dst_offset(request_data):
    request_data['event'].update(scenario='讨论社团活动', timezone='Australia/Sydney')
    request_data['intent'] = 'selection'
    request_data['period'] = {'start': '2026-10-04', 'end': '2026-10-05'}
    request_data['candidates'] = [{'id': 'dst', 'start': '2026-10-04T01:30', 'end': '2026-10-04T04:30'}]
    result = read_request(request_data)
    choice = result['practical_choice']['first_choice']
    assert choice['start'] == '2026-10-04T01:30:00+10:00'
    assert choice['end'] == '2026-10-04T04:30:00+11:00'


def test_birth_range_keeps_stable_hour_instead_of_discarding_whole_day(request_data):
    person = request_data['participants'][0]['person']
    person.update(time_certainty='approximate', birth_time_range={'start': '19:00', 'end': '20:00'})
    result = read_request(request_data)
    natal = result['participants'][0]['natal']
    assert natal['hour_known'] is True
    assert natal['four_pillars']['hour']['branch'] == '戌'
    assert natal['birth_time_uncertainty']['status'] == 'interval_verified'
    assert natal['calendar_context']['birth_instant_utc'] is None
    assert '19:00–20:00' in render_answer(result)


def test_birth_range_crossing_hour_keeps_both_branches(request_data):
    person = request_data['participants'][0]['person']
    person.update(time_certainty='approximate', birth_time_range={'start': '18:59', 'end': '19:01'})
    natal = read_request(request_data)['participants'][0]['natal']
    assert natal['hour_known'] is False
    assert {p[1] for p in natal['four_pillars']['hour']['candidate_ganzhi']} == {'酉', '戌'}


def test_month_lookup_returns_actual_geng_zi_section_and_variants_follow_passages():
    result = climate_passages('庚|子')
    assert 'qiongtong:c005:p0114' in {r['passage_id'] for r in result['results']}
    assert all('十一月庚金' in r['section'] for r in result['results'])
    passage = get_passage('ziping:c010:p0006')
    assert '難通月氣' in passage['text']
    assert passage['quality_notes']
    assert any(w['variants'] for w in passage['witnesses'])
    assert passage['facsimile_status'] == 'not_checked'


def test_research_budget_expires_without_inventing_searches(tmp_path):
    now = datetime(2026, 9, 24, tzinfo=UTC)
    r = begin('出行', root=tmp_path, clock=now)
    assert r['queries'] == []
    ident = r['research_id']
    assert load(ident, root=tmp_path, clock=now + timedelta(seconds=299))['may_search']
    with pytest.raises(ValueError, match='5分钟'):
        record(ident, '出行', root=tmp_path, clock=now + timedelta(seconds=300))
    result = finish(ident, 'budget_expired', root=tmp_path, clock=now + timedelta(seconds=302))
    assert result['elapsed_seconds'] == 302
    assert result['candidates'] == []


def test_candidate_review_does_not_register_an_executable_rule(tmp_path):
    r = begin('出行', root=tmp_path)
    source = {'title': '测试古籍', 'edition': '独立测试版本', 'source_url': 'https://example.org/scan',
              'locator': '卷一页一', 'quote': '某条件', 'context': '前文某条件后文',
              'conditions': '须核某条件', 'exceptions': '尚待核对', 'modern_mapping': '',
              'verification_notes': '测试夹具，不是真实古籍核验'}
    candidate = record(r['research_id'], '出行', source=source, root=tmp_path)['candidates'][0]
    checks = dict.fromkeys(('reviewer', 'source_verification', 'applicability', 'exceptions', 'counterexample', 'conclusion'), '测试记录，不认证解释')
    reviewed = review(r['research_id'], candidate['source_sha256'], checks, root=tmp_path)['candidates'][0]
    assert reviewed['status'] == 'review_recorded' and reviewed['executable'] is False
    assert search('出行', root=tmp_path)['total_matches'] == 1
    finish(r['research_id'], 'sufficient_sources', root=tmp_path)
    assert not load(r['research_id'], root=tmp_path)['may_search']


def test_fabricated_quote_is_not_saved(tmp_path):
    r = begin('出行', root=tmp_path)
    source = dict.fromkeys(('title', 'edition', 'locator', 'quote', 'context', 'conditions', 'exceptions', 'modern_mapping', 'verification_notes'), '文本')
    source.update(source_url='https://example.org/scan', quote='原文没有这句')
    with pytest.raises(ValueError, match='上下文'):
        record(r['research_id'], '出行', source=source, root=tmp_path)
    assert load(r['research_id'], root=tmp_path)['candidates'] == []


def test_omitted_han_fold_is_detected_even_with_correct_corpus_hash(tmp_path, monkeypatch):
    import json

    import build_han_variants as builder

    table = json.loads(builder.TABLE.read_text(encoding='utf-8'))
    assert table['mapping'].pop('慶') == '庆'
    changed = tmp_path / 'mutated.json'
    changed.write_text(json.dumps(table), encoding='utf-8')
    monkeypatch.setattr(builder, 'TABLE', changed)
    assert builder.main(['--check']) == 1


def test_research_cli_rejects_path_escape_without_creating_files(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    proc = subprocess.run([sys.executable, '-X', 'utf8',
                           str(Path(__file__).parents[1] / 'scripts/research_session.py'),
                           'status', '--stdin', '--data-dir', str(tmp_path)],
                          input=json.dumps({'research_id': '../outside'}),
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 1
    assert json.loads(proc.stdout)['error'] == 'invalid_research'
    assert 'Traceback' not in proc.stderr
    assert not list(tmp_path.iterdir())


def _source(**change):
    source = {'title': '测试古籍', 'edition': '独立测试版本', 'source_url': 'https://example.org/scan',
              'locator': '卷一页一', 'quote': '某条件', 'context': '前文某条件后文',
              'conditions': '须核某条件', 'exceptions': '', 'modern_mapping': '',
              'verification_notes': '测试夹具，不是真实古籍核验'}
    return {**source, **change}


def test_research_cannot_claim_sufficient_sources_without_one(tmp_path):
    r = begin('出行', root=tmp_path)
    record(r['research_id'], '出行', root=tmp_path)  # a search that found nothing
    with pytest.raises(ValueError, match='没有候选来源'):
        finish(r['research_id'], 'sufficient_sources', root=tmp_path)
    assert load(r['research_id'], root=tmp_path)['status'] == 'in_progress'


def test_research_source_url_may_not_carry_credentials(tmp_path):
    r = begin('出行', root=tmp_path)
    for url in ('https://user:secret@example.org/scan', 'ftp://example.org/scan', 'https:///scan'):
        with pytest.raises(ValueError, match='无凭据'):
            record(r['research_id'], '出行', source=_source(source_url=url), root=tmp_path)
    assert load(r['research_id'], root=tmp_path)['candidates'] == []


def test_research_stopped_after_the_deadline_is_recorded_as_expired(tmp_path):
    """A late 「no applicable source」 would hide that the five minutes ran out."""
    now = datetime(2026, 9, 24, tzinfo=UTC)
    r = begin('出行', root=tmp_path, clock=now)
    result = finish(r['research_id'], 'no_applicable_source', root=tmp_path, clock=now + timedelta(seconds=301))
    assert result['stop_reason'] == 'budget_expired'
    early = begin('出行', root=tmp_path, clock=now)
    assert finish(early['research_id'], 'no_applicable_source', root=tmp_path,
                  clock=now + timedelta(seconds=10))['stop_reason'] == 'no_applicable_source'
