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

from classical_search import iter_passages, normalized
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
# Text assets a host may quote: hexagram texts, the life guide, tarot, dream
# notes and the rule files' own excerpts. Lookup tables are not quotable.
QUOTABLE_ASSETS = ('64hex', 'life_guide', 'tarot78', 'jiemeng', 'classical_evidence', 'luck_rules',
                   'geju_rules', 'tiaohou', 'method_rules', 'bazi_rules', 'shensha')
ASSET_TITLES = {'life_guide': '高性价比人生指南', '64hex': '周易'}

QUOTE = re.compile(r'「([^「」\n]{2,240})」|『([^『』\n]{2,240})』|“([^“”\n]{2,240})”')
HAN = re.compile(r'[一-鿿]')
ELLIPSIS = re.compile(r'……|…|\.{3,}|⋯+')
TITLE_BEFORE = re.compile(r'《([^》]{1,16})》[^「『“。！？\n]{0,24}$')
CUE_BEFORE = re.compile(r'(原文|古籍|古书|书中|書中|书上|书里|有云|云|曰|有言|条文|口诀|卦辞|爻辞)'
                        r'(?:里|中|上)?(?:说|讲|道|写|写道|写着|载|记载)?\s*[:：，,]?\s*$')
CLASSICAL = set('之乎者也焉矣兮曰爲為於則')
# Transcription markers: commentary brackets and rare glyphs written as
# 〔字形SKnnnn：字〕. A quote reads through them, so the match key drops them.
GLYPH = re.compile(r'〔字形[^：〕]*：([^〕未])〕')
MARKER = re.compile(r'〔[^〕]*〕')

STEM = '甲乙丙丁戊己庚辛壬癸'
BRANCH = '子丑寅卯辰巳午未申酉戌亥'
PILLAR = re.compile(rf'([年月日时時])柱(?:是|为|為|[：:])?\s*([{STEM}][{BRANCH}])')
DAY_MASTER = re.compile(rf'日主(?:是|为|為|[：:])?\s*([{STEM}])')
PILLAR_KEYS = {'年': 'year', '月': 'month', '日': 'day', '时': 'hour', '時': 'hour'}

SENTENCE = re.compile(r'[^。！？!?；;\n]+')
SCORE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:分|%|％)|百分之([零一二三四五六七八九十百\d]+)')
SCORE_CONTEXT = re.compile(r'概率|几率|机率|匹配|契合|成功率|指数|评分|打分|得分|把握|可能性|胜算|命中率|准确率|覆盖率')
CERTAIN = re.compile(r'一定|肯定|必然|必定|注定|保证|百分之百|绝对|毫无疑问|必能|必会|稳了|铁定|板上钉钉')
QUOTED = re.compile(r'「[^」]*」|『[^』]*』|“[^”]*”|"[^"]*"')
CLAUSE = re.compile(r'[，,、：:（(]')
NEGATION = re.compile(r'不|未必|没|无法|並非|并非|别|難以|难以|谈不上')
OUTCOME = re.compile(r'录用|录取|成功|发财|暴富|结婚|离婚|升职|升官|中奖|考上|怀孕|康复|好运|坏运|顺利|失败|破财'
                     r'|[吉凶灾]|生病|重病|去世|成格|破格|用神|喜用|应期|一帆风顺|贵人')
HEDGE = re.compile(r'候选|待核|未定|尚未|未判|不能确定|无法确定|可能|或许|若|如果|条件|是否|还要|需要|未必|不一定|暂|倾向')
SETTLED_GEJU = r'(?:是|属|属于|为|為|定为|成|就是|取)\s*(?:{})格'
TIE_STATUSES = {'tied_no_clause_separates', 'practical_tie'}
TIE_PICK = re.compile(r'最好的一天|最佳|首选|最吉|最好|最合适|最推荐|第一选择')
TIE_KEPT = re.compile(r'并列|都可以|同样|没有先后|不分先后|任选|按你|看你|偏好|都行')

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
    """(title key, locator, text key) for every quotable paragraph."""
    rows = [(_key(book['title']), passage['passage_id'], _key(MARKER.sub('', GLYPH.sub(r'\1', passage['text']))))
            for book, passage in iter_passages()]
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


def _quote_findings(answer: str, facts_key: str, checked: dict) -> list[dict]:
    findings = []
    for match in QUOTE.finditer(answer):
        quote = next(group for group in match.groups() if group)
        before = answer[max(0, match.start() - 40):match.start()]
        title = TITLE_BEFORE.search(before)
        cued = title or CUE_BEFORE.search(before) or len(CLASSICAL & set(quote)) >= 2
        if len(HAN.findall(quote)) < 6 or not cued:
            checked['quotes_skipped'] += 1
            continue
        checked['quotes_checked'] += 1
        parts = [p for p in (_key(x) for x in ELLIPSIS.split(quote)) if p]
        hits = [(t, loc) for t, loc, text in _corpus() if _in_order(parts, text)]
        cited = _key(title.group(1)) if title else ''
        known = any(_title_matches(cited, t) for t in _library_titles())
        if hits and cited and known and not any(_title_matches(cited, t) for t, _ in hits):
            findings.append(_finding('misattributed_quote', 'error', quote,
                                     f'原文在 {hits[0][1]}，不在《{title.group(1)}》'))  # type: ignore[union-attr]
        elif not hits and not (len(parts) == 1 and parts[0] in facts_key):
            if cited and not known:
                findings.append(_finding('quote_outside_library', 'warning', quote,
                                         f'《{title.group(1)}》不在随包古籍内，无法核对原文'))  # type: ignore[union-attr]
            else:
                findings.append(_finding('unverified_quote', 'error', quote, '随包古籍和工具结果里都找不到这段原文'))
    return findings


def _charts(facts: list[dict]) -> list[dict]:
    found = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if isinstance(value.get('four_pillars'), dict):
                found.append(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(facts)
    return found


def _pillar_findings(answer: str, facts: list[dict], checked: dict) -> list[dict]:
    charts = _charts(facts)
    if not charts:
        return []
    findings = []
    for match in PILLAR.finditer(answer):
        checked['pillars_checked'] += 1
        slot, ganzhi = PILLAR_KEYS[match.group(1)], match.group(2)
        if slot == 'hour' and not any(c.get('hour_known', True) for c in charts):
            findings.append(_finding('unknown_hour_pillar', 'error', match.group(0), '出生时辰未知，工具没有给出时柱'))
        elif not any(c['four_pillars'].get(slot, {}).get('ganzhi') == ganzhi for c in charts):
            actual = '/'.join(str(c['four_pillars'].get(slot, {}).get('ganzhi')) for c in charts)
            findings.append(_finding('pillar_mismatch', 'error', match.group(0), f'工具结果为 {actual}'))
    for match in DAY_MASTER.finditer(answer):
        checked['pillars_checked'] += 1
        masters = {str(c['four_pillars'].get('day', {}).get('ganzhi', ' '))[0] for c in charts}
        if match.group(1) not in masters:
            findings.append(_finding('day_master_mismatch', 'error', match.group(0), f'工具结果为 {"/".join(sorted(masters))}'))
    return findings


def _certain(sentence: str) -> bool:
    """A certainty marker the sentence asserts: not quoted, not negated earlier in its clause."""
    own = QUOTED.sub('', sentence)
    for match in CERTAIN.finditer(own):
        clause = CLAUSE.split(own[:match.start()])[-1]
        if not NEGATION.search(clause):
            return True
    return False


def _geju_titles(facts: list[dict]) -> list[str]:
    titles: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            review = value.get('geju_review')
            if isinstance(review, dict) and review.get('verdict') == 'unresolved':
                titles.extend(f['title'] for f in review.get('families', []) if f.get('title'))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(facts)
    return titles


def _has_tie(facts: list[dict]) -> bool:
    def walk(value: object) -> bool:
        if isinstance(value, dict):
            if value.get('status') in TIE_STATUSES or (isinstance(value.get('tied'), list) and len(value['tied']) > 1):
                return True
            return any(walk(item) for item in value.values())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        return False
    return walk(facts)


def _sentence_findings(answer: str, facts: list[dict], facts_text: str, checked: dict) -> list[dict]:
    findings = []
    titles = _geju_titles(facts)
    settled = re.compile(SETTLED_GEJU.format('|'.join(map(re.escape, titles)))) if titles else None
    tie = _has_tie(facts)
    for sentence in (m.group(0).strip() for m in SENTENCE.finditer(answer)):
        for match in SCORE.finditer(sentence):
            checked['scores_checked'] += 1
            if SCORE_CONTEXT.search(sentence) and match.group(0) not in facts_text:
                findings.append(_finding('invented_score', 'error', sentence, '工具结果里没有这个分数或比例'))
        if _certain(sentence) and OUTCOME.search(sentence):
            findings.append(_finding('certainty_claim', 'error', sentence, '传统条款和工具结果不支持确定性的结果断言'))
        if settled and settled.search(sentence) and not HEDGE.search(sentence):
            findings.append(_finding('unresolved_settled', 'error', sentence, '工具格局结论为未判，只能说候选和待核条件'))
        if tie and TIE_PICK.search(sentence) and not TIE_KEPT.search(sentence):
            findings.append(_finding('tie_collapsed', 'error', sentence, '工具结果是并列，没有条款分出先后'))
    return findings


def _finding(code: str, severity: str, excerpt: str, detail: str) -> dict:
    return {'code': code, 'severity': severity, 'excerpt': excerpt[:80], 'detail': detail}


def check_answer(answer: str, facts: list[dict]) -> dict:
    checked = dict.fromkeys(('quotes_checked', 'quotes_skipped', 'pillars_checked', 'scores_checked'), 0)
    facts_text = json.dumps(facts, ensure_ascii=False)
    findings = [*_quote_findings(answer, _key(facts_text), checked),
                *_pillar_findings(answer, facts, checked),
                *_sentence_findings(answer, facts, facts_text, checked)]
    return {'ok': True, 'tool': 'answer_check', 'version': __version__,
            'passed': not any(f['severity'] == 'error' for f in findings),
            'findings': findings, 'checked': {**checked, 'facts_loaded': len(facts)}, 'boundary': BOUNDARY}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='发出前机械核对回答正文：引文、四柱、分数、确定性断言、未判格局、并列',
        epilog='Top-level JSON keys: ok tool version passed findings checked boundary; errors: error message. '
               'Exit 0 when no error finding.')
    parser.add_argument('--answer', required=True, help="回答正文文件；'-' 读标准输入")
    parser.add_argument('--facts', action='append', default=[], help='本次工具 JSON 输出，可重复')
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        answer = sys.stdin.read() if args.answer == '-' else Path(args.answer).read_text(encoding='utf-8')
        facts = [json.loads(Path(p).read_text(encoding='utf-8')) for p in args.facts]
        result = check_answer(answer, facts)
    except (OSError, ValueError) as exc:
        json_print(error_envelope('answer_check', 'invalid_input', str(exc)))
        return 1
    json_print(result)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
