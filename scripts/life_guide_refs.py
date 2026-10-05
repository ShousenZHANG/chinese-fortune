"""Cross references in 《高性价比人生指南》, resolved to the titles they point at.

A port of the book's own ``tools/check-refs.mjs`` (MIT, eternity4719) at the
pinned commit, used by ``import_life_guide.py`` only (maintenance; not shipped).
The rules are the book's:

- In an entry, a bare 「第 N 条」 is this section's entry N, searched only in
  说人话/收益/备注/成本; 来源 holds law article numbers. A cross-section
  「第 X 节第 Y 条」 is searched in 来源 too. Section intros are searched whole.
- In a long article there is no 「本节」, so only 「第 X 节第 Y 条」 counts.
- A bare 「第 N 条」 right after a citation (《…》, 〔…〕, 「14 号」, 该解释, or a
  name ending in 法/条例/办法/规定/准则/细则/公约) is a law article, not an entry.
- Lists 「第 3、10、11 条」 and ranges 「第 11 到 14 条」 expand; a range only
  up to 30 apart.
- Relative pointers (上一条, 下一条 …) and references to missing entries are
  problems.
- A reference is anchored when its context shares three consecutive Han
  characters, a Latin or digit token, or two Han characters within its own
  clause, with the target title.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FIELDS = re.compile(r'^- (说人话|收益|备注|成本)：')
CROSS_FIELDS = re.compile(r'^- (说人话|收益|备注|成本|来源)：')
SPEC = r'[\d、,\s]+?(?:(?:到|至)\s*第?\s*\d+)?'
CROSS_RE = re.compile(rf'第\s*(\d+)\s*节第\s*({SPEC})\s*条')
BARE_RE = re.compile(rf'第\s*({SPEC})\s*条')
RANGE_RE = re.compile(r'^\s*(\d+)\s*(?:到|至)\s*第?\s*(\d+)\s*$')
RELATIVE_RE = re.compile(r'(?<![最之以])(上一条|下一条|前一条|后一条|上面那条|上面这条|前面那条)')
CITE_RE = re.compile(r'(《[^》]*》|〔[^〕]*〕|\d+\s*号|该(?:解释|意见|办法|规定|条例|通知|法)|'
                     r'[^\s，。；：、（）「」]{0,8}(?:法|条例|办法|规定|准则|细则|公约))$')
ENTRY_HEAD = re.compile(r'^### (\d+)\. (.*)$')
DOC_HEAD = re.compile(r'^#{1,6}\s+(.+?)\s*$')
HAN = re.compile(r'^[一-龥]+$')
CLAUSE = '。；！？：，'
SENTENCE = '。；！？：'


@dataclass
class Ref:
    unit: str                      # where: 'book', 'intro' or 'doc'
    section: int                   # source section (0 for a long article)
    entry: int                     # source entry number (0 for an intro or article)
    target: tuple[int, int]
    title: str | None              # the target's title, None when it does not exist
    expanded: bool                 # came from a range; anchors are not checked for those
    anchored: bool = True
    context: str = ''


@dataclass
class Scan:
    refs: list[Ref] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def numbers(spec: str) -> list[tuple[int, bool]]:
    """「3、10」 → [(3, False), (10, False)]; 「11 到 14」 → each with True."""
    found: list[tuple[int, bool]] = []
    for part in re.split(r'[、,]', spec):
        r = RANGE_RE.match(part)
        if r:
            a, b = int(r.group(1)), int(r.group(2))
            if 0 <= b - a <= 30:
                found += [(i, True) for i in range(a, b + 1)]
            continue
        if part.strip().isdigit():
            found.append((int(part.strip()), False))
    return found


def _context(line: str, idx: int) -> str:
    before = line[:idx]
    start = max(before.rfind(p) for p in SENTENCE)
    return before[start + 1:][-44:]


def _narrow(line: str, idx: int) -> str:
    before = line[:idx]

    def cut(s: str) -> tuple[str, str]:
        start = max(s.rfind(p) for p in CLAUSE)
        return s[:start + 1], s[start + 1:]
    head, tail = cut(before)
    if len(re.sub(r'[见按同和依据参照的在]', '', tail)) >= 4:
        return tail[-24:]
    return (cut(head[:-1])[1] + tail)[-24:]


def _after(line: str, idx: int) -> str:
    rest = re.sub(rf'^第\s*\d+\s*节?第?\s*(?:{SPEC})?\s*条', '', line[idx:])
    end = re.search(r'[。；！？]', rest)
    return (rest[:end.start()] if end else rest)[:40]


def _longest(text: str, title: str) -> int:
    best = 0
    for i in range(len(text)):
        n = 1
        while i + n <= len(text):
            seg = text[i:i + n]
            if not HAN.match(seg) or seg not in title:
                break
            best = max(best, n)
            n += 1
    return best


def _anchored(ref_ctx: str, narrow: str, after: str, title: str) -> bool:
    wide = ref_ctx + after
    if any(t in title for t in re.findall(r'[0-9A-Za-z]{2,}', wide)) or _longest(wide, title) >= 3:
        return True
    return _longest(narrow + after, title) >= 2


def scan(books: dict[int, str], docs: dict[str, str]) -> Scan:
    """``books``: section number → file text; ``docs``: path → article text."""
    titles = {sec: {int(m.group(1)): m.group(2).strip() for m in map(ENTRY_HEAD.match, text.splitlines()) if m}
              for sec, text in books.items()}
    result = Scan()
    units = [('book', sec, text) for sec, text in sorted(books.items())] + \
            [('doc', 0, text) for _, text in sorted(docs.items())]
    for kind, sec, text in units:
        cur = 0
        for no, line in enumerate(text.splitlines(), 1):
            if kind == 'doc':
                if DOC_HEAD.match(line):
                    continue
            else:
                head = ENTRY_HEAD.match(line)
                if head:
                    cur = int(head.group(1))
                    continue
            in_entry = kind == 'book' and cur > 0
            if (not CROSS_FIELDS.match(line)) if in_entry else not line.strip():
                continue
            where = f'第 {sec} 节第 {cur} 条' if in_entry else (f'第 {sec} 节节首' if kind == 'book' else '长文')
            for m in RELATIVE_RE.finditer(line):
                result.problems.append(f'{where}第 {no} 行用了相对指路「{m.group(1)}」')
            unit = 'book' if in_entry else ('intro' if kind == 'book' else 'doc')
            for m in CROSS_RE.finditer(line):
                for x, expanded in numbers(m.group(2)):
                    tsec = int(m.group(1))
                    title = titles.get(tsec, {}).get(x)
                    result.refs.append(Ref(unit, sec, cur, (tsec, x), title, expanded, context=_context(line, m.start())))
                    if title is None:
                        result.problems.append(f'{where}引用第 {tsec} 节第 {x} 条——该节没有这一条')
                    else:
                        result.refs[-1].anchored = expanded or _anchored(
                            _context(line, m.start()), _narrow(line, m.start()), _after(line, m.start()), title)
            if kind == 'doc' or (in_entry and not FIELDS.match(line)):
                continue
            stripped = CROSS_RE.sub('', line)
            for m in BARE_RE.finditer(stripped):
                if CITE_RE.search(stripped[:m.start()].rstrip()):
                    continue
                for x, expanded in numbers(m.group(1)):
                    title = titles[sec].get(x)
                    result.refs.append(Ref(unit, sec, cur, (sec, x), title, expanded, context=_context(stripped, m.start())))
                    if title is None:
                        result.problems.append(f'{where}引用第 {x} 条——本节只有 {len(titles[sec])} 条')
                    elif in_entry and x == cur:
                        result.problems.append(f'{where}引用了它自己')
                    else:
                        result.refs[-1].anchored = expanded or _anchored(
                            _context(stripped, m.start()), _narrow(stripped, m.start()),
                            _after(stripped, m.start()), title)
    return result
