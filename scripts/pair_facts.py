"""Facts between two charts: which pillars of A and B combine, clash, punish or harm.

The compatibility route computes each person's chart separately; the host then
compared the two by hand, which was the slowest task in the 24-task host run
and easy to get wrong. This lists every cross-chart relation the single-chart
tables define, position by position, plus each day master's 十神 as seen from
the other. It classifies relations; it does not judge them. Whether a classical
text applies a relation between two people's charts, and what it would mean for
a marriage or a parent and child, is a separate, sourced question
(references/14-hehun.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import product

from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from bazi_tables import (
    DIZHI_CHONG,
    DIZHI_HAI,
    DIZHI_LIU_HE,
    PILLAR_LABELS_CN,
    SAN_HE_GROUPS,
    SAN_HUI_GROUPS,
    SAN_XING_PAIRS,
    SAN_XING_SELF,
    SAN_XING_TRIPLES,
    TIANGAN_HE,
)
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print, shi_shen

ORDER = ('year', 'month', 'day', 'hour')
BIRTH_KEYS = ('year', 'month', 'day', 'hour', 'minute', 'gender', 'timezone', 'longitude', 'city', 'sect', 'lunar')
BOUNDARY = ('关系分类事实：哪一柱和哪一柱构成合、冲、刑、害。不是婚姻、亲子或合作好坏的判断，'
            '也没有分数；跨盘能否这样用、怎样解释，要按原文逐条核对。')
NOTES = ('canggan_he 列出两支藏干之间的天干五合，常被称为暗合；哪些支算暗合各家取法不同，只作候选事实。',
         '同一对地支可能同时是六合与刑（如巳申），两条都列出，不互相抵消。',
         '时辰未知的一方不使用时柱；其余三柱照常比较。')


def subject_chart(birth: dict) -> dict:
    """One person's chart from a birth request; unknown hour stays unknown."""
    unknown = set(birth) - set(BIRTH_KEYS)
    if unknown:
        raise ValueError('unknown birth fields: ' + ', '.join(sorted(unknown)))
    args: list[str] = []
    for key in BIRTH_KEYS:
        value = birth.get(key)
        if value is None or value is False:
            continue
        args += [f'--{key}'] if value is True else [f'--{key}', str(value)]
    chart = calculate_bazi(chart_parser().parse_args(args))
    if not chart.get('ok'):
        raise ValueError(chart.get('message') or chart.get('error') or 'chart failed')
    return chart


def _positions(chart: dict) -> list[dict]:
    pillars = chart['four_pillars']
    keep = [k for k in ORDER if k in pillars and (k != 'hour' or chart.get('hour_known', True))]
    return [{'pillar': k, 'label': PILLAR_LABELS_CN[k], **pillars[k]} for k in keep]


def _trio_kind(pair: frozenset[str]) -> list[str]:
    kinds = []
    if any(pair <= set(trio) for trio, _ in SAN_HE_GROUPS):
        kinds.append('ban_san_he')
    if any(pair <= set(trio) for trio, _ in SAN_HUI_GROUPS):
        kinds.append('ban_san_hui')
    if any(pair <= set(trio) for trio in SAN_XING_TRIPLES) or tuple(sorted(pair)) in {tuple(sorted(p)) for p in SAN_XING_PAIRS}:
        kinds.append('dizhi_xing')
    return kinds


def _pair_relations(a: dict, b: dict) -> list[dict]:
    where = {'a': a['label'], 'b': b['label']}
    rows = []
    stems = frozenset((a['stem'], b['stem']))
    if stems in TIANGAN_HE:
        rows.append({'kind': 'tiangan_he', 'a': where['a'] + '干' + a['stem'], 'b': where['b'] + '干' + b['stem'],
                     'transforms_to': TIANGAN_HE[stems]})
    sa, sb = where['a'] + '支' + a['branch'], where['b'] + '支' + b['branch']
    branches = frozenset((a['branch'], b['branch']))
    if a['branch'] == b['branch']:
        if a['branch'] in SAN_XING_SELF:
            rows.append({'kind': 'dizhi_xing', 'a': sa, 'b': sb, 'type': '自刑'})
    else:
        if branches in DIZHI_LIU_HE:
            rows.append({'kind': 'dizhi_liu_he', 'a': sa, 'b': sb, 'transforms_to': DIZHI_LIU_HE[branches]})
        if branches in DIZHI_CHONG:
            rows.append({'kind': 'dizhi_chong', 'a': sa, 'b': sb})
        if branches in DIZHI_HAI:
            rows.append({'kind': 'dizhi_hai', 'a': sa, 'b': sb})
        rows += [{'kind': kind, 'a': sa, 'b': sb} for kind in _trio_kind(branches)]
    for x, y in product(a['hidden_stems'], b['hidden_stems']):
        if frozenset((x, y)) in TIANGAN_HE:
            rows.append({'kind': 'canggan_he', 'a': sa, 'b': sb, 'stems': [x, y],
                         'transforms_to': TIANGAN_HE[frozenset((x, y))]})
    return rows


def _full_trios(a_pos: list[dict], b_pos: list[dict]) -> list[dict]:
    """Three-branch groups completed only by putting both charts together."""
    rows = []
    groups = [('san_he', trio, wx) for trio, wx in SAN_HE_GROUPS] + \
             [('san_hui', trio, wx) for trio, wx in SAN_HUI_GROUPS] + \
             [('san_xing', trio, None) for trio in SAN_XING_TRIPLES]
    for kind, trio, wx in groups:
        in_a = {p['branch'] for p in a_pos} & set(trio)
        in_b = {p['branch'] for p in b_pos} & set(trio)
        if in_a | in_b == set(trio) and in_a != set(trio) and in_b != set(trio):
            rows.append({'kind': kind, 'group': ''.join(trio), **({'transforms_to': wx} if wx else {}),
                         'from_a': [p['label'] + '支' + p['branch'] for p in a_pos if p['branch'] in trio],
                         'from_b': [p['label'] + '支' + p['branch'] for p in b_pos if p['branch'] in trio]})
    return rows


def pair_facts(chart_a: dict, chart_b: dict) -> dict:
    a_pos, b_pos = _positions(chart_a), _positions(chart_b)
    relations = [row for a, b in product(a_pos, b_pos) for row in _pair_relations(a, b)]
    dm_a, dm_b = chart_a['four_pillars']['day']['stem'], chart_b['four_pillars']['day']['stem']
    return {
        'ok': True, 'tool': 'pair_facts', 'version': __version__, 'schema_version': '1.0',
        'subjects': {name: {'four_pillars': {p['pillar']: p['ganzhi'] for p in pos},
                            'hour_known': bool(chart.get('hour_known', True))}
                     for name, chart, pos in (('A', chart_a, a_pos), ('B', chart_b, b_pos))},
        'day_masters': {'A': dm_a, 'B': dm_b, 'A_sees_B': shi_shen(dm_a, dm_b), 'B_sees_A': shi_shen(dm_b, dm_a)},
        'relations': relations + _full_trios(a_pos, b_pos),
        'notes': list(NOTES),
        'boundary': BOUNDARY,
        'next_checks': ['按 references/14-hehun.md 查原文是否把该关系用于两人之间，以及适用的柱位与条件',
                        '各自的格局、喜忌仍按单人流程分别判断，不因双方有合就改单人结论'],
    }


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='两人八字之间逐柱的合冲刑害事实（不打分、不判好坏）',
        epilog='stdin: {"a": {birth}, "b": {birth}}；birth 键同 bazi_calc：year month day hour minute gender '
               'timezone longitude city sect lunar，省略 hour 表示时辰未知。'
               'Top-level JSON keys: ok tool version schema_version subjects day_masters relations notes '
               'boundary next_checks; errors: error message')
    parser.add_argument('--stdin', action='store_true', required=True, help='从标准输入读两人出生资料 JSON')
    parser.parse_args(argv)
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or not all(isinstance(request.get(k), dict) for k in ('a', 'b')):
            raise ValueError('需要 {"a": {...}, "b": {...}} 两人的出生资料')
        result = pair_facts(subject_chart(request['a']), subject_chart(request['b']))
    except (ValueError, KeyError, TypeError) as exc:
        json_print(error_envelope('pair_facts', 'invalid_input', str(exc)))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
