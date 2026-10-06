
"""Ten-year luck cycles judged by 《子平真诠》's own 取运 chapters (first batch: 正官, 财, 伤官).

A cycle's stem and branch are matched against the sentences of each 配法 the
chart's stems and storage allow (``assets/luck_rules.json``). Nothing here
settles the 格局: every 配法 is a candidate, interpretive conditions (身轻,
身旺, 财多…) stay open with both sides shown, and the verdict covers the ten
years, never a single day (spec: docs/superpowers/specs/2026-10-06-luck-assessment-design.md).
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from bazi_rules import evaluate_condition, family_candidates
from bazi_tables import DIZHI_CHONG, TIANGAN_HE
from utils import HIDDEN_STEMS, TIANGAN_WUXING, shi_shen

RULES_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'luck_rules.json'
PILLARS = ('year', 'month', 'day', 'hour')
LIMIT = ('配法按可计算的透藏列为候选；位置、合克、成败是否成立没判；'
         '十年一个结论，不细到每天。')


@cache
def load_luck_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding='utf-8'))


def _stems(chart: dict) -> list[tuple[str, str]]:
    """(pillar, stem) of the exposed stems other than the day master's."""
    pillars = chart.get('four_pillars') or {}
    return [(p, pillars[p]['stem']) for p in ('year', 'month', 'hour')
            if (pillars.get(p) or {}).get('stem') in TIANGAN_WUXING]


def _exposed_roles(chart: dict) -> list[tuple[str, str]]:
    day = chart['day_master']['stem']
    return [(stem, shi_shen(day, stem)) for _, stem in _stems(chart)]


def _premise(chart: dict, premise: dict) -> str:
    """'met', 'not_met' or 'unknown' for one premise."""
    predicate = premise['predicate']
    if predicate in ('present_any', 'exposed_any', 'exposed_none'):
        return evaluate_condition(chart, {'id': 'luck', 'label': premise.get('label', ''), 'kind': 'computed',
                                          'predicate': predicate, 'roles': premise['roles']})['state']
    exposed = _exposed_roles(chart)
    if predicate == 'exposed_count_at_least':
        return 'met' if sum(role in premise['roles'] for _, role in exposed) >= premise['count'] else 'not_met'
    if predicate == 'combines':
        left = [s for s, role in exposed if role in premise['roles']]
        right = [s for s, role in exposed if role in premise['with']]
        return 'met' if any(frozenset((a, b)) in TIANGAN_HE for a in left for b in right) else 'not_met'
    raise ValueError('unknown luck premise: ' + predicate)


def _applies(effect: dict, role: str, char: str, chart: dict) -> bool:
    if role in effect.get('roles', []):
        return True
    natal = [s for s, r in _exposed_roles(chart) if r in effect.get('combines_natal', [])]
    return bool(natal) and any(frozenset((char, s)) in TIANGAN_HE for s in natal)


def _verdicts(scenario: dict, role: str, char: str, chart: dict, is_stem: bool) -> list[dict]:
    """The scenario's sentences about this character: base effects, then branches.

    A computed branch that holds replaces the base verdict for the roles it
    names (「至於……則……」); an interpretive branch is listed beside it, open.
    """
    found: list[dict] = []
    overridden: set[str] = set()
    for branch in scenario.get('branches', []):
        state = _premise(chart, branch) if branch.get('predicate') else 'unknown'
        if branch['kind'] == 'computed' and state != 'met':
            continue
        if branch['kind'] == 'interpretive' and branch.get('predicate') and state != 'met':
            continue
        for effect in branch['effects']:
            if (is_stem or not effect.get('combines_natal')) and _applies(effect, role, char, chart):
                kind = 'met' if branch['kind'] == 'computed' else 'interpretive'
                found.append({'verdict': effect['verdict'], 'words': effect['words'],
                              'condition': branch['condition'], 'state': kind})
                if kind == 'met':
                    overridden.add(role)
    for effect in scenario.get('effects', []):
        if effect.get('combines_natal') and not is_stem:
            continue
        if _applies(effect, role, char, chart) and role not in overridden:
            found.insert(0, {'verdict': effect['verdict'], 'words': effect['words'], 'condition': None,
                             'state': 'met'})
    return found


def _summarise(definite: list[list[str]], conditional: list[list[str]]) -> str:
    """One word for a character across all candidate scenarios."""
    verdicts = {v for group in definite for v in group}
    if len(verdicts) == 1:
        return verdicts.pop()
    if verdicts:
        return 'mixed'
    return 'conditional' if any(conditional) else 'not_mentioned'


def _years(luck: dict) -> tuple[int | None, int | None]:
    if 'start_year' in luck:
        return luck.get('start_year'), luck.get('end_year')
    # An ISO end is when the next cycle starts; da_yun counts the cycle as start + 9.
    start = int(luck['start'][:4]) if luck.get('start') else None
    return start, (start + 9 if start is not None else None)


def _unavailable(reason: str, luck: dict) -> dict:
    return {'status': 'unavailable', 'reason': reason, 'luck': {'ganzhi': luck.get('ganzhi')},
            'granularity': 'ten_year_cycle', 'limit': LIMIT}


def assess_luck(chart: dict, luck: dict, registry: dict | None = None) -> dict:
    """What one ten-year cycle does under each candidate 配法 of the connected 格."""
    registry = registry or load_luck_rules()
    ganzhi = luck.get('ganzhi')
    if not ganzhi or luck.get('status', 'calculated') != 'calculated':
        return _unavailable('大运没算出来（起运资料不全）', luck)
    if not chart.get('hour_known'):
        return _unavailable('出生时辰未知，透干藏支判不全', luck)
    month = (chart.get('four_pillars') or {}).get('month') or {}
    if month.get('branch') not in HIDDEN_STEMS or month.get('candidate_ganzhi'):
        return _unavailable('月令没定（生在交节附近）', luck)
    day = chart['day_master']['stem']
    stem, branch = ganzhi[0], ganzhi[1]
    main = HIDDEN_STEMS[branch][0]
    stem_role, branch_role = shi_shen(day, stem), shi_shen(day, main)
    connected = {f['family_id']: f for f in registry['families']}
    families = [{'family_id': c['family_id'], 'title': c['title'], 'basis': c['basis'],
                 'connected': c['family_id'] in connected} for c in family_candidates(chart)]
    scenarios: list[dict] = []
    for family in families:
        if not family['connected']:
            continue
        for scenario in connected[family['family_id']]['scenarios']:
            premises = [{'label': p['label'], 'state': _premise(chart, p)} for p in scenario['premises']]
            if any(p['state'] != 'met' for p in premises):
                continue
            scenarios.append({
                'id': scenario['id'], 'title': scenario['title'], 'family_id': family['family_id'],
                'passage_id': scenario['passage_id'], 'quote': scenario['quote'], 'premises': premises,
                'stem': {'char': stem, 'role': stem_role,
                         'verdicts': _verdicts(scenario, stem_role, stem, chart, True)},
                'branch': {'char': branch, 'via': f'本气{main}', 'role': branch_role,
                           'verdicts': _verdicts(scenario, branch_role, branch, chart, False)}})
    summary = {}
    for part in ('stem', 'branch'):
        definite = [[v['verdict'] for v in s[part]['verdicts'] if v['state'] == 'met'] for s in scenarios]
        open_ = [[v['verdict'] for v in s[part]['verdicts'] if v['state'] == 'interpretive'] for s in scenarios]
        summary[part] = _summarise([d for d in definite if d], open_)
    start, end = _years(luck)
    reading = {'status': 'assessed', 'luck': {'ganzhi': ganzhi, 'start_year': start, 'end_year': end},
               'families': families, 'scenarios': scenarios, 'summary': summary,
               'granularity': 'ten_year_cycle', 'limit': LIMIT}
    reading['notes'] = _notes(chart, reading, registry)
    return reading


PILLAR_NAMES = {'year': '年支', 'month': '月支', 'day': '日支', 'hour': '时支'}


def _note(registry: dict, note_id: str, text: str, state: str = 'met') -> dict:
    source = next(n for n in registry['notes'] if n['id'] == note_id)
    return {'id': note_id, 'passage_id': source['passage_id'], 'quote': source['quote'], 'text': text, 'state': state}


def _notes(chart: dict, reading: dict, registry: dict) -> list[dict]:
    """《论行运》 rules the chart and the cycle can settle (spec §2.4)."""
    notes: list[dict] = []
    pillars = chart['four_pillars']
    stem, branch = reading['luck']['ganzhi']
    day = chart['day_master']['stem']
    stem_role = shi_shen(day, stem)
    connected = {f['family_id'] for f in reading['families'] if f['connected']}
    exposed = _exposed_roles(chart)
    roles = {r for _, r in exposed}
    officer_exposed = [s for s, r in exposed if r == '正官']
    if 'officer' in connected and officer_exposed and frozenset((branch, pillars['month']['branch'])) in DIZHI_CHONG:
        notes.append(_note(registry, 'N0', f"官露时，原文把地支刑冲算作不利；这步运的{branch}冲你的月支{pillars['month']['branch']}，"
                                           '原文没写冲哪一支才算，这里只提示，不判', 'conditional'))
    if ('officer' in connected and stem_role in ('正印', '偏印') and any(
            frozenset((o, s)) in TIANGAN_HE for o in officer_exposed for s, _ in exposed if s != o)):
        notes.append(_note(registry, 'N1', '这步是印运，看起来对官格是喜；但你的盘里透出的官被另一干合住，原文把这种情况算作似喜实忌'))
    if ('officer' in connected and stem_role == '伤官' and roles & {'正印', '偏印'}) or (
            'wealth' in connected and stem_role == '七杀' and '食神' in roles):
        notes.append(_note(registry, 'N2', ('官格逢伤官运、命里又透印' if stem_role == '伤官' else '财格逢七杀运、命里又透食')
                           + '，原文把这种情况算作似忌实喜'))
    clashes = [(p, pillars[p]['branch']) for p in PILLARS
               if frozenset((branch, (pillars.get(p) or {}).get('branch'))) in DIZHI_CHONG]
    if clashes:
        parts = [f"冲{PILLAR_NAMES[p]}{b}（{'急' if p in ('year', 'month') else '缓'}）" for p, b in clashes]
        notes.append(_note(registry, 'N3', f"这步运的{branch}" + '、'.join(parts)))
        weight = {'favoured': '算喜，逢冲伤得轻', 'avoided': '算忌，逢冲伤得重'}.get(reading['summary']['branch'])
        if weight:
            notes.append(_note(registry, 'N4', f'这步运的地支按上面的说法{weight}'))
    return notes


WORD = {'favoured': '喜', 'avoided': '忌', 'harmless': '不碍', 'unpromising': '未见其美'}


def _part(reading: dict, part: str) -> str:
    """One sentence about the cycle's stem or branch across the candidate 配法."""
    scenarios = reading['scenarios']
    first = scenarios[0][part]
    label = f"「{first['char']}」（{first['role']}" + (f"，按{first['via']}）" if part == 'branch' else '）')
    summary = reading['summary'][part]
    quotes = '、'.join(dict.fromkeys(f"「{v['words']}」" for s in scenarios for v in s[part]['verdicts']
                                    if v['state'] == 'met'))
    if summary in WORD:
        lead = '几种可能的配法都算' if len(scenarios) > 1 else '算'
        return f"对{label}{lead}{WORD[summary]}（{quotes}）"
    if summary == 'mixed':
        each = '；'.join(f"{s['title']}算{WORD[v['verdict']]}「{v['words']}」" for s in scenarios
                        for v in s[part]['verdicts'] if v['state'] == 'met')
        return f"对{label}几种配法说法不一：{each}"
    if summary == 'conditional':
        each = '；'.join(f"{s['title']}在「{v['condition']}」时算{WORD[v['verdict']]}「{v['words']}」"
                        for s in scenarios for v in s[part]['verdicts'] if v['state'] == 'interpretive')
        return f"对{label}要看条件：{each}，这些条件原文没给可计算的标准，这里没判"
    return f"对{label}这几种配法的取运句子都没提"


def luck_paragraph(reading: dict, who: str = '你') -> str:
    """Layer 2 of a period or chart answer: one ten-year cycle, cited."""
    luck = reading['luck']
    if reading['status'] != 'assessed':
        return f"这步大运的喜忌这次给不出：{reading['reason']}。"
    span = f"（{luck['start_year']}–{luck['end_year']}）" if luck.get('start_year') else ''
    head = f"{who}现在走的{luck['ganzhi']}运{span}。"
    pending = [f['title'] for f in reading['families'] if not f['connected']]
    if not reading['scenarios']:
        connected = [f['title'] for f in reading['families'] if f['connected']]
        body = (f"按月令{who}的盘是{'、'.join(connected)}格候选，但不属于已接入的配法。" if connected else
                f"按月令{who}的盘是{'、'.join(pending)}格候选，这一格的取运章还没接入，这步运的喜忌这次不判。")
        return head + body
    titles = '、'.join(s['title'] for s in reading['scenarios'])
    family = '、'.join(dict.fromkeys(f['title'] for f in reading['families'] if f['connected']))
    text = (head + f"按《子平真诠》{family}取运：{who}的盘按能算的透藏有{len(reading['scenarios'])}种可能的配法——{titles}。"
            + _part(reading, 'stem') + '；' + _part(reading, 'branch') + '。')
    text += ''.join(f"{n['text']}（原文「{n['quote']}」，{n['passage_id']}）。" for n in reading.get('notes', []))
    if pending:
        text += f"月令另有{'、'.join(pending)}格候选，取运章还没接入。"
    return text + (f"{who}的盘到底按哪种配法成立，还要看位置和合克，这里没判。"
                   '这是十年一个说法，不细到每天；逐日吉凶仍按出生年相主。')
