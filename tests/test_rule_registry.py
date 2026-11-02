"""规则登记表：每条规则都有出处、实现、测试、授权一条链。"""
import re
from pathlib import Path

import rule_registry
from conftest import run_cli
from rule_registry import CODE_CITED, FAMILIES, MODERN, Family, _rule, build, chain

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune/scripts'
# 这些模块的出处走 JSON 资产或 SPECS 表，由对应的族登记。
SPEC_BACKED = {'liuren_cast', 'liuyao_plan', 'qimen_patterns', 'qimen_zhuanpan', 'sanyuan_hehun', 'ziwei_patterns'}


def test_every_rule_has_a_complete_chain():
    result = build()
    assert result['broken'] == []
    assert result['total_rules'] >= 500
    for row in result['rules']:
        assert row['licenses'] or row['status'] == MODERN, row['id']
        assert row['implementer'] and row['tests']


def test_every_module_that_cites_a_passage_is_registered():
    covered = {module for module, *_ in CODE_CITED} | SPEC_BACKED
    citing = {path.stem for path in SCRIPTS.glob('*.py')
              if rule_registry.PASSAGE_LITERAL.search(path.read_text(encoding='utf-8'))}
    citing -= {'rule_registry'}
    assert citing <= covered, sorted(citing - covered)


def test_ids_are_unique_within_each_family():
    for family in FAMILIES:
        ids = [rule['id'] for rule in family.rules()]
        assert len(ids) == len(set(ids)), family.id


def test_a_broken_link_is_reported_not_hidden():
    fake = Family('fake', '假族', 'no_such_module:nothing', ('tests/no_such_test.py',),
                  lambda: [_rule('x', ['liuyao:c999:p9999']), _rule('y'), _rule('z', ['zengshan:c008:p0001'], status=MODERN)])
    problems = [p for rule in fake.rules() for p in chain(fake, rule)['problems']]
    assert any(p.startswith('passage_missing') for p in problems)
    assert 'no_source' in problems and 'modern_convention_with_source' in problems
    assert rule_registry._implementer_ok(fake.implementer) is False
    assert rule_registry._tests_ok(fake) == ['tests/no_such_test.py']


def test_family_listing_and_unknown_family():
    got = run_cli('rule_registry.py', '--family', 'liuren-transmission')
    assert got['ok'] and {r['id'] for r in got['rules']} >= {'liuren:涉害', 'liuren:别责', 'liuren:昴星'}
    assert all(re.match(r'liuren:c\d{3}:p\d{4}$', pid) for r in got['rules'] for pid in r['passages'])
    bad = run_cli('rule_registry.py', '--family', 'nope', expect_rc=1)
    assert bad['ok'] is False
