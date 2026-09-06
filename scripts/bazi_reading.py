"""Classical reading input: chart facts and source passages, without score-led verdicts."""
from __future__ import annotations

import argparse
from copy import deepcopy
from typing import Any

from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from classical_search import get_passage, search_classics
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print, shi_shen

PILLARS = {'year': '年柱', 'month': '月柱', 'day': '日柱', 'hour': '时柱'}
PROFILE = {
    'id': 'ziping-month-v1', 'primary_book': 'ziping',
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
            'birth_time_uncertainty', 'qi_yun_status')
    clean = {key: chart[key] for key in keys if key in chart}
    queries = ['用神', '用神变化', '用神成败救应']
    if any(word in question for word in ('调候', '寒暖', '五行', '用神')):
        queries.append('气候')
    roles = {item['role'] for item in structure['exposed_stems']}
    chapter_for_role = {'正官': '正官', '七杀': '偏官', '正印': '印绶',
                        '偏印': '印绶', '食神': '食神', '伤官': '伤官',
                        '正财': '财', '偏财': '财'}
    for item in structure['month_hidden_stems']:
        title = chapter_for_role.get(item['role'])
        if item['exposed_at'] and title and title not in queries:
            queries.append(title)
    if {'伤官', '正官'} <= roles:
        queries.append('伤官')
    # The primary rule's chapter is explicit; a high keyword count in a preface
    # must not displace the actual methodological paragraph.
    passages: list[dict] = [get_passage('ziping:c008:p0001'), get_passage('ziping:c008:p0002')]
    seen: set[str] = {p['passage_id'] for p in passages}
    for query in queries:
        for passage in search_classics(query, book='ziping', limit=1):
            if passage['passage_id'] not in seen:
                seen.add(passage['passage_id'])
                passages.append(passage)
    if not passages:
        raise ValueError('主体系原文检索未返回结果；核查知识库完整性后再解释')
    claims = _observations(chart, structure)
    return {'ok': True, 'tool': 'bazi_reading', 'version': __version__, 'schema_version': '1.0',
            'question': question, 'method_profile': PROFILE, 'chart_facts': clean,
            'observed_structure': structure,
            'reading_support': {'schema_version': '1.0', 'claims': claims,
                                'review_status': 'facts_checked_interpretation_required'},
            'source_passages': passages,
            'next_checks': ['先读月令与对应格局条款，再逐项核对成败救应',
                            '调候只在其明确前提下补充，不与格局用神强制合并',
                            '时间层级不足时不从原局推具体年月事件'],
            'output_policy': '先白话回答，最多三条主判断；短引文附出处，条件和否定不可省略',
            'boundary': '检索到原文不等于条款适用；透藏位置不等于旺衰或人生吉凶'}


def render_facts(result: dict) -> str:
    """A concise chart explanation, explicitly separate from a host's personal interpretation."""
    parts = [claim['text'] for claim in result['reading_support']['claims']]
    parts.append('这里的“藏”指地支包含的天干，“透”指它也出现在天干一排。' +
                 ('日柱待定时，暂不把十神或透藏作用当作已核事实。'
                  if result['observed_structure'].get('status') == 'birth_time_required' else
                  '上述位置已经核实；格局是否成立，还要对照原文检查其他干支的作用。'))
    source = result['source_passages'][0]
    parts.append(f"可继续核对《{source['book_title']}》{source['chapter_title']}："
                 f"{source['passage_id']}。以上为传统文化解读。")
    return '\n\n'.join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = chart_parser()
    parser.description = '八字白话解读准备：盘面事实、固定主体系、可追溯原文'
    parser.epilog = ('Top-level JSON keys: ok tool version schema_version question method_profile '
                     'chart_facts observed_structure reading_support source_passages next_checks '
                     'output_policy boundary; errors: error message')
    parser.add_argument('--question', default='', help='本次最关心的问题')
    parser.add_argument('--markdown', action='store_true', help='输出简短盘面说明，非完整个人判断')
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    # These optional calculations feed diagnostics, not the classical evidence input.
    args.no_shensha = args.no_geju = args.no_yongshen = True
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
