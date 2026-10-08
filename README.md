# Chinese Fortune · 古籍与白话解读

[![skills.sh](https://www.skills.sh/b/shousenzhang/chinese-fortune)](https://skills.sh/shousenzhang/chinese-fortune)
[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ShousenZHANG/chinese-fortune)](https://github.com/ShousenZHANG/chinese-fortune/releases)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](#安装)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

让你的 AI 按古籍原文算八字、挑日子、看运势：先用大白话直接回答，引用的原文都附出处和白话解释；干支、吉凶等级、大运喜忌都由程序计算，不让 AI 凭记忆编。也能按《高性价比人生指南》回答现实生活问题。

[English](README.en.md) · [安装](#安装) · [这样问](#装好后这样问) · [能做什么](#能做什么) · [更新与卸载](#更新与卸载)

## 安装

**最省事：把这句话发给你的 AI**

> 安装这个 Skill：https://github.com/ShousenZHANG/chinese-fortune

**Claude Code**

```text
/plugin marketplace add ShousenZHANG/chinese-fortune
/plugin install chinese-fortune@chinese-fortune
```

**Codex、Cursor、GitHub Copilot、Gemini CLI 等**

```sh
npx skills add ShousenZHANG/chinese-fortune
```

Gemini CLI 也可以用自带命令：`gemini skills install https://github.com/ShousenZHANG/chinese-fortune`。

**claude.ai、ChatGPT、Claude API**：从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载 `chinese-fortune-v版本号.zip`。claude.ai 在 Settings > Features 上传；ChatGPT（Business、Enterprise、Edu）在 Plugins > Skills 上传；Claude API 用 Skills API 上传。

只需 Python 3.9 或以上（macOS 自带的 `python3` 就够），不用 pip 安装任何包，计算不联网：排盘库 lunar_python 和时区数据 tzdata 已随包附带。CI 在 Python 3.9、3.11、3.12 上验证。

<details>
<summary>给 AI 的安装说明</summary>

1. 按用户用的宿主选上面一种安装方式。拿不准时用 Release 里的 zip，解压到宿主的技能目录（Claude Code `~/.claude/skills/`，Codex `~/.codex/skills/`，Gemini CLI `~/.gemini/skills/`），应得到 `chinese-fortune/SKILL.md`。
2. 不要运行 pip。依次试 `python3`、`python`、`py -3`，找一个 3.9 以上的；都没有时征得用户同意再装 Python（命令见 SKILL.md「运行环境与诊断」）。
3. 在 chinese-fortune 文件夹里自检，两条都返回 `"ok": true` 就装好了：

```sh
python scripts/classical_search.py --validate
python scripts/request_time.py --current-timezone Asia/Shanghai
```

</details>

## 装好后这样问

问到命理时，AI 会先问这道题用得上的出生资料（日期、时间、出生地、性别）和你现在住的城市；时间记不清可以给范围，比如 19–20 点。

| 想知道 | 可以这样问 |
|---|---|
| 八字命局 | 我出生于 1990 年 5 月 10 日 14:30，男，北京出生，现在住悉尼。请用白话解释八字的主要结构，说明哪些条件成立、哪些地方有分歧。 |
| 哪天对我好 | 下个月哪天搬家好？未来七天哪天对我好？ |
| 面试、考试几点 | 下周二上午和周四下午能面试，每次一小时，选哪个？ |
| 大运、流年 | 我现在这步大运好不好？2027 年运势怎么样？ |
| 穿什么、戴什么 | 我穿什么颜色、戴什么对自己有利？ |
| 黄历、六爻 | 10 月 29 日搬家可以吗？用六爻看下周二的面试。 |
| 查古籍 | 《子平真诠》怎么理解用神？先解释意思，再给原文位置。 |
| 现实生活 | 失业了先做什么？替朋友担保签不签？ |

只查古籍不需要生辰。时辰不知道就直说，程序保留可固定的柱；交节或日界附近，年、月、日柱也可能需要比较候选。

## 回答长什么样

输入出生资料，先排出可核对的盘面，再按古籍条件解释。回答先用大白话直接回答问题；后面引用短原文，每段古文后立即解释它是什么意思、为什么与你的情况有关。

八字默认采用《子平真诠》的月令格局。《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》用于对应问题的补充与对照，分歧分别说明。

下面节选自[白话输出示例](docs/OUTPUT-EXAMPLE.md)（依据固定测试盘撰写，不是真实用户预测）：

> 不能直接给你一个“补某种五行就好”的答案。按这套古法，盘中一条约束关系比较突出，同时还有削弱它和支持它的关系，需要放在一起看；不能只抓住一个名称就判好坏。
>
> 《子平真诠》说：“八字用神，專求月令。”这里的“用神”是从出生月份确定分析的起点；本例先看己土正官，并不等于“最缺什么就补什么”。
>
> 所以，本例能完成的判断是：**以正官为主线，财与伤官同时参与；直接套“官印相生”或“伤官见官必坏”都不合适。**

## 能做什么

| 方法 | 能回答 | 依据 |
|---|---|---|
| 八字命局 | 格局、用神、成败条件 | 《子平真诠》月令格局为主，《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》对照；八家 25 条核查路径 |
| 大运 | 这步运是喜是忌 | 《子平真诠》取运章：正官、财、伤官三家已接，其余五家未接 |
| 流年 | 某一年、今年、明年 | 《渊海子平》《三命通会》《滴天髓》论太岁与岁运，逐条列关系，不合总分 |
| 个人择日、期间运势 | 哪天好、哪天要避开 | 《协纪辨方书》卷三十三相主，按出生年干支分大吉到大凶 |
| 择时 | 面试、考试、出行、搬家几点 | 相主加事项忌日；面试、考试另接《奇门遁甲元灵经》 |
| 穿戴、颜色、方位 | 穿什么颜色、戴什么 | 《穷通宝鉴》调候的一般取法（这一格的例外未按本人盘逐条核对） |
| 黄历 | 某天宜忌 | 《协纪辨方书》《渊海子平》有出处的忌日条款 |
| 紫微、六爻、周易、梅花、奇门、六壬 | 点名时使用 | 各书固定转录，按实际覆盖解释 |
| 古籍检索 | 原文、版本、上下文 | 十三部固定转录，535 个章节或卷单元、18,982 段，离线可查 |
| 现实生活问题 | 失业、担保、押金、保险等 | 《高性价比人生指南》34 节 660 条、8 篇长文；急症和自伤念头先给第一个动作 |

- 排八字，处理出生地时区、夏令时、真太阳时、日界和未知时辰。
- 离线检索十三部固定转录版古籍：535 个章节或卷单元、18,982 段，返回原文位置、版本和上下文。
- 按官、财、印、食、杀、伤、阳刃、禄劫八家整理 25 条核查路径，区分盘面事实、成立条件和例外。
- 每次先获取用户现居地时间；同一次解读复用该时刻，出生时间与所问时间另行处理。
- 点名时使用紫微、六爻、周易等方法，按各自实际覆盖解释。

完整转录库、已整理规则、影像校勘是不同进度。八家条件中，可计算的部分由程序核实；强弱、配合和救应的作用由宿主结合完整原文解释。测试通过不代表现实预测命中率。

## 为什么可信

- **程序算，AI 讲**：干支、十神、吉凶等级、大运喜忌都由随包脚本计算，AI 只把结果讲成白话，不自己另算。
- **每个结论都有出处**：引文附书名和段落编号，可以用 `classical_search.py --passage-id` 原样查到。
- **说不清就照说**：几个选项等级相同、条件还没核完、几本书说法相反，回答会直说，不替你挑，也不按条数投票。
- **时间算准**：出生地时区、夏令时、真太阳时、日界、节气交接分开处理；出生时间只记得范围，也能逐分钟比较所有可能。
- **可以事后检验**：你同意跟踪后，事前冻结判断，事后记录实际结果，见[前瞻验证](references/28-prospective-validation.md)。

## 隐私与数据

排盘、择日和古籍检索都由随包脚本在你的电脑（或宿主的沙盒）里运行，不联网，也不会自动保存你的出生资料或问答；你和 AI 的对话照常经过你所用的 AI 服务。唯一会联网的是起卦时你主动选用的量子随机源，它只取一串随机数，不带任何个人信息，取不到就改用本机随机数。

经你确认后，也可单独保存本机出生档案，支持查看、更正和删除。默认放在 `~/.local/share/chinese-fortune`，不进入仓库或发行包；每次计算不会自动保存整段问答。

## 更新与卸载

| 安装方式 | 更新 | 卸载 |
|---|---|---|
| Claude Code 插件 | `claude plugin marketplace update chinese-fortune`，再 `claude plugin update chinese-fortune@chinese-fortune` | `claude plugin uninstall chinese-fortune@chinese-fortune` |
| npx skills | `npx skills update chinese-fortune` | `npx skills remove chinese-fortune` |
| Gemini CLI | 卸载后重新安装 | `gemini skills uninstall chinese-fortune` |
| zip 上传 | 下载新版 zip 重新上传 | 在宿主的 Skills 设置里删除 |

每个版本的变化见 [CHANGELOG](CHANGELOG.md)。

## 详细说明

### 通用问题怎样回答

可以问求职、面试、出行、约会沟通、学习考试或其他生活事项。系统先明确你问的事情，复用已确认的个人资料，分别处理出生地、当前所在地与事件时间。新场景也能进入同一流程，能给出的结论取决于找到的适用依据。

回答默认约300–600字：先用自然白话说结果，再给必要的古籍短引文，每段引文后马上说明它是什么意思、与你的情况怎样对应。已有依据先答；材料不足时，宿主使用现有检索工具补查约5分钟，并记录实际找到什么。网络或检索工具不可用会如实说明。

想选时间时，一次给出可用日期、每天可用时段和持续时间。有多个同档候选，再说明希望尽早、尽晚或自己的优先顺序。结果给出明确的日期、开始与结束时间、时区以及可用备选，清楚区分古法判断与实际安排理由。只有一个窗口时，也只说它为什么排得下，不称它是未经比较的命理最优。

出生时间只记得19–20点时，可以保留这个范围，比较所有有效钟面分钟的共同盘面；不擅自选19:30，也不直接丢掉整段信息。原文查询随带已记录的版本异文。补查材料保存到外部候选库，复核记录与可执行规则分别管理。

**哪天对你好、哪天不好，按《协纪辨方书》卷三十三「相主」直接给出。** 相主看的是出生那一年的干支（原文「從來皆論生年不論生日」），拿所选时间的年、月、日、时四柱去比：太岁或月建冲你，挑哪天都避不开，回答会先说这一条，不会把这样的日子叫作吉。每一天分大吉、吉、平、小凶、凶、大凶，理由与原文随答附上；问一段时间就列最好的和要避开的日子，比较候选档期就先按吉凶排、再按你的偏好排。出行、婚嫁、搬家、开业另有一组事项忌日（《渊海子平》天地转杀，以及协纪自称吉神不能化解的月破、四废、四忌四穷、往亡、归忌）先行排除。问穿什么颜色、戴什么，按《穷通宝鉴》这一格调候的一般取法换算颜色和饰物，每一环附出处；这一格的例外（如「丙丁过多与水局另论」）还没按你的盘逐条核对，回答会说明，也不给「少穿」的颜色。用完整命局合参喜忌来判断个人运势，仍未实现。

- [输入与时间选择](references/24-personalized-forecast.md#通用请求与明确时间)
- [约5分钟补查与候选库](references/25-classical-research.md#限时补查与候选库)
- [自然白话输出](references/27-direct-answer.md)

### 问这两天、下周和面试时间

现在可以接收这类问题，明确实际日期范围，分别计算你的出生盘与目标年月日时，核查大运交接，并筛掉已过期、冲突或时间不够的候选档期。出生地、你现在的位置、未来事件的地点分别处理。

择时会列出每个可行窗口最早、最晚能开始的时间，覆盖整件事的持续过程，包括途中换时辰、交节或夏令时变化。只在你有空的时段细算，重叠档期复用结果。生时、地点经度、多人主次与依据缺口分别提示，不会互相覆盖。

面试、考试还会自动接入《元灵经》已核的地盘、值符和值使，覆盖整个候选窗口，并核对各人的出生年干落宫。未核的星门不填猜测值，年干核对也不冒充完整八字排名。

连续安排也可一起检查：按你指定的顺序，核对每件事的可选窗口、持续时间、跨城时区和交通准备时间；同一人的出生盘复用。输出可行行程示例，明确区分“排得下”和“命理首选”。

另外接入了《子平真诠》的两种具体运程例式。只有你的出生条件与大运实际符合时，才解释对应的同类、相冲或相合关系，并附原文和白话说明；这些结构核查不代替整体运势判断。

**个人逐日吉凶已按《协纪辨方书》相主实现**：看你出生那一年的干支，把所选时间的年、月、日、时一起比，给出大吉到大凶，依据和等级都来自原文。它不是完整八字合参；出行、嫁娶、搬家、开业在协纪「民用三十七事」里，其余事项是借用这套方法，回答里会写明。下表由 `python scripts/fortune_rules.py --capabilities-markdown` 生成，和代码不一致时测试会失败。

<!-- capability-table:start -->
| 事项 | 流程 | 个人吉凶（相主） | 原文授权 | 事项忌日 | 现实参考 |
|---|---|---|---|---|---|
| 阶段运势（`outlook`） | 期间 | 已实现 | 借用 | — | — |
| 面试（`interview`） | 择时 | 已实现 | 借用（最接近「上官」） | — | 第31节、第19节 |
| 工作沟通、谈薪、转岗（`work_conversation`） | 择时 | 已实现 | 借用 | — | 第31节、第19节 |
| 学习考试（`exam`） | 择时 | 已实现 | 借用（最接近「入學」） | — | 第23节、第31节 |
| 约会、感情沟通（`relationship_conversation`） | 择时 | 已实现 | 借用（最接近「會親友」） | — | 第10节 |
| 出行（`travel`） | 择时 | 已实现 | 协纪民用事「出行」 | 已实现 | 第13节、第21节 |
| 订婚、领证、婚礼（`wedding`） | 择时 | 已实现 | 协纪民用事「嫁娶」（只含婚礼） | 已实现 | 长文、第10节 |
| 搬家、入住（`moving`） | 择时 | 已实现 | 协纪民用事「移徙」 | 已实现 | 第15节 |
| 开业、产品与作品发布（`business`） | 择时 | 已实现 | 协纪民用事「開市」（只含开业） | 已实现 | 第12节 |
| 报价、催款（`billing`） | 择时 | 已实现 | 借用（名目有納財、交易、立券，未核是否对应） | — | 第9节、第12节、第8节 |
| 连续行程（`multiple_events`） | 连续行程 | — | — | — | — |
| 关系匹配（`compatibility`） | 专项 | — | — | — | 第10节 |
| 起名改名（`naming`） | 专项 | — | — | — | — |
| 城市与场所比较（`location`） | 专项 | — | — | — | — |
| 环境与风水（`fengshui`） | 专项 | — | — | — | — |
| 复盘纠错（`review`） | 专项 | — | — | — | — |
<!-- capability-table:end -->

「现实参考」一列是回答末尾可能附上的《高性价比人生指南》条目，按所在地筛选，不参与术数判断。

纯现实问题（失业了先做什么、替朋友担保签不签、通勤两小时值不值）走人生决策流程：从冻结的《高性价比人生指南》（eternity4719/HowToLiveBetter，提交 `842e11c9`，正文 CC BY 4.0，移植的检索和决策流程 MIT）里查条目，先看贴合程度，再按书里的算法排性价比和证据等级，分先做和别做，每条注明第几节第几条，书里没写的部分照实说；急症、自伤念头和正在进行的法律程序先给第一个动作，求助电话只给在中国大陆的人。本库收录除 3 条外的全书：34 节 660 条、8 篇长文、各节导读、术语表，以及解析好的交叉引用。命理问题优先走术数流程。详见 [人生决策](references/29-life-decision.md)。

可以这样问：

> 结合我已确认的出生资料，看下周的情况。先说能核实的结论，再解释古籍依据；区分整段背景和每天的差别。

> 我下周二上午和周四下午能面试，每次一小时，地点悉尼。先核对档期，再查有没有适用于我的古籍择时依据。

输入字段、当前覆盖和实际操作见 [个人未来时段与择时](references/24-personalized-forecast.md)。工具入口是 `python scripts/fortune_reading.py --stdin`；它通过标准输入接收 JSON，普通使用由宿主根据对话填写。`--markdown` 是事实与缺口草稿，完整解释还须查证。

### 直接运行脚本

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --question 解释主要结构 --markdown
```

`--markdown` 输出盘面和条件核查草稿。完整解读由宿主继续检查本题相关解释条件，再回答问题。省略该参数可取得结构化盘面、规则条件和完整证据组。

黄历与六爻也有白话输出。黄历带 `--question` 时首句先回答所问之事（出行、结婚、搬家、开业），依据有出处的忌日条款，并指出通书宜忌表与条款不一致之处；六爻说明用神取哪一爻、出处和旺衰，不下成败断语。

```sh
python scripts/huangli_query.py --date 2026-10-29 --question 这天搬家可以吗 --markdown
python scripts/liuyao_cast.py coins --question 下周二面试能过吗 --current-timezone Asia/Shanghai --markdown
```

查书与原文：

```sh
python scripts/classical_search.py --list-books
python scripts/classical_search.py --book ziping --query 用神
python scripts/classical_search.py --passage-id ziping:c008:p0001
```

同请求复现时间时，把 request_time.py 返回的 utc 传给后续计算的 `--request-time`。用户现居地用 `--current-timezone`，出生地用 `--city` 或经度与出生时区；历史、未来问题使用明确目标时间。

参数详情见 `python scripts/<脚本名>.py --help`。默认八字工具不输出工程旺衰、神煞断语或唯一用神，也不需要为找旧字段重复调用诊断工具。

### 结果应该怎样读

回答应说清：盘上有什么，条款为什么适用，哪些例外会改变判断。

“藏干”是地支中所含的天干；“透干”是它也出现在天干一排。字出现在哪里可以核算，它是否有力、能否起到救应作用还需解释。某条路径不成立，不等于整个盘“失败”。

古文、注文和项目整理分别标明。不会从一颗星直接断配偶行为、疾病或收入；现实建议结合用户已知处境。采用 Caveman 的简洁原则，保留自然中文、原因和关键条件。

[八家规则](docs/BAZI-RULES.md) · [输出契约](references/22-output-contract.md) · [方法路由](SKILL.md#方法路由) · [迁移与验证](docs/OUTPUT-VALIDATION.md)

### 古籍怎样用于你的问题

新增《协纪辨方书》《选择要略》《增删卜易》《紫微斗数全书》《梅花易数》《六壬大全》《遁甲演义》《奇门遁甲元灵经》的固定转录材料。不同版本卷数不同，收录范围按所选目录说明，不宣称所有古籍全版本齐全。

面试、考试、出行等16类需求有对应研究入口；八类八字取运可读完整章节、例外与条件清单。起名字源、完整阳宅布局等仍明确列出独立资料缺口。

```sh
python scripts/classical_guidance.py --scenario interview --retrieve --limit 1
python scripts/classical_guidance.py --family 伤官
python scripts/classical_search.py --chapter-id ziping:c026 --limit 10
```

收到原文之后，还要核对本人的条件和计算方法。新增书目不意味着所有个人预测或面试排名已经可用；详见[古籍适配与补查](references/25-classical-research.md)。

部分禁忌写在几个事项之后，检索已补上这些远处的共用条件。例如查纳财会同时带回“前五条俱忌”，查出行会带回后文追加禁忌。已发现的断句与字形问题保留说明，尚未核清的条件不会自动变成结论。

### 古籍与发行包

运行包保留十三书全部选定章节及索引，原始 HTML/wiki 来源材料另放 `*-sources.zip`，普通使用无需下载。两包都附 SHA256SUMS；运行包明确声明自己的验证范围，缺文件不会因“没有来源目录”而跳过检查。

“全文完整”只指所选版本目录收齐，不表示所有版本汇编、逐页影像校勘或全书规则自动实现。每部书的来源、授权和限制见 [来源说明](docs/CLASSICAL-SOURCES.md)。调候、紫微与六爻的条款范围见 [内容覆盖](docs/CONTENT-COVERAGE.md)。

### 怎样检验回答是否可靠

先固定方法和问题范围，再逐条说明你的哪些信息符合哪条依据；依据冲突就说清楚，不靠换算法凑肯定答案。回答仍然先用白话直说，再给短引文和白话解释。

你同意跟踪后，可以在事情发生前保存原判断，之后确认实际结果；支持查看、更正和删除。记录保存在仓库外，不重复保存生辰。统计同时显示未能判断、待确认及删除数量，按相同方法、版本和事件定义分组。这是检验机制，不是已经证明能预测现实事件。操作见 [前瞻验证](references/28-prospective-validation.md)。

## 参与开发

欢迎提 issue 和 PR，流程与验收要求见 [CONTRIBUTING](CONTRIBUTING.md)。

以下在源码仓库运行，发行包不含开发测试：

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

正式发行从完整提交 SHA 构建，经新环境安装与实际 ZIP 检查后发布同一份 CI 产物。详见 [发布流程](docs/RELEASE-PROCESS.md) 与 [CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)。实际模型回答评估与确定性测试分开，保留失败记录。

## 许可证

代码采用 [MIT](LICENSE)，第三方古籍转录保留各自授权。用于传统文化研习；现实医疗、法律和投资决定依据相应专业信息。
