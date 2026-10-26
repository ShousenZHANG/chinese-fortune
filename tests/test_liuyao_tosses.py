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
