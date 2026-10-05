#!/usr/bin/env python
"""Real-world references from the frozen 《高性价比人生指南》, gated by region.

Two uses. After a divination answer, in its own section and never used to
rank dates or colours: an entry is attached when it is mapped to the matter,
is not marked TODO (the book's own rule: do not use those as conclusions),
and applies where the matter takes place — see ``region.py``. At most three.
For a real-life question: ``--decide`` runs the book's decision workflow
(life_decision.py), ``--query`` searches with the book's filters and ranking
(life_search.py), and ``--sections``, ``--term``, ``--articles`` read its
question table, glossary and long articles.

    python scripts/life_guide.py --scenario travel --current-timezone Australia/Sydney \\
        --destination-timezone Asia/Singapore
    python scripts/life_guide.py --entry 15:1 --current-timezone Australia/Sydney
    python scripts/life_guide.py --query 押金 --current-timezone Australia/Sydney
    python scripts/life_guide.py --article marriage --current-timezone Asia/Shanghai
    python scripts/life_guide.py --decide "替朋友担保签不签" --current-timezone Asia/Shanghai --markdown
    python scripts/life_guide.py --query 保险 --grade A --ratio 极高 --sort ratio
"""
from __future__ import annotations

import argparse
import json
import re
from functools import cache
from pathlib import Path

import life_decision
import life_search
from region import crosses_border, is_zone, resolve_destination, resolve_region
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

DATA_FILE = Path(__file__).resolve().parents[1] / 'assets' / 'life_guide.json'
LIMIT = 3

# Reviewed by hand against each entry's text; keyword matching finds none of
# 面试, 出行 or 开业 in any title, so it cannot be relied on. A string names
# one of the book's long articles. Entries in QUESTION_PATTERNS fit only
# part of the matter and come first, so the limit does not cut them when the
# question does ask about that part.
Ref = tuple[int, int] | str
SCENARIO_ENTRIES: dict[str, list[Ref]] = {
    'travel': [(13, 33), (13, 35), (21, 1), (21, 2), (21, 3), (21, 4)],
    'moving': [(15, 1), (15, 3), (15, 5)],
    'interview': [(31, 14), (31, 7), (19, 3)],
    'work_conversation': [(31, 15), (19, 1), (19, 3), (19, 4)],
    'wedding': ['marriage', (10, 9), (10, 10), (10, 11)],
    'relationship_conversation': [(10, 3), (10, 5), (10, 2)],
    # 合婚 is a specialist workflow with no fortune_reading answer to ride
    # after; references/14-hehun.md has it call ``--scenario compatibility``.
    # 10:1, 10:4 and the long article comment on 合婚 itself, so none of
    # them rides with it. (842e11c9 moved the two kept ones from 10:17/10:18.)
    'compatibility': [(10, 17), (10, 16)],
    'business': [(12, 1), (12, 3), (12, 7)],
    'billing': [(9, 15), (12, 15), (8, 18)],
    'exam': [(23, 8), (31, 7)],
}
# Entries that fit only part of their scenario: attached when the question
# names that part. 23:8 is about paying for a 考证 course, not 高考 or 考研;
# 准考证 is an exam ticket and 毕业证书 a diploma, neither a course to pay for.
QUESTION_PATTERNS: dict[tuple[int, int], re.Pattern] = {
    (23, 8): re.compile(r'(?<!准)考证|考个证|资格证|职业证书|技能证书|证书培训'),
    # Sleeping above about 2,450 m: 黄土、云贵、内蒙古高原 and 西宁 are lower.
    (13, 33): re.compile(r'(?<!黄土)(?<!云贵)(?<!蒙古)高原|西藏|拉萨|林芝|日喀则|阿里地区|冈仁波齐|青藏|青海湖|玉树|果洛|'
                         r'格尔木|色达|理塘|稻城|川西|香格里拉|珠峰|高反|海拔\s*[3-5]\d{3}'),
    (13, 35): re.compile(r'野外|徒步|露营|户外|登山|爬山'),
    # Working abroad, not a 劳务派遣 agency at home or experience abroad.
    (31, 14): re.compile(r'出国打工|出国务工|出国劳务|对外劳务|海外务工|劳务输出|去(?:国外|海外|境外)打工|出国工作|外派出国'),
    # Getting into 体制: not 考公共英语, 考公司, 考公安大学, 考编程, 艺考编导,
    # nor someone already in it taking another exam.
    (31, 7): re.compile(r'考公(?![共司安交])|考编(?![程导辑制])|考公务员|报考公务员|公务员(?:考试|面试)|'
                        r'(?<![中美英法德日韩俄泰澳加新])国考|(?<!节)省考|考事业编|事业编考试|考进体制|进体制'),
    # Income from a company abroad, not a remote meeting or a foreign client call.
    (31, 15): re.compile(r'(?:给|替|帮|接)(?:境外|国外|海外|外国)(?:公司|企业|雇主|客户)|'
                         r'(?:境外|国外|海外|外国)(?:公司|企业|雇主|客户)[^，。]{0,8}(?:远程|报酬|收入|工资|个税|收汇|接单)|'
                         r'远程[^，。]{0,8}(?:境外|国外|海外|外国)'),
    (9, 15): re.compile(r'催款|催收|要债|讨债|追债|讨薪|要账|收账|追讨'),
}
# A question that names the part but from the other side vetoes the entry:
# 9:15 is for the one collecting, not the one being chased or who owes;
# 13:33 is for going up, not coming back down.
QUESTION_VETOES: dict[tuple[int, int], re.Pattern] = {
    (9, 15): re.compile(r'被[^，。]{0,4}(?:催|要债|讨债|追债|追讨|要账)|(?:我|自己)欠'),
    (13, 33): re.compile(r'从[^，。]{0,6}(?:高原|西藏|拉萨|青藏)回|海拔(?:低|不高)'),
}
FOREIGN_NOTE = '中国大陆口径：你所在地的规定、机构和电话可能不同'
TODO_NOTE = '原书把这条标为待核实（TODO），按原书的规矩不能当结论用'


@cache
def _data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding='utf-8'))


@cache
def _index() -> dict[tuple[int, int], dict]:
    return {(e['section'], e['number']): e for e in _data()['entries']}


@cache
def _articles() -> dict[str, dict]:
    """Long articles, shaped like entries for the gate and the renderer."""
    return {a['id']: {**a, 'kind': 'article', 'todo': False, 'disputed': False, 'dispute': None}
            for a in _data().get('articles', [])}


def _lookup(ref: Ref) -> dict | None:
    return _articles().get(ref) if isinstance(ref, str) else _index().get(ref)


def library_source() -> dict:
    """Where the frozen text comes from and how it may be reused, for citing beside it."""
    source = _data()['source']
    detail = source.get('license_detail') or {}
    return {**{k: source[k] for k in ('repo', 'commit', 'snapshot_date', 'license')},
            'attribution': detail.get('attribution'), 'changes': detail.get('changes')}


def _applies(entry: dict, payload: dict) -> bool:
    if entry['region'] == '通用':
        return True
    if entry['region'] == '中国公民在境外':
        # Advice for leaving the country: a trip abroad that crosses a border,
        # not Sydney to Melbourne.
        return resolve_destination(payload) == '境外' and crosses_border(payload)
    return resolve_region(payload)['region'] == entry['region']


def _asked(key: Ref, payload: dict) -> bool:
    if not isinstance(key, tuple) or key not in QUESTION_PATTERNS:
        return True
    question = str(payload.get('question') or '')
    veto = QUESTION_VETOES.get(key)
    return bool(QUESTION_PATTERNS[key].search(question)) and not (veto and veto.search(question))


def entries_for(payload: dict) -> list[dict]:
    """Entries (and articles) to attach to an answer about this matter, in mapped order."""
    scenario = str((payload.get('event') or {}).get('scenario') or '')
    rows = []
    for key in SCENARIO_ENTRIES.get(scenario, []):
        entry = _lookup(key)
        if entry and not entry['todo'] and _applies(entry, payload) and _asked(key, payload):
            rows.append(entry)
    return rows[:LIMIT]


def _annotated(entry: dict, payload: dict) -> dict:
    """A copy saying when the rules are not the user's, or the book doubts it."""
    row = dict(entry)
    if entry['region'] == '中国大陆' and resolve_region(payload)['region'] != '中国大陆':
        row['region_note'] = FOREIGN_NOTE
    if entry['todo']:
        row['todo_note'] = TODO_NOTE
    return row


def get_entry(section: int, number: int, payload: dict) -> dict | None:
    """One entry on explicit request, noting when its rules are not the user's."""
    entry = _index().get((section, number))
    return None if entry is None else _annotated(entry, payload)


def get_article(key: str, payload: dict) -> dict | None:
    """A long article, whole, with the same region note."""
    article = _articles().get(key)
    return None if article is None else _annotated(article, payload)


def search(query: str, payload: dict | None = None, limit: int = 5, filters: dict | None = None,
           sort: str = 'book', applicable: bool = False) -> list[dict]:
    """Whole entries matching the query and the book's filters.

    TODO entries are left out unless asked for, as in ``entries_for``: the
    book says not to conclude from those. Each hit carries the same notes as
    an explicit lookup. By default an entry for another region is returned
    with a 中国大陆口径 note (asking about another place is legitimate);
    ``applicable`` keeps only the entries that apply where the user is.
    """
    if not query.strip() and not filters:
        return []
    rows = life_search.search(_data()['entries'], query, filters, sort=sort)
    if applicable:
        where = resolve_region(payload or {})['region']
        rows = [r for r in rows if r[0]['region'] in ('通用', where)
                or (r[0]['region'] == '中国公民在境外' and where == '境外')]
    out = []
    for entry, match, _ in rows[:limit]:
        row = _annotated(entry, payload or {})
        out.append({**row, 'match': match} if match == 'partial' else row)
    return out


def sections() -> list[dict]:
    """Each section with the question it answers (README) and its intro."""
    questions = {q['section']: q['question'] for q in _data()['guide']['questions']}
    return [{'section': s['section'], 'title': s['title'], 'question': questions.get(s['section']),
             'intro': s['intro']} for s in _data()['sections']]


def glossary(term: str | None = None) -> list[dict]:
    rows = _data()['guide']['glossary']
    if term is None:
        return rows
    return [r for r in rows if term.lower() in r['term'].lower() or r['term'].lower() in term.lower()]


def decide(question: str, payload: dict | None = None) -> dict:
    return life_decision.decide(_data(), question, payload)


def _split(value: str | None) -> set[str] | None:
    return set(value.split(',')) if value else None


def _filters(args: argparse.Namespace) -> dict:
    filters = {'section': {int(x) for x in args.section.split(',')} if args.section else None,
               'grade': _split(args.grade), 'ratio': _split(args.ratio), 'lens': _split(args.lens),
               'money': _split(args.money), 'time': _split(args.time), 'will': _split(args.will),
               'disputed': args.disputed, 'include_todo': args.include_todo}
    return {k: v for k, v in filters.items() if v}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='《高性价比人生指南》冻结快照：术数回答后的现实参考、人生决策、检索筛选（不参与术数排序）',
        epilog='Top-level JSON keys: ok tool version source region and one of entries, decision, sections, '
               'glossary, articles. entries[]: section number title fields grade cost_tags cost_score ratio lens '
               'todo disputed dispute region refs [region_note todo_note match]; an article row has kind id path '
               'title text region refs. decision: question region stop sections do dont not_in_book match '
               'articles notes terms.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--scenario')
    mode.add_argument('--entry', help='节:条，例如 15:1')
    mode.add_argument('--query', help='关键词；空格分开的每个词都要命中，整句中文自动拆词兜底')
    mode.add_argument('--decide', help='用户原话；按书里的决策流程查条目、排序、分先做和别做')
    mode.add_argument('--article', help='长文编号，例如 marriage')
    mode.add_argument('--articles', action='store_true', help='列出全部长文')
    mode.add_argument('--sections', action='store_true', help='列出各节回答的问题和导读')
    mode.add_argument('--term', help='查术语表；给 all 列出全部')
    parser.add_argument('--current-timezone')
    parser.add_argument('--event-timezone')
    parser.add_argument('--destination-timezone')
    parser.add_argument('--question', help='用户原话；只适合一部分问法的条目要靠它判断')
    group = parser.add_argument_group('筛选（照书里检索页的维度，逗号分隔多选）')
    group.add_argument('--section', help='节号，例如 7,19')
    group.add_argument('--grade', help='A,B,C')
    group.add_argument('--ratio', help='极高,高,一般')
    group.add_argument('--lens', help='换寿命,换钱,换时间精力,换人身自由')
    group.add_argument('--money', help='0,少,多')
    group.add_argument('--time', help='少,中,多')
    group.add_argument('--will', help='否,些,是')
    group.add_argument('--disputed', action='store_true', help='只要标了争议的')
    group.add_argument('--include-todo', action='store_true', help='连待核实的一起返回（不能当结论用）')
    parser.add_argument('--sort', choices=('book', 'ratio', 'relevance'), default='book',
                        help='book 原书顺序；ratio 性价比再证据等级；relevance 命中程度')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--applicable', action='store_true', help='只要适用于所在地的条目（默认标注地区不符，不筛掉）')
    parser.add_argument('--markdown', action='store_true', help='--decide 时输出带出处的白话草稿')
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = _parser().parse_args(argv)
    event = {k: v for k, v in {'scenario': args.scenario, 'timezone': args.event_timezone,
                               'destination_timezone': args.destination_timezone}.items() if v}
    payload = {'current_timezone': args.current_timezone, 'event': event, 'question': args.question}
    body: dict = {}
    try:
        # An unknown zone name must not quietly count as 境外.
        for zone in (args.current_timezone, args.event_timezone, args.destination_timezone):
            if zone and not is_zone(zone):
                raise ValueError(f'不是 IANA 时区名：{zone!r}（例如 Australia/Sydney）')
        if not 1 <= args.limit <= 100:
            raise ValueError('--limit 须在 1 到 100 之间')
        if args.entry:
            parts = args.entry.split(':')
            if len(parts) != 2 or not all(x.isdigit() for x in parts):
                raise ValueError('--entry 须为「节:条」，例如 15:1')
            found = get_entry(int(parts[0]), int(parts[1]), payload)
            if found is None:
                raise ValueError(f'本库没有第 {parts[0]} 节第 {parts[1]} 条')
            body['entries'] = [found]
        elif args.query is not None:
            if not args.query.strip() and not _filters(args):
                raise ValueError('--query 不能为空（只想筛选时给一个筛选条件）')
            body['entries'] = search(args.query, payload, args.limit, _filters(args), args.sort, args.applicable)
        elif args.decide is not None:
            if not args.decide.strip() or len(args.decide) > 2000:
                raise ValueError('--decide 须为 1–2000 字符的原话')
            body['decision'] = decide(args.decide, payload)
            if args.markdown:
                print(life_decision.render(body['decision']))
                return 0
        elif args.article:
            article = get_article(args.article, payload)
            if article is None:
                raise ValueError(f'本库没有长文 {args.article!r}')
            body['entries'] = [article]
        elif args.articles:
            body['articles'] = [{k: a[k] for k in ('id', 'path', 'title', 'region')} for a in _data()['articles']]
        elif args.sections:
            body['sections'] = sections()
        elif args.term:
            body['glossary'] = glossary(None if args.term == 'all' else args.term)
        else:
            body['entries'] = entries_for(payload)
    except (ValueError, OSError) as exc:
        json_print(error_envelope('life_guide', 'invalid_input', str(exc)))
        return 1
    json_print(ok_envelope('life_guide', {'source': library_source(), 'region': resolve_region(payload), **body}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
