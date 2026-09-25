# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

历史条目与早期标签存在缺漏，保留原记录，不追溯补造发布。旧测试数量和成本只描述当时版本；v4 已替换被发现无效的奇门、六爻检查，不能将旧通过率视为原典正确率。

## [4.7.0] — 戊癸日不再误拦截，首句直接回答

### 戊、癸日的窗口被错拦

截路空亡在戊、癸日有两说：《渊海子平》作子丑（`yuanhai:c048:p0003`），《三命通会》作戌亥（`sanming:c003:p0035`），判据分不出高下，按 [裁决顺序](references/26-precedence.md) 并列。v4.6.0 只要窗口落在戊、癸日就判为冲突，不看窗口碰没碰到这两说点名的时辰。实测：候选 2026-09-21 08:00–12:00（戊戌日，覆盖辰巳午）加 09-22、偏好「尽早」，输出说「涉及另一条忌时或版本分歧，目前不能把它当作整体合适的时间来推荐」。两说都不忌辰巳午，这句是假话，并且波及所有戊、癸日，约占五分之一的日子。

- `rank_candidates` 的每个窗口新增 `contested_hours_in_window`：窗口实际覆盖、且某一说点名的时辰，带所据 `readings` 与 `segment_start`／`segment_end`。`unresolved_hour_rules` 保留，只作信息用。
- 实际选择、二次筛查、`clause_conflict` 阻断和白话正文改读 `contested_hours_in_window`。上面那个用例现在给出首选 09-21、备选 09-22。
- `forbidden_hours_in_window` 各项也带 `segment_start`／`segment_end`，按时间顺序排列。

### 首句直接回答

- `fortune_reading.py --markdown` 的首句不再查固定句子表，而是用候选、日期和条款拼出来；只有需要用户补输入的状态沿用固定问句。按问句类型切首句：是否题以「可以：」「不行。」「不建议。」开头。
- 被条款排除的候选在首句点名，例如「oct14 需要避开：覆盖到辛酉日，是秋季的天转日，《渊海子平》说这天忌出行。」冲突时给出窗口名和具体钟点。首选所在窗口有忌时，首句加一句「别把时间挪进 11:41–13:00（午时）……」。
- 按档期偏好排出的首选，首句写明「这是按档期排的，不是古法排序」。
- 删去排除行上自相矛盾的「单看日期未触犯一条规则」，也删去与多数问题无关的「收到钱或录用」。未决日只在窗口碰到争议时辰时才提。「可继续补查约5分钟」只在 `evidence_needed`、`screened_only` 两种状态出现。按日问运势时，首句直说本库现有条款里没有按日给个人算整体吉凶这一类。

### 不替用户编分钟

用户没给时间偏好时，首选的 start 只是窗口边界。现在只有整个窗口都通过筛查，首选才带 `flexible_start`（可开始的时刻区间）；窗口里有忌时或争议时辰时不带它，因为晚一点开始可能正好落进忌时。

### 找回被删掉的直答规则

a9b291f 把 `references/27-direct-answer.md` 从 133 行删到 54 行，首句表、限制句判据和禁用词表一并删掉；同一提交把守这几张表的 eval-26 针头改写成新文案，所以门禁没响。现已在新内容旁恢复「首句按问句类型切」「限制句判据」「禁用词」（甲类、乙类、不许删）与「发出前核对」，eval-26 补回针头并用 `needle_note` 说明经过。

### 黄历不再替用户裁决

- 建除与通书宜忌字面冲突时，旧提示写「通书结论已把神煞/宿/干支一并权衡」「遇冲突以 yi/ji 为准」。两句都没有出处，已删除；现在只说两者是不同体系，本工具不裁决。`yi_ji_source` 同样改为如实描述：`lunar_python` 按月干支与日干支查内置表。
- 新增 `clause_conflicts`：天地转杀日里，通书表列为宜、而条款原文点名为「最忌」的事项，带 `passage_id`。只标原文原样出现的词：2026-10-14 辛酉标出嫁娶，不标动土。普通日子为 `[]`。

### 其他

- 六爻用神提示新增 `yongshen_hint_source`：有出处的行带 `passage_id` 与原文短句，没有的明说没有。新增「面试」，依《增删卜易·用神章》「占功名、官府……皆以官鬼爻爲用神」（`zengshan:c008:p0001`）；面试对应功名属现代类比。
- `bazi_reading.py --markdown` 首句改为回应问题并给出月令格局的核查结果，不再以四柱串开头；十神名称首次出现时用生克关系解释。
- 发行包不再带 `scripts/requirements-dev.txt`：该文件首行写着「不进运行包」，此前却一直随包发布。门禁改为从 `SCRIPT_EXCLUDE` 推导。
- `fortune_reading.py` 的白话渲染移出输入错误的 `except`：渲染阶段的 KeyError 是缺陷，不能再报成「目前还算不了这一部分」。
- 删除无人调用的 `utils.parse_datetime_arg`。
- 新增手动触发的 `.github/workflows/release.yml`：按 [发布流程](docs/RELEASE-PROCESS.md) 把一次成功的 main CI 产物原样发布，核对 run 身份、来源与校验和，拒绝覆盖已有标签，先草稿后发布，并逐字节核对 GitHub 实际提供的附件。门禁覆盖全部工作流的 Actions 固定版本。

### 发布记录缺口

v4.5.0 合入 main 后没有打 tag，也没有发 GitHub Release。按本文件开头「不追溯补造发布」的惯例，不补打 tag，在此如实记录。新增门禁：4.3.0 之后每个已发布版本都须有 tag，允许清单只有 4.5.0 并注明原因。

**输出形态变化**：新增 `contested_hours_in_window`、`flexible_start`、`clause_conflicts`、`yongshen_hint_source`，首句文案改变，故取 minor 版本号。

## [4.6.0] — 条件判断与前瞻验证

- 解读前固定主方法和范围；逐条核对个人条件、例外和时间粒度，未解决的分歧不合并成肯定答案。
- 新增用户授权的本机外部验证记录：冻结事前判断、确认结果、更正历史、删除及同方法版本事件分组统计。
- 同时披露回答覆盖率、结果确认覆盖率及删除数量；记录机制不代表现实预测准确率已获验证。

## [4.5.0] — 通用场景与自然白话

- 通用事项与意图路由；依据现实偏好给出明确日期、时段和时区，独立披露个人古法排名缺口。
- 修复未知立春出生时辰崩溃、多人优先级绕过、通用忌日筛选被表述成整体个人推荐。
- 出生范围逐分钟核对共同盘面；灵活出行窗口保留能容纳完整事件的子窗口。
- 结构化调候查询、随段落传递的影像异文、独立简繁映射校验。
- 5分钟研究会话与外部候选资料库，保存真实检索记录，复核不自动注册算法。
- 统一自然白话回答与证据状态，更新能力说明及完整任务测试。

## [4.4.0]

### 简体查询不再被静默漏掉

检索把库内繁体正文与用户查询折到同一形再匹配，而这个折叠表原先是两条手写字符串——没人想到的字就检索不到。实测：`聋哑` 零命中，`聾啞` 26 条；`痈` 1 条，`癰` 5 条；`肿` 3 条，`腫` 5 条。

后果不止是少召回。**空结果正是本技能宣布「古籍没有这条」时的依据**，而漏字造成的空和真的没有，输出一模一样——`聋哑` 与 `染发` 返回同一个信封。于是一个有二十多条段落的主题，可能被答成古籍从未提及。

- 新增 `scripts/build_han_variants.py`（维护工具，不进运行包，依赖见 `scripts/requirements-dev.txt`）：离线遍历 `knowledge/` 全部汉字，用 opencc 生成 `assets/han-variants.json`。当前 6276 字、1577 条折叠。运行时只读这份 JSON，发行包依赖仍是 `lunar_python` 与 `tzdata` 两个。
- `classical_search.normalized` 改读该表，保留六条手写别名作为库外字的兜底。返回的正文与引文仍是各版本原字，折叠只作用于匹配键。
- 新增门禁：库内每个汉字都必须能从它的简体形检索到。删掉表里任意一条折叠，`tests/test_classical_library.py` 变红（已实测）。加书后跑 `python scripts/build_han_variants.py`，`--check` 只比对不写文件。

### 零命中现在带着自己的依据

`search_with_scope()` 与 CLI 的检索响应新增三个键，命中与否形状一致：

- `searched` —— 读了哪 13 部书、多少章、多少段（当前 535 章 / 18982 段），以及折叠表的位置
- `normalized_query` —— 实际用于匹配的词形
- `total_matches` —— 命中总数，区别于 `limit` 截断后的 `results`

`references/27-direct-answer.md` 例三要求层 2 写「查了 X、Y、Z，零命中」；在此之前工具层没有任何字段支撑这句话。`search_classics()` 签名与返回不变。

### 其他

- `27-direct-answer.md` 配色一节原先让模型调 `fortune_ranking.climate_colors(日主, 月支)`，而该模块没有命令行入口，照做必然失败。改为走 `classical_search.py --book qiongtong`，并写明没有任何命令会直接给出「该买什么颜色」——链条第三段无出处这件事本来就写在同一节。
- `build_skill.py` 的 `SCRIPT_EXCLUDE` 成为「哪些是维护工具」的唯一清单；`test_cli_contract`、`test_harness_gates` 改为从它派生豁免，不再各自维护一份。三份副本已经漂开过，新增工具时三处都要改才不报错。

## [4.3.0]

### 修复 v4.2.0 排名的六处阻断缺陷

一轮对抗式审计（七个维度并行核查，每条发现再由独立 agent 复现推翻）确认 v4.2.0 新增的排名在面向人的路径上是坏的。全量 2982 项测试当时全绿，一条都没拦住；下列每条都补了会红的用例。

- `render_answer` 的说明表从未加入排名引入的两个状态，`main()` 的 `except KeyError` 又把崩溃印成「目前还算不了这一部分」并 exit 1。唯一 `rule_based` 的场景一旦真排出结果，白话输出必然失败，而 JSON 输出正常——所以表面上看不出来。现补 `ranked`、`tied_no_clause_separates`、`excluded_by_clause` 三段文案，并在状态缺文案时直接抛错，不再伪装成算不出来。
- 候选被条款全部排除时，`recommendation` 停在初值 `evidence_needed`，输出反过来说「核实的条款还不足以断定吉凶」。新增 `excluded_by_clause` 状态：条款给了答案就说答案。
- 跨日窗口只按第一段日柱判忌日与季节，忌时却遍历全窗，口径自相矛盾。2026-10-13 20:00 出发、10-14 14:00 落地的窗口有八成时长在辛酉（秋天转），实测未被排除并给出「可以走」。现逐日判忌，任一日命中即整窗排除；忌时按各时辰**所在日**的日干取表。
- 一个候选被占用时段切成两段窗口后与自己并列，`tied` 里出现两次同一个 id、首选被置空。`ties` 改按候选 id 去重计数。
- `evals.json` 的 `file_contains` 断言全仓库没有执行器——`fc5c255` 删除 `evals/run_checks.py` 迁入 pytest 时只搬了 `script` 分支，且用过滤而非报错处理未知类型，八条断言静默掉队、其中七个针头随文档改写失效。现补 `test_reference_goldens_still_contain_their_required_text`，并加一条门禁：出现没有 runner 的断言类型直接失败。三条失效针头改钉当前文档实际承诺的行为。
- 截路空亡戊癸日的裁决算错。`26-precedence.md` 第三层「自洽者胜」据「戊癸日五鼠遁起壬子，子时壬子、丑时癸丑」判归《渊海子平》的子丑——推演只数到丑时。同一遁到戌亥又得壬戌、癸亥，《三命通会》的戌亥同样满足「二时上俱遇壬癸为水」；十干里只有戊、癸有第二组，两书恰恰只在这一格分歧。判据分不出来，按本篇「判不出来的，回到列分歧」：`jielu_kongwang('戊'|'癸')` 改为 `resolved: false` 并列两说，不产出忌时、不进 tier 计算。第三层因此暂无落地实例。

### 第二轮：修复第一轮修复自己带进来的问题

第一批改完后又跑了一轮对抗复核（三个视角并行，每条发现再由独立 agent 复现推翻），确认 17 条。第一批在一处只修了一半，另有几处是新代码引入的。

- **逐日判忌只修了日柱，季节那一半照旧取第一段。** 节气可以在日内交接，同一日干支因此可能横跨两个月、两个季节。实测 2034-02-04 辛卯（立春 05:41）：窗口 03:00 起判为冬（放行），06:00 起判为春（辛卯为春地转，排除）——同一天、相反结论，由窗口起点决定。循环键改为 `(day, month)` 对，任一段命中即整窗排除。
- **一个候选同时有清白窗口和被排除窗口时仍被选为首选。** 输出一句「就定 trip：trip 覆盖的日子命中忌日，trip 覆盖的庚申日没有」，同一份结果里 `judgment` 已是 `excluded_by_clause`。幸存者现先剔除出现在 `excluded` 里的 id。这条是第一批引入的：改动前它是一次可见的崩溃，补上文案后变成一句自信的错话。
- **新写的白话把乙类词「两书相反」写进摘要段**，被同一批刚收紧的 `27-direct-answer.md` 和刚修好的 hook 当场拦下。改写措辞，并新增一条测试：五种窗口的摘要段都不得含任何乙类词——把这条规则从仓库外的 hook 搬进仓库内的门禁。
- **摘要宣布两书分歧，两说与出处却一个字都没渲染**，违反本篇「输家条款那一行不许删」。新增 `_clause_evidence`：层 2 逐条列出排除依据、忌时推演、以及未决日的两说与各自 `passage_id`。
- **给出排名的白话里没有任何出处**，违反自检表「排名有没有 passage_id？没有就不许排」。同一块层 2 现在总是带出裁决表版本与条款段落 ID，即使没有候选被排除。
- **「你只给了这一个候选」在其余候选被档期刷掉时是假话**——档期不可用的候选根本不进排名，代码分不开「只有一个」和「其余排不下」。现按 `candidate_comparison` 里 `available=False` 的条数分两种措辞。
- **`JIELU_HOURS` 有四行没有任何测试锁住**：把辛日改成卯辰，3000 项全绿，而随条输出的五鼠遁推演会照错表现算出一句自相矛盾的伪出处。新增测试用独立重算的判据逐干比对，并断言推演里写到的每个时辰确实落在壬癸上。
- 忌时按 Unicode 码位排序，卯时排在寅时之前。改为依 `pillars` 的时间顺序，不再排序。
- 本轮改动自己造成 `26-precedence.md` 行号前移，留下六处指向新内容的「第 47 行」，其中一处随 JSON 发给调用方。跨篇引用全部改为引原句。

十二条变异（把每个修复逐一改回去）现在全部被测试捕获；改动前其中四条可以带着全绿出厂。

### 出处与输出形态

- 截路空亡原先每条都引 `yuanhai:c048:p0004`，但该段只举甲己见申酉一例、后接「余皆仿此」，读者回查某干无从核对。现随条附本干的五鼠遁推演；戊癸两说各自带自己的段落 ID（`yuanhai:c048:p0003`、`sanming:c003:p0035`）。
- tier 的 `sources[]` 只留真正决定 tier 的天地转杀；截路空亡移入 `context_sources`，它是层 2 的时辰注，不是 tier 依据。
- 删除 `hour_clear`——它在「没有条款能分高下」的结论旁边递一份二选一短名单，正是本篇禁止的无授权排序。层 2 叙述用 `forbidden_hours_in_window`。
- **输出形态变化**：`forbidden_hours_in_window` 由分支名列表改为带 `day_ganzhi`／`hour_branch`／`passage_id`／`derivation` 的记录列表；新增 `days`、`unresolved_hour_rules`、`context_sources`；`recommendation.status` 新增一个取值。故取 minor 版本号而非 patch。

### 文档

- `26-precedence.md`：第三层的实例改写为「本层目前没有已落地的实例」并说明为何被推翻；戊癸分歧移入未决表，附完整十二时推演。
- `27-direct-answer.md`：乙类判据由「前三行」改为「摘要段（首个空行之前）」，与两层结构对齐；乙类表去掉与「保留（不许删）」栏重复的未决／待核／前提不成立／另说，补入 `passage_id`、`precedence_version` 并说明与自检表不冲突；甲类表标明带通配的一条走正则；修正一处指错的跨篇行号引用；说明 Stop hook 不随本包发布，且曾因读错输入通道而长期空转。

## [4.2.0]

### 条款冲突裁决与有出处的候选排名

- 新增 `references/26-precedence.md`：同一体系内两条条款相反时的裁决顺序（类型优先 → 同体系书序 → 自洽者胜），带 `precedence-v1` 版本号。跨体系、跨方法仍列分歧不排序；输家条款必须在层 2 保留一行。已知未决分歧列表随实测增补。
- 新增 `scripts/fortune_ranking.py`：出行场景的候选排名。层级为布尔条件，不含权重；每个 tier 必须带可回查的 `passage_id`。天地转杀按季节排除忌日，截路空亡给出忌时并保留两书分歧。冲生肖等无条款支撑的民俗项标 `passage_id: null`，只作背景，不进 tier。
- `fortune_rules.py` 的 `SCENARIOS` 增加第四列 ranking 状态；`travel` 转为 `rule_based` 并声明 `precedence_version` 与 `ranking_reference`，其余十五个场景保持 `not_implemented`。门禁改为「已实现排名必须声明裁决表版本」，同时继续锁死协纪辨方书卷33/34 不得成为面试排名依据。

### 直接回答

- 新增 `references/27-direct-answer.md`：摘要层的首行规则（按问句类型给结论／动作／是否）、三段模板、甲类禁用词与乙类限位词、限制句判据（换一题还成立即套话）。本题独有的限制、输家条款、前提不成立的说明明确列为不可删。
- `22-output-contract.md` 第 4 节与第 47 行、`24-personalized-forecast.md` 排名政策行、`25-classical-research.md` 取舍句、`SKILL.md` 工作流第 1 步分别接入新篇。

### 验证

- 新增 `tests/test_ranking.py` 17 项（条目发布时写作 11 项，是同版本第二个提交又加了 6 项而未回改）：引文可回查且含所引字句、天地转杀只命中当季两日、截路空亡为时辰规则、戊癸分歧必须携带、冲生肖不得带 passage_id、未映射场景拒绝借用条款、排名须声明裁决表版本。
- 回归用例 `test_september_window_has_no_clause_ordering` 固化一次实测纠错：2026-09-11 至 09-30 的出行窗口在条款下全部并列、零排除；此前按黄历宜忌排出的首选属无授权排名。

仅新增与文档接线，未改动既有算法、知识库与输出 schema。

## [4.1.0] - 2026-09-12

- 新增13部固定转录材料与个人时段流程：当前取时、出生与目标分别计算、独立档案和白话说明。
- 连续行程支持2–8件事、跨城时区和显式交通准备时间，共用一次出生计算；返回可行组合，不包装成命理最优。
- 完整个人日时排名、关键异文及部分专项条款仍未完成；版本号不代表这些能力已经开放。

### 奇门原例修正与候选时段接入

- 默认输出《元灵经》已核地盘、值符和值使；修正天禽加兑及天任入中，旧全盘仅显式兼容调用。
- 面试、考试候选自动分段核对时局和本人年干；保留中气、日界与夏令时变化，未补齐的条件不排名。
- 删除错误的固定“天芮天禽同宫”说明，README、技能入口和方法规格同步。

## [Unreleased]

- 候选档期逐段关联个人盘面，计算完整事件的最早／最晚可开始范围；覆盖跨时辰与夏令时实际时长，重叠窗口合并，只细算可行档期。
- 古籍检索补齐7组远处共用禁忌并校验哈希，增加同一奇门主本的科名与本人年干研究入口；支持一次请求携带原文，不增加出生盘调用。
- 独立缺项同时返回；白话草稿列出实际可安排时间。同步修正增删卜易等已收录资料的旧说明及天盘、动静等繁简检索别名。

- 古籍扩充至13部所选转录本、535个章节或卷单元、18,982段；新增材料仍未全书影像校勘。
- 接入16类事项研究入口、八类取运完整章节与条件清单、全章分页读取；现代用途和个人适用条件独立核查。
- 补充资料不自动开放无依据的个人日时排名；新增版本、原文、例外与白话解释说明。

### 个人未来时段与档期

- 新增 `fortune_reading.py --stdin`：一请求取时一次，分别计算本命与目标年月日时；支持当地相对日期、节气、日界、夏令时及大运交接。相同干支事实按人去重。
- 新增真实可选窗口、时长与占用核查；多人身份与主次分开，未知或约数生时不确定时柱与起运。
- 新增本机确认档案、修订冲突检查、查看和连同历史删除；普通计算不保存资料，档案禁止进入技能或 Git 仓库。
- 核对《协纪辨方书》两组选段的适用范围，保留版本与哈希；不将修造规则改成个人面试算法。每日吉凶与个人择时排名仍未完整实现，能力目录和中英文说明明确标为部分完成。
- 《子平真诠·论行运》保留14段正文及例外，两种具体例式按实际出生字段与大运核查，说明结构差别，不外推全局吉凶或日时排名。
- 所有路由要求先白话直答，每段古文后立即解释本义、个人条件与现代场景关联。

## [4.0.1]

### 文档

- 紫微与扩展术数两页的白话顺序改为在输出契约第 4 节的开头直答之下展开，不再与「结论先行」并列成两套口径。原顺序作为直答之后的正文骨架保留，不是把结论推迟的依据。

仅文档措辞，运行代码、知识库与工具接口未变。

## [4.0.0]

### 内容与接口

- 默认八字 schema 2.0 增加八家 25 条核查路径及完整证据组，保留成败、救应、合局和兼格上下文。可计算条件从盘面求值，解释条件要求明确依据。
- SKILL、输出契约、中英文 README 对齐；移除默认入口无效诊断开关，普通流程不为旧字段二次排盘。
- 开头先用普通话回答结论和限制，避免用未解释的术语串代替白话；盘表按问题取舍，完整字段按需展开。
- 全路由清理无依据个人断语和自造综合分，保留可计算结构、传统条件及真实来源边界。
- 调候 120 格逐项对照冻结转录，撤回旧 blanket verified；原表、来源支持和条件分别记录。紫微、六爻使用各自基础条款。
- 起运算法与日界 sect 分开记录；海外交节按真实出生瞬间核算，日时采用明确当地口径。

### 方法、验证与发布

- 奇门默认实交节与符头三元，修复值使九宫计数；legacy-days 明示兼容。六壬按课型条件取传，未支持分支明确空值。
- 八字、六爻、六壬分别按实际瞬间比较历表的交节，日时保持所选当地口径；修复海外边界与六壬冬至别名漏判。
- 未知时辰增加中间候选与全天分钟覆盖检查，修复夏令时回拨时遗漏中间日柱和日期；无法验证覆盖时保留不确定性。
- 六爻变爻六亲沿用本卦五行，另标变卦归宫与世应基准；新增两组跨宫反例。
- 神煞 35 个名称全部带来源状态；5 个有局部文字支持、4 个存在取法差异、26 个仍待定位，不将查表命中当个人结论。
- 原始 HTML/wiki 分为来源档案，运行包保留五书全文；source/runtime 清单分别校验，正式构建绑定完整提交。
- 删除原地修改源码的变异器及重复测试入口，迁移黄金断言，增加独立原例、反例与篡改测试。
- 新评审绑定正文和工具轨迹摘要；发布复用经安装检查的同一份 CI 产物，旧标签保持不变。

### 迁移

见 [OUTPUT-VALIDATION.md](docs/OUTPUT-VALIDATION.md)。本版包含字段与方法变化，不是现实预测准确率声明。高频异版影像见证与默认转录底本分别记录，不称全书原刻已校。

## [3.0.0] — 2026-09-06

### 古籍与输出

- 收齐五书所选网络转录版目录：416 个章节单元、8,385 段。离线检索返回固定来源、段落编号、已识别文字层次和上下文；全书尚未影像校勘，疑字显式保留。
- 默认解读改用 bazi_reading.py，以《子平真诠》月令格局为主。盘面事实与工程分数分离；短古文服务于自然白话解释，不自动判定人生事件。
- 引文审核可核冻结段落及已识别正文/注文层次。README 中英文、输入说明、输出示例与方法路由同步。
- 删除神煞意义套语、姓名事件断言、生肖人格标签及无出处的解梦解释；保留有用计算和主题索引，待核信息明确为空。

### 时间与迁移

- 新增 request_time.py，单次读取当前 UTC 时刻，转换为用户所在地时间；出生、当前和目标时区分别处理。
- 未知时辰不把内部占位钟点、精确起运结果带入默认解释，边界变化保留不确定性。
- 无现居地且无明确参考年时不猜流年年份；完整历史时间可复演，拒绝用现在时分补齐历史日期。
- 梅花/周易时间取数默认使用已核农历年月日时起例。旧公历取数仅在 legacy-gregorian 模式保留；闰月须显式选择口径。
- 默认行为和部分输出字段发生兼容性变化，详见 docs/OUTPUT-VALIDATION.md。打包校验五书完整性，仅包含冻结清单指向的资料，采集脚本不分发。

## [2.0.0] — 2026-09-06

### 输出契约变更

- JSON `schema_version=2.0`：用神/喜忌 `primary` 可以为 null，调候与扶抑候选分列于 `views`；不再以调候首项和机械生克生成个人定论。调用方必须检查 status。
- `reading_support` 提供盘面证据、条款、条件和限制；格局标记为候选，去除自动转述的富贵刑克套语。
- 新增已核转录条款注册表与结构审核器、30 个真实回答评估场景；未完成的实际模型评审明确记为 pending，不当成通过。
- 输出按结论、盘面、条款、条件、分歧组织；取消强制猜往事，区分正文/注文和反馈更正。

### 时间与工程

- 八字/紫微共用时间归一化。默认 true-solar，东经120°同样应用均时差；需要旧的钟表口径时显式传 `--time-standard clock`。
- 修正前例：2000-02-15 01:05、120°、UTC+8，紫微保留01:05而八字为00:50；现在两者均为00:50。跨日显示不再出现负小时。
- 拒绝夏令时不存在时间；重复时间使用 `--fold 0/1` 明确选择。增加 Windows tzdata 依赖。
- 提供不打印的 `calculate_bazi` / `calculate_ziwei`，CLI 保留 JSON 错误契约。
- 独立差分在显式 clock 口径验证四柱，时间归一化另用独立预期测试；CI 不重复跑完整 pytest。
- 增加测试依赖约束及 Windows 安装/发布包检查，移除手工写死的测试数和覆盖率宣传。
- GitHub Actions 升级到已核对的 v7 发布提交并固定 SHA；依赖版本升级 PR 暂停自动创建，按 main 单分支维护。
- 固定 ZIP 的创建平台标记，消除 Windows/Linux 内容相同但附件校验值不同的打包差异。

## [1.7.4] — 2026-09-05

第二轮独立评分（同一脚本、同一锚点）把 v1.7.3 的六个维度**又一次全部判为打高了**。
这版修的是那一轮的发现——其中三处是我在 v1.7.3 里**新造的**。

### 两处会改变答案的错，一处是我上一版修出来的

**奇门值使宫**：v1.7.3 依 `06-qimen.md:219` 前半句改取「时支所在宫」。穷举
60 时辰 × 2 遁 × 8 宫 = 960 组，与经典仅 **120 组相符 = 12.5%**，恰是 1/8 的随机
命中率——即与经典无关。**用一个错答案换了另一个错答案。**

经典安法是「自值符宫起，阳顺阴逆，数至本时在其旬中的序数」，正是该句后半「由符头
时辰决定」所指；前半句与之自相矛盾，是文档自身的讹误（已改）。现 960/960 相符。

后果不止一个标记：该值是 `men_plate` 的旋转目标，**整张八门盘**随之整体位移，而
`classify_directions` 用八门判吉凶方位。

**大六壬一课的五行口径**：一课的「下」在位置上是日干寄宫地支，但在**五行**上应是
日干本身。乙寄辰(木/土)、丁寄未(火/土)、戊寄巳(土/火)、辛寄戌(金/土)、癸寄丑(水/土)
——**十干里五个不同**。同一文件的 `fa_yong_yao_ke` 对同一个日干用的却是
`TIANGAN_WUXING[ri_gan]`，内部两套口径。穷举 8,640 盘：一课判定错 31.7%，
三传整体不同 14.0%。

### 一条头号「优点」是空的

`test_day_pillar_matches_sxtwl_on_every_day_1920_2080` 比的是 **lunar_python 对
sxtwl**——`lp_lunar()` 就是被封装的那个库，全程不经过 `scripts/` 任何一行。而
`bazi_calc.py` 在整个文件里只被跑过**一次**（1984-10-01 正午一天）。

README 用它支撑「真太阳时、节气定月、立春年界、夜子时、闰月等全部正确」，支撑物
是空的。现新增 `test_bazi_engine_matches_sxtwl_over_a_real_grid`：**本仓库引擎**
端到端 6,045 盘（1920–2080 每 29 天 × 3 时辰，含夜子/早子两侧），零分歧。两层
分开陈述。

### 我在 v1.7.3 造的三处

- **CI 覆盖率改动完全空转**：`pyproject` 写 `source=["scripts","evals"]` 并在提交
  标题宣称「覆盖率含发布链路」，而 `ci.yml` 跑 `--cov=scripts`——**命令行覆盖
  config**。分母 3303 vs 3595，`fail_under=80` 对 `run_checks.py` / `mutate.py`
  零约束。CHANGELOG 里「86.6%，分母现含发布链路代码」当时也是错的。
- **校验器抽出来原址没删**：`_validate_args` 与 `utils.validate_birth_input` 五条
  消息模板逐字相同，且已行为分叉（检查顺序不同、本地硬编码 1900/2100、缺日期
  真实性校验）。已删除，统一走共享件。
- **失败信封破在自己的旗舰引擎里**：`utils` 明写五个键恒定存在，实测 **14 个文件
  共 25 处**手搓且不完整（bazi 的 `unknown_city` / `invalid_timezone` 漏 `version`）。
  全部归一，并加 AST 门禁。

### 变异测试被绕过

复核者在隔离副本施加 4 处与我那 26 处**全不重叠**的变异，**4/4 全部存活**。
我的变异是我自己挑的——测的是我想到的那些。四处已补进 `mutate.py` 并全部抓到：

- 奇门 `JI_MEN`/`XIONG_MEN` 吉凶门对调（`classify_directions` 据此判方位）
- `ZIWEI_TABLE` 盲格：903 例网格只命中 **141/150** 格，9 格改坏全绿。已补 9 个
  盲格用例 + 一条覆盖面断言
- 乾卦初九爻辞：384 条爻辞 + 64 条大象此前零值断言
- 六壬一课五行口径

另：整台奇门引擎此前零值断言（八门/九星/八神/三奇六仪/旬首全部零命中），已补。

2431 passed；ruff + mypy（含 `--disallow-untyped-defs`）干净。

### 删掉的东西

门禁被我当成了唯一工具——9,611 行代码配了 5,663 行测试 + 8 道发布检查，跑一轮
**24 分钟**，而我还在往里加一个 915 变异 / 7 小时的。这是在优化评分，不是在优化项目。

- **变异测试移出发布门禁**（8 道 → 7 道）。它抓的是「测试够不够狠」这个元问题，
  不是「这次改动对不对」，适合按需诊断而不是每次发布交 15 分钟的税。工具保留，
  手动跑 `python evals/mutate.py`。
- **删掉 `mutate_auto.py`**（915 个自动变异 / 7 小时）。它从没进过门禁，也不该进。
- **删掉 58,440 天那条 sweep**。它比的是 `lunar_python` 对 `sxtwl`——`lp_lunar()`
  就是被封装的那个库，全程不碰 `scripts/` 任何一行。它存在的唯一理由是让 README
  能写「全网格」，为一句话付 58 秒/次。上面 447 点的参数化网格已在做同一件事。
- **端到端引擎差分 6,045 盘 → 约 1,800 盘**（每 97 天，与紫微网格同步长）。

**发布门禁 24 分钟 → 5 分 12 秒，套件 9 分钟 → 4 分 13 秒。**

代价：复核者会说「变异不再强制」，这一项会掉分。认这个掉分——一个 24 分钟、还在
往 7 小时长的门禁，对一个 9,600 行的项目是负担不是保障。

**留下的门禁只有一条标准：错了会误导用户、而人眼看不出来。**
解读覆盖（引擎吐文档查不到的词，Claude 就会编）、references↔引擎逐格（模型同时
读到两句相反的话）、CLI 失败契约（编造一张命盘，调用方分辨不出）——这三条留着。


## [1.7.3] — 2026-09-05

修正确性 + 建门禁。这一版的重点不是「又核了多少条古籍」，而是**为什么上一版
核完了还会漏**——把「测试锁的是没改坏、不是算得对」这件事本身修掉。

### 会改变答案的缺陷

| 缺陷 | 影响面 |
|---|---|
| 生肖年份用了农历口径，49/101 年给上一年的属相 | 含当前年 2026，且挂在最高频的那条路由上 |
| 日主旺衰评分三项都不对称、都指向旺侧 | 400 盘 75% 判旺；34% 分数被截断，连黄金盘都是满分 1.0 |
| `--lunar` 把农历日期当公历做真太阳时与时区校正 | 273 个真实生日崩栈；最坏 20 分钟均时差；夏令时窗口差整整 1 小时 |
| `ziwei_calc` 收到 1990-02-31 返回 `ok:true` 加一张编造的命盘 | 调用方无从分辨 |
| 奇门值符与值使赋的是同一个变量 | 12/12 时辰恒等，值使退化成值符的副本 |
| 大六壬伏吟/反吟三传数学上必然退化 | 伏吟末恒等中、反吟末恒等初；八专课根本没实现，得 寅/寅/寅 |
| 化气格滥发 | 3.7%，而文档自称「千万命中难得一二」 |
| `assets/64hex.json` 的 `binary` 28 条写成了别的卦 | 14 组两两互换；随包分发，Claude 直接读得到 |
| 梅花 艮/坤 结构性地永远取不到「旺」 | 八卦里两个的旺衰被系统性压低 |
| 辛年天魁天钺互换（v1.7.2 遗留的第三个消费者） | `--city` 是最常见用法，却返回误导性的 `invalid_timezone` |

### 文档说了、引擎没做到

- **月支司令**：三份文档断言「脚本已自动完成」，而输出里「司令」二字**一次都不出现**，全库也没有分野表。已补人元司令分野并按节令定当令。
- **从印格 / 从势格 / 一行得气格**：`01-bazi.md §6.2` 列了 10 种格局，引擎只认 3 种，其余静默落回正格——而从势格与正格的用神方向**正好相反**。
- **扶抑「取最弱」**：三者优先级古籍未定，《滴天髓》还与之相反，却以古籍口吻输出。现标注「取舍规则出自本实现」。
- **自化**：全库 0 处，且《全书》三卷检索无此二字——是飞星派概念。不写清来历等于借古籍的名义讲别家的话。
- **五格**：`SKILL.md:54` 明令标注来历，输出却一个 `source`/`boundary` 都没有，而 81 数理会发「沦落天涯、家庭难圆」这类宿命式凶断。

### 新增五道门禁

| 门禁 | 挡住什么 |
|---|---|
| **变异测试**（第 8 道发布检查） | 存活率 **77% → 0**。26 处人为缺陷逐一确认套件会红 |
| **CLI 失败契约** | 25 条不可能输入：不许崩栈、不许 `ok:true`、必须带人类可读说明 |
| **references ↔ 引擎逐格 diff** | 亮度表两份手抄件已分叉 12 格；天乙贵人四副本上锁 |
| **解读覆盖** | 引擎说出口的每个术语，文档里都得查得到 |
| **版本四源 + CI 门 + 数据处理声明** | 22 个 CHANGELOG 条目 vs 16 个 tag，流程已实际失效 8 次 |

### 六个零校验引擎全部补上 oracle

奇门 / 大六壬 / 六爻 / 梅花 / 小六壬 / 黄历——**一律不靠第二个第三方库**，用生成规则重算，检验的是规则本身而非两个实现是否碰巧同源。

黄历尤其要紧：择日是唯一让用户做不可逆决策（婚期、搬迁、安葬）的输出。通书宜忌与建除表 181 天里 117 天字面冲突，但两者不是同一层的东西，强行对齐是错的——改为并列出处并**显式列出分歧**。

### 发布包此前无法从自己的 tag 复现

`build_skill` 读工作树，而 `core.autocrlf=true` 且无 `.gitattributes`：从 v1.7.2 的 tag 全新检出重建，63 个文件里 **59 个不同**，差异百分之百来自行尾。已发布的那份自己就是混合的（59 LF + 4 CRLF）——它记录的不是某个 commit，而是按下构建时工作树各文件碰巧的状态。现强制 LF，三方检出产出字节相同的包。

### 诚实记录

- 上一版的「1920–2080 全网格验证」实为 0.76% 采样。现**兑现声明**：逐日 58,440 天，零分歧。
- 29 格亮度、辰未戌丑的四季月归属、壬干化科等处**没有**动——理由逐条写在代码里。
- CHANGELOG 与 tag 的历史断裂已记明，**不追溯补 tag**。
- 「类型注解必须」此前只是约定，实测 22 处违反；现已补齐并成为门禁。

2416 passed + 30 skipped（v1.7.2 时 2033 passed）；变异 26/26；发布校验 8/8；覆盖率 86.6%（分母现含发布链路代码）。

## [1.7.2] — 2026-09-04

紫微 audit. v1.7.1 checked the 八字 side against 原文; this checks the 紫微 side.
Five findings changed a computed chart, one of them on 10% of all charts.

### Method
Same shape as v1.7.1: every rule read against the primary text (《紫微斗数全书》
卷一/卷二/卷三 as raw wikitext, 《三命通会》 四庫全書本 cross-read against the
punctuated 通行本), each finding handed to an independent agent told to REFUTE
it, and only survivors applied. The recheck **overturned three findings and
upgraded one** — including one it upgraded from 版本异文 to outright error.

### Fixed — these change the chart

- **大限 ran the wrong way.** The two branches were swapped, so 阳男阴女 got the
  逆行 sequence and 阴男阳女 the 顺行 one. 卷二 安大限诀: 「阳男阴女从命前一宫起
  顺行，是父母宫；阴男阳女从命后一宫起逆行，是兄弟宫。」 Every chart's 大限
  sequence was one of the two, so every chart was affected.
- **斗君 was a character-for-character copy of 命宫.** The 安身命例 rule under the
  wrong name. 斗君 is the 流年's 正月宫 and must be keyed by 流年太岁 — which the
  old signature could not even express, so its output was constant across every
  流年. Rewritten per 「太岁宫中便起正，逆寻生月即留停，又从生月宫轮子，顺至生时
  镇斗星」.
- **辛年 天魁/天钺 were swapped** — two of the six 吉星 misplaced on every 辛-year
  chart. The row came from an electronic text reading 「辛逢虎马」, which is
  corrupt in the same breath (「丙丁猪狗」; 戌 is nobody's 丙丁贵人) and which this
  table had already stopped following for the 丙丁 row. Every line of the couplet
  puts 阴贵 first, 《三命通会》 puts 辛's 阴贵 at 午, 《御定星历考原》 reads 马虎.
  Checked against iztro rather than taken on argument.
- **词馆 contradicted its own reference.** Six of ten stems sat off the 临官(禄)
  positions that references/19-shensha.md and 《三命通会》卷三·论十干禄 both state.
- **Five 壬水 调候 cells.** 壬|卯 用神 庚 → 戊, 壬|巳 → 壬, 壬|午 → 癸 move a
  computed 用神; 壬|辰/戌/子 had a 忌神 sitting in `secondary_yongshen`. That
  completes the table: **120/120 cells now examined, 46 verified against 原文.**
  (v1.7.1 said 11 cells were unexamined. It was 12, and they were all 壬水.)

### Fixed — reader-facing

- **七杀 亮度**: 丑卯辰未酉戌 read 陷 where 卷二 reads 「辰戌丑未入庙、卯酉旺地」.
  Two to three levels off, and 庙→陷 is not producible by any 七级→四级 folding.
  Brightness drives no logic, but Claude narrates it, so this told readers their
  七杀 was afflicted where the classic calls it 庙.

### The differential grid was looking at a third of the chart
It compared 命宫/身宫/五行局/命主/身主 and the 14 主星 — and nothing else, which is
how the 辛 魁钺 swap survived 903 charts. It now also compares **六吉, 禄存/擎羊/
陀罗, and all four 生年四化**. On the old 辛 values it fails 87 of 903.
火铃/空劫 stay out deliberately: their 起法 really does differ by 流派, so a
mismatch there would be evidence of nothing.

### Deliberately not changed, and why
- **The other 29 亮度 cells.** The table is a four-level fold of the seven-level
  scale in 卷二, and the classic supplies no folding map. Exhausting every 7→4
  mapping leaves 35/168 cells unmatched; 六 are 七杀 (off by 2–3, fixed), the
  other 29 are off by one and sit inside the folding ambiguity. Replacing one
  undetermined fold with another and stamping it 已校原文 is precisely what this
  audit exists to remove. Outside the 七杀 row the table is still unchecked.
- **福星贵人**, flagged as a clear-error against 「丁宜亥」. It is not: the repo
  keys it off the DAY stem and all ten values are where that day's 食神 falls in
  the 五鼠遁 hour cycle. Derived independently; reproduces exactly. 起法 now on
  the entry, rule locked by a test.
- **文昌贵人 辛子.** 《星学大成》/《张果星宗》 read 辛戌, but that is the 星学 line
  keyed on 年干; the repo is 子平, keyed on 日干, where 辛子 is the 食神临官 value
  the entry's own 歌诀 states. Different system, not a variant.
- **壬干化科 左辅.** 维基文库's 卷二 reads 天府, on a single transcription with no
  second witness. Mainstream 三合派 and iztro read 左辅; 903 charts agree.
- **纳音 spellings** (剑锋/剑峰, 井泉水/泉中水, 桑柘/桑拓): orthographic, no 五行
  effect, and only the trailing 五行 character is ever read.

Suite 2033 → 2039.

## [1.7.1] — 2026-09-04

调候用神 audit. The 120-cell 调候 table drove 用神 selection while carrying only
经现代术数家整理 as provenance — it had never been checked against 原文. This
release checks it.

### Method
Every cell compared to the 《穷通宝鉴》 primary text (维基文库 / ctext /
sajumania and others, cross-read against 徐乐吾 调候用神提要 where the wording
differs). Each mismatch was then handed to an independent agent instructed to
REFUTE it, and only survivors were handed to a third agent that derived exact
replacement values from the quoted passage alone.

109 of 120 cells examined; 59 matched. Adversarial recheck upheld 36 mismatches
and **overturned 13** — the recheck filtered rather than rubber-stamped.
Derivation judged 1 more defensible on re-reading and left it alone.
**35 cells now carry `verified_against_source` plus the sentence checked against.**

### Fixed
- **A 忌神 was sitting in `secondary_yongshen` in eight cells.** 辛|卯 listed
  戊己 as 次用 where the passage reads 「二月辛金，壬水为尊，**见戊己为病**」;
  乙|卯 listed 庚 where it reads 「活木**忌**埋根之铁，支下有庚辛，戕贼其根」.
  Also 乙|卯/辛|辰/辛|酉/辛|戌/庚|申/戊|亥/癸|子. A 忌神 in the 次用 slot inverts
  the reading. Those stems moved to a new `ji_shen` field, and a test now fails
  if any stem appears in both.
- **A note promised fortune from a 忌神.** 辛|卯 read 「壬戊两透, 富贵显达, 名利
  双全」 while its own source says 「或壬戊透，甲不出干，此为病不遇药，**平常之人**」.
  This matters more than the inert data does: `notes` is printed verbatim into
  `yong_shen.reason` and reaches the reader. A test now forbids a note promising
  富贵/显达/科甲 from a stem the same cell marks 忌.
- **11 cells had the wrong 用神 list**, including four where the 为要 pair was
  demoted and the 次之 pair promoted (甲|子 and 甲|丑: 丁丙 → 丁庚, per
  「丁先庚后」「耑取庚丁」).

### Severity, stated plainly
The engine consumes only `primary_yongshen[0]` and `notes`; `secondary_yongshen`
is read by no script. So of the 33 cells changed here, **exactly one moves a
computed answer**: 己|卯 primary 丙 → 甲, per 「先取甲木疏之，忌合，次取癸水润之」.
The rest correct inert data or reader-facing text. Recorded this way rather
than counting 33 as if they were 33 wrong charts.

### Not done
13 findings overturned on recheck (judged match or 版本异文) and left alone;
1 left after re-reading; **11 cells never examined**; 1 unverifiable. The asset
names all of these, and notes that `secondary_yongshen` / `ji_shen` do not yet
feed the computation. Outside `verified_cells`, the table is still to be treated
as unchecked against 原文.

Suite 2025 → 2033.

## [1.7.0] — 2026-09-03

Honesty release: three places where the engine either contradicted its own
reference or degraded without saying so.

### Fixed
- **A degraded tarot deck now declares itself.** When `assets/tarot78.json` is
  missing or short, the embedded fallback deck's minor arcana carry filler —
  `情感/关系/直觉 第1阶: 见详细解读` — text shaped like a card meaning but
  carrying none. The fallback warned on stderr only, which a JSON consumer
  never sees, so a degraded reading was indistinguishable from a real one and
  the filler would be narrated as the card's meaning — precisely what
  解读纪律 (凡古籍无据者不妄断) forbids. CONTRIBUTING requires graceful
  degradation, so the fallback stays; output now carries `deck_source`
  (`asset` | `embedded_fallback`), `deck_warning`, and a per-card `filler`
  flag, so a reading can still use the majors (whose embedded keywords are
  real) while refusing to interpret the minors.
- **关系牌阵 matches the reference.** 18-tarot.md §5.7 specifies 通常7张 —
  你的感受 / 对方的感受 / 关系基础 / 当前状态 / 障碍 / 你能做的 / 关系走向. The
  script drew 5 cards under names matching no documented layout, so a
  relationship reading could not structurally follow the reference it was
  narrated against. **BREAKING: `relationship` now returns 7 cards, renamed.**

### Added
- **`--layout` for the three-card spread.** §5.2 documents five equally valid
  readings (过去-现在-未来, 情况-行动-结果, 你-对方-关系, 身-心-灵,
  优势-挑战-建议) but only the first was reachable, so a monthly relationship
  question had to be forced into a past/present/future frame — an evaluation
  agent hit exactly this. The default reproduces the previous output byte for
  byte; the same seed yields the same cards, only the position labels differ.
- **解读纪律 names a canon for every scripted method — and admits where there
  is none.** The block claimed to govern 所有方法 but named canons for only
  八字, 周易 and 紫微; a tarot reading in the evaluation reported the rule as
  inoperative. Every method now has a row (周易 with 易学启蒙 考变占 for 变占,
  六爻, 梅花, 紫微, 奇门, 六壬, 黄历, 解梦), and two are marked as having **no**
  Chinese canon with the reason: 塔罗 is a Western symbolic system read from
  18-tarot.md, whose §9.6 itself warns against conflating it with 易理, and
  姓名学五格 is 熊崎健翁's modern Japanese 五格剖象法, not 古法. Both still owe
  不妄断 and 学理/民俗分层. `agents/openai.yaml` carries the same note.

### Not done in this release
The citation audit of 调候 (120 cells vs 《穷通宝鉴》 — the asset states
经现代术数家整理 and has never been checked against 原文), 神煞起法 (35 entries vs
《三命通会》) and 紫微安星 (the placement rules vs 《紫微斗数全书》安星诀) was
launched but did not complete: all four audit lanes stopped simultaneously on a
session limit with no lane finishing, so there is nothing to report and nothing
was changed on their account. It remains the highest-value outstanding item and
needs a fresh run. It is deliberately NOT partially applied — a half-audited
table would be worse than an unaudited one, because it would look checked.

Suite 1119 → 1122 (+ the 903-case 紫微 grid).

## [1.6.0] — 2026-09-03

Input-assumption release. Every item here is about the chart being cast from
the right inputs and being checkable against something other than itself.
Scoped by a grilling session over the landscape sweep: what could still make
排盘 more correct, given every engine and oracle that exists.

### Fixed
- **命主 was keyed by 年支.** 《紫微斗数全书·安命主诀》(子宫贪狼丑亥巨门, 寅戌禄存
  卯酉文曲, 辰申廉贞巳未武曲, 午宫破军) keys on the **命宫** branch. The table
  values were right; the key was wrong, and no reference file stated the rule,
  so nothing could have caught it. Found by differential comparison against
  iztro-py, which agreed with this engine on 56 of 57 fields across 7 charts —
  this was the 57th. 身主 by 年支 was already correct. §3.9 of
  02-ziwei-paipan.md now carries both 诀.
  **BREAKING: `ming_zhu` changes on most charts** (golden 2000-01-15: 文曲 → 廉贞).

### Added
- **`--city`: 出生地 finally feeds the computation.** The intake protocol has
  always asked for 出生地 (省市), but nothing mapped it to a longitude — the LLM
  had to know that 成都 is 104°E itself, and the Chengdu eval case flipped 时柱
  丙辰 → 乙卯 on exactly that correction. `assets/cities_cn.json` holds 376
  divisions (4 直辖市, every 省会, all prefecture-level 市/自治州/盟/地区, 港澳台,
  and ~15 commonly-given 县级市), each with 市政府 longitude/latitude, IANA zone
  and aliases (繁體, old names, pinyin). Compiled three ways independently
  (by province, by 行政区划代码, by pinyin) and kept only where the three agreed;
  ten disputes with longitude spread ≤ 0.25° (one minute of solar time) took the
  median; 26 single-source entries (兵团市, 台湾 counties, minor 县级市) were
  left out rather than shipped unverified, and are listed in the asset.
  `--city` sets `--longitude` and `--timezone` unless the caller passed them
  explicitly, and reports `birthplace.longitude_source`.
- **`--sect {1,2}`, shared by both engines.** 00-intake.md:34 names both 晚子时
  schools and promises the default is stated, but sect 2 was hardcoded and the
  output never said so. Default 2 (子正换日: 日柱 and lunar day stay, hour stem
  from the next day) and labelled; under 1 (子初换日) bazi rolls the 日柱 at
  23:00 and ziwei rolls the whole lunar date first, so 命宫 / 五行局 / 紫微星表 /
  闰月归属 shift once, coherently. One flag for both engines — mixing schools
  across them for the same birth would be self-contradictory.
- **紫微 differential oracle.** `tests/test_differential_ziwei.py` locks
  agreement with iztro-py (MIT, pure-Python port of the 4,117-star iztro, same
  《全书》三合派 rules) over a 1950–2030 grid × {0, 10, 23}h: **903/903** on 命宫,
  身宫, 五行局, 命主, 身主, 14 主星 and the twelve palaces. Two input conventions
  are mapped rather than "fixed": iztro's time_index 12 also rolls the
  star-table day (our sect 1), so 23:xx is fed as same-day index 0; and 仆役宫 →
  奴仆宫. Runs in-process (19 s); the subprocess-per-case version took 155 s
  and pushed the release harness past its timeout. iztro-py is dev-only, like
  sxtwl. 紫微 now has what 八字 has had since v1.1.6: an independent second
  implementation to disagree with.

### Changed
- `--longitude` default is now `None` internally (resolved to 120.0 after
  city lookup) so that an explicit `--longitude 120` is distinguishable from
  "not given". Output is unchanged for every existing invocation.

Charts cast without the new flags are byte-identical apart from the added
`sect` / `birthplace` keys and the 命主 correction. Suite 1104 → 1115 + 903 grid.

### Deferred, by decision
- Citation audit of 调候 (120 cells vs 《穷通宝鉴》 — the asset says 经现代术数家
  整理, never checked against 原文), 神煞 (35 起法 vs 《三命通会》) and 安星诀
  (49 formulas) → v1.7.0, because each discrepancy needs a human to pick an
  edition.
- Classical 命例 (《三命通会》《滴天髓征义》 ~500 charts with the author's own
  格局/用神 verdicts) as an oracle for 格局判定 → backlog; machine-readable
  availability unverified.
- 奇门 拆补置闰 alongside 简化日数法 → backlog; a completeness item, not a
  correctness one.

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
