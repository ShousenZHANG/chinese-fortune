# Chinese Fortune

Calculate a chart, consult classical sources, and explain the result in plain language.

BaZi follows a fixed primary approach: the month-structure method in Zi Ping Zhen Quan. Di Tian Sui, Qiong Tong Bao Jian, San Ming Tong Hui and Yuan Hai Zi Ping provide separately attributed comparisons. Their differences remain visible.

## What it provides

- BaZi chart calculation with birth timezone, DST, true solar time and unknown-hour handling.
- Offline retrieval from five frozen classical editions, including chapter identifiers, source locations and neighboring paragraphs.
- Observable stem and branch relationships for checking a passage's conditions.
- Current time in the user's present location, captured once and reused across the request.
- Other methods only when requested, within their documented scope.

The default reading input excludes engineering strength scores, fatalistic spirit-star descriptions, zodiac compatibility scores and name-number verdicts. Diagnostic interfaces remain available for inspecting calculations.

## Start

Use Python 3.11 or later and a host that can load skill files and execute Python. The tested interpreter baseline is Python 3.11 / 3.12.

1. Download the corresponding ZIP from [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases).
2. Extract it and open a terminal inside the chinese-fortune folder.
3. Install the pinned runtime baseline:

```sh
python -m pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
python scripts/classical_search.py --validate
python scripts/request_time.py --current-timezone Australia/Sydney
```

Import the folder using your host's skill installation mechanism. The host must read SKILL.md and run scripts/ using the Python environment where dependencies were installed. If a dependency is missing, check that installation and execution use the same interpreter.

Example request: “Born 1990-05-10 at 14:30, male, Beijing; currently in Sydney. Explain the chart's main structure in plain language and show the evidence.”

A text lookup needs no birth data. An unknown birth hour stays unknown.

## Direct use

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --markdown
python scripts/classical_search.py --book ziping --query 用神
python scripts/classical_search.py --passage-id ziping:c008:p0001
```

The Markdown option explains chart facts. A complete personal interpretation still requires the host to read source passages, check conditions and answer the question. Without that option, the command returns structured facts and source retrieval results.

Keep birth timezone, present-location timezone and explicit target time separate. Reuse the utc value from request_time.py as --request-time across one request. Explicit historical or future dates do not borrow the machine's current clock.

## Evidence and limits

knowledge/manifest.json freezes each edition and its expected chapter inventory. Validation detects missing chapters and modified files. Every retrieved paragraph has a stable ID, provenance and context.

Acquiring a complete transcription does not establish image collation, rule applicability or real-world predictive validity. Each status is recorded separately. [Source and licensing notes](docs/CLASSICAL-SOURCES.md) describe the actual coverage.

[Reading example](docs/OUTPUT-EXAMPLE.md) · [Output contract](references/22-output-contract.md) · [Migration and validation](docs/OUTPUT-VALIDATION.md)

## Development

Run these commands in the Git source checkout. The release ZIP contains runtime files; it excludes development dependencies and tests.

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python -X utf8 evals/run_checks.py --checks-only
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

Use --checks-only after the complete test suite passes. Consult [CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml) for results tied to a commit. Actual model-answer evaluation remains separate from deterministic tests.

Other methods are [optional](references/23-optional-methods.md) and do not vote on BaZi conclusions. Code is [MIT](LICENSE); third-party texts retain the licensing recorded in the knowledge manifest and source notes.

For cultural study. Medical, legal and investment decisions require appropriate real-world information.
