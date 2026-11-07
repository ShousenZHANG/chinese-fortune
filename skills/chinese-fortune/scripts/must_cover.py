"""What an answer must state, named by the tool that computed it (plan A1: R2 N04, N07, N19, S21).

Each item is {'id', 'what', 'groups'}: the answer covers it when one line holds at least one string
from every group. answer_check reports a missed item as an error. Items are facts the tool already
gave; the list says which of them a reply to this question cannot leave out.
"""
from __future__ import annotations

DIGITS = '〇一二三四五六七八九'


def item(item_id: str, what: str, *groups: list[str]) -> dict:
    return {'id': item_id, 'what': what, 'groups': [list(dict.fromkeys(g for g in group if g)) for group in groups]}


def number_forms(n: int) -> list[str]:
    forms = [f'{n} 步', f'{n}步']
    if 0 <= n < 10:
        forms.append(DIGITS[n] + '步')
    elif 10 <= n < 100:
        tens, ones = divmod(n, 10)
        forms.append(('' if tens == 1 else DIGITS[tens]) + '十' + (DIGITS[ones] if ones else '') + '步')
    return forms


# Which 运限 layer a reply discusses is not known to the tool, so this item names a check instead of
# listing twenty stars: answer_check applies it to every layer whose 四化 the answer mentions (N04).
SIHUA = {'id': 'sihua:palaces', 'check': 'sihua_palaces',
         'what': '说到哪一层运限的四化，就在同一行写出各星落在哪一宫（照 transformation_palaces）'}


def sanyuan_items(match: dict) -> list[dict]:
    """The 三元九宫 count a reader can redo (N19): start palace, direction, steps, for both people."""
    out = []
    for who, key in (('男', 'male'), ('女', 'female')):
        p = match[key]
        start = p['start_palace']
        out.append(item(f'sanyuan:{key}', f"{who}从{DIGITS[start]}宫起甲子，{p['direction']}数 {p['steps']} 步",
                        [f'{DIGITS[start]}宫起', f'{start}宫起', f'{DIGITS[start]}宫开始'],
                        [p['direction'] + '数', p['direction'] + '行', p['direction'] + '推'],
                        number_forms(p['steps'])))
    out.append(item('sanyuan:relation', f"合成{match['relation']}", [match['relation']]))
    return out


GEJU_LIMIT = ['候选', '未定', '还没定', '尚未定', '待核', '还要核', '不能定', '不能确定', '没有定', '未成格', '不算定格']


def geju_items() -> list[dict]:
    """A 格局 question answered without saying it is still a candidate (N07)."""
    return [item('geju:limit', '格局只到候选：写明还没定格，以及还要核哪条', GEJU_LIMIT)]
