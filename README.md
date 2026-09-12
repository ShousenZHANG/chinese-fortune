# Chinese Fortune · 古籍与白话解读

输入出生资料，先排出可核对的盘面，再按古籍条件解释。回答先用大白话直接回答问题；后面引用短原文，每段古文后立即解释它是什么意思、为什么与你的情况有关。

八字默认采用《子平真诠》的月令格局。《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》用于对应问题的补充与对照，分歧分别说明。

## 能做什么

- 排八字，处理出生地时区、夏令时、真太阳时、日界和未知时辰。
- 离线检索十三部固定转录版古籍：535 个章节或卷单元、18,982 段，返回原文位置、版本和上下文。
- 按官、财、印、食、杀、伤、阳刃、禄劫八家整理 25 条核查路径，区分盘面事实、成立条件和例外。
- 每次先获取用户现居地时间；同一次解读复用该时刻，出生时间与所问时间另行处理。
- 点名时使用紫微、六爻、周易等方法，按各自实际覆盖解释。

完整转录库、已整理规则、影像校勘是不同进度。八家条件中，可计算的部分由程序核实；强弱、配合和救应的作用由宿主结合完整原文解释。测试通过不代表现实预测命中率。

## 问这两天、下周和面试时间

现在可以接收这类问题，明确实际日期范围，分别计算你的出生盘与目标年月日时，核查大运交接，并筛掉已过期、冲突或时间不够的候选档期。出生地、你现在的位置、未来事件的地点分别处理。

择时会列出每个可行窗口最早、最晚能开始的时间，覆盖整件事的持续过程，包括途中换时辰、交节或夏令时变化。只在你有空的时段细算，重叠档期复用结果。生时、地点经度、多人主次与依据缺口分别提示，不会互相覆盖。

面试、考试还会自动接入《元灵经》已核的地盘、值符和值使，覆盖整个候选窗口，并核对各人的出生年干落宫。未核的星门不填猜测值，年干核对也不冒充完整八字排名。

连续安排也可一起检查：按你指定的顺序，核对每件事的可选窗口、持续时间、跨城时区和交通准备时间；同一人的出生盘复用。输出可行行程示例，明确区分“排得下”和“命理首选”。

另外接入了《子平真诠》的两种具体运程例式。只有你的出生条件与大运实际符合时，才解释对应的同类、相冲或相合关系，并附原文和白话说明；这些结构核查不代替整体运势判断。

**个人逐日吉凶和“最适合你的面试时段”仍是部分完成。** 目前工具能核算个人关系与现实档期，但还没有经完整古籍条件验证的排名算法。已有运程依据可继续核查并解释背景；缺日、时依据时先补查，不把通用黄历或生克关系包装成个人首选。查证仍不足，就明确说哪一部分算不了。

可以这样问：

> 结合我已确认的出生资料，看下周的情况。先说能核实的结论，再解释古籍依据；区分整段背景和每天的差别。

> 我下周二上午和周四下午能面试，每次一小时，地点悉尼。先核对档期，再查有没有适用于我的古籍择时依据。

输入字段、当前覆盖和实际操作见 [个人未来时段与择时](references/24-personalized-forecast.md)。工具入口是 `python scripts/fortune_reading.py --stdin`；它通过标准输入接收 JSON，普通使用由宿主根据对话填写。`--markdown` 是事实与缺口草稿，完整解释还须查证。

经你确认后，也可单独保存本机出生档案，支持查看、更正和删除。默认放在 `~/.local/share/chinese-fortune`，不进入仓库或发行包；每次计算不会自动保存整段问答。

## 开始使用

需要 Python 3.11 或以上，以及能读取技能并运行 Python 的宿主。CI 验证 Python 3.11、3.12。

1. 从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载 `chinese-fortune-v版本号.zip`，解压。
2. 进入 chinese-fortune 文件夹，安装并检查：

```sh
python -m pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
python scripts/classical_search.py --validate
python scripts/request_time.py --current-timezone Australia/Sydney
```

3. 按宿主的技能安装方式导入文件夹。宿主需读取 SKILL.md，并用安装依赖的同一个 Python 运行工具。

可以这样问：

> 我出生于 1990 年 5 月 10 日 14:30，男，北京出生，现在住悉尼。请用白话解释八字的主要结构，说明哪些条件成立、哪些地方有分歧。

> 《子平真诠》怎么理解用神？先解释意思，再给原文位置。

只查古籍不需要生辰。时辰不知道就直说，程序保留可固定的柱；交节或日界附近，年、月、日柱也可能需要比较候选。

## 直接运行

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --question 解释主要结构 --markdown
```

`--markdown` 输出盘面和条件核查草稿。完整解读由宿主继续检查本题相关解释条件，再回答问题。省略该参数可取得结构化盘面、规则条件和完整证据组。

查书与原文：

```sh
python scripts/classical_search.py --list-books
python scripts/classical_search.py --book ziping --query 用神
python scripts/classical_search.py --passage-id ziping:c008:p0001
```

同请求复现时间时，把 request_time.py 返回的 utc 传给后续计算的 `--request-time`。用户现居地用 `--current-timezone`，出生地用 `--city` 或经度与出生时区；历史、未来问题使用明确目标时间。

参数详情见 `python scripts/<脚本名>.py --help`。默认八字工具不输出工程旺衰、神煞断语或唯一用神，也不需要为找旧字段重复调用诊断工具。

## 结果应该怎样读

回答应说清：盘上有什么，条款为什么适用，哪些例外会改变判断。

“藏干”是地支中所含的天干；“透干”是它也出现在天干一排。字出现在哪里可以核算，它是否有力、能否起到救应作用还需解释。某条路径不成立，不等于整个盘“失败”。

古文、注文和项目整理分别标明。不会从一颗星直接断配偶行为、疾病或收入；现实建议结合用户已知处境。采用 Caveman 的简洁原则，保留自然中文、原因和关键条件。

[八家规则](docs/BAZI-RULES.md) · [输出契约](references/22-output-contract.md) · [方法路由](SKILL.md#方法路由) · [迁移与验证](docs/OUTPUT-VALIDATION.md)

## 古籍与发行包

运行包保留十三书全部选定章节及索引，原始 HTML/wiki 来源材料另放 `*-sources.zip`，普通使用无需下载。两包都附 SHA256SUMS；运行包明确声明自己的验证范围，缺文件不会因“没有来源目录”而跳过检查。

“全文完整”只指所选版本目录收齐，不表示所有版本汇编、逐页影像校勘或全书规则自动实现。每部书的来源、授权和限制见 [来源说明](docs/CLASSICAL-SOURCES.md)。调候、紫微与六爻的条款范围见 [内容覆盖](docs/CONTENT-COVERAGE.md)。

## 开发与验证

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

代码采用 [MIT](LICENSE)，第三方古籍转录保留各自授权。用于传统文化研习；现实医疗、法律和投资决定依据相应专业信息。

## 古籍怎样用于你的问题

新增《协纪辨方书》《选择要略》《增删卜易》《紫微斗数全书》《梅花易数》《六壬大全》《遁甲演义》《奇门遁甲元灵经》的固定转录材料。不同版本卷数不同，收录范围按所选目录说明，不宣称所有古籍全版本齐全。

面试、考试、出行等16类需求有对应研究入口；八类八字取运可读完整章节、例外与条件清单。起名字源、完整阳宅布局等仍明确列出独立资料缺口。

```sh
python scripts/classical_guidance.py --scenario interview --retrieve --limit 1
python scripts/classical_guidance.py --family 伤官
python scripts/classical_search.py --chapter-id ziping:c026 --limit 10
```

收到原文之后，还要核对本人的条件和计算方法。新增书目不意味着所有个人预测或面试排名已经可用；详见[古籍适配与补查](references/25-classical-research.md)。

部分禁忌写在几个事项之后，检索已补上这些远处的共用条件。例如查纳财会同时带回“前五条俱忌”，查出行会带回后文追加禁忌。已发现的断句与字形问题保留说明，尚未核清的条件不会自动变成结论。
