"""规则登记表：每条规则串成「出处段落 → 规则 → 实现函数 → 测试 → 授权」一条链，任何一环断了就报出来。

规则本身仍住在原处（assets/*.json 或模块里的 SPECS 表），这里只把它们逐条列举并核链：
- 出处：古籍库段落能取到（get_passage），或资产自带的外部来源有网址；现代约定须明标 modern_convention。
- 实现：module:function 能导入、可调用。
- 测试：列出的测试文件存在，且提到实现模块名。
- 授权：古籍库段落取 knowledge/manifest.json 该书的 license；外部网址按网站对上库中同站书目的 license。

CLI:
    python rule_registry.py            # 各族汇总与断链
    python rule_registry.py --family liuyao
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from classical_search import get_passage
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

ROOT = Path(__file__).resolve().parents[1]
# Tests live at the repository root, two levels above the skill folder.
REPO = ROOT.parents[1]
MODERN = 'modern_convention'


def _asset(name: str) -> dict:
    return json.loads((ROOT / 'assets' / name).read_text(encoding='utf-8'))


def _rule(rule_id: str, passages: list[str] | None = None, urls: list[str] | None = None,
          status: str = 'sourced') -> dict:
    return {'id': rule_id, 'passages': list(passages or []), 'urls': list(urls or []), 'status': status}


def _bazi_routes() -> list[dict]:
    return [_rule(r['id'], [r['passage_id']]) for f in _asset('bazi_rules.json')['families'] for r in f['routes']]


def _luck() -> list[dict]:
    return [_rule(s['id'], [s['passage_id']]) for f in _asset('luck_rules.json')['families'] for s in f['scenarios']]


def _geju() -> list[dict]:
    return [_rule(r['id'], [r['passage_id']]) for r in _asset('geju_rules.json')['rules']]


def _liuyao() -> list[dict]:
    return [_rule(r['id'], [r['passage_id'], *r.get('context_passage_ids', [])]) for r in _asset('liuyao_rules.json')['rules']]


def _hehun() -> list[dict]:
    return [_rule(c['id'], [c['passage_id']]) for c in _asset('hehun_clauses.json')['clauses']]


def _external(asset: str, url_key: str) -> list[dict]:
    data = _asset(asset)
    urls = {s['id']: s.get(url_key) for s in data['sources']}
    return [_rule(r['id'], urls=[urls.get(i) or f'missing-source:{i}' for i in r['source_ids']]) for r in data['rules']]


def _tiaohou() -> list[dict]:
    cells = _asset('tiaohou_provenance.json')['cells']
    return [_rule('tiaohou:' + key, [ref['passage_id'] for ref in cell.get('source_refs', [])])
            for key, cell in cells.items()]


def _ziwei_patterns() -> list[dict]:
    from ziwei_patterns import SPECS
    return [_rule('ziwei:' + s.name, [s.passage_id, *s.extra] if s.passage_id else [],
                  status='sourced' if s.passage_id else MODERN) for s in SPECS]


def _sanyuan() -> list[dict]:
    from sanyuan_hehun import DISSENT, SOURCE_IDS
    return [_rule('sanyuan-jiugong', [*SOURCE_IDS, DISSENT['passage_id']])]


def _liuyao_plan() -> list[dict]:
    from liuyao_plan import SOURCES
    return [_rule('liuyao-plan:' + key, [pid]) for key, pid in SOURCES.items()]


def _qimen_plate() -> list[dict]:
    from qimen_zhuanpan import SOURCES
    return [_rule('qimen-zhuanpan', list(SOURCES))]


def _qimen_patterns() -> list[dict]:
    from qimen_patterns import CODED_RULES, NOT_COMPUTED, SPECS
    rows = [_rule(f'qimen:{name}:{quote}', [pid]) for name, _, pid, quote, _, _ in SPECS]
    rows += [_rule(f'qimen:{name}', [pid]) for name, pid in CODED_RULES]
    rows += [_rule(f"qimen-not-computed:{row['name']}", [row['passage_id']], status='not_computed')
             for row in NOT_COMPUTED]
    return rows


def _liuren() -> list[dict]:
    from liuren_cast import BRANCH_SOURCES
    return [_rule('liuren:' + name, list(pids)) for name, pids in BRANCH_SOURCES.items()]


PASSAGE_LITERAL = re.compile(r'(?<![a-z])[a-z]+:c\d{3}:p\d{4}(?!\d)')


def _cited_in(module: str) -> Callable[[], list[dict]]:
    """Every passage id literal in a module's source is a rule citation that must resolve."""
    def rows() -> list[dict]:
        text = (ROOT / 'scripts' / f'{module}.py').read_text(encoding='utf-8')
        return [_rule(f'{module}:{pid}', [pid]) for pid in sorted(set(PASSAGE_LITERAL.findall(text)))]
    return rows


# 规则散在模块常量里的，按模块登记；实现取该模块对外的判定函数。
CODE_CITED = [
    ('annual_assessment', '流年评估', 'annual_assessment:assess_year', ('tests/test_annual_assessment.py',)),
    ('fortune_rules', '择日裁决顺序', 'fortune_rules:capabilities', ('tests/test_capability_table.py',)),
    ('fortune_ranking', '择日排序', 'fortune_ranking:day_prohibitions', ('tests/test_ranking.py',)),
    ('fortune_selection', '择时比较', 'fortune_selection:compare_candidates', ('tests/test_selection_workflow.py',)),
    ('xiangzhu', '协纪相主', 'xiangzhu:na_yin_row', ('tests/test_xiangzhu.py',)),
    ('xieji_days', '协纪日宜忌', 'xieji_days:prohibitions', ('tests/test_xieji_days.py',)),
    ('wuxing_colours', '五行颜色', 'wuxing_colours:aspects_asked', ('tests/test_wuxing_colours.py',)),
    ('ziwei_minor', '紫微杂曜', 'ziwei_minor:minor_note', ('tests/test_ziwei_minor.py',)),
    ('ziwei_horoscope', '紫微流曜', 'ziwei_horoscope:layer_stars', ('tests/test_ziwei_horoscope.py',)),
    ('liuyao_cast', '六爻用神与伏神', 'liuyao_cast:hidden_spirits', ('tests/test_liuyao_fushen.py',)),
    ('qimen_cast', '元灵经核心', 'qimen_cast:source_core', ('tests/test_qimen_liuren_oracle.py',)),
    ('qimen_select', '奇门择时', 'qimen_select:judge', ('tests/test_qimen_patterns.py',)),
    ('bazi_rules', '子平取用（模块内）', 'bazi_rules:assess_rules', ('tests/test_bazi_rules.py',)),
    ('geju_assessment', '格局（模块内）', 'geju_assessment:assess_geju', ('tests/test_geju_assessment.py',)),
    ('liuyao_judge', '六爻规则自动判', 'liuyao_judge:judge', ('tests/test_liuyao_judge.py',)),
    ('pair_facts', '合盘事实', 'pair_facts:pair_facts', ('tests/test_pair_facts.py',)),
    ('answer_check', '回答核对', 'answer_check:check_answer', ('tests/test_answer_check.py',)),
    ('fortune_reading', '运势读法', 'fortune_reading:outlook_skeleton', ('tests/test_answer_length.py',)),
    ('ziwei_gods', '紫微流年神煞', 'ziwei_gods:twelve_gods', ('tests/test_ziwei_schools.py',)),
    ('fengshui_measure', '风水测量合同', 'fengshui_measure:measure', ('tests/test_fengshui_measure.py',)),
    ('zibai', '紫白九星', 'zibai:zibai', ('tests/test_zibai.py',)),
    ('life_areas', '人生领域速读', 'life_areas:life_areas', ('tests/test_life_areas.py',)),
    ('liuyao_timing', '六爻应期候选', 'liuyao_timing:timing', ('tests/test_liuyao_timing.py',)),
    ('meihua_cast', '梅花取数与应期', 'meihua_cast:timing', ('tests/test_meihua_methods.py',)),
]


@dataclass(frozen=True)
class Family:
    id: str
    title: str
    implementer: str
    tests: tuple[str, ...]
    rules: Callable[[], list[dict]]


FAMILIES = [
    Family('bazi-routes', '子平真诠取用路线', 'bazi_rules:assess_rules', ('tests/test_bazi_rules.py',), _bazi_routes),
    Family('bazi-luck', '子平真诠行运', 'luck_assessment:assess_luck',
           ('tests/test_luck_assessment.py', 'tests/test_luck_expansion.py'), _luck),
    Family('geju', '子平真诠格局候选', 'geju_assessment:assess_geju', ('tests/test_geju_assessment.py',), _geju),
    Family('tiaohou', '穷通宝鉴调候', 'tiaohou_provenance:get_tiaohou_audit', ('tests/test_method_rules.py',),
           _tiaohou),
    Family('liuyao', '增删卜易规则库', 'liuyao_judge:judge', ('tests/test_liuyao_judge.py',), _liuyao),
    Family('liuyao-plan', '六爻解读次序', 'liuyao_plan:plan', ('tests/test_liuyao_plan.py',), _liuyao_plan),
    Family('hehun', '合婚条款', 'pair_facts:clause_refs', ('tests/test_pair_facts.py',), _hehun),
    Family('sanyuan-hehun', '三元九宫合婚', 'sanyuan_hehun:match', ('tests/test_sanyuan_hehun.py',), _sanyuan),
    Family('ziwei-patterns', '紫微格局', 'ziwei_patterns:detect_patterns', ('tests/test_ziwei_patterns.py',),
           _ziwei_patterns),
    Family('qimen-plate', '遁甲演义转盘', 'qimen_zhuanpan:plate', ('tests/test_qimen_patterns.py',), _qimen_plate),
    Family('qimen-patterns', '遁甲演义格局', 'qimen_patterns:detect', ('tests/test_qimen_patterns.py',),
           _qimen_patterns),
    Family('liuren-transmission', '六壬大全取传', 'liuren_cast:fa_yong', ('tests/test_qimen_liuren_oracle.py',),
           _liuren),
    Family('method-rules', '紫微六爻方法条款', 'method_rules:method_reading_packet', ('tests/test_method_rules.py',),
           lambda: _external('method_rules.json', 'source_url')),
    Family('classical-evidence', '八字古籍证据', 'reading_support:load_evidence', ('tests/test_reading_support.py',),
           lambda: _external('classical_evidence.json', 'url')),
    *(Family('code:' + module, title, impl, tests, _cited_in(module)) for module, title, impl, tests in CODE_CITED),
]


@lru_cache(maxsize=1)
def _licenses() -> tuple[dict, dict]:
    books = json.loads((ROOT / 'knowledge' / 'manifest.json').read_text(encoding='utf-8'))['books']
    by_book = {b['id']: b['license'] for b in books}
    by_host: dict[str, dict] = {}
    for b in books:
        for url in [b.get('source_url'), *(c.get('source_url') for c in b.get('chapters', []))]:
            if url:
                by_host.setdefault(urlparse(url).netloc, b['license'])
    return by_book, by_host


@cache
def _passage_ok(pid: str) -> bool:
    try:
        return bool(get_passage(pid)['text'])
    except (KeyError, ValueError, FileNotFoundError):
        return False


def _implementer_ok(spec: str) -> bool:
    module, _, attr = spec.partition(':')
    try:
        return callable(getattr(importlib.import_module(module), attr))
    except (ImportError, AttributeError):
        return False


def _tests_ok(family: Family) -> list[str]:
    module = family.implementer.partition(':')[0]
    missing = []
    for test in family.tests:
        path = REPO / test
        if not path.is_file() or module not in path.read_text(encoding='utf-8'):
            missing.append(test)
    return missing


def chain(family: Family, rule: dict) -> dict:
    by_book, by_host = _licenses()
    problems = []
    licenses = {}
    if rule['status'] == MODERN:
        if rule['passages'] or rule['urls']:
            problems.append('modern_convention_with_source')
    elif not rule['passages'] and not rule['urls']:
        problems.append('no_source')
    for pid in rule['passages']:
        if not _passage_ok(pid):
            problems.append(f'passage_missing:{pid}')
        book = pid.split(':')[0]
        if by_book.get(book):
            licenses[book] = by_book[book]
        else:
            problems.append(f'no_license:{book}')
    for url in rule['urls']:
        host = urlparse(url).netloc
        if not host:
            problems.append(f'bad_url:{url}')
        elif by_host.get(host):
            licenses[host] = by_host[host]
        else:
            problems.append(f'no_license:{host}')
    return {**rule, 'family': family.id, 'implementer': family.implementer, 'tests': list(family.tests),
            'licenses': licenses, 'problems': problems}


def build(family_id: str | None = None) -> dict:
    families = [f for f in FAMILIES if family_id in (None, f.id)]
    if not families:
        raise ValueError(f'unknown family: {family_id}')
    summary, chains, broken = [], [], []
    for family in families:
        rows = [chain(family, rule) for rule in family.rules()]
        family_problems = ([] if _implementer_ok(family.implementer) else ['implementer_missing']) + [
            f'test_missing_or_unrelated:{t}' for t in _tests_ok(family)]
        summary.append({'id': family.id, 'title': family.title, 'implementer': family.implementer,
                        'tests': list(family.tests), 'rules': len(rows), 'problems': family_problems})
        broken += [{'family': family.id, 'problem': p} for p in family_problems]
        broken += [{'family': family.id, 'rule': r['id'], 'problem': p} for r in rows for p in r['problems']]
        chains += rows
    return {'families': summary, 'rules': chains, 'broken': broken, 'total_rules': len(chains)}


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version families total_rules broken [rules when --family is given]

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='规则登记表：出处、规则、实现、测试、授权逐条核链', epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--family', help='只列这一族并给出逐条链: ' + ', '.join(f.id for f in FAMILIES))
    args = parser.parse_args(argv)
    try:
        result = build(args.family)
    except ValueError as exc:
        json_print(error_envelope('rule_registry', 'unknown_family', str(exc)))
        return 1
    detail = {'families': result['families'], 'total_rules': result['total_rules'], 'broken': result['broken']}
    if args.family:
        detail['rules'] = result['rules']
    if result['broken']:
        json_print(error_envelope('rule_registry', 'broken_chain', f"{len(result['broken'])} 处断链，明细见 broken", **detail))
        return 1
    json_print({'ok': True, 'tool': 'rule_registry', 'version': __version__, **detail})
    return 0


if __name__ == '__main__':
    sys.exit(main())
