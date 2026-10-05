"""Search, filter and rank 《高性价比人生指南》 the book's way.

The filters and the ranking follow the book's own search page (index.html at
the pinned commit, MIT): an entry passes when every chosen value of every
dimension matches (section, 性价比 tier, 口径, evidence grade, 钱/时间/毅力,
争议, 待核实) and every query word occurs in its title, 说人话, 成本, 收益,
备注, 来源 or grade. Ranking for a decision: tier (极高 > 高 > 一般), then
grade (A > B > C); tiers are only compared within one 口径.

One addition for plain Chinese questions, which do not come with spaces: when
no entry holds every word, the query is cut at question words and function
words, and entries are scored by how many of the remaining pieces (and their
two-character windows) they hold. Such hits are marked ``match: partial``.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from functools import cache

TIER_ORDER = {'极高': 0, '高': 1, '一般': 2}
GRADE_ORDER = {'A': 0, 'B': 1, 'C': 2}
TAG_LABEL = {'钱': {'0': '不花钱', '少': '花少量钱', '多': '花不少钱'},
             '时间': {'少': '顺手', '中': '花几小时', '多': '每天占时间'},
             '毅力': {'否': '不用毅力', '些': '要一点毅力', '是': '要很多毅力'}}
# Question words and function words a plain question carries around its topic.
STOP = re.compile(r'怎么办|怎么样|怎么|如何|为什么|什么|哪些|哪个|哪里|是不是|要不要|该不该|值不值|能不能|可不可以|'
                  r'可以吗|行不行|划不划算|划算吗|值得吗|犯不犯法|犯法吗|违法吗|先做什么|签不签|还是|应该|需要|'
                  r'帮我|请问|一下|有没有|会不会|算不算|多少|几天|不上|不起|不了|不到|不出|不动|不行|不好|'
                  r'注意事项|注意|问题|事情|情况|东西|办法|建议|有关|关于|'
                  # Quantities say how much, not what about: 「每天」「两小时」「三万」.
                  r'每[天周月年次]|[一二两三四五六七八九十百千万几半\d]+个?(?:小时|分钟|天|周|个月|月|年|次|岁|万|千|元|块)|'
                  r'[吗呢吧啊呀了的得地着过我你他她它这那就都也还又很太更最能会要想该去来做个些种次]')
# Everyday word → the words the book uses for exactly the same thing. Only
# pairs with one meaning; nothing broader than the word itself.
SAME_MEANING = {'发烧': ('发热', '体温'), '拉肚子': ('腹泻',), '被裁': ('辞退', '裁员'), '裁员': ('辞退',),
                '欠薪': ('欠了工钱', '讨薪'), '租房': ('租赁', '房东')}
ROLE_WORDS = frozenset({'朋友', '家人', '亲戚', '同事', '老板', '父母', '爸妈', '孩子', '老人', '老公', '老婆',
                        '对象', '别人', '熟人', '自己', '家里'})
PUNCT = re.compile(r'[，。？！、：；,.?!:;（）()「」“”"\'\s]+')
LATIN = re.compile(r'[A-Za-z0-9][A-Za-z0-9%.]*')


def hay(entry: dict) -> str:
    """The text the book's search page looks in, lowercased."""
    f = entry['fields']
    text = '\n'.join([entry['title'], f['说人话'], f['成本'], f['收益'], f['备注'], f['来源'], entry['grade']])
    return text.replace('**', '').lower()


def pieces(query: str) -> list[str]:
    """The topic words of a plain question: 「押金不退怎么办」 → ['押金不退']."""
    found: list[str] = []
    for chunk in PUNCT.split(query):
        for piece in STOP.split(chunk):
            piece = piece.strip().lower()
            if len(piece) >= 2 and piece not in found:
                found.append(piece)
    return found


def book_words(keys: list[str]) -> list[str]:
    """The book's own word where everyday speech uses another (发烧 → 体温)."""
    extra: list[str] = []
    for word, words in SAME_MEANING.items():
        if any(word in k for k in keys):
            extra += [w for w in words if w not in keys and w not in extra]
    return extra


def coverage(entry: dict, piece: str) -> float:
    """How much of a topic piece the entry holds, by two-character windows;
    whom it concerns (朋友, 孩子…) is left out of the count."""
    text = hay(entry)
    if piece in text:
        return 1.0
    if len(piece) <= 2 or LATIN.fullmatch(piece):
        return 0.0
    held = [False] * len(piece)
    for i in range(len(piece) - 1):
        if piece[i:i + 2] in text:
            held[i] = held[i + 1] = True
    role = [False] * len(piece)
    for word in ROLE_WORDS:
        at = piece.find(word)
        while at != -1:
            role[at:at + len(word)] = [True] * len(word)
            at = piece.find(word, at + 1)
    counted = [k for k in range(len(piece)) if not role[k]]
    return sum(held[k] for k in counted) / len(counted) if counted else 0.0


def _windows(piece: str) -> list[str]:
    if LATIN.fullmatch(piece) or len(piece) <= 2:
        return [piece]
    return [piece] + [piece[i:i + 2] for i in range(len(piece) - 1)]


def score(entry: dict, keys: list[str], weight: dict[str, float] | None = None,
          extra: list[str] | None = None) -> float:
    """Pieces and windows found, each weighted by how rare it is in the book
    (「通勤」 counts for more than 「每天」); a hit in the title counts twice and
    a whole piece twice again. The book's own words for an everyday one count
    like a window, never like the whole piece the asker wrote."""
    text, title = hay(entry), entry['title'].lower()
    total = 0.0
    for key in keys + (extra or []):
        whole = key in keys
        for window in dict.fromkeys(_windows(key) if whole else [key]):
            if window in text:
                rare = (weight or {}).get(window, 1.0)
                total += rare * (2 if window in title else 1) * (2 if whole and window == key else 1)
    return total


def _rarity(pool: list[dict], keys: list[str]) -> dict[str, float]:
    texts = [hay(e) for e in pool]
    weight = {}
    for key in keys:
        for window in _windows(key) + [key]:
            df = sum(window in t for t in texts)
            rare = math.log((len(texts) + 1) / (df + 1)) + 1 if df else 0.0
            # Whom it concerns is not what it is about: in 「替朋友担保」 the
            # matter is 担保, not 朋友.
            weight[window] = rare * (0.3 if window in ROLE_WORDS else 1.0)
    return weight


def passes(entry: dict, filters: dict) -> bool:
    """Every chosen value of every dimension, as on the book's search page."""
    tags = entry['cost_tags']
    checks = (('section', entry['section']), ('ratio', entry['ratio']), ('lens', entry['lens']),
              ('grade', entry['grade']), ('money', tags.get('钱')), ('time', tags.get('时间')),
              ('will', tags.get('毅力')))
    for key, value in checks:
        chosen = filters.get(key)
        if chosen and value not in chosen:
            return False
    if filters.get('disputed') and not entry['disputed']:
        return False
    return filters.get('include_todo') or not entry['todo']


def rank_key(entry: dict, relevance: float = 0) -> tuple:
    return (TIER_ORDER.get(entry['ratio'], 3), GRADE_ORDER.get(entry['grade'], 3), -relevance,
            entry['section'], entry['number'])


def search(entries: Iterable[dict], query: str = '', filters: dict | None = None,
           sort: str = 'book', limit: int | None = None) -> list[tuple[dict, str, float]]:
    """(entry, 'all' or 'partial', relevance) for every entry that passes."""
    filters = filters or {}
    pool = [e for e in entries if passes(e, filters)]
    rows: list[tuple[dict, str, float]]
    terms = [t for t in query.lower().split() if t]
    if not terms:
        rows = [(e, 'all', 0) for e in pool]
    else:
        rows = [(e, 'all', score(e, terms)) for e in pool if all(t in hay(e) for t in terms)]
        if not rows:
            keys = pieces(query)
            extra = book_words(keys)
            weight = _rarity(pool, keys + extra)
            # An entry fits when it holds at least half of some topic piece, or
            # the book's own word for it: a lone 「土豆」 in 「火星上种土豆」 does not.
            fits = [e for e in pool if any(coverage(e, k) >= 0.5 for k in keys) or any(w in hay(e) for w in extra)]
            scored = [(e, 'partial', score(e, keys, weight, extra)) for e in fits] if keys else []
            best = max((s for _, _, s in scored), default=0)
            # Keep the strong part: at least half the best score, or the book's
            # own word for the topic in the title (「体温」 for 「发烧」), which a
            # literal match on the asker's word would otherwise crowd out.
            rows = [r for r in scored if r[2] > 0 and (r[2] >= best / 2 or any(w in r[0]['title'] for w in extra))]
    if sort == 'ratio':
        rows.sort(key=lambda r: rank_key(r[0], r[2]))
    elif sort == 'relevance' or (terms and rows and rows[0][1] == 'partial'):
        rows.sort(key=lambda r: (-r[2], *rank_key(r[0])))
    else:
        rows.sort(key=lambda r: (r[0]['section'], r[0]['number']))
    return rows[:limit] if limit else rows


@cache
def _glossary_re(terms: tuple[str, ...]) -> re.Pattern | None:
    if not terms:
        return None
    latin = [t for t in terms if re.fullmatch(r'[A-Za-z0-9%. ]+', t)]
    cjk = [t for t in terms if t not in latin]
    parts = []
    if latin:
        parts.append(r'(?<![A-Za-z0-9])(?:' + '|'.join(map(re.escape, latin)) + r')(?![A-Za-z0-9])')
    if cjk:
        parts.append('(?:' + '|'.join(map(re.escape, cjk)) + ')')
    return re.compile('|'.join(parts))


def glossary_terms(glossary: list[dict], texts: Iterable[str]) -> list[dict]:
    """The book's glossary rows whose term appears in any of the texts."""
    by_term = {}
    for row in glossary:
        for term in row['term'].split('、'):
            by_term[term.strip()] = row
    pattern = _glossary_re(tuple(sorted(by_term, key=len, reverse=True)))
    if pattern is None:
        return []
    seen: dict[str, dict] = {}
    for text in texts:
        for m in pattern.finditer(text):
            row = by_term[m.group(0)]
            seen.setdefault(row['term'], row)
    return list(seen.values())


def sections_for(questions: list[dict], query: str, limit: int = 3) -> list[int]:
    """Sections whose README question shares the most topic words with the query."""
    keys = pieces(query)
    scored = []
    for q in questions:
        text = q['question'].lower()
        s = sum(2 if w == k else 1 for k in keys for w in dict.fromkeys(_windows(k)) if w in text)
        if s:
            scored.append((s, q['section']))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [sec for _, sec in scored[:limit]]


def tag_labels(entry: dict) -> list[str]:
    return [TAG_LABEL[k].get(entry['cost_tags'].get(k, ''), entry['cost_tags'].get(k, '')) for k in ('钱', '时间', '毅力')
            if entry['cost_tags'].get(k)]
