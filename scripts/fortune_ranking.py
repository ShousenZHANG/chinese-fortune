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


def _clash_branch(branch: str) -> str:
    """Return the branch that clashes with ``branch`` (六冲)."""
    order = '子丑寅卯辰巳午未申酉戌亥'
    return order[(order.index(branch) + 6) % 12]


def tiandi_zhuan(day_stem: str, day_branch: str, season: str) -> dict | None:
    """Day-level travel prohibition. Returns the hit, or None when clear."""
    pair = TIANDI_ZHUAN.get(season)
    if pair is None:
        return None
    for label, (stem, branch) in zip(('天转', '地转'), pair):
        if (day_stem, day_branch) == (stem, branch):
            return {'rule': 'tiandi_zhuan', 'kind': label,
                    'passage_id': TIANDI_SOURCE,
                    'quote': '其日最忌，上官受职、出行商贾、造作、嫁娶，必主凶',
                    'reason': f'{season} 的{label}日为 {stem}{branch}，本日命中'}
    return None


def jielu_kongwang(day_stem: str) -> dict:
    """Hour-level prohibition derived from the day stem."""
    hours = JIELU_HOURS[day_stem]
    entry = {'rule': 'jielu_kongwang', 'forbidden_hours': list(hours),
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
