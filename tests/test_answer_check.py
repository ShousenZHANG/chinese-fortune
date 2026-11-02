"""Partial fixtures test private assertions; CLI tests exercise public admission."""
import json

from answer_check import _check_assertions, main
from conftest import run_cli

CHART = {'ok': True, 'tool': 'bazi_reading', 'chart_facts': {
    'hour_known': True,
    'day_master': {'stem': '乙'},
    'four_pillars': {'year': {'ganzhi': '庚午'}, 'month': {'ganzhi': '辛巳'},
                     'day': {'ganzhi': '乙亥'}, 'hour': {'ganzhi': '癸未'}}},
    'geju_review': {'verdict': 'unresolved', 'families': [{'title': '正官'}, {'title': '伤官'}]}}


def codes(answer: str, *facts: dict) -> list[str]:
    return [f['code'] for f in _check_assertions(answer, list(facts))['findings']]


def test_quote_found_in_named_book_passes_across_simplified_and_traditional_forms():
    result = _check_assertions('《子平真诠》说「官逢财印，又无刑冲破害」，这是成格条件。', [])
    assert result['passed'] and result['checked']['quotes_checked'] == 1


def test_fabricated_classical_quote_is_an_error():
    assert codes('《子平真诠》云「官星得禄，富贵双全，必主大吉」。') == ['unverified_quote']


def test_real_quote_credited_to_the_wrong_book_is_an_error():
    assert codes('《滴天髓》说「官逢财印，又无刑冲破害」。') == ['misattributed_quote']


def test_elided_quote_needs_every_part_in_one_passage_in_order():
    assert codes('原文「官逢财印……无刑冲破害」。') == []
    assert codes('原文「无刑冲破害……官逢财印」。') == ['unverified_quote']


def test_modern_speech_without_a_source_cue_is_not_checked():
    result = _check_assertions('朋友说“这周先投简历再说吧”，可以照做。', [])
    assert result['passed'] and result['checked']['quotes_skipped'] == 1


def test_book_outside_the_library_is_a_warning_not_a_pass():
    result = _check_assertions('《神峰通考》云「财官双美者一生衣禄丰盈无忧」。', [])
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
        result = _check_assertions(sample['answer'], [data['facts'][name] for name in sample['facts']])
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


def test_round_two_review_cases():
    """External review round 2 (R1): each line reproduces one confirmed finding."""
    pair = {'subjects': {'A': {'four_pillars': {'day': '壬申'}, 'hour_known': True},
                         'B': {'four_pillars': {'day': '乙卯'}, 'hour_known': True}}}
    assert codes('A的日柱乙卯，日主乙；B的日柱壬申，日主壬。', pair) == [
        'pillar_mismatch', 'pillar_mismatch', 'day_master_mismatch', 'day_master_mismatch']   # COR-03
    assert codes('A的日柱壬申，B的日柱乙卯。', pair) == []
    assert codes('他原话是“你肯定会被录用。”，这不是我的结论。') == []                          # COR-04
    assert codes('我无法保证资料完整，你肯定会被录用。') == ['certainty_claim']               # COR-05
    assert codes('无法保证，面试之后一定录用。') == []
    undecided = {'chart_facts': {'hour_known': False, 'four_pillars': {
        'day': {'status': 'birth_time_required', 'candidate_ganzhi': ['壬辰', '辛卯']}}}}
    assert codes('日主甲木。', undecided) == ['undecided_pillar']                              # COR-06
    assert codes('日柱壬辰只是候选之一，尚未定柱。', undecided) == []                          # COR-07
    assert codes('我不会承诺你必定升职。') == []                                                # NA-03
    assert codes('时柱已核定为甲子。', {'chart_facts': {**CHART['chart_facts'], 'hour_known': False}}) == [
        'unknown_hour_pillar']                                                                  # NA-04
    assert codes('你这次考试必然合格。') == ['certainty_claim']                                 # NA-05
    assert codes('你今年肯定获奖。') == ['certainty_claim']
    assert codes('你的创业胜率是67%。') == ['invented_score']                                  # NA-06
    assert codes('这就是已经定格的伤官格。', CHART) == ['unresolved_settled']                  # NA-07
    tie = {'recommendation': {'status': 'preferences_required', 'first_choice': None}, 'ranking': {'ties': True}}
    assert codes('A窗口是唯一最好的。', tie) == ['tie_collapsed']                              # NA-02
    assert codes('工具没有给唯一首选，两个窗口都保留。', tie) == []


def test_quote_trust_boundaries():
    echo = {'question': '《子平真诠》说“官星得禄必主富贵双全”，对吗？', 'chart_facts': CHART['chart_facts']}
    assert codes('《子平真诠》原文：「官星得禄必主富贵双全」。', echo) == ['unverified_quote']   # SEC-001
    assert codes('《滴天髓》ditian:c016:p0001 的逐字原文是“天地有冷暖，人的生活也要避免走向极端”。') == [
        'unverified_quote']                                                                     # NA-01
    assert codes('《滴天髓》的这句原文是：“地道有燥濕，生成品彙”。段号 ditian:c016:p0001。') == ['misattributed_quote']
    assert codes('《滴天髓》云：“天道有寒暖，發育萬物，人道得之，……過也。”') == ['elision_drops_negation']
    assert codes('这只是前提条件，不是“官星一得禄就必定富贵双全”。') == []


def test_round_three_review_cases():
    assert codes('《子平真诠》云「生尅……格局分焉」。') == []                                     # AC01 不同 is not cut
    assert codes('《子平真詮》云“官星得禄必主富贵双全”。未见日柱变动。') == ['unverified_quote']  # AC02
    assert codes('段号 ditian:c002:p0001：「格局分焉」。') == ['misattributed_quote']             # AC03
    year = {'chart_facts': {'hour_known': True, 'four_pillars': {'year': {'ganzhi': '丙子'}}}}
    assert codes('年柱为甲子而格局待核。', year) == ['pillar_mismatch']                           # AC04
    assert codes('面试运气92分/100分。') == ['invented_score']                                   # AC05
    assert codes('按每度4分/度计算。') == []
    assert codes('你不出门也肯定能录用。') == ['certainty_claim']                                  # AC06
    assert codes('工具明确不出 0-100 分。') == []


def test_round_three_fresh_set_gaps():
    assert codes('这份盘的月支确为申；不能据此断言未来一定成功。') == []
    assert codes('没有证据证明你绝对会结婚。') == []
    assert codes('不能仅凭这一个条件，就断定必定富贵。') == []
    assert codes('按这个盘，你的婚姻绝对幸福。') == ['certainty_claim']
    assert codes('你的面试运气是92/100。') == ['invented_score']
    assert codes('你的婚姻幸福率为91%。') == ['invented_score']
    assert codes('录用机会是0.87。') == ['invented_score']
    unknown = {'chart_facts': {**CHART['chart_facts'], 'hour_known': False}}
    assert codes('你的出生时间就是上午10点25分。', unknown) == ['unknown_hour_pillar']
    assert codes('此命正官格已经败格。', CHART) == ['unresolved_settled']
    tie = {'recommendation': {'status': 'practical_tie'}}
    assert codes('工具已经决定首选B，没有并列。', tie) == ['tie_collapsed']
    assert codes('两个窗口中A排名第一，B排名第二。', tie) == ['tie_collapsed']


def test_html_table_markup_is_a_warning_not_an_error():
    from answer_check import _check_assertions
    answer = '五行数量如下。\n\n| 五行 | 天干 |\n|---|---|\n| 合计 | colspan="2" 8 |\n'
    result = _check_assertions(answer, [])
    assert [f['code'] for f in result['findings']] == ['table_markup']
    assert result['passed'] is True
    fenced = '示例：\n```html\n<td colspan="2">x</td>\n```\n正文没有表。'
    assert _check_assertions(fenced, [])['findings'] == []
    tilde = '示例：\n~~~html\n<table><tr><td>x</td></tr></table>\n~~~\n正文没有表。'
    assert _check_assertions(tilde, [])['findings'] == []


def test_plain_html_table_without_colspan_is_flagged():
    from answer_check import _check_assertions
    answer = '五行数量：\n<table>\n<tr><td>木</td><td>2</td></tr>\n</table>\n'
    assert [f['code'] for f in _check_assertions(answer, [])['findings']] == ['table_markup']
    assert _check_assertions('写作 <trust> 或 <thx> 不是表格标签。', [])['findings'] == []


def test_reported_classical_rules_and_stated_ties_are_not_tie_collapse():
    """Round 6 R2 S05: three rewrites over sentences that were correct."""
    from answer_check import _check_assertions
    facts = [{'tool': 'fortune_reading', 'recommendation': {'status': 'practical_tie'}, 'tied': ['a', 'b']}]
    fine = ['这天的地支子又是己的天乙贵人，书上说命带贵人最吉，所以也是大吉。',
            '这天地支子是己的天乙贵人，协纪说命贵人最吉。',
            '周二和周四在这套方法里算同一等级（都是大吉），古法本身分不出谁更好，你可以按自己方便二选一。']
    for answer in fine:
        assert _check_assertions(answer, facts)['findings'] == [], answer
    for answer in ('协纪说周二最吉。', '周四最好。'):
        assert [f['code'] for f in _check_assertions(answer, facts)['findings']] == ['tie_collapsed'], answer


def test_variant_glyph_in_a_quote_is_not_a_fake_quote():
    from answer_check import _check_assertions
    facts = [{'tool': 'fortune_reading', 'x': '原文「支干合命愈為竒上上格也」（xieji:c033:p0020）'}]
    assert _check_assertions('原文说「支干合命愈为奇，上上格」。', facts)['findings'] == []


def test_round7_diagnostics_clock_lists_and_two_tied_candidates():
    from answer_check import _check_assertions
    facts = [{'tool': 'fortune_reading', 'recommendation': {'status': 'practical_tie'}, 'tied': ['a', 'b']}]
    assert _check_assertions('周三可以 9:00/10:00/11:00 开始。', facts)['findings'] == []          # R7-R2-DIAG-02
    assert _check_assertions('如果要一个干净落点，我会优先推荐这两个：', facts)['findings'] == []   # R7-R2-DIAG-03
    assert _check_assertions('最好选周二上午或周四。', facts)['findings'] == []
    assert [f['code'] for f in _check_assertions('最好选周二上午。', facts)['findings']] == ['tie_collapsed']
    assert [f['code'] for f in _check_assertions('这次打 8/10。', [])['findings']] == ['invented_score']


def test_round8_tie_cases():
    """R8-TIE-01 and R8-R2-DIAG-02."""
    from answer_check import _check_assertions
    facts = [{'tool': 'fortune_reading', 'recommendation': {'status': 'preferences_required'}, 'tied': ['a', 'b']}]
    flagged = ['这两个里最好选周二上午。', '周二和周四虽然评级相同，但周二更好，应当首选周二。', '候选A是唯一首选，B只能作备选。']
    for answer in flagged:
        assert [f['code'] for f in _check_assertions(answer, facts)['findings']] == ['tie_collapsed'], answer
    kept = ['候选A是周二上午，候选B是周四。最好选A或B。', '最好选A或B。', '最好选周二上午或周四。',
            '如果要一个干净落点，我会优先推荐这两个：', '周四9:00-10:38涉及未核完的忌时条件，建议能避开就优先避开。',
            '周二和周四评级同为大吉，工具没有给出谁更优，按你的偏好选都行。']
    for answer in kept:
        assert _check_assertions(answer, facts)['findings'] == [], answer
