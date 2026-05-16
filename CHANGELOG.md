# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-16

### Added — initial public release

**Core skill**
- `SKILL.md` — 123-line router with frontmatter trigger description (covers 25+ Chinese & English trigger keywords)
- `agents/openai.yaml` — OpenAI-compatible runtime metadata for cross-platform invocation

**References (23 files, ~11,540 lines)**
- `00-foundations.md` — Yin-Yang, 5 elements, 10 stems, 12 branches, 60 Jiazi, 8 trigrams, 24 solar terms, time pillars, 10 Gods, 12 life stages
- `01-bazi.md` — Four Pillars: chart construction, day-master strength, 10 Gods, shensha, patterns, luck cycles, annual interpretation, 6 family relations, health, three worked examples
- `02-ziwei.md` — Zi Wei Dou Shu: 12 palaces, chart steps, 14 main stars + assistants, 4 transformations, 三方四正, 大限, classic patterns, two worked examples
- `03-yijing.md` — I-Ching: 三易, 十翼, 阴阳爻, 64 hex formation, 6 casting methods, changing lines, 互/综/错/变卦
- `04-liuyao.md` — Liu Yao: 8 palaces, 世应, 六亲, 六神, 纳甲 full table, 用神, 10-step casting procedure
- `05-meihua.md` — Mei Hua Yi Shu: 7 casting methods, 体/用 core, 5 generation/control relations, 外应, 10 application categories
- `06-qimen.md` — Qi Men Dun Jia: 3 boards, 9 palaces, 3 wonders, 6 instruments, 8 gates, 9 stars, 8 gods, layout procedure, 12+ patterns
- `07-daliuren.md` — Da Liu Ren: 月将, 4 lessons, 3 transmissions (9 methods), 12 generals, 9 schools
- `08-fengshui.md` — Form school + 八宅 + 玄空飞星 + 三元九运 + 24 mountains + 形煞 + internal layout + modern reinterpretation
- `09-mianxiang.md` — Face: 3 zones, 5 features, 12 palaces, 5 face shapes, moles, lines, complexion, modern thin-slicing parallel
- `10-shouxiang.md` — Palm: 5 main lines, 8 trigrams in hand, 7+5 hand types, finger joints, nails, life-line timing
- `11-cezi.md` — Glyphomancy: 8 techniques (拆/添/减/反/谐音/字象/字意/笔画), 5 case studies, character-element mapping
- `12-huangli.md` — Almanac: 12 jianchu, 28 lunar mansions, 10 event categories, 三煞, 太岁, 彭祖百忌, full daily structure
- `13-qiming.md` — Naming: 5-grid analysis (天/人/地/外/总), 81 numerology (full table), 三才, BaZi-based supplementation, company naming
- `14-hehun.md` — Marriage compatibility: 3 methods, 12×12 zodiac matrix, 6 BaZi axes, modern meaning
- `15-jiemeng.md` — Dream interpretation: 6 dream types, traditional + Freud/Jung, ~80 common symbols across 10 categories
- `16-shengxiao.md` — Chinese zodiac: 12 detailed entries, 三合/六合/相冲/相刑/相害, 60 Jiazi pairings, 太岁 (本命/冲/刑/害/破)
- `17-xingzuo.md` — Western astrology: 12 signs, 4 elements × 3 modes, planets, houses, aspects, 12×12 compatibility
- `18-tarot.md` — 78 cards (22 major + 56 minor by suit), 7 spreads, reading procedure, vs I-Ching comparison
- `19-shensha.md` — Auspicious & inauspicious shensha: 16 + 19 entries with full 起法 (calculation rules)
- `20-disclaimer.md` — Red lines, ethical boundaries, crisis-handoff template, language safeguards
- `21-extended-methods.md` — Coverage matrix for 14 rare methods (Tai Yi, Tie Ban, Cheng Gu, Hetu-Luoshu, Seven Politics, Yan Qin, Xuan Kong Da Gua, Dou Shou, Ling Qian, Bei Jiao, Zhuge, bird/omen, etc.)
- `64hex-full.md` — All 64 hexagrams: classical 卦辞 + 大象 + 384 lines (王弼通行本) + 用九/用六 + 白话 summary

**Scripts (12 files, ~3,825 lines)**
- `bazi_calc.py` — Full BaZi: 4 pillars, hidden stems, 10 Gods per pillar, 5-element count (surface + hidden), nayin, shensha (9 categories), 大运 cycles, 流年
- `ziwei_calc.py` — Zi Wei: 命/身宫, 五行局, 紫微星position, 14 main stars, 12 palaces, 三方四正, 大限, year-干 transformations
- `yijing_cast.py` — I-Ching: 4 casting methods (coins/numbers/time/text), main/nuclear/changed hex, full classical text via assets/64hex.json
- `liuyao_cast.py` — Liu Yao: extends yijing with 京房八宫, 世应, 纳甲 (per-trigram), 六亲, 六神, 旺相休囚, 月破/日破/旬空
- `meihua_cast.py` — Mei Hua: time / numbers / name casting, 体/用 with 生克比和, seasonal strength
- `xiaoliuren_cast.py` — Xiao Liu Ren quick cast (no dependencies): 6-palace cycle, lunar/solar input
- `huangli_query.py` — Daily almanac: 12 jianchu, 28 mansions, 宜/忌, 吉时, directional gods, 彭祖百忌, 胎神, 冲煞
- `lunar_convert.py` — Solar ↔ lunar with jieqi, ganzhi, zodiac, 28-xiu
- `name_analyze.py` — Naming: 5-grid + 81 numerology + 三才, with 2,594-char Kangxi stroke table
- `zodiac_compat.py` — Zodiac info, 12×12 compatibility (1-10 score), year-zodiac lookup, Tai Sui check
- `tarot_draw.py` — Tarot: 5 spreads (one/three/celtic/relationship/daily), full 78-card deck, seedable
- `utils.py` — Shared constants: 干/支/五行/八卦/藏干, 十神 computation, 五虎遁/五鼠遁, longitude correction, UTF-8 JSON printing, graceful lunar_python guard

**Assets (11 JSON files, 211 KB)**
- `ganzhi.json` — 10 stems + 12 branches + 60 Jiazi + nayin + 5 he + 4 san-he + 4 san-hui + 6 chong + 4 xing + 6 hai
- `wuxing.json` — 5 elements with full property map + 旺相休囚死 by season
- `bagua.json` — 8 trigrams with binary, nature, family, body, animal, directions
- `64hex.json` — 64 hexagrams: judgment + image + 6 lines each (+ 用九/用六 for 乾/坤)
- `ziwei_stars.json` — 14 main + 6 auspicious + 6 malefic stars, 10 year-stem transformations, 5 wuxing-ju
- `shensha.json` — 16 auspicious + 19 inauspicious shensha with 起法 tables, 6 旬空, 三合五行 group
- `24jieqi.json` — 24 solar terms with 节/气 marker + BaZi month mapping
- `tarot78.json` — 22 major + 56 minor arcana (upright + reversed meanings)
- `jiemeng.json` — ~80 dream symbols (traditional + modern psychology)
- `name_bihua.json` — 2,594 Kangxi-dictionary stroke counts
- `name_shuli.json` — Full 81-numerology table

**Validation**
- `evals/evals.json` — 12 test cases covering all major methods
- `evals/run_checks.py` — 4-check release harness: frontmatter strict (`name` + `description` only, ≤1024 chars, 9 mandatory triggers); all scripts emit valid non-error JSON; all routed references exist; no TODO/TBD/placeholder/pycache leftover

**Documentation**
- `README.md` — English
- `README.zh.md` — Simplified Chinese
- `LICENSE` — MIT + cultural-content disclaimer
- `CONTRIBUTING.md` — Bilingual contribution guide
- `CHANGELOG.md` — This file

### Safety

- Hard-coded red lines refuse: death prediction, medical/legal/financial advice, curses, third-party blame, fee demands, product recommendations
- Crisis-handoff template for self-harm / acute distress signals
- Disclaimer auto-emitted on every chart-based reading

### Known limits

- `ziwei_calc.py` covers 命/身宫 + 14 main stars; assistant stars (副星) and 自化 / 流年 飞星 marked as scope for v1.1
- `奇门` / `大六壬` / `太乙` lack computation scripts (reference-only for now)
- `jiemeng.json` at 80 entries (target 500+ for v1.1)
- `assets/64hex.json` covers 王弼通行本 only; alternative transmissions not included
