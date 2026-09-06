# Chinese Fortune · 古籍与八字研习

把出生资料算成盘面，再对照古籍解释。重点是让人看懂：先回答问题，用白话说明依据，必要时附短古文。

默认以《子平真诠》的月令格局为主线。《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》用于对应条款的补充与对照。不同体系的结论分开说明。

## 能做什么

- 排八字，处理出生地时区、夏令时、真太阳时和未知时辰。
- 查询五部核心古籍的固定版本原文，返回章节、段落编号和相邻上下文。
- 提供月令、透干、藏干等实际盘面依据，辅助逐项检查古籍条件。
- 按用户当前所在地取得“今天”和“今年”，同次计算复用同一个时刻。
- 用户点名时使用紫微、六爻、周易等其他方法。具体范围见 [方法路由](SKILL.md#方法路由)。

默认解读不使用工程旺衰评分、神煞吉凶套语、生肖分数或五格姓名结论。诊断接口保留计算信息，便于检查历史结果；这些信息不等于古籍判断。

## 开始使用

需要 Python 3.11 或以上，以及能读取技能文件、运行 Python 的宿主。安装与测试基线为 Python 3.11 / 3.12。

1. 从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载对应版本 ZIP，解压。
2. 进入解压后的 chinese-fortune 文件夹，运行：

```sh
python -m pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
```

3. 按宿主的技能安装方式导入这个文件夹。宿主需要读取 SKILL.md，并能在同一 Python 环境运行 scripts/ 下的工具。
4. 确认工具能运行：

```sh
python scripts/classical_search.py --validate
python scripts/request_time.py --current-timezone Australia/Sydney
```

出现“缺少依赖”时，先确认安装命令和运行命令使用同一个 Python。出现时区错误时，提供城市对应的 IANA 时区，例如 Asia/Shanghai 或 Australia/Sydney。

可以这样提问：

> 我出生于 1990 年 5 月 10 日 14:30，男，出生地北京，现在住悉尼。请用白话解释这个盘的主要结构，重点说判断依据。

> 《子平真诠》如何理解用神？请给原文位置，再用白话解释。

仅查古籍不需要出生资料。排盘时不知道时辰就直接说明，系统保留三柱，不猜时间。

## 直接运行

白话盘面说明：

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --current-timezone Australia/Sydney --markdown
```

这是可核对的盘面说明；完整个人解读仍需宿主阅读相关原文、检查条件并回答用户的问题。省略 --markdown 可取得结构化事实和原文检索结果。

查原文：

```sh
python scripts/classical_search.py --list-books
python scripts/classical_search.py --book ziping --query 用神
python scripts/classical_search.py --passage-id ziping:c008:p0001
```

脚本参数见 python scripts/<脚本名>.py --help。明确历史或未来时刻时传目标日期时间；需要复现同次计算时，把 request_time.py 返回的 utc 传给后续工具的 --request-time。

## 怎么看结果

好的回答应直接说明三件事：盘上有什么、古籍为什么这样解释、哪些条件尚未满足。术语随文解释，古文作为依据，不让用户先读懂一串术语。

“藏干”表示地支中包含的天干；“透干”表示它也出现在天干一排。查到这些位置不自动表示格局成立。时柱未知或条款条件不足时，会明确说明影响范围。

[正文示例](docs/OUTPUT-EXAMPLE.md) · [输出规则](references/22-output-contract.md) · [迁移与验证](docs/OUTPUT-VALIDATION.md)

## 古籍库的完整性

以 knowledge/manifest.json 冻结的作品、版本和目录为准：

- **全文收录**：逐章保存，检查目录、文件和段落摘要，缺章不能通过完整性检查。
- **来源可追溯**：每段保留来源、版本、章节和文字层次。
- **规则可用**：个人解释还需检查该条的前提与例外。全文收齐不代表所有规则已经自动实现。
- **影像校勘**：单独记录，未实际校勘就不标为已校。

[来源与授权记录](docs/CLASSICAL-SOURCES.md) 说明各书采用的版本、收录范围和尚存问题。古籍记载与现实预测效果分别验证，不把测试通过率当命中率。

## 开发和验证

以下命令在 Git 源码仓库执行；发行 ZIP 只含运行文件，不含开发依赖与测试集。

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python -X utf8 evals/run_checks.py --checks-only
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

--checks-only 用于前一步完整 pytest 已通过的情况。CI 结果见 [Actions](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)。实际回答评估与工程测试分开，见 [验证说明](docs/OUTPUT-VALIDATION.md)。

## 项目范围和许可

当前主线是八字五书及其可核查的解释。其他方法按各自覆盖范围开放，不自动混入综合结论；见 [可选方法](references/23-optional-methods.md)。

代码采用 [MIT](LICENSE)。古籍原作、转录整理和来源页面的授权分别记录于知识库清单及来源说明；不能把代码的 MIT 许可套用到所有第三方资料。

用于传统文化研习。医疗、法律、投资等现实决定应依据相应专业信息。
