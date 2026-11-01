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
from classical_search import get_passage, iter_passages, normalized
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
# Text assets a host may quote: hexagram texts, the life guide, tarot, dream
# notes and the rule files' own excerpts. Lookup tables are not quotable.
QUOTABLE_ASSETS = ('64hex', 'life_guide', 'tarot78', 'jiemeng', 'classical_evidence', 'luck_rules',
                   'geju_rules', 'tiaohou', 'method_rules', 'bazi_rules', 'shensha', 'hehun_clauses', 'liuyao_rules')
ASSET_TITLES = {'life_guide': '高性价比人生指南', '64hex': '周易'}

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
MODALS = set('可能得宜必敢會会須须當当應应')
# A quote the answer itself says the books do not contain is being refuted, not cited.
QUOTE_DENIED_BEFORE = re.compile(r'(?:不是|并非|而非|并不是|不等于|远不是|而不是)\s*$')
QUOTE_REFUTED = re.compile(r'找不到|查不到|没查到|搜不到|检索不到|没有这句|并无此|并无这|不是原文|没有找到|未见|不存在')
# Facts fields that echo the user rather than the tools: a quote found only there
# is the user's own wording and proves nothing about the books.
USER_ECHO = frozenset({'question', 'query', 'normalized_query', 'prompt', 'input', 'request', 'answer'})
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
        tail = text[max(end, found - 2):found]
        if len(part) <= 8 and tail and (NEGATOR.fullmatch(tail[-1]) or (
                len(tail) == 2 and NEGATOR.fullmatch(tail[0]) and tail[1] in MODALS)):
            return True
        end = found + len(part)
    return False


def _in_cited_passage(parts: list[str], passage_id: str) -> bool:
    """The quote is in that passage's text, its section or its chapter title."""
    try:
        passage = get_passage(passage_id)
    except ValueError:
        return False
    text = _key(MARKER.sub('', GLYPH.sub(r'\1', passage['text'])))
    headings = _key(passage.get('section') or '') + _key(passage.get('chapter_title') or '')
    return _in_order(parts, text) or all(p in headings for p in parts)


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


def _quote_findings(answer: str, facts_key: str, checked: dict) -> list[dict]:
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
        terms = [_key(x) for x in quote.split('、')]
        if len(terms) > 1 and all(0 < len(t) <= 4 for t in terms):
            # 「修造、用事」 lists terms the book uses, not one continuous sentence.
            hits = [(t, loc) for t, loc, text in _corpus() if all(term in text for term in terms)]
            parts = terms
        else:
            parts = [p for p in (_key(x) for x in ELLIPSIS.split(quote)) if p]
            hits = [(t, loc) for t, loc, text in _corpus() if _in_order(parts, text)]
        cited_name = title.group(1) if title else ''
        cited = _key(cited_name)
        known = any(_title_matches(cited, t) for t in _library_titles())
        elided = len(parts) > 1 and bool(ELLIPSIS.search(quote))
        cut = next((loc for _, loc, text in _corpus() if elided and _drops_negator(parts, text)), None)
        if hits and cut:
            findings.append(_finding('elision_drops_negation', 'error', quote,
                                     f'省略号删掉了 {cut} 原文紧挨着保留部分的否定字，意思被反过来了'))
        elif hits and cited_passage and not _in_cited_passage(parts, cited_passage.group(1)):
            findings.append(_finding('misattributed_quote', 'error', quote,
                                     f'所引段落 {cited_passage.group(1)} 里没有这段原文'))
        elif hits and cited and known and not any(_title_matches(cited, t) for t, _ in hits):
            findings.append(_finding('misattributed_quote', 'error', quote, f'原文在 {hits[0][1]}，不在《{cited_name}》'))
        elif not hits and not (len(parts) == 1 and parts[0] in facts_key):
            if cited and not known:
                findings.append(_finding('quote_outside_library', 'warning', quote,
                                         f'《{cited_name}》不在随包古籍内，无法核对原文'))
            else:
                findings.append(_finding('unverified_quote', 'error', quote, '随包古籍和工具结果里都找不到这段原文'))
    return findings


def _finding(code: str, severity: str, excerpt: str, detail: str) -> dict:
    return {'code': code, 'severity': severity, 'excerpt': excerpt[:80], 'detail': detail}


def _without_user_echo(value: object) -> object:
    if isinstance(value, dict):
        return {k: _without_user_echo(v) for k, v in value.items() if k not in USER_ECHO}
    if isinstance(value, list):
        return [_without_user_echo(v) for v in value]
    return value


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


def check_answer(answer: str, facts: list[dict]) -> dict:
    checked = dict.fromkeys(('quotes_checked', 'quotes_skipped', 'pillars_checked', 'scores_checked'), 0)
    facts_text = json.dumps(facts, ensure_ascii=False)
    tool_text = json.dumps(_without_user_echo(facts), ensure_ascii=False)
    findings = [*_quote_findings(answer, _key(tool_text), checked), *pillar_findings(answer, facts, checked),
                *markup_findings(answer)]
    titles = unresolved_titles(facts)
    tie = has_tie(facts)
    for sentence in (s.strip() for s in sentences(answer)):
        findings += score_findings(sentence, facts_text, checked)
        findings += certainty_findings(sentence)
        if titles:
            findings += geju_findings(sentence, titles)
        if tie:
            findings += tie_findings(sentence)
    return {'ok': True, 'tool': 'answer_check', 'version': __version__,
            'passed': not any(f['severity'] == 'error' for f in findings),
            'findings': findings, 'checked': {**checked, 'facts_loaded': len(facts)}, 'boundary': BOUNDARY}


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
