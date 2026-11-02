"""Minimum usable shapes for tool facts supplied to the answer checker.

Admission checks structure and success, not provenance or interpretation.
Rejected siblings remain in the result so a valid chart cannot hide them.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

PILLARS = frozenset(('year', 'month', 'day', 'hour'))
STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
GANZHI = frozenset(STEMS[i % 10] + BRANCHES[i % 12] for i in range(60))
CLOCK_WINDOW = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d–(?:[01]\d|2[0-3]):[0-5]\d')


@dataclass(frozen=True)
class EvidenceProblem:
    index: int
    reason: str


@dataclass(frozen=True)
class PillarEvidence:
    four_pillars: dict
    hour_known: bool
    label: str | None


@dataclass(frozen=True)
class ParsedEvidence:
    facts: tuple[dict, ...]
    chart_count: int
    problems: tuple[EvidenceProblem, ...]
    pillars: tuple[PillarEvidence, ...]


def _ganzhi(value: object) -> bool:
    return isinstance(value, str) and value in GANZHI


def _candidates(value: object) -> bool:
    return isinstance(value, list) and all(_ganzhi(item) for item in value)


def _windows(value: object, candidates: list) -> bool:
    if not isinstance(value, list):
        return False
    for window in value:
        if not isinstance(window, dict) or not isinstance(window.get('clock'), str):
            return False
        if not CLOCK_WINDOW.fullmatch(window['clock']):
            return False
        if _ganzhi(window.get('ganzhi')):
            if window['ganzhi'] not in candidates:
                return False
        else:
            repeated = window.get('repeated_clock')
            if window.get('ganzhi') is not None or not isinstance(repeated, dict):
                return False
            if not all(_ganzhi(repeated.get(key)) and repeated[key] in candidates for key in ('first', 'second')):
                return False
    return True


def _pillar(value: object, key: str) -> bool:
    if not isinstance(value, dict):
        return False
    if 'ganzhi' in value:
        return _ganzhi(value['ganzhi'])
    if key == 'hour' and value.get('status') == '时柱待补':
        return True
    if value.get('status') not in ('birth_time_required', 'birth_time_range'):
        return False
    candidates = value.get('candidate_ganzhi')
    if not isinstance(candidates, list):
        return False
    return _candidates(candidates) and ('candidate_windows' not in value or _windows(value['candidate_windows'], candidates))


def _natal(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    pillars = value.get('four_pillars')
    return isinstance(pillars, dict) and all(_pillar(pillars.get(key), key) for key in PILLARS)


def _bazi_reading(value: dict) -> bool:
    return _natal(value.get('chart_facts'))


def _fortune(value: dict) -> bool:
    people = value.get('participants')
    return isinstance(people, list) and bool(people) and all(
        isinstance(person, dict) and _natal(person.get('natal')) for person in people)


def _fortune_source(value: dict) -> bool:
    if 'participants' in value:
        return False
    capability = value.get('capability')
    if not isinstance(capability, dict):
        return False
    if value.get('status') == 'specialist_required':
        return capability.get('route') == 'specialist' and isinstance(value.get('message'), str) and bool(value['message'])
    if value.get('status') != 'partial' or capability.get('route') != 'itinerary':
        return False
    catalog, events, itinerary = value.get('natal_catalog'), value.get('events'), value.get('itinerary')
    if not isinstance(catalog, dict) or not catalog or not all(
            isinstance(row, dict) and _natal(row.get('natal')) for row in catalog.values()):
        return False
    if not isinstance(events, list) or len(events) < 2 or not isinstance(itinerary, dict):
        return False
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('result'), dict):
            return False
        people = event['result'].get('participants')
        if not isinstance(people, list) or not people or not all(
                isinstance(person, dict) and isinstance(person.get('natal_ref'), str)
                and person['natal_ref'] in catalog for person in people):
            return False
    return isinstance(itinerary.get('plans'), list) and isinstance(itinerary.get('status'), str)


def _pair(value: dict) -> bool:
    subjects = value.get('subjects')
    if not isinstance(subjects, dict) or not isinstance(value.get('relations'), list):
        return False
    for name in ('A', 'B'):
        subject = subjects.get(name)
        if not isinstance(subject, dict):
            return False
        decided, undecided = subject.get('four_pillars'), subject.get('undecided_pillars')
        if not isinstance(decided, dict) or not isinstance(undecided, dict):
            return False
        if set(decided) | set(undecided) != PILLARS or set(decided) & set(undecided):
            return False
        if not all(_ganzhi(item) for item in decided.values()) or not all(_candidates(item) for item in undecided.values()):
            return False
    return True


def _ziwei(value: dict) -> bool:
    palaces = value.get('twelve_palaces')
    if not isinstance(palaces, list) or len(palaces) != 12:
        return False
    if not all(isinstance(palace, dict) and type(palace.get('index')) is int
               and isinstance(palace.get('branch'), str) and len(palace['branch']) == 1 and palace['branch'] in BRANCHES
               and isinstance(palace.get('name'), str) and bool(palace['name'].strip()) for palace in palaces):
        return False
    return ({p['index'] for p in palaces} == set(range(12))
            and len({p['branch'] for p in palaces}) == 12 and len({p['name'] for p in palaces}) == 12)


def _liuyao(value: dict) -> bool:
    chart = value.get('main_chart')
    if not isinstance(chart, dict) or type(chart.get('hex_number')) is not int or not 1 <= chart['hex_number'] <= 64:
        return False
    if not isinstance(chart.get('hex_name'), str) or not chart['hex_name'].strip():
        return False
    lines = chart.get('lines')
    return (isinstance(lines, list) and len(lines) == 6
            and all(isinstance(line, dict) and type(line.get('position')) is int for line in lines)
            and {line['position'] for line in lines} == set(range(1, 7)))


def _liuyao_rules(value: dict) -> bool:
    rules = value.get('rules')
    return ('main_chart' not in value and isinstance(rules, list) and bool(rules)
            and all(isinstance(rule, dict) and isinstance(rule.get('id'), str) and bool(rule['id'])
                    and isinstance(rule.get('scope'), str) and bool(rule['scope']) for rule in rules))


def _pillar_strings(value: object, *, unknown_hour: bool = False) -> bool:
    return (isinstance(value, dict) and set(value) == PILLARS
            and all(_ganzhi(item) or (unknown_hour and key == 'hour' and item is None) for key, item in value.items()))


def _birth_candidates(value: dict) -> bool:
    segments = value.get('segments')
    return (value.get('mode') in ('range', 'candidates') and isinstance(segments, list) and bool(segments)
            and all(isinstance(row, dict) and _pillar_strings(row.get('four_pillars')) for row in segments))


def _birth_correction(value: dict) -> bool:
    return (isinstance(value.get('changed_fields'), list) and bool(value['changed_fields'])
            and all(isinstance(value.get(key), dict)
                    and _pillar_strings(value[key].get('four_pillars'), unknown_hour=True) for key in ('before', 'after')))


def _pillars_to_dates(value: dict) -> bool:
    return (_pillar_strings(value.get('pillars'), unknown_hour=True)
            and isinstance(value.get('range'), dict) and isinstance(value.get('candidates'), list))


def _rows(value: dict, key: str, fields: dict[str, type], *, empty: bool = True) -> bool:
    rows = value.get(key)
    return (isinstance(rows, list) and (empty or bool(rows))
            and all(isinstance(row, dict) and all(
                isinstance(row.get(name), kind) and (kind is not str or bool(row[name].strip()))
                for name, kind in fields.items()) for row in rows))


def _search(value: dict) -> bool:
    return (_rows(value, 'results', {'passage_id': str, 'text': str})
            or _rows(value, 'books', {'id': str, 'title': str}, empty=False)
            or (isinstance(value.get('witnesses'), dict)
                and isinstance(value['witnesses'].get('records'), list))
            or (value.get('errors') == [] and type(value.get('passages')) is int))


def _yilin_lin(value: object) -> bool:
    if not isinstance(value, dict) or not all(isinstance(value.get(k), str) and value[k] for k in ('ben', 'zhi')):
        return False
    if value.get('key') != value['ben'] + '之' + value['zhi']:
        return False
    versions = value.get('versions')
    if not isinstance(versions, list) or len(versions) != 2 or not all(isinstance(row, dict) for row in versions):
        return False
    if {row.get('book') for row in versions if isinstance(row.get('book'), str)} != {'yilin', 'yilin_siku'}:
        return False
    for row in versions:
        if not isinstance(row.get('edition'), str) or not row['edition']:
            return False
        if row.get('text') is None:
            if row.get('passage_id') is not None or not isinstance(row.get('reason'), str) or not row['reason']:
                return False
        elif not (isinstance(row['text'], str) and row['text']
                  and isinstance(row.get('passage_id'), str) and row['passage_id'].startswith(row['book'] + ':')
                  and isinstance(row.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])):
            return False
    return True


def _yilin(value: dict) -> bool:
    query = value.get('query')
    if not isinstance(query, dict) or not isinstance(query.get('from'), str):
        return False
    if query.get('to') is not None:
        lin = value.get('lin')
        return (isinstance(lin, dict) and _yilin_lin(lin) and lin['ben'] == query['from'] and lin['zhi'] == query['to'])
    lins = value.get('lins')
    return (isinstance(lins, list) and len(lins) == 64 and all(_yilin_lin(lin) and lin['ben'] == query['from'] for lin in lins)
            and len({lin['zhi'] for lin in lins}) == 64)


def _guidance(value: dict) -> bool:
    return ((isinstance(value.get('scenario'), str) and isinstance(value.get('routes'), list)
             and isinstance(value.get('source_status'), str))
            or (isinstance(value.get('plan'), dict) and isinstance(value.get('groups'), list)
                and value.get('retrieval_only') is True)
            or (isinstance(value.get('family'), str) and _rows(value, 'evidence', {'passage_id': str, 'text': str}, empty=False))
            or (isinstance(value.get('scenarios'), list) and isinstance(value.get('source_cards'), dict))
            or (value.get('errors') == [] and type(value.get('scenarios')) is int
                and type(value.get('luck_families')) is int))


def _life_guide(value: dict) -> bool:
    return (isinstance(value.get('source'), dict) and bool(value['source'])
            and (_rows(value, 'entries', {'title': str})
                 or _rows(value, 'articles', {'id': str, 'title': str})
                 or _rows(value, 'sections', {'title': str})
                 or isinstance(value.get('glossary'), (dict, list))
                 or (isinstance(value.get('decision'), dict) and bool(value['decision']))))


def _hex(value: object) -> bool:
    return (isinstance(value, dict) and type(value.get('number')) is int and 1 <= value['number'] <= 64
            and isinstance(value.get('name'), str) and bool(value['name']) and isinstance(value.get('lines'), list)
            and len(value['lines']) == 6)


def _calendar(value: dict) -> bool:
    return (isinstance(value.get('solar_date'), dict) and type(value['solar_date'].get('year')) is int
            and isinstance(value.get('lunar_date'), dict) and type(value['lunar_date'].get('year')) is int
            and isinstance(value.get('ganzhi'), dict) and all(_ganzhi(value['ganzhi'].get(k)) for k in ('year', 'month', 'day')))


def _method_rules(value: dict) -> bool:
    return (_rows(value, 'rules', {'id': str}, empty=False)
            or (value.get('errors') == [] and value.get('scope') in ('structural_only', 'frozen_excerpt_and_rule_schema')))


def _qimen_select(value: dict) -> bool:
    return (value.get('method') == 'dunjia-zhuanpan' and isinstance(value.get('input'), dict)
            and isinstance(value['input'].get('from'), str) and type(value['input'].get('days')) is int
            and isinstance(value.get('excluded'), dict)
            and _rows(value, 'candidates', {'date': str, 'window': str}))


def _fengshui(value: dict) -> bool:
    return (isinstance(value.get('measurement'), dict)
            and type(value['measurement'].get('input_bearing')) in (float, int)
            and isinstance(value.get('tradition'), dict)
            and all(isinstance(value['tradition'].get(k), dict)
                    and isinstance(value['tradition'][k].get('mountain'), str) for k in ('facing', 'sitting')))


def _zodiac(value: dict) -> bool:
    return ((isinstance(value.get('a'), str) and isinstance(value.get('b'), str)
             and isinstance(value.get('branches'), list) and len(value['branches']) == 2
             and isinstance(value.get('relations'), list) and type(value.get('score')) is int)
            or (type(value.get('year')) is int and isinstance(value.get('zodiac'), str))
            or (type(value.get('year')) is int and _ganzhi(value.get('year_ganzhi')))
            or (isinstance(value.get('zodiac'), str) and isinstance(value.get('branch'), str)
                and value.get('interpretation_status') == 'relations_only'))


SOURCE_CHECKS: dict[str, Callable[[dict], bool]] = {
    'classical_search': _search, 'classical_guidance': _guidance, 'life_guide': _life_guide, 'yilin': _yilin,
    'huangli': _calendar, 'lunar_convert': _calendar, 'method_rules': _method_rules,
    'meihua': lambda v: _hex(v.get('main_hex')) and isinstance(v.get('ti_yong'), dict),
    'yijing': lambda v: _hex(v.get('main_hex')) or _hex(v) or _rows(v, 'hexagrams', {'number': int, 'name': str}, empty=False),
    'qimen': lambda v: _pillar_strings(v.get('ganzhi')) and isinstance(v.get('palaces'), (dict, list)) and bool(v['palaces']),
    'daliuren': lambda v: _pillar_strings(v.get('ganzhi')) and isinstance(v.get('san_chuan'), dict)
        and v['san_chuan'].get('status') in ('supported', 'unsupported') and isinstance(v.get('si_ke'), list) and len(v['si_ke']) == 4,
    'xiaoliuren': lambda v: v.get('method') == '小六壬' and isinstance(v.get('result'), dict)
        and v['result'].get('palace') in ('大安', '留连', '速喜', '赤口', '小吉', '空亡'),
    'tiaohou_provenance': lambda v: (isinstance(v.get('review'), dict) and isinstance(v['review'].get('key'), str)
        and isinstance(v['review'].get('status'), str)) or (v.get('errors') == [] and isinstance(v.get('summary'), dict)),
    'zodiac': _zodiac,
    'name': lambda v: isinstance(v.get('name'), str) and _rows(v, 'characters', {'char': str}, empty=False)
        and isinstance(v.get('five_grids'), dict) and bool(v['five_grids']),
    'explore': lambda v: isinstance(v.get('origin'), dict) and isinstance(v.get('target'), dict)
        and all(type(v['target'].get(k)) in (float, int) for k in ('lat', 'lon')) and type(v.get('distance_m')) in (float, int),
    'tarot': lambda v: isinstance(v.get('spread'), str) and _rows(v, 'cards', {'card_name_zh': str, 'orientation': str}, empty=False),
    'jiemeng': lambda v: (isinstance(v.get('symbol'), str) and isinstance(v.get('category'), str))
        or _rows(v, 'matches', {'symbol': str})
        or (isinstance(v.get('categories'), list) and type(v.get('total_symbols')) is int),
    'reading_review': lambda v: v.get('errors') == [] and isinstance(v.get('packet'), dict)
        and isinstance(v['packet'].get('claims'), list) and v.get('semantic_review') == 'required',
    'fortune_rules': lambda v: _rows(v, 'capabilities', {'scenario': str}, empty=False)
        or (_rows(v, 'principle', {'passage_id': str, 'text': str}, empty=False)
            and isinstance(v.get('context_and_exceptions'), list)),
    'fengshui_measure': _fengshui, 'qimen_select': _qimen_select,
}


PRODUCERS: dict[str, tuple[Callable[[dict], bool] | None, Callable[[dict], bool] | None]] = {
    'bazi': (_natal, None), 'bazi_reading': (_bazi_reading, None), 'fortune_reading': (_fortune, _fortune_source),
    'pair_facts': (_pair, None), 'ziwei': (_ziwei, None), 'liuyao': (_liuyao, _liuyao_rules),
    'birth_candidates': (None, _birth_candidates), 'birth_correction': (None, _birth_correction),
    'pillars_to_dates': (None, _pillars_to_dates),
    **{name: (None, check) for name, check in SOURCE_CHECKS.items()},
}


def _pillar_root(chart: dict, label: str | None = None) -> PillarEvidence:
    return PillarEvidence(chart['four_pillars'], chart.get('hour_known', True) is not False, label)


def _pillar_evidence(value: dict) -> list[PillarEvidence]:
    tool = value['tool']
    if tool == 'bazi':
        return [_pillar_root(value)]
    if tool == 'bazi_reading':
        return [_pillar_root(value['chart_facts'])]
    if tool == 'pair_facts':
        return [PillarEvidence({**subject['four_pillars'],
                                **{key: {'status': 'birth_time_required', 'candidate_ganzhi': candidates}
                                   for key, candidates in subject['undecided_pillars'].items()}},
                               subject.get('hour_known', True) is not False, label)
                for label, subject in value['subjects'].items() if label in ('A', 'B')]
    if tool == 'fortune_reading':
        if 'participants' in value:
            return [_pillar_root(person['natal'], person.get('id')) for person in value['participants']]
        if value.get('capability', {}).get('route') == 'itinerary':
            return [_pillar_root(value['natal_catalog'][person['natal_ref']]['natal'], person.get('id'))
                    for event in value['events'] for person in event['result']['participants']]
    if tool == 'birth_candidates':
        return [_pillar_root(segment) for segment in value['segments']]
    if tool == 'birth_correction':
        return [_pillar_root(value[key], f'birth_correction:{key}') for key in ('before', 'after')]
    return []


def parse_evidence(values: object) -> ParsedEvidence:
    """Admit successful known envelopes and retain an indexed reason for each rejection."""
    if not isinstance(values, list):
        return ParsedEvidence((), 0, (EvidenceProblem(0, 'facts must be a list of tool outputs'),), ())
    facts, problems = [], []
    pillars = []
    chart_count = 0
    for index, value in enumerate(values):
        reason = ''
        if not isinstance(value, dict):
            reason = 'tool output must be an object'
        elif value.get('ok') is not True:
            reason = 'tool output requires ok=true'
            if value.get('error'):
                reason += f" ({value['error']})"
            if value.get('message'):
                reason += f": {str(value['message'])[:240]}"
        elif not isinstance(value.get('tool'), str) or value['tool'] not in PRODUCERS:
            reason = 'tool identity is missing, malformed or unsupported'
        else:
            chart_check, source_check = PRODUCERS[value['tool']]
            chart = chart_check is not None and chart_check(value)
            source = ((chart_check is None and source_check is None)
                      or (source_check is not None and source_check(value)))
            if not chart and not source:
                reason = f"{value['tool']} has no usable facts payload"
            else:
                facts.append(value)
                chart_count += chart
                pillars += _pillar_evidence(value)
        if reason:
            problems.append(EvidenceProblem(index, reason))
    return ParsedEvidence(tuple(facts), chart_count, tuple(problems), tuple(pillars))


def _geju(value: dict) -> dict:
    review = value.get('geju_review')
    if isinstance(review, dict) and review.get('verdict') == 'unresolved':
        families = review.get('families')
        if isinstance(families, list) and all(isinstance(row, dict) and isinstance(row.get('title'), str) for row in families):
            return {'geju_review': {'verdict': 'unresolved', 'families': [{'title': row['title']} for row in families]}}
    return {}


def _selection(value: dict) -> dict:
    fields: dict = {}
    for key in ('recommendation', 'ranking', 'practical_choice', 'practical_screening'):
        block = value.get(key)
        if isinstance(block, dict):
            fields[key] = {k: block[k] for k in ('status', 'ties')
                           if isinstance(block.get(k), str) or type(block.get(k)) is bool}
            tied = block.get('tied')
            if isinstance(tied, list) and all(isinstance(item, str) for item in tied):
                fields[key]['tied'] = tied
    return fields


def assertion_facts(evidence: ParsedEvidence) -> list[dict]:
    """Project diagnostic fields at their producer locations; incidental prose is not a fact."""
    projected = []
    for value in evidence.facts:
        if value['tool'] in ('bazi', 'bazi_reading'):
            projected.append(_geju(value))
        elif value['tool'] == 'fortune_reading':
            results = [value]
            people = value.get('participants', [])
            if 'participants' not in value and value['capability']['route'] == 'itinerary':
                results += [event['result'] for event in value['events']]
                people = list(value['natal_catalog'].values())
            projected += [_selection(result) for result in results]
            projected += [_geju(person['natal_interpretation']) for person in people
                          if isinstance(person.get('natal_interpretation'), dict)]
        elif value['tool'] == 'zodiac' and type(value.get('score')) is int:
            projected.append({'score': value['score']})
    return projected
