"""Cross-chart relation facts for two people, position by position."""
import json

from conftest import SCRIPTS
from pair_facts import pair_facts, subject_chart

A = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
     'timezone': 'Asia/Shanghai', 'longitude': 116.4}   # 己卯 丁丑 壬申 乙巳
B = {'year': 2001, 'month': 8, 'day': 20, 'hour': 15, 'minute': 20, 'gender': 'female',
     'timezone': 'Asia/Shanghai', 'longitude': 121.47}  # 辛巳 丙申 乙卯 甲申


def facts(a=A, b=B):
    return pair_facts(subject_chart(a), subject_chart(b))


def kinds(result, kind):
    return sorted((r['a'], r['b']) for r in result['relations'] if r['kind'] == kind)


def test_stem_and_branch_pairs_by_position():
    result = facts()
    assert kinds(result, 'tiangan_he') == [('年干己', '时干甲')]
    assert kinds(result, 'dizhi_liu_he') == [('日支申', '年支巳'), ('时支巳', '时支申'), ('时支巳', '月支申')]
    assert kinds(result, 'dizhi_chong') == [] and kinds(result, 'dizhi_hai') == []
    assert ('时支巳', '月支申') in kinds(result, 'dizhi_xing')
    assert ('月支丑', '年支巳') in kinds(result, 'ban_san_he')


def test_day_masters_seen_from_each_side():
    result = facts()
    assert result['day_masters'] == {'A': '壬', 'B': '乙', 'A_sees_B': '伤官', 'B_sees_A': '正印'}


def test_hidden_stem_combinations_are_labelled_by_school():
    result = facts()
    hidden = [r for r in result['relations'] if r['kind'] == 'canggan_he']
    assert any(r['a'] == '年支卯' and r['stems'] == ['乙', '庚'] for r in hidden)
    assert '暗合' in result['notes'][0]


def test_unknown_hour_drops_that_pillar_only():
    result = facts(a={k: v for k, v in A.items() if k not in ('hour', 'minute')})
    assert result['subjects']['A']['hour_known'] is False
    assert not any(r['a'].startswith('时') for r in result['relations'])
    assert any(r['b'].startswith('时') for r in result['relations'])


def test_full_trio_needs_both_charts():
    a = {**A, 'year': 1990, 'month': 5, 'day': 10, 'hour': 14}   # 庚午 辛巳 乙亥 癸未
    b = {**B, 'year': 1999, 'month': 3, 'day': 10, 'hour': 8}  # 己卯 year supplies 卯 for 亥卯未
    trios = [r for r in facts(a, b)['relations'] if r['kind'] == 'san_he']
    assert trios and all(r['from_a'] and r['from_b'] for r in trios)


def test_cli_reads_both_subjects_from_stdin():
    import subprocess
    import sys
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'pair_facts.py'), '--stdin'],
                          input=json.dumps({'a': A, 'b': B}), capture_output=True, text=True, encoding='utf-8')
    data = json.loads(proc.stdout)
    assert proc.returncode == 0 and data['tool'] == 'pair_facts' and data['relations']
    assert '不是' in data['boundary']
    bad = subprocess.run([sys.executable, str(SCRIPTS / 'pair_facts.py'), '--stdin'],
                         input=json.dumps({'a': A}), capture_output=True, text=True, encoding='utf-8')
    assert bad.returncode == 1 and json.loads(bad.stdout)['ok'] is False


def test_unknown_hour_on_a_term_day_leaves_moving_pillars_undecided():
    """立春当天、时辰未知：年月日柱都会随时刻变化，不能拿占位柱算关系或日主十神。"""
    a = {'year': 2000, 'month': 2, 'day': 4, 'gender': 'male', 'timezone': 'Asia/Shanghai'}
    result = facts(a=a)
    subject = result['subjects']['A']
    assert subject['four_pillars'] == {}
    assert subject['undecided_pillars']['year'] == ['己卯', '庚辰']
    assert subject['undecided_pillars']['day'] == ['壬辰', '辛卯']
    assert result['relations'] == []
    assert result['day_masters']['A'] is None and result['day_masters']['A_sees_B'] is None
    assert result['day_masters']['status'] == 'day_pillar_undecided'


def test_a_repeated_clock_time_can_be_disambiguated_with_fold():
    a = {'year': 2024, 'month': 11, 'day': 3, 'hour': 1, 'minute': 30, 'gender': 'male',
         'timezone': 'America/New_York', 'longitude': -74.006, 'fold': 0}
    assert facts(a=a)['subjects']['A']['four_pillars']['day']


def test_answer_check_reads_pair_facts_output():
    from answer_check import check_answer
    result = check_answer('A的日主为甲，年柱己卯。', [facts()])
    assert [f['code'] for f in result['findings']] == ['day_master_mismatch']


def test_same_pillar_branch_class_and_matched_clauses():
    result = facts()
    kinds = {(r['kind'], r['a'], r['b']) for r in result['relations']}
    assert ('same_branch_class', '年支卯', '日支卯') in kinds
    matched = {c['id'] for c in result['classical_clauses']['matched']}
    assert {'G5-C08', 'G5-C13'} <= matched  # 天干五合/六合 clauses
    assert '三元男女九宫合卦' not in result['classical_clauses']['not_computed_methods']
    assert result['classical_clauses']['computed_methods'] == ['三元男女九宫合卦']
    assert result['sanyuan_jiugong']['relation'] == '归魂'
    same_sex = facts(b={**B, 'gender': 'male'})
    assert same_sex['sanyuan_jiugong'] is None and '三元男女九宫合卦' in same_sex['classical_clauses']['not_computed_methods']
    twin = facts(b={**A, 'gender': 'female'})
    assert any(r['kind'] == 'same_pillar' and r['a'] == '日柱壬申' for r in twin['relations'])


def test_every_hehun_clause_quotes_its_hashed_passage():
    import hashlib
    from pathlib import Path

    from classical_search import get_passage, normalized
    data = json.loads((Path(SCRIPTS).parent / 'assets' / 'hehun_clauses.json').read_text(encoding='utf-8'))
    assert len(data['clauses']) == 17
    strip = str.maketrans('', '', '，。、；：「」')
    for clause in data['clauses']:
        text = get_passage(clause['passage_id'])['text']
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == clause['sha256'], clause['id']
        assert normalized(clause['quote'].translate(strip))[:12] in normalized(text.translate(strip)), clause['id']
        assert clause['forbidden_inferences']


def test_time_standard_field_reaches_the_calculator():
    result = facts(a={**A, 'time_standard': 'clock'})
    assert result['subjects']['A']['four_pillars']['day']


def test_say_groups_relations_by_family_and_ends_with_day_masters():
    lines = facts()['say']
    assert [line.split('：')[0] for line in lines[:7]] == ['合', '冲', '刑', '害', '会', '同柱', '同类地支']
    assert lines[0].startswith('合：A年干己—B时干甲')
    assert lines[1] == '冲：无'
    assert lines[-1] == '日主互见：A 日主壬看 B 日主乙为伤官；B 看 A 为正印'


def test_relation_type_decides_which_clauses_apply():
    """R1/R3: marriage clauses and 三元 only for a couple; parent-child gets its one clause; partners get none."""
    import pair_facts as pf
    a, b = subject_chart(A), subject_chart(B)
    parent = pf.pair_facts(a, b, 'parent_child')
    assert parent['relation']['label'] == '亲子' and parent['sanyuan_jiugong'] is None
    assert all(c['id'] == 'G5-FR-S06-C01' for c in parent['classical_clauses']['matched'])
    partner = pf.pair_facts(a, b, 'partnership')
    assert partner['classical_clauses']['matched'] == [] and '合作' in partner['say'][-1]
    assert pf.pair_facts(a, b)['relation']['type'] == 'marriage'
    import pytest
    with pytest.raises(ValueError):
        pf.pair_facts(a, b, 'enemies')


def test_router_asks_the_relation_first_and_collects_in_rounds():
    import sys
    sys.path.insert(0, str(SCRIPTS))
    from question_router import route
    assert route('我和男朋友合不合')['relation'] == 'marriage'
    assert route('我和孩子的八字合不合')['relation'] == 'parent_child'
    assert route('想和他合伙做生意，看看合盘')['relation'] == 'partnership'
    unknown = route('我们俩八字合不合')
    assert unknown['relation'] is None and unknown['intake_rounds'][0]['round'] == 0
    assert [r['round'] for r in route('我和女朋友合婚')['intake_rounds']] == [1, 2]
