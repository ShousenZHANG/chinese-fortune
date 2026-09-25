"""Classical reading input: chart facts and source passages, without score-led verdicts."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from bazi_rules import assess_rules, evidence_bundle
from classical_search import get_passage
from tiaohou_provenance import get_tiaohou_audit
from utils import (
    __version__,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    normalize_birth_time,
    shi_shen,
)
from wuxing_colours import asks_colour, colour_advice, colour_lead, colour_lines

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


def _clock_dates(solar: dict, sect: int) -> tuple[date, date]:
    civil = date(solar['year'], solar['month'], solar['day'])
    pillar_day = civil + timedelta(days=int(sect == 1 and solar['hour'] == 23))
    return civil, pillar_day


def _probes_cover_minutes(chart: dict, probes: list[dict]) -> bool:
    """Verify sampled dates and Jie intervals cover every supported clock minute.

    This is time normalization only, not 1,440 additional charts. Both folds
    belong to an unknown birth hour; nonexistent local minutes contribute no
    candidate. Unusual history that three charts cannot cover stays uncertain.
    """
    args = chart['input']
    base = chart['solar_date']  # Unknown-hour conversion preserves the input civil date.
    sect = args['sect']
    dates = [_clock_dates(p['solar_date'], sect) for p in probes]
    civil_dates = {civil for civil, _ in dates}
    pillar_dates = {pillar for _, pillar in dates}
    intervals = [(
        datetime.fromisoformat(p['calendar_context']['previous_jie']['calendar_datetime']),
        datetime.fromisoformat(p['calendar_context']['next_jie']['calendar_datetime']),
    ) for p in probes]
    valid_minutes = 0
    for minute_of_day in range(24 * 60):
        hour, minute = divmod(minute_of_day, 60)
        for fold in ((0, 1) if args.get('timezone') else (None,)):
            try:
                normalized = normalize_birth_time(
                    base['year'], base['month'], base['day'], hour, minute,
                    args['longitude'], args['tz'], args.get('timezone'), fold,
                    args['time_standard'])
            except ValueError as exc:
                if args.get('timezone') and str(exc).endswith('不存在 (夏令时跳时)'):
                    continue  # A confirmed gap is not a possible birth instant.
                return False
            civil, pillar = _clock_dates(normalized['solar_date'], sect)
            if civil not in civil_dates or pillar not in pillar_dates:
                return False
            zone = normalized['timezone']
            offset = zone['offset_hours'] if zone else args['tz']
            instant = datetime(base['year'], base['month'], base['day'], hour, minute,
                               tzinfo=timezone(timedelta(hours=offset)))
            if not any(start <= instant < end for start, end in intervals):
                return False
            valid_minutes += 1
    return valid_minutes > 0


def _without_unknown_hour_precision(chart: dict) -> dict:
    """Keep only verified stable observations; sampled noon is never a known birth time."""
    clean = deepcopy(chart)
    if clean.get('birth_time_uncertainty', {}).get('status') == 'interval_verified':
        return clean
    if clean['hour_known']:
        return clean
    probes: list[dict] = []
    checked_times: list[str] = []
    failed_times: list[str] = []
    original = chart.get('input')
    if isinstance(original, dict):
        for hour, minute in ((0, 0), (12, 0), (23, 59)):
            values = {**original, 'hour': hour, 'minute': minute, 'years': 10,
                      'no_shensha': True, 'no_geju': True, 'no_yongshen': True,
                      'current_timezone': None, 'request_time': None, 'as_of_year': None}
            probe = calculate_bazi(argparse.Namespace(**values))
            if not probe.get('ok'):
                failed_times.append(f'{hour:02}:{minute:02}')
                continue
            probes.append(probe)
            checked_times.append(f'{hour:02}:{minute:02}')
    complete = len(probes) == 3 and _probes_cover_minutes(chart, probes)
    affected = []
    for key in ('year', 'month', 'day'):
        possibilities = sorted({p['four_pillars'][key]['ganzhi'] for p in probes})
        if not complete or len(possibilities) != 1:
            affected.append(key)
            clean['four_pillars'][key] = {'status': 'birth_time_required',
                                           'candidate_ganzhi': possibilities}
        else:
            clean['four_pillars'][key] = deepcopy(probes[0]['four_pillars'][key])
    clean['four_pillars']['hour'] = {'status': '时柱待补'}
    if 'day' in affected:
        clean['day_master'] = {'status': 'birth_time_required'}
        for year in clean.get('liu_nian', []):
            year.pop('shi_shen', None)
    else:
        clean['day_master'] = deepcopy(probes[0]['day_master'])
        for year in clean.get('liu_nian', []):
            if year.get('ganzhi'):
                year['shi_shen'] = shi_shen(clean['day_master']['stem'], year['ganzhi'][0])
    clean['birth_time_uncertainty'] = {
        'status': 'day_samples_verified' if complete else 'boundary_check_unavailable',
        'checked_clock_times': checked_times,
        'failed_clock_times': failed_times,
        'candidate_coverage': 'minute_grid_verified' if complete else 'incomplete',
        'affected_pillars': affected,
        'meaning': ('候选来自同一出生日期的00:00、12:00、23:59实际排盘；'
                    '按分钟核对全天时间归一化、日界及交节区间，重复钟面覆盖两个fold。'
                    '核对失败则候选不完整，不能固定三柱。采样时刻不是已知生时，不能挑较像的一盘当事实'),
    }
    clean['calendar_context']['note'] = ('内部正午不是生时；解读另算首、中、尾候选，'
                                        '其完整性见birth_time_uncertainty.candidate_coverage')
    for field in ('solar_date', 'lunar_date'):
        dates = sorted({tuple(p[field][part] for part in ('year', 'month', 'day')) for p in probes})
        if not complete or len(dates) != 1:
            clean[field] = {'status': 'birth_time_required',
                            'candidate_dates': [dict(zip(('year', 'month', 'day'), value, strict=True))
                                                for value in dates],
                            'basis': '所选日时口径的日期也可能跨界；不把内部正午日期当确定事实'}
        else:
            clean[field] = {k: v for k, v in probes[0][field].items()
                            if k not in ('hour', 'minute') and not k.endswith('_in_ganzhi')}
    old_tst = clean.get('true_solar_time') or {}
    clean['true_solar_time'] = {k: old_tst[k] for k in ('longitude', 'time_standard') if k in old_tst}
    clean['true_solar_time']['status'] = 'birth_time_required'
    old_zone = clean.get('timezone') or {}
    clean['timezone'] = {'tz_name': old_zone.get('tz_name'), 'status': 'birth_time_required'}
    clean['qi_yun'] = None
    clean['da_yun'] = []
    clean['qi_yun_status'] = 'birth_time_required'
    return clean


def chart_facts(chart: dict) -> dict:
    """Reuse validated natal facts without loading every natal interpretation path."""
    if not chart.get('ok') or chart.get('tool') != 'bazi':
        raise ValueError('需要成功的八字盘面')
    chart = _without_unknown_hour_precision(chart)
    # Keep the original paths so evidence checking can compare the same facts.
    keys = ('four_pillars', 'day_master', 'hour_known', 'solar_date', 'lunar_date',
            'true_solar_time', 'timezone', 'birthplace', 'sect', 'qi_yun', 'da_yun',
            'liu_nian', 'current_time_context', 'liu_nian_status', 'liu_nian_scope', 'liu_nian_note',
            'birth_time_uncertainty', 'qi_yun_status', 'calendar_context')
    return {key: chart[key] for key in keys if key in chart}


def prepare_reading(chart: dict, question: str = '') -> dict:
    clean = chart_facts(chart)
    structure = observed_structure(clean)
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
    claims = _observations(clean, structure)
    extra: dict = {'colour_advice': colour_advice(clean, question)} if asks_colour(question) else {}
    return {**extra, 'ok': True, 'tool': 'bazi_reading', 'version': __version__, 'schema_version': '2.0',
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


# 十神 names, explained by the relation that defines them (utils.shi_shen).
SHI_SHEN_PLAIN = {
    '比肩': '和日主同一五行、阴阳相同', '劫财': '和日主同一五行、阴阳相反',
    '食神': '由日主生出、阴阳相同', '伤官': '由日主生出、阴阳相反',
    '偏财': '被日主所克、阴阳相同', '正财': '被日主所克、阴阳相反',
    '七杀': '克制日主、阴阳相同', '正官': '克制日主、阴阳相反',
    '偏印': '生扶日主、阴阳相同', '正印': '生扶日主、阴阳相反',
}


def _routes_summary(routes: list[dict]) -> str:
    """Open routes by name, closed ones by name or, when many, by count."""
    def name(route: dict) -> str:
        return route['title'].split('：')[0]
    closed = [r for r in routes if any(c['state'] == 'not_met' for c in r['conditions'])]
    pending = [r for r in routes if r not in closed
               and any(c['state'] == 'unknown' for c in r['conditions'])]
    settled = [r for r in routes if r not in closed and r not in pending]
    parts = []
    if settled:
        parts.append('、'.join(map(name, settled)) + '的条件都已核到')
    if pending:
        parts.append('、'.join(map(name, pending)) + '的前提已见到，还有条件没核完')
    if closed:
        parts.append(('、'.join(map(name, closed)) if len(closed) <= 2 else f'其余{len(closed)}条路线')
                     + '现在不成立' if pending or settled else
                     f'查到的{len(closed)}条取用路线现在都不成立')
    return '；'.join(parts)


def _lead(result: dict) -> str | None:
    """Answer first: the question, then what the month-branch check found.

    The first line used to be the four-pillar string whatever was asked.
    """
    families = result['rule_assessment']['families']
    day = result['chart_facts'].get('day_master', {}).get('stem')
    branch = result['observed_structure'].get('month_branch')
    if not families or not day or not branch:
        return None
    question = (result.get('question') or '').strip()
    ask = f'就「{question}」来说，先要看月令格局。' if question else ''
    titles = '、'.join(f['title'] for f in families)
    routes = _routes_summary(result['rule_assessment']['routes'])
    head = f'{ask}日主是{day}（日柱的天干，代表你本人），按月令{branch}，本次从{titles}的条款入手'
    return f'{head}：{routes}。' if routes else head + '。'


def _role_terms(result: dict) -> str:
    structure = result['observed_structure']
    roles = [item['role'] for item in structure.get('month_hidden_stems', []) + structure.get('exposed_stems', [])]
    roles += [f['title'] for f in result['rule_assessment']['families']]
    named = [r for r in dict.fromkeys(roles) if r in SHI_SHEN_PLAIN]
    if not named:
        return ''
    return ('括号里的名称是十神，指某个天干和日主的关系：' +
            '；'.join(f'{r}是{SHI_SHEN_PLAIN[r]}的那个字' for r in named) +
            '。它们只是关系名称，不直接等于职业、性格或好坏。')


def render_facts(result: dict) -> str:
    """A concise chart explanation, explicitly separate from a host's personal interpretation."""
    lead = _lead(result)
    parts = ([lead] if lead else []) + [claim['text'] for claim in result['reading_support']['claims']]
    advice = result.get('colour_advice')
    if advice:
        # A colour question is answered first; the chart facts follow as background.
        parts = [colour_lead(advice), *colour_lines(advice), *parts]
    terms = _role_terms(result)
    if terms:
        parts.append(terms)
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
                     'chart_facts observed_structure reading_support rule_assessment evidence_bundle climate_review next_checks '
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
