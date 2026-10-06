"""Answer a real-life decision from 《高性价比人生指南》, the book's way.

A port of the book's own decision workflow onto the frozen library. The
workflow is the book repository's skills/life-decision-guide at commit
842e11c9 (code, MIT License, Copyright (c) 2026 eternity4719; the notice
ships in assets/life_guide.json under source.license_detail.code_notice):

0. Stop first for an emergency in progress, a suicidal thought, or a legal
   process already under way: give the first action and the reviewed entries
   for that situation, and nothing else — no ranking.
1. Find the sections whose README question matches, then the entries.
2. Rank: fit first in two bands (an automatic search also finds entries that
   merely mention the topic), then the book's order within a band — 性价比
   tier, then evidence grade; never across 口径 (寿命, 钱, 时间精力, 人身自由
   are not traded for each other).
3. Return 先做 (per 口径), 别做 (the book's 反面清单 entries that match), and
   书里没写 when nothing matches; every row cites its section and entry,
   keeps its full fields, and carries the notes the workflow requires.

Nothing here writes the one-sentence conclusion: that is the host's, from
these rows, under references/29-life-decision.md.
"""
from __future__ import annotations

import re

import life_search as ls
from region import resolve_region

LIMIT = 7
# What turns those words into something else, within the clause that holds
# them: insurance, prevention, a hypothetical, the past, a forecast
# (「中风险理财」「火灾险」「怎么预防心梗」「去年中风过」「六爻看我会不会中风」).
# 「很危险」 is not insurance.
NOT_NOW = re.compile(r'保险|[灾外疾疗寿]险|险种|投保|理赔|风险|预防|防止|防溺|怎么防|防范|'
                     r'会不会|可能会|以后|将来|如果|万一|假如|要是|假设|'
                     r'去年|前年|上个月|以前|曾经|小时候|后遗症|康复|恢复期|'
                     r'最近|经常|有时|偶尔|老是|总是|一直有|'
                     r'牌子|品牌|哪款|药膏|烫伤膏|急救包|急救箱|'
                     r'八字|命里|命理|命盘|运势|流年|大运|紫微|斗数|六爻|起卦|算一|算算|卦|塔罗|星座|风水')
# A background word in one clause says nothing about the next: 「我有保险」 does
# not cancel 「同事触电昏迷了」, 「如果以后……？但我现在喘不上气」 is now. Not 不过:
# it is inside 「喘不过气」.
CLAUSE = re.compile(r'[，,。!！?？；;、\s]+|但是|可是|而且|但')
# 「没有胸痛」 denies the symptom; 「怕不是心梗」「是不是心梗」 do not.
NEGATED = re.compile(r'(?<![怕莫是])(?:不是|没有|没|并非|不)$')
CRISIS = re.compile(r'自杀|不想活|活不下去|活着没意思|活着没意义|想去死|想死(?!在)|死了算了|不如死了|轻生|结束生命|'
                    r'割腕|跳楼|了结自己')
LEGAL = re.compile(r'被传唤|传唤我|被公安传唤|被拘留|被刑拘|被起诉|收到起诉书|收到了起诉书|起诉状|被抓|被立案|被逮捕|'
                   r'传票|派出所叫我|被派出所叫|叫去问话')
# The book's fourth tier of whom a benefit lands on: strangers, and standing
# surety or moving money for someone.
FOURTH_TIER = re.compile(r'陌生人|路人|替人担保|替朋友担保|帮人担保|帮朋友担保|担保|帮人转账|帮人收款|救人|扶老人|'
                         r'要不要扶|该不该扶|扶不扶|扶起来|见义勇为')
LAWSUIT = re.compile(r'起诉|打官司|仲裁|告他|告公司|索赔|赔偿|维权|讨薪|要回|讨回|拖欠|欠薪|欠工资|不发工资|工资不发')
LAWSUIT_TITLE = re.compile(r'仲裁|起诉|诉讼|法院|官司')
# Sections whose amounts, time limits and lists carry a cut-off date.
POLICY_SECTIONS = frozenset({7, 19, 21, 24, 31, 32})
DONT_SECTION = 6
# Asking what to do first: a long article that lays the steps out in order is
# the book's own answer (《被裁了之后先做什么》), so its first steps come along.
FIRST_STEP = re.compile(r'先做什么|第一步|第一件事|怎么办|先干什么|当天')
# An emergency in progress, the way people describe it, with the book's section
# 13 entries for it and the first action they give: 'call' (120; 119 for a
# fire), 'do' (the first aid itself: cool a burn, keep a fracture still),
# 'gas' (out first, 13:19), 'assault' (somewhere safe, then 110, 13:42).
# One list makes both the detector and the entries, so they cannot drift
# apart. Tests check each number still holds the expected title.
GAS_LEAK = r'(?:燃气|煤气|天然气|液化气)\S{0,4}?(?:泄漏|漏气|漏了)|闻到(?:煤气|燃气|天然气)|(?:煤气|燃气)味'
EMERGENCY_ENTRIES: list[tuple[re.Pattern, list[tuple[int, int]], str]] = [
    (re.compile(r'被性侵|被强奸|遭到性侵'), [(13, 42)], 'assault'),
    (re.compile(GAS_LEAK), [(13, 19)], 'gas'),
    (re.compile(r'一氧化碳'), [(13, 19)], 'gas'),
    (re.compile(r'着火|火灾|失火|起火'), [(13, 24)], 'call'),
    (re.compile(r'(?:婴儿|宝宝|不满 ?1 岁)\S{0,8}?噎'), [(13, 43)], 'call'),
    (re.compile(r'(?:婴儿|宝宝|不满 ?1 岁)\S{0,8}?(?:没反应|没呼吸|没有呼吸)'), [(13, 44)], 'call'),
    (re.compile(r'嘴歪|一侧没劲|一边没劲|半边身子|半身不能动|说话说不清|中风|卒中|天旋地转|看东西成双'),
     [(13, 3), (13, 4)], 'call'),
    (re.compile(r'眼睛突然\S{0,3}黑|一只眼\S{0,4}黑掉'), [(13, 5)], 'call'),
    (re.compile(r'胸口压着疼|胸口剧痛|胸痛|心梗|胸口很闷|胸口闷|胸闷|胸口发紧'), [(13, 7), (13, 8)], 'call'),
    (re.compile(r'最疼的头痛|头痛欲裂|剧烈头痛'), [(13, 9)], 'call'),
    (re.compile(r'大出血|血止不住|止不住血|流血不止|血流不止|血一直流|一直在流血|流了很多血'), [(13, 12)], 'call'),
    (re.compile(r'扎进|插进身体|刺进身体'), [(13, 40)], 'call'),
    (re.compile(r'溺水|落水|掉(?:进|到)?(?:河|水|湖|海|池塘|水库)里?'), [(13, 25)], 'call'),
    (re.compile(r'触电'), [(13, 18)], 'call'),
    (re.compile(r'中毒|误服|误吞|误食|喝了农药|吃错药|吞了电池|吞了纽扣电池'), [(13, 20)], 'call'),
    (re.compile(r'噎住|卡住喉咙|卡在喉咙'), [(13, 26), (13, 43)], 'call'),
    (re.compile(r'过敏性休克|全身起疹'), [(13, 15)], 'call'),
    (re.compile(r'抽搐'), [(13, 16)], 'call'),
    (re.compile(r'喘不上气|喘不过气|上不来气|透不过气|呼吸困难'), [(13, 15), (13, 11)], 'call'),
    (re.compile(r'倒地|没呼吸|没有呼吸|心跳停|心脏骤停|昏迷|叫不醒|晕倒|昏倒|晕过去|不省人事|没有意识|没意识|'
                r'(?:叫|喊|拍)\S{0,3}?没反应|人没反应'), [(13, 1), (13, 2)], 'call'),
    (re.compile(r'中暑|热射病'), [(13, 22), (13, 23)], 'call'),
    (re.compile(r'被蛇咬|蛇咬'), [(13, 29)], 'call'),
    (re.compile(r'烫伤|烧伤'), [(13, 14)], 'do'),
    (re.compile(r'骨折'), [(13, 41)], 'do'),
    (re.compile(r'溅到(?:眼睛|身上|皮肤)|[酸碱]溅'), [(13, 21)], 'do'),
]
EMERGENCY = re.compile('|'.join(f'(?:{pattern.pattern})' for pattern, _, _ in EMERGENCY_ENTRIES))
# The first action when several things happen at once: the most pressing.
ACTION_ORDER = ('assault', 'gas', 'call', 'do')
CRISIS_ENTRIES = [(1, 25), (1, 32), (29, 11)]
LEGAL_ENTRIES = [(8, 5), (8, 20)]
FIRST_ACTION = {
    # 第 13 节第 19 条: out first, then the phone; not back in for the valve.
    ('gas', True): '先把人都带到室外，再打 119；别留在屋里找原因，也别回去关阀门。照下面第 13 节的条目做，别先讲性价比。',
    ('gas', False): '先把人都带到室外，再打你所在地的急救或消防电话；别留在屋里找原因，也别回去关阀门。'
                    '照下面第 13 节的条目做，别先讲性价比。',
    ('emergency', True): '先打 120（着火打 119），照下面第 13 节的条目做现场第一个动作，别先讲性价比。',
    ('emergency', False): '先打你所在地的急救电话，照下面第 13 节的条目做现场第一个动作，别先讲性价比；条目里的 120 是中国大陆的号码。',
    ('do', True): '先照下面第 13 节的条目做现场处置；伤得重、人不清醒或者在变坏，就打 120。别先讲性价比。',
    ('do', False): '先照下面第 13 节的条目做现场处置；伤得重、人不清醒或者在变坏，就打你所在地的急救电话。别先讲性价比；'
                   '条目里的 120 是中国大陆的号码。',
    # 第 13 节第 42 条.
    ('assault', True): '先到安全的地方打 110；验伤之前别洗澡、别换洗衣服、别收拾现场，72 小时内去医院。照下面第 13 节的条目做。',
    ('assault', False): '先到安全的地方打你所在地的报警电话；验伤之前别洗澡、别换洗衣服、别收拾现场，72 小时内去医院。'
                        '照下面第 13 节的条目做。',
    ('crisis', True): '先打全国心理援助热线 12356（未成年人 12355），再看下面第 1 节和第 29 节的条目；不做劝导式分析，不评价动机。',
    ('crisis', False): '先按你所在地的官方心理危机援助信息求助，有即时危险就打当地急救电话；下面的条目里的号码是中国大陆的。'
                       '不做劝导式分析，不评价动机。',
    ('legal', True): '先看下面第 8 节的条目；书只给通用口径，个案要找律师。',
    ('legal', False): '先看下面第 8 节的条目；它们是中国大陆的法律口径，书只给通用说法，个案要找你所在地的律师。',
}
BENEFICIARY_NOTE = ('这件事的好处落在第 ④ 档（陌生人，或替人担保、帮人转账）：好处和风险要一起写——'
                    '被讹、被卷进案子、被报复，不能只写好处，也不能写成一律别管。')
# The workflow's own rule for 「法律支持你」 (skills/life-decision-guide): the
# process cost goes with it. The workflow wrote 「一审普通程序 6 个月起」; the law
# sets a limit, not a minimum (《民事诉讼法》2023 年修正第 152、164 条), so the
# durations are stated as the law states them, and only for mainland China.
PROCESS_NOTE = ('「法律支持你」的事连过程成本一起说：要不要打官司、大概多久、律师费谁掏。'
                '时长按中国大陆《民事诉讼法》（2023 年修正）第 152、164 条：一审普通程序应当在立案后 6 个月内审结，'
                '特殊情况经院长批准可延长 6 个月，还要延长的报上级法院批准；简易程序 3 个月内审结，可延长 1 个月。'
                '这是审限的上限，不是起点，也不含立案前、管辖异议、鉴定和上诉的时间；事情不归中国大陆法院管的，按当地程序。'
                '律师费不在诉讼费用里，败诉方负担的诉讼费用不包括它（合同另有约定或法律另有规定的除外）。')
# A labour dispute goes to arbitration before any court (book 7:2, 19:17).
LABOUR_NOTE = ('「法律支持你」的事连过程成本一起说。劳动争议先走劳动仲裁，不服裁决再去法院：'
               '书里写仲裁受理后 45 日内结案，复杂的最多再延 15 日，投诉和仲裁都不收费（第 7 节第 2 条、第 19 节第 17 条）；'
               '请律师的律师费一般自己出。「结案」不等于「到账」，公司没财产、老板跑了，赢了也可能拿不到钱。')
ABROAD_PROCESS_NOTE = ('「法律支持你」的事连过程成本一起说：要不要打官司、大概多久、律师费谁掏。'
                       '书里的时长、收费和仲裁规则是中国大陆的，不能直接套用：按事情发生地、有管辖权的地方的程序来，'
                       '问当地律师或官方法律援助。')
LABOUR = re.compile(r'欠薪|拖欠工资|欠工资|欠了工钱|不发工资|工资不发|讨薪|工伤|辞退|裁员|被裁|加班费|劳动仲裁|'
                    r'劳动合同|经济补偿|赔偿金|劳动监察')
POLICY_NOTE = '政策会变：这一节的金额、时限、名单写了截至日期，答复里带上日期，并提醒去官方渠道自查。'


def citation(entry: dict) -> str:
    """「第 8 节第 18 条（借钱写清借条）」: the parenthesis is the title's first
    clause, whole; a long one drops its own parenthetical, never cut mid-word."""
    clause = re.split(r'[，：；,:]', entry['title'])[0]
    if len(clause) > 20:
        clause = re.sub(r'（[^）]*）|\([^)]*\)', '', clause) or clause
    return f"第 {entry['section']} 节第 {entry['number']} 条（{clause}）"


def _states(clause: str, pattern: re.Pattern) -> bool:
    """Whether the clause says the thing is so, not that it is not."""
    for m in pattern.finditer(clause):
        if m.group(0).startswith('没'):
            # 「没有呼吸困难」 denies a symptom; 「他没有呼吸了」 is one.
            if not re.match(r'困难|急促|不畅|问题', clause[m.end():]):
                return True
        elif not NEGATED.search(clause[max(0, m.start() - 4):m.start()]):
            return True
    return False


def _now(question: str, pattern: re.Pattern) -> list[str]:
    """The clauses that describe the thing as happening now."""
    return [c for c in CLAUSE.split(question) if c and not NOT_NOW.search(c) and _states(c, pattern)]


def stop_kind(question: str) -> str | None:
    """'crisis', 'emergency' or 'legal' when the question describes one now.

    A suicidal thought always counts. An emergency or a legal process counts
    when some clause states it as happening: a clause about insurance,
    prevention, a hypothetical, the past or a forecast does not (「火灾险」
    「会不会被起诉」「六爻看我会不会中风」), and it does not cancel another clause
    that does (「同事触电昏迷了，我有保险」「我现在胸痛，帮我起一卦」).
    """
    if CRISIS.search(question):
        return 'crisis'
    if _now(question, EMERGENCY):
        return 'emergency'
    if _now(question, LEGAL):
        return 'legal'
    return None


def _stop_entries(kind: str, question: str) -> list[tuple[int, int]]:
    if kind == 'crisis':
        return CRISIS_ENTRIES
    if kind == 'legal':
        return LEGAL_ENTRIES
    live = '，'.join(_now(question, EMERGENCY))
    found: list[tuple[int, int]] = []
    for pattern, keys, _ in EMERGENCY_ENTRIES:
        if pattern.search(live):
            found += [k for k in keys if k not in found]
    return found[:3] or [(13, 1)]


def _first_action(kind: str, question: str, mainland: bool) -> str:
    if kind != 'emergency':
        return FIRST_ACTION[(kind, mainland)]
    live = '，'.join(_now(question, EMERGENCY))
    actions = {action for pattern, _, action in EMERGENCY_ENTRIES if pattern.search(live)}
    action = next((a for a in ACTION_ORDER if a in actions), 'call')
    return FIRST_ACTION[('emergency' if action == 'call' else action, mainland)]


def _process_note(question: str, chosen: list[dict], region: str) -> str | None:
    """The 「法律支持你」 note for this matter, or None when nothing goes to law."""
    legal = [e for e in chosen if e['section'] in (7, 8, 9, 19) and LAWSUIT_TITLE.search(e['title'])]
    if not (LAWSUIT.search(question) or legal):
        return None
    if region != '中国大陆':
        return ABROAD_PROCESS_NOTE
    labour = LABOUR.search(question) or (not LAWSUIT.search(question)
                                         and all(e['section'] in (7, 19) and LABOUR.search(e['title']) for e in legal))
    return LABOUR_NOTE if labour else PROCESS_NOTE


def _row(entry: dict, index: dict, region: str) -> dict:
    row = {'citation': citation(entry), 'section': entry['section'], 'number': entry['number'],
           'title': entry['title'], 'ratio': entry['ratio'], 'lens': entry['lens'], 'grade': entry['grade'],
           'costs': ls.tag_labels(entry), 'benefit_size': entry['cost_tags'].get('收益'),
           'fields': entry['fields'], 'region': entry['region']}
    if entry['region'] == '中国大陆' and region != '中国大陆':
        row['region_note'] = '中国大陆口径：你所在地的规定、机构和电话可能不同'
    if entry['disputed']:
        row['dispute'] = entry['dispute']
    if entry.get('errata'):
        row['errata'] = entry['errata']
    if entry['section'] in POLICY_SECTIONS:
        row['policy_note'] = POLICY_NOTE
    related = [index[tuple(r)] for r in entry.get('refs', []) if tuple(r) in index][:3]
    if related:
        row['related'] = [citation(e) + ' ' + e['title'] for e in related]
    return row


def decide(data: dict, question: str, payload: dict | None = None, limit: int = LIMIT) -> dict:
    """The rows and notes the answer is written from."""
    payload = payload or {}
    region = resolve_region(payload)['region']
    entries = data['entries']
    index = {(e['section'], e['number']): e for e in entries}
    result: dict = {'question': question, 'region': region, 'source': _source_line(data),
                    'do': [], 'dont': [], 'articles': [], 'notes': [], 'terms': [], 'sections': []}
    kind = stop_kind(question)
    if kind:
        # Hotlines are mainland numbers: say them only to someone there.
        mainland = region == '中国大陆'
        result['stop'] = {'kind': kind, 'first_action': _first_action(kind, question, mainland),
                          'entries': [_row(index[k], index, region) for k in _stop_entries(kind, question) if k in index]}
        result['not_in_book'] = False
        result['match'] = 'stop'
        return result
    sections = ls.sections_for(data['guide']['questions'], question)
    result['sections'] = [{'section': s, 'question': next(q['question'] for q in data['guide']['questions']
                                                           if q['section'] == s)} for s in sections]
    hits = ls.search(entries, question, sort='relevance', limit=40)
    # Entries in the matched sections fit better; keep the order otherwise.
    hits.sort(key=lambda r: (0 if r[0]['section'] in sections else 1, -r[2]))
    candidates = hits[:20]
    do = [r for r in candidates if r[0]['section'] != DONT_SECTION]
    dont = [r for r in candidates if r[0]['section'] == DONT_SECTION]
    chosen = _pick(do, limit)
    by_lens: dict[str, list[dict]] = {}
    for e, _, _ in chosen:
        by_lens.setdefault(e['lens'], []).append(_row(e, index, region))
    result['do'] = [{'lens': lens, 'entries': rows} for lens, rows in by_lens.items()]
    result['dont'] = [_row(e, index, region) for e, _, _ in sorted(dont, key=lambda r: ls.rank_key(r[0], r[2]))[:3]]
    result['not_in_book'] = not chosen and not dont
    result['match'] = 'none' if not candidates else candidates[0][1]
    shown = [e for e, _, _ in chosen + dont]
    result['uncovered'] = [p for p in ls.pieces(question) if shown and not _covered(p, shown)]
    keys = ls.pieces(question) + ls.book_words(ls.pieces(question))
    articles = [a for a in data['articles'] if any(k in a['title'].lower() for k in keys)]
    result['articles'] = [_article_row(a, question, region) for a in articles[:2]]
    if FOURTH_TIER.search(question):
        result['notes'].append(BENEFICIARY_NOTE)
    process = _process_note(question, [e for e, _, _ in chosen], region)
    if process:
        result['notes'].append(process)
    texts = [r['fields']['说人话'] + r['fields']['收益'] for g in result['do'] for r in g['entries']]
    result['terms'] = ls.glossary_terms(data['guide']['glossary'], texts)
    return result


def _pick(rows: list[tuple[dict, str, float]], limit: int) -> list[tuple[dict, str, float]]:
    """Up to ``limit`` rows, chosen within each 口径 and never across them.

    Inside a 口径: fit first in two bands, then the book's tier and grade. The
    口径 take turns, best fit first, so a 极高 in 换钱 never pushes out the
    best-fitting 换寿命 row (「总死亡率降 12%」 and 「每年省 500 元」 are not on one scale).
    """
    best = max((r[2] for r in rows), default=0)

    def band(r: tuple[dict, str, float]) -> int:
        return 0 if r[2] >= 0.75 * best else 1
    lenses: dict[str, list[tuple[dict, str, float]]] = {}
    for r in sorted(rows, key=lambda r: (band(r), *ls.rank_key(r[0], r[2]))):
        lenses.setdefault(r[0]['lens'], []).append(r)
    order = sorted(lenses, key=lambda lens: (band(lenses[lens][0]), -max(r[2] for r in lenses[lens])))
    chosen: list[tuple[dict, str, float]] = []
    while len(chosen) < limit and any(lenses[lens] for lens in order):
        for lens in order:
            if lenses[lens] and len(chosen) < limit:
                chosen.append(lenses[lens].pop(0))
    # Rows of one 口径 stay together, in that 口径's own order.
    return sorted(chosen, key=lambda r: order.index(r[0]['lens']))


def _first_steps(text: str, limit: int = 3) -> dict | None:
    """The article's first section of numbered steps: its heading and first items."""
    for block in re.split(r'\n(?=## )', text):
        if not block.startswith('## '):
            continue
        items = re.findall(r'^\d+\.\s*(.+)$', block, re.M)
        if items:
            return {'heading': block.split('\n', 1)[0][3:].strip(), 'items': items[:limit]}
    return None


def _article_row(article: dict, question: str, region: str) -> dict:
    row = {'id': article['id'], 'title': article['title'], 'region': article['region']}
    steps = _first_steps(article['text']) if FIRST_STEP.search(question) else None
    if steps:
        row['first_steps'] = steps
    if article['region'] == '中国大陆' and region != '中国大陆':
        row['region_note'] = '中国大陆口径：你所在地的规定、机构和电话可能不同'
    return row


def _covered(piece: str, shown: list[dict]) -> bool:
    """Whether a row shown holds half the piece, or the book's word for it."""
    words = ls.book_words([piece])
    return any(ls.coverage(e, piece) >= 0.5 or any(w in ls.hay(e) for w in words) for e in shown)


def _source_line(data: dict) -> str:
    source = data['source']
    return (f"出处：《高性价比人生指南》，eternity4719，{source['repo']}（提交 {source['commit'][:8]}，"
            f"{source['snapshot_date']}），正文按 {source['license']} 使用")


TERMS_SHOWN = 3


def _gist(row: dict, sentences: int = 2) -> str:
    """The first sentences of 说人话 as the book has them, and where the rest is.

    Cut only at a sentence end, so no number is split or changed.
    """
    text = row['fields']['说人话']
    parts = [p for p in text.split('。') if p]
    if len(parts) <= sentences:
        return text
    return '。'.join(parts[:sentences]) + f"。（全文见{row['citation'].split('（')[0]}）"


def render(result: dict) -> str:
    """Layer 2 of the answer: the rows, cited. The host writes the conclusion above it."""
    lines: list[str] = []
    stop = result.get('stop')
    if stop:
        # The first action is the first line: nothing above it.
        lines.append(stop['first_action'])
        lines += [f"- {r['citation']}：{r['fields']['说人话']}" for r in stop['entries']]
    if result['do']:
        lines.append('先做（每个口径内先看贴合程度，再按性价比和证据等级排）：')
    for group in result['do']:
        lines.append(f"{group['lens']}：")
        for r in group['entries']:
            tail = [f"性价比{r['ratio']}", f"证据等级 {r['grade']}", '、'.join(r['costs'])]
            if r.get('region_note'):
                tail.append(r['region_note'])
            lines.append(f"- {r['title']}——{r['citation']}，{'，'.join(t for t in tail if t)}。")
            lines.append(f"  {_gist(r)}")
            if r.get('dispute'):
                lines.append(f"  原书备注：「{r['dispute']}」")
            lines += [f"  {e['note']}" for e in r.get('errata', [])]
    if result['dont']:
        lines.append('别做 / 不用做（书里的反面清单）：')
        lines += [f"- {r['title']}——{r['citation']}，证据等级 {r['grade']}。" for r in result['dont']]
    if result['articles']:
        lines.append('相关长文：' + '；'.join(f"《{a['title']}》" for a in result['articles']))
        for a in result['articles']:
            if a.get('first_steps'):
                steps = a['first_steps']
                note = f"（{a['region_note']}）" if a.get('region_note') else ''
                lines.append(f"《{a['title']}》按时间排好了先后，第一段「{steps['heading']}」{note}：")
                lines += [f"  {i}. {item}" for i, item in enumerate(steps['items'], 1)]
    if result['not_in_book']:
        lines.append('书里没写：本库没有对得上的条目；可以给常识判断，但要标明那是常识，不是书里的内容。')
    elif result.get('uncovered'):
        lines.append('书里没写：' + '、'.join(f'「{p}」' for p in result['uncovered'])
                     + '这部分本库没有对得上的条目，上面的条目只管其余部分；这部分只能给常识判断并标明。')
    dated = [r['citation'].split('（')[0] for g in result['do'] for r in g['entries'] if r.get('policy_note')]
    if dated:
        # Said once for every row it concerns, not after each.
        lines.append(f"{'、'.join(dated)}：{POLICY_NOTE}")
    lines += result['notes']
    shown = '\n'.join(lines)
    terms = [t for t in result['terms'] if t['term'] in shown][:TERMS_SHOWN]
    if terms:
        # Only the terms the draft itself uses; the packet keeps them all.
        lines.append('术语：' + '；'.join(f"{t['term']}——{t['meaning']}" for t in terms))
    lines.append(result['source'])
    return '\n'.join(lines)
