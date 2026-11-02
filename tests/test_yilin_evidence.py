"""Real Yilin source results retain edition and missing-text boundaries in checking."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from answer_check import check_answer
from conftest import run_cli

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evals'))
import check_claude_answers


@pytest.fixture(scope='module')
def source():
    return run_cli('yilin_lookup.py', '--from', '復', '--to', '鼎')


@pytest.mark.parametrize('args', [('--from', '復', '--to', '鼎'),
                                  ('--from', '豐', '--to', '晉'), ('--from', '乾')])
def test_public_checker_admits_real_single_missing_and_complete_yilin_sources(args):
    facts = run_cli('yilin_lookup.py', *args)
    result = check_answer('两个版本分别列出，缺文与待定归属保留。', [facts])
    assert result['passed'], result
    assert result['checked']['facts_loaded'] == 1
    assert result['checked']['chart_facts_loaded'] == 0


def test_recorded_yilin_invocation_keeps_its_own_real_facts(source):
    record = {'turns': [{'tools': [{'argv': ['python', 'scripts/yilin_lookup.py', '--from', '復', '--to', '鼎'],
                                  'output': json.dumps(source, ensure_ascii=False)}]}]}
    assert check_claude_answers.tool_facts(record) == [source]


def test_yilin_fact_admission_never_authorizes_fabricated_quotation(source):
    result = check_answer('《焦氏易林》说：“专属测试伪句保证人人财运第一。”', [source])
    assert not result['passed']
    assert any(f['code'] == 'unverified_quote' for f in result['findings'])
    assert not any(f['code'] == 'invalid_facts' for f in result['findings'])


@pytest.mark.parametrize('mutation', ['shell', 'duplicate_edition', 'missing_hash', 'missing_reason', 'empty_collection'])
def test_yilin_admission_rejects_unusable_source_shapes(source, mutation):
    facts = deepcopy(source)
    if mutation == 'shell':
        facts = {'ok': True, 'tool': 'yilin'}
    elif mutation == 'duplicate_edition':
        facts['lin']['versions'][1] = deepcopy(facts['lin']['versions'][0])
    elif mutation == 'missing_hash':
        facts['lin']['versions'][0].pop('sha256')
    elif mutation == 'missing_reason':
        facts['lin']['versions'][0].update(text=None, passage_id=None)
    else:
        facts.pop('lin')
        facts['lins'] = []
        facts['query']['to'] = None
    result = check_answer('按两个版本核对。', [facts])
    assert not result['passed']
    assert any(f['code'] == 'invalid_facts' for f in result['findings'])
