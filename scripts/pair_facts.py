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
from pathlib import Path

from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from bazi_reading import chart_facts
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
# 四孟、四仲、四季: the branch classes the 女命/男命 clauses compare (日支 against 年支 or 日支).
BRANCH_CLASSES = {'四孟': '寅申巳亥', '四仲': '子午卯酉', '四季': '辰戌丑未'}
CLAUSES = Path(__file__).resolve().parents[1] / 'assets' / 'hehun_clauses.json'
BIRTH_KEYS = ('year', 'month', 'day', 'hour', 'minute', 'gender', 'timezone', 'longitude', 'city', 'sect', 'lunar',
              'fold', 'time_standard', 'tz')
BOUNDARY = ('关系分类事实：哪一柱和哪一柱构成合、冲、刑、害。不是婚姻、亲子或合作好坏的判断，'
            '也没有分数；跨盘能否这样用、怎样解释，要按原文逐条核对。')
NOTES = ('canggan_he 列出两支藏干之间的天干五合，常被称为暗合；哪些支算暗合各家取法不同，只作候选事实。',
         '同一对地支可能同时是六合与刑（如巳申），两条都列出，不互相抵消。',
         '时辰未知的一方不使用时柱；生日正逢交节或日界时，年、月、日柱也可能未定，未定的柱只列候选，不参与关系和日主十神。')


def subject_chart(birth: dict) -> dict:
    """One person's chart facts from a birth request.

    These are the single-chart reading's cleaned facts, so an unknown birth time
    leaves every pillar it can move undecided with its candidates, instead of
    the calculator's internal placeholder pillars.
    """
    unknown = set(birth) - set(BIRTH_KEYS)
    if unknown:
        raise ValueError('unknown birth fields: ' + ', '.join(sorted(unknown)))
    args: list[str] = []
    for key in BIRTH_KEYS:
        value = birth.get(key)
        if value is None or value is False:
            continue
        flag = '--' + key.replace('_', '-')
        args += [flag] if value is True else [flag, str(value)]
    chart = calculate_bazi(chart_parser().parse_args(args))
    if not chart.get('ok'):
        raise ValueError(chart.get('message') or chart.get('error') or 'chart failed')
    return chart_facts(chart)


def _positions(chart: dict) -> list[dict]:
    """Only the pillars the chart has fixed; an undecided pillar has no 干支 to relate."""
    pillars = chart['four_pillars']
    keep = [k for k in ORDER if (pillars.get(k) or {}).get('ganzhi')
            and (k != 'hour' or chart.get('hour_known', True))]
    return [{'pillar': k, 'label': PILLAR_LABELS_CN[k], **pillars[k]} for k in keep]


def _undecided(chart: dict) -> dict:
    return {k: v.get('candidate_ganzhi', []) for k, v in chart['four_pillars'].items()
            if isinstance(v, dict) and not v.get('ganzhi')}


def _day_masters(chart_a: dict, chart_b: dict) -> dict:
    dm_a = (chart_a['four_pillars'].get('day') or {}).get('stem')
    dm_b = (chart_b['four_pillars'].get('day') or {}).get('stem')
    if isinstance(dm_a, str) and isinstance(dm_b, str):
        return {'A': dm_a, 'B': dm_b, 'A_sees_B': shi_shen(dm_a, dm_b), 'B_sees_A': shi_shen(dm_b, dm_a)}
    return {'A': dm_a, 'B': dm_b, 'A_sees_B': None, 'B_sees_A': None, 'status': 'day_pillar_undecided',
            'meaning': '有一方日柱未定，不给日主互见的十神；补出生时刻后重算'}


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
    if a['ganzhi'] == b['ganzhi']:
        rows.append({'kind': 'same_pillar', 'a': where['a'] + '柱' + a['ganzhi'], 'b': where['b'] + '柱' + b['ganzhi']})
    if {a['pillar'], b['pillar']} <= {'year', 'day'} and 'day' in (a['pillar'], b['pillar']):
        group = next((name for name, members in BRANCH_CLASSES.items()
                      if a['branch'] in members and b['branch'] in members), None)
        if group:
            rows.append({'kind': 'same_branch_class', 'a': sa, 'b': sb, 'class': group})
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


def clause_refs(relations: list[dict]) -> dict:
    """Source clauses on two people that these relations bear on, and the methods the tool cannot compute."""
    present = {row['kind'] for row in relations}
    clauses = json.loads(CLAUSES.read_text(encoding='utf-8'))['clauses']
    brief = [{'id': c['id'], 'passage_id': c['passage_id'], 'positions': c['positions'], 'claim': c['claim'],
              'not_computed': c['not_computed']} for c in clauses if set(c['pair_facts_kinds']) & present]
    missing = sorted({m for c in clauses if not c['pair_facts_kinds'] for m in c['not_computed']})
    return {'matched': brief, 'not_computed_methods': missing,
            'meaning': '原文条款只列出处与原句结论；适用须按 assets/hehun_clauses.json 的 conditions 与歧义逐条核，'
                       '用 classical_search.py --passage-id 读全文；不合成婚配分数'}


GROUPS = (('合', ('tiangan_he', 'dizhi_liu_he', 'san_he', 'ban_san_he')), ('冲', ('dizhi_chong',)),
          ('刑', ('dizhi_xing', 'san_xing')), ('害', ('dizhi_hai',)), ('会', ('san_hui', 'ban_san_hui')),
          ('同柱', ('same_pillar',)), ('同类地支', ('same_branch_class',)))
KIND_NAMES = {'tiangan_he': '天干五合', 'dizhi_liu_he': '地支六合', 'san_he': '跨盘三合', 'ban_san_he': '半合',
              'dizhi_chong': '六冲', 'dizhi_xing': '刑', 'san_xing': '跨盘三刑', 'dizhi_hai': '六害',
              'san_hui': '跨盘三会', 'ban_san_hui': '半会', 'same_pillar': '干支相同', 'same_branch_class': '同属'}


def _row_text(row: dict) -> str:
    detail = row.get('transforms_to') and f"合{row['transforms_to']}" or row.get('type') or row.get('class') or ''
    name = KIND_NAMES.get(row['kind'], row['kind'])
    if 'from_a' in row:
        return f"A{'、'.join(row['from_a'])}与B{'、'.join(row['from_b'])}凑成{row['group']}{name}"
    return f"A{row['a']}—B{row['b']}（{name}{'，' + detail if detail else ''}）"


def say_lines(relations: list[dict], masters: dict) -> list[str]:
    """One line per relation family, A/B positions named, then the day masters; hidden-stem pairs counted apart."""
    lines = []
    for title, kinds in GROUPS:
        rows = [_row_text(r) for r in relations if r['kind'] in kinds]
        lines.append(f"{title}：{'；'.join(rows) if rows else '无'}")
    hidden = sum(r['kind'] == 'canggan_he' for r in relations)
    lines.append(f"藏干相合（暗合候选，各家取法不同）：{hidden} 处，明细见 relations")
    if masters.get('A_sees_B'):
        lines.append(f"日主互见：A 日主{masters['A']}看 B 日主{masters['B']}为{masters['A_sees_B']}；"
                     f"B 看 A 为{masters['B_sees_A']}")
    else:
        lines.append('日主互见：有一方日柱未定，暂不给')
    return lines


def pair_facts(chart_a: dict, chart_b: dict) -> dict:
    a_pos, b_pos = _positions(chart_a), _positions(chart_b)
    relations = [row for a, b in product(a_pos, b_pos) for row in _pair_relations(a, b)] + _full_trios(a_pos, b_pos)
    return {
        'ok': True, 'tool': 'pair_facts', 'version': __version__, 'schema_version': '1.0',
        'subjects': {name: {'four_pillars': {p['pillar']: p['ganzhi'] for p in pos},
                            'undecided_pillars': _undecided(chart),
                            'hour_known': bool(chart.get('hour_known', True))}
                     for name, chart, pos in (('A', chart_a, a_pos), ('B', chart_b, b_pos))},
        'day_masters': _day_masters(chart_a, chart_b),
        'relations': relations,
        'say': say_lines(relations, _day_masters(chart_a, chart_b)),
        'classical_clauses': clause_refs(relations),
        'notes': list(NOTES),
        'boundary': BOUNDARY,
        'next_checks': ['按 references/14-hehun.md 查原文是否把该关系用于两人之间，以及适用的柱位与条件',
                        '各自的格局、喜忌仍按单人流程分别判断，不因双方有合就改单人结论'],
    }


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='两人八字之间逐柱的合冲刑害事实（不打分、不判好坏）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='stdin: {"a": {birth}, "b": {birth}}；birth 键同 bazi_calc：year month day hour minute gender\n'
               'timezone longitude city sect lunar，省略 hour 表示时辰未知。\n'
               'Top-level JSON keys: ok tool version schema_version subjects day_masters relations say classical_clauses notes\n'
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
