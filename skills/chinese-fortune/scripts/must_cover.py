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


def hour_items(boundary: dict | None, item_id: str = 'hour:boundary', who: str = '') -> list[dict]:
    """A birth time near a 时辰 edge, or whose clock reading gives another 时辰 (R3 N19)."""
    if not boundary:
        return []
    other = boundary['other_branch']
    return [item(item_id, f"{who}{boundary['say']}", [f'{other}时'], ['分钟', '钟表', '真太阳时'])]


def liuyao_conflict_items(hits: list[dict]) -> list[dict]:
    """A rule met on a target line whose own table lists a book passage saying otherwise (R3 T31)."""
    out = []
    for hit in hits:
        conflicts = hit.get('conflicts') or []
        for row in hit.get('results', []):
            if not conflicts or row.get('position') is None or not str(row.get('state', '')).startswith('met'):
                continue
            ids = [c['passage_id'] for c in conflicts]
            short = [pid.split(':', 1)[1] for pid in ids]
            out.append(item(f"liuyao:{hit['id']}:{row['position']}",
                            f"第{row['position']}爻{hit['name']}：{hit.get('allowed_interpretation') or ''}"
                            f"书内另有说法（{'、'.join(ids)}），两边都要写出处",
                            ids + short))
    return out


SETUP_WORDS = ('装卦', '排卦', '逐爻', '六神', '纳甲', '纳支')


def liuyao_line_items(question: str, lines: list[dict]) -> list[dict]:
    """Asked to set the hexagram out: every line with its 纳支, 六神 and 六亲 (R3 T08)."""
    if not any(word in question for word in SETUP_WORDS):
        return []
    return [item(f"liuyao:line{ln['position']}",
                 f"第{ln['position']}爻写出纳支{ln['branch']}、六神{ln['liu_shen']}、六亲{ln['liu_qin']}",
                 [ln['liu_shen']], [ln['branch']], [ln['liu_qin']]) for ln in lines]


def annual_scope_items(readings: list[dict]) -> list[dict]:
    """A 流年 relation the tool found only in part, with the books' wording that leaves it open (R3 T21)."""
    return [item(f"annual:{hit['id']}:{reading.get('year')}", hit['scope_note'],
                 ['只有天干', '只合天干', '天干相合', '干合'], ['不合', '没合', '未合', '都合', '没说清'])
            for reading in readings or [] for hit in reading.get('hits') or [] if hit.get('scope_note')]
