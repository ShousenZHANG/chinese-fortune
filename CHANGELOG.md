# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.3] — 2026-09-03

Two chart-correctness defects, both about a chart being cast from the wrong
inputs rather than from the wrong rules. Found by a landscape sweep of open
source 命理 engines, datasets and corpora — the sweep found no engine that casts
more accurately than this one, but it did surface an input assumption nothing
here had ever questioned.

### Fixed
- **紫微 闰月 now splits at the fifteenth.** references/02-ziwei-paipan.md:15
  states the mainstream rule — 闰月处理: 十五日前算上月, 十五日后算下月 — but
  ziwei_calc took `abs(lunar.getMonth())`, attributing the whole leap month to
  its base month. 命宫, 身宫, 斗君 and the 辅星 placements all key off the lunar
  month, so a birth in a leap month after the 15th had every one of them a
  palace out of place. 闰四月初十 and 闰四月十六 of 2020 previously returned an
  identical chart (命宫 子 both); they now return 命宫 子 and 命宫 丑. The month
  attribution is stated in `notes` rather than applied silently, matching how
  the qimen 三元 divergence is already handled. Adds `--leap` so a leap month is
  reachable without lunar_python's internal negative-month encoding. 八字 is
  untouched: its 月柱 is 节气-based, so leap months never enter it.

### Added
- **`--timezone`: historical offsets and 夏令时, resolved from tzdata.** A birth
  time is given as it read on the clock, but 时辰 boundaries are defined against
  standard time — and China's clocks have not always been UTC+8. tzdata records
  30 offset changes for Asia/Shanghai between 1900 and 1995, of which **14
  windows sit at UTC+9**: 1919, 1940-1949, and the 夏令时 of **1986-1991**.
  Inside one of those, a clock reading is an hour ahead of standard time, and
  because 时辰 boundaries fall on the hour, anyone born in the hour after a
  boundary was given a 时柱 one position out.

  1988-07-01, clock 07:30 — which is 06:30 standard time, and 07:00 is the
  卯/辰 boundary:

  | | 时柱 | 用神 reasoning |
  |---|---|---|
  | without `--timezone` | 甲辰 | 扶抑与调候一致 |
  | with `--timezone Asia/Shanghai` | **癸卯** | 调候优先, 扶抑次之 |

  紫微 shifts with it: 命宫 寅 becomes 卯 for the same birth.

  No new arithmetic was needed. `longitude_correction` already derives its
  reference meridian as `tz * 15`, so handing it the real offset for that
  instant moves the meridian to 135°E and the existing code subtracts the hour.
  `zoneinfo` is stdlib and `tzdata` is Apache-2.0, so the MIT licence and the
  runtime dependency set are unchanged. Both bazi_calc and ziwei_calc accept
  the flag and fall back to the flat `--tz` without it.

  00-intake.md now carries 夏令时 as an edge case, tells the reader to pass the
  zone rather than hand-subtracting an hour, and to surface the uncertainty
  when a user cannot recall whether the time they reported was 夏令时.

Charts cast without the new flags are byte-identical apart from the added
`timezone` / leap-month keys. Suite 1096 → 1104.

### On the landscape sweep
80 candidates across 8 lanes (八字/紫微/周易 engines, calendrical ground truth,
classical corpora, golden charts, AI-era competitors), 22 verified against
primary sources. Nothing displaced lunar_python or sxtwl. Worth recording so
they are not re-proposed: `china-testing/bazi` (1.5k stars) wraps the same
lunar_python and ships no licence, so it is useless as a differential oracle;
`MingLi-Bench` (2.4k stars) scores predictive accuracy, which this project's
解读纪律 refuses; one 3.8k-star repo advertising machine-readable 古籍原文 turned
out to ship modern paraphrase in pseudo-classical register, ~23 KB of
TypeScript standing in for works it labels at 100,000 characters. The Hong Kong
Observatory 节气 XML matches our own boundary instants exactly but is
non-commercial-only, so it can corroborate by hand and never ship.

## [1.5.2] — 2026-09-03

Defects surfaced by a behavioural evaluation of the skill, then each one
independently reproduced before any fix was written. Two of the nine reported
did not survive that check and are recorded below as not-fixed, with reasons.

### Fixed
- **`lunar_convert` published a 时柱 it invented.** Neither subcommand took an
  hour worth the name — `lunar2solar` had no `--hour` at all and silently built
  the chart at 12:00; `solar2lunar` defaulted to 0, which is indistinguishable
  from a user who genuinely said 子时 — and both still emitted a fully-formed
  `time_in_ganzhi` / `ganzhi.hour`. references/00-intake.md:30 says 时辰未知 →
  时柱缺如, 标注"时柱待补", 不揣测时辰, and :31 — the line directly below — names
  `lunar2solar` as the tool to reach for when only the 农历 date is known. The
  tool prescribed for the missing-data case was inventing the missing data.
  Sweeping the assumed hour across one date moves only those two fields; 日柱,
  28宿 and 节气 are hour-invariant, so suppressing them costs nothing else.
- **`bazi_calc` reported two different 起运 ages for one chart** — `qi_yun`
  said 9, `da_yun[0]` said 10, with nothing explaining the gap. Neither was
  wrong in isolation; the field names hid two different conventions.
  `qi_yun.start_age` held lunar_python's `Yun.getStartYear()`, which is a
  DURATION from birth (9 years 5 months here), with the months truncated away;
  `da_yun[].start_age` held 虚岁. references/01-bazi.md §7.2 adjudicates: 起运 is
  written 6岁4个月 and the bands are anchored to it — 起运6岁 → 6—16、16—26 — and
  all three worked examples (:625, :655, :684) step by 10 from the 起运岁 in
  周岁. **BREAKING: every `da_yun[].start_age` drops by 1.** `qi_yun` now carries
  years / months / days and a rendered text; the 虚岁 figure survives as
  `start_age_xusui` rather than being passed off as 周岁.
- **`shen_sha` verdicts contradicted the reference that qualifies them.**
  assets/shensha.json shipped 十恶大败 as a flat 主大败之时,事业财运均不利, while
  references/19-shensha.md §3.15 says 命理界争议较大,子平派多不采用 and that
  file's principle 6 names 十恶大败 as something that must not induce 恐慌. The
  caveat lived only in a file the engine never reads, so the alarming line was
  what reached the reader — on 10 of 60 day pillars. 魁罡 was missing §3.13's
  两条件 (不喜见财官破格 / 喜见印比助力). Detection was correct in both cases; only
  the wording was wrong.
- **Tarot published a star sign in a field called `element`.** 21 of the 22
  major arcana carry astrology (12 signs + 9 planets) and only 愚者 carries 风.
  references/18-tarot.md §4 gives the four elements to the four MINOR suits and
  gives the majors none, so 巨蟹座 under `element` invited a reader to treat it
  as a peer of 火/水/风/土. Majors now report `element: null` with the
  astrological value under a new `astro` key; minors are untouched.
- **`lines_visual` had no way to be oriented.** It is drawn 上爻-first (correct
  — that is how a hexagram is written) while `lines[]` and `active_lines` number
  初爻=1 from the bottom, so the ○ marker always landed on visual row
  `7 - position` and a 三爻 move rendered on the fourth row from the top. Every
  row is now labelled, as references/04-liuyao.md §3.1 labels its own diagram.
  v1.4.0 had already had to fix a genuinely mirrored 爻位 bug in this same file,
  so the misreading risk was not hypothetical.

### Added
- **Three-pillar mode.** `--hour` is now optional. references/00-intake.md has
  always said 时辰未知 → 仍可排年/月/日柱; 时柱缺如, but `required=True` meant the
  script refused to run, leaving the rule unexecutable through the very tool
  that implements it — in the evaluation an agent had to pass `--hour 12` and
  hand-suppress every contaminated field. Omitting it now drops the hour from
  the pillars dict entirely, so 五行得分, 旺衰, 用神, 格局, 神煞 and 干支互动 count
  six characters instead of eight rather than counting a guess. Output gains
  `hour_known` and `notes`; `four_pillars.hour` becomes `{status: 时柱待补}`.
  Supplying `--hour` is provably unchanged — the snapshot diff for an
  eight-character chart is exactly the two new keys.

### Not fixed, and why
- **解梦 script vs reference "contradiction" — refuted.** 15-jiemeng.md declares
  itself a 解读框架 and the 105-entry asset is the 词条 lexicon; SKILL.md routes
  to both as the 传统 and 心理 halves of one dual reading. Different granularity
  is the design, not a conflict.
- **`--search` returning 0 for 家 / 蟒 — left alone.** Widening the predicate to
  scan interpretation text would take 家 from 0 to 12 matches and 水 from 2 to 6,
  each returning a full entry — multiplying the payload of a script whose whole
  purpose is to cost less than reading the 38 KB asset. 蟒 needs a synonym map or
  a new entry, which is content authoring, not a bug fix.
- **Tarot `--layout` — deferred.** 18-tarot.md §5.2 documents five three-card
  layouts and the script offers only 过去/现在/未来. That is a missing feature,
  not a defect, and it does not make any current reading wrong.

Suite 1093 → 1096.

## [1.5.1] — 2026-09-03

Maintainability release. No behaviour change to any engine — every split and
merge below is locked by a value-level snapshot or an equivalence test.

### Changed
- **No script exceeds the project's own 800-line maximum.** bazi_calc.py
  (1719, 2.1x) split into bazi_tables / bazi_shensha / bazi_strength /
  bazi_geju + a 562-line entry point; ziwei_calc.py (1071) into ziwei_tables /
  ziwei_stars / ziwei_palaces / ziwei_patterns + a 364-line entry point. Both
  cut at the files' existing section banners, so nothing moved relative to its
  neighbours, and both dependency graphs are acyclic. The largest script is now
  qimen_cast.py at 794 lines, and a test keeps it that way.
- **One 时辰 helper instead of five.** ziwei's branch_of_hour, liuren's
  hour_to_zhi, xiaoliuren's hour_branch_from_hour, meihua's shichen_num and
  yijing's shichen_index all carried the same arithmetic with the same 23/0 ->
  子 case. Verified identical across all 24 hours, then pointed at
  utils.hour_branch / hour_branch_index / shichen_number. This is the
  arithmetic huangli got wrong in v1.4.0 — worth having in one place.
- **旬空 and 六冲 to utils.** bazi and liuyao carried identical 旬空 offset
  tables (verified equal across all 60 pillars); 六冲 existed three ways. bazi's
  copy also fell back to 甲子旬 for an impossible offset, silently claiming a
  空亡 that is not there.
- **One version constant instead of four.** utils.__version__ is the single
  source; liuren_cast had its own pinned at 1.0.0 and qimen_cast a hardcoded
  "1.0.0" in its payload, so both had been reporting a version five minors
  stale in every response. build_skill reads utils.py rather than
  regex-scraping bazi_calc.py.

### Removed
- qimen_cast.heaven_plate (46 lines) — called from nowhere. main() computes
  the same rotation inline and, unlike the dead function, handles
  hour_stem == 甲 (甲 遁于六仪), so wiring the function in rather than deleting
  it would have been a regression.
- A duplicate xun_head call in qimen main(), a byte-identical copy of
  utils.jiazi_index, and ziwei's reverse 纳音 keyword table (every 纳音 name
  already ends with its own 五行 character; verified for all 60 pairs).

### Added
- A full-output snapshot for ziwei_calc, added before its split: evals asserts
  only has_keys for that engine, so 命宫/身宫/五行局/星位/四化/大限 values were
  unguarded — the same gap the bazi snapshot closed in v1.4.0.
- Equivalence tests: all five 时辰 wrappers still agree with utils on every
  hour; the 60 pillars still partition into six 旬; every engine echoes
  utils.__version__; no script exceeds 800 lines.

### Kept deliberately
bazi_calc.INLINE_QI_FA was flagged as an unreachable fallback but is NOT
removed: it is unreachable only while assets/shensha.json is present. With the
asset missing it supplies 羊刃/飞刃/天乙贵人, which is the graceful degradation
CONTRIBUTING requires of every script.

Suite 1064 -> 1083, coverage 85.9% -> 87.3%.

## [1.5.0] — 2026-09-03

Context-cost release. What a reading actually loads is roughly halved, without
deleting any content a reader can reach — the material moved behind pointers
or behind a script, and two content bugs surfaced while verifying the moves.

Measured cost per trigger (CJK 1.1 tok/char, ASCII 0.25):

| 触发 | before | after |
|---|---|---|
| 周易 | 27.4k | 8.6k (-69%) |
| 解梦 | 24.7k | 7.3k (-70%) |
| 塔罗 | 14.8k | 8.6k (-42%) |
| 八字 | 21.9k | 14.1k (-36%) |
| 黄历 | 14.4k | 9.2k (-36%) |
| 紫微 | 22.0k | 14.8k (-33%) |

### Fixed
- **爻题 ordering** — positions 1 and 6 emitted 九初 / 九上. Classically the
  ordinal leads at exactly those two positions: 乾 reads 初九 九二 九三 九四
  九五 上九. This string is quoted back to the reader as `active_line_text` on
  every cast, so it was wrong throughout, not only in the new lookup.
- **03-yijing.md 四动 rule** — the prose said 以上爻为主 while the table at the
  end of the same file said 下爻为主. 朱子《易学启蒙·考变占》: 二爻变以上爻为主,
  四爻变以之卦二不变爻占、仍以下爻为主. The prose was wrong.

### Added
- `yijing_cast.py lookup --number N` (卦名/卦辞/大象/六爻辞/白话) and
  `--all`, replacing the reference file the 周易 route used to force-load.
- `jiemeng_lookup.py` — `--symbol` / `--search` / `--categories`. The 解梦
  route previously had no script, so the only way to reach the 105 传统
  readings was to read the whole 38 KB asset.
- `references/00-intake.md` — the collection protocol, 边界情形 table and
  必出字段 list, moved out of the always-loaded router and linked from all
  five personal-data routes so the step-9 在世状态 ethics check stays reachable.
- `references/01-bazi-paipan.md`, `references/02-ziwei-paipan.md` — the manual
  casting procedures, opened only when the script is unavailable or the user
  wants the derivation explained.
- Tests locking progressive disclosure, which run_checks cannot: every
  personal-data route must carry 00-intake.md, no references/ file may be
  unreachable, and no asset may be unread by every script.

### Removed
- `references/64hex-full.md` (43 KB). Its 卦辞 (64/64), 象辞 (64/64) and 爻辞
  (384/384) were identical to `assets/64hex.json`, which the engine already
  loads and prints; a cast needed two or three hexagram blocks and paid for
  all 64. The 六条变爻断例 it also carried are already in 03-yijing.md §八.
- Six assets read by no script and mentioned in no reference, eval or test:
  24jieqi, bagua, ganzhi, wuxing, ziwei_stars, name_shuli (37 KB). Two were
  contradictory second sources — ganzhi.json's 巳 hidden-stem order had drifted
  from utils.HIDDEN_STEMS (order is load-bearing), and name_shuli.json's 吉凶
  labels disagree with name_analyze.SHULI_81 on 22 of 81 numbers.

### Changed
- Workflow step 5 no longer says "read the relevant reference file in full
  (always read 00-foundations.md on first invocation)". Foundations is opened
  for 理论 questions or a missing table; 塔罗/解梦/星座 never needed its
  干支/五行 tables (0, 1 and 2 keyword hits respectively).
- The one-line 免责声明 template is inlined in SKILL.md; 20-disclaimer.md is
  opened when a request touches a red line, shows a crisis signal, or concerns
  a third party's chart. The seven red-line bullets stay in SKILL.md.
- The Data assets table became one line telling Claude not to open assets —
  every value reaches it through a script's JSON.
- SKILL.md 15,491 -> 11,599 bytes.

### Not done (and why)
The planned reference trimming (删「学习路径」/「现代视角」) was dropped after
checking each target: 15-jiemeng.md's 现代心理学视角 is the 心理 half of the
dual reading eval #7 asserts, 09-mianxiang.md's 现代医学警告 is a safety
guardrail, and several others are the cultural/psychological framing
CONTRIBUTING's code of conduct requires. The 学习路径 sections total ~1 KB
spread across four different method files, so they save under 400 tokens on
any single trigger. 03-yijing.md's 六十四卦速查 was also kept — it is now the
only in-document hexagram index, since 64hex-full.md is gone.

## [1.4.1] — 2026-09-02

Gate-hardening release. No behaviour changes to any engine; the release
harness now fails where it previously passed vacuously.

### Fixed
- `check_release_cleanliness` ignored `git ls-files`' exit code, so the
  committed-`.pyc` gate degraded to a loop over an empty list — reporting
  PASS — whenever git failed or the tree was not a worktree.
- `check_interpretive_discipline` guarded SKILL.md with 8 needles but
  `agents/openai.yaml` with a single substring, so four of the five classics
  and both discipline clauses could be stripped from the agent prompt with the
  gate still green. The needle lists are now symmetric constants. This
  immediately surfaced a real gap: openai.yaml carried the clauses only in
  English, so the canonical 凡古籍无据者不妄断 / 禁止套话和迎合 anchors are now
  present in both files.
- `check_unit_tests` crashed inside its own failure path — pytest output that
  is not valid UTF-8 on a CJK console left `proc.stdout` as `None`, so a
  failing test surfaced as the harness's own `TypeError` rather than the
  failure it was meant to report.
- `build_skill.read_version()` fell back to `"0.0.0"` when the VERSION
  constant was absent, and `test_build` always passed `--out`, so the
  version-derived default filename was never exercised. A refactor moving the
  constant would have shipped a misnamed zip with nothing red.

### Added
- **`--help` is now the output schema.** Every CLI's parser carries an epilog
  listing its top-level JSON keys and the error contract. Callers previously
  had no documented way to learn that BaZi emits `four_pillars` (not
  `pillars`), or that 黄历 emits `ji_shi` / `xiong_shi` / `shichen_detail` —
  `four_pillars` appears in zero `.md` or `.yaml` files. Kept in argparse
  rather than a `docs/` file so the schema cannot drift from the CLI it
  documents.
- Tests for the release harness itself, which previously had none.
- A lock on the ANU quantum honesty disclaimer, which could be deleted with
  every check and all 1039 tests still green.
- eval #7 asserted a single CJK character (蛇) in a 38 KB asset; it now
  asserts the dual-reading structure its `expected_output` promises. (The
  obvious 传统/心理 needles were checked against the asset first and do not
  occur — those keys are English.)
- eval #13 locks the qimen 三元 honesty note, which shipped in v1.3.0 with no
  invariant lock unlike every other honesty text in the project.

### Changed
- CI lints the whole repo, not just `scripts/` + `tests/` — `run_checks.py`,
  the release gate itself, was never linted.
- Documentation claims corrected after verifying each against the code:
  `assets/` does NOT hold 1900-2100 fallback tables (no script reads them and
  `require_lunar()` exits 1); `64hex.json` has no 序卦/综卦 fields; SKILL.md's
  闰月 pointer led to a section that never mentions 闰月; CONTRIBUTING still
  said "4 checks" in both language sections; CHANGELOG dated 1.2.0/1.3.0
  2026-07-04 when both commits are 2026-07-17; the READMEs claimed every
  method has a `references/` doc, which 随机寻访 does not.

Suite 1039 → 1064, coverage floor unchanged.

## [1.4.0] — 2026-09-02

Correctness release. Two engines were returning wrong answers with full
confidence; both are fixed and locked by oracles that assert values, not
shapes. **Readings produced by v1.3.0 and earlier should be re-run.**

### Fixed
- **爻位序 mirrored in every hexagram cast (周易 / 梅花 / 六爻)** — `BAGUA`
  encodes each trigram top-to-bottom, so 初爻 is bit 2, but the writer
  (`from_numbers` / `build_lines`) and the reader (`lines_to_trigrams`) both
  iterated bit 0 as 初爻. Being wrong on both sides made the round trip
  self-consistent: the hexagram NAME was always right, so no test caught it,
  while everything downstream was mirrored. Over all 384 (上卦, 下卦, 动爻)
  combinations: 每爻阴阳 wrong in 288, **变卦 wrong in 256** (every cast whose
  changing line was 1, 3, 4 or 6), 互卦 wrong in 360; `liuyao_cast` coin casts
  resolved 48 of 64 hexagrams to the wrong 卦名 and 纳甲. Output contradicted
  itself — a line drawn 阳 carried a 六 line text. The tables were already
  right (`assets/64hex.json` `lines[].type` agrees 64/64, and
  `references/64hex-full.md` numbers 初爻 upward), so only the three call
  sites changed.
  ERRATUM: `numbers --upper 3 --lower 5 --change 1` gave 火水未济64; correct is
  火天大有14. `coins --seed 42` gave 雷火丰55; correct is 山火贲22.
- **黄历 子时 row carried the next day's 时柱** — the 子 block was sampled at
  23:30 of the queried day, which under the 晚子时 (sect-2) convention this
  project uses belongs to the NEXT day's 子 时柱. The row reported that day's
  干支/天神/吉凶/冲煞 while the same JSON's `ganzhi.day` and `chong_sha`
  described the queried day, and the 12 rows were not a contiguous 六十甲子
  run. For 2026-06-24 (日柱 己巳, 五鼠遁 甲己起甲子) the row printed 丙子 and
  its verdict flipped 凶 → 吉. The v1.3.0 regression test asserted only the
  干支 BRANCH against the 时辰 label, which the wrong pillar satisfied.
- **`--help` unusable on non-UTF-8 stdio** — 14 of the 15 CLIs carry Chinese
  argparse help. `json_print` forced UTF-8, but argparse writes `--help` long
  before it, so `--help` exited 1 with no output on a non-CJK console and
  emitted undecodable bytes when stdout was a pipe — which is how SKILL.md
  documents invoking them. `utils.ensure_utf8_stdio()` now runs before
  `parse_args` in every CLI.
- **`zodiac_compat` exited 0 while emitting an error payload** — the only one
  of the 13 engines to do so, so callers checking the exit code read a failure
  as success.
- **`huangli` `tai_shen_fang_wei.desc` removed** — it called
  `getDayPositionTaiDesc`, which `lunar_python` does not define, so the key
  was `None` on every date. Not repointed at `getDayPositionTaiSuiDesc`: 太岁
  is not 胎神.

### Added
- `--datetime` (ISO) on `meihua_cast` (top level — 当下月令 feeds 体用旺衰 for
  all three subcommands, not just `time`) and on `yijing_cast time`. Defaults
  to `now()`, so behaviour is unchanged. `ti_yong.body_strength` drifted with
  the real calendar month and was therefore entirely untested; it now has a
  golden.
- Oracles that assert values rather than shapes: all 64 hexagrams' line values
  against `assets/64hex.json`; 黄历 时辰 stems against 五鼠遁 plus a contiguous
  60-cycle check; a full-output 八字 snapshot locking
  `shen_sha`/`yong_shen`/`ge_ju`/`interactions`; `--help` under `cp1252` for
  every CLI; `zodiac_compat` error exit codes. Shared `run_cli()` in
  `conftest.py` asserts the exit code, so a status regression cannot pass
  silently. Suite 1013 → 1039, coverage 84.8% → 85.9%.

### Changed
- **BREAKING** — `shichen_detail` / `ji_shi` / `xiong_shi` now hold **13**
  entries, not 12: 子时 is split into `早子 00:00-01:00` (queried day's 日干)
  and `夜子 23:00-24:00` (next day's), so no row spans two 时柱. Rows are in
  clock order, so index 0 is `00:00-01:00` and `hour_range` `23:00-01:00` no
  longer appears. Each row gains a `branch` key, since `shichen` is now
  早子/夜子 for the two 子 rows.
- `evals.json` #2 golden corrected to 山火贲22 (was the mirrored 雷火丰55).

## [1.3.0] — 2026-07-17

Maintenance + correctness sweep: traditional 时辰 boundaries, CI runner
deadline, qimen school-note, subcommand coverage, README refresh.

### Fixed
- **huangli 时辰 boundaries (correctness)** — `shichen_detail` used even clock
  blocks (00-02, 02-04 …) that straddle two traditional 时辰, mislabeling the
  second half of every block. Now uses the classical odd-start convention
  (子 23-01, 丑 01-03 … 亥 21-23) with a `shichen` label per block; each
  block's 干支 branch now provably equals its 时辰 (regression-tested).
  NOTE: `hour_range` values in output changed — hence the minor version bump.

### Added
- Qimen 三元 school note: `determine_ju` documents the 简化日数法 vs 拆补置闰法
  divergence (±1 元 near 节气 edges) in both the script docstring and
  references/06-qimen.md — honest approximation, no unfounded claims.
- `tests/test_subcommands.py` (+6, suite 1007 → 1013; coverage 82.5 → 84.8%):
  hand-verified yijing numbers golden (3/5 → 火风鼎50, 变 火水未济), yijing
  text / meihua name determinism, xiaoliuren solar golden + 子时 boundary,
  huangli traditional-boundary regression lock.

### Changed
- CI actions bumped for the GitHub Node20 runner removal (2026-09-16):
  checkout v4→v5, setup-python v5→v6, upload-artifact v4→v5.
- READMEs (中/EN): badges + metrics refreshed (1013 tests / 85% coverage /
  15 engines / 7-check harness), new feature bullets (解读纪律 CI-lock,
  optional quantum entropy, exploration tool), methods table gains the
  exploration row.

## [1.2.0] — 2026-07-17

Interpretive-discipline release: classical sources become the binding rule.

### Added
- **SKILL.md「解读纪律 (Interpretive Discipline) — 古籍为纲」** — BaZi judgments
  must anchor in the five classics with an explicit precedence order:
  《子平真诠》(格局) →《滴天髓》(强弱气势) →《穷通宝鉴》(调候, already shipped as
  assets/tiaohou.json) →《三命通会》(神煞杂断) →《渊海子平》(十神六亲). Hard
  rules: 凡古籍无据者不妄断 (label folk-lore/school views as such or stay
  silent); 禁止套话和迎合 (no platitudes, no flattery-softened verdicts); only
  the strongest-evidence, most-verifiable conclusions (chart-anchored, 应期
  falsifiable, classic-citable); 学理/民俗 layered; explicit conflict-resolution
  order (调候 vs 格局, classics vs modern schools).
- `check_interpretive_discipline` in evals/run_checks.py (harness now 7 checks)
  — CI-locks the discipline text in SKILL.md and the classics anchor in
  agents/openai.yaml so it cannot silently regress.
- references/01-bazi.md header now carries the binding 论断依据 note.
- agents/openai.yaml default_prompt extended with the same discipline for
  OpenAI-runtime consumers.

### Changed
- evals/run_checks.py: ruff-clean (import order, capture_output).

## [1.1.9] — 2026-05-31

Randonautica-inspired exploration tool (honest, no pseudoscience).

### Added
- `scripts/explore_cast.py` — 今日随机寻访点: QRNG (reuses `entropy.py`) →
  uniform random points in a radius → dependency-free grid-density anomaly
  (attractor / void / power / blindspot, all clamped inside the circular
  radius) → bearing + distance + 16-point compass, cross-referenced with
  today's 黄历 吉神方位 (财神/喜神/福神). Carries a safety block and an explicit
  disclaimer: it is a randomized walk prompt, NOT a prediction and NOT a
  mind-matter-interaction (MMI) device — intention is recorded, never biases
  the entropy. SKILL.md routes 随机寻访/探索 to it.
- `tests/test_explore.py` (+12, suite 989 → 1001) — within-radius for all 4
  modes, seed determinism, geometry (haversine/bearing/compass), input
  validation, 黄历 alignment, safety/disclaimer presence.

### Note
Borrowed only the *legitimate* tech from Randonautica (QRNG + spatial density
anomaly + intention UX + safety). The "intention biases quantum RNG / z-score =
psi" MMI claim is explicitly rejected, consistent with this project's stance
that divination efficacy is not a physically-measurable quantity.

## [1.1.8] — 2026-05-31

Optional quantum entropy source for divination casts.

### Added
- `scripts/entropy.py` — pluggable cast entropy: `seed` (deterministic),
  `system` (OS CSPRNG, default), or `quantum` (`QuantumRandom`, physical
  randomness from ANU quantum-vacuum noise, gracefully degrading to
  `os.urandom` with a `degraded` flag if the source is unreachable).
- `--entropy {system,quantum}` on `yijing_cast`, `liuyao_cast`, `tarot_draw`;
  output carries an honest `entropy` provenance block.
- `tests/test_entropy.py` (+12, suite 977 → 989) — source selection,
  forced-offline degrade, `getrandbits`/`shuffle`/`choice` correctness, and
  script wiring. Network-free (the quantum path is tested via the fallback).

### Note
The `quantum` source is offered as a *physically-true randomness* option only.
It does **not** make a reading more accurate — hexagram/card outcomes are
uniform regardless of entropy source, and divination accuracy has no physical
dependence on where the bits come from. Output always labels the source so the
distinction stays transparent. (Relativity/quantum mechanics cannot improve
divination accuracy; the calendar layer's solar-term precision already uses
relativistic time scales via lunar_python's VSOP87 port, to < 1 s.)

## [1.1.6] — 2026-05-31

Independent-verification + quality-gate release. Cross-checks the calendar
engine against a second codebase and wires lint + coverage gates into CI.

### Added
- **Differential tests vs `sxtwl`** (`tests/test_differential.py`) — an
  INDEPENDENT engine (C++ port of 寿星天文历). Cross-checks 日柱 over a 447-date
  grid (1920-2080) and 年/月柱 on all non-节气 days; both engines agree. This
  closes the "self-snapshot" gap (the rest of the suite validated bazi_calc
  against the very library it wraps). Also asserts the 立春 year-pillar switch
  is time-aware (flips at the exact instant, verified more precise than sxtwl's
  date-level API).
- **lint + coverage gates** — `ruff` (config in `pyproject.toml`) and
  subprocess-tracked `coverage` with `fail_under = 80` (real total **82%**;
  subprocess tracking via `COVERAGE_PROCESS_START` since most tests drive the
  CLIs out-of-process). Both wired into CI.
- Tests for `lunar_convert` (公历↔农历 round-trip) and zodiac info/year/taisui
  sub-commands (suite 94 → 977 with the differential grid).

### Changed
- Cleaned all `ruff` findings across 16 scripts: removed unused imports/vars,
  deduped 4 repeated keys in the name 笔画 fallback (same-value, no behaviour
  change), moved module imports to top, renamed ambiguous `l`, added explicit
  `zip(strict=...)`. `ziwei_calc` now surfaces `true_solar_time_applied`.

## [1.1.5] — 2026-05-31

Bug-fix release — three silent-wrong defects found by an adversarial line-by-line
audit, plus value-level test coverage to lock them.

### Fixed
- **塔罗 (HIGH)** — `tarot_draw.load_deck` gated on `isinstance(deck, list)`, but
  the asset ships as `{major_arcana, minor_arcana}` (dict), so the curated 78-card
  deck **never loaded** and every reading silently used placeholder text
  ("…第N阶: 见详细解读"). Added `_flatten_asset_deck`; readings now carry the real
  per-card 正/逆位 meanings.
- **黄历 吉时/凶时 (HIGH)** — classification used "时辰 has any 宜", which is true for
  all 12, so output was always 12 吉 / 0 凶 (meaningless). Now derived from the
  时辰 黄道/黑道 (`getTimeTianShenLuck`): a real 吉/凶 split. Removed dead
  `getTimes()` / `getTimeXun()` calls.
- **紫微 真太阳时 (HIGH)** — `--tz`/`--longitude` were accepted but ignored, so a
  user-supplied longitude produced an uncorrected chart (silent-wrong near 子时).
  Now wired through `longitude_correction` (with day roll-over) — **opt-in**: only
  applied when a non-default longitude/tz is given, so 时辰-granular charts on the
  default meridian are unchanged (no regression).
- **生肖 (LOW)** — same-sign pairs (e.g. 鼠-鼠) were mis-flagged 三合 because
  `da in group and db in group` is true when `da == db`. Now requires distinct
  branches.

### Added
- +5 tests (suite 94 → 99): value-golden assertions for 紫微 命宫/身宫/局,
  奇门 阳遁8局, 大六壬 丙午日; regression locks for the tarot asset, huangli 黄黑道
  吉凶 split, ziwei longitude opt-in, same-sign 三合; replaced a tautological
  meihua `relation` truthy-check with a valid-relation assertion.

## [1.1.4] — 2026-05-31

Continuous integration — closes the last engineering gap found in a 4-repo
competitor scan (only the off-topic Master-skill had CI; no fortune skill did).

### Added
- `.github/workflows/ci.yml` — on every push / PR to main: install deps,
  run the 94-test pytest suite, the `run_checks.py` release harness, and
  `build_skill.py`, on Python 3.11 + 3.12; uploads the built skill zip as a
  CI artifact. Concurrency-cancelled, pip-cached, least-privilege permissions.
- `requirements-dev.txt` — dev/CI deps (runtime + pytest).
- CI / tests / license badges on both READMEs.

## [1.1.3] — 2026-05-31

Packaging + bilingual-install pass — one-command distributable for Claude
Code, Claude.ai upload, and OpenAI/other runtimes.

### Added
- `scripts/build_skill.py` — self-validating, deterministic packager that
  emits `dist/chinese-fortune-v<version>.zip`. Whitelists runtime files
  (SKILL.md, references/, scripts/ runtime, assets/, agents/, READMEs,
  LICENSE), excludes all dev/test cruft (tests/, evals/, __pycache__, .bak,
  _competitors, the builder itself), nests under `chinese-fortune/`, and
  aborts on bad frontmatter / over-long description / non-compiling script.
- `tests/test_build.py` (+4, suite now 94) — asserts SKILL.md at package
  root, runtime files present, ZERO dev-cruft leakage, and that a freshly
  extracted package runs standalone.

### Changed
- README.md / README.zh.md: replaced the single `cp -r` step with a 3-target
  **Install** table (Claude Code unzip · Claude.ai upload · OpenAI adapter)
  plus the `build_skill.py` one-liner. Stays concise.

## [1.1.2] — 2026-05-31

Test-coverage + agent-hardening pass, informed by a 2026 market scan of
best-in-class 命理 engines (cantian-ai/bazi-mcp, 6tail/lunar-python &
tyme4ts, sxwnl, SylarLong/iztro) and academic evals (Celebrity-50, BaziQA).

### Added
- **Engine test coverage** (`tests/test_engines.py`, +15 tests, suite now 90):
  contract + determinism tests for the 8 previously-untested engines (周易,
  梅花, 六爻, 小六壬, 生肖合婚, 奇门, 大六壬, 黄历) plus 紫微 structure, and a
  table-free **五鼠遁 hour-stem invariant** verified across 5 charts. Seeded
  casts asserted reproducible; 六冲/三合 compatibility asserted by score.

### Changed
- `agents/openai.yaml` default_prompt hardened: restates script-first
  computation, references/ grounding, disclaimer, and the red-line refusals —
  so the OpenAI adapter carries the safety layer even before SKILL.md loads.

### Notes
- **Precision re-classified as already-solved.** Market scan confirmed
  lunar_python's 节气 engine is a port of sxwnl's `ShouXingUtil` (VSOP87,
  mean 节气 error < 1s) — i.e. already at the top-tier ephemeris bar. The
  earlier "no high-precision ephemeris" concern was a false deduction; the
  only remaining numeric approximation (Spencer EOT, ±20s) is negligible
  against 2-hour 时辰 buckets.
- **Honest ceiling.** Remaining depth gaps (per-method golden corpus, iztro
  紫微 cross-check, LLM-judge interpretation eval) require validated external
  datasets and are intentionally not fabricated. Divination *truth* is not
  scientifically validatable; engine *correctness* is — and that is what the
  test suite now locks.

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
