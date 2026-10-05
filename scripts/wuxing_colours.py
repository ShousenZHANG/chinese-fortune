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

from classical_search import climate_passages, get_passage
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
# What each frame a cell's note names does to the cell's general choice, read
# by hand against the cell's own sentence about it (a test keeps the list
# complete). (cell, frame) -> (effect, condition, stems, passage):
#   confirms - the sentence still takes the general choice (丙寅 火局「端取壬水」);
#   changes  - it takes another stem, reorders, or only tells a fate without a
#              choice: the general choice is not this person's choice;
#   condition 'absent' / 'present' - the sentence holds only when none / one
#              of ``stems`` stands among the other heavenly stems
#              (庚子「不见丙丁者」, 戊戌「壬癸透干」); otherwise it does not apply.
# 土局 is not judged (no single agreed frame), so it has no row.
FRAME_REVIEW: dict[tuple[str, str], tuple[str, str, str, str]] = {
    ('丙|寅', '火'): ('confirms', '', '', 'qiongtong:c003:p0016'),   # 支成火局，端取壬水为贵
    ('丁|午', '火'): ('confirms', '', '', 'qiongtong:c003:p0218'),   # 得庚壬两透者，科甲定然
    ('戊|午', '火'): ('confirms', '', '', 'qiongtong:c004:p0052'),   # 透癸不能大济，得壬水出干则此非比
    ('辛|午', '火'): ('confirms', '', '', 'qiongtong:c005:p0178'),   # 得壬透破火方可
    ('癸|子', '水'): ('confirms', '', '', 'qiongtong:c006:p0224'),   # 得丙火重出干者……之荣
    ('庚|子', '水'): ('changes', 'absent', '丙丁', 'qiongtong:c005:p0116'),   # 不见丙丁者，此乃伤官格
    ('壬|亥', '水'): ('changes', 'absent', '戊己', 'qiongtong:c006:p0107'),   # 不见戊己，名润下格
    ('辛|酉', '金'): ('changes', 'absent', '壬', 'qiongtong:c005:p0209'),     # 无壬淘洗，此宜用丁
    ('庚|申', '水'): ('changes', 'absent', '丁', 'qiongtong:c005:p0075'),     # 乏丁用丙
    ('丁|未', '水'): ('changes', 'present', '壬癸', 'qiongtong:c003:p0238'),  # 见水透干，则湿木性
    ('戊|辰', '木'): ('changes', 'present', '甲乙', 'qiongtong:c004:p0023'),  # 又甲乙出干……得一庚透
    ('戊|戌', '水'): ('changes', 'present', '壬癸', 'qiongtong:c004:p0087'),  # 壬癸透干，用戊止流
    ('辛|子', '水'): ('changes', 'present', '癸', 'qiongtong:c005:p0244'),    # 癸水出干，有二戊制者
    ('甲|酉', '木'): ('changes', 'present', '甲乙', 'qiongtong:c002:p0053'),  # 干透比劫，反取庚金为先
    ('甲|寅', '木'): ('changes', '', '', 'qiongtong:c002:p0012'),   # 得庚为贵
    ('甲|寅', '水'): ('changes', '', '', 'qiongtong:c002:p0012'),   # 戊透为贵
    ('甲|辰', '金'): ('changes', '', '', 'qiongtong:c002:p0021'),   # 方可用丁
    ('乙|辰', '水'): ('changes', '', '', 'qiongtong:c002:p0089'),   # 丙戊高透
    ('乙|酉', '金'): ('changes', '', '', 'qiongtong:c002:p0119'),   # 宜暗藏丁
    ('丁|寅', '火'): ('changes', '', '', 'qiongtong:c003:p0180'),   # 总不可无水
    ('丁|辰', '木'): ('changes', '', '', 'qiongtong:c003:p0201'),   # 取庚为先
    ('丁|辰', '水'): ('changes', '', '', 'qiongtong:c003:p0202'),   # 戊己两透；一甲破土定是常人
    ('戊|申', '水'): ('changes', '', '', 'qiongtong:c004:p0070'),   # 宜取甲泄之
    ('己|卯', '木'): ('changes', '', '', 'qiongtong:c004:p0141'),   # 庚透富贵；当用丁泄之
    ('己|酉', '金'): ('changes', '', '', 'qiongtong:c004:p0182'),   # 无丙丁出救
    ('庚|卯', '木'): ('changes', '', '', 'qiongtong:c005:p0023'),   # 审校：从财木局等分支忌比助
    ('庚|辰', '火'): ('changes', '', '', 'qiongtong:c005:p0042'),   # 癸水透；见壬制之
    ('庚|巳', '金'): ('changes', '', '', 'qiongtong:c005:p0050'),   # 用丙无力，用丁方妙
    ('庚|戌', '水'): ('changes', '', '', 'qiongtong:c005:p0094'),   # 丙透救之
    ('庚|亥', '水'): ('changes', '', '', 'qiongtong:c005:p0105'),   # 支见亥子，得己出制
    ('辛|寅', '火'): ('changes', '', '', 'qiongtong:c005:p0137'),   # 庚壬两透，破局制火
    ('辛|寅', '水'): ('changes', '', '', 'qiongtong:c005:p0138'),   # 得丙透照暖
    ('壬|卯', '木'): ('changes', '', '', 'qiongtong:c006:p0025'),   # 有庚透者
    ('壬|未', '木'): ('changes', '', '', 'qiongtong:c006:p0065'),   # 当用金水为贵
    ('壬|子', '水'): ('changes', '', '', 'qiongtong:c006:p0116'),   # 丙不出干，即有戊土，亦系庸人
    ('壬|丑', '金'): ('changes', '', '', 'qiongtong:c006:p0131'),   # 见丁颇吉
    ('癸|寅', '火'): ('changes', '', '', 'qiongtong:c006:p0137'),   # 有壬出救者
    ('癸|午', '火'): ('changes', '', '', 'qiongtong:c006:p0175'),   # 支成炎局，无壬出干
    ('癸|亥', '木'): ('changes', '', '', 'qiongtong:c006:p0213'),   # 有丁出干清寒；干见丙丁异路之荣
}
# The passages' other names for a frame: 癸午 says 炎局.
FRAME_WORDS = {'火': ('火局', '炎局')}
EXCESS_RE = re.compile(r'([甲乙丙丁戊己庚辛壬癸]+)(过多|太多)')
STEM_CHARS = '甲乙丙丁戊己庚辛壬癸'
# Every cell whose general stems span two or more elements and whose note or
# cited passage says 兼用, 并用, 皆用, 并论, 参酌, 随宜, 酌用 or 不拘先后 was
# read by hand against the passage; a test keeps the list complete.
# UNORDERED: (kind, the words that decide it, how the lead says it). joint:
# used together; by_trouble: chosen by what the chart shows.
UNORDERED: dict[str, tuple[str, str, str]] = {
    '辛|午': ('joint', '兼用', '{stems}兼用'),                         # 「壬己兼用」 (c005:p0178)
    '丁|酉': ('joint', '皆用', '{stems}并用'),                         # 「八月甲丙庚皆用」 (c003:p0249)
    '庚|巳': ('by_trouble', '非拘执先後',                               # 「須用壬丙戊，但非拘执先後」 (c005:p0051)
             '须用{stems}，原文说不拘先后，要看盘上具体缺什么来取'),
    '丙|亥': ('by_trouble', '随宜酌用',                                 # 「木旺宜庚，水旺宜戊……随宜酌用可也」 (c003:p0133)
             '{stems}要看盘上哪样旺来取，原文说随宜酌用'),
}
# The word appears, but the passage still gives the general stems an order
# (the 酌用 there is about the conditional stems).
ORDERED_DESPITE: dict[str, str] = {
    '壬|子': '戊先丙后',
    '丁|戌': '仍分优劣',                                  # 「三秋甲庚丙并用，仍分优劣……九月端用甲庚」
    '丁|亥': '甲木为尊，庚金佐之', '丁|子': '甲木为尊，庚金佐之', '丁|丑': '甲木为尊，庚金佐之',
    '戊|午': '先看壬水，次取甲木',
    '己|申': '先癸後丙', '己|酉': '先癸後丙', '己|戌': '先癸後丙',
    '甲|寅': '癸藏丙透',                                  # 「得丙癸逢……癸藏丙透，名寒木向阳」
    '庚|酉': '用丁甲',                                    # 「用丁甲，丙不可少」
}

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


def _frame_sentences(key: str, wuxing: str) -> list[dict]:
    """The cell's own sentences about this frame standing, verbatim, each with its passage.

    「若干支无火局」 speaks of the frame's absence and is left out.
    """
    found = []
    for passage in climate_passages(key).get('results', []):
        for sentence in passage['text'].split('。'):
            for word in FRAME_WORDS.get(wuxing, (f'{wuxing}局',)):
                if word in sentence and not re.search(rf'(?:无|無|不成|不见)[^，]{{0,2}}{word}', sentence):
                    found.append({'passage_id': passage['passage_id'], 'quote': sentence.strip() + '。'})
                    break
    return found


def _other_stems(chart: dict) -> tuple[str, bool]:
    """The heavenly stems besides the day master's, and whether all three are known."""
    pillars = chart.get('four_pillars') or {}
    known = [(pillars.get(p) or {}).get('stem') for p in ('year', 'month', 'hour')]
    return ''.join(s for s in known if s), all(known)


def _frame_effect(key: str, wuxing: str, stems: tuple[str, bool]) -> dict:
    """What a standing frame does to this cell's general choice, per FRAME_REVIEW."""
    effect, condition, needed, passage = FRAME_REVIEW.get((key, wuxing), ('changes', '', '', ''))
    shown, complete = stems
    if condition == 'absent' and any(s in shown for s in needed):
        hit = '、'.join(s for s in needed if s in shown)
        return {'effect': 'not_applicable', 'reviewed_passage': passage,
                'why': f'原文这一说要不见{needed}，你的盘天干有{hit}'}
    if condition == 'present' and complete and not any(s in shown for s in needed):
        return {'effect': 'not_applicable', 'reviewed_passage': passage,
                'why': f"原文这一说要{'或'.join(needed)}透出天干，你的盘天干没有"}
    return {'effect': effect, 'reviewed_passage': passage}


def exception_checks(chart: dict, note: str, key: str | None = None) -> list[dict]:
    """The note's exceptions the chart's own branches can settle, and the ones it cannot.

    Facts only: whether a frame stands, with the branches that show it, and
    the cell's own sentences about it. Those sentences mostly carry further
    conditions (「不见丙丁者」「干透比劫」) that are not checked here.
    """
    pillars = chart.get('four_pillars') or {}
    branches = [pillars[p]['branch'] for p in ('year', 'month', 'day', 'hour')
                if (pillars.get(p) or {}).get('branch')]
    checks = [_frame_check(w, branches) for w in dict.fromkeys(FRAME_RE.findall(note or ''))]
    if key:
        stems = _other_stems(chart)
        checks = [{**c, 'passages': _frame_sentences(key, c['condition'][0]),
                   **_frame_effect(key, c['condition'][0], stems)} if c['status'] == 'met' else c for c in checks]
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
        same = next((n for n in needed if n['wuxing'] == wuxing), None)
        if same:
            # 「庚辛」: both metal, one colour, but both named.
            same['stems'].append(stem_needed)
        else:
            needed.append({'stem': stem_needed, 'stems': [stem_needed], 'wuxing': wuxing})
    first = needed[0]
    # Quote the passage that names the stem, not merely the cell's first one.
    refs = [r['passage_id'] for r in audit['source_refs']]
    ref = next((r for r in refs if first['stem'] in get_passage(r)['text']), refs[0])
    wear = [{'wuxing': n['wuxing'], 'stem': n['stem'], 'colours': list(COLOURS[n['wuxing']]),
             'things': THINGS[n['wuxing']][0], 'colour_quote': COLOUR_QUOTES[n['wuxing']],
             'thing_quote': THINGS[n['wuxing']][1], 'thing_source': THINGS[n['wuxing']][2]} for n in needed]
    checks = exception_checks(chart, audit['review_note'], key)
    met = any(c['status'] == 'met' and c.get('effect') == 'changes' for c in checks)
    return {
        'status': 'ok', 'key': key, 'cell_status': audit['status'],
        'seasonal_only': audit['status'] == 'seasonal_only',
        'day_master': stem, 'month_branch': month,
        'needed': needed, 'wear': wear,
        'order': _order(key, [n['stem'] for n in needed]),
        # The cell's general choice; the note's exceptions are not checked against this chart.
        'scope': 'general_choice_for_cell',
        # A frame the cell treats apart stands in this chart: the general
        # choice is not given as this person's choice.
        'individual_application': ('exception_met' if met
                                   else audit.get('individual_application', 'requires_chart_conditions')),
        'personal_choice': not met,
        # Frames the branches settle are checked; the rest of the note is not,
        # so the chart as a whole is still not claimed as checked.
        'chart_conditions_checked': False,
        'exception_checks': checks,
        'tiaohou': {'passage_id': ref, 'quote': _excerpt(ref, first['stem']),
                    'review_note': audit['review_note'],
                    'conditional_stems': list(audit.get('source_conditional_candidates') or []),
                    'other_passages': [r for r in refs if r != ref]},
        'sources': {'colour': COLOUR_SOURCE, 'shade': SHADE_SOURCE, 'things': THING_SOURCE},
        'limit': LIMIT,
    }


def _ordered(wear: list[dict], name: Callable[[dict], str], joint: bool = False) -> str:
    items = [f"{name(w)}（{w['wuxing']}）" for w in wear]
    if joint and len(items) > 1:
        return '，'.join(items) + '，不分先后'
    return '，其次'.join(items)


def _order(key: str, stems: list[str]) -> str:
    """ranked, joint or by_trouble for this cell's general stems."""
    return UNORDERED[key][0] if key in UNORDERED and len(stems) > 1 else 'ranked'


def modality_violations(advice: dict, text: str) -> list[str]:
    """Where the rendered text is stronger or weaker than the cell's note.

    A conditional stem (「有条件」「酌用」「亦可」「……才用」) may not be
    written as a general choice, and stems the note takes in no order
    (「兼用」「并用」「非拘执先后」) may not be put in order.
    """
    found = []
    for stem in advice['tiaohou']['conditional_stems']:
        if re.search(rf'(?:先取|其次)[{STEM_CHARS}、]*{stem}[{STEM_CHARS}、]*（', text):
            found.append(f'有条件的{stem}写成了一般取法')
    if advice.get('order', 'ranked') != 'ranked':
        if re.search(r'先取|首选', text):
            found.append('原文不分先后，却写了先取或首选')
        for n in advice['needed'][1:]:
            if re.search(rf"其次[{STEM_CHARS}、]*{n['stem']}", text):
                found.append(f"原文不分先后，{n['stem']}被排成了其次")
    return found


def _cell(advice: dict) -> str:
    return f"{advice['day_master']}日主生在{advice['month_branch']}月"


def colour_lead(advice: dict, aspects: list[str] | None = None) -> str:
    """The first sentence: the cell's general choice for what the question asked,
    then that the chart's own exceptions were not checked."""
    if advice['status'] != 'ok':
        return f"这一问现在给不出，因为{advice['reason']}。"
    aspects = aspects or advice.get('aspects') or ['colour']
    wear = advice['wear']
    order = advice.get('order', 'ranked')
    joint = order != 'ranked'
    stems = [f"{'、'.join(n.get('stems', [n['stem']]))}（{n['wuxing']}）" for n in advice['needed']]
    if order == 'joint':
        needed = UNORDERED[advice['key']][2].format(stems='、'.join(stems))
    elif order == 'by_trouble':
        needed = UNORDERED[advice['key']][2].format(stems='、'.join(stems))
    else:
        needed = '先取' + '，其次'.join(stems)
    first = '' if joint else '首选'
    parts = []
    if 'colour' in aspects:
        parts.append(f"衣服{first}{_ordered(wear, lambda w: '、'.join(w['colours']), joint)}")
    if 'colour' in aspects or 'things' in aspects:
        # Two things normally, the first two in order; taking the first two of
        # an unordered cell would rank it after all.
        parts.append(f"佩戴{first}{_ordered(wear if joint else wear[:2], lambda w: w['things'], joint)}")
    if 'direction' in aspects:
        parts.append(f"方位是{_ordered(wear, lambda w: HETU[w['wuxing']][0], joint)}")
    if 'number' in aspects:
        parts.append(f"数字是{_ordered(wear, lambda w: HETU[w['wuxing']][1], joint)}")
    if not advice.get('personal_choice', True):
        text = _withheld_lead(advice, needed, wear, aspects)
    else:
        head = f"按《穷通宝鉴》调候，{_cell(advice)}，这一格一般{needed}"
        if parts:
            head += '。照这个换算：' + '；'.join(parts)
        text = head + '。' + _exception_sentence(advice)
    drift = modality_violations(advice, text)
    if drift:
        # A deterministic guard, not a style note: refuse rather than say more
        # (or less) than the note does.
        raise RuntimeError('渲染的情态与审校说明不符：' + '；'.join(drift))
    return text


def _withheld_lead(advice: dict, needed: str, wear: list[dict], aspects: list[str]) -> str:
    """The lead when a frame the cell treats apart stands in this chart."""
    met = [c for c in advice['exception_checks'] if c['status'] == 'met' and c.get('effect') == 'changes']
    what = {'colour': '颜色', 'things': '佩戴', 'direction': '方位', 'number': '数字', 'element': '喜用五行'}
    asked = '、'.join(dict.fromkeys(what[a] for a in aspects if a in what)) or '颜色'
    general = '和'.join(f"{'、'.join(w['colours'])}（{w['wuxing']}）" for w in wear)
    said = []
    for c in met:
        quotes = '；'.join(f"「{q['quote']}」（{q['passage_id']}）" for q in c.get('passages', [])[:2])
        said.append(f"{c['condition']}成立（{c['basis']}），原文对{c['condition']}另有说法："
                    + (quotes if quotes else f"见审校说明「{advice['tiaohou']['review_note']}」与下列出处"))
    return (f"按你的盘，这一问给不出个人首选的{asked}：{_cell(advice)}，《穷通宝鉴》这一格一般{needed}"
            f"，换成颜色是{general}；但你的盘" + '；'.join(said) + '。'
            '原文对这种局另有取法或另带条件（透不透某干、有没有制化），程序没有逐条判断，'
            '所以上面那组一般取法不当成你的个人建议；要定，得按原文对照全盘看。')


def _exception_sentence(advice: dict) -> str:
    """What the chart's branches settle about the cell's exceptions, in one or two sentences."""
    checks = advice.get('exception_checks') or []
    if not checks:
        return '这是这一格的一般取法，你的盘是不是原文说的例外（见下）还没有逐条核对。'
    said = []
    for c in checks:
        if c['status'] == 'met' and c.get('effect') == 'confirms':
            quote = next((q for q in c.get('passages', []) if q['passage_id'] == c['reviewed_passage']), None)
            said.append(f"{c['condition']}成立（{c['basis']}），原文在这种局下仍取上面的用神"
                        + (f"：「{quote['quote']}」（{quote['passage_id']}）" if quote else ''))
        elif c['status'] == 'met' and c.get('effect') == 'not_applicable':
            said.append(f"{c['condition']}成立（{c['basis']}），但{c['why']}，那一说不适用，仍按一般取法")
        elif c['status'] == 'met':
            said.append(f"{c['condition']}成立（{c['basis']}）")
        elif c['status'] == 'not_met':
            said.append(f"{c['condition']}不成立（{c['basis']}）")
        else:
            said.append(f"{c['condition']}没判（{c['reason']}）")
    text = '这是这一格的一般取法。这一格另论的例外，按你的盘：' + '；'.join(said) + '。'
    if any(c['status'] == 'met' and c.get('effect') not in ('confirms', 'not_applicable') for c in checks):
        # Only a call without FRAME_REVIEW reaches here (a key was not given).
        text += '成立的这一条会不会改变上面的取法，这里没有判断：审校说明只作提示，要对照这一格的原文（出处见下）来看。'
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
                                              for w in (advice['wear'] if advice.get('order', 'ranked') != 'ranked'
                                                        else advice['wear'][:2])) + '。',
    ]
    if 'direction' in aspects or 'number' in aspects:
        lines.append(f"方位与数字：《协纪辨方书》卷一「{HETU_QUOTE}」（{HETU_SOURCE}）。")
    if 'element' in aspects:
        lines.append('问「五行缺什么」时，古法不数哪种五行少，而是看这张八字最需要哪种；上面按《穷通宝鉴》调候回答，'
                     '《子平真诠》按月令格局取用神是另一种方法，结论要另核，这里不合在一起。')
    lines.append('不列「少穿」的颜色：这几段原文没有说克用神的那种五行就是你的忌神，忌什么要看全盘。')
    lines.append(advice['limit'])
    return lines
