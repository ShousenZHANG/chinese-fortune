# 大运取运判断（第一批）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对当前（及下一步）大运，按《子平真诠》正官、财、伤官三章取运原文，给出运干、运支对本人是喜、忌、不碍、未见其美、看条件还是原文没提，每个结论带原句；十年一个结论，逐日相主不变。

**Architecture:** 新数据 `assets/luck_rules.json`（审定过的配法、前提、原句、喜忌）+ 新模块 `scripts/luck_assessment.py`（`assess_luck` 判断、`luck_paragraph` 渲染），复用 `bazi_rules.family_candidates` 与 `evaluate_condition` 判透藏；`fortune_reading.py`、`bazi_reading.py` 只在输出层接入。

**Tech Stack:** Python 3.11+，pytest，现有 `classical_search.get_passage`、`bazi_rules`、`bazi_tables`、`utils.shi_shen`/`HIDDEN_STEMS`。

**Spec:** `docs/superpowers/specs/2026-10-06-luck-assessment-design.md`

## Global Constraints

- 运行：`python -X utf8`；测试 `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q`（全量加 `-n auto`）。
- Windows + Git Bash；含反斜杠的补丁写成 Python 文件执行，不用 heredoc。
- 十年一个结论，不改逐日相主等级，不做流年（spec §1）。
- 不用身强弱打分替原文选「身轻／身旺」分支（spec §1）。
- 每个 `words` 必须是 `quote` 子串；`quote` 必须是冻结原文子串且 `sha256` 一致（spec §2、§5）。
- `verdict` 只有 `favoured`、`avoided`、`harmless`、`unpromising`；汇总另有 `mixed`、`conditional`、`not_mentioned`（spec §2、§3）。
- 「助印」「助財」只照字面记为印、财本身（spec §2.3）。
- 地支按本气藏干取十神，输出注明「按本气」（spec §2.4）。
- 只接 `officer`、`wealth`、`hurt` 三族；其余候选 `connected: false`（spec §3）。
- 提交信息用 conventional commits，不加 Co-Authored-By。

---

### Task 1: 审定数据 `assets/luck_rules.json` 与完整性测试

**Files:**
- Create: `assets/luck_rules.json`
- Create: `tests/test_luck_assessment.py`

**Interfaces:**
- Produces: `assets/luck_rules.json`，结构：`{"schema_version","book","verification","families":[{"family_id","title","chapter","scenarios":[{"id","title","passage_id","sha256","quote","premises":[{"label","predicate","roles"?, "with"?, "count"?}],"effects":[{"roles"?, "combines_natal"?, "verdict","words"}],"branches":[{"kind":"computed|interpretive","condition","predicate"?, "effects":[...]}]}]}],"notes":[{"id","passage_id","sha256","quote"}]}`。
  - `predicate` ∈ `present_any`、`exposed_any`、`exposed_none`（交给 `bazi_rules.evaluate_condition`）、`combines`（`roles` 中某透干与 `with` 中某透干天干五合）、`exposed_count_at_least`（`roles` 透干个数 ≥ `count`）。
  - `combines_natal`：运干与本命某个 `combines_natal` 类透干五合时适用。

- [ ] **Step 1: 写数据完整性测试（先失败）**

```python
"""大运取运判断：审定数据与判断逻辑（spec docs/superpowers/specs/2026-10-06-luck-assessment-design.md）。"""
import json
from pathlib import Path

import pytest
from classical_search import get_passage

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / 'assets' / 'luck_rules.json').read_text(encoding='utf-8'))
ROLES = {'比肩', '劫财', '食神', '伤官', '偏财', '正财', '七杀', '正官', '偏印', '正印'}
VERDICTS = {'favoured', 'avoided', 'harmless', 'unpromising'}
PREDICATES = {'present_any', 'exposed_any', 'exposed_none', 'combines', 'exposed_count_at_least'}


def _scenarios():
    return [s for f in RULES['families'] for s in f['scenarios']]


def _effects(s):
    return s.get('effects', []) + [e for b in s.get('branches', []) for e in b['effects']]


def test_only_the_first_batch_is_connected():
    assert [f['family_id'] for f in RULES['families']] == ['officer', 'wealth', 'hurt']
    assert [f['chapter'] for f in RULES['families']] == ['ziping:c032', 'ziping:c034', 'ziping:c042']


@pytest.mark.parametrize('scenario', _scenarios(), ids=lambda s: s['id'])
def test_every_quote_is_the_frozen_text_and_every_verdict_is_in_it(scenario):
    passage = get_passage(scenario['passage_id'])
    assert passage['sha256'] == scenario['sha256']
    assert scenario['quote'] in passage['text']
    for effect in _effects(scenario):
        assert effect['verdict'] in VERDICTS
        assert effect['words'] in scenario['quote'], (scenario['id'], effect['words'])
        assert set(effect.get('roles', [])) <= ROLES and set(effect.get('combines_natal', [])) <= ROLES
        assert effect.get('roles') or effect.get('combines_natal')
    for premise in scenario['premises'] + [b for b in scenario.get('branches', []) if b.get('predicate')]:
        assert premise['predicate'] in PREDICATES
        assert set(premise.get('roles', [])) <= ROLES and set(premise.get('with', [])) <= ROLES
    for branch in scenario.get('branches', []):
        assert branch['kind'] in ('computed', 'interpretive')
        assert branch['kind'] == 'interpretive' or branch.get('predicate')


def test_every_luck_paragraph_of_the_three_chapters_has_a_scenario():
    """All but each chapter's general remarks (c032 p0001 p0007, c034 p0001, c042 p0001)."""
    used = {s['passage_id'] for s in _scenarios()}
    expected = ({f'ziping:c032:p{i:04}' for i in range(2, 7)} | {f'ziping:c034:p{i:04}' for i in range(2, 9)}
                | {f'ziping:c042:p{i:04}' for i in range(2, 8)})
    assert used == expected


@pytest.mark.parametrize('note', RULES['notes'], ids=lambda n: n['id'])
def test_every_general_note_is_the_frozen_text(note):
    passage = get_passage(note['passage_id'])
    assert passage['sha256'] == note['sha256'] and note['quote'] in passage['text']
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py`
Expected: FAIL（`luck_rules.json` 不存在）。

- [ ] **Step 3: 写数据文件**

`assets/luck_rules.json` 全文见本计划附录 A（逐条对应 spec §2.1–§2.4 的表格）。

- [ ] **Step 4: 运行，确认通过**

Run: 同 Step 2。Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add assets/luck_rules.json tests/test_luck_assessment.py
git commit -m "feat: reviewed luck rules for officer, wealth and hurt cycles"
```

---

### Task 2: `assess_luck` 判断逻辑

**Files:**
- Create: `scripts/luck_assessment.py`
- Modify: `tests/test_luck_assessment.py`（追加）

**Interfaces:**
- Consumes: `assets/luck_rules.json`（Task 1）；`bazi_rules.family_candidates(chart)`、`bazi_rules.evaluate_condition(chart, condition)`；`utils.shi_shen(day, stem)`、`utils.HIDDEN_STEMS`；`bazi_tables.TIANGAN_HE`、`bazi_tables.DIZHI_CHONG`。
- Produces: `assess_luck(chart: dict, luck: dict, registry: dict | None = None) -> dict`，返回 spec §3 的结构；`luck` 接受 `{'ganzhi', 'start_year', 'end_year'}` 或 `{'status': 'calculated', 'ganzhi', 'start', 'end'}`（ISO 字符串）。`load_luck_rules() -> dict`。

- [ ] **Step 1: 追加测试（先失败）**

```python
from luck_assessment import assess_luck


def _chart(year, month, day, hour, hour_known=True):
    pillars = {'year': {'stem': year[0], 'branch': year[1]}, 'month': {'stem': month[0], 'branch': month[1]},
               'day': {'stem': day[0], 'branch': day[1]}, 'hour': {'stem': hour[0], 'branch': hour[1]}}
    return {'day_master': {'stem': day[0]}, 'four_pillars': pillars, 'hour_known': hour_known}


USER = _chart('丁丑', '壬子', '庚子', '丙戌')
JI_YOU = {'ganzhi': '己酉', 'start_year': 2023, 'end_year': 2032}


def test_the_users_own_chart_in_the_ji_you_cycle():
    """庚 in 子 (伤官): 佩印, 用煞印, 带煞, 用官 all stand by the stems and storage."""
    reading = assess_luck(USER, JI_YOU)
    assert reading['status'] == 'assessed'
    assert {s['id'] for s in reading['scenarios']} == {'hurt-seal', 'hurt-kill-seal', 'hurt-kill', 'hurt-officer'}
    assert reading['summary'] == {'stem': 'favoured', 'branch': 'conditional'}
    assert reading['scenarios'][0]['branch']['via'] == '本气辛'
    assert {f['family_id']: f['connected'] for f in reading['families']} == {'hurt': True, 'food': False}


def test_a_missing_hour_or_cycle_gives_no_verdict():
    assert assess_luck(_chart('丁丑', '壬子', '庚子', '丙戌', hour_known=False), JI_YOU)['status'] == 'unavailable'
    assert assess_luck(USER, {'status': 'birth_time_required'})['status'] == 'unavailable'


def test_a_family_not_yet_connected_is_said_so():
    """甲 in 子: 癸 is 正印, the seal family, whose chapter is not in this batch."""
    reading = assess_luck(_chart('甲子', '丙子', '甲寅', '甲子'), {'ganzhi': '丁丑', 'start_year': 2020, 'end_year': 2029})
    assert reading['status'] == 'assessed' and not reading['scenarios']
    assert reading['families'][0]['connected'] is False


def test_a_computed_branch_overrides_the_general_sentence():
    """财旺生官带食破局: 「逢煞反吉」 replaces 「不利七煞」 (c034 p0002)."""
    # 甲 in 辰 (戊 偏财 本气), 辛 正官 exposed, 丙 食神 exposed; 七杀 庚 cycle.
    chart = _chart('辛酉', '丙辰', '甲子', '丙寅')
    reading = assess_luck(chart, {'ganzhi': '庚午', 'start_year': 2020, 'end_year': 2029})
    w1 = next(s for s in reading['scenarios'] if s['id'] == 'wealth-officer')
    assert [v['verdict'] for v in w1['stem']['verdicts']] == ['favoured']
    assert w1['stem']['verdicts'][0]['words'] == '逢煞反吉'


def test_a_cycle_stem_combining_the_exposed_officer_is_avoided():
    """《论行运》p0008 「丁生亥月，而年透壬官……逢丁則合官」: 丁 combines the 壬 officer, 「不可逢合」 (c032 p0002)."""
    chart = _chart('壬寅', '辛亥', '丁卯', '庚子')
    reading = assess_luck(chart, {'ganzhi': '丁未', 'start_year': 2020, 'end_year': 2029})
    general = next(s for s in reading['scenarios'] if s['id'] == 'officer-exposed')
    assert [v['words'] for v in general['stem']['verdicts']] == ['不可逢合']


def test_robbery_combining_the_killer_is_computed():
    """正官带煞, 用劫合煞 (c032 p0006): 乙 劫财 and 庚 七杀 both exposed for 甲, 乙庚 combine."""
    chart = _chart('乙卯', '辛酉', '甲子', '庚午')
    reading = assess_luck(chart, {'ganzhi': '戊申', 'start_year': 2020, 'end_year': 2029})
    o5 = next(s for s in reading['scenarios'] if s['id'] == 'officer-kill')
    assert any(v['words'] == '財運可行' and v['state'] == 'met' for v in o5['stem']['verdicts'])


def test_conflicting_candidates_are_mixed_not_chosen():
    """伤官佩印 says 「財地則凶」, 伤官用财's strong-body branch 「喜財運」: a wealth cycle is
    avoided in one and only conditional in the other, so the summary keeps the definite one;
    two definite opposite verdicts would be mixed."""
    from luck_assessment import _summarise
    assert _summarise([['favoured'], ['avoided']], []) == 'mixed'
    assert _summarise([['favoured'], ['favoured']], [['avoided']]) == 'favoured'
    assert _summarise([], [['favoured']]) == 'conditional'
    assert _summarise([], []) == 'not_mentioned'
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py`
Expected: FAIL（`ModuleNotFoundError: luck_assessment`）。

- [ ] **Step 3: 写模块**

```python
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
    start, end = luck.get('start'), luck.get('end')
    return (int(start[:4]) if start else None, int(end[:4]) if end else None)


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


def _notes(chart: dict, reading: dict, registry: dict) -> list[dict]:
    """Filled in by Task 3."""
    return []
```

- [ ] **Step 4: 运行，确认通过**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/luck_assessment.py tests/test_luck_assessment.py
git commit -m "feat: judge a luck cycle against each candidate 配法"
```

---

### Task 3: 《论行运》通则备注 N0–N4

**Files:**
- Modify: `scripts/luck_assessment.py`（替换 `_notes`）
- Modify: `tests/test_luck_assessment.py`（追加）

**Interfaces:**
- Consumes: `registry['notes']`（Task 1，id 为 `N0`–`N4`），`reading['summary']`、`reading['families']`、`reading['scenarios']`（Task 2）。
- Produces: `reading['notes']: list[{'id','passage_id','quote','text','state'}]`，`state` ∈ `met`、`conditional`。

- [ ] **Step 1: 追加测试（先失败）**

```python
def test_a_clash_with_the_year_or_month_is_urgent_with_the_day_or_hour_mild():
    """《论行运》p0006 丙生子月亥年：巳 clashes 亥 (year), 午 clashes 子 (month); p0010 年月则急。"""
    chart = _chart('辛亥', '庚子', '丙寅', '戊戌')
    si = assess_luck(chart, {'ganzhi': '丁巳', 'start_year': 2020, 'end_year': 2029})
    n3 = next(n for n in si['notes'] if n['id'] == 'N3')
    assert '冲年支亥' in n3['text'] and '急' in n3['text']
    shen = assess_luck(chart, {'ganzhi': '丙申', 'start_year': 2030, 'end_year': 2039})
    assert '冲日支寅' in next(n for n in shen['notes'] if n['id'] == 'N3')['text']
    assert '缓' in next(n for n in shen['notes'] if n['id'] == 'N3')['text']


def test_an_officer_cycle_of_hurt_with_a_seal_exposed_seems_bad_but_is_not():
    """p0005 「官逢傷運，而命透印」."""
    chart = _chart('癸酉', '辛酉', '甲子', '癸酉')     # 甲 in 酉: 辛 正官 本气; 癸 正印 exposed
    reading = assess_luck(chart, {'ganzhi': '丁卯', 'start_year': 2020, 'end_year': 2029})
    assert any(n['id'] == 'N2' for n in reading['notes'])


def test_no_note_when_nothing_clashes():
    reading = assess_luck(USER, JI_YOU)        # 酉 clashes 卯; the user's branches are 丑子子戌
    assert not any(n['id'] == 'N3' for n in reading['notes'])
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py -k "clash or seems or nothing"`
Expected: FAIL（`StopIteration` / 断言失败）。

- [ ] **Step 3: 替换 `_notes`**

```python
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
```

- [ ] **Step 4: 运行，确认通过**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/luck_assessment.py tests/test_luck_assessment.py
git commit -m "feat: clash and seeming-good notes from 论行运"
```

---

### Task 4: `luck_paragraph` 白话渲染

**Files:**
- Modify: `scripts/luck_assessment.py`（追加）
- Modify: `tests/test_luck_assessment.py`（追加）

**Interfaces:**
- Consumes: `assess_luck` 返回值。
- Produces: `luck_paragraph(reading: dict, who: str = '你') -> str`。

- [ ] **Step 1: 追加测试（先失败）**

```python
def test_the_paragraph_says_the_cycle_the_agreement_and_the_limits():
    from luck_assessment import luck_paragraph
    text = luck_paragraph(assess_luck(USER, JI_YOU))
    assert text.startswith('你现在走的己酉运（2023–2032）')
    assert '几种可能的配法都算喜' in text and '「印運亦吉」' in text
    assert '看条件' in text and '按本气辛' in text
    assert '十年一个说法，不细到每天' in text and '逐日吉凶仍按出生年相主' in text


def test_the_paragraph_for_an_unconnected_family_or_missing_hour():
    from luck_assessment import luck_paragraph
    seal = assess_luck(_chart('甲子', '丙子', '甲寅', '甲子'), {'ganzhi': '丁丑', 'start_year': 2020, 'end_year': 2029})
    assert '取运章还没接入' in luck_paragraph(seal)
    gone = assess_luck(_chart('丁丑', '壬子', '庚子', '丙戌', hour_known=False), JI_YOU)
    assert luck_paragraph(gone).startswith('这步大运的喜忌这次给不出：出生时辰未知')
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py -k paragraph`
Expected: FAIL（`ImportError: luck_paragraph`）。

- [ ] **Step 3: 追加渲染函数**

```python
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
    text += ''.join(n['text'] + '。' for n in reading.get('notes', []))
    if pending:
        text += f"月令另有{'、'.join(pending)}格候选，取运章还没接入。"
    return text + (f"{who}的盘到底按哪种配法成立，还要看位置和合克，这里没判。"
                   '这是十年一个说法，不细到每天；逐日吉凶仍按出生年相主。')
```

- [ ] **Step 4: 运行，确认通过**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/luck_assessment.py tests/test_luck_assessment.py
git commit -m "feat: plain-language paragraph for a luck cycle"
```

---

### Task 5: 接入 `fortune_reading.py`

**Files:**
- Modify: `scripts/fortune_reading.py:186`（`row['traditional_observations']` 之后）与 `render_answer`（`traditional_observations` 循环之后、兜底段落条件）
- Modify: `tests/test_luck_assessment.py`（追加）

**Interfaces:**
- Consumes: `assess_luck`、`luck_paragraph`；`target['luck_catalog']`（`fortune_calendar.active_luck` 的输出，含 `status`、`ganzhi`、`start`、`end`）。
- Produces: `participants[].luck_reading: list[dict]`（目标窗口内生效的每步大运，至多两步）；渲染时在有 `personal_calendar` 的回答里加段。

- [ ] **Step 1: 追加端到端测试（先失败）**

```python
def _period(start, end):
    return {'current_timezone': 'Asia/Shanghai', 'request_time': '2026-10-05T10:00:00Z',
            'question': '未来七天哪天对我好', 'intent': 'period', 'period': {'start': start, 'end': end},
            'event': {'scenario': 'outlook', 'timezone': 'Asia/Shanghai', 'longitude': 120.64},
            'participants': [{'id': 'me', 'confirmed': True, 'person': {
                'birth': {'year': 1997, 'month': 12, 'day': 24, 'hour': 19, 'minute': 30, 'gender': 'male',
                          'timezone': 'Asia/Shanghai', 'longitude': 120.64}, 'time_certainty': 'exact'}}]}


def test_a_period_answer_carries_the_cycle_and_keeps_the_daily_grades():
    from fortune_reading import read_request, render_answer
    result = read_request(_period('2026-10-06T00:00:00+08:00', '2026-10-13T00:00:00+08:00'))
    readings = result['participants'][0]['luck_reading']
    assert [r['luck']['ganzhi'] for r in readings] == ['己酉'] and readings[0]['status'] == 'assessed'
    grades = [e['grade'] for e in result['personal_calendar']['entries']]
    text = render_answer(result)
    assert '你现在走的己酉运' in text and '逐日吉凶仍按出生年相主' in text
    assert '已实现的两条运程例式没有给出本题的完整结论' not in text
    assert grades == [e['grade'] for e in read_request(_period('2026-10-06T00:00:00+08:00',
                                                               '2026-10-13T00:00:00+08:00'))['personal_calendar']['entries']]
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py -k period`
Expected: FAIL（`KeyError: 'luck_reading'`）。

- [ ] **Step 3: 接入**

在 `scripts/fortune_reading.py` 顶部 import 区加：

```python
from luck_assessment import assess_luck, luck_paragraph
```

在 `row['traditional_observations'] = luck_observations(natal, target)` 之后加：

```python
    # 《子平真诠》取运 for each ten-year cycle the window touches: ten years per verdict.
    row['luck_reading'] = [assess_luck(natal, luck) for luck in target['luck_catalog'][:2]
                           if luck.get('status') == 'calculated']
```

在 `render_answer` 中，`for observation in person['traditional_observations'][:2]:` 循环结束后（仍在 `for person in result['participants']:` 内）加：

```python
        if result.get('personal_calendar'):
            who = '你' if len(result['participants']) == 1 else person['id']
            lines.extend(luck_paragraph(r, who) for r in person.get('luck_reading', []))
```

把兜底段落的条件

```python
    if not ranking and not any(p['traditional_observations'] for p in result['participants']):
```

改为

```python
    assessed = bool(result.get('personal_calendar')) and any(
        r['status'] == 'assessed' for p in result['participants'] for r in p.get('luck_reading', []))
    if not ranking and not assessed and not any(p['traditional_observations'] for p in result['participants']):
```

- [ ] **Step 4: 运行相关测试**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py tests/test_fortune_reading.py tests/test_xiangzhu.py`
Expected: PASS（若已有测试断言兜底段落出现，按新条件更新该断言并在提交信息里说明）。

- [ ] **Step 5: 提交**

```bash
git add scripts/fortune_reading.py tests/test_luck_assessment.py
git commit -m "feat: period answers carry the active luck cycle's verdict"
```

---

### Task 6: 接入 `bazi_reading.py`

**Files:**
- Modify: `scripts/bazi_reading.py`（`prepare_reading` 返回值、`render_facts` 末段之前）
- Modify: `tests/test_luck_assessment.py`（追加）

**Interfaces:**
- Consumes: `assess_luck`、`luck_paragraph`；`chart_facts` 中的 `da_yun`（`start_year`、`end_year`、`ganzhi`）、`current_time_context.local`、`liu_nian[0].year`。
- Produces: `prepare_reading(...)['luck_reading']: list[dict]`（当前与下一步大运），仅在问题含 `LUCK_WORDS` 时出现。

- [ ] **Step 1: 追加测试（先失败）**

```python
def test_a_chart_question_about_the_coming_years_gets_this_and_the_next_cycle():
    from bazi_calc import build_parser, calculate_bazi
    from bazi_reading import prepare_reading, render_facts
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '1997', '--month', '12', '--day', '24', '--hour', '19', '--minute', '30',
        '--gender', 'male', '--as-of-year', '2026']))
    result = prepare_reading(chart, '我这几年运势怎么样')
    assert [r['luck']['ganzhi'] for r in result['luck_reading']] == ['己酉', '戊申']
    assert '你现在走的己酉运' in render_facts(result)
    assert 'luck_reading' not in prepare_reading(chart, '我适合做什么工作')
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py -k coming`
Expected: FAIL（`KeyError: 'luck_reading'`）。

- [ ] **Step 3: 接入**

`scripts/bazi_reading.py` import 区加：

```python
from luck_assessment import assess_luck, luck_paragraph
```

模块级常量（`SHI_SHEN_PLAIN` 之前）加：

```python
# Questions about the coming years: answer with this and the next ten-year cycle.
LUCK_WORDS = ('大运', '运势', '这几年', '今年', '明年', '这十年', '走什么运', '运程', '行运')


def _cycles_now(clean: dict) -> list[dict]:
    """This and the next ten-year cycle, by the chart's own reference year."""
    context = clean.get('current_time_context') or {}
    year = int(context['local'][:4]) if context.get('local') else (
        (clean.get('liu_nian') or [{}])[0].get('year'))
    cycles = clean.get('da_yun') or []
    if not year or not cycles:
        return []
    at = next((i for i, c in enumerate(cycles) if c['start_year'] <= year <= c['end_year']), None)
    return [] if at is None else cycles[at:at + 2]
```

`prepare_reading` 中 `extra` 定义之后加：

```python
    if any(word in question for word in LUCK_WORDS):
        extra['luck_reading'] = [assess_luck(clean, cycle) for cycle in _cycles_now(clean)]
```

`render_facts` 中 `parts.append('上述检查用于传统原局分析；完整回答还需结合本题核完解释条件。')` 之前加：

```python
    for index, reading in enumerate(result.get('luck_reading', [])):
        text = luck_paragraph(reading)
        parts.append(text if index == 0 else text.replace('你现在走的', '下一步是', 1))
```

- [ ] **Step 4: 运行相关测试**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q tests/test_luck_assessment.py tests/test_bazi_reading.py tests/test_wuxing_colours.py`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/bazi_reading.py tests/test_luck_assessment.py
git commit -m "feat: chart answers about the coming years carry this and the next cycle"
```

---

### Task 7: 文档、能力目录、冒烟、版本

**Files:**
- Modify: `scripts/fortune_rules.py:18`（`outlook` 能力说明）
- Modify: `references/24-personalized-forecast.md`（「当前能做到哪里」表的「古籍解释」行）
- Modify: `references/01-bazi.md`（颜色段之后加一段大运取运）
- Modify: `evals/package_smoke.py`（加一项）
- Modify: `CHANGELOG.md`（新 `[5.5.0]`）、`scripts/utils.py`（`__version__ = "5.5.0"`）

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 文档与发布包验收。

- [ ] **Step 1: 改能力目录与文档**

`scripts/fortune_rules.py` 中 `'outlook'` 一行的第三项改为：

```python
'个人日子吉凶按协纪相主（出生年干支）已实现；大运按《子平真诠》正官、财、伤官三章取运给十年一个喜忌（其余五格未接），与逐日分开'
```

`references/24-personalized-forecast.md` 表中「古籍解释」行改为：

```markdown
| 古籍解释 | 保留本命核查及《子平真诠·论行运》14 段正文与例外；两种具体例式可核个人条件。大运另按正官、财、伤官三章取运逐步给喜忌（`participants[].luck_reading`，见 [八字](01-bazi.md)），十年一个结论，不改逐日等级；其余五格的取运章未接 |
```

`references/01-bazi.md` 在颜色说明两段之后加：

```markdown
问运势、这几年、大运时，`bazi_reading.py` 对当前和下一步大运给 `luck_reading`：按月令候选（正官、财、伤官三格已接入，其余五格写明未接）和能计算的透藏，列出符合的《子平真诠》取运配法；对运干、运支（按本气）逐一给喜、忌、不碍、未见其美、看条件或原文没提，每条带原句。几种配法说法一致才直说，不一致分列；「身轻／身旺」「财多／印多」这类原文没给标准的条件两边都列、不判。另按《论行运》提示冲年月为急、冲日时为缓，以及似喜实忌、似忌实喜。这是十年一个结论，不细到每天。
```

- [ ] **Step 2: 冒烟加一项**

`evals/package_smoke.py` 中 `colours = ...` 断言之后加：

```python
        luck = json.loads(run([str(python), '-X', 'utf8', str(skill / 'scripts/bazi_reading.py'),
                               '--year', '1997', '--month', '12', '--day', '24', '--hour', '19', '--minute', '30',
                               '--gender', 'male', '--timezone', 'Asia/Shanghai', '--longitude', '120',
                               '--as-of-year', '2026', '--question', '我这几年运势怎么样'], work))
        assert luck['luck_reading'][0]['status'] == 'assessed' and luck['luck_reading'][0]['luck']['ganzhi'] == '己酉'
```

- [ ] **Step 3: CHANGELOG 与版本**

`scripts/utils.py`：`__version__ = "5.5.0"`。`CHANGELOG.md` 顶部加：

```markdown
## [5.5.0] — 大运按《子平真诠》取运给喜忌（第一批：正官、财、伤官）

- 问运势、这几年、大运时，对当前和下一步大运按月令候选与能计算的透藏，列出符合的取运配法（正官 6 种、财 7 种、伤官 6 种，逐句对照原文审定，见 `assets/luck_rules.json`），对运干、运支逐一给喜、忌、不碍、未见其美、看条件或原文没提，每条带原句；几种配法说法一致才直说，不一致分列；「身轻／身旺」这类原文没给标准的条件两边都列、不判。
- 另按《论行运》提示：冲年月为急、冲日时为缓；运美逢冲轻、运忌逢冲重；官逢印运而官被合是似喜实忌，官逢伤运而命透印、财逢煞运而命透食是似忌实喜。
- 十年一个结论，不细到每天；逐日吉凶仍按出生年相主，两层分开写。其余五格（印、食神、七杀、阳刃、建禄月劫）写明「取运章还没接入」。
- 依据：GPT 对 v5.3.0 的审计报告第 5 节；设计 `docs/superpowers/specs/2026-10-06-luck-assessment-design.md`。
```

- [ ] **Step 4: 全量验证**

Run: `python -X utf8 -m pytest -p no:timeouts -p no:cacheprovider -q -n auto` → PASS；`ruff check scripts tests evals` → All checks passed；`mypy scripts` → no issues；`python -X utf8 scripts/build_skill.py --dist-dir <scratchpad>/dist55` 后 `python -X utf8 evals/package_smoke.py --archive <scratchpad>/dist55/chinese-fortune-v5.5.0.zip` → exit 0。

- [ ] **Step 5: 提交**

```bash
git add scripts/fortune_rules.py references/24-personalized-forecast.md references/01-bazi.md evals/package_smoke.py CHANGELOG.md scripts/utils.py
git commit -m "docs: 5.5.0 notes, luck-cycle reference, smoke item"
```

---

## 附录 A：`assets/luck_rules.json`

角色缩写（写入 JSON 时展开为十神名）：官 `正官`；杀 `七杀`；财 `正财`、`偏财`；印 `正印`、`偏印`；食 `食神`；伤 `伤官`；食伤 `食神`、`伤官`；比劫 `比肩`、`劫财`。

```json
{
 "schema_version": "1.0",
 "book": "ziping",
 "verification": "transcription_checked_mapping_reviewed_2026-10-06",
 "families": [
  {
   "family_id": "officer",
   "title": "正官",
   "chapter": "ziping:c032",
   "scenarios": [
    {
     "id": "officer-exposed",
     "title": "官露通忌",
     "passage_id": "ziping:c032:p0002",
     "sha256": "53c25c334fd3462afaf04e9de350091d5006cdfd591204374fee330d8dd4294c",
     "quote": "若官露而不可逢合、不可雜煞、不可重官與地支刑沖，不問所就何局，皆不利也。",
     "premises": [
      {
       "label": "正官透出",
       "predicate": "exposed_any",
       "roles": [
        "正官"
       ]
      }
     ],
     "effects": [
      {
       "combines_natal": [
        "正官"
       ],
       "verdict": "avoided",
       "words": "不可逢合"
      },
      {
       "roles": [
        "七杀"
       ],
       "verdict": "avoided",
       "words": "不可雜煞"
      },
      {
       "roles": [
        "正官"
       ],
       "verdict": "avoided",
       "words": "不可重官"
      }
     ]
    },
    {
     "id": "officer-wealth-seal",
     "title": "正官而用财印",
     "passage_id": "ziping:c032:p0002",
     "sha256": "53c25c334fd3462afaf04e9de350091d5006cdfd591204374fee330d8dd4294c",
     "quote": "正官而用財印，身稍輕則取助身，官稍輕則助官。",
     "premises": [
      {
       "label": "正官可见",
       "predicate": "present_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "财透出",
       "predicate": "exposed_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "印透出",
       "predicate": "exposed_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "身稍輕",
       "effects": [
        {
         "roles": [
          "正印",
          "偏印",
          "比肩",
          "劫财"
         ],
         "verdict": "favoured",
         "words": "取助身"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "官稍輕",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财",
          "正官"
         ],
         "verdict": "favoured",
         "words": "助官"
        }
       ]
      }
     ]
    },
    {
     "id": "officer-wealth",
     "title": "正官用财",
     "passage_id": "ziping:c032:p0003",
     "sha256": "3641b09d75fbfe429ae32007dd9aa98fd5e3209b099b95e11792175c0883eb40",
     "quote": "正官用財，運喜印綬身旺之地，切忌食傷。若身旺而財輕官弱，即仍取財官運可也。",
     "premises": [
      {
       "label": "正官可见",
       "predicate": "present_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "财透出",
       "predicate": "exposed_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "印不透",
       "predicate": "exposed_none",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正印",
        "偏印",
        "比肩",
        "劫财"
       ],
       "verdict": "favoured",
       "words": "運喜印綬身旺之地"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "avoided",
       "words": "切忌食傷"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "身旺而財輕官弱",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财",
          "正官"
         ],
         "verdict": "favoured",
         "words": "仍取財官運可也"
        }
       ]
      }
     ]
    },
    {
     "id": "officer-seal",
     "title": "正官佩印",
     "passage_id": "ziping:c032:p0004",
     "sha256": "866e02bd3da73b43f80328352d84a7999d1d127f415ff701e25364f1fe68fa4a",
     "quote": "正官佩印，運喜財鄉，傷食反吉。若官重身輕而佩印，則身旺爲宜，不必財運也。",
     "premises": [
      {
       "label": "正官可见",
       "predicate": "present_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "印透出",
       "predicate": "exposed_any",
       "roles": [
        "正印",
        "偏印"
       ]
      },
      {
       "label": "财不透",
       "predicate": "exposed_none",
       "roles": [
        "正财",
        "偏财"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "favoured",
       "words": "運喜財鄉"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "favoured",
       "words": "傷食反吉"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "官重身輕而佩印",
       "effects": [
        {
         "roles": [
          "比肩",
          "劫财"
         ],
         "verdict": "favoured",
         "words": "身旺爲宜"
        }
       ]
      }
     ]
    },
    {
     "id": "officer-hurt-seal",
     "title": "正官带伤食而用印制",
     "passage_id": "ziping:c032:p0005",
     "sha256": "eef97b8568e8013b5be0d5733d140d50877005f15e7759575b5ad048d9cb0d36",
     "quote": "正官帶傷食而用印製，運喜官旺印旺之鄉，財運切忌。若印綬疊出，財運亦無害矣。",
     "premises": [
      {
       "label": "正官可见",
       "predicate": "present_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "食伤可见",
       "predicate": "present_any",
       "roles": [
        "食神",
        "伤官"
       ]
      },
      {
       "label": "印透出",
       "predicate": "exposed_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正官",
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "運喜官旺印旺之鄉"
      },
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "avoided",
       "words": "財運切忌"
      }
     ],
     "branches": [
      {
       "kind": "computed",
       "condition": "印綬疊出",
       "predicate": "exposed_count_at_least",
       "roles": [
        "正印",
        "偏印"
       ],
       "count": 2,
       "effects": [
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "harmless",
         "words": "財運亦無害"
        }
       ]
      }
     ]
    },
    {
     "id": "officer-kill",
     "title": "正官带煞",
     "passage_id": "ziping:c032:p0006",
     "sha256": "95525be664592a71fa4925037263b4af6fde653dfe82ca0493251f78b62498e1",
     "quote": "正官而帶煞，傷食反爲不礙。其命中用劫合煞，則財運可行，傷食可行；身旺，印綬亦可行，只不可復露七煞；若命用傷官合煞，則傷食與財俱可行，而不宜逢印矣。",
     "premises": [
      {
       "label": "正官可见",
       "predicate": "present_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "七杀透出",
       "predicate": "exposed_any",
       "roles": [
        "七杀"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "harmless",
       "words": "傷食反爲不礙"
      }
     ],
     "branches": [
      {
       "kind": "computed",
       "condition": "用劫合煞",
       "predicate": "combines",
       "roles": [
        "劫财"
       ],
       "with": [
        "七杀"
       ],
       "effects": [
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "favoured",
         "words": "財運可行"
        },
        {
         "roles": [
          "食神",
          "伤官"
         ],
         "verdict": "favoured",
         "words": "傷食可行"
        },
        {
         "roles": [
          "七杀"
         ],
         "verdict": "avoided",
         "words": "不可復露七煞"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "用劫合煞而身旺",
       "predicate": "combines",
       "roles": [
        "劫财"
       ],
       "with": [
        "七杀"
       ],
       "effects": [
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "印綬亦可行"
        }
       ]
      },
      {
       "kind": "computed",
       "condition": "用傷官合煞",
       "predicate": "combines",
       "roles": [
        "伤官"
       ],
       "with": [
        "七杀"
       ],
       "effects": [
        {
         "roles": [
          "食神",
          "伤官",
          "正财",
          "偏财"
         ],
         "verdict": "favoured",
         "words": "傷食與財俱可行"
        },
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "avoided",
         "words": "不宜逢印"
        }
       ]
      }
     ]
    }
   ]
  },
  {
   "family_id": "wealth",
   "title": "财",
   "chapter": "ziping:c034",
   "scenarios": [
    {
     "id": "wealth-officer",
     "title": "财旺生官",
     "passage_id": "ziping:c034:p0002",
     "sha256": "b769ad6fd1d9f75d913e4457172bc497b09ef1dfa5bb2a9840138ba0d924290c",
     "quote": "其財旺生官者，運喜身旺印緩，不利七煞傷官；若生官而復透印，傷官之地，不甚有害。至於生官而帶食破局，則運喜印綬，而逢煞反吉矣。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "正官透出",
       "predicate": "exposed_any",
       "roles": [
        "正官"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "比肩",
        "劫财",
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "運喜身旺印緩"
      },
      {
       "roles": [
        "七杀",
        "伤官"
       ],
       "verdict": "avoided",
       "words": "不利七煞傷官"
      }
     ],
     "branches": [
      {
       "kind": "computed",
       "condition": "生官而復透印",
       "predicate": "exposed_any",
       "roles": [
        "正印",
        "偏印"
       ],
       "effects": [
        {
         "roles": [
          "伤官"
         ],
         "verdict": "harmless",
         "words": "傷官之地，不甚有害"
        }
       ]
      },
      {
       "kind": "computed",
       "condition": "生官而帶食破局",
       "predicate": "exposed_any",
       "roles": [
        "食神"
       ],
       "effects": [
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "運喜印綬"
        },
        {
         "roles": [
          "七杀"
         ],
         "verdict": "favoured",
         "words": "逢煞反吉"
        }
       ]
      }
     ]
    },
    {
     "id": "wealth-food",
     "title": "财用食生",
     "passage_id": "ziping:c034:p0003",
     "sha256": "c1a384aef29c12376b4bebeb1299eb809705833652a640d91b19ad6492e4b61d",
     "quote": "財用食生，財食重而身輕，則喜助身；財食輕而身重，則仍行財食，煞運不忌，官運反晦矣。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "食神可见",
       "predicate": "present_any",
       "roles": [
        "食神"
       ]
      },
      {
       "label": "正官不透",
       "predicate": "exposed_none",
       "roles": [
        "正官"
       ]
      }
     ],
     "effects": [],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "財食重而身輕",
       "effects": [
        {
         "roles": [
          "比肩",
          "劫财",
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "喜助身"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "財食輕而身重",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财",
          "食神"
         ],
         "verdict": "favoured",
         "words": "仍行財食"
        },
        {
         "roles": [
          "七杀"
         ],
         "verdict": "harmless",
         "words": "煞運不忌"
        },
        {
         "roles": [
          "正官"
         ],
         "verdict": "avoided",
         "words": "官運反晦"
        }
       ]
      }
     ]
    },
    {
     "id": "wealth-seal",
     "title": "财格佩印",
     "passage_id": "ziping:c034:p0004",
     "sha256": "2b2a268cbf66bdb1e72c129f276ca8a8ace00c2fa2b38ead9132dd641ec38fa4",
     "quote": "財格佩印，運喜官鄉；身弱逢之，最喜印旺。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正官"
       ],
       "verdict": "favoured",
       "words": "運喜官鄉"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "身弱",
       "effects": [
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "最喜印旺"
        }
       ]
      }
     ]
    },
    {
     "id": "wealth-food-seal",
     "title": "财用食印",
     "passage_id": "ziping:c034:p0005",
     "sha256": "655795ed5ea0854bd80a8738edcb095a3e0bbad40940fb3f953b7a5cf87a6c9f",
     "quote": "財用食印，財輕則喜財食，身輕則喜比印，官運亦礙，煞反不忌也。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "食神可见",
       "predicate": "present_any",
       "roles": [
        "食神"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正官"
       ],
       "verdict": "avoided",
       "words": "官運亦礙"
      },
      {
       "roles": [
        "七杀"
       ],
       "verdict": "harmless",
       "words": "煞反不忌"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "財輕",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财",
          "食神"
         ],
         "verdict": "favoured",
         "words": "喜財食"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "身輕",
       "effects": [
        {
         "roles": [
          "比肩",
          "劫财",
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "喜比印"
        }
       ]
      }
     ]
    },
    {
     "id": "wealth-hurt",
     "title": "财带伤官",
     "passage_id": "ziping:c034:p0006",
     "sha256": "3ba319c8e5096ae7055d499401f43de85fcc136fa159280009c540032e8b8552",
     "quote": "財帶傷官，財運則亨，煞運不利，運行官印，未見其美矣。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "favoured",
       "words": "財運則亨"
      },
      {
       "roles": [
        "七杀"
       ],
       "verdict": "avoided",
       "words": "煞運不利"
      },
      {
       "roles": [
        "正官",
        "正印",
        "偏印"
       ],
       "verdict": "unpromising",
       "words": "未見其美"
      }
     ]
    },
    {
     "id": "wealth-kill",
     "title": "财带七煞",
     "passage_id": "ziping:c034:p0007",
     "sha256": "781f3318f98a0decc353d11d51caea2769b110e0f6812b5e5f6beebc07eb23ce",
     "quote": "財帶七煞，不論合煞制煞，運喜食傷身旺之方。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "七杀可见",
       "predicate": "present_any",
       "roles": [
        "七杀"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "食神",
        "伤官",
        "比肩",
        "劫财"
       ],
       "verdict": "favoured",
       "words": "運喜食傷身旺之方"
      }
     ]
    },
    {
     "id": "wealth-kill-seal",
     "title": "财用煞印",
     "passage_id": "ziping:c034:p0008",
     "sha256": "5aacc4f01b39a24b75c44b6b9f2124bec3f148f6c22ec740d2cb25c4e3069d25",
     "quote": "財用煞印，印旺最宜，逢財必忌。傷食之方，亦順意矣。",
     "premises": [
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "七杀可见",
       "predicate": "present_any",
       "roles": [
        "七杀"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "印旺最宜"
      },
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "avoided",
       "words": "逢財必忌"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "favoured",
       "words": "亦順意"
      }
     ]
    }
   ]
  },
  {
   "family_id": "hurt",
   "title": "伤官",
   "chapter": "ziping:c042",
   "scenarios": [
    {
     "id": "hurt-wealth",
     "title": "伤官用财",
     "passage_id": "ziping:c042:p0002",
     "sha256": "cc5619ac438cc0c994f1e20ee70d24909f54c3cd801e44ebfa3ce7800ad51f5b",
     "quote": "傷官用財，財旺身輕，則利印比；身强財淺，則喜財運，傷官亦宜。",
     "premises": [
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      },
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      }
     ],
     "effects": [],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "財旺身輕",
       "effects": [
        {
         "roles": [
          "正印",
          "偏印",
          "比肩",
          "劫财"
         ],
         "verdict": "favoured",
         "words": "利印比"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "身强財淺",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "favoured",
         "words": "喜財運"
        },
        {
         "roles": [
          "伤官"
         ],
         "verdict": "favoured",
         "words": "傷官亦宜"
        }
       ]
      }
     ]
    },
    {
     "id": "hurt-seal",
     "title": "伤官佩印",
     "passage_id": "ziping:c042:p0003",
     "sha256": "597bf7271bcb9d941efc7bb147dbeeae61a93fad42ff8467061697d14db74dbe",
     "quote": "傷官佩印，運行官煞爲宜，印運亦吉，傷食不礙，財地則凶。",
     "premises": [
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正官",
        "七杀"
       ],
       "verdict": "favoured",
       "words": "運行官煞爲宜"
      },
      {
       "roles": [
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "印運亦吉"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "harmless",
       "words": "傷食不礙"
      },
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "avoided",
       "words": "財地則凶"
      }
     ]
    },
    {
     "id": "hurt-wealth-seal",
     "title": "伤官兼用财印",
     "passage_id": "ziping:c042:p0004",
     "sha256": "5fe3c9964a0c57a6d25213f651e244d1aae668d9630babb0ff9224704934887f",
     "quote": "傷官兼用財印，其財多而帶印者，運喜助印；印多而帶財者，運喜助財。",
     "premises": [
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      },
      {
       "label": "财可见",
       "predicate": "present_any",
       "roles": [
        "正财",
        "偏财"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "財多而帶印",
       "effects": [
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "運喜助印"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "印多而帶財",
       "effects": [
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "favoured",
         "words": "運喜助財"
        }
       ]
      }
     ]
    },
    {
     "id": "hurt-kill-seal",
     "title": "伤官用煞印",
     "passage_id": "ziping:c042:p0005",
     "sha256": "eb7f84368aa07c156e9713904eedc10b698c76c2500e3a414101db61eb145b8c",
     "quote": "傷官而用煞印，印運最利，傷食亦亨，雜官非吉，逢財即危。",
     "premises": [
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      },
      {
       "label": "七杀可见",
       "predicate": "present_any",
       "roles": [
        "七杀"
       ]
      },
      {
       "label": "印可见",
       "predicate": "present_any",
       "roles": [
        "正印",
        "偏印"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "印運最利"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "favoured",
       "words": "傷食亦亨"
      },
      {
       "roles": [
        "正官"
       ],
       "verdict": "avoided",
       "words": "雜官非吉"
      },
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "avoided",
       "words": "逢財即危"
      }
     ]
    },
    {
     "id": "hurt-kill",
     "title": "伤官带煞",
     "passage_id": "ziping:c042:p0006",
     "sha256": "9b85865e31e665b063994dae25645be9dd317aa3bccdc01dd1fbda909e3a7569",
     "quote": "傷官帶煞，喜印忌財。然傷重煞輕，運喜印而財亦吉。惟七殺根重，則運喜傷食印綬，身旺亦吉，而逢財爲凶矣。",
     "premises": [
      {
       "label": "伤官可见",
       "predicate": "present_any",
       "roles": [
        "伤官"
       ]
      },
      {
       "label": "七杀可见",
       "predicate": "present_any",
       "roles": [
        "七杀"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "喜印"
      },
      {
       "roles": [
        "正财",
        "偏财"
       ],
       "verdict": "avoided",
       "words": "忌財"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "傷重煞輕",
       "effects": [
        {
         "roles": [
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "運喜印"
        },
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "favoured",
         "words": "財亦吉"
        }
       ]
      },
      {
       "kind": "interpretive",
       "condition": "七殺根重",
       "effects": [
        {
         "roles": [
          "食神",
          "伤官",
          "正印",
          "偏印"
         ],
         "verdict": "favoured",
         "words": "運喜傷食印綬"
        },
        {
         "roles": [
          "比肩",
          "劫财"
         ],
         "verdict": "favoured",
         "words": "身旺亦吉"
        },
        {
         "roles": [
          "正财",
          "偏财"
         ],
         "verdict": "avoided",
         "words": "逢財爲凶"
        }
       ]
      }
     ]
    },
    {
     "id": "hurt-officer",
     "title": "伤官用官",
     "passage_id": "ziping:c042:p0007",
     "sha256": "9d518c6be13ef470cb72632f336be550f84533165e9a364ef41e883c1da43050",
     "quote": "傷官用官，運喜財印，不利傷食。若局中官露而財印兩旺，則比劫傷官，未始非吉矣。",
     "premises": [
      {
       "label": "正官透出",
       "predicate": "exposed_any",
       "roles": [
        "正官"
       ]
      },
      {
       "label": "伤官不透",
       "predicate": "exposed_none",
       "roles": [
        "伤官"
       ]
      }
     ],
     "effects": [
      {
       "roles": [
        "正财",
        "偏财",
        "正印",
        "偏印"
       ],
       "verdict": "favoured",
       "words": "運喜財印"
      },
      {
       "roles": [
        "食神",
        "伤官"
       ],
       "verdict": "avoided",
       "words": "不利傷食"
      }
     ],
     "branches": [
      {
       "kind": "interpretive",
       "condition": "局中官露而財印兩旺",
       "effects": [
        {
         "roles": [
          "比肩",
          "劫财",
          "伤官"
         ],
         "verdict": "harmless",
         "words": "未始非吉"
        }
       ]
      }
     ]
    }
   ]
  }
 ],
 "notes": [
  {
   "id": "N0",
   "passage_id": "ziping:c032:p0002",
   "sha256": "53c25c334fd3462afaf04e9de350091d5006cdfd591204374fee330d8dd4294c",
   "quote": "若官露而不可逢合、不可雜煞、不可重官與地支刑沖，不問所就何局，皆不利也。"
  },
  {
   "id": "N1",
   "passage_id": "ziping:c025:p0004",
   "sha256": "2d33fafa01d9d585cfd309713f9f134b639349fa14e01868ea274a8737a2a3ed",
   "quote": "如官逢印運，而本命有合"
  },
  {
   "id": "N2",
   "passage_id": "ziping:c025:p0005",
   "sha256": "01814aa7ff0e0a614b8bb184a8e35bc54a3139b223f6982c9dc65690fbe7d89b",
   "quote": "如官逢傷運，而命透印；財行煞運，而命透食之類是也。"
  },
  {
   "id": "N3",
   "passage_id": "ziping:c025:p0010",
   "sha256": "19d31e95c9f3f699587549f7501ae35554f346d7c976f54097df679f2dbc9b95",
   "quote": "沖年月則急，沖時日則緩也。"
  },
  {
   "id": "N4",
   "passage_id": "ziping:c025:p0011",
   "sha256": "38dee93e00ac444d7d1d79801cbc14f7c08d9d841d27086c8fca99e36a67d5f1",
   "quote": "運本美而逢沖則輕，運既忌而又沖則重也。"
  }
 ]
}
```
