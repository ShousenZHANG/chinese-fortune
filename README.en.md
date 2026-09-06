<div align="center">

# Chinese Fortune · 中国传统命理

**A Claude Skill packing 20+ Chinese metaphysics methods (五术: 山·医·命·相·卜) into one portable skill.**

[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![release](https://img.shields.io/github/v/release/ShousenZHANG/chinese-fortune)](https://github.com/ShousenZHANG/chinese-fortune/releases)

[简体中文](README.md) ｜ **English**

</div>

---

BaZi, Zi Wei Dou Shu, I-Ching, Liu Yao, Qi Men Dun Jia, Feng Shui, almanac, naming, Tarot, and more. Heavy calendrical math runs in deterministic Python scripts; Claude narrates from the reference docs. **Cultural and educational reference only — not medical, legal, or financial advice.**

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Methods](#methods)
- [How It Works](#how-it-works)
- [Safety](#safety)
- [Quality Gates](#quality-gates)
- [Contributing](#contributing)
- [License & Sources](#license--sources)

## Features

- **20+ methods, one skill** — divination, destiny, physiognomy, and practical arts in a single self-contained skill. No backend, no network.
- **Deterministic computation** — Python scripts calculate charts with `lunar_python`; the language model explains their structured results.
- **Explicit time conventions** — BaZi and Zi Wei share solar-time normalization, date rollover and DST validation. Independent-engine grids check clock-time pillars and star placement; separate boundary tests check normalization. These checks do not establish predictive validity.
- **Progressive disclosure** — Claude loads the small router first, then only the reference/script for the method in play. Minimal context cost.
- **Traceable interpretation** — chart facts, conditional traditional readings and practical suggestions are separate. Selected classical passages have source records; unverified table entries remain candidates. Structural checks require evidence and conditions; actual prose still needs semantic review.
- **Optional quantum entropy** — casts accept `--entropy quantum` (ANU quantum-vacuum noise; degrades gracefully and is honestly labeled; no accuracy claim).
- **Exploration tool** — `explore_cast.py`: QRNG points + density anomalies (attractor/void) + almanac auspicious-direction overlay + safety block, Randonautica-style walk prompts (explicitly not prediction, not MMI).
- **Safety rails** — hard red lines (no death-date prediction, no medical/legal/financial calls, no curses) plus a crisis hand-off, built into the skill.
- **Quality checks** — pytest with coverage, `ruff`, `mypy`, release checks and Windows package smoke tests. Consult the current run for measured results.

## Quick Start

Download `chinese-fortune-v*.zip` from [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) and import:

| Platform | How |
|---|---|
| **Claude Code** | Unzip into `~/.claude/skills/` → restart. The `chinese-fortune/` folder is the skill. |
| **Claude.ai** | Settings → Capabilities → Skills → **Upload skill** → select the zip. |
| **OpenAI / other** | Unzip anywhere; point your agent at `agents/openai.yaml` and call the `scripts/` as tools. |

```bash
pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
```

Then just talk to Claude — the skill auto-triggers on Chinese or English fortune requests:

```text
Born 1990-05-10, 2:30 PM, male, Beijing. Give me a full BaZi reading.
Cast an I-Ching hexagram with coins on whether I should switch jobs.
I want to move house in June 2026, I'm a Dragon — which days are auspicious?
```

Scripts also run standalone (structured JSON on stdout):

```bash
python scripts/bazi_calc.py --year 1990 --month 5 --day 10 --hour 14 --gender male
python scripts/yijing_cast.py coins --question "should I take the offer?"
python scripts/huangli_query.py --date 2026-06-15
```

Run `python scripts/<name>.py --help` for options. Build the package from source: `python scripts/build_skill.py`.

## Methods

The [SKILL.md routing table](SKILL.md#quick-router--pick-the-right-method) is the shared inventory of methods, references and callable scripts. A `—` in the Script column means reference-only support. A script implements the documented scope; it does not cover every school or establish predictive validity. School-specific limits live in the linked reference.

## How It Works

```
SKILL.md           router — frontmatter trigger + method table
references/        theory, interpretation guides and output contract
scripts/           deterministic engines and evidence review
assets/            lookup tables and versioned classical evidence
evals/             release checks and actual-response evaluation runner (source checkout)
tests/             pytest golden values + edge cases + independent-engine diff
```

The project combines `lunar_python` calendrical calculations with its own time normalization and conditional interpretation layer. Version 2.0 returns nullable final 用神/喜忌 values and separate candidates. See [migration and validation](docs/OUTPUT-VALIDATION.md).

## Safety

Hard red lines (see [references/20-disclaimer.md](references/20-disclaimer.md)): no death-date prediction, no medical/legal/financial decisions, no curse/harm requests, no blaming third parties, no paid "remedies". Every reading is framed as a reflective pattern with a brief disclaimer, and acute-distress signals trigger a crisis-resource hand-off.

## Quality Gates

```bash
python -X utf8 evals/run_checks.py     # release harness (7 checks)
python -m pytest tests/                # unit + integration + independent diff
```

CI (Python 3.11 / 3.12) enforces five gates:

| Gate | What |
|---|---|
| `ruff` | linting, zero tolerance |
| `mypy` | static type checking |
| `pytest` | **CI-reported tests** — golden values, 立春/late-子时/leap-month edges, 五鼠遁 invariant, an end-to-end engine differential vs `sxtwl` (~1,800 charts), and a 903-chart 紫微 differential vs `iztro` |
| coverage | subprocess-tracked **CI-reported coverage**, fails under 80% |
| harness | SKILL.md validation + interpretive-discipline lock + 19 machine-asserted scenarios + script JSON integrity (7 checks) |

## Contributing

PRs welcome — deeper Zi Wei / Xuan Kong logic, more `evals` scenarios, Traditional-Chinese translations. Run `evals/run_checks.py` and `pytest` before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License & Sources

[MIT](LICENSE). Built on classical texts (《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》 …) and [`6tail/lunar-python`](https://github.com/6tail/lunar-python). Readings are conditional traditional interpretations for cultural and educational reference; they do not represent statistically validated event probabilities.

## Version 2 output contract

Use `pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt`.
BaZi and ZiWei default to `--time-standard true-solar`; `clock` is an explicit
school choice. Ambiguous local times require `--fold 0/1`.

`schema_version=2.0`: use `status` and `yong_shen.views`; `primary` can be null.
Candidates are not final personal verdicts. `reading_support` links facts and
conditions to source records. Quotation checks are structural, not independent
proof of semantic correctness or predictive validity.

Exact test counts and coverage belong to the CI report of the tested commit.
Thirty scenarios in `evals/reading_cases.json` are an evaluation specification,
not passed model runs. Missing real answers or semantic reviews fail
`evals/evaluate_readings.py --responses recording.json`.
