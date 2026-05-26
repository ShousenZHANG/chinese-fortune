# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] — 2026-05-26

Engineering-hardening pass (no reading-logic changes). Closes blockers from a CTO-grade code audit; raises correctness, determinism, and test rigor.

### Fixed
- **真太阳时 day roll-over (correctness)** — `utils.longitude_correction` clamped near-midnight times to the same day, corrupting the 日柱 (day pillar) for western/eastern longitudes. Now returns `(day_offset, hour, minute)`; `bazi_calc.py` and `qimen_cast.py` apply the offset to the date before deriving pillars.
- **Operator precedence** in `lunar_convert._serialize` 节气 lookup (`A or B and C`) → explicit null-guarded branch.
- **Non-deterministic output** — `bazi_calc.py` 流年 used `datetime.now().year`; added `--as-of-year` for reproducible output.
- **Silent wrong strokes** — `name_analyze.py` defaulted unknown chars to 8 strokes; now merges `FALLBACK_BIHUA` under the asset (fixes missing common chars e.g. 涵=12), adds a `reliable` flag, and a `--strict` mode that refuses estimation.
- `00-foundations.md` 天干相克 label "5克" → "10克 (阳干5 + 阴干5)".
- `evals/run_checks.py` printed `ok` per check before a later check failed (misleading); now collects results and prints a PASS/FAIL summary with correct exit code; stopped false-flagging gitignored `__pycache__` (only TRACKED cache fails).

### Added
- **Input validation** in `bazi_calc.py` (month/day/hour/minute/year bounds) returning structured errors before touching lunar_python.
- **pytest suite** (`tests/`, 72 tests) — golden values for 十神/五行/60甲子/真太阳时, midnight roll-over regression, bazi end-to-end snapshots, determinism, input validation, name reliability.
- **Machine assertions** for all 12 eval scenarios (`evals.json`) + `check_eval_assertions` and `check_unit_tests` wired into `run_checks.py` (deterministic substrate now verified, not just described).
- Pinned `lunar_python>=1.4.4,<2.0`.

### Removed
- `scripts/bazi_geju.py` + `scripts/ziwei_patterns.py` (1666 LOC) — unused (zero imports) and divergent from the inline 格局/pattern logic in `bazi_calc.py`/`ziwei_calc.py`. Consolidated to a single source of truth. The inline engines remain the active, tested implementations.

### Known deferred (non-blocking)
- Shared constant tables (旬空/六冲/季节五行) still duplicated across a few cast scripts (identical values, low risk). The real divergence hazard (differing 格局 thresholds) was in the removed dead modules.

## [1.1.0] — 2026-05-16

Major depth + safety upgrade after deep competitive code analysis of top 6 GitHub rivals (jinchenma94/bazi-skill 1420⭐, hhszzzz/taibu 156⭐, Horace-Maxwell/horosa-skill 136⭐, china-testing/bazi 1316⭐, Renhuai123/ziwei-doushu 563⭐, cantian-ai/bazi-mcp 373⭐). All algorithms re-derived from classical public-domain sources (《穷通宝鉴》《滴天髓》《紫微斗数全书》《奇门遁甲秘籍大全》《六壬大全》).

### Added

**New methods with computational scripts**
- `scripts/qimen_cast.py` (833 lines) — 奇门遁甲 时家盘: 局数自动判定 (节气+三元), 三奇六仪 地盘/天盘排布, 八门九星八神飞布, 8 种格局检出 (三诈/天遁/地遁/人遁/青龙返首/飞鸟跌穴/击刑/入墓)
- `scripts/liuren_cast.py` (647 lines) — 大六壬 时课: 月将加时, 四课, 三传 (5法: 贼克/比用/遥克/伏吟/反吟), 12 天将昼夜布盘, 用神 keyword routing

**Pattern detection modules**
- `scripts/bazi_geju.py` (746 lines) — 八字格局自动判定: 特殊格 (从财/从杀/从儿/从势/化气/一行得气/两气成象) + 10 正格 + 破/纯/救应判定
- `scripts/ziwei_patterns.py` (920 lines) — 紫微 24 格局检测: 6 上格 + 8 中格 + 4 副格 + 6 凶格

**New assets**
- `assets/tiaohou.json` — 《穷通宝鉴》调候用神 120 entries (10 干 × 12 月支), 含季节、五行状态、primary/secondary 用神、寒燥分

### Changed

**SKILL.md upgrades**
- Frontmatter description appended activation directive ("即使只提到 ... 也主动调用")
- New 9-step Information Collection Protocol with AskUserQuestion / plain text dispatch
- New Edge Cases dispatch table (10 scenarios: 时辰未知/节气交界/夜子时/闰月/海外/双胞胎/收养 etc.)
- New Closed-Loop Calibration step in Workflow (3-5 已发生 events for user verification)
- New Required Output Fields section enforcing 用神/格局/真太阳时 surface in every BaZi reading

**Script improvements**
- `scripts/utils.py` — added Equation of Time (Spencer formula) to `longitude_correction()`; new `true_solar_time_info()` returns full breakdown with EOT contribution (±16 min seasonal variation)
- `scripts/bazi_calc.py` (448 → 1003 lines) — wired all 35 神煞 (vs 9 before) via `SHENSHA_CATEGORY` dispatch; added 用神/喜神/忌神 selection (扶抑+调候 综合); 月支本气×3/中气×1.5/余气×0.8 weighted 五行; 干支互动 detection (天干五合/地支六合/三合/三会/六冲/六害/三刑); 自动判格 (delegated to bazi_geju); 真太阳时校正 surfaced in output
- `scripts/ziwei_calc.py` (488 → 1041 lines) — added 6 吉星 (左辅右弼文昌文曲天魁天钺), 6 煞曜 (擎羊陀罗火星铃星地空地劫), 9 杂曜 (天马红鸾天喜孤辰寡宿天哭天虚龙池凤阁), 命主/身主 by 年支, 斗君, 自化 detection per 宫干, 大限四化, 流年四化 via `--liu-year`, 借宫 for empty palaces, 14 主星亮度 (庙旺平陷), 24-pattern 格局 detection, **fixed 大限顺逆 bug** for 阴男阳女

**Validation**
- `evals/run_checks.py` — added `qimen_cast` + `liuren_cast` to `check_core_scripts` test matrix; all 4 checks pass

### Stats vs 1.0.0
- Files: 62 (was 51, +11)
- Markdown: 12,627 lines
- Python: 9,148 lines (was 3,825, +138%)
- Total: ~21,775 lines

### License attribution
All algorithms re-derived from public-domain classical Chinese metaphysics sources. No code copied from AGPL or proprietary repos. Inspiration credit to competitive landscape audit (jinchenma94/bazi-skill UX patterns; hhszzzz/taibu architecture concepts; Horace-Maxwell/horosa-skill envelope patterns; ziwei-doushu pattern catalog structure) — interfaces and design patterns only, no source.

---

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
