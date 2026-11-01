"""What an answer asserts, sentence by sentence, against the tool output.

A phrase only counts when the answer stands behind it. Quoted text, a claim
under a denial frame (不能说、无法保证、不认为…), a claim negated right before it
(不一定、并非最佳、不是财格) or retracted right after it (…这种断言不能成立) is not
an assertion. An earlier unrelated negative does not cancel a claim (你没有经验
也肯定能录用), and a reversal (但、不过、却) starts a fresh scope, so "虽然并列，
但A最好" is still a pick.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

STEM = '甲乙丙丁戊己庚辛壬癸'
BRANCH = '子丑寅卯辰巳午未申酉戌亥'
GZ = f'[{STEM}][{BRANCH}]'
SLOTS = {'年': 'year', '月': 'month', '日': 'day', '时': 'hour', '時': 'hour'}
ORDER = ('year', 'month', 'day', 'hour')

MOMENT_HEADER = re.compile(r'时刻|时间|日期|UTC|钟表|候选|假设|样例')
SENTENCE = re.compile(r'[^。！？!?；;\n]+')
QUOTED = re.compile(r'「[^」]*」|『[^』]*』|“[^”]*”|"[^"\n]*"')
REVERSAL = re.compile(r'但是|但|不过|可是|然而|却')
DENIAL = re.compile(r'不能说|不能讲|不能把|不能写|不能断言|不能保证|无法保证|不保证|没法保证|不敢说|不该说|不应说|不要说|别说'
                    r'|不会承诺|不承诺|不能承诺|无法承诺|不敢承诺|不打包票|没有给|没给|未给|没有排出|没排出'
                    r'|明确不出|工具不出|不出分|给不出|不给出|不打分|打不了|编不出|没法打|无法打|没有可以|没有能够|没有办法'
                    r'|不能据此断言|不能据此说|没有证据证明|没有证据说|无法证明|不能证明'
                    r'|谈不上|不等于|不代表|并不意味|不是说|没有依据说|没依据说|不认为|不觉得|不认可|不同意|否认|不能直接说')
NEGATED_BEFORE = re.compile(r'(?:并非|不是|不算|没有|未必|谈不上|无法|不能|没法|[不非没未别])\s*$')
DENIED_PREMISE = re.compile(r'不能(?:仅|单|只|光)?凭|不能因为|不能由|不能根据')
RETRACTED_AFTER = re.compile(r'不能成立|不成立|说不得|不能这么说|不能说死|是错误的|是错的|不对')

PILLAR = re.compile(rf'([年月日时時])柱\s*(?:是|为|為|已核定为|核定为|已确定为|确定为|已定为|定为|已定|就是|取|：|:)?\s*({GZ})')
# A birth hour stated as fact when the tool says the hour is unknown.
HOUR_CLAIM = re.compile(r'(?:出生时间|出生时刻|生时)\s*(?:就是|是|为|确定为|定为)[^，,。；;]{0,6}\d{1,2}\s*点'
                        r'|(?:确定|就是|定为)[^，,。；;]{0,2}[子丑寅卯辰巳午未申酉戌亥]时出生')
HEDGED_AFTER = re.compile(r'^[^，,。；;而但且和与及]{0,6}(?:候选|之一|待定|未定|尚未|假设|待核)')
SUBJECT = re.compile(r'(?<![A-Za-z])([AB])(?![A-Za-z])')
SEQUENCE = re.compile(rf'(?:四柱|八字|命盘|排盘)[^。\n{STEM}]{{0,6}}({GZ})[、，,\s]*({GZ})[、，,\s]*({GZ})(?:[、，,\s]*({GZ}))?')
DAY_MASTER = re.compile(rf'日主\s*(?:是|为|為|：|:)?\s*([{STEM}])')

SCORES = (
    # Not a clock list: 9:00/10:00/11:00 once matched 00/10 (round 7 R7-R2-DIAG-02).
    re.compile(r'(?<![\d.:：])\d{1,3}(?:\.\d+)?\s*/\s*(?:100|10)(?![\d.:：])'),
    re.compile(r'(?:机会|概率|几率|机率|可能性?)\s*(?:是|为|有)?\s*0?\.\d+'),
    re.compile(r'(?<![点时：:\d.])\d+(?:\.\d+)?\s*分(?![钟之])'),
    re.compile(r'(?<=[打得是为給给有评拿])[零一二三四五六七八九十百两]{1,5}分(?![钟之])'),
    re.compile(r'(?:评分|打分|得分|分数|指数)\s*(?:是|为|為|：|:)?\s*\d+(?:\.\d+)?'),
)
CLOCK_BEFORE = re.compile(r'(?:[点时]|[×*÷])\s*$')
CLOCK_AFTER = re.compile(r'\s*(?:\d|秒|多钟|多秒|/\s*度)')
PERCENT = re.compile(r'\d+(?:\.\d+)?\s*[%％]|百分之[零一二三四五六七八九十百\d]+')
CHANCE = re.compile(r'机会|概率|几率|机率|可能|[一-鿿]率|赢面|把握|胜算|匹配|契合|运势|录用|录取')

CERTAIN = re.compile(r'一定|肯定|必然|必定|注定|保证|百分之百|绝对|毫无疑问|必能|必会|稳了|铁定|板上钉钉')
OUTCOME = re.compile(r'录用|录取|offer|入职|上岸|通过|合格|及格|过关|获批|晋升|加薪|涨薪|痊愈|好转|成功|发财|暴富|结婚|离婚|升职|升官|中奖|考上|怀孕|康复|好运|坏运'
                     r'|顺利|失败|破财|[吉凶灾]|生病|重病|去世|成格|破格|用神|喜用|应期|一帆风顺|贵人|脱单|复合'
                     r'|幸福|美满|顺遂|长寿|平安|富贵', re.I)

GEJU_NAMES = ('正官', '七杀', '偏官', '正财', '偏财', '财', '正印', '偏印', '印绶', '印', '食神', '伤官',
              '阳刃', '羊刃', '建禄', '月劫', '禄劫')
PERSON = re.compile(r'你|您|他|她|对方|你们|他们')
FUTURE = re.compile(r'\s*(?:会|能|将|可以|得到|拿到|赚到|赚|获得|获|中|成为|过)')
HEDGE = re.compile(r'候选|待核|未定|尚未|未判|不能确定|无法确定|可能|或许|如果|若|还要核|还需核|倾向|暂')
TIE_STATUSES = {'tied_no_clause_separates', 'practical_tie', 'preferences_required'}
TIE_PICK = re.compile(r'最好的一天|最佳|首选|最吉|最好|最合适|最推荐|第一选择|唯一|胜过|优于|好过|强过|优先|其次|更好|更佳|首推|排第一'
                      r'|先选|次选|排出先后|高一个等级|低一个等级|比.{1,8}?(?:高|好|强|吉|优)|排名第[一二]|第一名')
TIE_KEPT = re.compile(r'并列|都可以|同样|没有先后|不分先后|任选|按你|看你|偏好|都行|等级相同|都保留'
                      r'|同一等级|同一个等级|二选一|分不出|不分高下|按自己'
                      # 「优先推荐这两个」 keeps both tied candidates (round 7 R7-R2-DIAG-03).
                      r'|这两个|这两天|这两段|这两处|两个都|两天都|二者|两者')
# 「书上说命贵人最吉」 reports a classical rule, not a ranking of the tied candidates
# (round 6 R2 S05 rewrote a correct answer three times over it). The exemption holds
# only while no date or candidate sits between the reporting verb and the word.
REPORTED = re.compile(r'(?:书上|书中|书里|原文|原书|协纪|古书|《[^》]{1,12}》)[^，。；！？]{0,4}?(?:说|云|曰|称|讲|写)')
CANDIDATE = re.compile(r'周[一二三四五六日天]|星期|\d+\s*[月日号点时]|[上下]午|晚上|早上|这天|那天|这一天|候选|时段|窗口')


def sentences(answer: str) -> Iterator[str]:
    """Sentences of the answer with quoted spans blanked first, so a 。 inside a quote cannot
    split it open and quoted words never assert."""
    masked = QUOTED.sub(lambda m: '〇' * len(m.group(0)), answer)
    for match in SENTENCE.finditer(masked):
        yield match.group(0)


def asserted(sentence: str, start: int, end: int) -> bool:
    before = sentence[:start]
    if NEGATED_BEFORE.search(before[-3:]):
        return False
    scope = REVERSAL.split(before)[-1]
    frames = list(DENIAL.finditer(scope))
    if frames:
        # The nearest frame governs the claim unless it already has its own object
        # before a clause break: 无法保证资料完整，你肯定会被录用 still promises.
        gap = scope[frames[-1].end():]
        delim = re.search(r'[，,；;]', gap)
        if delim is None or not gap[:delim.start()].strip(' ：:'):
            return False
    clauses = re.split(r'[，,；;]', scope)
    # 不能仅凭这一条，就断定必定富贵: the denied premise governs the 就 clause that follows it.
    if len(clauses) > 1 and re.match(r'\s*(?:就|便|则|也就)', clauses[-1]) and DENIED_PREMISE.search(clauses[-2]):
        return False
    after = REVERSAL.split(sentence[end:])[0]
    return not RETRACTED_AFTER.search(after)


def _last_scope(sentence: str) -> str:
    return REVERSAL.split(sentence)[-1]


def _walk(value: object) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _ganzhi(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get('ganzhi')
    return value if isinstance(value, str) and re.fullmatch(GZ, value) else None


def charts(facts: list[dict]) -> list[dict]:
    """Every chart in the facts as {slot: 干支 or None, 'hour_known', 'label'}, any producer's shape.

    pair_facts keys its two people A and B; the label keeps a claim about A from
    being satisfied by B's chart.
    """
    found: list[dict] = []

    def visit(value: object, label: str | None) -> None:
        if isinstance(value, dict):
            pillars = value.get('four_pillars')
            if isinstance(pillars, dict):
                found.append({**{slot: _ganzhi(pillars.get(slot)) for slot in ORDER},
                              'hour_known': value.get('hour_known', True) is not False, 'label': label})
            for key, item in value.items():
                visit(item, key if key in ('A', 'B') else label)
        elif isinstance(value, list):
            for item in value:
                visit(item, label)
    visit(facts, None)
    return found


def _subject_charts(found: list[dict], prefix: str) -> list[dict]:
    """The charts a claim is about: the last A/B named before it, else every chart."""
    named = SUBJECT.findall(prefix)
    chosen = [c for c in found if named and c['label'] == named[-1]]
    return chosen or found


def _finding(code: str, excerpt: str, detail: str) -> dict:
    return {'code': code, 'severity': 'error', 'excerpt': excerpt[:80], 'detail': detail}


def _table_pillars(answer: str) -> Iterator[tuple[str, str, str]]:
    """(slot, 干支, row) from Markdown tables whose own header row names the pillars."""
    tables: list[list[str]] = []
    previous_was_row = False
    for line in answer.splitlines():
        is_row = line.strip().startswith('|')
        if is_row:
            if previous_was_row:
                tables[-1].append(line)
            else:
                tables.append([line])
        previous_was_row = is_row
    for rows in tables:
        cells = [c.strip() for c in rows[0].strip().strip('|').split('|')]
        header = [next((SLOTS[ch] for ch in SLOTS if c.startswith(ch + '柱')), None) for c in cells]
        if not any(header) or any(MOMENT_HEADER.search(c) for c in cells):
            continue  # a table of moments or candidates compares times, not this birth chart
        found = [(slot, match.group(0), row) for row in rows[1:]
                 for slot, cell in zip(header, (c.strip() for c in row.strip().strip('|').split('|')))
                 if slot and (match := re.search(GZ, cell))]
        if all(len({gz for s2, gz, _ in found if s2 == slot}) <= 1 for slot in ORDER):
            yield from found


def pillar_findings(answer: str, facts: list[dict], checked: dict) -> list[dict]:
    found = charts(facts)
    if not found:
        return []
    claims: list[tuple[str, str, str, list[dict]]] = [(slot, gz, row, found) for slot, gz, row in _table_pillars(answer)]
    findings: list[dict] = []
    master_findings: list[dict] = []
    for sentence in sentences(answer):
        for match in PILLAR.finditer(sentence):
            if asserted(sentence, match.start(), match.end()) and not HEDGED_AFTER.search(sentence[match.end():]):
                claims.append((SLOTS[match.group(1)], match.group(2), match.group(0),
                               _subject_charts(found, sentence[:match.start()])))
        for match in SEQUENCE.finditer(sentence):
            if asserted(sentence, match.start(), match.end()):
                about = _subject_charts(found, sentence[:match.start()])
                claims += [(slot, gz, match.group(0), about) for slot, gz in zip(ORDER, match.groups()) if gz]
        if not any(c['hour_known'] for c in found):
            for match in HOUR_CLAIM.finditer(sentence):
                if asserted(sentence, match.start(), match.end()):
                    findings.append(_finding('unknown_hour_pillar', match.group(0), '出生时辰未知，不能把某个时刻说成已定'))
        for match in DAY_MASTER.finditer(sentence):
            checked['pillars_checked'] += 1
            if not asserted(sentence, match.start(), match.end()):
                continue
            about = _subject_charts(found, sentence[:match.start()])
            masters = {c['day'][0] for c in about if c['day']}
            if not masters:
                master_findings.append(_finding('undecided_pillar', match.group(0), '工具没有定下日柱，日主只能说候选'))
            elif match.group(1) not in masters:
                master_findings.append(_finding('day_master_mismatch', match.group(0),
                                                f'工具结果为 {"/".join(sorted(masters))}'))
    for slot, ganzhi, excerpt, about in claims:
        checked['pillars_checked'] += 1
        if slot == 'hour' and not any(c['hour_known'] for c in about):
            findings.append(_finding('unknown_hour_pillar', excerpt, '出生时辰未知，工具没有给出时柱'))
        elif not any(c[slot] for c in about):
            findings.append(_finding('undecided_pillar', excerpt, '工具没有定下这一柱，只能说候选'))
        elif not any(c[slot] == ganzhi for c in about):
            findings.append(_finding('pillar_mismatch', excerpt,
                                     '工具结果为 ' + '/'.join(str(c[slot]) for c in about)))
    return findings + master_findings


def score_findings(sentence: str, facts_text: str, checked: dict) -> list[dict]:
    findings = []
    hits = [m for pattern in SCORES for m in pattern.finditer(sentence)]
    hits += [m for m in PERCENT.finditer(sentence)
             if CHANCE.search(sentence[max(0, m.start() - 8):m.end() + 6])]
    for match in hits:
        if CLOCK_BEFORE.search(sentence[:match.start()]) or CLOCK_AFTER.match(sentence[match.end():]):
            continue  # 0 点 32 分, 前1分08秒: a time, not a score
        checked['scores_checked'] += 1
        text = match.group(0).replace(' ', '')
        known = text in facts_text or text.replace('％', '%') in facts_text
        if not known and asserted(sentence, match.start(), match.end()):
            findings.append(_finding('invented_score', sentence, '工具结果里没有这个分数或比例'))
            break
    return findings


def certainty_findings(sentence: str) -> list[dict]:
    for match in CERTAIN.finditer(sentence):
        rest = REVERSAL.split(sentence[match.end():])[0]
        clause = re.split(r'[，,；;：:]', _last_scope(sentence[:match.start()]))[-1]
        promise = bool(PERSON.search(clause) and FUTURE.match(rest))  # 你今年肯定获奖, 你一定会拿到投资
        if (promise or OUTCOME.search(rest) or OUTCOME.search(_last_scope(sentence[:match.start()])[-6:])) \
                and asserted(sentence, match.start(), match.end()):
            return [_finding('certainty_claim', sentence, '传统条款和工具结果不支持确定性的结果断言')]
    return []


def unresolved_titles(facts: list[dict]) -> list[str]:
    titles: list[str] = []
    for node in _walk(facts):
        review = node.get('geju_review')
        if isinstance(review, dict) and review.get('verdict') == 'unresolved':
            titles += [f['title'] for f in review.get('families', []) if isinstance(f, dict) and f.get('title')]
    return titles


def geju_findings(sentence: str, titles: list[str]) -> list[dict]:
    names = '|'.join(map(re.escape, sorted(set(titles) | set(GEJU_NAMES), key=len, reverse=True)))
    patterns = (re.compile(rf'(?:是|属于|属|为|為|定为|成|就是|取)\s*(?:{names})格'),
                re.compile(rf'(?:{names})格\s*(?:已经|已|就)?(?:成立|成格|已成|确定|定了|无疑)'),
                re.compile(rf'(?:已经|已)?(?:定格|成格|成立|确定)的\s*(?:{names})格'),
                re.compile(rf'(?:{names})格\s*(?:已经|已)?(?:败格|破格|成格)'),
                re.compile(r'格局(?:已定|已经确定|确定了|已成)|用神(?:已经|已)?确定为'))
    scope = _last_scope(sentence)
    offset = len(sentence) - len(scope)
    for pattern in patterns:
        for match in pattern.finditer(scope):
            if HEDGE.search(scope):
                return []
            if asserted(sentence, offset + match.start(), offset + match.end()):
                return [_finding('unresolved_settled', sentence, '工具格局结论为未判，只能说候选和待核条件')]
    return []


def has_tie(facts: list[dict]) -> bool:
    """Any producer's tie: a tie status, a tied list, ranking.ties, or no first choice yet for want of preferences."""
    return any(node.get('status') in TIE_STATUSES or node.get('ties') is True
               or (isinstance(node.get('tied'), list) and len(node['tied']) > 1)
               for node in _walk(facts))


def tie_findings(sentence: str) -> list[dict]:
    scope = _last_scope(sentence)
    offset = len(sentence) - len(scope)
    # 没有并列 denies the tie; only an affirmed tie keeps the choice open.
    if any(not NEGATED_BEFORE.search(scope[:m.start()][-3:]) for m in TIE_KEPT.finditer(scope)):
        return []
    for match in TIE_PICK.finditer(scope):
        said = list(REPORTED.finditer(scope[:match.start()]))
        if said and not CANDIDATE.search(scope[said[-1].end():match.start()]):
            continue
        # 「最好选周二上午或周四」 names two candidates, which is the tie kept, not collapsed.
        after = scope[match.end():]
        if len(CANDIDATE.findall(after)) >= 2 and re.search(r'或|和|与|、|及', after):
            continue
        if asserted(sentence, offset + match.start(), offset + match.end()):
            return [_finding('tie_collapsed', sentence, '工具结果是并列，没有条款分出先后')]
    return []
