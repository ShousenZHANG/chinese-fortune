"""Prose checks against the frozen books and the tool output behind an answer."""
import json

from answer_check import check_answer, main
from conftest import run_cli

CHART = {'chart_facts': {
    'hour_known': True,
    'day_master': {'stem': '乙'},
    'four_pillars': {'year': {'ganzhi': '庚午'}, 'month': {'ganzhi': '辛巳'},
                     'day': {'ganzhi': '乙亥'}, 'hour': {'ganzhi': '癸未'}}},
    'geju_review': {'verdict': 'unresolved', 'families': [{'title': '正官'}, {'title': '伤官'}]}}


def codes(answer: str, *facts: dict) -> list[str]:
    return [f['code'] for f in check_answer(answer, list(facts))['findings']]


def test_quote_found_in_named_book_passes_across_simplified_and_traditional_forms():
    result = check_answer('《子平真诠》说「官逢财印，又无刑冲破害」，这是成格条件。', [])
    assert result['passed'] and result['checked']['quotes_checked'] == 1


def test_fabricated_classical_quote_is_an_error():
    assert codes('《子平真诠》云「官星得禄，富贵双全，必主大吉」。') == ['unverified_quote']


def test_real_quote_credited_to_the_wrong_book_is_an_error():
    assert codes('《滴天髓》说「官逢财印，又无刑冲破害」。') == ['misattributed_quote']


def test_elided_quote_needs_every_part_in_one_passage_in_order():
    assert codes('原文「官逢财印……无刑冲破害」。') == []
    assert codes('原文「无刑冲破害……官逢财印」。') == ['unverified_quote']


def test_modern_speech_without_a_source_cue_is_not_checked():
    result = check_answer('朋友说“这周先投简历再说吧”，可以照做。', [])
    assert result['passed'] and result['checked']['quotes_skipped'] == 1


def test_book_outside_the_library_is_a_warning_not_a_pass():
    result = check_answer('《神峰通考》云「财官双美者一生衣禄丰盈无忧」。', [])
    assert [f['code'] for f in result['findings']] == ['quote_outside_library']
    assert result['passed']


def test_named_pillar_must_match_the_chart():
    assert codes('日柱是甲子，日主甲木。', CHART) == ['pillar_mismatch', 'day_master_mismatch']
    assert codes('日柱乙亥，日主乙木，时柱癸未。', CHART) == []


def test_hour_pillar_named_when_hour_unknown():
    unknown = {'chart_facts': {**CHART['chart_facts'], 'hour_known': False}}
    assert codes('时柱癸未。', unknown) == ['unknown_hour_pillar']


def test_scores_the_tool_never_gave_are_errors():
    assert codes('你们的匹配度是85分。') == ['invented_score']
    assert codes('成功率大概百分之七十。') == ['invented_score']
    assert codes('原文覆盖率85%。', {'coverage': '85%'}) == []


def test_certainty_about_outcomes_is_an_error_unless_negated():
    assert codes('你肯定能被录用。') == ['certainty_claim']
    assert codes('我不能说你肯定能被录用。') == []
    assert codes('日柱可以肯定是乙亥。', CHART) == []


def test_unresolved_formation_stated_as_settled():
    assert codes('你是正官格。', CHART) == ['unresolved_settled']
    assert codes('正官格只是候选，还要核月令。', CHART) == []
    assert codes('你是正官格。') == []


def test_tie_collapsed_into_a_single_best_day():
    tie = {'recommendation': {'status': 'tied_no_clause_separates', 'tied': ['a', 'b']}}
    assert codes('10月28日是最好的一天。', tie) == ['tie_collapsed']
    assert codes('这几天并列，按你的安排选。', tie) == []
    assert codes('10月28日是最好的一天。') == []


def test_cli_reports_findings_and_exit_status(tmp_path):
    answer = tmp_path / 'a.txt'
    facts = tmp_path / 'f.json'
    answer.write_text('日柱甲子。', encoding='utf-8')
    facts.write_text(json.dumps(CHART, ensure_ascii=False), encoding='utf-8')
    data = run_cli('answer_check.py', '--answer', answer, '--facts', facts, expect_rc=1)
    assert data['tool'] == 'answer_check' and not data['passed']
    assert data['findings'][0]['code'] == 'pillar_mismatch'
    answer.write_text('日柱乙亥。', encoding='utf-8')
    assert main(['--answer', str(answer), '--facts', str(facts)]) == 0


def test_cli_rejects_unreadable_facts(tmp_path):
    answer = tmp_path / 'a.txt'
    answer.write_text('日柱乙亥。', encoding='utf-8')
    data = run_cli('answer_check.py', '--answer', answer, '--facts', tmp_path / 'missing.json', expect_rc=1)
    assert data['ok'] is False


def test_quoted_or_clause_negated_certainty_is_not_an_assertion():
    assert codes('不能说“你肯定能被录用”。') == []
    assert codes('也不能说癸酉必然更好，结论不能说死。') == []
    assert codes('以上只是参考，不代表现实中一定顺利。') == []
    assert codes('无论如何，你一定能成功。') == ['certainty_claim']


def test_quote_reads_through_rare_glyph_markers_and_catches_paraphrase():
    assert codes('《协纪辨方书》说七杀「若至二点必凶」。') == []
    assert codes('书中说“财与官一两点都相宜”。') == ['unverified_quote']


def test_external_adversarial_set_is_classified_as_labelled():
    """104 samples from the external review (G1 R4): every label must hold."""
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'data' / 'answer_check_adversarial.json').read_text(encoding='utf-8'))
    wrong = []
    for sample in data['samples']:
        result = check_answer(sample['answer'], [data['facts'][name] for name in sample['facts']])
        got = {f['code'] for f in result['findings'] if f['severity'] == 'error'}
        ok = (not result['passed']) == sample['error'] and (
            not sample['error'] or not sample['codes_any'] or got & set(sample['codes_any']))
        if not ok:
            wrong.append((sample['id'], sorted(got)))
    assert not wrong


def test_chapter_titles_term_lists_and_clock_times_are_not_false_alarms():
    assert codes('《子平真诠》「論用神成敗救應」一章讲成败。') == []
    assert codes('《协纪辨方书》的相主原本用于“修造、用事”。') == []
    assert codes('若在 0 点至 0 点 31 分出生，日柱为乙卯；交节前1分08秒。') == []


def test_compressed_quote_of_a_real_passage_is_still_caught():
    assert codes('原文说"命禄最吉"。') == ['unverified_quote']


def test_only_a_table_headed_by_pillars_is_read_as_pillars():
    answer = ('| 年柱 | 月柱 | 日柱 | 时柱 |\n| --- | --- | --- | --- |\n| 庚午 | 辛巳 | 乙亥 | 癸未 |\n\n'
              '| 大运 | 年份 |\n| --- | --- |\n| 甲戌 | 2023—2032 |\n')
    assert codes(answer, CHART) == []


def test_tables_of_moments_or_candidates_are_not_the_birth_chart():
    answer = ('| 时刻 | 年柱 | 月柱 |\n| --- | --- | --- |\n| 2026-02-04 04:03 | 丙午 | 庚寅 |\n'
              '| 2026-02-04 03:00 | 乙巳 | 己丑 |\n')
    assert codes(answer, CHART) == []


def test_stdin_envelope_carries_answer_and_facts():
    import subprocess
    import sys

    from conftest import SCRIPTS
    done = subprocess.run([sys.executable, str(SCRIPTS / 'answer_check.py'), '--stdin'],
                          input=json.dumps({'answer': '日柱甲子。', 'facts': [CHART]}, ensure_ascii=False),
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 1 and json.loads(done.stdout)['findings'][0]['code'] == 'pillar_mismatch'
    bad = subprocess.run([sys.executable, str(SCRIPTS / 'answer_check.py'), '--stdin'], input='[]',
                         capture_output=True, text=True, encoding='utf-8')
    assert bad.returncode == 1 and json.loads(bad.stdout)['ok'] is False
