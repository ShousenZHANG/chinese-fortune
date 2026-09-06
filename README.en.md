# Chinese Fortune

Calculate a chart, check classical conditions, and explain the result in plain language.

BaZi follows the month-structure approach in Zi Ping Zhen Quan. Four other classical works provide separately attributed comparisons; differences remain visible.

## Capabilities

- BaZi calculations with birth timezone, DST, true solar time, day boundaries and unknown-hour handling.
- Offline retrieval from five frozen transcriptions: 416 chapter/volume units and 8,385 paragraphs, with provenance and context.
- Eight BaZi rule families and 25 review paths. Observable conditions are computed; interpretive conditions require explicit reasoning from the chart and full passages.
- Current time in the user's present location, captured once per request.
- Zi Wei, Liu Yao and other methods when requested, within their documented scope.

A complete transcription, implemented rules, image collation and predictive validity are separate claims. Tests do not establish predictive accuracy.

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
