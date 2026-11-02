"""回答核对的冻结样本：第三、四轮外部核验样本加 v6.0 改义省略样本，逐条比对检查器与标注。

tracked 列出已知不一致（漏检或误报）、尚未修的样本；检查器结果与 tracked 必须完全吻合，
修好一条或新坏一条都会让这里失败，从而把误报和漏检的变化记账。
冻结片段只测试内部断言；公共信封准入另由 test_evidence_admission.py 覆盖。
"""
import json
from pathlib import Path

import pytest
from answer_check import _check_assertions

DATA = json.loads((Path(__file__).resolve().parent / 'data' / 'answer_check_frozen.json').read_text(encoding='utf-8'))


def observed(sample: dict) -> str:
    facts = [DATA['facts_table'][key] for key in sample['facts']]
    return 'must_pass' if _check_assertions(sample['answer'], facts)['passed'] else 'must_flag'


def test_disagreements_are_exactly_the_tracked_ones():
    wrong = sorted(s['id'] for s in DATA['samples'] if observed(s) != s['expected'])
    assert wrong == sorted(DATA['tracked'])


def test_metrics_on_the_frozen_set():
    cells = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
    for sample in DATA['samples']:
        flag_expected, flag_seen = sample['expected'] == 'must_flag', observed(sample) == 'must_flag'
        cells[('T' if flag_expected == flag_seen else 'F') + ('P' if flag_seen else 'N')] += 1
    assert cells['FP'] == 0 and cells['FN'] == 0, cells
    assert sum(cells.values()) == len(DATA['samples']) >= 80


@pytest.mark.parametrize('sample_id', ['a4-avoid-verb', 'a4-modal-chain', 'a4-truncated-start'])
def test_meaning_changing_elisions_are_named(sample_id):
    sample = next(s for s in DATA['samples'] if s['id'] == sample_id)
    findings = _check_assertions(sample['answer'], [])['findings']
    assert [f['code'] for f in findings] == ['elision_drops_negation']
