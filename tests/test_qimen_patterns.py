"""《遁甲演义》转盘与卷二格局：逐条用原书「假如」例对照。"""
import re

import pytest
from classical_search import get_passage
from conftest import run_cli
from qimen_cast import earth_plate
from qimen_patterns import NOT_COMPUTED, SPECS, detect
from qimen_select import SLOT_VETO, judge
from qimen_zhuanpan import plate


def chart(dun, ju, hour):
    return plate(earth_plate(dun, ju), dun, hour)


def hits(dun, ju, hour, **gz):
    return detect(chart(dun, ju, hour), {'hour': hour, **gz})


def test_every_quote_is_verbatim_in_its_passage():
    squash = re.compile(r'\s+')
    for name, _, pid, quote, _, _ in SPECS:
        assert squash.sub('', quote) in squash.sub('', get_passage(pid)['text']), name
    for row in hits('阳遁', 1, '庚午', day='甲子'):
        assert squash.sub('', row['quote']) in squash.sub('', get_passage(row['passage_id'])['text']), row['name']
    for row in NOT_COMPUTED:
        assert get_passage(row['passage_id'])['text'] and row['reason']


# (遁, 局, 日, 时, 格局, 宫)，均出自 dunjia:c002 各条「假如」例。
BOOK_EXAMPLES = [
    ('阳遁', 4, '乙酉', '乙酉', '天遁', 1),         # p0003 阳四局乙庚日乙酉时
    ('阴遁', 6, '戊午', '庚申', '天遁', 9),         # p0003 阴六局戊癸日庚申时
    ('阳遁', 1, '丙子', '辛卯', '地遁', 2),         # p0004 阳一局丙辛日辛卯时
    ('阴遁', 9, '甲子', '丙寅', '地遁', 8),         # p0004 阴九局甲己日丙寅时
    ('阳遁', 7, '乙丑', '丙子', '人遁', 6),         # p0005 阳七局乙庚日丙子时
    ('阳遁', 9, '甲子', '辛未', '飞鸟跌穴', 9),     # p0006
    ('阳遁', 3, '甲子', '丁卯', '飞鸟跌穴', 3),     # p0006
    ('阳遁', 1, '甲子', '丙寅', '青龙返首', 8),     # p0007
    ('阳遁', 1, '甲子', '庚午', '玉女守门', 7),     # p0008
    ('阳遁', 9, '甲子', '庚午', '三奇得使', 3),     # p0009 乙奇得使
    ('阴遁', 3, '丙子', '壬辰', '三奇得使', 9),     # p0009 乙奇得使
    ('阳遁', 9, '乙丑', '戊寅', '三奇得使', 4),     # p0009 丁奇得使
    ('阴遁', 2, '丙子', '己亥', '青龙逃走', 8),     # p0025
    ('阴遁', 2, '甲子', '壬申', '白虎猖狂', 3),     # p0026
    ('阴遁', 3, '甲子', '壬申', '朱雀投江', 7),     # p0027
    ('阳遁', 4, '丙子', '戊子', '螣蛇夭矫', 1),     # p0028
    ('阴遁', 4, '甲子', '丙寅', '大格', 8),         # p0029
    ('阳遁', 3, '甲子', '丙寅', '刑格', 4),         # p0031 庚在中五寄坤
    ('阴遁', 5, '己巳', '丙寅', '伏干格', 4),       # p0030 日干格：庚加日干己
    ('阳遁', 2, '丙子', '己丑', '时格', 3),         # p0030
    ('阳遁', 5, '丙子', '戊戌', '荧入太白', 7),     # p0033
    ('阴遁', 6, '甲子', '丙寅', '荧入太白', 4),     # p0033
    ('阳遁', 4, '甲子', '壬申', '太白入荧', 2),     # p0034
    ('阴遁', 3, '乙丑', '戊寅', '太白入荧', 2),     # p0034 地盘丙在中五寄坤
    ('阳遁', 5, '甲子', '庚午', '飞干格', 7),       # p0036
    ('阳遁', 2, '甲子', '壬申', '天乙伏宫格', 2),   # p0037
    ('阳遁', 9, '甲子', '庚午', '天乙飞宫格', 2),   # p0038
    ('阴遁', 4, '丙子', '庚寅', '三奇入墓', 6),     # p0042
    ('阳遁', 1, '甲子', '庚午', '六仪击刑', 3),     # p0043
    ('阳遁', 1, '甲子', '甲子', '伏吟', None),      # p0044
    ('阳遁', 1, '甲子', '乙丑', '反吟', None),      # p0045
]


@pytest.mark.parametrize('dun,ju,day,hour,name,palace', BOOK_EXAMPLES,
                         ids=[f'{e[4]}-{e[0]}{e[1]}{e[3]}' for e in BOOK_EXAMPLES])
def test_book_example_reproduces(dun, ju, day, hour, name, palace):
    got = hits(dun, ju, hour, day=day)
    assert any(h['name'] == name and h['palace'] == palace for h in got), [(h['name'], h['palace']) for h in got]


def test_year_and_month_new_moon_stems():
    # p0030 岁格：辛丑年阳五局癸酉时，天柱六庚临八宫地盘辛。
    got = hits('阳遁', 5, '癸酉', year='辛丑')
    assert [h['palace'] for h in got if h['name'] == '岁格'] == [8]
    # p0030 月格：阳八局丁卯时，月朔干己，六庚临九宫地盘己。
    got = hits('阳遁', 8, '丁卯', month_shuo='己巳')
    assert [h['palace'] for h in got if h['name'] == '月格'] == [9]
    assert not [h for h in hits('阳遁', 8, '丁卯') if h['name'] == '月格']


def test_plate_matches_the_book_wording():
    pl = chart('阳遁', 7, '丙子')  # p0005：天任直符加五（寄坤），生门直使加一，太阴在直符前二六宫。
    assert pl['zhi_fu'] == {'origin_palace': 8, 'palace': 2, 'stem': '己', 'star': '天任'}
    assert (pl['zhi_shi']['door'], pl['zhi_shi']['palace']) == ('生门', 1)
    assert (pl['gods'][6], pl['doors'][6]) == ('太阴', '休门')
    yang = chart('阳遁', 1, '丙寅')  # p0005：直符临八，后一九天一，后二九地六，前二太阴四，前三六合九。
    assert {p: yang['gods'][p] for p in (8, 1, 6, 4, 9)} == {8: '值符', 1: '九天', 6: '九地', 4: '太阴', 9: '六合'}
    yin = chart('阴遁', 9, '丙寅')  # p0005：直符临二，前一九天七，前二九地六，后二太阴四，后三六合三。
    assert {p: yin['gods'][p] for p in (2, 7, 6, 4, 3)} == {2: '值符', 7: '九天', 6: '九地', 4: '太阴', 3: '六合'}
    pl = chart('阴遁', 9, '丙寅')  # p0004：以景加七，开门合六己临八宫。
    assert (pl['doors'][7], pl['doors'][8], pl['earth'][8]) == ('景门', '开门', ['己'])
    pl = chart('阳遁', 5, '癸酉')  # c001:p0007：旬首在五，天禽为直符、死门为直使，随坤二同转。
    assert (pl['zhi_fu']['star'], pl['zhi_shi']['door']) == ('天禽', '死门')
    assert '天禽' in pl['stars'][pl['zhi_fu']['palace']]


def test_two_book_examples_disagree_with_their_own_rule_and_are_not_fixtures():
    # p0035 甲申日壬申时称「天柱为六庚下临九宫」；按本书其余各例的转法，九宫是天禽、地盘坤二之干。
    assert not [h for h in hits('阳遁', 5, '壬申', day='甲申') if h['name'] == '伏干格']
    # p0009 阴三局壬辰时称「乙奇在杜门」；按值使数到坤二的转法，九宫是开门。格局本身（乙加辛）照样成立。
    assert chart('阴遁', 3, '壬辰')['doors'][9] == '开门'


def test_door_compulsion_follows_the_listed_examples():
    pl = chart('阳遁', 1, '甲子')  # 伏吟，八门在本宫，均不受迫
    assert not [h for h in detect(pl, {'hour': '甲子'}) if h['category'] == '门迫']
    forced = [h for h in hits('阳遁', 4, '乙酉', day='乙酉') if h['category'] == '门迫']
    assert all(('吉门被迫' in h['evidence']) == (h['evidence'][:2] in ('开门', '休门', '生门', '景门')) for h in forced)


def test_flawed_use_is_marked_unless_the_zhi_fu_shares_the_palace():
    got = [h for h in hits('阴遁', 3, '壬辰', day='丙子') if h['name'] == '三奇得使']
    assert got and all('㣲疵' in h['note'] for h in got)
    clean = [h for h in hits('阳遁', 9, '戊寅', day='乙丑') if h['name'] == '三奇得使']  # 丁加壬，不重凶格
    assert clean and all('note' not in h for h in clean)


def test_cast_cli_full_plate_and_old_plate_no_longer_judges_patterns():
    args = ('--date', '2026-06-18', '--time', '08:00', '--target-timezone', 'Asia/Shanghai')
    got = run_cli('qimen_cast.py', *args, '--plate-method', 'dunjia-zhuanpan')
    assert got['completion_status'] == 'complete'
    assert (got['zhi_fu_star'], got['zhi_fu_palace'], got['zhi_shi_men']) == ('天禽', 7, '死门')
    assert all(p['star'] for p in got['palaces'] if p['index'] != 5)
    assert got['patterns'] and all(h['passage_id'].startswith('dunjia:c002:') for h in got['patterns'])
    assert got['patterns_not_computed'] == NOT_COMPUTED
    old = run_cli('qimen_cast.py', *args, '--plate-method', 'rotating-compat')
    assert old['patterns'] == [] and '不判格局' in old['method_profile']['scope']


def test_selection_never_keeps_a_vetoed_hour():
    got = run_cli('qimen_select.py', '--from', '2026-11-02', '--days', '3', '--target-timezone', 'Asia/Shanghai')
    assert got['candidates'] and sum(got['excluded'].values()) + len(got['candidates']) == 36
    keys = [(c['date'], c['sampled_at']) for c in got['candidates']]
    assert keys == sorted(keys)
    assert '不分高下' in got['say']
    slot = {'date': '2026-11-02', 'window': 'x', 'sampled_at': '00:00', 'ganzhi': {'day': '甲子', 'hour': '庚午'},
            'ju': 'x', 'patterns': hits('阳遁', 1, '庚午', day='甲子')}
    assert judge(slot) in SLOT_VETO  # 庚午时：五不遇时、六仪击刑都在，玉女守门不能救


@pytest.mark.parametrize('argv', [
    ['--from', '2026-02-30', '--target-timezone', 'Asia/Shanghai'],
    ['--from', '2026-11-02', '--days', '40', '--target-timezone', 'Asia/Shanghai'],
    ['--from', '2026-11-02', '--target-timezone', 'Mars/Base'],
])
def test_selection_refuses_bad_input(argv):
    got = run_cli("qimen_select.py", *argv, expect_rc=1)
    assert got['ok'] is False


def test_router_sends_qimen_hour_picking_to_the_selector():
    from question_router import route
    picked = route('用奇门帮我择时，下周哪个时辰去签约好')
    assert picked['flow'] == 'method' and 'qimen_select.py' in picked['command']
    assert 'qimen_cast.py' in route('奇门遁甲看租房合同签不签')['command']
