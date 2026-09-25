"""What suits the chart: colours, things worn, directions and numbers by the 调候 用神.

Every link but the last is a passage:
1. 日主 and 月令 give the stems 《穷通宝鉴》 names first for this chart
   (tiaohou_provenance: ``source_general_candidates`` and their passages).
2. Each stem has its 五行.
3. 五行 to colour: 《三命通会》卷七 「…其色青…其色赤…其色黄…其色白…其色黑」,
   with the shades 《梅花易数》卷二 files under each 五行.
4. 五行 to things worn: 《梅花易数》卷三 on what each trigram's 五行 is made of;
   to directions and numbers: 《协纪辨方书》卷一 「河圖一六為水居北二七為火居南
   三八為木居東四九為金居西五十為土居中」.
5. What to wear less: the 五行 that overcomes the first-named stem, unless the
   text itself names that 五行 for this chart (子平真詮 「何爲忌？命中所忌，
   我逆而施之者是也」).
No classical sentence says that wearing a colour changes what happens; the
answer says so once, as a limit of this question, not as a disclaimer.
"""
from __future__ import annotations

from collections.abc import Callable

from classical_search import get_passage
from tiaohou_provenance import get_tiaohou_audit
from utils import TIANGAN_WUXING

COLOUR_SOURCE = 'sanming:c007:p0004'
COLOUR_QUOTES = {'木': '其色青', '火': '其色赤', '土': '其色黄', '金': '其色白', '水': '其色黑'}
SHADE_SOURCE = 'meihua:c002:p0118'
SHADE_QUOTE = '青碧綠色屬木，紅紫赤色屬火，白屬金，黑屬水，黃屬土'
# Everyday names for the shades the two passages give.
COLOURS = {'木': ('绿色', '青色'), '火': ('红色', '紫色'), '土': ('黄色', '咖啡色'),
           '金': ('白色', '金银色'), '水': ('黑色', '深蓝色')}
THING_SOURCE = 'meihua:c003:p0069'
# 五行 -> (things worn, the words that say what that 五行 is made of, where).
THINGS = {
    '金': ('金银首饰、金属饰物', '乾金為圓白之物。其色白，其性剛，為寶貨之物', THING_SOURCE),
    '木': ('木质、竹制的饰物', '巽、震為竹木', THING_SOURCE),
    '土': ('玉石、陶瓷一类的饰物', '艮為土中之物，瓦石之類', THING_SOURCE),
    '水': ('黑色的饰物', '坎為黑色', THING_SOURCE),
    '火': ('红色、紫色的饰物', '紅紫赤色屬火', SHADE_SOURCE),
}
AVOID_SOURCE = ('ziping:c025:p0003', '何爲忌？命中所忌，我逆而施之者是也')
HETU_SOURCE = 'xieji:c001:p0017'
HETU_QUOTE = '河圖一六為水居北二七為火居南三八為木居東四九為金居西五十為土居中'
HETU = {'水': ('北方', '1、6'), '火': ('南方', '2、7'), '木': ('东方', '3、8'),
        '金': ('西方', '4、9'), '土': ('中央', '5、10')}
# What a question asks for, by its words. A direction question about furniture
# or a room is 风水, which this answer does not cover (see question_router.py).
ASPECT_WORDS = {
    'colour': ('颜色', '什么色', '幸运色', '开运色', '吉祥色', '穿什么', '衣服', '穿搭', '色系'),
    'things': ('佩戴', '戴什么', '饰品', '首饰', '配饰', '手串', '手链', '项链', '戒指', '吊坠', '挂件',
               '戴金', '戴银', '戴玉', '玉石', '水晶'),
    'direction': ('方位', '哪个方向', '什么方向', '哪边', '往哪', '哪个方位'),
    'number': ('数字', '手机号', '车牌', '门牌', '楼层', '号码'),
    'element': ('五行缺', '缺什么', '缺哪', '五行喜', '喜什么五行', '喜用', '我的用神', '用神是', '补什么',
                '补五行', '旺我的五行'),
}
KE_BY = {'木': '金', '火': '水', '土': '木', '金': '火', '水': '土'}   # what overcomes each
LIMIT = ('古籍讲的是这张八字需要哪种五行，没有一句说穿某种颜色、戴某样东西、用某个数字或往某个方向就能改变遭遇；'
         '按喜用五行换算这些是后来的通行做法，这里按这个做法换算。')


# Review-note clauses about claims this answer does not make (office, wealth,
# advice in general), as opposed to the text's own chart conditions.
POLICY_CLAUSES = ('现实建议', '现实职权', '现实富贵')


def aspects_asked(question: str | None) -> list[str]:
    """Which of colour, things, direction, number and element the question asks."""
    text = question or ''
    return [aspect for aspect, words in ASPECT_WORDS.items() if any(word in text for word in words)]


def asks_colour(question: str | None) -> bool:
    """Whether the question is one this module answers (any aspect)."""
    return bool(aspects_asked(question))


def _excerpt(passage_id: str, stem: str) -> str:
    """The opening clauses of the passage up to the one after ``stem``, verbatim."""
    text = get_passage(passage_id)['text']
    sentence = next((s for s in text.split('。') if stem in s), text.split('。')[0])
    clauses = sentence.strip().split('，')
    at = next(i for i, c in enumerate(clauses) if stem in c) if stem in sentence else 0
    return '，'.join(clauses[:at + 2])


def _conditions(note: str) -> str:
    """The chart conditions of a review note, without its usage policy."""
    kept = []
    for part in note.rstrip('。').split('；'):
        clauses = [c for c in part.split('，') if not any(p in c for p in POLICY_CLAUSES)]
        if clauses:
            kept.append('，'.join(clauses))
    return '；'.join(kept) + '。'


def colour_advice(chart: dict, question: str | None = None) -> dict:
    """What suits this chart for what the question asks, or why it cannot be given."""
    advice = _advice(chart)
    advice['aspects'] = aspects_asked(question) or ['colour']
    return advice


def _advice(chart: dict) -> dict:
    stem = (chart.get('day_master') or {}).get('stem')
    month = ((chart.get('four_pillars') or {}).get('month') or {}).get('branch')
    if not stem or not month:
        return {'status': 'unavailable',
                'reason': '日主或月令还没定下来（出生时间或交节附近），调候用神取不出来'}
    key = f'{stem}|{month}'
    audit = get_tiaohou_audit(key)
    stems = audit['source_general_candidates'] or audit.get('seasonal_context_candidates') or []
    if not stems:
        return {'status': 'unavailable', 'key': key, 'reason': '这一格《穷通宝鉴》没有给出首选用神'}
    needed: list[dict] = []
    for stem_needed in stems:
        wuxing = TIANGAN_WUXING[stem_needed]
        if wuxing not in [n['wuxing'] for n in needed]:
            needed.append({'stem': stem_needed, 'wuxing': wuxing})
    first = needed[0]
    # Quote the passage that names the stem, not merely the cell's first one.
    refs = [r['passage_id'] for r in audit['source_refs']]
    ref = next((r for r in refs if first['stem'] in get_passage(r)['text']), refs[0])
    wear = [{'wuxing': n['wuxing'], 'stem': n['stem'], 'colours': list(COLOURS[n['wuxing']]),
             'things': THINGS[n['wuxing']][0], 'colour_quote': COLOUR_QUOTES[n['wuxing']],
             'thing_quote': THINGS[n['wuxing']][1], 'thing_source': THINGS[n['wuxing']][2]} for n in needed]
    enemy = KE_BY[first['wuxing']]
    avoid = ([] if enemy in [n['wuxing'] for n in needed] else
             [{'wuxing': enemy, 'colours': list(COLOURS[enemy]), 'overcomes': first['stem']}])
    return {
        'status': 'ok', 'key': key, 'cell_status': audit['status'],
        'seasonal_only': audit['status'] == 'seasonal_only',
        'day_master': stem, 'month_branch': month,
        'needed': needed, 'wear': wear, 'avoid': avoid,
        'tiaohou': {'passage_id': ref, 'quote': _excerpt(ref, first['stem']),
                    'conditions': _conditions(audit['review_note']),
                    'other_passages': [r for r in refs if r != ref]},
        'sources': {'colour': COLOUR_SOURCE, 'shade': SHADE_SOURCE, 'things': THING_SOURCE,
                    'avoid': AVOID_SOURCE[0]},
        'limit': LIMIT,
    }


def _ordered(wear: list[dict], name: Callable[[dict], str]) -> str:
    return '，其次'.join(f"{name(w)}（{w['wuxing']}）" for w in wear)


def colour_lead(advice: dict, aspects: list[str] | None = None) -> str:
    """The first sentence: what the question asked, first to last, and what to avoid."""
    if advice['status'] != 'ok':
        return f"这一问现在给不出，因为{advice['reason']}。"
    aspects = aspects or advice.get('aspects') or ['colour']
    wear, avoid = advice['wear'], advice['avoid'][:1]
    parts = []
    if 'element' in aspects:
        needed = '，其次'.join(f"{n['wuxing']}（{n['stem']}）" for n in advice['needed'])
        parts.append(f"按《穷通宝鉴》调候，你的八字最需要{needed}")
    if 'colour' in aspects:
        head = f"衣服首选{_ordered(wear, lambda w: '、'.join(w['colours']))}"
        parts.append(head + (f"；少穿{'、'.join(avoid[0]['colours'])}（{avoid[0]['wuxing']}）" if avoid else ''))
    if 'colour' in aspects or 'things' in aspects:
        parts.append(f"佩戴首选{_ordered(wear[:2], lambda w: w['things'])}")
    if 'direction' in aspects:
        head = f"有利方位是{_ordered(wear, lambda w: HETU[w['wuxing']][0])}"
        parts.append(head + (f"；少往{HETU[avoid[0]['wuxing']][0]}（{avoid[0]['wuxing']}）" if avoid else ''))
    if 'number' in aspects:
        parts.append(f"幸运数字是{_ordered(wear, lambda w: HETU[w['wuxing']][1])}")
    return ('' if parts[0].startswith('按') else '按你的八字，') + '；'.join(parts) + '。'


def colour_lines(advice: dict, aspects: list[str] | None = None) -> list[str]:
    """Layer 2: why, link by link, each with its passage."""
    if advice['status'] != 'ok':
        return []
    aspects = aspects or advice.get('aspects') or ['colour']
    tiaohou = advice['tiaohou']
    needed = '、'.join(f"{n['stem']}（{n['wuxing']}）" for n in advice['needed'])
    season = '（这一月没有专段，按季节总论）' if advice['seasonal_only'] else ''
    lines = [
        f"为什么：你是{advice['day_master']}日主，生在{advice['month_branch']}月{season}。《穷通宝鉴》这一格先要"
        f"{needed}，原文「{tiaohou['quote']}」（{tiaohou['passage_id']}）。原文还讲了条件：{tiaohou['conditions']}",
        '五行配色：《三命通会》卷七「' + '」「'.join(COLOUR_QUOTES[w['wuxing']] for w in advice['wear'])
        + f"」（{COLOUR_SOURCE}）；《梅花易数》卷二「{SHADE_QUOTE}」（{SHADE_SOURCE}）。",
        '佩戴物的五行：《梅花易数》' + '；'.join(f"「{w['thing_quote']}」（{w['thing_source']}）"
                                              for w in advice['wear'][:2]) + '。',
    ]
    if 'direction' in aspects or 'number' in aspects:
        lines.append(f"方位与数字：《协纪辨方书》卷一「{HETU_QUOTE}」（{HETU_SOURCE}）。")
    if 'element' in aspects:
        lines.append('问「五行缺什么」时，古法不数哪种五行少，而是看这张八字最需要哪种；上面按《穷通宝鉴》调候回答，'
                     '《子平真诠》按月令格局取用神是另一种方法，结论要另核，这里不合在一起。')
    if advice['avoid']:
        a = advice['avoid'][0]
        lines.append(f"为什么少穿{'、'.join(a['colours'])}：{a['wuxing']}克{TIANGAN_WUXING[a['overcomes']]}，"
                     f"会压住你最需要的{a['overcomes']}。子平说「{AVOID_SOURCE[1]}」（{AVOID_SOURCE[0]}）。")
    else:
        lines.append('这一格要用的几种五行里已经有克首选用神的那一种，所以不列要少穿的颜色。')
    lines.append(advice['limit'])
    return lines
