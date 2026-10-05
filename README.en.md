# Chinese Fortune

Calculate a chart, check classical conditions, and answer in plain language first. Each short classical quotation must be followed immediately by its plain meaning and its relevance to the person's actual conditions.

BaZi follows the month-structure approach in Zi Ping Zhen Quan. Four other classical works provide separately attributed comparisons; differences remain visible.

## General requests and clear answers

Job searches, interviews, travel, relationship conversations and new everyday scenarios share a request workflow. A scenario being accepted does not establish a complete classical prediction method for it. Confirmed birth ranges are compared at minute resolution instead of guessing one instant.

Answers use natural Chinese, normally 300–600 characters: the useful conclusion first, then a necessary short quotation and an immediate explanation of its meaning and personal applicability. Supported parts are answered first; missing sources trigger a recorded five-minute research budget using the host's available search tools. Candidate material stays outside the package and is never automatically registered as an executable rule.

Explicit practical preferences can select a first and backup appointment with dates, start/end times and time zones. These are practical choices, distinct from personal auspiciousness ranking, which remains incomplete. Travel, weddings, moving and business openings have a generic day-exclusion filter (天地转杀 from Yuanhai Ziping, and the Xieji Bianfang Shu prohibitions it says no auspicious spirit can lift); it does not use the full natal chart to establish personal suitability. Known textual variants now follow normal passage retrieval.

## Capabilities

- BaZi calculations with birth timezone, DST, true solar time, day boundaries and unknown-hour handling.
- Offline retrieval from 13 frozen transcriptions: 535 chapter/volume units and 18,982 paragraphs, with provenance and context.
- Eight BaZi rule families and 25 review paths. Observable conditions are computed; interpretive conditions require explicit reasoning from the chart and full passages.
- Current time in the user's present location, captured once per request.
- Zi Wei, Liu Yao and other methods when requested, within their documented scope.

A complete transcription, implemented rules, image collation and predictive validity are separate claims. Tests do not establish predictive accuracy.

## Personal periods and appointment windows

The new `python scripts/fortune_reading.py --stdin` entry point accepts confirmed people, the current location, a target period, event location, available windows, duration and busy intervals. It resolves relative dates, calculates natal and target facts separately, checks active ten-year cycles, and filters real scheduling conflicts. Birth, current and event time zones remain distinct. Identical pillar facts are referenced through a per-person catalog to avoid repeating the full chart.

Candidate comparisons cover the entire event, including changes during it, and show the earliest and latest feasible start. Selection requests default to hour facts only inside feasible windows, merging overlaps; the rest of the period retains month and active-cycle background. Independent missing conditions remain visible together. These scheduling limits are not auspicious-time recommendations.

Interview and exam requests also calculate Yuanling's verified earth plate and chief star/door anchors throughout each candidate window, with a separate birth-year-stem lookup for each person. Unknown cells remain unknown; year-stem lookup is not full-BaZi ranking.

Ordered multi-event requests now check each event’s windows, duration, time zone and explicit travel/preparation buffer together. Each natal chart is calculated and transmitted once. Returned plans are feasibility witnesses, not auspiciousness rankings.

Two specific examples from Zi Ping Zhen Quan now check actual natal antecedents against the active ten-year cycle. Their observations distinguish same-element support, branch opposition and stem combination, with quotations and plain explanations. These are structural checks, not overall fortune or event predictions; the full chapter's exceptions remain available.

**Which days are good or bad for you is answered by 相主 from 《协纪辨方书》 volume 33**, which judges the chosen time's year, month, day and hour pillars against the stem and branch of the year you were born (「從來皆論生年不論生日」). A year or month that clashes your birth year is said first and no day inside it is called good, since changing the day does not avoid it. Each day is graded 大吉 to 大凶 with its reasons and passages; a period gets its best and worst days, and candidate slots are ordered by grade first, then by your stated preference. Event day rules (天地转杀 and 协纪's unliftable prohibitions) still exclude first. Clothing colours and things to wear follow the general 调候 choice of your chart's cell in 《穷通宝鉴》, each link cited; the cell's exceptions (for example 「丙丁过多与水局另论」) are not yet checked against your chart, the answer says so, and no colour is named to avoid. Weighing the whole chart's 喜忌 against a period is still not implemented. `--markdown` is a factual draft, not a completed prediction.

相主 is 协纪's method for choosing a time for an undertaking. Travel, weddings, moving and opening a business are on its list of commoners' undertakings (民用三十七事, `xieji:c011:p0005`); interviews, exams, dates, salary talks and quotes are not, so for those the method is borrowed and the answer says so. The generated coverage table is in the Chinese README.

An answer may end with a separate **real-world reference** section drawn from a frozen snapshot of 《高性价比人生指南》 (eternity4719/HowToLiveBetter, commit `842e11c9`, CC BY 4.0): book titles quoted verbatim with section, entry, grade and cost-effectiveness tier, filtered by where the matter takes place (never by the computer's clock zone), and never used in any divination ranking.

Plain real-life questions (what to do first after a layoff, whether to stand surety for a friend, whether a two-hour commute is worth it) go to the book's own decision workflow: `life_guide.py --decide` finds the entries, ranks them by fit and then by the book's cost-effectiveness tier and evidence grade within one outcome type, splits "do" from the book's "don't" list, cites section and entry for each, and names what the book does not cover; an emergency, a suicidal thought or a legal process already under way gets the first action before anything else, with hotline numbers only for someone in mainland China. The ported search and workflow code is MIT; the text is CC BY 4.0. The library holds the whole book except three entries left out by product scope: 660 entries in 34 sections, 8 long articles, section intros, the glossary and resolved cross references. Divination questions keep priority. See [life decisions](references/29-life-decision.md).

See the [request schema, coverage and research workflow](references/24-personalized-forecast.md). Long periods default to month facts; day/hour detail is limited to 31 local days per request. Missing event longitude retains year/month facts and marks solar day/hour data incomplete. Approximate birth times use conservative whole-date comparisons rather than an assumed exact hour.

Optional, explicitly confirmed profiles support revisioned updates, inspection and deletion outside the repository and installed skill. The default is `~/.local/share/chinese-fortune`. Calculations do not automatically persist conversations or profiles.

## Start

Use Python 3.11 or later and a host that reads skill files and executes Python. CI checks Python 3.11 and 3.12.

Download the runtime ZIP from [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases), extract it, enter the chinese-fortune directory and run:

```sh
python -m pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
python scripts/classical_search.py --validate
python scripts/request_time.py --current-timezone Australia/Sydney
```

Import the folder into your host. Use the same Python environment for installation and execution.

Example: “Born 1990-05-10 at 14:30, male, Beijing; currently in Sydney. Explain the main BaZi structure in plain language, including applicable conditions and exceptions.”

Text lookup needs no birth data. Unknown birth time remains unknown; near day or solar-term boundaries, other pillars may also need alternatives.

## Direct use

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --markdown
python scripts/classical_search.py --list-books
python scripts/classical_search.py --book ziping --query 用神
python scripts/classical_search.py --passage-id ziping:c008:p0001
```

`huangli_query.py --question … --markdown` answers the asked event (travel, wedding, moving, opening) first from the sourced day rules and names where the almanac table disagrees; `liuyao_cast.py … --markdown` places the 用神 with its source and gives no verdict.

Markdown provides a chart-and-conditions draft. The host completes the relevant interpretive checks and answers the question. JSON returns chart_facts, rule_assessment and a deduplicated evidence_bundle with complete paragraphs and exceptions. Do not call the diagnostic engine again to fetch absent legacy ge_ju or yong_shen fields.

Keep birth timezone, present-location timezone and target time separate. Reuse request_time.py's utc as --request-time within a request.

## Sources and distribution

The runtime archive retains every selected chapter and index. Raw HTML/wiki provenance is in a separate sources ZIP; ordinary users need only the runtime ZIP. SHA256SUMS covers both.

Runtime validation has an explicit scope. Missing files do not silently switch validation modes. [Sources](docs/CLASSICAL-SOURCES.md) explain edition and licensing limits; [coverage](docs/CONTENT-COVERAGE.md) distinguishes verified clauses, partial support and gaps.

[Rules](docs/BAZI-RULES.md) · [Output contract](references/22-output-contract.md) · [Migration](docs/OUTPUT-VALIDATION.md)

## Development

In the source checkout:

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

Release builds use a full commit SHA, clean-install checks and the exact CI artifact. See [release process](docs/RELEASE-PROCESS.md). Recorded model-answer reviews remain separate from deterministic tests.

Code is [MIT](LICENSE); third-party texts retain their recorded licensing. For cultural study, with real-world medical, legal and investment decisions based on appropriate professional information.

## Scenario-specific classical research

Eight additional transcriptions cover almanac selection, Liu Yao, Zi Wei, Mei Hua, Qi Men and Liu Ren. `classical_guidance.py --scenario interview --retrieve --limit 1` retrieves relevant originals; `--family 伤官` returns the complete luck chapter and conditions for a confirmed natal structure. Chapter pagination preserves later exceptions. Sixteen scenario routes expose available sources and unresolved needs, including naming lexicography and full residential Feng Shui. Source acquisition does not certify a personal ranking algorithm. See [the research workflow](references/25-classical-research.md).

Retrieval also verifies and returns selected non-adjacent shared prohibitions for arrival, exams, travel, billing, business, moving and marriage. Remaining textual problems and unreviewed conditions are explicit. Add `include_research:true` to a future-period request to retrieve this material in the same call without another natal calculation.

## Prospective validation

Fix the method and scope before interpretation, check personal applicability and exceptions, and disclose unresolved conflicts. With user consent, `prediction_log.py` stores prospective records outside the repository, freezes forecasts, and preserves confirmed outcome corrections. Coverage, unverified outcomes, deletions and method/version/event cohorts accompany observed hit rates. This mechanism does not establish predictive validity. See [the workflow](references/28-prospective-validation.md).
