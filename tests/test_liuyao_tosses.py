"""A user's own six coin tosses are charted as given, never re-randomised."""
from conftest import run_cli

WHEN = ['--date', '2026-10-26', '--time', '10:00']


def test_reported_tosses_produce_their_own_hexagrams():
    data = run_cli('liuyao_cast.py', 'coins', '--lines', '7,8,9,6,7,7', *WHEN, '--question', '面试')
    assert data['raw_lines'] == [7, 8, 9, 6, 7, 7]
    assert data['main_chart']['hex_name'] == '风火家人'
    assert data['changed_chart']['hex_name'] == '天雷无妄'
    assert data['active_lines'] == [3, 4]
    assert data['entropy']['source'] == 'user_tosses' and data['entropy']['reproducible']
    again = run_cli('liuyao_cast.py', 'coins', '--lines', '7，8，9，6，7，7', *WHEN, '--question', '面试')
    assert again['main_chart'] == data['main_chart']


def test_bad_or_conflicting_tosses_are_refused():
    for bad in ('7,8,9', '7,8,9,6,7,5', 'a,b,c,d,e,f'):
        data = run_cli('liuyao_cast.py', 'coins', '--lines', bad, *WHEN, expect_rc=1)
        assert data['ok'] is False and '6/7/8/9' in data['message']
    data = run_cli('liuyao_cast.py', 'coins', '--lines', '7,7,7,7,7,7', '--seed', '3', *WHEN, expect_rc=1)
    assert '--seed' in data['message']


def test_every_cast_indexes_the_reference_rules_and_rules_resolve():
    data = run_cli('liuyao_cast.py', 'coins', '--lines', '7,8,9,6,7,7', *WHEN)
    ids = [rule_id for topic in data['rule_index']['topics'].values() for rule_id, _ in topic['rules']]
    assert len(ids) == 47 and 'liuyao-return-restraint' in ids
    rule = run_cli('liuyao_cast.py', 'rules', '--id', 'liuyao-return-restraint')['rules'][0]
    assert rule['passage_id'].startswith('zengshan:') and rule['application_status'] == 'reference_only'
    assert len(run_cli('liuyao_cast.py', 'rules', '--scope', 'timing')['rules']) == 5
    name = data['rule_index']['topics']['strength']['name']
    assert run_cli('liuyao_cast.py', 'rules', '--scope', name)['rules']  # the shown Chinese name works too


def test_every_liuyao_rule_quotes_its_hashed_passage():
    import hashlib
    import json
    from pathlib import Path

    from classical_search import get_passage, normalized
    root = Path(__file__).resolve().parents[1]
    rules = json.loads((root / 'skills/chinese-fortune/assets' / 'liuyao_rules.json').read_text(encoding='utf-8'))['rules']
    strip = str.maketrans('', '', '，。、；：「」')
    for rule in rules:
        text = get_passage(rule['passage_id'])['text']
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == rule['sha256'], rule['id']
        assert normalized(rule['quote'].translate(strip)) in normalized(text.translate(strip)), rule['id']
        assert rule['forbidden_inferences'] and rule['required_conditions']
