<div align="center">

# Chinese Fortune · 中国传统命理

**A Claude Skill packing 20+ Chinese metaphysics methods (五术: 山·医·命·相·卜) into one portable skill.**

[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-2149%20passing-brightgreen)](tests)
[![coverage](https://img.shields.io/badge/coverage-88%25-brightgreen)](#quality-gates)
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
- **Deterministic computation** — 15 Python engines on `lunar_python` (a port of the [寿星天文历](https://github.com/6tail/lunar-python) algorithm, solar-term error < 1s) do the 排盘/起卦, instead of asking an LLM to do error-prone arithmetic.
- **Calendrically rigorous** — true solar time, solar-term month boundaries, the 立春 year boundary, late-子时, and leap months are all correct, and cross-checked against the **independent `sxtwl` engine** at two levels: (1) **this repo's engine** end-to-end over 6,045 charts (1920–2080, every 29 days × 3 hours, covering both sides of the 夜子/早子 boundary), zero divergence; (2) the underlying `lunar_python` library against sxtwl on all 58,440 days, zero divergence — that second layer validates the dependency, not this repo's code, and the two are stated separately.
- **Progressive disclosure** — Claude loads the small router first, then only the reference/script for the method in play. Minimal context cost.
- **Interpretive discipline (CI-locked)** — BaZi judgments are bound to the five classics (《子平真诠》《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》): no claim the classics cannot support, no platitudes or flattery, only the most verifiable conclusions. The discipline text is asserted by the release harness — deleting it fails the build.
- **Optional quantum entropy** — casts accept `--entropy quantum` (ANU quantum-vacuum noise; degrades gracefully and is honestly labeled; no accuracy claim).
- **Exploration tool** — `explore_cast.py`: QRNG points + density anomalies (attractor/void) + almanac auspicious-direction overlay + safety block, Randonautica-style walk prompts (explicitly not prediction, not MMI).
- **Safety rails** — hard red lines (no death-date prediction, no medical/legal/financial calls, no curses) plus a crisis hand-off, built into the skill.
- **Engineered** — 2149 tests / 88% coverage / `ruff` + `mypy` + a 5-gate CI + a 7-check release harness.

## Quick Start

Download `chinese-fortune-v*.zip` from [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) and import:

| Platform | How |
|---|---|
| **Claude Code** | Unzip into `~/.claude/skills/` → restart. The `chinese-fortune/` folder is the skill. |
| **Claude.ai** | Settings → Capabilities → Skills → **Upload skill** → select the zip. |
| **OpenAI / other** | Unzip anywhere; point your agent at `agents/openai.yaml` and call the `scripts/` as tools. |

```bash
pip install "lunar_python>=1.4.4,<2.0"   # all platforms: accurate 农历 / 八字 / 黄历
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

| Group | Methods | Has script |
|---|---|---|
| **命 Destiny** | BaZi, Zi Wei Dou Shu, 称骨, 河洛理数, 七政四余 | BaZi, Zi Wei |
| **卜 Divination** | I-Ching, Liu Yao, Mei Hua, Qi Men, Da Liu Ren, Xiao Liu Ren, Tai Yi, oracle slips, Bei Jiao | I-Ching, Liu Yao, Mei Hua, Qi Men, Da/Xiao Liu Ren |
| **相 Physiognomy** | Feng Shui (Eight Mansions / Xuan Kong), face, palm, glyphomancy | — (reference-guided) |
| **术 Practical** | almanac date selection, naming, compatibility, dream, zodiac, astrology, Tarot | almanac, naming, compatibility/zodiac, Tarot |
| **游 Exploration** | random walk points (QRNG + almanac directions; not divination) | exploration |

Each method except exploration (a pure tool, no reference doc) maps to a reference doc in `references/`, and (where computation helps) a script in `scripts/`. The full routing table lives in [SKILL.md](SKILL.md).

## How It Works

```
SKILL.md           router — frontmatter trigger + method table
references/  (23)   the canon: theory + per-method interpretation guides
scripts/     (15)   deterministic engines (lunar_python + SystemRandom + optional QRNG)
assets/      (12)   JSON lookup tables (干支, 64卦, 神煞, Tarot, strokes …)
evals/             release harness + 19 machine-asserted scenarios
tests/             pytest golden values + edge cases + independent-engine diff
```

Calendrical correctness (true solar time, solar-term months, 立春 year boundary, late-子时, leap months) is delegated to `lunar_python`; the skill adds the 格局/用神/interpretation layer on top.

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
| `pytest` | **2149 tests** — golden values, 立春/late-子时/leap-month edges, 五鼠遁 invariant, day-pillar differential vs the independent `sxtwl` engine over all 58,440 days of 1920–2080, and a 903-chart 紫微 differential vs `iztro` |
| coverage | subprocess-tracked **88%**, fails under 80% |
| harness | SKILL.md validation + interpretive-discipline lock + 19 machine-asserted scenarios + script JSON integrity (7 checks) |

## Contributing

PRs welcome — deeper Zi Wei / Xuan Kong logic, more `evals` scenarios, Traditional-Chinese translations. Run `evals/run_checks.py` and `pytest` before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License & Sources

[MIT](LICENSE). Built on classical texts (《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》 …) and [`6tail/lunar-python`](https://github.com/6tail/lunar-python). Cultural/educational reference only — readings are probabilistic patterns, not deterministic predictions.
