#!/usr/bin/env python
"""Freeze 《高性价比人生指南》 (eternity4719/HowToLiveBetter) into assets/life_guide.json.

Maintenance tool, excluded from the runtime package. It reads the GitHub
codeload ZIP directly and refuses any ZIP whose embedded commit is not the
pinned one, so the frozen text cannot drift from a folder edited by hand.

Every entry keeps its six fields verbatim, its machine cost tags, its grade and
whether it is marked TODO or disputed. Two entries are left out on purpose,
by number, as a product-scope decision recorded in the output: this skill
does not carry the book's verdicts on the efficacy of divination itself.
Exclusion is by reviewed number, never by keyword — 21:4's 「医疗转运」 would
match 转运 and is kept.

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
REGION_OVERRIDES: dict[tuple[int, int], str] = {}

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
# 「第 22 条」 (this section's entry 22). Chinese-numeral law articles such as
# 「第二十六条」 do not match; an Arabic one in a section with an excluded
# entry does, and then needs review — a false alarm fails safe.
REF_RE = re.compile(r'第\s*(\d+)\s*节(?:第\s*(\d+)\s*条)?|本节第\s*(\d+)\s*条|第\s*(\d+)\s*条')


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
    return {'section': section, 'section_title': section_title, 'number': number, 'title': title,
            'cost_tags': cost_tags, 'fields': fields, 'grade': grade,
            'todo': bool(re.search(r'TODO|待核实', block)), 'disputed': '争议' in fields['备注'],
            'region': _region(section, number)}


def _cross_refs(entry: dict) -> list[dict]:
    text = '\n'.join(entry['fields'].values())
    excluded_sections = {s for s, _ in EXCLUDED}
    flags = []

    def flag(section: int, number: int, found: str) -> None:
        key = (entry['section'], entry['number'], section, number)
        flags.append({'from': [entry['section'], entry['number']], 'to': [section, number],
                      'text': found, 'resolution': REVIEWED_CROSS_REFS.get(key)})

    for match in REF_RE.finditer(text):
        section = int(match.group(1)) if match.group(1) else entry['section']
        number = match.group(2) or match.group(3) or match.group(4)
        if number is None:
            if section in excluded_sections:
                flag(section, 0, match.group(0))
        elif (section, int(number)) in EXCLUDED:
            flag(section, int(number), match.group(0))
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
    if {(x['section'], x['number']) for x in excluded} != set(EXCLUDED):
        raise ValueError('排除清单里有条目在快照中找不到，编号可能已变化')
    cross = [flag for entry in entries for flag in _cross_refs(entry)]
    unreviewed = [flag for flag in cross if not flag['resolution']]
    if unreviewed:
        raise ValueError('保留条目引用了被排除条目，须先人工审定：' + json.dumps(unreviewed, ensure_ascii=False))
    return {
        'schema_version': '1.0',
        'title': '高性价比人生指南',
        'purpose': '现实参考资料库：只在术数回答之后单独成段，不参与择日、配色等术数排序。',
        'source': {'repo': REPO, 'commit': COMMIT, 'snapshot_date': SNAPSHOT_DATE,
                   'license': 'Unlicense', 'files': files},
        'region_policy': {'universal_sections': sorted(UNIVERSAL_SECTIONS),
                          'abroad_sections': sorted(ABROAD_SECTIONS),
                          'default': '中国大陆', 'overrides': len(REGION_OVERRIDES)},
        'excluded': excluded,
        'cross_refs_to_excluded': cross,
        'entries': entries,
    }


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='把《高性价比人生指南》固定快照导入 assets/life_guide.json；维护工具，不进运行包',
        epilog='Writes assets/life_guide.json. Top-level JSON keys: schema_version title purpose '
               'source region_policy excluded cross_refs_to_excluded entries')
    parser.add_argument('--zip', type=Path, required=True, help='GitHub codeload ZIP，注释须为固定提交')
    args = parser.parse_args(argv)
    try:
        data = build(args.zip)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f'导入失败：{exc}', file=sys.stderr)
        return 1
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{OUTPUT.relative_to(ROOT)}：{len(data["entries"])} 条，排除 {len(data["excluded"])} 条，'
          f'提交 {COMMIT[:12]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
