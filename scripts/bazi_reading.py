"""Classical reading input: chart facts and source passages, without score-led verdicts."""
from __future__ import annotations

import argparse
from copy import deepcopy
from typing import Any

from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from bazi_rules import assess_rules, evidence_bundle
from classical_search import get_passage
from tiaohou_provenance import get_tiaohou_audit
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print, shi_shen

PILLARS = {'year': '年柱', 'month': '月柱', 'day': '日柱', 'hour': '时柱'}
PROFILE = {
    'id': 'ziping-month-v2', 'primary_book': 'ziping',
    'primary_method': '子平真诠月令格局',
    'supporting_books': ['ditian', 'qiongtong', 'sanming', 'yuanhai'],
    'conflict_policy': '主体系先解释；其他体系分别对照，冲突保留，不投票',
    'scope': '原局盘面与条款核查，不自动判定现实事件',
}


def observed_structure(chart: dict) -> dict:
    """Record exact stems/locations; presence alone never establishes strength or rescue."""
    pillars = chart['four_pillars']
    day = chart['day_master'].get('stem')
    if day is None:
        return {'month_branch': pillars['month'].get('branch'), 'month_hidden_stems': [],
                'exposed_stems': [], 'status': 'birth_time_required',
                'meaning': '日柱可能随出生时间跨界；十神和透藏作用须分候选盘核对'}
    exposed = []
    for key, pillar in pillars.items():
        if key == 'day' or 'stem' not in pillar:
            continue
        stem = pillar['stem']
        roots = [f'{other}.hidden_stems.{i}'
                 for other, p in pillars.items()
                 for i, hidden in enumerate(p.get('hidden_stems', [])) if hidden == stem]
        exposed.append({'pillar': key, 'stem': stem, 'role': shi_shen(day, stem),
                        'path': f'four_pillars.{key}.stem',
                        'same_stem_hidden_at': roots})
    month = []
    for i, stem in enumerate(pillars['month'].get('hidden_stems', [])):
        month.append({'stem': stem, 'role': shi_shen(day, stem),
                      'path': f'four_pillars.month.hidden_stems.{i}',
                      'exposed_at': [r['pillar'] for r in exposed if r['stem'] == stem]})
    return {'month_branch': pillars['month'].get('branch'), 'month_hidden_stems': month,
            'exposed_stems': exposed,
            'meaning': '记录透藏位置；藏有同字不等于根气有力，出现财印不等于救应成立'}


def _observations(chart: dict, structure: dict) -> list[dict]:
    facts = [{'path': f'four_pillars.{key}.ganzhi', 'value': p['ganzhi']}
             for key, p in chart['four_pillars'].items() if 'ganzhi' in p]
    records: list[dict] = [{'id': 'pillars', 'kind': 'chart_fact', 'status': 'supported',
                'text': '已可固定的柱为' + '、'.join(f['value'] for f in facts)
                        + ('。' if chart['hour_known'] else '；出生时辰未知，时柱暂缺。'),
                'facts': facts, 'source_ids': [], 'rule_id': None,
                'scope': 'natal', 'conditions': {}, 'exceptions': []}] if facts else []
    uncertainty = chart.get('birth_time_uncertainty', {})
    if uncertainty.get('affected_pillars'):
        labels = '、'.join(PILLARS[key] for key in uncertainty['affected_pillars'])
        records.append({'id': 'birth-boundary', 'kind': 'hypothesis', 'status': 'insufficient',
                        'text': f'出生时辰未知，时柱暂缺；{labels}存在时间边界，须补出生时间或分别核对候选盘。',
                        'facts': [], 'source_ids': [], 'rule_id': None, 'scope': 'natal',
                        'conditions': {}, 'exceptions': []})
    month = structure['month_hidden_stems']
    if month:
        terms = '、'.join(f"{item['stem']}（{item['role']}）" for item in month)
        visible = [item for item in month if item['exposed_at']]
        detail = '；'.join(f"{item['stem']}也出现在{'、'.join(PILLARS[p] for p in item['exposed_at'])}的天干"
                          for item in visible)
        records.append({'id': 'month-structure', 'kind': 'chart_fact', 'status': 'supported',
                        'text': f"月支{structure['month_branch']}藏{terms}。" + (detail + '。' if detail else ''),
                        'facts': [{'path': item['path'], 'value': item['stem']} for item in month]
                                 + [{'path': f'four_pillars.{key}.stem', 'value': item['stem']}
                                    for item in visible for key in item['exposed_at']],
                        'source_ids': [], 'rule_id': None, 'scope': 'natal',
                        'conditions': {}, 'exceptions': []})
    visible = structure['exposed_stems']
    if visible:
        records.append({'id': 'exposed-roles', 'kind': 'chart_fact', 'status': 'supported',
                        'text': '天干一排还可核对：' + '；'.join(
                            f"{PILLARS[item['pillar']]}{item['stem']}是{item['role']}" for item in visible) + '。',
                        'facts': [{'path': 'day_master.stem', 'value': chart['day_master']['stem']}]
                                 + [{'path': item['path'], 'value': item['stem']} for item in visible],
                        'source_ids': [], 'rule_id': None, 'scope': 'natal',
                        'conditions': {}, 'exceptions': []})
    return records


def _without_unknown_hour_precision(chart: dict) -> dict:
    """Keep only stable observations; internal noon never becomes reading evidence."""
    clean = deepcopy(chart)
    if clean['hour_known']:
        return clean
    probes: list[dict] = []
    original = chart.get('input')
    if isinstance(original, dict):
        for hour, minute in ((0, 0), (23, 59)):
            values = {**original, 'hour': hour, 'minute': minute, 'years': 10,
                      'no_shensha': True, 'no_geju': True, 'no_yongshen': True,
                      'current_timezone': None, 'request_time': None, 'as_of_year': None}
            probe = calculate_bazi(argparse.Namespace(**values))
            if not probe.get('ok'):
                probes = []
                break
            probes.append(probe)
    affected = []
    for key in ('year', 'month', 'day'):
        possibilities = sorted({p['four_pillars'][key]['ganzhi'] for p in probes})
        if len(possibilities) != 1:
            affected.append(key)
            clean['four_pillars'][key] = {'status': 'birth_time_required',
                                           'candidate_ganzhi': possibilities}
    clean['four_pillars']['hour'] = {'status': '时柱待补'}
    if 'day' in affected:
        clean['day_master'] = {'status': 'birth_time_required'}
        for year in clean.get('liu_nian', []):
            year.pop('shi_shen', None)
    clean['birth_time_uncertainty'] = {
        'status': 'day_endpoints_compared' if probes else 'boundary_check_unavailable',
        'checked_clock_times': ['00:00', '23:59'] if probes else [],
        'affected_pillars': affected,
        'meaning': '候选来自同一出生日期的首尾钟表时间；它们不是已知生时，不能选中较像的一盘当作事实',
    }
    clean['solar_date'] = {k: v for k, v in clean['solar_date'].items() if k not in ('hour', 'minute')}
    clean['lunar_date'] = {k: v for k, v in clean['lunar_date'].items() if not k.endswith('_in_ganzhi')}
    for field in ('solar_date', 'lunar_date'):
        dates = sorted({tuple(p[field][part] for part in ('year', 'month', 'day')) for p in probes})
        if len(dates) != 1:
            clean[field] = {'status': 'birth_time_required',
                            'candidate_dates': [dict(zip(('year', 'month', 'day'), value, strict=True))
                                                for value in dates],
                            'basis': '所选日时口径的日期也可能跨界；不把内部正午日期当确定事实'}
    old_tst = clean.get('true_solar_time') or {}
    clean['true_solar_time'] = {k: old_tst[k] for k in ('longitude', 'time_standard') if k in old_tst}
    clean['true_solar_time']['status'] = 'birth_time_required'
    old_zone = clean.get('timezone') or {}
    clean['timezone'] = {'tz_name': old_zone.get('tz_name'), 'status': 'birth_time_required'}
    clean['qi_yun'] = None
    clean['da_yun'] = []
    clean['qi_yun_status'] = 'birth_time_required'
    return clean


def prepare_reading(chart: dict, question: str = '') -> dict:
    if not chart.get('ok') or chart.get('tool') != 'bazi':
        raise ValueError('需要成功的八字盘面')
    chart = _without_unknown_hour_precision(chart)
    structure = observed_structure(chart)
    # Keep the original paths so evidence checking can compare the same facts.
    keys = ('four_pillars', 'day_master', 'hour_known', 'solar_date', 'lunar_date',
            'true_solar_time', 'timezone', 'birthplace', 'sect', 'qi_yun', 'da_yun',
            'liu_nian', 'current_time_context', 'liu_nian_status', 'liu_nian_scope', 'liu_nian_note',
            'birth_time_uncertainty', 'qi_yun_status', 'calendar_context')
    clean = {key: chart[key] for key in keys if key in chart}
    assessment = assess_rules(clean)
    climate = None
    extra_ids: list[str] = []
    if any(term in question for term in ('调候', '用神', '喜忌', '寒暖', '五行')):
        day = clean['day_master'].get('stem')
        month = clean['four_pillars']['month'].get('branch')
        if day and month:
            climate = get_tiaohou_audit(f'{day}|{month}')
            # Include neighboring passages as well as the audited locators so
            # clauses are not reduced to the candidate names in the sidecar.
            for ref in climate['source_refs']:
                paragraph = get_passage(ref['passage_id'])
                extra_ids.extend(p['passage_id'] for p in paragraph['context'])
        else:
            climate = {'status': 'birth_time_required',
                       'meaning': '日干或月令未固定，先比较候选盘；不拿占位柱选调候'}
    bundle = evidence_bundle(assessment, question, getter=get_passage, extra_passage_ids=extra_ids)
    claims = _observations(chart, structure)
    return {'ok': True, 'tool': 'bazi_reading', 'version': __version__, 'schema_version': '2.0',
            'question': question, 'method_profile': PROFILE, 'chart_facts': clean,
            'observed_structure': structure,
            'reading_support': {'schema_version': '1.0', 'claims': claims,
                                'review_status': 'facts_checked_interpretation_required'},
            'rule_assessment': assessment, 'evidence_bundle': bundle, 'climate_review': climate,
            'next_checks': ['对照证据组完成本题相关路线的解释条件，逐条写明依据和反例',
                            '候选取用还须检查透干合支与兼格，不能把路线命中当格局已成',
                            '调候和岁运问题分别检索对应条款，不把原局规则外推到具体日期'],
            'output_policy': '先白话回答，最多三条主判断；短引文附出处，条件和否定不可省略',
            'boundary': '检索到原文不等于条款适用；透藏位置不等于旺衰或人生吉凶'}


def render_facts(result: dict) -> str:
    """A concise chart explanation, explicitly separate from a host's personal interpretation."""
    parts = [claim['text'] for claim in result['reading_support']['claims']]
    parts.append('这里的“藏”指地支包含的天干，“透”指它也出现在天干一排。' +
                 ('日柱待定时，暂不把十神或透藏作用当作已核事实。'
                  if result['observed_structure'].get('status') == 'birth_time_required' else
                  '上述位置已经核实；格局是否成立，还要对照原文检查其他干支的作用。'))
    assessment = result['rule_assessment']
    families = assessment['families']
    if families:
        parts.append('按月令，本次从' + '、'.join(f['title'] for f in families) +
                     '的条款入手；以下是具体条件检查，尚不代表格局成立。')
        for route in assessment['routes']:
            unmet = [c['label'] for c in route['conditions'] if c['state'] == 'not_met']
            met = [c['label'] for c in route['conditions']
                   if c['state'] == 'met' and c['id'] != 'full_chart']
            unknown = [c['label'] for c in route['conditions'] if c['state'] == 'unknown']
            if unmet:
                explanation = '未满足：' + '、'.join(unmet) + '。这条路径现在不能直接成立。'
            else:
                explanation = ('已核实：' + '、'.join(met) + '。') if met else ''
                if unknown:
                    explanation += '还影响结论的条件：' + '；'.join(unknown) + '。'
            parts.append(route['title'] + '：' + explanation)
    parts.append('上述检查用于传统原局分析；完整回答还需结合本题核完解释条件。')
    return '\n\n'.join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = chart_parser(diagnostics=False)
    parser.description = '八字白话解读准备：盘面事实、固定主体系、可追溯原文'
    parser.epilog = ('Top-level JSON keys: ok tool version schema_version question method_profile '
                     'chart_facts observed_structure reading_support rule_assessment evidence_bundle next_checks '
                     'output_policy boundary; errors: error message')
    parser.add_argument('--question', default='', help='本次最关心的问题')
    parser.add_argument('--markdown', action='store_true', help='输出简短盘面说明，非完整个人判断')
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    chart = calculate_bazi(args)
    if not chart.get('ok'):
        json_print(chart)
        return 1
    try:
        result: dict[str, Any] = prepare_reading(chart, args.question)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        json_print(error_envelope('bazi_reading', 'reading_unavailable', str(exc)))
        return 1
    if args.markdown:
        print(render_facts(result))
    else:
        json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
