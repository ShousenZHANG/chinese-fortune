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
# An emergency in progress, described the way people describe it.
EMERGENCY = re.compile(r'倒地|没呼吸|没有呼吸|心跳停|大出血|血止不住|流血不止|着火|火灾|失火|溺水|落水|触电|中毒|误服|'
                       r'喝了农药|吃错药|卒中|中风|嘴歪|半边身子|半身不能动|一侧没劲|心梗|胸口压着疼|胸口剧痛|胸痛|'
                       r'抽搐|噎住|喘不上气|呼吸困难|昏迷|叫不醒|过敏性休克|一氧化碳')
# What turns those words into something else: insurance, prevention, a
# hypothetical, a forecast. 「中风险理财」「火灾险」「怎么预防心梗」「六爻看我会不会中风」.
NOT_NOW = re.compile(r'险|预防|防止|防溺|怎么防|会不会|可能会|以后|将来|如果|万一|'
                     r'八字|命里|命理|命盘|运势|流年|大运|紫微|斗数|六爻|起卦|算一|算算|卦|塔罗|星座|风水')
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
# Reviewed entries for each stop, by what is happening. Tests check that each
# number still holds the expected title, so a renumbering cannot slip through.
EMERGENCY_ENTRIES: list[tuple[re.Pattern, list[tuple[int, int]]]] = [
    (re.compile(r'着火|火灾|失火'), [(13, 24)]),
    (re.compile(r'一氧化碳|煤气'), [(13, 19)]),
    (re.compile(r'嘴歪|一侧没劲|半边身子|半身不能动|说话说不清|中风|卒中'), [(13, 3), (13, 4)]),
    (re.compile(r'胸口压着疼|胸口剧痛|胸痛|心梗'), [(13, 7), (13, 8)]),
    (re.compile(r'大出血|血止不住|流血不止'), [(13, 12)]),
    (re.compile(r'溺水|落水'), [(13, 25)]),
    (re.compile(r'触电'), [(13, 18)]),
    (re.compile(r'中毒|误服|喝了农药|吃错药'), [(13, 20)]),
    (re.compile(r'噎住'), [(13, 26), (13, 43)]),
    (re.compile(r'过敏性休克|全身起疹'), [(13, 15)]),
    (re.compile(r'抽搐'), [(13, 16)]),
    (re.compile(r'喘不上气|呼吸困难'), [(13, 15), (13, 11)]),
    (re.compile(r'倒地|没呼吸|没有呼吸|心跳停|昏迷|叫不醒'), [(13, 1), (13, 2)]),
]
CRISIS_ENTRIES = [(1, 25), (1, 32), (29, 11)]
LEGAL_ENTRIES = [(8, 5), (8, 20)]
FIRST_ACTION = {
    ('emergency', True): '先打 120（着火打 119），照下面第 13 节的条目做现场第一个动作，别先讲性价比。',
    ('emergency', False): '先打你所在地的急救电话，照下面第 13 节的条目做现场第一个动作，别先讲性价比；条目里的 120 是中国大陆的号码。',
    ('crisis', True): '先打全国心理援助热线 12356（未成年人 12355），再看下面第 1 节和第 29 节的条目；不做劝导式分析，不评价动机。',
    ('crisis', False): '先按你所在地的官方心理危机援助信息求助，有即时危险就打当地急救电话；下面的条目里的号码是中国大陆的。'
                       '不做劝导式分析，不评价动机。',
    ('legal', True): '先看下面第 8 节的条目；书只给通用口径，个案要找律师。',
    ('legal', False): '先看下面第 8 节的条目；它们是中国大陆的法律口径，书只给通用说法，个案要找你所在地的律师。',
}
BENEFICIARY_NOTE = ('这件事的好处落在第 ④ 档（陌生人，或替人担保、帮人转账）：好处和风险要一起写——'
                    '被讹、被卷进案子、被报复，不能只写好处，也不能写成一律别管。')
# The workflow's own rule for 「法律支持你」 (skills/life-decision-guide).
PROCESS_NOTE = ('「法律支持你」的事连过程成本一起说：要不要打官司、大概多久（一审普通程序 6 个月起、可延长，'
                '简易程序 3 个月）、律师费谁掏（律师费不在诉讼费用里，败诉方负担不包括它）。')
POLICY_NOTE = '政策会变：这一节的金额、时限、名单写了截至日期，答复里带上日期，并提醒去官方渠道自查。'


def citation(entry: dict) -> str:
    """「第 8 节第 18 条（借钱写清借条）」: the parenthesis is the title's first
    clause, whole; a long one drops its own parenthetical, never cut mid-word."""
    clause = re.split(r'[，：；,:]', entry['title'])[0]
    if len(clause) > 20:
        clause = re.sub(r'（[^）]*）|\([^)]*\)', '', clause) or clause
    return f"第 {entry['section']} 节第 {entry['number']} 条（{clause}）"


def stop_kind(question: str) -> str | None:
    """'crisis', 'emergency' or 'legal' when the question describes one now.

    A suicidal thought always counts. An emergency or a legal process does
    not when the question is about insurance, prevention, a hypothetical or
    a forecast (「火灾险」「会不会被起诉」「六爻看我会不会中风」).
    """
    if CRISIS.search(question):
        return 'crisis'
    if NOT_NOW.search(question):
        return None
    if EMERGENCY.search(question):
        return 'emergency'
    if LEGAL.search(question):
        return 'legal'
    return None


def _stop_entries(kind: str, question: str) -> list[tuple[int, int]]:
    if kind == 'crisis':
        return CRISIS_ENTRIES
    if kind == 'legal':
        return LEGAL_ENTRIES
    found: list[tuple[int, int]] = []
    for pattern, keys in EMERGENCY_ENTRIES:
        if pattern.search(question):
            found += [k for k in keys if k not in found]
    return found[:3] or [(13, 1)]


def _row(entry: dict, index: dict, region: str) -> dict:
    row = {'citation': citation(entry), 'section': entry['section'], 'number': entry['number'],
           'title': entry['title'], 'ratio': entry['ratio'], 'lens': entry['lens'], 'grade': entry['grade'],
           'costs': ls.tag_labels(entry), 'benefit_size': entry['cost_tags'].get('收益'),
           'fields': entry['fields'], 'region': entry['region']}
    if entry['region'] == '中国大陆' and region != '中国大陆':
        row['region_note'] = '中国大陆口径：你所在地的规定、机构和电话可能不同'
    if entry['disputed']:
        row['dispute'] = entry['dispute']
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
        result['stop'] = {'kind': kind, 'first_action': FIRST_ACTION[(kind, mainland)],
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
    best = max((r[2] for r in do), default=0)
    do.sort(key=lambda r: (0 if r[2] >= 0.75 * best else 1, *ls.rank_key(r[0], r[2])))
    chosen = do[:limit]
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
    result['articles'] = [{'id': a['id'], 'title': a['title'], 'region': a['region']} for a in articles[:2]]
    if FOURTH_TIER.search(question):
        result['notes'].append(BENEFICIARY_NOTE)
    if LAWSUIT.search(question) or any(e['section'] in (7, 8, 9, 19) and LAWSUIT_TITLE.search(e['title'])
                                       for e, _, _ in chosen):
        result['notes'].append(PROCESS_NOTE)
    texts = [r['fields']['说人话'] + r['fields']['收益'] for g in result['do'] for r in g['entries']]
    result['terms'] = ls.glossary_terms(data['guide']['glossary'], texts)
    return result


def _covered(piece: str, shown: list[dict]) -> bool:
    """Whether a row shown holds half the piece, or the book's word for it."""
    words = ls.book_words([piece])
    return any(ls.coverage(e, piece) >= 0.5 or any(w in ls.hay(e) for w in words) for e in shown)


def _source_line(data: dict) -> str:
    source = data['source']
    return (f"出处：《高性价比人生指南》，eternity4719，{source['repo']}（提交 {source['commit'][:8]}，"
            f"{source['snapshot_date']}），正文按 {source['license']} 使用")


def render(result: dict) -> str:
    """Layer 2 of the answer: the rows, cited. The host writes the conclusion above it."""
    lines: list[str] = []
    stop = result.get('stop')
    if stop:
        lines.append('先停下：' + stop['first_action'])
        lines += [f"- {r['citation']}：{r['fields']['说人话']}" for r in stop['entries']]
    for group in result['do']:
        lines.append(f"先做（{group['lens']}；先看贴合程度，再按性价比和证据等级排）：")
        for r in group['entries']:
            tail = [f"性价比{r['ratio']}", f"证据等级 {r['grade']}", '、'.join(r['costs'])]
            if r.get('region_note'):
                tail.append(r['region_note'])
            lines.append(f"- {r['title']}——{r['citation']}，{'，'.join(t for t in tail if t)}。")
            lines.append(f"  {r['fields']['说人话']}")
            if r.get('dispute'):
                lines.append(f"  原书备注：「{r['dispute']}」")
            if r.get('policy_note'):
                lines.append(f"  {r['policy_note']}")
    if result['dont']:
        lines.append('别做 / 不用做（书里的反面清单）：')
        lines += [f"- {r['title']}——{r['citation']}，证据等级 {r['grade']}。" for r in result['dont']]
    if result['articles']:
        lines.append('相关长文：' + '；'.join(f"《{a['title']}》" for a in result['articles']))
    if result['not_in_book']:
        lines.append('书里没写：本库没有对得上的条目；可以给常识判断，但要标明那是常识，不是书里的内容。')
    elif result.get('uncovered'):
        lines.append('书里没写：' + '、'.join(f'「{p}」' for p in result['uncovered'])
                     + '这部分本库没有对得上的条目，上面的条目只管其余部分；这部分只能给常识判断并标明。')
    lines += result['notes']
    if result['terms']:
        lines.append('术语：' + '；'.join(f"{t['term']}——{t['meaning']}" for t in result['terms']))
    lines.append(result['source'])
    return '\n'.join(lines)
