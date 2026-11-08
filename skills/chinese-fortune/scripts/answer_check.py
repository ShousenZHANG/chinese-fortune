"""Mechanical check of a finished answer against the tool output behind it.

reading_support.review_claims audits a structured claims packet; hosts mostly
write prose, so this reads the prose itself. Quotations must exist in the
frozen books, named pillars must match the chart, scores the tool never gave
must not appear, and conditions the tool left open must not come back as
certainties or as a single best choice. A clean result is the floor, not a
review: whether the reasoning holds still needs a semantic reader.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from answer_assertions import (
    certainty_findings,
    geju_findings,
    has_tie,
    pillar_findings,
    score_findings,
    sentences,
    tie_findings,
    unresolved_titles,
)
from answer_evidence import PillarEvidence, assertion_facts, parse_evidence
from classical_search import get_passage, iter_passages, normalized
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
# Text assets a host may quote: hexagram texts and the rule files' own
# excerpts. Lookup tables are not quotable.
QUOTABLE_ASSETS = ('64hex', 'classical_evidence', 'luck_rules',
                   'geju_rules', 'tiaohou', 'method_rules', 'bazi_rules', 'shensha', 'hehun_clauses', 'liuyao_rules')
ASSET_TITLES = {'64hex': '周易'}

# Bracket quotes may wrap lines; ASCII pairs stay on one line. Markdown block
# quotes count as quotations when a source cue or title introduces them.
QUOTE = re.compile(r'「([^「」]{2,400})」|『([^『』]{2,400})』|“([^“”]{2,400})”|"([^"\n]{2,240})"')
BLOCK = re.compile(r'(?m)^[ \t]*>[ \t]?(.+)$')
HAN = re.compile(r'[一-鿿]')
ELLIPSIS = re.compile(r'……|…|\.{3,}|⋯+')
TITLE_BEFORE = re.compile(r'《([^》]{1,16})》[^「『“"。！？]{0,40}$')
# A cited passage id (ditian:c016:p0001) is the strongest cue there is: the quote
# must then be in that very passage.
PASSAGE_REF = re.compile(r'([a-z]+:c\d{3}:p\d{4})[^「『“"。！？]{0,24}$')
PASSAGE_REF_AFTER = re.compile(r'^[^「『“"\n]{0,16}?([a-z]+:c\d{3}:p\d{4})')
NEGATOR = re.compile(r'[不無无非勿莫未弗毋]')
MODALS = set('可能得宜必敢會会須须當当應应以')
# 「最忌見傷」截成「見傷」：删掉忌、畏一类动词，同样把意思反过来。
AVOID_VERBS = set('忌畏怕嫌惡恶戒禁')
# A quote the answer itself says the books do not contain is being refuted, not cited.
QUOTE_DENIED_BEFORE = re.compile(r'(?:不是|并非|而非|并不是|不等于|远不是|而不是)\s*$')
QUOTE_REFUTED = re.compile(r'找不到|查不到|没查到|搜不到|检索不到|没有这句|并无此|并无这|不是原文|没有找到|未见|不存在')
TITLE_AFTER = re.compile(r'^[\s—\-－–、，,：:）)]{0,4}(?:出自|见于|见|语出)?\s*《([^》]{1,16})》')
CUE_BEFORE = re.compile(r'(原文|古籍|古书|书中|書中|书上|书里|有云|云|曰|有言|条文|口诀|卦辞|爻辞|载|記載|记载)'
                        r'(?:里|中|上)?(?:说|讲|道|写|写道|写着|载|记载|是|为)?\s*[:：，,]?\s*$')
CLASSICAL = set('之乎者也焉矣兮曰爲為於則')
# Transcription markers: commentary brackets and rare glyphs written as
# 〔字形SKnnnn：字〕. A quote reads through them, so the match key drops them.
GLYPH = re.compile(r'〔字形[^：〕]*：([^〕未])〕')
MARKER = re.compile(r'〔[^〕]*〕')

BOUNDARY = '机械检查：通过只说明没发现这几类硬错误，不等于推理和解释正确；语义仍需复核。'


def _key(text: str) -> str:
    return re.sub(r'[\W_]', '', normalized(text))


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


@cache
def _corpus() -> tuple[tuple[str, str, str], ...]:
    """(title key, locator, text key) for every quotable paragraph, section and chapter title."""
    rows: list[tuple[str, str, str]] = []
    headings: set[tuple[str, str]] = set()
    for book, chapter_title, passage in iter_passages():
        title = _key(book['title'])
        rows.append((title, passage['passage_id'], _key(MARKER.sub('', GLYPH.sub(r'\1', passage['text'])))))
        headings |= {(title, chapter_title), (title, passage.get('section') or '')}
    rows += [(title, 'heading', _key(text)) for title, text in headings if text]
    for name in QUOTABLE_ASSETS:
        data = json.loads((ASSETS / f'{name}.json').read_text(encoding='utf-8'))
        title = _key(ASSET_TITLES.get(name, name))
        rows += [(title, f'assets/{name}.json', _key(s)) for s in _strings(data) if len(s) >= 4]
    return tuple(rows)


@cache
def _library_titles() -> frozenset[str]:
    return frozenset(title for title, _, _ in _corpus())


def _in_order(parts: list[str], text: str) -> bool:
    start = 0
    for part in parts:
        found = text.find(part, start)
        if found < 0:
            return False
        start = found + len(part)
    return True


def _flips(cut: str) -> bool:
    """The text cut away right before a kept part ends on 不/無…, 不可/不可以, or 忌/畏."""
    if not cut:
        return False
    if cut[-1] in AVOID_VERBS:
        return True
    i = len(cut)
    while i > 0 and len(cut) - i < 2 and cut[i - 1] in MODALS:
        i -= 1
    return i > 0 and bool(NEGATOR.fullmatch(cut[i - 1]))


def _drops_negator(parts: list[str], text: str) -> bool:
    """An elision whose cut ends right on 不/無/非…: 「人道得之，……過也」 drops 不可 and reverses the sentence."""
    start = text.find(parts[0])
    if start < 0:
        return False
    end = start + len(parts[0])
    for part in parts[1:]:
        found = text.find(part, end)
        if found < 0:
            return False
        if _flips(text[max(end, found - 3):found]):
            return True
        end = found + len(part)
    return False


SHORT_GAP_CONSEQUENCE = re.compile(r'^(?:则|則|便|方|乃|即|始|斯|无不|無不)')
SENTENCE_END = re.compile(r'[。！？；]')


def _drops_short_condition(parts: list[str], text: str) -> bool:
    start = text.find(parts[0])
    if start < 0:
        return False
    end = start + len(parts[0])
    for part in parts[1:]:
        found = text.find(part, end)
        if found < 0:
            return False
        gap = text[end:found]
        if gap and len(gap) <= 24 and not SENTENCE_END.search(gap) and SHORT_GAP_CONSEQUENCE.match(part):
            return True
        end = found + len(part)
    return False


def _truncates_negator(first: str, text: str) -> bool:
    """「可逢合」 cut from 「不可逢合」: the quote starts on a modal right after a negator, and that is
    the only place the book has it."""
    if not first or first[0] not in MODALS:
        return False
    spots = [m.start() for m in re.finditer(re.escape(first), text)]
    return bool(spots) and all(NEGATOR.fullmatch(text[s - 1:s] or ' ') for s in spots)


def _passage_corpus(passage_id: str) -> tuple[tuple[str, str, str], ...]:
    try:
        passage = get_passage(passage_id)
    except ValueError:
        return ()
    title = _key(passage['book_title'])
    return tuple((title, passage_id, _key(MARKER.sub('', GLYPH.sub(r'\1', text))))
                 for text in (passage['text'], passage.get('section'), passage.get('chapter_title')) if text)


def _title_matches(cited: str, title: str) -> bool:
    return bool(cited) and (cited in title or title in cited)


def _quotes(answer: str) -> Iterator[tuple[str, str, str]]:
    """(quote, text before it, text after it) for bracket, ASCII and block quotations."""
    for match in QUOTE.finditer(answer):
        quote = next(group for group in match.groups() if group)
        yield quote, answer[max(0, match.start() - 60):match.start()], answer[match.end():match.end() + 40]
    groups: list[list[re.Match[str]]] = []
    for line in BLOCK.finditer(answer):
        if groups and line.start() == groups[-1][-1].end() + 1:
            groups[-1].append(line)
        else:
            groups.append([line])
    for group in groups:
        first, last = group[0], group[-1]
        yield (''.join(m.group(1) for m in group), answer[max(0, first.start() - 60):first.start()],
               answer[last.end():last.end() + 24])


def _quote_findings(answer: str, checked: dict) -> list[dict]:
    findings = []
    for quote, before, after in _quotes(answer):
        right_after = re.split(r'[。！？!?\n]', after, maxsplit=1)[0][:16]
        if QUOTE_REFUTED.search(right_after) or QUOTE_REFUTED.search(before[-20:]) or QUOTE_DENIED_BEFORE.search(before):
            checked['quotes_skipped'] += 1
            continue
        title = TITLE_BEFORE.search(before) or TITLE_AFTER.search(after)
        cited_passage = PASSAGE_REF.search(before) or PASSAGE_REF_AFTER.search(after)
        cued = bool(title or cited_passage or CUE_BEFORE.search(before))
        han = len(HAN.findall(quote))
        if not (cued and han >= 4) and not (han >= 6 and len(CLASSICAL & set(quote)) >= 2):
            checked['quotes_skipped'] += 1
            continue
        checked['quotes_checked'] += 1
        cited_name = title.group(1) if title else ''
        cited = _key(cited_name)
        passage_id = cited_passage.group(1) if cited_passage else ''
        passage_rows = _passage_corpus(passage_id) if passage_id else ()
        known = any(_title_matches(cited, t) for t in _library_titles())
        if cited and not known:
            if passage_rows:
                findings.append(_finding('misattributed_quote', 'error', quote,
                                         f'所引段落 {passage_id} 不属于《{cited_name}》'))
            else:
                findings.append(_finding('quote_outside_library', 'warning', quote,
                                         f'《{cited_name}》不在随包古籍内，无法核对原文'))
            continue
        corpus = _corpus() + passage_rows
        terms = [_key(x) for x in quote.split('、')]
        if len(terms) > 1 and all(0 < len(t) <= 4 for t in terms):
            # 「修造、用事」 lists terms the book uses, not one continuous sentence.
            hits = [(t, loc, text) for t, loc, text in corpus if all(term in text for term in terms)]
            parts = terms
        else:
            parts = [p for p in (_key(x) for x in ELLIPSIS.split(quote)) if p]
            hits = [(t, loc, text) for t, loc, text in corpus if _in_order(parts, text)]
        sources = [(loc, text) for t, loc, text in hits
                   if (not cited or _title_matches(cited, t)) and (not passage_id or loc == passage_id)]
        elided = len(parts) > 1 and bool(ELLIPSIS.search(quote))
        cut = next((loc for loc, text in sources if elided and _drops_negator(parts, text)), None)
        condition = next((loc for loc, text in sources if elided and _drops_short_condition(parts, text)), None)
        truncated = sources and all(_truncates_negator(parts[0], text) for _, text in sources)
        if cut:
            findings.append(_finding('elision_drops_negation', 'error', quote,
                                     f'省略号删掉了 {cut} 原文紧挨着保留部分的否定字，意思被反过来了'))
        elif truncated:
            findings.append(_finding('elision_drops_negation', 'error', quote,
                                     f'引文开头截掉了 {sources[0][0]} 原文紧挨着的否定字，意思被反过来了'))
        elif condition:
            findings.append(_finding('elision_drops_condition', 'error', quote,
                                     f'省略号删掉了 {condition} 原文里结论前的条件，条件句变成了无条件的说法'))
        elif hits and passage_id and not sources:
            findings.append(_finding('misattributed_quote', 'error', quote,
                                     f'所引段落 {passage_id} 与所署书名未能共同核对这段原文'))
        elif hits and cited and not sources:
            findings.append(_finding('misattributed_quote', 'error', quote, f'原文在 {hits[0][1]}，不在《{cited_name}》'))
        elif not hits:
            findings.append(_finding('unverified_quote', 'error', quote, '随包古籍内找不到这段原文'))
        elif not cited and not passage_id:
            # R3 S21: 「原文是『不可逢合』」 with neither book nor passage id cannot be located by the reader.
            findings.append(_finding('quote_without_source', 'error', quote,
                                     f'原文在 {hits[0][1]}：引文旁写出书名和段号'))
    return findings


def _finding(code: str, severity: str, excerpt: str, detail: str) -> dict:
    return {'code': code, 'severity': severity, 'excerpt': excerpt[:80], 'detail': detail}


# 第五轮 T22 四项易懂度低分都来自 Markdown 表里残留的 HTML 合并单元格写法 (colspan)。
TABLE_MARKUP = re.compile(r'colspan|rowspan|</?(?:table|tr|td|th)(?=[\s>/])', re.I)
# Fences open with three or more backticks or tildes and close with the same run.
CODE_FENCE = re.compile(r'^(`{3,}|~{3,})[^\n]*\n.*?^\1[`~]*[ \t]*$', re.S | re.M)


def markup_findings(answer: str) -> list[dict]:
    match = TABLE_MARKUP.search(CODE_FENCE.sub('', answer))
    if not match:
        return []
    start = max(0, match.start() - 20)
    return [_finding('table_markup', 'warning', answer[start:match.end() + 20],
                     '表格里有 HTML 写法（如 colspan）；多数宿主不渲染，改成每行列数相同的 Markdown 表')]


# 「不是《滴天髓》的原句」「《子平真诠》里没有这句」: the search covers only the bundled transcriptions,
# so an absence is said with that scope or not at all (R2 N08). The scope words may sit anywhere in the
# same sentence; 「随包转录本《子平真诠》里检索不到」 passes.
ABSENCE = re.compile(r'(?:不是|并非|并不是|不属于)《[^》]{1,20}》的?(?:原句|原文|原话|句子)'
                     r'|《[^》]{1,20}》(?:里|中|原书)?(?:没有|并无|查无|找不到|未见|不见)(?:这句|此句|这段|该句|此语|原文|这话)?')
ABSENCE_SCOPE = re.compile(r'随包|转录|所收|本次所?查|检索到的|这些版本|所查|整理本')


# A denial that names the exact string right after it (「…里没有这句：XXX」) is checked by the quote check;
# its scope is still advised, but only the bare claim that a book lacks something is an error.
NAMED_DENIAL = re.compile(r'^\s*[：:「『“"]')


def absence_findings(sentence: str) -> list[dict]:
    match = ABSENCE.search(sentence)
    if not match or ABSENCE_SCOPE.search(sentence):
        return []
    severity = 'warning' if NAMED_DENIAL.match(sentence[match.end():]) else 'error'
    return [_finding('unscoped_absence_claim', severity, sentence,
                     '检索只覆盖随包转录本：写成「随包转录本里没有」，不能说原书或该书没有')]


def must_cover_findings(answer: str, facts: list[dict]) -> list[dict]:
    """Items a tool marked as required for this question (must_cover.py) that no line of the answer states."""
    lines = [line for line in answer.splitlines() if line.strip()]
    findings = []
    for fact in facts:
        items = fact.get('must_cover') if isinstance(fact, dict) else None
        for entry in items if isinstance(items, list) else []:
            groups = entry.get('groups') if isinstance(entry, dict) else None
            if not isinstance(groups, list) or not groups:
                continue
            if not any(all(any(alt in line for alt in group) for group in groups) for line in lines):
                findings.append(_finding('must_cover_missing', 'error', str(entry.get('what', '')),
                                         f"{fact.get('tool', '工具')}要求这题必须答到：{entry.get('what', '')}"
                                         '（同一行里写出）'))
    return findings


CITED_ID = re.compile(r'\b([a-z_]+:c\d{3}:p\d{4})\b')


def citation_findings(answer: str, facts: list[dict]) -> list[dict]:
    """A passage id in the answer that no tool result of this round carries (plan A3, R2 S24)."""
    if not facts:
        return []
    known = json.dumps(facts, ensure_ascii=False)
    missing = sorted({pid for pid in CITED_ID.findall(answer) if pid not in known})
    return [_finding('citation_not_in_facts', 'warning', pid,
                     f'{pid} 不在本轮任何工具结果里：用 classical_search.py --passage-id {pid} 核实后再引，'
                     '或把取到它的那次结果一起交给 --facts') for pid in missing]


@cache
def _layer(passage_id: str) -> str | None:
    try:
        return get_passage(passage_id).get('layer')
    except ValueError:
        return None


def commentary_findings(answer: str) -> list[dict]:
    """A commentary passage cited as the book's own words (R3 N08: 《滴天髓辑要》 notes as 《滴天髓》)."""
    findings = []
    for line in answer.splitlines():
        for pid in dict.fromkeys(CITED_ID.findall(line)):
            if _layer(pid) == 'commentary' and '注' not in line:
                findings.append(_finding('commentary_cited_as_text', 'error', line.strip()[:80],
                                         f'{pid} 是注文（layer=commentary），不是原书正文：同一行写明「注文」或「某某注」'))
    return findings


def _ziwei_layers(facts: list[dict]) -> Iterator[dict]:
    for fact in facts:
        horoscope = fact.get('horoscope') if isinstance(fact, dict) and fact.get('tool') == 'ziwei' else None
        for layer in (horoscope or {}).values():
            if isinstance(layer, dict) and isinstance(layer.get('transformation_palaces'), list):
                yield layer


def sihua_palace_findings(answer: str, facts: list[dict]) -> list[dict]:
    """A layer's 四化 listed without where the stars sit (R2 N04): each line that names 化X with its star
    should also name that star's palace (本命宫名或地支宫)."""
    findings = []
    lines = answer.splitlines()
    required = any(isinstance(f, dict) and any(isinstance(e, dict) and e.get('check') == 'sihua_palaces'
                                                for e in f.get('must_cover') or []) for f in facts)
    for layer in _ziwei_layers(facts):
        missing = []
        for row in layer['transformation_palaces']:
            if not row.get('branch'):
                continue
            kind, star = row['kind'], row['star']
            named = [line for line in lines if star in line and (kind in line or kind[1:] in line)]
            if not named:
                continue
            palace = (row.get('natal_palace') or '').removesuffix('宫')
            if not any((palace and palace in line) or f"{row['branch']}宫" in line for line in named):
                missing.append(f"{kind}{star}")
        # The tool's must_cover makes one missing palace an error; older facts without it keep the warning.
        if len(missing) >= (1 if required else 2):
            findings.append(_finding('sihua_palace_missing', 'error' if required else 'warning', '、'.join(missing),
                                     f"{layer.get('layer', '')}四化只列了星，没写各星落在哪一宫；"
                                     '照 transformation_palaces 补上（本命宫名或地支宫）'))
    return findings


def _check_assertions(answer: str, facts: list[dict],
                      pillars: tuple[PillarEvidence, ...] | None = None,
                      assertions: list[dict] | None = None) -> dict:
    checked = dict.fromkeys(('quotes_checked', 'quotes_skipped', 'pillars_checked', 'scores_checked'), 0)
    scores = facts if assertions is None else [row['score'] for row in assertions if 'score' in row]
    facts_text = json.dumps(scores, ensure_ascii=False)
    assertions = facts if assertions is None else assertions
    findings = [*_quote_findings(answer, checked), *pillar_findings(answer, facts, checked, pillars),
                *markup_findings(answer), *sihua_palace_findings(answer, facts),
                *must_cover_findings(answer, facts), *citation_findings(answer, facts), *commentary_findings(answer)]
    titles = unresolved_titles(assertions)
    tie = has_tie(assertions)
    for sentence in (s.strip() for s in sentences(answer)):
        findings += score_findings(sentence, facts_text, checked)
        findings += certainty_findings(sentence)
        findings += absence_findings(sentence)
        if titles:
            findings += geju_findings(sentence, titles)
        if tie:
            findings += tie_findings(sentence)
    return {'ok': True, 'tool': 'answer_check', 'version': __version__,
            'passed': not any(f['severity'] == 'error' for f in findings),
            'findings': findings, 'checked': {**checked, 'facts_loaded': len(facts)}, 'boundary': BOUNDARY}


def check_answer(answer: str, facts: object) -> dict:
    evidence = parse_evidence(facts)
    result = _check_assertions(answer, list(evidence.facts), evidence.pillars, assertion_facts(evidence))
    invalid = [_finding('invalid_facts', 'error', f'facts[{problem.index}]',
                        f'facts[{problem.index}]: {problem.reason}') for problem in evidence.problems]
    result['findings'] = invalid + result['findings']
    result['checked']['chart_facts_loaded'] = evidence.chart_count
    result['passed'] = result['passed'] and not invalid
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='发出前机械核对回答正文：引文、四柱、分数、确定性断言、未判格局、并列',
        epilog='Top-level JSON keys: ok tool version passed findings checked boundary; errors: error message. '
               'Exit 0 when no error finding.')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--answer', help="回答正文文件；'-' 读标准输入")
    source.add_argument('--stdin', action='store_true',
                        help='从标准输入读 {"answer": 正文, "facts": [本次工具 JSON 输出, ...]}，不用另存文件')
    parser.add_argument('--facts', action='append', default=[], help='本次工具 JSON 输出文件，可重复')
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        facts = [json.loads(Path(p).read_text(encoding='utf-8')) for p in args.facts]
        if args.stdin:
            request = json.loads(sys.stdin.read())
            if not isinstance(request, dict) or not isinstance(request.get('answer'), str):
                raise ValueError('需要 {"answer": "正文", "facts": [...]}')
            answer = request['answer']
            extra = request.get('facts', [])
            if not isinstance(extra, list):
                raise ValueError('facts 须是 JSON 数组（每项是一个工具输出对象）')
            facts += extra
        else:
            answer = sys.stdin.read() if args.answer == '-' else Path(args.answer).read_text(encoding='utf-8')
        if not all(isinstance(f, dict) for f in facts):
            raise ValueError('facts 每一项须是一个 JSON 对象（工具输出）')
        result = check_answer(answer, facts)
    except (OSError, ValueError) as exc:
        json_print(error_envelope('answer_check', 'invalid_input', str(exc)))
        return 1
    json_print(result)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
