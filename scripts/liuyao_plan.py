"""六爻解读次序: 先主判 (用神), 再旁证 (元神、忌神、仇神、世应、卦形), 神煞卦辞只作参考.

依据《增删卜易》: 元神生用神、忌神克用神、仇神克元神而生忌神 (zengshan:c009:p0001);
元神能否生用神、忌神能否克用神各列条件 (c010:p0001、p0006、p0007、p0008); 神煞不替代
生克 (「吉凶神煞之多端，何如生克制化之一理」，c032:p0735)。宽泛的问题 (「今年运势如何」)
先锁定一件具体的事; 用户没说时只答当前状态、下一阶段和一个决定条件 (借鉴 liuyao-skills
的分阶段做法)。这里只排列盘面事实与次序, 不下吉凶。
"""
from __future__ import annotations

from liuyao_judge import CHONG, KE, SHENG

LIU_QIN = ('父母', '兄弟', '子孙', '妻财', '官鬼')
BROAD_WORDS = ('运势', '运气', '怎么样', '如何', '前景', '发展', '整体', '这一年', '今年', '下半年', '近况')
EVENT_WORDS = ('面试', '考试', '录取', '求财', '投资', '合同', '官司', '病', '婚', '复合', '升职', '找工作', '房子', '出行',
               '借钱', '失物', '生意', '孩子', '父母')
SOURCES = {'definitions': 'zengshan:c009:p0001', 'yuan_strong': 'zengshan:c010:p0001',
           'yuan_weak': 'zengshan:c010:p0006', 'ji_strong': 'zengshan:c010:p0007', 'ji_weak': 'zengshan:c010:p0008',
           'shensha': 'zengshan:c032:p0735'}


def relative_wuxing(palace_wx: str) -> dict[str, str]:
    """六亲 -> 五行, relative to the palace element."""
    gen_me = next(w for w, t in SHENG.items() if t == palace_wx)
    ke_me = next(w for w, t in KE.items() if t == palace_wx)
    return {'兄弟': palace_wx, '子孙': SHENG[palace_wx], '妻财': KE[palace_wx], '官鬼': ke_me, '父母': gen_me}


def scope(question: str) -> str:
    q = question or ''
    if any(w in q for w in EVENT_WORDS):
        return 'specific'
    return 'broad' if any(w in q for w in BROAD_WORDS) else 'specific'


def _line_facts(out: dict, line: dict) -> dict:
    t = out['cast_time']
    moving = line['position'] in (out.get('active_lines') or [])
    changed = (out.get('changed_chart') or {}).get('lines', [None] * 6)[line['position'] - 1] if moving else None
    facts = {'position': line['position'], 'branch': line['branch'], 'wuxing': line['wuxing'],
             'state': line['state'], 'moving': moving, 'markers': line['markers'],
             'on_month_or_day': line['branch'] in (t['month_branch'], t['day_branch']),
             'clashed_by_day': CHONG.get(line['branch']) == t['day_branch']}
    if changed:
        facts['changes_to'] = changed['branch']
        facts['return_generation'] = SHENG[changed['wuxing']] == line['wuxing']
        facts['return_restraint'] = KE[changed['wuxing']] == line['wuxing']
    return facts


def plan(out: dict) -> dict:
    main = out['main_chart']
    hint = out.get('yongshen_hint') or ''
    relative = next((q for q in LIU_QIN if q in hint), None)
    question_scope = scope(out.get('question') or '')
    if relative is None or not main.get('palace_wuxing'):
        say = ['用神未定：先确认所问之事对应哪一类六亲（问事业取官鬼、财取妻财等），再按主判、旁证次序看。']
        if question_scope == 'broad':
            say.insert(0, '问题较宽：先请用户点名一件具体的事；没点名时只答当前状态、下一阶段和一个决定条件，不铺开做全面预测。')
        return {'question_scope': question_scope, 'relative': None,
                'order': ['用神未定：先确认所问之事对应哪一类六亲，再按主判、旁证次序看'], 'sources': SOURCES, 'say': say}
    wx = relative_wuxing(main['palace_wuxing'])
    use_wx = wx[relative]
    yuan = next(r for r, w in wx.items() if SHENG[w] == use_wx)
    ji = next(r for r, w in wx.items() if KE[w] == use_wx)
    chou = next(r for r, w in wx.items() if KE[w] == wx[yuan])
    lines_of = lambda rel: [_line_facts(out, ln) for ln in main['lines'] if ln['liu_qin'] == rel]  # noqa: E731
    shi = next(ln for ln in main['lines'] if ln['is_shi'])
    ying = next(ln for ln in main['lines'] if ln.get('is_ying'))
    checks = out.get('rule_checks') or {}
    primary = {'relative': relative, 'wuxing': use_wx, 'lines': lines_of(relative),
               'fu_shen': [r for r in out.get('fu_shen') or [] if r['relative'] == relative],
               'rule_hits': [r['id'] for r in checks.get('hits', []) if any(x.get('position') for x in r['results'])]}
    shapes = [r['id'] for r in checks.get('hits', []) if r['scope'] == 'special_hexagram']
    shi_to_use = ('同类' if shi['wuxing'] == use_wx else '世生用' if SHENG[shi['wuxing']] == use_wx
                  else '世克用' if KE[shi['wuxing']] == use_wx else '用生世' if SHENG[use_wx] == shi['wuxing'] else '用克世')
    secondary: dict = {
        'yuan_shen': {'relative': yuan, 'lines': lines_of(yuan), 'source': SOURCES['yuan_strong']},
        'ji_shen': {'relative': ji, 'lines': lines_of(ji), 'source': SOURCES['ji_strong']},
        'chou_shen': {'relative': chou, 'lines': lines_of(chou), 'source': SOURCES['definitions']},
        'shi_ying': {'shi': shi['position'], 'ying': ying['position'], 'shi_is_use': shi['liu_qin'] == relative,
                     'shi_to_use': shi_to_use},
        'shapes': shapes,
    }
    moving = lambda rel: [f['position'] for f in lines_of(rel) if f['moving']]  # noqa: E731
    say = [f"主判：用神{relative}（{use_wx}）" + (
        '在' + '、'.join(f"{f['position']}爻{f['branch']}（{f['state']}{'，动' if f['moving'] else ''}）" for f in primary['lines'])
        if primary['lines'] else '不上卦，看 fu_shen') + '；先看它的旺衰、日月生克与动变。',
           f"旁证：元神{yuan}{'动' + str(moving(yuan)) if moving(yuan) else '静'}、忌神{ji}"
           f"{'动' + str(moving(ji)) if moving(ji) else '静'}、仇神{chou}；世爻{shi['position']}、应爻{ying['position']}"
           f"（{shi_to_use}）。元神、忌神有力无力按 zengshan:c010:p0001、p0006、p0007、p0008 逐条核。",
           '神煞与卦辞只作参考，不替代用神生克（zengshan:c032:p0735）。']
    if question_scope == 'broad':
        say.insert(0, '问题较宽：先请用户点名一件具体的事；没点名时只答当前状态、下一阶段和一个决定条件，不铺开做全面预测。')
    return {'question_scope': question_scope, 'relative': relative, 'primary': primary, 'secondary': secondary,
            'order': ['主判：用神旺衰、日月生克、动变', '旁证：元神忌神仇神动静与有力无力、世应、卦形', '参考：神煞、卦辞'],
            'sources': SOURCES, 'say': say}
