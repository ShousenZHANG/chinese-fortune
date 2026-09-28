#!/usr/bin/env python
"""Freeze 《高性价比人生指南》 (eternity4719/HowToLiveBetter) into assets/life_guide.json.

Maintenance tool, excluded from the runtime package. It reads the GitHub
codeload ZIP directly and refuses any ZIP whose embedded commit is not the
pinned one, so the frozen text cannot drift from a folder edited by hand.

Every entry keeps its six fields verbatim, its machine cost tags, its grade and
whether it is marked TODO or disputed. Three entries are left out on purpose,
by number, as a product-scope decision: this skill does not carry the book's
verdicts on divination. The exclusion list lives here and in the docs only;
the output holds no trace of those entries, not even their titles.
Exclusion is by reviewed number, never by keyword — 21:4's 「医疗转运」 would
match 转运 and is kept.

The long article docs/结婚划不划算.md is frozen whole beside the entries.

    python scripts/import_life_guide.py --zip path/to/howtolivebetter-main.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

from utils import ensure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'assets' / 'life_guide.json'
REPO = 'https://github.com/eternity4719/HowToLiveBetter'
COMMIT = '8276caec9508c11c5c80a65440b17895023e2fb9'
SNAPSHOT_DATE = '2026-09-27'
FIELDS = ('成本', '说人话', '收益', '证据等级', '来源', '备注')

EXCLUDED = {
    (6, 15): '产品范围：本技能不收录评价付费算命、塔罗、星座有效性的条目',
    (6, 22): '产品范围：本技能不收录评价转运、招财物件有效性的条目',
    (29, 12): '产品范围：备注把算命列为针对丧亲者和老人的骗局（指向第 6 节第 15 条），同样不收录',
}
# Words that mark an entry as passing judgement on divination. The run fails
# on any kept entry containing one until it is excluded or reviewed. Not 转运:
# the book uses it for 医疗转运.
DIVINATION_WORDS = ('算命', '占卜', '塔罗', '星座', '风水', '招财', '开光', '命理', '玄学', '八字')

# Conservative: a section with any law, policy or hotline content is 中国大陆
# until an entry is individually reviewed as universal. Only plainly
# research-based sections default to 通用.
UNIVERSAL_SECTIONS = {2, 3, 4, 22, 28}
ABROAD_SECTIONS = {21, 32}
# Reviewed by hand, entry by entry (2026-09-28): every entry in a 中国大陆
# section whose title, 说人话, 收益 and 备注 name no Chinese law, rule,
# institution, platform or hotline, and every entry in a 通用 section that
# does. 通用 means the advice rests on research or physical fact; Chinese
# statistics cited as background do not make it 中国大陆. An entry whose
# argument cites a Chinese rule (按规定, 监管要求, 交强险限额, 七日无理由,
# 2001 年以后的抗震规范, 国家免疫规划) stays 中国大陆 even when its title
# reads universal.
_TO_UNIVERSAL = {
    1: (2, 3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 34),
    5: (11, 15, 17, 18, 19, 21, 28, 37, 38),
    6: (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 18, 19, 20, 21, 23, 24, 25, 26),
    7: (14,),
    10: (1, 3, 4, 5, 6, 8, 9, 15, 17, 18),
    12: (18,),
    13: (5, 6, 9, 10, 14, 19, 32, 33, 34, 35, 41),
    14: (1, 3, 4),
    16: (1, 3, 4, 7, 8, 9),
    17: (3, 4, 8),
    18: (4, 6),
    20: (1, 2, 5, 7, 8, 9, 11),
    23: (2, 7, 10, 14, 15, 16, 17, 18, 19),
    27: (1, 4, 5, 6, 7, 10, 13),
    29: (2, 4, 5, 7, 8, 9),
    30: (1, 6),
    33: (5, 16),
}
_TO_MAINLAND = {2: (5,), 3: (19,), 22: (1, 2, 3, 4, 5, 6), 28: (2,)}
REGION_OVERRIDES: dict[tuple[int, int], str] = {
    **{(s, n): '通用' for s, ns in _TO_UNIVERSAL.items() for n in ns},
    **{(s, n): '中国大陆' for s, ns in _TO_MAINLAND.items() for n in ns},
}
# The book marks a dispute by opening a sentence with it: 「争议。」 followed by
# the other side, 「争议在于：…」, 「争议很大：…」. 「劳动争议」, 「结账有争议时」
# and 「本身没有争议」 are not such a mark.
DISPUTE_RE = re.compile(r'(?:^|(?<=[。！？]))\s*(争议(?:[。：:，,]|在|很大)[^。！？]*[。！？]?)')
ARTICLE = ('marriage', 'docs/结婚划不划算.md', '中国大陆')

# Kept entries that mention an excluded one, once reviewed. The run fails on
# any new mention that is not listed here. A reference to a whole section is
# keyed with entry number 0; a divination word with (0, 0).
REVIEWED_CROSS_REFS: dict[tuple[int, int, int, int], str] = {
    (6, 23, 29, 0): '指向第 29 节里情绪低落时的做法，不是被排除的第 12 条',
    (16, 4, 6, 0): '指向第 6 节里偏方、补充剂一类的无效花费，不是被排除的两条',
    (30, 8, 29, 0): '指向第 29 节里家人的应对，不是被排除的第 12 条',
    (30, 9, 6, 0): '指向第 6 节里防蓝光眼镜一条，不是被排除的两条',
}

ENTRY_RE = re.compile(r'^### (\d+)\. (.+)$', re.M)
TAG_RE = re.compile(r'<!--\s*成本标签:\s*(.*?)\s*-->')
# 「第 9 节第 20 条」, 「第 6 节」 (a whole section), 「本节第 24 条」 and a bare
# 「第 22 条」 (this section's entry 22), each with lists and ranges as the
# book writes them: 「第 29、30 条」, 「第 1 节第 17 到 19 条」. Chinese-numeral
# law articles such as 「第二十六条」 do not match; an Arabic one in a section
# with an excluded entry does, and then needs review — a false alarm fails safe.
LIST_SEP = r'\s*(?:、|和|及|与|或)\s*'
RANGE_SEP = r'\s*(?:至|到|-|—|–|~|～)\s*'
NUMS = rf'\d+(?:(?:{LIST_SEP}|{RANGE_SEP})\d+)*'
REF_RE = re.compile(rf'第\s*(\d+)\s*节(?:\s*第\s*({NUMS})\s*条)?|本节\s*第\s*({NUMS})\s*条|第\s*({NUMS})\s*条')
# 「本节「…」那条」: a reference by title, compared with the excluded titles.
QUOTE_RE = re.compile(r'「([^」]{4,60})」')


def _numbers(spec: str) -> list[int]:
    """「14、15」 → [14, 15]; 「17 到 19」 → [17, 18, 19]."""
    found: list[int] = []
    for part in re.split(LIST_SEP, spec):
        bounds = [int(n) for n in re.split(RANGE_SEP, part) if n]
        if len(bounds) == 2 and 0 <= bounds[1] - bounds[0] <= 50:
            found += range(bounds[0], bounds[1] + 1)
        else:
            found += bounds
    return found


def _region(section: int, number: int) -> str:
    if (section, number) in REGION_OVERRIDES:
        return REGION_OVERRIDES[(section, number)]
    if section in ABROAD_SECTIONS:
        return '中国公民在境外'
    return '通用' if section in UNIVERSAL_SECTIONS else '中国大陆'


def _entry(section: int, section_title: str, block: str) -> dict:
    head = ENTRY_RE.match(block)
    if not head:
        raise ValueError(f'第 {section} 节有无法识别的条目标题：{block[:40]!r}')
    number, title = int(head.group(1)), head.group(2).strip()
    fields = {}
    for name in FIELDS:
        found = re.search(rf'^- {name}：(.*)$', block, re.M)
        if not found or not found.group(1).strip():
            raise ValueError(f'第 {section} 节第 {number} 条缺「{name}」栏')
        fields[name] = found.group(1).strip()
    tags = TAG_RE.search(block)
    if not tags:
        raise ValueError(f'第 {section} 节第 {number} 条缺成本标签')
    cost_tags = dict(pair.split('=', 1) for pair in tags.group(1).split())
    grade = fields['证据等级'][:1]
    if grade not in 'ABC':
        raise ValueError(f'第 {section} 节第 {number} 条证据等级不是 A/B/C：{fields["证据等级"]!r}')
    dispute = _dispute(fields['备注'])
    return {'section': section, 'section_title': section_title, 'number': number, 'title': title,
            'cost_tags': cost_tags, 'fields': fields, 'grade': grade,
            'todo': bool(re.search(r'TODO|待核实', block)), 'disputed': dispute is not None,
            'dispute': dispute, 'region': _region(section, number)}


def _dispute(note: str) -> str | None:
    """The other side, verbatim: the sentence the mark opens, or the next one
    when the mark is only a short label (「争议。」, 「争议在无糖那一侧。」)."""
    found = DISPUTE_RE.search(note)
    if not found:
        return None
    text = found.group(1).strip()
    if len(text) <= 10:
        following = re.match(r'\s*([^。！？]+[。！？]?)', note[found.end():])
        if following:
            text += following.group(1).strip()
    return text


def _cross_refs(entry: dict, excluded_titles: dict[tuple[int, int], str]) -> list[dict]:
    text = '\n'.join(entry['fields'].values())
    excluded_sections = {s for s, _ in EXCLUDED}
    flags = []

    def flag(section: int, number: int, found: str) -> None:
        key = (entry['section'], entry['number'], section, number)
        flags.append({'from': [entry['section'], entry['number']], 'to': [section, number],
                      'text': found, 'resolution': REVIEWED_CROSS_REFS.get(key)})

    for match in REF_RE.finditer(text):
        section = int(match.group(1)) if match.group(1) else entry['section']
        spec = match.group(2) or match.group(3) or match.group(4)
        if spec is None:
            if section in excluded_sections:
                flag(section, 0, match.group(0))
            continue
        for number in _numbers(spec):
            if (section, number) in EXCLUDED:
                flag(section, number, match.group(0))
    for quoted in QUOTE_RE.findall(text):
        for (section, number), title in excluded_titles.items():
            if quoted in title or title in quoted:
                flag(section, number, f'「{quoted}」')
    for word in DIVINATION_WORDS:
        if word in entry['title'] or word in text:
            flag(0, 0, word)
    return flags


def build(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        commit = archive.comment.decode('ascii', 'replace').strip()
        if commit != COMMIT:
            raise ValueError(f'ZIP 提交是 {commit or "（无注释）"}，不是固定的 {COMMIT}')
        members = sorted(n for n in archive.namelist() if re.search(r'/book/\d{2}-[^/]+\.md$', n))
        files, entries, excluded = {}, [], []
        for name in members:
            raw = archive.read(name)
            base = name.rsplit('/', 1)[-1]
            files[base] = hashlib.sha256(raw).hexdigest()
            section, section_title = int(base[:2]), base[3:-3]
            for block in re.split(r'\r?\n(?=### )', raw.decode('utf-8')):
                if not block.startswith('### '):
                    continue
                entry = _entry(section, section_title, block)
                key = (entry['section'], entry['number'])
                if key in EXCLUDED:
                    excluded.append({'section': key[0], 'number': key[1], 'title': entry['title'],
                                     'reason': EXCLUDED[key]})
                    continue
                entries.append(entry)
        article = _article(archive, files)
    if {(x['section'], x['number']) for x in excluded} != set(EXCLUDED):
        raise ValueError('排除清单里有条目在快照中找不到，编号可能已变化')
    titles = {(x['section'], x['number']): x['title'] for x in excluded}
    # The article goes through the same checks, as a pseudo-entry of section 0.
    pseudo = {'section': 0, 'number': 0, 'title': article['title'], 'fields': {'全文': article['text']}}
    cross = [flag for entry in [*entries, pseudo] for flag in _cross_refs(entry, titles)]
    unreviewed = [flag for flag in cross if not flag['resolution']]
    if unreviewed:
        raise ValueError('保留条目引用了被排除条目，须先人工审定：' + json.dumps(unreviewed, ensure_ascii=False))
    # Nothing about the excluded entries is written: not their titles, not
    # the references to them (those resolutions stay in REVIEWED_CROSS_REFS).
    return {
        'schema_version': '1.1',
        'title': '高性价比人生指南',
        'purpose': '现实参考资料库：只在术数回答之后单独成段，不参与择日、配色等术数排序。',
        'source': {'repo': REPO, 'commit': COMMIT, 'snapshot_date': SNAPSHOT_DATE,
                   'license': 'Unlicense', 'files': files},
        'region_policy': {'universal_sections': sorted(UNIVERSAL_SECTIONS),
                          'abroad_sections': sorted(ABROAD_SECTIONS),
                          'default': '中国大陆', 'overrides': len(REGION_OVERRIDES)},
        'articles': [article],
        'entries': entries,
    }


def _article(archive: zipfile.ZipFile, files: dict[str, str]) -> dict:
    key, path, region = ARTICLE
    name = next((n for n in archive.namelist() if n.endswith('/' + path)), None)
    if name is None:
        raise ValueError(f'快照里没有长文 {path}')
    raw = archive.read(name)
    files[path] = hashlib.sha256(raw).hexdigest()
    text = raw.decode('utf-8')
    head = re.match(r'#\s+(.+)', text)
    if not head:
        raise ValueError(f'长文 {path} 没有一级标题')
    return {'id': key, 'path': path, 'title': head.group(1).strip(), 'region': region, 'text': text}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='把《高性价比人生指南》固定快照导入 assets/life_guide.json；维护工具，不进运行包',
        epilog='Writes assets/life_guide.json. Top-level JSON keys: schema_version title purpose '
               'source region_policy articles entries')
    parser.add_argument('--zip', type=Path, required=True, help='GitHub codeload ZIP，注释须为固定提交')
    args = parser.parse_args(argv)
    try:
        data = build(args.zip)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f'导入失败：{exc}', file=sys.stderr)
        return 1
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{OUTPUT.relative_to(ROOT)}：{len(data["entries"])} 条，排除 {len(EXCLUDED)} 条，长文 {len(data["articles"])} 篇，'
          f'提交 {COMMIT[:12]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
