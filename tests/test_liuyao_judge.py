"""L1: liuyao rules judged from chart fields, narrow branches only, manual conditions kept."""
import json
from pathlib import Path

from conftest import SCRIPTS, run_cli
from liuyao_judge import CHART, LINE, judge

WX = {'子': '水', '亥': '水', '寅': '木', '卯': '木', '巳': '火', '午': '火', '申': '金', '酉': '金',
      '丑': '土', '辰': '土', '未': '土', '戌': '土'}


def chart(branches, changed=None, active=(), month='戌', day='酉', states=None, markers=None, qin='妻财', hint='妻财'):
    def line(i, b, st='旺', mk=()):
        return {'position': i + 1, 'branch': b, 'wuxing': WX[b], 'liu_qin': qin, 'state': st, 'markers': list(mk),
                'is_shi': i == 1}
    states = states or ['旺'] * 6
    markers = markers or [[] for _ in range(6)]
    main = {'hex_number': 37, 'shi_position': 2, 'lines': [line(i, b, states[i], markers[i]) for i, b in enumerate(branches)]}
    out = {'main_chart': main, 'active_lines': list(active), 'cast_time': {'month_branch': month, 'day_branch': day},
           'yongshen_hint': hint, 'fu_shen': []}
    if changed:
        out['changed_chart'] = {'hex_number': 25, 'lines': [line(i, b, mk=('旬空',) if b == '亥' else ())
                                                            for i, b in enumerate(changed)]}
    return out


def states(out, rule_id, position=1):
    row = next((r for r in judge(out, [position])['hits'] if r['id'] == rule_id), None)
    return [x['state'] for x in row['results']] if row else []


def test_every_computable_rule_has_a_check():
    rules = json.loads((Path(SCRIPTS).parent / 'assets' / 'liuyao_rules.json').read_text(encoding='utf-8'))['rules']
    computable = {r['id'] for r in rules if any(c['computable'] for c in r['required_conditions'])}
    assert computable <= set(LINE) | set(CHART)


def test_advance_retreat_and_return_effects_follow_the_book_pairs():
    base = ['寅', '丑', '亥', '未', '巳', '卯']
    adv = chart(base, changed=['卯'] + base[1:], active=[1])
    assert states(adv, 'liuyao-advance-branches') == ['met_pending_manual']
    ret = chart(['卯'] + base[1:], changed=['寅'] + base[1:], active=[1])
    assert states(ret, 'liuyao-retreat-branches') == ['met_pending_manual']
    back = chart(base, changed=['亥'] + base[1:], active=[1])          # 寅木化亥水: 回头生
    assert states(back, 'liuyao-return-generation') == ['met_pending_manual']
    assert states(back, 'liuyao-change-empty') == ['met_pending_manual']
    tomb = chart(base, changed=['未'] + base[1:], active=[1])          # 木化未: 化墓 (只认木分支)
    assert states(tomb, 'liuyao-change-tomb') == ['met_pending_manual']
    fire_tomb = chart(['巳'] + base[1:], changed=['戌'] + base[1:], active=[1])
    assert states(fire_tomb, 'liuyao-change-tomb') == []                # 火化戌不自动判


def test_static_line_rules_and_whole_hexagram_shapes():
    weak = chart(['卯', '丑', '亥', '未', '巳', '卯'], states=['休'] + ['旺'] * 5, day='酉')
    assert states(weak, 'liuyao-day-break-weak-static') == ['met_pending_manual']
    strong = chart(['卯', '丑', '亥', '未', '巳', '卯'], day='酉')
    assert states(strong, 'liuyao-hidden-motion-strong-static') == ['met_pending_manual']
    clash = chart(['子', '寅', '辰', '午', '申', '戌'])                # 初四、二五、三上皆冲
    assert any(r['id'] == 'liuyao-six-clash' for r in judge(clash, [1])['hits'])


def test_rules_for_other_relatives_are_not_applicable():
    out = judge(chart(['寅', '丑', '亥', '未', '巳', '卯'], hint='父母'), [1])
    assert not any(r['id'] == 'liuyao-use-wealth' for r in out['hits'])


def test_cli_reports_rule_checks_and_no_target_case():
    out = run_cli('liuyao_cast.py', 'coins', '--lines', '7,8,9,6,7,7', '--date', '2026-10-26', '--time', '10:00',
                  '--target-timezone', 'Asia/Shanghai', '--current-timezone', 'Asia/Shanghai', '--question', '求财')
    checks = out['rule_checks']
    assert checks['targets'] == [2, 4] and checks['checked'] == 47
    assert any(r['id'] == 'liuyao-return-generation' for r in checks['hits'])
    none = run_cli('liuyao_cast.py', 'coins', '--lines', '7,8,9,6,7,7', '--date', '2026-10-26', '--time', '10:00',
                   '--target-timezone', 'Asia/Shanghai', '--current-timezone', 'Asia/Shanghai', '--question', '面试')
    assert none['rule_checks']['no_target'] is True
    given = run_cli('liuyao_cast.py', 'coins', '--lines', '7,8,9,6,7,7', '--date', '2026-10-26', '--time', '10:00',
                    '--target-timezone', 'Asia/Shanghai', '--current-timezone', 'Asia/Shanghai', '--question', '面试',
                    '--target-position', '5')
    assert given['rule_checks']['targets'] == [5] and given['rule_checks']['target_basis'] == 'given'
