"""L2: main judgment first, supporting evidence second, broad questions narrowed."""
from conftest import run_cli
from liuyao_plan import relative_wuxing, scope

CAST = ['coins', '--lines', '7,8,9,6,7,7', '--date', '2026-10-26', '--time', '10:00',
        '--target-timezone', 'Asia/Shanghai', '--current-timezone', 'Asia/Shanghai']


def test_relatives_follow_the_palace_element():
    assert relative_wuxing('木') == {'兄弟': '木', '子孙': '火', '妻财': '土', '官鬼': '金', '父母': '水'}


def test_plan_names_use_yuan_ji_chou_and_shi_ying():
    plan = run_cli('liuyao_cast.py', *CAST, '--question', '求财')['reading_plan']
    assert plan['relative'] == '妻财' and plan['primary']['wuxing'] == '土'
    assert (plan['secondary']['yuan_shen']['relative'], plan['secondary']['ji_shen']['relative'],
            plan['secondary']['chou_shen']['relative']) == ('子孙', '兄弟', '父母')
    assert [f['position'] for f in plan['primary']['lines']] == [2, 4]
    assert plan['secondary']['shi_ying'] == {'shi': 2, 'ying': 5, 'shi_is_use': True, 'shi_to_use': '同类'}
    assert plan['say'][0].startswith('主判：用神妻财') and 'zengshan:c032:p0735' in plan['say'][-1]


def test_broad_questions_are_narrowed_first():
    assert scope('今年运势如何') == 'broad' and scope('下周面试能过吗') == 'specific'
    plan = run_cli('liuyao_cast.py', *CAST, '--question', '今年运势如何')['reading_plan']
    assert plan['question_scope'] == 'broad' and plan['say'][0].startswith('问题较宽')
