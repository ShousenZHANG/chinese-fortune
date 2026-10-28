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
from classical_search import iter_passages, normalized
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
# Text assets a host may quote: hexagram texts, the life guide, tarot, dream
# notes and the rule files' own excerpts. Lookup tables are not quotable.
QUOTABLE_ASSETS = ('64hex', 'life_guide', 'tarot78', 'jiemeng', 'classical_evidence', 'luck_rules',
                   'geju_rules', 'tiaohou', 'method_rules', 'bazi_rules', 'shensha', 'hehun_clauses')
ASSET_TITLES = {'life_guide': '高性价比人生指南', '64hex': '周易'}

# Bracket quotes may wrap lines; ASCII pairs stay on one line. Markdown block
# quotes count as quotations when a source cue or title introduces them.
QUOTE = re.compile(r'「([^「」]{2,400})」|『([^『』]{2,400})』|“([^“”]{2,400})”|"([^"\n]{2,240})"')
BLOCK = re.compile(r'(?m)^[ \t]*>[ \t]?(.+)$')
HAN = re.compile(r'[一-鿿]')
ELLIPSIS = re.compile(r'……|…|\.{3,}|⋯+')
TITLE_BEFORE = re.compile(r'《([^》]{1,16})》[^「『“"。！？]{0,24}$')
TITLE_AFTER = re.compile(r'^[\s—\-－–、，,：:）)]{0,4}(?:出自|见于|见|语出)?\s*《([^》]{1,16})》')
CUE_BEFORE = re.compile(r'(原文|古籍|古书|书中|書中|书上|书里|有云|云|曰|有言|条文|口诀|卦辞|爻辞|载|記載|记载)'
                        r'(?:里|中|上)?(?:说|讲|道|写|写道|写着|载|记载)?\s*[:：，,]?\s*$')
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


def _title_matches(cited: str, title: str) -> bool:
    return bool(cited) and (cited in title or title in cited)


def _quotes(answer: str) -> Iterator[tuple[str, str, str]]:
    """(quote, text before it, text after it) for bracket, ASCII and block quotations."""
    for match in QUOTE.finditer(answer):
        quote = next(group for group in match.groups() if group)
        yield quote, answer[max(0, match.start() - 40):match.start()], answer[match.end():match.end() + 24]
    groups: list[list[re.Match[str]]] = []
    for line in BLOCK.finditer(answer):
        if groups and line.start() == groups[-1][-1].end() + 1:
            groups[-1].append(line)
        else:
            groups.append([line])
    for group in groups:
        first, last = group[0], group[-1]
        yield (''.join(m.group(1) for m in group), answer[max(0, first.start() - 40):first.start()],
               answer[last.end():last.end() + 24])


def _quote_findings(answer: str, facts_key: str, checked: dict) -> list[dict]:
    findings = []
    for quote, before, after in _quotes(answer):
        title = TITLE_BEFORE.search(before) or TITLE_AFTER.search(after)
        cued = bool(title or CUE_BEFORE.search(before))
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
        if hits and cited and known and not any(_title_matches(cited, t) for t, _ in hits):
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


def check_answer(answer: str, facts: list[dict]) -> dict:
    checked = dict.fromkeys(('quotes_checked', 'quotes_skipped', 'pillars_checked', 'scores_checked'), 0)
    facts_text = json.dumps(facts, ensure_ascii=False)
    findings = [*_quote_findings(answer, _key(facts_text), checked), *pillar_findings(answer, facts, checked)]
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
            facts += request.get('facts') or []
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
