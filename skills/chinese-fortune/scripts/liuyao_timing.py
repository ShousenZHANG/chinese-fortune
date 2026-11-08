"""六爻应期候选：《增删卜易》各门类应期总注章（zengshan:c030:p0001）各条，按「餘仿此」推到每个地支。

每条只在条件看得出时给：主事爻静或动、变出何支、月破、旬空、入墓、逢合。给的是候选地支（年、月、日、时
按事远近取，原文「遠事定之以年月，近事應之於日時」），不排先后、不合成一个日期。要先判旺衰的两条
（太旺逢墓逢冲、衰绝遇生遇旺）和看大象、元神的几条，工具不判，列在 not_computed。

墓：木墓未（zengshan:c028:p0005）、金墓丑（c028:p0006）、火墓戌（c030:p0001）、水墓辰（c032:p0323）；
土与水同绝于巳（c028:p0006），墓也按辰，这一项是推出来的，输出里注明。
"""
from __future__ import annotations

from utils import chong_branch, tg_dz_wuxing

LIUHE = {'子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯',
         '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午'}
TOMB = {'木': '未', '金': '丑', '火': '戌', '水': '辰', '土': '辰'}
# 进神：同五行往前一位（寅→卯、巳→午、申→酉、亥→子、丑→辰、辰→未、未→戌、戌→丑）；反过来是退神。
ADVANCE = {'寅': '卯', '巳': '午', '申': '酉', '亥': '子', '丑': '辰', '辰': '未', '未': '戌', '戌': '丑'}
PASSAGE = 'zengshan:c030:p0001'
QUOTES = {
    'static': '靜而逢值逢沖', 'moving': '動而逢合逢值', 'changed': '其吉凶有戌日應者，有酉日應者',
    'advance': '化進神、逢值逢合', 'retreat': '化退神、忌值忌沖', 'month_break': '月破喜塡',
    'empty': '旬空最愛塡沖', 'tomb': '入三墓俱喜沖開', 'harmony': '遇六合亦宜相擊',
    'horizon': '遠事定之以年月，近事應之於日時',
}
NOT_COMPUTED = ['太旺者逢墓逢沖、衰絕者遇生遇旺：要先判主事爻旺衰，工具不判',
                '大象吉凶而受克、元神來助、世空元動：要先判用神吉凶与元神，工具不判']


def _rule(rule: str, branches: list[str], why: str) -> dict:
    return {'rule': rule, 'branches': list(dict.fromkeys(branches)), 'why': why,
            'passage_id': PASSAGE, 'quote': QUOTES[rule]}


def line_timing(line: dict, changed: dict | None, moving: bool, month_branch: str, day_branch: str) -> list[dict]:
    b = line['branch']
    rules = []
    if moving:
        rules.append(_rule('moving', [LIUHE[b], b], f'{b}爻发动：逢合{LIUHE[b]}、逢值{b}'))
        cb = (changed or {}).get('branch')
        if cb:
            rules.append(_rule('changed', [b, cb], f'{b}变出{cb}：动爻、变爻两支'))
            if ADVANCE.get(b) == cb:
                rules.append(_rule('advance', [b, LIUHE[b]], f'{b}化{cb}为进神：逢值{b}、逢合{LIUHE[b]}'))
            elif ADVANCE.get(cb) == b:
                rules.append(_rule('retreat', [cb, chong_branch(cb)], f'{b}化{cb}为退神：值{cb}、冲{chong_branch(cb)}'))
    else:
        rules.append(_rule('static', [b, chong_branch(b)], f'{b}爻安静：逢值{b}、逢冲{chong_branch(b)}'))
    markers = line.get('markers') or []
    if '月破' in markers or b == chong_branch(month_branch):
        rules.append(_rule('month_break', [LIUHE[b], b], f'{month_branch}月冲{b}为月破：逢合{LIUHE[b]}、填实{b}'))
    if '旬空' in markers:
        rules.append(_rule('empty', [b, chong_branch(b)], f'{b}旬空：填实{b}、冲空{chong_branch(b)}'))
    element = tg_dz_wuxing(b)
    tomb = TOMB.get(element)
    changed_branch = (changed or {}).get('branch') if moving else None
    if tomb and tomb in (day_branch, changed_branch):
        where = '日' if day_branch == tomb else '变爻'
        row = _rule('tomb', [chong_branch(tomb)], f'{element}墓{tomb}，入{where}墓：冲开逢{chong_branch(tomb)}')
        if element == '土':
            row['note'] = '土墓按辰是随水推出的，原文没有直写'
        rules.append(row)
    partner = LIUHE[b]
    if partner in (month_branch, day_branch) or changed_branch == partner:
        rules.append(_rule('harmony', [chong_branch(b), chong_branch(partner)],
                           f'{b}与{partner}合：冲开逢{chong_branch(b)}或{chong_branch(partner)}'))
    return rules


def timing(main_chart: dict, changed_chart: dict | None, active: list[int], targets: list[int],
           month_branch: str, day_branch: str) -> dict:
    rows = []
    changed_lines = (changed_chart or {}).get('lines') or []
    for position in targets:
        line = main_chart['lines'][position - 1]
        changed = changed_lines[position - 1] if changed_lines and position in active else None
        rules = line_timing(line, changed, position in active, month_branch, day_branch)
        rows.append({'position': position, 'branch': line['branch'], 'liu_qin': line.get('liu_qin'),
                     'moving': position in active, 'rules': rules,
                     'candidates': list(dict.fromkeys(b for r in rules for b in r['branches']))})
    return {'targets': rows, 'horizon': {'passage_id': PASSAGE, 'quote': QUOTES['horizon']},
            'not_computed': NOT_COMPUTED,
            'scope': '候选地支并列，不排先后；年、月、日、时按事远近取，工具不替用户定'}


def _hexagram(yang: list[int]) -> dict:
    from yijing_cast import hex_lookup_by_trigrams, lines_to_trigrams
    number, name = hex_lookup_by_trigrams(*lines_to_trigrams([7 if v else 8 for v in yang]))
    return {'number': number, 'name': name}


def cuo_zong(lines: list[int]) -> dict:
    """错卦（六爻阴阳全反）与综卦（六爻上下颠倒）；随包古籍没有错综的原文，只是结构变换。"""
    yang = [1 if v in (7, 9) else 0 for v in lines]
    return {'cuo': _hexagram([1 - v for v in yang]), 'zong': _hexagram(list(reversed(yang))),
            'basis': '结构变换：错卦阴阳全反，综卦上下颠倒；随包古籍没有错综条文，不据此断事'}
