"""六爻规则库 (assets/liuyao_rules.json) 中可由盘面字段判定的条件, 逐条自动判.

每条规则的 required_conditions 分可计算 (computable) 与须人工两类。这里只判可计算的,
按原文写明的窄分支 (如化墓只认木化未); 须人工的照列为 manual, 不替原文定。一条规则在
某爻上的状态: not_met 有可计算条件不成立; met_pending_manual 可计算的都成立、还有人工
条件; met 全部可计算且成立。met 只说条件字面齐备, 不等于吉凶已定。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

RULES_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'liuyao_rules.json'
SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}
KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}
CHONG = {'子': '午', '午': '子', '丑': '未', '未': '丑', '寅': '申', '申': '寅',
         '卯': '酉', '酉': '卯', '辰': '戌', '戌': '辰', '巳': '亥', '亥': '巳'}
HE = {'子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯',
      '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午'}
BRANCH_WUXING = {'子': '水', '亥': '水', '寅': '木', '卯': '木', '巳': '火', '午': '火',
                 '申': '金', '酉': '金', '丑': '土', '辰': '土', '未': '土', '戌': '土'}
# zengshan:c032:p0137 / p0139 的七组支对, 照原文。
ADVANCE = {('亥', '子'), ('寅', '卯'), ('巳', '午'), ('申', '酉'), ('丑', '辰'), ('辰', '未'), ('未', '戌')}
RETREAT = {(b, a) for a, b in ADVANCE}
STRONG, WEAK = ('旺', '相'), ('休', '囚', '死')
RELATIVE_RULES = {'liuyao-use-parent': '父母', 'liuyao-use-official': '官鬼', 'liuyao-use-sibling': '兄弟',
                  'liuyao-use-wealth': '妻财', 'liuyao-use-child': '子孙'}


class Ctx:
    def __init__(self, out: dict):
        self.main, self.changed = out['main_chart'], out.get('changed_chart')
        self.active = list(out.get('active_lines') or [])
        self.month, self.day = out['cast_time']['month_branch'], out['cast_time']['day_branch']
        self.fu_shen = out.get('fu_shen') or []

    def line(self, p: int) -> dict:
        return self.main['lines'][p - 1]

    def change(self, p: int) -> dict | None:
        return self.changed['lines'][p - 1] if self.changed and p in self.active else None

    def pairs(self, chart: dict, table: dict) -> bool:
        b = [ln['branch'] for ln in chart['lines']]
        return all(table[b[i]] == b[i + 3] for i in range(3))


LineCheck = Callable[[Ctx, int], bool]


def _moving(c: Ctx, p: int) -> bool:
    return p in c.active


def _changed_wx(c: Ctx, p: int) -> str | None:
    ch = c.change(p)
    return ch['wuxing'] if ch else None


LINE: dict[str, LineCheck] = {
    'liuyao-change-local-effect': _moving,
    'liuyao-advance-branches': lambda c, p: bool(c.change(p)) and (c.line(p)['branch'], c.change(p)['branch']) in ADVANCE,
    'liuyao-retreat-branches': lambda c, p: bool(c.change(p)) and (c.line(p)['branch'], c.change(p)['branch']) in RETREAT,
    'liuyao-return-generation': lambda c, p: bool(c.change(p)) and SHENG[_changed_wx(c, p)] == c.line(p)['wuxing'],
    'liuyao-return-restraint': lambda c, p: bool(c.change(p)) and KE[_changed_wx(c, p)] == c.line(p)['wuxing'],
    'liuyao-change-empty': lambda c, p: bool(c.change(p)) and '旬空' in c.change(p)['markers'],
    'liuyao-change-broken': lambda c, p: bool(c.change(p)) and CHONG[c.change(p)['branch']] == c.month,
    'liuyao-change-tomb': lambda c, p: bool(c.change(p)) and c.line(p)['wuxing'] == '木' and c.change(p)['branch'] == '未',
    'liuyao-change-absolute': lambda c, p: bool(c.change(p)) and c.line(p)['wuxing'] == '木' and c.change(p)['branch'] == '申',
    'liuyao-true-empty-seasonal': lambda c, p: c.month in '寅卯' and c.line(p)['wuxing'] == '土' and '旬空' in c.line(p)['markers'],
    'liuyao-moving-empty-not-final': lambda c, p: _moving(c, p) and '旬空' in c.line(p)['markers'],
    'liuyao-empty-exit': lambda c, p: c.line(p)['branch'] == c.month and '旬空' in c.line(p)['markers'],
    'liuyao-empty-clash-filled': lambda c, p: '旬空' in c.line(p)['markers'] and CHONG[c.line(p)['branch']] == c.day,
    'liuyao-month-break': lambda c, p: CHONG[c.line(p)['branch']] == c.month,
    'liuyao-hidden-motion-strong-static': lambda c, p: not _moving(c, p) and c.line(p)['state'] in STRONG
    and CHONG[c.line(p)['branch']] == c.day,
    'liuyao-seasonal-strength': lambda c, p: c.month in '申酉' and c.line(p)['wuxing'] == '金',
    'liuyao-month-support': lambda c, p: SHENG[BRANCH_WUXING[c.month]] == c.line(p)['wuxing'],
    'liuyao-month-restraint': lambda c, p: KE[BRANCH_WUXING[c.month]] == c.line(p)['wuxing'],
    'liuyao-day-support': lambda c, p: SHENG[BRANCH_WUXING[c.day]] == c.line(p)['wuxing'],
    'liuyao-day-restraint': lambda c, p: KE[BRANCH_WUXING[c.day]] == c.line(p)['wuxing'],
    'liuyao-strength-beyond-season': lambda c, p: c.line(p)['branch'] == c.day,
    'liuyao-day-break-weak-static': lambda c, p: not _moving(c, p) and c.line(p)['state'] in WEAK
    and CHONG[c.line(p)['branch']] == c.day,
    'liuyao-timing-static': lambda c, p: not _moving(c, p) and c.line(p)['branch'] == '子',
    'liuyao-timing-moving': lambda c, p: _moving(c, p) and c.line(p)['branch'] == '子',
    'liuyao-timing-tomb-release': lambda c, p: c.line(p)['branch'] == '午' and c.day == '戌',
    'liuyao-timing-month-break': lambda c, p: c.month == '子' and c.line(p)['branch'] == '午'
    and '月破' in c.line(p)['markers'],
    'liuyao-quiet-strength-effect': lambda c, p: not c.active and c.line(p)['state'] in WEAK and any(
        o['state'] in STRONG and KE[o['wuxing']] == c.line(p)['wuxing'] for o in c.main['lines'] if o['position'] != p),
}

def _has_relative(relative: str) -> Callable[[Ctx], bool]:
    return lambda c: any(ln['liu_qin'] == relative for ln in c.main['lines'])


CHART: dict[str, Callable[[Ctx], bool]] = {
    **{rid: _has_relative(rel) for rid, rel in RELATIVE_RULES.items()},
    'liuyao-use-self-shi': lambda c: any(ln['is_shi'] and ln['position'] == c.main['shi_position'] for ln in c.main['lines']),
    'liuyao-six-clash': lambda c: c.pairs(c.main, CHONG),
    'liuyao-six-harmony': lambda c: c.pairs(c.main, HE),
    'liuyao-clash-to-harmony': lambda c: bool(c.active) and c.pairs(c.main, CHONG) and bool(c.changed)
    and c.pairs(c.changed, HE),
    'liuyao-harmony-to-clash': lambda c: bool(c.changed) and c.pairs(c.main, HE) and c.pairs(c.changed, CHONG),
    'liuyao-fanyin-explicit-pattern': lambda c: c.main['hex_number'] == 1 and bool(c.changed)
    and c.changed['hex_number'] == 2 and len(c.active) == 6,
    'liuyao-fuyin-explicit-pattern': lambda c: c.main['hex_number'] == 44 and bool(c.changed)
    and c.changed['hex_number'] == 32 and {5, 6} <= set(c.active),
    'liuyao-single-active': lambda c: len(c.active) == 1,
    'liuyao-single-static': lambda c: len(c.active) == 5,
    'liuyao-crowded-motion': lambda c: len(c.active) == 6,
    'liuyao-hidden-from-palace': lambda c: bool(c.fu_shen),
    'liuyao-hidden-flying-generation': lambda c: any(f['relation'] == '飞神生伏神' for r in c.fu_shen for f in r['fu_shen']),
    'liuyao-hidden-empty-flying-release': lambda c: any('旬空' in f['fei_shen']['markers'] for r in c.fu_shen
                                                        for f in r['fu_shen']),
    'liuyao-hidden-strong-flying-restraint': lambda c: any(
        f['relation'] == '飞神克伏神' and c.line(f['position'])['state'] in STRONG for r in c.fu_shen for f in r['fu_shen']),
}


def targets(out: dict, positions: list[int] | None) -> list[int]:
    if positions:
        return [p for p in positions if 1 <= p <= 6]
    hint = out.get('yongshen_hint') or ''
    return [ln['position'] for ln in out['main_chart']['lines'] if ln['liu_qin'] and ln['liu_qin'] in hint]


def _applies(rule_id: str, hint: str) -> bool:
    """取用类条款只对本题的用神类别有意义; 世爻条款只在提示取世时。"""
    if rule_id in RELATIVE_RULES:
        return RELATIVE_RULES[rule_id] in hint
    if rule_id == 'liuyao-use-self-shi':
        return '世' in hint
    return True


def judge(out: dict, positions: list[int] | None = None) -> dict:
    rules = json.loads(RULES_PATH.read_text(encoding='utf-8'))['rules']
    ctx, lines = Ctx(out), targets(out, positions)
    hint = out.get('yongshen_hint') or ''
    rows = []
    for rule in rules:
        manual = [c['label'] for c in rule['required_conditions'] if not c['computable']]
        if not _applies(rule['id'], hint):
            results = [{'position': None, 'state': 'not_applicable'}]
        elif rule['id'] in CHART:
            ok = CHART[rule['id']](ctx)
            results = [{'position': None, 'state': ('met_pending_manual' if manual else 'met') if ok else 'not_met'}]
        elif rule['id'] in LINE and not lines:
            results = [{'position': None, 'state': 'no_target'}]
        elif rule['id'] in LINE:
            results = [{'position': p, 'state': ('met_pending_manual' if manual else 'met') if LINE[rule['id']](ctx, p)
                        else 'not_met'} for p in lines]
        else:
            results = [{'position': None, 'state': 'manual_only'}]
        rows.append({'id': rule['id'], 'name': rule['name'], 'scope': rule['scope'], 'passage_id': rule['passage_id'],
                     'results': results, 'manual': manual})
    hits = [r for r in rows if any(x['state'].startswith('met') for x in r['results'])]
    return {'targets': lines, 'target_basis': 'given' if positions else 'yongshen_relative',
            'checked': len(rows), 'hits': hits,
            'not_met': [r['id'] for r in rows if all(x['state'] == 'not_met' for x in r['results'])],
            'manual_only': [r['id'] for r in rows if r['results'][0]['state'] == 'manual_only'],
            'no_target': not lines,
            'meaning': 'met 只说原文字面条件在盘上齐备；manual 列的条件（问题对象、喜忌、救助等）仍须人工核，未核前不下吉凶。'}
