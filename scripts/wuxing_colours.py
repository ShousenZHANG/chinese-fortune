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

Step 1 is the cell's general choice, not a verdict on this chart: every cell
of the registry is ``requires_chart_conditions``, and its review note names
the exceptions (「丙丁过多与水局另论」) that only the whole chart settles. The
ones the branches settle — a 三合 or 三会 frame, 「X局」 — are read off the
chart (``exception_checks``); 「过多」 has no stated threshold and stays
undecided; everything else in the note is shown whole and not claimed. No colour is
named to avoid: nothing in these passages makes the 五行 that overcomes the
first stem this person's 忌神.
No classical sentence says that wearing a colour changes what happens; the
answer says so once, as a limit of this question, not as a disclaimer.
"""
from __future__ import annotations

import re
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
LIMIT = ('古籍讲的是八字需要哪种五行，没有一句说穿某种颜色、戴某样东西、用某个数字或往某个方向就能改变遭遇；'
         '按喜用五行换算这些是后来的通行做法，这里按这个做法换算。')

# 「X局」 in a review note: a 三合 or 三会 frame. Only a full set of three counts;
# a half frame is not 成局. 土 has no single agreed frame, so it is not judged.
FRAMES = {'水': (('申', '子', '辰'), ('亥', '子', '丑')), '火': (('寅', '午', '戌'), ('巳', '午', '未')),
          '木': (('亥', '卯', '未'), ('寅', '卯', '辰')), '金': (('巳', '酉', '丑'), ('申', '酉', '戌'))}
FRAME_RE = re.compile(r'([水火木金土])局')
EXCESS_RE = re.compile(r'([甲乙丙丁戊己庚辛壬癸]+)(过多|太多)')

CELL_STATUS = {'supported_with_conditions': '原文支持，但有条件', 'partially_supported': '原文只部分支持',
               'conflicts_with_text': '旧表与原文不合，这里按原文', 'seasonal_only': '这一月没有专段，只按季节总论'}


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


def _frame_check(wuxing: str, branches: list[str]) -> dict:
    name = f'{wuxing}局'
    if wuxing == '土':
        return {'condition': name, 'status': 'unknown', 'reason': '土局的成局口径各书不一，本工具不判'}
    have = set(branches)
    sets = FRAMES[wuxing]
    shown = '、'.join(branches)
    full = next((s for s in sets if set(s) <= have), None)
    if full:
        return {'condition': name, 'status': 'met', 'basis': f"地支{''.join(full)}齐全，你的地支是{shown}"}
    # Each unknown pillar can supply at most one missing branch.
    unknown_pillars = 4 - len(branches)
    if unknown_pillars and any(len(set(s) - have) <= unknown_pillars for s in sets):
        why = '时辰未知，差一支就凑齐' if unknown_pillars == 1 else f'还有{unknown_pillars}柱地支未知，可能凑齐'
        return {'condition': name, 'status': 'unknown', 'reason': f"{why}，你的地支是{shown or '无'}"}
    return {'condition': name, 'status': 'not_met',
            'basis': f"三合{''.join(sets[0])}、三会{''.join(sets[1])}都不齐，你的地支是{shown}"}


def exception_checks(chart: dict, note: str) -> list[dict]:
    """The note's exceptions the chart's own branches can settle, and the ones it cannot.

    Facts only: whether a frame stands, with the branches that show it. Whether
    that frame changes the choice is the note's business, and it is shown whole.
    """
    pillars = chart.get('four_pillars') or {}
    branches = [pillars[p]['branch'] for p in ('year', 'month', 'day', 'hour')
                if (pillars.get(p) or {}).get('branch')]
    checks = [_frame_check(w, branches) for w in dict.fromkeys(FRAME_RE.findall(note or ''))]
    checks += [{'condition': f'{stems}{word}', 'status': 'unknown', 'reason': '原文没说多少算多'}
               for stems, word in dict.fromkeys(EXCESS_RE.findall(note or ''))]
    return checks


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
    return {
        'status': 'ok', 'key': key, 'cell_status': audit['status'],
        'seasonal_only': audit['status'] == 'seasonal_only',
        'day_master': stem, 'month_branch': month,
        'needed': needed, 'wear': wear,
        # The cell's general choice; the note's exceptions are not checked against this chart.
        'scope': 'general_choice_for_cell',
        'individual_application': audit.get('individual_application', 'requires_chart_conditions'),
        # Frames the branches settle are checked; the rest of the note is not,
        # so the chart as a whole is still not claimed as checked.
        'chart_conditions_checked': False,
        'exception_checks': exception_checks(chart, audit['review_note']),
        'tiaohou': {'passage_id': ref, 'quote': _excerpt(ref, first['stem']),
                    'review_note': audit['review_note'],
                    'conditional_stems': list(audit.get('source_conditional_candidates') or []),
                    'other_passages': [r for r in refs if r != ref]},
        'sources': {'colour': COLOUR_SOURCE, 'shade': SHADE_SOURCE, 'things': THING_SOURCE},
        'limit': LIMIT,
    }


def _ordered(wear: list[dict], name: Callable[[dict], str]) -> str:
    return '，其次'.join(f"{name(w)}（{w['wuxing']}）" for w in wear)


def _cell(advice: dict) -> str:
    return f"{advice['day_master']}日主生在{advice['month_branch']}月"


def colour_lead(advice: dict, aspects: list[str] | None = None) -> str:
    """The first sentence: the cell's general choice for what the question asked,
    then that the chart's own exceptions were not checked."""
    if advice['status'] != 'ok':
        return f"这一问现在给不出，因为{advice['reason']}。"
    aspects = aspects or advice.get('aspects') or ['colour']
    wear = advice['wear']
    needed = '，其次'.join(f"{n['stem']}（{n['wuxing']}）" for n in advice['needed'])
    parts = []
    if 'colour' in aspects:
        parts.append(f"衣服首选{_ordered(wear, lambda w: '、'.join(w['colours']))}")
    if 'colour' in aspects or 'things' in aspects:
        parts.append(f"佩戴首选{_ordered(wear[:2], lambda w: w['things'])}")
    if 'direction' in aspects:
        parts.append(f"方位是{_ordered(wear, lambda w: HETU[w['wuxing']][0])}")
    if 'number' in aspects:
        parts.append(f"数字是{_ordered(wear, lambda w: HETU[w['wuxing']][1])}")
    head = f"按《穷通宝鉴》调候，{_cell(advice)}，这一格一般先取{needed}"
    if parts:
        head += '。照这个换算：' + '；'.join(parts)
    return head + '。' + _exception_sentence(advice)


def _exception_sentence(advice: dict) -> str:
    """What the chart's branches settle about the cell's exceptions, in one or two sentences."""
    checks = advice.get('exception_checks') or []
    if not checks:
        return '这是这一格的一般取法，你的盘是不是原文说的例外（见下）还没有逐条核对。'
    said = []
    for c in checks:
        if c['status'] == 'met':
            said.append(f"{c['condition']}成立（{c['basis']}）")
        elif c['status'] == 'not_met':
            said.append(f"{c['condition']}不成立（{c['basis']}）")
        else:
            said.append(f"{c['condition']}没判（{c['reason']}）")
    text = '这是这一格的一般取法。这一格另论的例外，按你的盘：' + '；'.join(said) + '。'
    if any(c['status'] == 'met' for c in checks):
        # Only the note says what the condition does: in 戊午 and 辛午 a fire
        # frame weakens 癸 and keeps 壬 first, i.e. confirms the general choice.
        text += '成立的这一条对取法有什么影响，原文写在下面的审校说明里，这里没有替你判断。'
    return text


def colour_lines(advice: dict, aspects: list[str] | None = None) -> list[str]:
    """Layer 2: why, link by link, each with its passage."""
    if advice['status'] != 'ok':
        return []
    aspects = aspects or advice.get('aspects') or ['colour']
    tiaohou = advice['tiaohou']
    needed = '、'.join(f"{n['stem']}（{n['wuxing']}）" for n in advice['needed'])
    season = '（这一月没有专段，按季节总论）' if advice['seasonal_only'] else ''
    conditional = ('有条件才取：' + '、'.join(tiaohou['conditional_stems']) + '。') if tiaohou['conditional_stems'] else ''
    lines = [
        f"为什么：你是{advice['day_master']}日主，生在{advice['month_branch']}月{season}。《穷通宝鉴》这一格先要"
        f"{needed}，原文「{tiaohou['quote']}」（{tiaohou['passage_id']}）。{conditional}",
        f"这一格的核对状态：{CELL_STATUS.get(advice['cell_status'], advice['cell_status'])}。"
        f"审校说明：{tiaohou['review_note']}"
        + ('其中能由地支判定的局已在上面核对；' if advice.get('exception_checks') else '')
        + '其余例外要看整张盘（透干、藏支、合化、旺衰），本工具没有逐条核对，所以上面是这一格的一般取法，'
        '不是按你的全盘定的。',
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
    lines.append('不列「少穿」的颜色：这几段原文没有说克用神的那种五行就是你的忌神，忌什么要看全盘。')
    lines.append(advice['limit'])
    return lines
