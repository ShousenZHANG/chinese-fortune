# Chinese Fortune · 古籍与白话解读

[![skills.sh](https://www.skills.sh/b/shousenzhang/chinese-fortune)](https://skills.sh/shousenzhang/chinese-fortune)
[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ShousenZHANG/chinese-fortune)](https://github.com/ShousenZHANG/chinese-fortune/releases)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](#安装)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**让 AI 按古籍原文算八字、挑日子、看运势，用大白话回答，每句引文都能查到出处。**

一个 [Agent Skill](https://agentskills.io)：干支、吉凶等级、大运喜忌由随包脚本计算，AI 只负责讲清楚，不凭记忆另算。古籍库收十五部固定转录版本，离线可查；现实生活问题按《高性价比人生指南》回答。支持 Claude Code、Codex、Cursor、GitHub Copilot、Gemini CLI、claude.ai 和只认 MCP 的工具。

[English](README.en.md) · [安装](#安装) · [这样问](#这样问) · [能做什么](#能做什么) · [为什么可信](#为什么可信) · [更新与卸载](#更新与卸载)

## 安装

最省事的办法是把这句话发给你的 AI：

> 安装这个 Skill：https://github.com/ShousenZHANG/chinese-fortune

| 宿主 | 命令 |
|---|---|
| Claude Code | `/plugin marketplace add ShousenZHANG/chinese-fortune`，再 `/plugin install chinese-fortune@chinese-fortune` |
| 同仓库的另外两个技能 | 现实生活问答 `life-guide`，塔罗、星座、解梦 `fortune-extras`：把上面命令里的 `chinese-fortune` 换成技能名（Claude Code 是 `/plugin install life-guide@chinese-fortune`） |
| Codex、Cursor、GitHub Copilot、Gemini CLI 等 | `npx skills add ShousenZHANG/chinese-fortune --skill chinese-fortune` |
| Gemini CLI（自带命令） | `gemini skills install https://github.com/ShousenZHANG/chinese-fortune --path skills/chinese-fortune` |
| claude.ai、ChatGPT、Claude API | 从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载 `chinese-fortune-v版本号.zip`：claude.ai 在 Settings > Features 上传；ChatGPT（Business、Enterprise、Edu）在 Plugins > Skills 上传；Claude API 用 Skills API 上传 |
| 只支持 MCP 的工具（Claude Desktop、Cursor、VS Code 等） | 解压同一个 zip，按下方配置接入 |

```json
{"mcpServers": {"chinese-fortune": {"command": "python", "args": ["/解压路径/chinese-fortune/scripts/mcp_server.py"]}}}
```

MCP 配置在 Windows 上把 `python` 换成 `py`，参数前加 `"-3"`；工具名和资源会自动列出，SKILL.md 和参考文档作为资源提供。保存档案、前瞻记录这两个会写个人资料的脚本不通过 MCP 开放。

只需 Python 3.9 或以上（macOS 自带的 `python3` 就够），不用 pip 安装任何包，计算不联网：排盘库 lunar_python 和时区数据 tzdata 已随包附带。CI 在 Python 3.9、3.11、3.12 和 Windows 上验证。装好后在技能目录自检，返回 `"healthy": true` 即可：

```sh
python scripts/doctor.py
```

<details>
<summary>给 AI 的安装说明</summary>

1. 按用户用的宿主选上面一种安装方式。拿不准时用 Release 里的 zip，解压到宿主的技能目录（Claude Code `~/.claude/skills/`，Codex `~/.codex/skills/`，Gemini CLI `~/.gemini/skills/`），应得到 `chinese-fortune/SKILL.md`。
2. 不要运行 pip。依次试 `python3`、`python`、`py -3`，找一个 3.9 以上的；都没有时征得用户同意再装 Python（命令见 SKILL.md「运行环境与诊断」）。
3. 在 chinese-fortune 文件夹里运行 `python scripts/doctor.py`，返回 `"healthy": true` 就装好了；否则按 `next_step` 处理。

</details>

## 这样问

问到命理时，AI 会先问这道题用得上的出生资料（日期、时间、出生地、性别）和你现在住的城市。时间记不清可以给范围，比如 19–20 点；只查古籍不需要生辰。

| 想知道 | 可以这样问 |
|---|---|
| 八字命局 | 我出生于 1990 年 5 月 10 日 14:30，男，北京出生，现在住悉尼。请用白话解释八字的主要结构，说明哪些条件成立、哪些地方有分歧。 |
| 哪天对我好 | 下个月哪天搬家好？未来七天哪天对我好？ |
| 面试、考试几点 | 下周二上午和周四下午能面试，每次一小时，选哪个？ |
| 大运、流年 | 我现在这步大运好不好？2027 年运势怎么样？ |
| 穿什么、戴什么 | 我穿什么颜色、戴什么对自己有利？ |
| 黄历、六爻、奇门 | 10 月 29 日搬家可以吗？用六爻看下周二的面试。下周哪个时辰适合出行？ |
| 查古籍 | 《子平真诠》怎么理解用神？先解释意思，再给原文位置。 |
| 现实生活 | 失业了先做什么？替朋友担保签不签？ |

回答先用大白话直接说结论，再给短原文，每段古文后马上解释它的意思、为什么和你的情况有关。下面节选自[白话输出示例](skills/chinese-fortune/docs/OUTPUT-EXAMPLE.md)（依据固定测试盘撰写，不是真实用户预测）：

> 不能直接给你一个“补某种五行就好”的答案。按这套古法，盘中一条约束关系比较突出，同时还有削弱它和支持它的关系，需要放在一起看；不能只抓住一个名称就判好坏。
>
> 《子平真诠》说：“八字用神，專求月令。”这里的“用神”是从出生月份确定分析的起点；本例先看己土正官，并不等于“最缺什么就补什么”。

## 能做什么

| 方法 | 能回答 | 依据 |
|---|---|---|
| 八字命局 | 格局、用神、成败条件 | 《子平真诠》月令格局为主，《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》对照；八家 25 条核查路径、46 条格局条件 |
| 大运 | 这步运各候选配法的喜忌及条件 | 《子平真诠》八家取运章、49 个候选配法；条件未决和反向例外并列 |
| 流年 | 某一年、今年、明年 | 《渊海子平》《三命通会》《滴天髓》论太岁与岁运，逐条列关系，不合总分 |
| 个人择日、期间运势 | 哪天好、哪天要避开 | 《协纪辨方书》卷三十三相主，按出生年干支分大吉到大凶 |
| 择时 | 面试、考试、出行、搬家几点 | 相主加事项忌日；面试、考试另接《奇门遁甲元灵经》 |
| 穿戴、颜色、方位 | 穿什么颜色、戴什么 | 《穷通宝鉴》调候的一般取法（这一格的例外未按本人盘逐条核对） |
| 黄历 | 某天宜忌 | 《协纪辨方书》《渊海子平》有出处的忌日条款 |
| 紫微、六爻、周易、梅花、奇门、六壬 | 点名时使用 | 各书固定转录，按实际覆盖解释；紫微可算流年斗君到流时；六爻自动判盘面能判的条件；奇门有《遁甲演义》转盘、卷二格局和逐时辰择时；六壬九宗门取传齐全 |
| 合婚、亲子、合作关系 | 两人哪几柱相合、相冲、相刑 | 逐柱列关系和日主互见的十神，按关系类型筛条款，只分类不打分；合婚另给《选择要略》三元九宫合卦并附驳议 |
| 出生时间不准、资料更正 | 时辰不确定、生日记错了 | 列出不变与会变的柱和受影响的结论；也能由四柱反查日期 |
| 风水坐向 | 测得的角度坐什么山 | 《协纪辨方书》二十四山分类；测量误差跨山时要求复测，不判吉凶 |
| 古籍检索 | 原文、版本、上下文 | 十五部固定转录，557 个章节或卷单元、29,685 段，离线可查；《焦氏易林》四部叢刊本与四库本可按本卦之卦并列查林 |
| 现实生活问题 | 失业、担保、押金、保险等 | 《高性价比人生指南》34 节 660 条、8 篇长文；急症和自伤念头先给第一个动作 |

完整转录库、已整理规则、影像校勘是不同进度：可计算的条件由程序核实，强弱、配合和救应的作用由 AI 结合完整原文解释。测试通过不代表现实预测命中率。各方法的支持范围和输入变化见 [6.0 迁移说明](skills/chinese-fortune/docs/MIGRATION-6.0.md)。

## 为什么可信

- **程序算，AI 讲**：干支、十神、吉凶等级、大运喜忌都由随包脚本计算，AI 只把结果讲成白话，不自己另算。
- **每个结论都有出处**：引文附书名和段落编号，可以用 `classical_search.py --passage-id` 原样查到。
- **说不清就照说**：几个选项等级相同、条件还没核完、几本书说法相反，回答会直说，不替你挑，也不按条数投票。
- **时间算准**：出生地时区、夏令时、真太阳时、日界、节气交接分开处理；出生时间只记得范围，也能逐分钟比较所有可能。
- **发出前机械核对**：`answer_check.py` 核对引文能否在随包古籍里逐字找到、四柱是否与排盘一致，有没有工具没给的分数和“肯定录用”一类断言。
- **可以事后检验**：你同意跟踪后，事前冻结判断，事后记录实际结果，见[前瞻验证](skills/chinese-fortune/references/28-prospective-validation.md)。

## 隐私与数据

本仓库的示例、测试和评测里的出生资料都是虚构的，不是任何真实个人的资料。

排盘、择日和古籍检索都由随包脚本在你的电脑（或宿主的沙盒）里运行，不联网，也不会自动保存你的出生资料或问答；你和 AI 的对话照常经过你所用的 AI 服务。唯一会联网的是起卦时你主动选用的量子随机源，它只取一串随机数，不带任何个人信息，取不到就改用本机随机数。

经你确认后，也可单独保存本机出生档案，支持查看、更正和删除。默认放在 `~/.local/share/chinese-fortune`，不进入仓库或发行包。

## 更新与卸载

| 安装方式 | 更新 | 卸载 |
|---|---|---|
| Claude Code 插件 | `claude plugin marketplace update chinese-fortune`，再 `claude plugin update chinese-fortune@chinese-fortune` | `claude plugin uninstall chinese-fortune@chinese-fortune` |
| npx skills | `npx skills update chinese-fortune` | `npx skills remove chinese-fortune` |
| Gemini CLI | 卸载后重新安装 | `gemini skills uninstall chinese-fortune` |
| zip 上传 | 下载新版 zip 重新上传 | 在宿主的 Skills 设置里删除 |

每个版本的变化见 [CHANGELOG](CHANGELOG.md)。

## 项目结构

```text
skills/chinese-fortune/     安装的就是这个目录（npx skills、Claude Code 插件、发行 zip）
├── SKILL.md                给 AI 的工作流程与方法路由
├── scripts/                排盘、择日、检索、核对脚本，附 lunar_python 与 tzdata
├── references/             各方法的规则说明，按需读取
├── knowledge/              十五部古籍的固定转录与来源索引
├── assets/                 规则库、条款与《高性价比人生指南》
└── docs/                   方法、来源、迁移与发布说明
tests/  evals/  docs/       开发测试与评测记录，不随安装
```

## 进阶说明

<details>
<summary>个人逐日吉凶怎样算、支持哪些事项</summary>

哪天对你好、哪天不好，按《协纪辨方书》卷三十三「相主」直接给出。相主看的是出生那一年的干支（原文「從來皆論生年不論生日」），拿所选时间的年、月、日、时四柱去比：太岁或月建冲你，挑哪天都避不开，回答会先说这一条，不会把这样的日子叫作吉。每一天分大吉、吉、平、小凶、凶、大凶，理由与原文随答附上；问一段时间就列最好的和要避开的日子，比较候选档期就先按吉凶排、再按你的偏好排。出行、婚嫁、搬家、开业另有一组事项忌日（《渊海子平》天地转杀，以及协纪自称吉神不能化解的月破、四废、四忌四穷、往亡、归忌）先行排除。

它不是完整八字合参：出行、嫁娶、搬家、开业在协纪「民用三十七事」里，其余事项是借用这套方法，回答里会写明这是相主等级比较。下表由 `python scripts/fortune_rules.py --capabilities-markdown` 生成，和代码不一致时测试会失败。

<!-- capability-table:start -->
| 事项 | 流程 | 个人吉凶（相主） | 原文授权 | 事项忌日 |
|---|---|---|---|---|
| 阶段运势（`outlook`） | 期间 | 已实现 | 借用 | — |
| 面试（`interview`） | 择时 | 已实现 | 借用（最接近「上官」） | — |
| 工作沟通、谈薪、转岗（`work_conversation`） | 择时 | 已实现 | 借用 | — |
| 学习考试（`exam`） | 择时 | 已实现 | 借用（最接近「入學」） | — |
| 约会、感情沟通（`relationship_conversation`） | 择时 | 已实现 | 借用（最接近「會親友」） | — |
| 出行（`travel`） | 择时 | 已实现 | 协纪民用事「出行」 | 已实现 |
| 订婚、领证、婚礼（`wedding`） | 择时 | 已实现 | 协纪民用事「嫁娶」（只含婚礼） | 已实现 |
| 搬家、入住（`moving`） | 择时 | 已实现 | 协纪民用事「移徙」 | 已实现 |
| 开业、产品与作品发布（`business`） | 择时 | 已实现 | 协纪民用事「開市」（只含开业） | 已实现 |
| 报价、催款（`billing`） | 择时 | 已实现 | 借用（名目有納財、交易、立券，未核是否对应） | — |
| 连续行程（`multiple_events`） | 连续行程 | — | — | — |
| 关系匹配（`compatibility`） | 专项 | — | — | — |
| 起名改名（`naming`） | 专项 | — | — | — |
| 城市与场所比较（`location`） | 专项 | — | — | — |
| 环境与风水（`fengshui`） | 专项 | — | — | — |
| 复盘纠错（`review`） | 专项 | — | — | — |
<!-- capability-table:end -->

</details>

<details>
<summary>问这两天、下周和面试时间</summary>

系统先明确你问的事情和实际日期范围，分别处理出生地、你现在的位置和未来事件的地点，计算出生盘与目标年月日时，核查大运交接，并筛掉已过期、冲突或时间不够的候选档期。

想选时间时，一次给出可用日期、每天可用时段和持续时间；有多个同档候选，再说明希望尽早、尽晚或自己的优先顺序。择时会列出每个可行窗口最早、最晚能开始的时间，覆盖整件事的持续过程，包括途中换时辰、交节或夏令时变化。只有一个窗口时，只说它为什么排得下，不称它是未经比较的命理最优。

面试、考试还会接入《元灵经》已核的地盘、值符和值使，并核对各人的出生年干落宫；未核的星门不填猜测值。连续安排可按你指定的顺序核对每件事的窗口、持续时间、跨城时区和交通准备时间，明确区分“排得下”和“命理首选”。

可以这样问：

> 我下周二上午和周四下午能面试，每次一小时，地点悉尼。先核对档期，再查有没有适用于我的古籍择时依据。

输入字段和当前覆盖见 [个人未来时段与择时](skills/chinese-fortune/references/24-personalized-forecast.md)、[约5分钟补查与候选库](skills/chinese-fortune/references/25-classical-research.md#限时补查与候选库)。

</details>

<details>
<summary>现实生活问题怎样回答</summary>

纯现实问题（失业了先做什么、替朋友担保签不签、通勤两小时值不值）走人生决策流程：从冻结的《高性价比人生指南》（eternity4719/HowToLiveBetter，提交 `842e11c9`，正文 CC BY 4.0，移植的检索和决策流程 MIT）里查条目，先看贴合程度，再按书里的算法排性价比和证据等级，分先做和别做，每条注明第几节第几条，书里没写的部分照实说。急症、自伤念头和正在进行的法律程序先给第一个动作，求助电话只给在中国大陆的人。本库收录除 3 条外的全书：34 节 660 条、8 篇长文、各节导读、术语表和交叉引用。命理问题优先走术数流程。详见 [人生决策](skills/chinese-fortune/references/29-life-decision.md)。

</details>

<details>
<summary>直接运行脚本</summary>

以下命令在技能目录（`chinese-fortune/`）里运行：

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --question 解释主要结构 --markdown
python scripts/huangli_query.py --date 2026-10-29 --question 这天搬家可以吗 --markdown
python scripts/liuyao_cast.py coins --question 下周二面试能过吗 --current-timezone Asia/Shanghai --markdown
python scripts/classical_search.py --list-books
python scripts/classical_search.py --passage-id ziping:c008:p0001
python scripts/classical_guidance.py --scenario interview --retrieve --limit 1
```

`--markdown` 输出盘面和条件核查草稿，完整解读由 AI 继续检查本题相关的解释条件。个人运势入口是 `python scripts/fortune_reading.py --stdin`，通过标准输入接收 JSON，普通使用由 AI 根据对话填写。同一请求复现时间时，把 `request_time.py` 返回的 utc 传给后续计算的 `--request-time`；现居地用 `--current-timezone`，出生地用 `--city` 或经度与出生时区。参数详情见 `python scripts/<脚本名>.py --help`。

</details>

<details>
<summary>结果应该怎样读</summary>

回答应说清：盘上有什么，条款为什么适用，哪些例外会改变判断。“藏干”是地支中所含的天干，“透干”是它也出现在天干一排；字出现在哪里可以核算，它是否有力、能否起到救应作用还需解释。某条路径不成立，不等于整个盘“失败”。

工具会在容易说错的地方直接给出 `say` 句子：真太阳时比钟表多或少几分钟、时辰未知时各钟表时段对应哪一柱、每步大运的周岁和虚岁、大运配法判喜判忌、格局只到候选、合婚按合冲刑害分组。回答照抄这些句子，不自己换算。字段清单见 [MIGRATION-5.10](skills/chinese-fortune/docs/MIGRATION-5.10.md)，6.0 的接口变化（统一结果信封、错误分类、新入口）见 [MIGRATION-6.0](skills/chinese-fortune/docs/MIGRATION-6.0.md)。

八字默认采用《子平真诠》的月令格局，《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》用于对应问题的补充与对照，分歧分别说明。六爻用神不上卦时按《增删卜易》找伏神；紫微格局按《紫微斗数全书》原句判定，每格给段号、原句和成格、加分、破格、待核四组条件。

[八家规则](skills/chinese-fortune/docs/BAZI-RULES.md) · [输出契约](skills/chinese-fortune/references/22-output-contract.md) · [方法路由](skills/chinese-fortune/SKILL.md#方法路由) · [迁移与验证](skills/chinese-fortune/docs/OUTPUT-VALIDATION.md)

</details>

<details>
<summary>古籍来源与发行包</summary>

古籍库收《子平真诠》《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》《协纪辨方书》《选择要略》《增删卜易》《紫微斗数全书》《梅花易数》《六壬大全》《遁甲演义》《奇门遁甲元灵经》和两个版本的《焦氏易林》。不同版本卷数不同，收录范围按所选目录说明；“全文完整”只指所选版本目录收齐，不表示所有版本汇编、逐页影像校勘或全书规则自动实现。每部书的来源、授权和限制见 [来源说明](skills/chinese-fortune/docs/CLASSICAL-SOURCES.md)，调候、紫微与六爻的条款范围见 [内容覆盖](skills/chinese-fortune/docs/CONTENT-COVERAGE.md)。

运行包保留全部选定章节及索引，原始 HTML/wiki 来源材料另放 `*-sources.zip`，普通使用无需下载。两包都附 SHA256SUMS，运行包声明自己的验证范围。

</details>

## 参与开发

欢迎提 issue 和 PR，流程与验收要求见 [CONTRIBUTING](CONTRIBUTING.md)。以下在源码仓库根目录运行：

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy skills/chinese-fortune/scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python skills/chinese-fortune/scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

正式发行从完整提交 SHA 构建，经新环境安装与实际 ZIP 检查后发布同一份 CI 产物，见 [发布流程](skills/chinese-fortune/docs/RELEASE-PROCESS.md)。实际模型回答评估与确定性测试分开，保留失败记录。

## 许可证

项目代码采用标准 [MIT](LICENSE)。随包依赖、移植代码、古籍转录及现实参考正文保留各自条款和署名，见 [第三方声明与许可全文](skills/chinese-fortune/THIRD_PARTY_NOTICES.md)。[产品免责声明](skills/chinese-fortune/DISCLAIMER.md) 单独列出，不增加许可限制。这些文件随安装目录、运行包和古籍来源包分发。
