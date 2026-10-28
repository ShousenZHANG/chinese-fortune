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

SENTENCE = re.compile(r'[^。！？!?；;\n]+')
QUOTED = re.compile(r'「[^」]*」|『[^』]*』|“[^”]*”|"[^"\n]*"')
REVERSAL = re.compile(r'但是|但|不过|可是|然而|却')
DENIAL = re.compile(r'不能说|不能讲|不能把|不能写|不能断言|不能保证|无法保证|不保证|没法保证|不敢说|不该说|不应说|不要说|别说'
                    r'|谈不上|不等于|不代表|并不意味|不是说|没有依据说|没依据说|不认为|不觉得|不认可|不同意|否认|不能直接说')
NEGATED_BEFORE = re.compile(r'(?:并非|不是|不算|没有|未必|谈不上|无法|不能|没法|[不非没未别])\s*$')
RETRACTED_AFTER = re.compile(r'不能成立|不成立|说不得|不能这么说|不能说死|是错误的|是错的|不对')

PILLAR = re.compile(rf'([年月日时時])柱\s*(?:是|为|為|已定为|定为|已定|就是|取|：|:)?\s*({GZ})')
SEQUENCE = re.compile(rf'(?:四柱|八字|命盘|排盘)[^。\n{STEM}]{{0,6}}({GZ})[、，,\s]*({GZ})[、，,\s]*({GZ})(?:[、，,\s]*({GZ}))?')
DAY_MASTER = re.compile(rf'日主\s*(?:是|为|為|：|:)?\s*([{STEM}])')

SCORES = (
    re.compile(r'(?<![点时：:\d.])\d+(?:\.\d+)?\s*分(?![钟之])'),
    re.compile(r'(?<=[打得是为給给有评拿])[零一二三四五六七八九十百两]{1,5}分(?![钟之])'),
    re.compile(r'(?:评分|打分|得分|分数|指数)\s*(?:是|为|為|：|:)?\s*\d+(?:\.\d+)?'),
)
CLOCK_BEFORE = re.compile(r'[点时]\s*$')
CLOCK_AFTER = re.compile(r'\s*(?:\d|秒)')
PERCENT = re.compile(r'\d+(?:\.\d+)?\s*[%％]|百分之[零一二三四五六七八九十百\d]+')
CHANCE = re.compile(r'机会|概率|几率|机率|可能|成功率|把握|准确率|命中率|胜算|匹配|契合|运势|录用|录取')

CERTAIN = re.compile(r'一定|肯定|必然|必定|注定|保证|百分之百|绝对|毫无疑问|必能|必会|稳了|铁定|板上钉钉')
OUTCOME = re.compile(r'录用|录取|offer|入职|上岸|通过|成功|发财|暴富|结婚|离婚|升职|升官|中奖|考上|怀孕|康复|好运|坏运'
                     r'|顺利|失败|破财|[吉凶灾]|生病|重病|去世|成格|破格|用神|喜用|应期|一帆风顺|贵人|脱单|复合', re.I)

GEJU_NAMES = ('正官', '七杀', '偏官', '正财', '偏财', '财', '正印', '偏印', '印绶', '印', '食神', '伤官',
              '阳刃', '羊刃', '建禄', '月劫', '禄劫')
HEDGE = re.compile(r'候选|待核|未定|尚未|未判|不能确定|无法确定|可能|或许|如果|若|还要核|还需核|倾向|暂')
TIE_STATUSES = {'tied_no_clause_separates', 'practical_tie'}
TIE_PICK = re.compile(r'最好的一天|最佳|首选|最吉|最好|最合适|最推荐|第一选择|唯一|胜过|优于|好过|强过|优先|其次|更好|更佳|首推|排第一')
TIE_KEPT = re.compile(r'并列|都可以|同样|没有先后|不分先后|任选|按你|看你|偏好|都行|等级相同')


def sentences(answer: str) -> Iterator[str]:
    """Sentences with quoted spans blanked, so indexes stay but quoted words never assert."""
    for match in SENTENCE.finditer(answer):
        text = match.group(0)
        yield QUOTED.sub(lambda m: '〇' * len(m.group(0)), text)


def asserted(sentence: str, start: int, end: int) -> bool:
    before = sentence[:start]
    if NEGATED_BEFORE.search(before[-3:]):
        return False
    scope = REVERSAL.split(before)[-1]
    if DENIAL.search(scope):
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
    """Every chart in the facts as {slot: 干支 or None, 'hour_known': bool}, any producer's shape."""
    found = []
    for node in _walk(facts):
        pillars = node.get('four_pillars')
        if isinstance(pillars, dict):
            found.append({**{slot: _ganzhi(pillars.get(slot)) for slot in ORDER},
                          'hour_known': node.get('hour_known', True) is not False})
    return found


def _finding(code: str, excerpt: str, detail: str) -> dict:
    return {'code': code, 'severity': 'error', 'excerpt': excerpt[:80], 'detail': detail}


def _table_pillars(answer: str) -> Iterator[tuple[str, str, str]]:
    """(slot, 干支, row) from Markdown tables whose header names the pillars."""
    rows = [line for line in answer.splitlines() if line.strip().startswith('|')]
    header: list[str | None] = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        slots = [next((SLOTS[ch] for ch in SLOTS if c.startswith(ch + '柱')), None) for c in cells]
        if any(slots):
            header = slots
            continue
        for slot, cell in zip(header, cells):
            match = re.search(GZ, cell)
            if slot and match:
                yield slot, match.group(0), row


def pillar_findings(answer: str, facts: list[dict], checked: dict) -> list[dict]:
    found = charts(facts)
    if not found:
        return []
    claims: list[tuple[str, str, str]] = list(_table_pillars(answer))
    findings: list[dict] = []
    master_findings: list[dict] = []
    masters = {c['day'][0] for c in found if c['day']}
    for sentence in sentences(answer):
        for match in PILLAR.finditer(sentence):
            if asserted(sentence, match.start(), match.end()):
                claims.append((SLOTS[match.group(1)], match.group(2), match.group(0)))
        for match in SEQUENCE.finditer(sentence):
            if asserted(sentence, match.start(), match.end()):
                claims += [(slot, gz, match.group(0)) for slot, gz in zip(ORDER, match.groups()) if gz]
        for match in DAY_MASTER.finditer(sentence):
            checked['pillars_checked'] += 1
            if masters and match.group(1) not in masters and asserted(sentence, match.start(), match.end()):
                master_findings.append(_finding('day_master_mismatch', match.group(0),
                                         f'工具结果为 {"/".join(sorted(masters))}'))
    for slot, ganzhi, excerpt in claims:
        checked['pillars_checked'] += 1
        if slot == 'hour' and not any(c['hour_known'] for c in found):
            findings.append(_finding('unknown_hour_pillar', excerpt, '出生时辰未知，工具没有给出时柱'))
        elif not any(c[slot] for c in found):
            findings.append(_finding('undecided_pillar', excerpt, '工具没有定下这一柱，只能说候选'))
        elif not any(c[slot] == ganzhi for c in found):
            findings.append(_finding('pillar_mismatch', excerpt,
                                     '工具结果为 ' + '/'.join(str(c[slot]) for c in found)))
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
        if (OUTCOME.search(rest) or OUTCOME.search(_last_scope(sentence[:match.start()])[-6:])) \
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
                re.compile(rf'(?:{names})格\s*(?:已经|已|就)?(?:成立|成格|已成|确定|定了|无疑)'))
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
    return any(node.get('status') in TIE_STATUSES or (isinstance(node.get('tied'), list) and len(node['tied']) > 1)
               for node in _walk(facts))


def tie_findings(sentence: str) -> list[dict]:
    scope = _last_scope(sentence)
    offset = len(sentence) - len(scope)
    if TIE_KEPT.search(scope):
        return []
    for match in TIE_PICK.finditer(scope):
        if asserted(sentence, offset + match.start(), offset + match.end()):
            return [_finding('tie_collapsed', sentence, '工具结果是并列，没有条款分出先后')]
    return []
