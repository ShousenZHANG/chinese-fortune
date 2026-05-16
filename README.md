# Chinese Fortune — A Claude Skill for Traditional Chinese Metaphysics

> 中国传统命理占卜 · Claude Skill · 20+ methods · MIT License
> [中文文档](README.zh.md) · [Quickstart](#quickstart) · [Methods](#supported-methods) · [Safety](#safety--limits)

A comprehensive Claude Code / Claude Agent SDK skill that bundles the full Chinese metaphysical canon (五术：山·医·命·相·卜) into a single navigable system. It supports analysis, chart-casting, lookups, and synthesis across **20+ traditional methods** plus adjacent practices (Western astrology, Tarot, dream interpretation, naming).

Designed for **cultural exploration and introspective reflection**, not for medical / legal / financial decisions.

---

## Highlights

- **20+ divination systems**: BaZi (Four Pillars), Zi Wei Dou Shu, I-Ching (64 hex full text), Liu Yao, Mei Hua Yi Shu, Qi Men Dun Jia, Da Liu Ren, Xiao Liu Ren, Feng Shui (Eight Mansions / Xuan Kong), face reading, palmistry, glyphomancy, almanac date selection, naming, marriage compatibility, dream interpretation, Chinese zodiac, Western astrology, Tarot, and an extended-methods matrix (Tai Yi, Tie Ban, Cheng Gu, Hetu-Luoshu, Seven Politics, Ling Qian, Bei Jiao, etc.)
- **Production-grade architecture**: progressive disclosure (123-line SKILL.md router → 23 reference docs → 11 Python scripts → 11 JSON assets)
- **Real computation**: `lunar_python` for solar/lunar conversion, 24 solar terms, 60 Jiazi cycle, true solar time; `random.SystemRandom` for genuine divinatory randomness
- **Strict safety rails**: hard-coded red lines (no death prediction, no medical/legal/financial advice, no curse removal, no relationship blame, crisis-handoff template)
- **Self-validating**: `evals/run_checks.py` enforces frontmatter compliance, script JSON output integrity, reference coverage, and release cleanliness
- **15,907 lines, 906 KB total**

---

## Quickstart

### 1. Install the skill

```bash
# Clone
git clone https://github.com/<your-org>/chinese-fortune.git
cd chinese-fortune

# Copy to Claude's user skill directory
# Claude Code (any OS)
cp -r . ~/.claude/skills/chinese-fortune

# Install Python dependency for accurate BaZi / lunar / almanac
pip install lunar_python
```

### 2. Use in Claude

Open a new Claude Code session and just talk:

```text
我 1990 年 5 月 10 日下午 2 点 30 分出生的男性，北京。详细批一下八字。
```

```text
帮我用铜钱起一卦，问要不要跳槽。
```

```text
2026 年 6 月想搬家，我属龙，哪几天合适？
```

The skill auto-triggers on Chinese or English requests matching its description. No manual invocation needed.

### 3. Direct CLI usage (no Claude required)

Every script emits structured JSON to stdout:

```bash
python scripts/bazi_calc.py --year 1990 --month 5 --day 10 \
  --hour 14 --minute 30 --gender male --longitude 116.4

python scripts/yijing_cast.py coins --question "should I take the offer?"

python scripts/huangli_query.py --date 2026-06-15

python scripts/zodiac_compat.py compat --a tiger --b monkey

python scripts/tarot_draw.py three --seed 42
```

Run `python scripts/<name>.py --help` for full options.

---

## Supported Methods

### 命 · Destiny analysis
| Method | Trigger | Reference | Script |
|---|---|---|---|
| 八字 BaZi (Four Pillars) | "八字" / "排盘" / birth time | [01-bazi.md](references/01-bazi.md) | `bazi_calc.py` |
| 紫微斗数 Zi Wei Dou Shu | "紫微" / "命宫" | [02-ziwei.md](references/02-ziwei.md) | `ziwei_calc.py` |
| 称骨算命 Bone-weight | "称骨" / "几两" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 河洛理数 Hetu-Luoshu | "河洛" / "先天数" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 七政四余 Seven Politics | "七政" / "果老星宗" | [21-extended-methods.md](references/21-extended-methods.md) | — |

### 卜 · Divination
| Method | Trigger | Reference | Script |
|---|---|---|---|
| 周易 I-Ching | "起卦" / "周易" / "易经" | [03-yijing.md](references/03-yijing.md) + [64hex-full.md](references/64hex-full.md) | `yijing_cast.py` |
| 六爻 Liu Yao | "六爻" / "摇卦" / "金钱卦" | [04-liuyao.md](references/04-liuyao.md) | `liuyao_cast.py` |
| 梅花易数 Mei Hua | "梅花" / "心易" | [05-meihua.md](references/05-meihua.md) | `meihua_cast.py` |
| 奇门遁甲 Qi Men | "奇门" / "八门" | [06-qimen.md](references/06-qimen.md) | — |
| 大六壬 Da Liu Ren | "六壬" / "三传" | [07-daliuren.md](references/07-daliuren.md) | — |
| 小六壬 Xiao Liu Ren | "小六壬" / "大安留连" | [21-extended-methods.md](references/21-extended-methods.md) | `xiaoliuren_cast.py` |
| 太乙神数 Tai Yi | "太乙" / "国运" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 灵签 Oracle slips | "观音签" / "签文" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 杯筊 Bei Jiao | "圣杯" / "笑杯" / "阴杯" | [21-extended-methods.md](references/21-extended-methods.md) | — |

### 相 · Physiognomy & Feng Shui
| Method | Trigger | Reference |
|---|---|---|
| 风水 Feng Shui (Eight Mansions / Xuan Kong / form school) | "风水" / "阳宅" / "玄空飞星" / "八宅" | [08-fengshui.md](references/08-fengshui.md) |
| 面相 Face Reading | "面相" / "脸相" / "痣" | [09-mianxiang.md](references/09-mianxiang.md) |
| 手相 Palmistry | "手相" / "掌纹" / "生命线" | [10-shouxiang.md](references/10-shouxiang.md) |
| 测字 Glyphomancy | "测字" / "拆字" | [11-cezi.md](references/11-cezi.md) |

### 卜·术 · Adjacent practical methods
| Method | Trigger | Reference | Script |
|---|---|---|---|
| 黄历 Almanac date selection | "黄历" / "宜搬家" / "择日" | [12-huangli.md](references/12-huangli.md) | `huangli_query.py` |
| 姓名学 Naming | "起名" / "改名" | [13-qiming.md](references/13-qiming.md) | `name_analyze.py` |
| 合婚 Compatibility | "合婚" / "我俩合不合" | [14-hehun.md](references/14-hehun.md) | `zodiac_compat.py` |
| 解梦 Dream interpretation | "解梦" / "梦见" | [15-jiemeng.md](references/15-jiemeng.md) | — |
| 生肖 Chinese zodiac | "属相" / "本命年" / "犯太岁" | [16-shengxiao.md](references/16-shengxiao.md) | `zodiac_compat.py` |
| 星座 Western astrology | "星座" / "上升" | [17-xingzuo.md](references/17-xingzuo.md) | — |
| 塔罗 Tarot | "塔罗" / "抽牌" | [18-tarot.md](references/18-tarot.md) | `tarot_draw.py` |

### Foundations & reference
| Topic | Reference |
|---|---|
| Yin-Yang, Five Elements, 10 Stems, 12 Branches, 60 Jiazi, 8 Trigrams, 24 Solar Terms | [00-foundations.md](references/00-foundations.md) |
| 神煞 Shensha (auspicious / inauspicious stars) | [19-shensha.md](references/19-shensha.md) |
| Disclaimer & ethical boundaries | [20-disclaimer.md](references/20-disclaimer.md) |
| Extended methods matrix | [21-extended-methods.md](references/21-extended-methods.md) |
| Full 64-hexagram text (judgment + image + all 384 lines) | [64hex-full.md](references/64hex-full.md) |

---

## Architecture

```
chinese-fortune/
├── SKILL.md                # 123-line router with frontmatter trigger description
├── agents/openai.yaml      # OpenAI-compatible runtime metadata
├── references/             # 23 markdown files, ~11,540 lines
│   ├── 00-foundations.md   # Yin-Yang, 5 elements, 10 stems, 12 branches, 8 trigrams
│   ├── 01-bazi.md          # Four Pillars: chart construction, 10 Gods, luck cycles
│   ├── 02-ziwei.md         # Zi Wei: 12 palaces, 14 main stars, transformations
│   ├── 03-yijing.md        # I-Ching theory & 6 casting methods
│   ├── 04-liuyao.md        # Liu Yao: 8 palaces, six relatives, six spirits
│   ├── 05-meihua.md        # Mei Hua: body/use, season strength, omens
│   ├── 06-qimen.md         # Qi Men: 9 palaces, 8 gates, 9 stars, 8 gods
│   ├── 07-daliuren.md      # Da Liu Ren: 4 lessons, 3 transmissions, 12 generals
│   ├── 08-fengshui.md      # 8 Mansions + Xuan Kong + form school + 24 mountains
│   ├── 09-mianxiang.md     # Face: 3 zones, 5 features, 12 palaces, moles, lines
│   ├── 10-shouxiang.md     # Palm: 5 lines, 8 trigrams in hand, hand types
│   ├── 11-cezi.md          # Glyphomancy: split/add/remove, classical cases
│   ├── 12-huangli.md       # Almanac: 12 jianchu, 28 lunar mansions, 10 events
│   ├── 13-qiming.md        # Naming: 5-grid analysis, 81 numerology, 3-talents
│   ├── 14-hehun.md         # Compatibility: 12×12 zodiac, 6 BaZi axes
│   ├── 15-jiemeng.md       # Dream: 6 dream types, ~80 common symbols
│   ├── 16-shengxiao.md     # 12 zodiac details + Tai Sui doctrine
│   ├── 17-xingzuo.md       # 12 Western signs + 4 elements + 3 modes
│   ├── 18-tarot.md         # 78 cards (22 major + 56 minor) + 7 spreads
│   ├── 19-shensha.md       # Shensha: 16 auspicious + 19 inauspicious
│   ├── 20-disclaimer.md    # Red lines + ethical framing + crisis handoff
│   ├── 21-extended-methods.md  # Coverage matrix for 14 rare methods
│   └── 64hex-full.md       # All 64 hexagrams, classical 王弼 text
├── scripts/                # 11 Python scripts + utils.py
│   ├── bazi_calc.py        # Full BaZi: 4 pillars, 10 Gods, shensha, luck cycles
│   ├── ziwei_calc.py       # Zi Wei skeleton: palaces, main stars, transformations
│   ├── yijing_cast.py      # I-Ching: 4 casting methods, main/nuclear/changed hex
│   ├── liuyao_cast.py      # Liu Yao with 8-palace, nayin, six relatives & spirits
│   ├── meihua_cast.py      # Mei Hua with body/use & season strength
│   ├── xiaoliuren_cast.py  # Xiao Liu Ren quick cast (no dep)
│   ├── huangli_query.py    # Daily almanac
│   ├── lunar_convert.py    # Solar ↔ lunar with jieqi
│   ├── name_analyze.py     # 5-grid + 81 numerology + 3-talents
│   ├── zodiac_compat.py    # 12×12 compatibility + Tai Sui
│   ├── tarot_draw.py       # 5 spreads, full 78-card deck
│   └── utils.py            # Shared constants, 10 Gods, longitude correction
├── assets/                 # 11 JSON lookup tables (211 KB)
│   ├── ganzhi.json         # 10 stems, 12 branches, 60 Jiazi + Nayin
│   ├── wuxing.json         # 5-element generation/control/seasonal strength
│   ├── bagua.json          # 8 trigrams with attributes
│   ├── 64hex.json          # 64 hexagrams (King Wen text)
│   ├── ziwei_stars.json    # 14 main + 12 assistant stars + transformations
│   ├── shensha.json        # 16 auspicious + 19 inauspicious shensha
│   ├── 24jieqi.json        # 24 solar terms
│   ├── tarot78.json        # 22 major + 56 minor arcana
│   ├── jiemeng.json        # ~80 dream symbols (traditional + psychological)
│   ├── name_bihua.json     # 2,594 characters' Kangxi stroke counts
│   └── name_shuli.json     # 81 numerology table
└── evals/
    ├── evals.json          # 12 test prompts covering all major methods
    └── run_checks.py       # 4-check release-readiness harness
```

---

## Safety & Limits

This skill **refuses** the following requests (see [20-disclaimer.md](references/20-disclaimer.md)):

- Death-date prediction
- Specific medical / terminal illness diagnosis (redirects to a doctor)
- Specific legal advice (redirects to a lawyer)
- Specific financial trades or investment timing (redirects to a licensed advisor)
- Cursing / harming third parties
- Naming a third party as the cause of misfortune
- Demanding payment or ritual fees
- Promoting purchase of "remedy items"
- Political election prediction

It **always**:

- Frames readings as cultural / introspective patterns, not deterministic prophecy
- Includes a brief disclaimer when delivering a chart-based reading
- Escalates to crisis resources (24h hotline) on signals of self-harm or acute distress

---

## Validation

Run the release checks before publishing or making changes:

```bash
PYTHONDONTWRITEBYTECODE=1 python -X utf8 evals/run_checks.py
```

Expected output:

```
ok check_skill_metadata
ok check_core_scripts
ok check_reference_coverage
ok check_release_cleanliness
```

The harness enforces:
1. SKILL.md frontmatter has exactly `name` + `description`, description ≤ 1024 chars, all 9 mandatory triggers present
2. All 11 core scripts emit valid non-error JSON
3. All routed reference files exist
4. No `TODO` / `TBD` / `placeholder` / `__pycache__` left in release

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome for:

- Additional reference depth (especially for 紫微 stars, 玄空 飞星 specifics, 解梦 词条)
- New methods (currently no script for 奇门 / 大六壬 / 太乙)
- Translations (currently 简体中文 only; 繁體中文 + English content welcome)
- More test cases in `evals/evals.json`

Please run `evals/run_checks.py` before submitting.

---

## License

[MIT](LICENSE) — free for personal, academic, and commercial use. No warranty.

---

## Acknowledgments

- Classical sources: 《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》《奇门遁甲秘笈大全》《六壬大全》《葬书》《麻衣相法》《钦定协纪辨方书》
- Python lunar calendar: [`6tail/lunar-python`](https://github.com/6tail/lunar-python)
- Built as a [Claude Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for Claude Code, Claude Agent SDK, and any compatible runtime

---

## Disclaimer

This software provides **cultural and educational reference** based on traditional Chinese metaphysical practice. It is **not** a substitute for medical, legal, psychological, or financial professional advice. Readings are probabilistic patterns, not deterministic predictions. Use thoughtfully.
