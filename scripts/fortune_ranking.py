"""Boolean-tier candidate ranking; every tier cites a passage, no invented weights.

Ranking exists only for scenarios whose ``personal_ranking`` is ``rule_based``
in :mod:`fortune_rules`. The tiers below come from ``references/26-precedence.md``
and are frozen alongside ``PRECEDENCE_VERSION``; changing either means changing
both, so an older ranking never silently upgrades.

Two rules the tiers must not break, both inherited from the reference set:

* ``references/25-classical-research.md`` — 候选排序依规则的完整取舍，不加自造权重.
  Tiers are therefore ordered booleans, never scores.
* ``references/24-personalized-forecast.md`` — 不能把候选的自然顺序、是否相生或
  黄历宜忌改成首选. Almanac verdicts and stem/branch affinity stay out of the
  tier computation; they may only be reported as context.
"""
from __future__ import annotations

from fortune_rules import PRECEDENCE_VERSION

# 天地转杀（yuanhai:c052:p0004）：秋见辛酉为天转、癸酉为地转；其日最忌「出行商贾」。
# 四季各自两日，键为节气季节，值为该季的 (天转, 地转)。
TIANDI_ZHUAN = {
    'spring': (('乙', '卯'), ('辛', '卯')),
    'summer': (('丙', '午'), ('戊', '午')),
    'autumn': (('辛', '酉'), ('癸', '酉')),
    'winter': (('壬', '子'), ('丙', '子')),
}
TIANDI_SOURCE = 'yuanhai:c052:p0004'

# 截路空亡：以日干取时，非以年。两书前四组一致，戊癸组分歧。
# 渊海子平 c048:p0003 作「戊癸子丑」；三命通会 c003:p0035 作「戊癸見戌亥」。
# 26-precedence.md 第三层「自洽者胜」判归渊海：两书共用判据是「二时上俱遇壬癸为水」，
# 戊癸日五鼠遁起壬子 —— 子时壬子、丑时癸丑，只有子丑符合该判据。
JIELU_HOURS = {
    '甲': ('申', '酉'), '己': ('申', '酉'),
    '乙': ('午', '未'), '庚': ('午', '未'),
    '丙': ('辰', '巳'), '辛': ('辰', '巳'),
    '丁': ('寅', '卯'), '壬': ('寅', '卯'),
    '戊': ('子', '丑'), '癸': ('子', '丑'),
}
JIELU_SOURCE = 'yuanhai:c048:p0004'
JIELU_DISSENT = {
    'passage_id': 'sanming:c003:p0035',
    'text': '戊癸見戌亥',
    'note': '《三命通会》戊癸作戌亥；本表按 26-precedence.md 第三层「自洽者胜」取《渊海子平》子丑。',
}

# 事项 -> 条款所列的古法名目。天地转杀原文写「上官受职、出行商贾、造作、嫁娶」；
# 截路空亡原文写「出入求財交易上官嫁娶百事皆忌」。现代事项映射到古法名目须显式，
# 不在此表内的事项不套用这两条。
SCENARIO_TERMS = {
    'travel': ('出行商贾', '出入'),
}

# 五行 -> 颜色。来自 references/00-foundations.md 的传统属性映射表；该表的表头
# 自带一句「不证明方位、颜色能改变结果」，所以本表只用于命名五行对应的颜色，
# 不构成任何选购或行动建议。
WUXING_COLOR = {
    '木': '青/绿', '火': '红', '土': '黄', '金': '白', '水': '黑',
}
STEM_WUXING = {
    '甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
    '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水',
}
COLOR_TABLE_REF = 'references/00-foundations.md'
COLOR_TABLE_CAVEAT = '以下只是文化对应，不用于诊断身体或人格，也不证明方位、颜色能改变结果。'


def _clash_branch(branch: str) -> str:
    """Return the branch that clashes with ``branch`` (六冲)."""
    order = '子丑寅卯辰巳午未申酉戌亥'
    return order[(order.index(branch) + 6) % 12]


def tiandi_zhuan(day_stem: str, day_branch: str, season: str) -> dict | None:
    """Day-level travel prohibition. Returns the hit, or None when clear."""
    pair = TIANDI_ZHUAN.get(season)
    if pair is None:
        return None
    for label, (stem, branch) in zip(('天转', '地转'), pair, strict=True):
        if (day_stem, day_branch) == (stem, branch):
            return {'rule': 'tiandi_zhuan', 'kind': label,
                    'passage_id': TIANDI_SOURCE,
                    'quote': '其日最忌，上官受职、出行商贾、造作、嫁娶，必主凶',
                    'reason': f'{season} 的{label}日为 {stem}{branch}，本日命中'}
    return None


def jielu_kongwang(day_stem: str) -> dict:
    """Hour-level prohibition derived from the day stem."""
    hours = JIELU_HOURS[day_stem]
    entry: dict = {'rule': 'jielu_kongwang', 'forbidden_hours': list(hours),
                   'passage_id': JIELU_SOURCE,
                   'quote': '此空亡非但命中见之不美，以至百事，求财主官皆不利也',
                   'reason': f'{day_stem}日忌 {hours[0]}{hours[1]} 两时辰'}
    if day_stem in ('戊', '癸'):
        entry['dissent'] = JIELU_DISSENT
    return entry


def zodiac_clash(day_branch: str, natal_year_branch: str) -> dict | None:
    """Folk-layer exclusion: the day branch clashes with the birth-year branch.

    Deliberately carries no ``passage_id``. The five books give 六冲 起法 but no
    clause saying a clash day is unfit for travel, so per 26-precedence.md this
    never enters tier computation — it is reported as folk context only.
    """
    if _clash_branch(day_branch) != natal_year_branch:
        return None
    return {'rule': 'zodiac_clash', 'layer': 'folk', 'passage_id': None,
            'reason': f'{day_branch}冲本命年支{natal_year_branch}',
            'note': '起法可算，但五书无「冲生肖不宜出行」的条款；不进 tier，只作民俗层背景。'}


def climate_colors(day_stem: str, month_branch: str) -> dict:
    """Name the colours matching the climate clause for this day stem and month.

    The chain has three links and the third one is missing, so the result says
    so instead of hiding it:

    1. day stem + month branch -> the month-specific clause  (sourced)
    2. clause names stems to take -> their five-phase colours (sourced table,
       but the table's own header denies that colour changes outcomes)
    3. colour -> "buy this one"                              (no source at all)

    ``tiaohou_provenance`` already carries the clause's own warning for this very
    case: 不把表名直接变成喜火的现实建议. This function stops at link 2 and
    reports link 3 as absent, so a caller cannot mistake it for a recommendation.
    """
    from tiaohou_provenance import get_tiaohou_audit

    audit = get_tiaohou_audit(f'{day_stem}|{month_branch}')
    if not audit or audit.get('status') == 'not_found':
        return {'status': 'no_month_clause',
                'reason': f'{day_stem}日主生{month_branch}月无当月专段，不用季节总论顶替。'}

    def _named(stems: list[str]) -> list[dict]:
        seen: dict[str, dict] = {}
        for stem in stems:
            phase = STEM_WUXING[stem]
            row = seen.setdefault(phase, {'wuxing': phase, 'color': WUXING_COLOR[phase],
                                          'from_stems': []})
            row['from_stems'].append(stem)
        return list(seen.values())

    return {
        'status': audit['status'],
        'clause_key': audit['key'],
        'general': _named(audit.get('source_general_candidates') or []),
        'conditional': _named(audit.get('source_conditional_candidates') or []),
        'sources': [r['passage_id'] for r in audit.get('source_refs') or []],
        'clause_note': audit.get('review_note'),
        'facsimile_status': audit.get('facsimile_status'),
        'color_table': {'reference': COLOR_TABLE_REF, 'caveat': COLOR_TABLE_CAVEAT},
        'broken_link': ('条款说取某五行，对照表给出该五行的颜色 —— 这两步有出处。'
                        '从颜色到「买这个对你有利」没有任何出处，本结果不构成选购建议。'),
        'individual_application': audit.get('individual_application'),
    }


def season_of(month_branch: str) -> str | None:
    """Season used by 天地转杀, taken from the solar-term month branch."""
    return {'寅': 'spring', '卯': 'spring', '辰': 'spring',
            '巳': 'summer', '午': 'summer', '未': 'summer',
            '申': 'autumn', '酉': 'autumn', '戌': 'autumn',
            '亥': 'winter', '子': 'winter', '丑': 'winter'}.get(month_branch)


def rank_candidates(comparison: list[dict], participant: dict, *, scenario: str) -> dict:
    """Rank ``candidate_comparison`` rows against the clause tiers.

    Reads day and hour pillars straight from the participant's own segments via
    ``target_segment_ref``; nothing is recomputed here, so a candidate can never
    be judged on a pillar the calendar did not produce. Candidates whose window
    lacks day granularity are reported as unrankable rather than assumed clear.
    """
    segments = participant['target']['segments']
    natal_year_branch = participant['natal']['four_pillars']['year']['branch']
    ranked, excluded, unrankable = [], [], []
    for candidate in comparison:
        if not candidate.get('available'):
            continue
        for window in candidate['windows']:
            refs = [s['target_segment_ref'] for p in window['participants']
                    if p['participant_id'] == participant['id'] for s in p['segments']]
            pillars = [segments[i]['facts']['pillars'] for i in refs]
            dated = [p for p in pillars if 'day' in p]
            if not dated:
                unrankable.append({'candidate_id': candidate['candidate_id'],
                                   'start': window['start'],
                                   'reason': '该窗口未细算到日柱，无法套用忌日条款'})
                continue
            day = dated[0]['day']
            season = season_of(dated[0]['month'][1])
            entry = {'candidate_id': candidate['candidate_id'], 'start': window['start'],
                     'end': window['end'], 'day_ganzhi': day}
            blocked = tiandi_zhuan(day[0], day[1], season) if season else None
            forbidden = jielu_kongwang(day[0])
            # The forbidden hours are branch names; flag only the ones this
            # window actually covers, so a clear window is not penalised for a
            # prohibited hour it never touches.
            covered = {p['hour'][1] for p in pillars if 'hour' in p}
            entry['forbidden_hours'] = forbidden
            entry['forbidden_hours_in_window'] = sorted(covered & set(forbidden['forbidden_hours']))
            folk = zodiac_clash(day[1], natal_year_branch)
            entry['folk_context'] = [f for f in (folk,) if f]
            if blocked:
                entry['excluded_by'] = [blocked]
                excluded.append(entry)
            else:
                entry['tier'] = 1
                entry['sources'] = [TIANDI_SOURCE, JIELU_SOURCE]
                ranked.append(entry)
    clear = [r for r in ranked if not r['forbidden_hours_in_window']]
    return {
        'scenario': scenario,
        'mapped_terms': list(SCENARIO_TERMS[scenario]),
        'precedence_version': PRECEDENCE_VERSION,
        'ranking_reference': 'references/26-precedence.md',
        'tiers': ranked,
        'excluded': excluded,
        'unrankable': unrankable,
        'tier_count': 1 if ranked else 0,
        'ties': len(ranked) > 1,
        'hour_clear': [r['candidate_id'] for r in clear],
        'scope': ('忌型条款只排除，不在未被排除的候选之间分高下；同 tier 内并列。'
                  'forbidden_hours_in_window 指该窗口实际覆盖到的忌时，仅作提示，'
                  '不改变 tier。黄历宜忌与干支相生不参与。'),
        'not_covered': ['跨时区班次', '多段行程的联合择时', '日内时辰的优劣排序（仅给忌时）'],
    }


def rank_travel_days(days: list[dict], *, natal_year_branch: str | None = None,
                     scenario: str = 'travel') -> dict:
    """Rank candidate days for a single-timezone journey.

    ``days`` items need ``date``, ``day_stem``, ``day_branch``, ``season``.
    Returns tiers plus the excluded set; ties keep the input order and are
    reported as ties rather than broken by an invented rule.
    """
    if scenario not in SCENARIO_TERMS:
        raise ValueError(f'{scenario} 未映射到古法名目；不得套用出行条款')
    ranked, excluded = [], []
    for day in days:
        hits = []
        blocked = tiandi_zhuan(day['day_stem'], day['day_branch'], day['season'])
        if blocked:
            hits.append(blocked)
        folk = zodiac_clash(day['day_branch'], natal_year_branch) if natal_year_branch else None
        entry = {'date': day['date'], 'ganzhi': day['day_stem'] + day['day_branch'],
                 'forbidden_hours': jielu_kongwang(day['day_stem']),
                 'folk_context': [f for f in (folk,) if f]}
        if hits:
            entry['excluded_by'] = hits
            excluded.append(entry)
        else:
            # Tier 1: no dated prohibition hits. There is no clause ordering
            # clear days against each other, so every clear day shares tier 1.
            entry['tier'] = 1
            entry['sources'] = [TIANDI_SOURCE, JIELU_SOURCE]
            ranked.append(entry)
    return {
        'scenario': scenario,
        'mapped_terms': list(SCENARIO_TERMS[scenario]),
        'precedence_version': PRECEDENCE_VERSION,
        'ranking_reference': 'references/26-precedence.md',
        'tiers': ranked,
        'excluded': excluded,
        'tier_count': 1 if ranked else 0,
        'ties': len(ranked) > 1,
        'scope': ('忌型条款只排除，不在未被排除的日子之间分高下；'
                  '同 tier 内并列，需另给依据才能再分。黄历宜忌与干支相生不参与。'),
        'not_covered': ['跨时区班次', '多段行程的联合择时', '日内时辰的优劣排序（仅给忌时）'],
    }
