"""Shapes the selection pipeline hands between stages and to the host.

Each TypedDict is the contract for one boundary: the day rules that bar an
event, the ranking rows built from them, the practical choice, and the
recommendation a renderer reads. Producers declare these as their return
types so mypy checks every key they write, and tests/test_contracts.py checks
real outputs against the same definitions at runtime, extra keys included.

No ``from __future__ import annotations`` here: TypedDict computes its
required keys when the class is created, and string annotations hide
``NotRequired`` from it on Python 3.11.
"""
from typing import Any, Literal, NotRequired, TypedDict

RecommendationStatus = Literal[
    'evidence_needed', 'participant_priority_required', 'availability_required',
    'no_feasible_slot', 'screened_only', 'tied_no_clause_separates', 'excluded_by_clause',
    'practical_choice', 'clause_conflict', 'screening_incomplete', 'preferences_required',
    'practical_tie', 'personal_calendar']
Grade = Literal['大吉', '吉', '平', '小凶', '凶', '大凶']
PracticalStatus = Literal[
    'no_practical_choice', 'participant_priority_required', 'clause_conflict',
    'screening_incomplete', 'preferences_required', 'practical_tie', 'practical_choice']


class Source(TypedDict):
    role: str
    passage_id: str
    quote: str


class PersonalFactor(TypedDict):
    """One sentence of 协纪卷三十三 (相主) applied to one pillar."""
    rule: str
    label: str
    polarity: Literal['good', 'bad', 'note']
    grade: Grade
    plain: str
    quote: str
    passage_id: str
    table: NotRequired[str]             # the passage that defines a positional table
    other: NotRequired[str]             # another book's contrary rule, named not followed


class PillarContext(TypedDict):
    ganzhi: str
    grade: Grade
    factors: list[PersonalFactor]


class PersonalDay(TypedDict):
    birth_year: str
    day_ganzhi: str
    grade: Grade
    factors: list[PersonalFactor]
    context: dict[str, PillarContext]   # 'year', 'month': weighed apart from the day
    repeats_without_day: list[PersonalFactor]


class PersonalPerson(TypedDict):
    participant_id: str
    birth_year: str
    days: list[PersonalDay]


class PersonalAssessment(TypedDict):
    grade: Grade                        # the worst day for the worst-placed person
    people: list[PersonalPerson]


class DayRuleHit(TypedDict):
    """One sourced day rule that bars the event: 天地转杀, a 协纪 prohibition,
    or a 相主 day that is 凶 for the person it is chosen for."""
    rule: str
    kind: str
    label: str
    day_ganzhi: str
    passage_id: str
    quote: str
    reason: str
    plain: str                          # the reader's sentence for it
    # 协纪 only: the 用事 name, how the day was derived, and every passage used.
    term: NotRequired[str]
    derivation: NotRequired[str]
    sources: NotRequired[list[Source]]
    # 相主 only: whose birth year the day is against.
    participant_id: NotRequired[str]
    birth_year: NotRequired[str]


class HourHit(TypedDict):
    """A 截路空亡 hour the window covers, located on the clock."""
    hour_branch: str
    day_ganzhi: str
    rule_stem: str                      # the day whose 五鼠遁 gave the hour stem
    derivation: str
    passage_id: str
    segment_start: str
    segment_end: str


class ContestedHourHit(TypedDict):
    """An hour only one reading of an unresolved day names."""
    hour_branch: str
    day_ganzhi: str
    rule_stem: str
    readings: list[str]
    segment_start: str
    segment_end: str


class RankingRow(TypedDict):
    candidate_id: str
    start: str
    end: str
    day_ganzhi: str
    days: list[dict[str, Any]]
    forbidden_hours_in_window: list[HourHit]
    contested_hours_in_window: list[ContestedHourHit]
    unresolved_hour_rules: list[str]
    folk_context: list[dict[str, Any]]
    # A surviving row carries its tier; an excluded row carries what excluded it.
    tier: NotRequired[int]
    sources: NotRequired[list[str]]
    context_sources: NotRequired[list[str]]
    excluded_by: NotRequired[list[DayRuleHit]]
    personal: NotRequired[PersonalAssessment]


class Unrankable(TypedDict):
    candidate_id: str
    start: str
    end: str
    reason: str


class Ranking(TypedDict):
    scenario: str
    mapped_terms: list[str]
    tiers: list[RankingRow]
    excluded: list[RankingRow]
    unrankable: list[Unrankable]
    tier_count: int
    ties: bool
    precedence_version: str
    ranking_reference: str
    rule_scope: str
    scope: str
    not_covered: list[str]
    uses_complete_natal_chart: bool
    personal_participant_ids: list[str]  # whose birth years graded the days
    personal_basis: dict[str, str]
    calendar_participant_id: NotRequired[str]


class FlexibleStart(TypedDict):
    earliest: str
    latest: str
    latest_inclusive: bool


class Placement(TypedDict):
    candidate_id: str
    start: str
    end: str
    timezone: str
    start_is_practical_boundary: bool
    flexible_start: NotRequired[FlexibleStart]
    grade: NotRequired[Grade]           # the 相主 grade of the chosen window


class PassedOver(TypedDict):
    candidate_id: str
    start: str
    end: str
    grade: Grade


class PracticalChoice(TypedDict):
    status: PracticalStatus
    first_choice: Placement | None
    backup: Placement | None
    basis: str
    personal_auspicious_ranking: bool
    reason: NotRequired[str]
    scope: NotRequired[str]
    checked_options: NotRequired[list[Ranking]]
    alternatives: NotRequired[list[Placement]]
    # Better-graded windows that no clean start could use (named, not hidden).
    passed_over: NotRequired[list[PassedOver]]


class Recommendation(TypedDict):
    status: RecommendationStatus
    first_choice: str | None
    backup: str | None
    basis: NotRequired[str]
    remaining: NotRequired[list[str]]
    tied: NotRequired[list[str]]
    excluded: NotRequired[list[str]]
    precedence_version: NotRequired[str]


class Blocker(TypedDict):
    code: str
    message: str
    participant_id: NotRequired[str]
