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
