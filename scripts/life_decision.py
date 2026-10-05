"""Answer a real-life decision from 《高性价比人生指南》, the book's way.

A port of the book's own decision workflow (skills/life-decision-guide at the
pinned commit, CC BY 4.0) onto the frozen library:

0. Stop first for an emergency in progress, a suicidal thought, or a legal
   process already under way; give the first action, not a ranking.
1. Find the sections whose README question matches, then the entries.
2. Rank the book's way: 性价比 tier, then evidence grade, then fit; never
   across 口径 (寿命, 钱, 时间精力, 人身自由 are not traded for each other).
3. Return 先做 (ranked, per 口径), 别做 (the book's 反面清单 entries that
   match), and 书里没写 when nothing matches; every row cites its section and
   entry, keeps its full fields, and carries the notes the workflow requires.

Nothing here writes the one-sentence conclusion: that is the host's, from
these rows, under references/29-life-decision.md.
"""
from __future__ import annotations

import re

import life_search as ls
from region import resolve_region

LIMIT = 7
EMERGENCY = re.compile(r'倒地|没呼吸|没有呼吸|心跳停|大出血|血止不住|着火|火灾|溺水|落水|触电|中毒|误服|喝了农药|'
                       r'卒中|中风|嘴歪|心梗|胸口压着疼|抽搐|噎住|喘不上气|呼吸困难|昏迷|叫不醒|过敏性休克')
CRISIS = re.compile(r'自杀|不想活|活不下去|轻生|想死|结束生命|割腕|跳楼')
LEGAL = re.compile(r'被传唤|被拘留|被刑拘|被起诉|被抓|被立案|被逮捕|收到传票|收到起诉状|派出所叫我')
# The book's fourth tier of whom a benefit lands on: strangers, and standing
# surety or moving money for someone.
FOURTH_TIER = re.compile(r'陌生人|路人|替人担保|替朋友担保|帮人担保|帮朋友担保|担保|帮人转账|帮人收款|救人|扶老人|见义勇为')
LAWSUIT = re.compile(r'起诉|打官司|仲裁|告他|告公司|索赔|赔偿|维权|讨薪|要回')
# Sections whose amounts, time limits and lists carry a cut-off date.
POLICY_SECTIONS = frozenset({7, 19, 21, 24, 31, 32})
DONT_SECTION = 6
STOPS = {
    'emergency': ({13}, '先打 120（着火打 119），按第 13 节的条目做现场第一个动作，别先讲性价比。'),
    'crisis': ({1, 29}, '先打全国心理援助热线 12356，再看第 1 节和第 29 节的条目；不做劝导式分析，不评价动机。'),
    'legal': ({8}, '先看第 8 节对应的条目；书只给通用口径，个案要找律师。'),
}
ABROAD_STOP = '这几个号码是中国大陆的；你不在中国大陆，就按所在地的官方急救和危机援助信息求助。'
BENEFICIARY_NOTE = ('这件事的好处落在第 ④ 档（陌生人，或替人担保、帮人转账）：好处和风险要一起写——'
                    '被讹、被卷进案子、被报复，不能只写好处，也不能写成一律别管。')
# The workflow's own rule for 「法律支持你」 (skills/life-decision-guide).
PROCESS_NOTE = ('「法律支持你」的事连过程成本一起说：要不要打官司、大概多久（一审普通程序 6 个月起、可延长，'
                '简易程序 3 个月）、律师费谁掏（律师费不在诉讼费用里，败诉方负担不包括它）。')
POLICY_NOTE = '政策会变：这一节的金额、时限、名单写了截至日期，答复里带上日期，并提醒去官方渠道自查。'


def citation(entry: dict) -> str:
    """「第 8 节第 18 条（借钱写清借条）」: the parenthesis is the title's first clause."""
    anchor = re.split(r'[，：；,:]', entry['title'])[0][:14]
    return f"第 {entry['section']} 节第 {entry['number']} 条（{anchor}）"


def _stop(question: str) -> str | None:
    for kind, pattern in (('emergency', EMERGENCY), ('crisis', CRISIS), ('legal', LEGAL)):
        if pattern.search(question):
            return kind
    return None


def _row(entry: dict, data: dict, payload: dict, region: str) -> dict:
    index = {(e['section'], e['number']): e for e in data['entries']}
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
    result: dict = {'question': question, 'region': region}
    stop = _stop(question)
    if stop:
        stop_sections, first = STOPS[stop]
        hits = ls.search(entries, question, {'section': stop_sections}, sort='relevance', limit=3) or \
            ls.search(entries, '', {'section': stop_sections}, sort='ratio', limit=3)
        result['stop'] = {'kind': stop, 'first_action': first,
                          'entries': [_row(e, data, payload, region) for e, _, _ in hits]}
        if stop in ('emergency', 'crisis') and region != '中国大陆':
            result['stop']['region_note'] = ABROAD_STOP
    sections = ls.sections_for(data['guide']['questions'], question)
    result['sections'] = [{'section': s, 'question': next(q['question'] for q in data['guide']['questions']
                                                           if q['section'] == s)} for s in sections]
    hits = ls.search(entries, question, sort='relevance', limit=40)
    # Entries in the matched sections fit better; keep the order otherwise.
    hits.sort(key=lambda r: (0 if r[0]['section'] in sections else 1, -r[2]))
    candidates = hits[:20]
    do = [r for r in candidates if r[0]['section'] != DONT_SECTION]
    dont = [r for r in candidates if r[0]['section'] == DONT_SECTION]
    # The book ranks the entries that fit; an automatic search also finds ones
    # that merely mention the topic. So fit comes first in two bands (close to
    # the best match, then the rest), and within a band the book's order:
    # 性价比 tier, then evidence grade.
    best = max((r[2] for r in do), default=0)
    do.sort(key=lambda r: (0 if r[2] >= 0.75 * best else 1, *ls.rank_key(r[0], r[2])))
    chosen = do[:limit]
    by_lens: dict[str, list[dict]] = {}
    for e, _, _ in chosen:
        by_lens.setdefault(e['lens'], []).append(_row(e, data, payload, region))
    result['do'] = [{'lens': lens, 'entries': rows} for lens, rows in by_lens.items()]
    result['dont'] = [_row(e, data, payload, region) for e, _, _ in sorted(dont, key=lambda r: ls.rank_key(r[0], r[2]))[:3]]
    result['not_in_book'] = not chosen and not dont and not stop
    result['match'] = 'none' if not candidates else candidates[0][1]
    keys = ls.pieces(question) + ls.book_words(ls.pieces(question))
    articles = [a for a in data['articles'] if any(k in a['title'].lower() for k in keys)]
    result['articles'] = [{'id': a['id'], 'title': a['title'], 'region': a['region']} for a in articles[:2]]
    notes = []
    if FOURTH_TIER.search(question):
        notes.append(BENEFICIARY_NOTE)
    if LAWSUIT.search(question) or any(e['section'] in (8, 9, 19) for e, _, _ in chosen if LAWSUIT.search(e['title'])):
        notes.append(PROCESS_NOTE)
    result['notes'] = notes
    texts = [r['fields']['说人话'] + r['fields']['收益'] for g in result['do'] for r in g['entries']]
    result['terms'] = ls.glossary_terms(data['guide']['glossary'], texts)
    return result


def render(result: dict) -> str:
    """Layer 2 of the answer: the rows, cited. The host writes the conclusion above it."""
    lines: list[str] = []
    stop = result.get('stop')
    if stop:
        lines.append('先停下：' + stop['first_action'] + (stop.get('region_note') or ''))
        lines += [f"- {r['citation']}：{r['fields']['说人话']}" for r in stop['entries']]
    for group in result['do']:
        lines.append(f"先做（{group['lens']}，按性价比和证据等级排）：")
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
    lines += result['notes']
    if result['terms']:
        lines.append('术语：' + '；'.join(f"{t['term']}——{t['meaning']}" for t in result['terms']))
    return '\n'.join(lines)
