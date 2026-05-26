# Chinese Fortune · 中国传统命理 Claude Skill

> 20+ traditional Chinese metaphysics methods in one Claude skill · MIT · [中文](README.zh.md)

A Claude Code / Agent SDK skill covering the Chinese metaphysical canon (五术：山医命相卜) — BaZi, Zi Wei Dou Shu, I-Ching, Liu Yao, Qi Men, Feng Shui, almanac, naming, Tarot, and more. Heavy calendrical math runs in deterministic Python scripts; Claude narrates the result from the reference docs.

For **cultural exploration and self-reflection** — not medical, legal, or financial advice.

## Quickstart

```bash
git clone https://github.com/<your-org>/chinese-fortune.git
cp -r chinese-fortune ~/.claude/skills/chinese-fortune   # install for Claude Code
pip install "lunar_python>=1.4.4,<2.0"                    # accurate 农历/八字/黄历
```

Then just talk to Claude — the skill auto-triggers on Chinese or English fortune requests:

```text
我 1990 年 5 月 10 日下午 2 点半出生，男，北京。详细批一下八字。
帮我用铜钱起一卦，问要不要跳槽。
2026 年 6 月想搬家，我属龙，哪几天合适？
```

Scripts also run standalone (structured JSON on stdout):

```bash
python scripts/bazi_calc.py --year 1990 --month 5 --day 10 --hour 14 --gender male
python scripts/yijing_cast.py coins --question "should I take the offer?"
python scripts/huangli_query.py --date 2026-06-15
```

Run `python scripts/<name>.py --help` for options.

## Methods

| Group | Methods | Has script |
|---|---|---|
| 命 Destiny | 八字 BaZi, 紫微斗数, 称骨, 河洛理数, 七政四余 | 八字, 紫微 |
| 卜 Divination | 周易 I-Ching, 六爻, 梅花易数, 奇门遁甲, 大六壬, 小六壬, 太乙, 灵签, 杯筊 | I-Ching, 六爻, 梅花, 奇门, 大六壬, 小六壬 |
| 相 Physiognomy | 风水 (八宅/玄空), 面相, 手相, 测字 | — (reference-guided) |
| 术 Practical | 黄历择日, 姓名学, 合婚, 解梦, 生肖, 星座, 塔罗 | 黄历, 姓名, 合婚/生肖, 塔罗 |

Each method maps to a reference doc in `references/` and (where computation helps) a script in `scripts/`. The full routing table lives in [SKILL.md](SKILL.md).

## How it works

```
SKILL.md          router — frontmatter trigger + method table
references/  (23)  the canon: theory + per-method interpretation guides
scripts/     (13)  deterministic computation (lunar_python + SystemRandom)
assets/      (12)  JSON lookup tables (干支, 64卦, 神煞, 塔罗, 笔画 …)
evals/            release harness + 12 scenario assertions
tests/            pytest golden-value + edge-case suite
```

Progressive disclosure: Claude loads the small router first, then only the reference/script for the method in play. Calendrical correctness (真太阳时, 节气定月, 立春年界, 夜子时, 闰月) is delegated to `lunar_python`; the skill adds the 格局/用神/interpretation layer on top.

## Safety

Hard red lines (see [references/20-disclaimer.md](references/20-disclaimer.md)): no death-date prediction, no medical/legal/financial decisions, no curse/harm requests, no blaming third parties, no paid "remedies". Every reading is framed as a reflective pattern with a brief disclaimer, and acute-distress signals trigger a crisis-resource handoff.

## Validation

```bash
python -X utf8 evals/run_checks.py     # 6-check release harness
python -m pytest tests/                # unit + integration suite
```

`run_checks.py` verifies: SKILL.md frontmatter, every script emits valid JSON, reference coverage, the 12 eval scenarios' machine assertions, the pytest suite, and release cleanliness. It prints a PASS/FAIL summary and exits non-zero on any failure.

## Contributing

PRs welcome — deeper 紫微/玄空飞星 logic, more `evals` scenarios, 繁體/English reference translations. Run `evals/run_checks.py` and `pytest` before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License & sources

[MIT](LICENSE). Built on classical texts (《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》 …) and [`6tail/lunar-python`](https://github.com/6tail/lunar-python). Cultural/educational reference only — readings are probabilistic patterns, not deterministic predictions.
