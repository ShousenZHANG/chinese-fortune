"""Classical reading input: chart facts and source passages, without score-led verdicts."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from annual_assessment import (
    ANNUAL_WORDS,
    annual_paragraph,
    annual_readings,
    unknown_year,
    year_pillar,
    years_asked,
)
from bazi_calc import build_parser as chart_parser
from bazi_calc import calculate_bazi
from bazi_derivation import asks_derivation, derivation_steps, hour_boundary, offset_sentence
from bazi_rules import assess_rules, evidence_bundle
from classical_search import get_passage
from geju_assessment import assess_geju, geju_paragraph
from life_areas import areas_asked, life_areas
from luck_assessment import assess_luck, luck_paragraph
from must_cover import annual_scope_items, geju_items, hour_items
from reading_views import compact_reading, facts_line, write_card, write_facts, write_report
from tiaohou_provenance import get_tiaohou_audit
from utils import (
    __version__,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    normalize_birth_time,
    shi_shen,
    zip_exact,
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


def _pillar_at(original: dict, minute_of_day: int, key: str, fold: int | None = None) -> str | None:
    hour, minute = divmod(minute_of_day, 60)
    values = {**original, 'hour': hour, 'minute': minute, 'years': 10, 'no_shensha': True, 'no_geju': True,
              'no_yongshen': True, 'current_timezone': None, 'request_time': None, 'as_of_year': None,
              **({'fold': fold} if fold is not None else {})}
    probe = calculate_bazi(argparse.Namespace(**values))
    return probe['four_pillars'][key]['ganzhi'] if probe.get('ok') else None


def candidate_windows(original: dict, key: str, samples: list[tuple[int, str]],
                      fold: int | None = None) -> list[dict]:
    """Clock windows of the birth date that give each candidate, found by bisecting between samples.

    A pillar changes at most once a day (the day boundary, or a term instant), so
    each change between two sampled times is one boundary minute.
    """
    cuts = []
    for (left, left_value), (right, right_value) in zip(samples, samples[1:]):
        if left_value == right_value:
            continue
        low, high = left, right
        while high - low > 1:
            middle = (low + high) // 2
            if _pillar_at(original, middle, key, fold) == left_value:
                low = middle
            else:
                high = middle
        cuts.append(high)
    edges = [0, *cuts, 1440]
    values = [samples[0][1]] + [next(v for m, v in samples if m >= cut) for cut in cuts]
    return [{'ganzhi': value, 'clock': f'{start // 60:02}:{start % 60:02}–{(end - 1) // 60:02}:{(end - 1) % 60:02}'}
            for start, end, value in zip(edges, edges[1:], values)]


def _minutes(windows: list[dict]) -> list[str]:
    values = []
    for window in windows:
        start, end = (int(t[:2]) * 60 + int(t[3:]) for t in window['clock'].split('–'))
        values += [window['ganzhi']] * (end - start + 1)
    return values


def fold_aware_windows(original: dict, key: str, samples: list[tuple[int, str]]) -> list[dict]:
    """Windows for both readings of a repeated summer-time clock hour.

    Where the first and second occurrence of the same clock minute give
    different pillars, the window says so instead of picking one.
    """
    if not original.get('timezone') or original.get('fold') is not None:
        return candidate_windows(original, key, samples)
    by_fold = []
    for fold in (0, 1):
        folded = [(m, _pillar_at(original, m, key, fold) or v) for m, v in samples]
        by_fold.append(_minutes(candidate_windows(original, key, folded, fold)))
    rows: list[dict] = []
    for minute, pair in enumerate(zip(*by_fold)):
        if rows and rows[-1]['pair'] == pair:
            rows[-1]['end'] = minute
        else:
            rows.append({'pair': pair, 'start': minute, 'end': minute})
    out = []
    for row in rows:
        clock = f"{row['start'] // 60:02}:{row['start'] % 60:02}–{row['end'] // 60:02}:{row['end'] % 60:02}"
        first, second = row['pair']
        out.append({'ganzhi': first, 'clock': clock} if first == second else
                   {'ganzhi': None, 'clock': clock, 'repeated_clock': {'first': first, 'second': second}})
    return out


def _window_text(window: dict, label: str) -> str:
    if window['ganzhi']:
        return f"钟表 {window['clock']} 出生为{window['ganzhi']}{label}"
    pair = window['repeated_clock']
    return (f"钟表 {window['clock']} 是夏令时回拨的重复时段：第一次为{pair['first']}{label}，"
            f"第二次为{pair['second']}{label}，要先问清是哪一次")


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
            if complete and isinstance(original, dict):
                samples = [(m, p['four_pillars'][key]['ganzhi']) for m, p in zip((0, 720, 1439), probes)]
                windows = fold_aware_windows(original, key, samples)
                label = {'year': '年', 'month': '月', 'day': '日'}[key]
                clock_standard = original.get('time_standard') == 'clock'
                basis = {'year': '年柱按立春交节分界，不按农历新年', 'month': '月柱按节气交节时刻分界',
                         'day': ('日柱按钟表时间与所选晚子时口径分界' if clock_standard
                                 else '日柱按真太阳时与所选晚子时口径分界')}[key]
                clean['four_pillars'][key]['candidate_windows'] = windows
                clean['four_pillars'][key]['say'] = (
                    '；'.join(_window_text(w, label) for w in windows) + f'（{basis}）')
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
                            'candidate_dates': [dict(zip_exact(('year', 'month', 'day'), value))
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
            'liu_nian', 'current_time_context', 'liu_nian_status', 'reference_year', 'liu_nian_scope', 'liu_nian_note',
            'birth_time_uncertainty', 'qi_yun_status', 'calendar_context', 'deceased')
    return {key: chart[key] for key in keys if key in chart and (key != 'deceased' or chart[key])}


def fact_packet(clean: dict, structure: dict | None = None) -> dict:
    """Build the same reviewable facts from full or compact chart_facts."""
    return {'schema_version': '1.0',
            'claims': _observations(clean, structure if structure is not None else observed_structure(clean)),
            'review_status': 'facts_checked_interpretation_required'}


def age_at_request(facts: dict) -> dict | None:
    """周岁 and 虚岁 on the request date, when a local request date is known; hosts got this wrong by hand."""
    context = facts.get('current_time_context') or {}
    tst = facts.get('true_solar_time') or {}
    if not context.get('timezone') or not tst.get('effective_date'):
        return None
    try:
        today = datetime.fromisoformat(str(context['local'])).date()
        # The civil birth date, not the true-solar date a late birth may roll into.
        born = date.fromisoformat(tst['effective_date']) - timedelta(days=tst.get('day_offset') or 0)
    except (KeyError, ValueError):
        return None
    full = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    from lunar_python import Solar
    birth_lunar_year = (facts.get('lunar_date') or {}).get('year') or born.year
    today_lunar_year = Solar.fromYmd(today.year, today.month, today.day).getLunar().getYear()
    nominal = today_lunar_year - birth_lunar_year + 1
    return {'date': today.isoformat(), 'full_years': full, 'nominal_years': nominal,
            'say': f"到 {today.isoformat()}，周岁 {full} 岁，虚岁 {nominal} 岁（虚岁按农历年计）"}


GEJU_WORDS = ('格局', '成格', '败格', '用神')


def prepare_reading(chart: dict, question: str = '') -> dict:
    clean = chart_facts(chart)
    if (clean.get('true_solar_time') or {}).get('applied'):
        clean['true_solar_time']['say'] = offset_sentence(clean['true_solar_time'])
    boundary = hour_boundary(clean['true_solar_time']) if clean.get('hour_known') and clean.get('true_solar_time') else None
    if boundary:
        clean['hour_boundary'] = boundary
    for cycle in clean.get('da_yun') or []:
        if cycle.get('ganzhi') and cycle.get('start_year'):
            cycle['say'] = (f"{cycle['start_year']}–{cycle.get('cut_at_death_year') or cycle['end_year']} 年走{cycle['ganzhi']}运"
                            f"（周岁 {cycle['start_age']}–{cycle['end_age']}，虚岁从 {cycle.get('start_age_xusui', '?')} 起）"
                            + (f"；卒于 {cycle['cut_at_death_year']} 年，这步运只到这里" if cycle.get('cut_at_death_year') else ''))
    age = age_at_request(clean)
    deceased = clean.get('deceased')
    died_year = deceased['year'] if deceased else None
    if deceased:
        # B6: a dead person has no age today; the age at death needs only the two dates.
        died = date.fromisoformat(deceased['date'])
        born = date.fromisoformat(deceased['birth_date'])
        full = died.year - born.year - ((died.month, died.day) < (born.month, born.day))
        age = {'date': deceased['date'], 'full_years': full, 'nominal_years': None, 'deceased': True,
               'say': f"已于 {deceased['date']} 去世，享年周岁 {full} 岁；不算今天的年龄，卒年之后的大运流年不排。"}
    if age:
        clean['age_at_request'] = age
    structure = observed_structure(clean)
    assessment = assess_rules(clean)
    geju = assess_geju(clean)
    climate = None
    extra_ids: list[str] = list(geju['source_passage_ids'])
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
    extra: dict = {'colour_advice': colour_advice(clean, question)} if asks_colour(question) else {}
    if any(word in question for word in LUCK_WORDS):
        cycles = _cycles_now(clean)
        reference = _reference_year(clean)
        asked = years_asked(question, reference)
        # The chart drops 流年 rows after the death, so the reference year can be missing; a dead person has no
        # current cycle either way, and that is not the same as "which year is it" being unknown (R9-LAD02).
        if died_year and (reference is None or reference > died_year or any(y > died_year for y in asked)):
            when = f'{max([reference or 0, *asked])} 年' if (reference or asked) else '现在'
            extra['luck_reading'] = [{'status': 'after_death', 'luck': {'ganzhi': None},
                                      'reason': f'已于 {died_year} 年去世，{when}没有在走的大运，不作个人评估'}]
        else:
            extra['luck_reading'] = ([assess_luck(clean, cycle) for cycle in cycles] if cycles else
                                     [{'status': 'unavailable', 'luck': {'ganzhi': None},
                                       'reason': '不知道今年是哪一年，选不出当前大运：先问用户现在住在哪里（时区），再算'}])
        for reading in extra['luck_reading']:
            for scenario in reading.get('scenarios', []):
                extra_ids.extend(scenario['source_passage_ids'])
            extra_ids.extend(n['passage_id'] for n in reading.get('notes', []))
    areas = areas_asked(question)
    if areas:
        extra['life_areas'] = life_areas(clean, (chart.get('input') or {}).get('gender'), areas)
        extra_ids.extend(s['passage_id'] for area in extra['life_areas']['areas'] for s in area['sources'])
    bundle = evidence_bundle(assessment, question, getter=get_passage, extra_passage_ids=extra_ids)
    years = years_asked(question, _reference_year(clean))
    if years:
        alive = annual_readings(clean, [y for y in years if not died_year or y <= died_year])
        by_year = {r['year']: r for r in alive}
        extra['annual_reading'] = [by_year.get(y) or after_death_year(y, died_year) for y in years]
    elif any(word in question for word in ANNUAL_WORDS):
        extra['annual_reading'] = [unknown_year('不知道今年是哪一年：先问用户现在住在哪里（时区），或者直接问哪一年')]
    result = {**extra, 'ok': True, 'tool': 'bazi_reading', 'version': __version__, 'schema_version': '2.1',
            'question': question, 'method_profile': PROFILE, 'chart_facts': clean,
            'observed_structure': structure,
            'reading_support': fact_packet(clean, structure),
            'rule_assessment': assessment, 'geju_review': geju, 'evidence_bundle': bundle, 'climate_review': climate,
            'next_checks': ['对照证据组完成本题相关路线的解释条件，逐条写明依据和反例',
                            '候选取用还须检查透干合支与兼格，不能把路线命中当格局已成',
                            '调候和岁运问题分别检索对应条款，不把原局规则外推到具体日期'],
            'output_policy': '先白话回答，最多三条主判断；短引文附出处，条件和否定不可省略',
            'boundary': '检索到原文不等于条款适用；透藏位置不等于旺衰或人生吉凶'}
    # Most hosts read the JSON, not the Markdown draft: the notes travel in both.
    result['host_notes'] = host_notes(result)
    result['derivation'] = derivation_steps(clean)
    must = (hour_items(boundary) + (geju_items() if any(word in question for word in GEJU_WORDS) else [])
            + annual_scope_items(result.get('annual_reading') or []))
    if must:
        result['must_cover'] = must
    return result


# Questions about the coming years: answer with this and the next ten-year cycle.
LUCK_WORDS = ('大运', '运势', '这几年', '今年', '明年', '这十年', '走什么运', '运程', '行运')


def host_notes(result: dict) -> list[str]:
    """What the host must say as the tool says it (evals/v56/REPORT.md 3.1)."""
    notes = ['十神、生肖、旺衰只用上面给的；十神只是关系名称，不直接等于职业、性格或好坏；不要自己写代码另算。']
    question = result.get('question') or ''
    if any(w in question for w in ('属', '生肖')):
        lunar = (result['chart_facts'].get('lunar_date') or {})
        zodiac = lunar.get('zodiac') if isinstance(lunar, dict) else None
        if zodiac:
            notes.append(f"生肖按工具算的农历年说：属{zodiac}；不要按公历年份自己推。")
    advice = result.get('colour_advice')
    if advice and advice.get('personal_choice') is False:
        notes.append('这一格的例外在你的盘里成立，原文改取别的：不要把一般取法说成个人建议，也不要另推颜色或饰物。')
    if 'luck_reading' in result:
        notes.append('大运配法和格局仍是候选；conditional、partial、mixed 及反向例外须原样说明，不能压成总吉凶。')
        for reading in result['luck_reading']:
            if reading['status'] != 'assessed' or not reading.get('scenarios'):
                notes.append(f"{reading['luck'].get('ganzhi') or '这步'}大运工具没判喜忌：不要自己判，照上面的原因说。")
    if 'annual_reading' in result:
        notes.append('流年只列原文说的冲、克、合关系和原文的说法，不合成总分，也不细到月份；「看救助」「看喜忌」的照说没判。')
    elif 'luck_reading' in result:
        notes.append('这里只说大运；要问某一年，请用户说出年份。')
    return list(dict.fromkeys(notes))


def _reference_year(clean: dict) -> int | None:
    """Which year it is for this request: the replayed or current instant, or the explicit year."""
    if clean.get('reference_year'):
        return clean['reference_year']
    context = clean.get('current_time_context') or {}
    return int(context['local'][:4]) if context.get('local') else (clean.get('liu_nian') or [{}])[0].get('year')


def after_death_year(year: int, died_year: int | None) -> dict:
    """A year after the death: not a personal reading, whatever the hour or day pillar."""
    return {'status': 'after_death', 'year': year, 'ganzhi': year_pillar(year), 'cycle': None, 'hits': [],
            'reason': f'卒于 {died_year} 年，这一年不作个人评估'}


def _cycles_now(clean: dict) -> list[dict]:
    """This and the next ten-year cycle, by the chart's own reference year."""
    year = _reference_year(clean)
    cycles = clean.get('da_yun') or []
    if not year or not cycles:
        return []
    at = next((i for i, c in enumerate(cycles) if c['start_year'] <= year <= c['end_year']), None)
    return [] if at is None else cycles[at:at + 2]


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
        parts.append('、'.join(map(name, pending)) + '的前提已见到，各自还有不同的条件没核完（逐条见下）')
    if closed:
        # Grouped by what each lacks: round 7 S18 still wrote three closed routes as
        # all 「因缺印透出」 when one lacked 七杀透出.
        by_gap: dict[str, list[str]] = {}
        for route in closed:
            gap = '、'.join(c['label'] for c in route['conditions'] if c['state'] == 'not_met')
            by_gap.setdefault(gap, []).append(name(route))
        parts.append('现在不成立的：' + '；'.join(f"{'、'.join(names)}缺{gap}" for gap, names in by_gap.items()))
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
    # No echo of the question: the v5.6 evaluation counted 「就……来说」 as filler.
    titles = '、'.join(f['title'] for f in families)
    routes = _routes_summary(result['rule_assessment']['routes'])
    head = f'日主是{day}（日柱的天干，代表你本人），按月令{branch}，本次从{titles}的条款入手'
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


def _route_lines(assessment: dict) -> list[str]:
    """The routes in two groups, each condition said once (v5.6: every route repeated
    「不等于已发挥作用」 and the month-resolution condition)."""
    # One line per route, open ones first, each with only its own missing or pending
    # items: round 6 R2 merged a closed route's 「缺印透出」 into two open routes
    # that had no such premise.
    lines: list[str] = []
    closed = [r for r in assessment['routes'] if any(c['state'] == 'not_met' for c in r['conditions'])]
    pending = [r for r in assessment['routes'] if r not in closed]
    for route in pending:
        left = [c['label'] for c in route['conditions'] if c['state'] == 'unknown' and c['id'] != 'month_resolution']
        lines.append(f"{route['title']}：可算的前提都满足，没有缺项" + (f"；这一条还要核：{'；'.join(left)}。" if left else '。'))
    for route in closed:
        missing = '、'.join(c['label'] for c in route['conditions'] if c['state'] == 'not_met')
        lines.append(f"{route['title']}：现在不成立，这一条缺{missing}。")
    if pending:
        lines.append('以上每条还都要核：这条属于月令本格，还是可成立的变格、兼格；只是检索到条款不算格局成立。'
                     '「可见」只说这个字在盘里，不等于它已发挥作用。')
    return lines


def render_facts(result: dict) -> str:
    """A concise chart explanation, explicitly separate from a host's personal interpretation."""
    lead = _lead(result)
    claims = [claim['text'] for claim in result['reading_support']['claims']]
    advice = result.get('colour_advice')
    if advice:
        # A colour question is answered by the colour; the pillars are its background,
        # the route checklist belongs to a chart question (v5.6: 1707 characters).
        pillars = [c for c in claims if c.startswith('已可固定的柱')]
        parts = [colour_lead(advice), *colour_lines(advice), *pillars]
        parts += _cycle_parts(result)
        parts.append('写回答时：' + ''.join(result.get('host_notes') or host_notes(result)))
        return '\n\n'.join(parts)
    parts = ([lead] if lead else []) + claims
    terms = _role_terms(result)
    if terms:
        parts.append(terms)
    parts.append('这里的“藏”指地支包含的天干，“透”指它也出现在天干一排。' +
                 ('日柱待定时，暂不把十神或透藏作用当作已核事实。'
                  if result['observed_structure'].get('status') == 'birth_time_required' else
                  '上述位置已经核实；格局是否成立，还要对照原文检查其他干支的作用。'))
    parts += _route_lines(result['rule_assessment'])
    if any(w in result.get('question', '') for w in ('格局', '成格', '败格', '变格', '救应', '用神')):
        parts.append(geju_paragraph(result['geju_review']))
    parts += _cycle_parts(result)
    if asks_derivation(result.get('question', '')):
        parts.append('推算过程：' + '；'.join(f"{d['step']}{d['result']}（{d['how']}）"
                                          for d in result.get('derivation', [])))
    parts.append('写回答时：' + ''.join(result.get('host_notes') or host_notes(result)))
    return '\n\n'.join(parts)


def _cycle_parts(result: dict) -> list[str]:
    """The luck cycles and the years asked about, when the question asks."""
    parts = []
    for index, reading in enumerate(result.get('luck_reading', [])):
        text = luck_paragraph(reading)
        parts.append(text if index == 0 else text.replace('你现在走的', '下一步是', 1))
    areas = [f"{a['label']}：{a['say']}" for a in (result.get('life_areas') or {}).get('areas', [])]
    return parts + [annual_paragraph(r) for r in result.get('annual_reading', [])] + areas


def build_parser() -> argparse.ArgumentParser:
    parser = chart_parser(diagnostics=False)
    parser.description = '八字白话解读准备：盘面事实、固定主体系、可追溯原文'
    parser.epilog = ('Top-level JSON keys: ok tool version schema_version question method_profile '
                     'chart_facts observed_structure reading_support rule_assessment geju_review evidence_bundle climate_review next_checks '
                     'output_policy boundary host_notes; optional: luck_reading annual_reading life_areas must_cover report card; compact: view evidence_index observations details; errors: error message')
    parser.add_argument('--question', default='', help='本次最关心的问题')
    parser.add_argument('--markdown', action='store_true', help='输出简短盘面说明，非完整个人判断')
    parser.add_argument('--view', choices=('full', 'compact'), default='full',
                        help='JSON 展示层：full 完整资料；compact 去重并以段号索引原文')
    parser.add_argument('--report', metavar='PATH', help='另存本地 .md/.html 核对报告；不覆盖已有文件')
    parser.add_argument('--report-style', choices=('plain', 'professional'), default='plain',
                        help='报告写法：plain 白话（默认）；professional 加四柱表、离线命盘图与条款核查表')
    parser.add_argument('--report-redact', action='store_true',
                        help='分享预览：隐去四柱干支、出生日期时间地点、问题原话与公历年份，不附完整 JSON')
    parser.add_argument('--card', metavar='PATH.svg',
                        help='另存一张离线 SVG 分享卡片（四柱、日主、月令、当前大运、条款与段号）；不覆盖已有文件')
    parser.add_argument('--card-redact', action='store_true',
                        help='分享卡片隐去四柱干支、出生资料和公历年份，只留十神关系、条款状态与段号')
    parser.add_argument('--facts-out', metavar='PATH.json',
                        help='把 --view 选定的 JSON 存到这个文件，屏幕只输出白话草稿和文件路径；'
                             '供 answer_check --facts 使用，只覆盖本工具以前写的 JSON')
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
    if args.report:
        try:
            result['report'] = write_report(result, render_facts(result), args.report,
                                            style=args.report_style, redact=args.report_redact)
        except (OSError, ValueError) as exc:
            json_print(error_envelope('bazi_reading', 'report_unavailable', f'{exc}；请指定新的可写文件路径'))
            return 1
    if args.card:
        try:
            result['card'] = write_card(result, args.card, redact=args.card_redact)
        except (OSError, ValueError) as exc:
            json_print(error_envelope('bazi_reading', 'card_unavailable', f'{exc}；请指定新的可写文件路径'))
            return 1
    view = compact_reading(result) if args.view == 'compact' else result
    if args.facts_out:
        try:
            saved = write_facts(args.facts_out, view)
        except (OSError, ValueError) as exc:
            json_print(error_envelope('bazi_reading', 'facts_unavailable', str(exc)))
            return 1
        print(render_facts(result) + '\n\n' + facts_line(saved))
    elif args.markdown:
        print(render_facts(result))
    else:
        json_print(view, compact=args.view == 'compact')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
