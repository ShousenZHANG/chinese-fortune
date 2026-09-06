# Chinese Fortune · 古籍与白话解读

输入出生资料，先排出可核对的盘面，再按古籍条件解释。回答先说人能听懂的话，术语随文解释，古文只作必要依据。

八字默认采用《子平真诠》的月令格局。《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》用于对应问题的补充与对照，分歧分别说明。

## 能做什么

- 排八字，处理出生地时区、夏令时、真太阳时、日界和未知时辰。
- 离线检索五部固定转录版古籍：416 个章节或卷单元、8,385 段，返回原文位置、版本和上下文。
- 按官、财、印、食、杀、伤、阳刃、禄劫八家整理 25 条核查路径，区分盘面事实、成立条件和例外。
- 每次先获取用户现居地时间；同一次解读复用该时刻，出生时间与所问时间另行处理。
- 点名时使用紫微、六爻、周易等方法，按各自实际覆盖解释。

完整转录库、已整理规则、影像校勘是不同进度。八家条件中，可计算的部分由程序核实；强弱、配合和救应的作用由宿主结合完整原文解释。测试通过不代表现实预测命中率。

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

运行包保留五书全部选定章节及索引，原始 HTML/wiki 来源材料另放 `*-sources.zip`，普通使用无需下载。两包都附 SHA256SUMS；运行包明确声明自己的验证范围，缺文件不会因“没有来源目录”而跳过检查。

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
