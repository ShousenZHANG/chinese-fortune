# 贡献指南 · Contributing

项目主线是可追溯的五部八字古籍、可靠排盘和有条件的白话解释。当前以《子平真诠》月令格局为主，其他四书作补充对照。不同体系不自动合并。

## 内容修改

- 引用必须指到知识库中的版本、章节、段落和文字层次。正文、古注与现代解释分开。
- 新增条款须写明适用条件、例外和盘面证据。取到原文不等于已经证明条款适用。
- 不把工程评分当古籍规则，不用无校准的百分比表达预测把握。
- 先用自然中文回答问题，术语随文解释，古文只作必要依据。
- 改动输入、输出或默认取法时，同步更新 SKILL.md、README 中英文版、参数帮助、用例和迁移说明。

五书版本与收录范围见 [来源记录](docs/CLASSICAL-SOURCES.md)。采集工具 scripts/import_classics.py 仅供维护；重新采集后审核差异和授权，不能用网络新内容静默覆盖已经冻结的段落。

可选解梦、姓名和生肖材料不得恢复无出处的人生断语。神煞只保留起法命中，不凭单一标签断吉凶。

## 开发与验收

需要 Python 3.11+；CI 使用 3.11 / 3.12。上游维护 main，依赖由维护者核查后更新。外部贡献可在自己的 fork 中建立分支并提交 PR。

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python scripts/classical_search.py --validate
python scripts/build_skill.py --dist-dir dist
python -X utf8 evals/package_smoke.py --archive dist/chinese-fortune-v<VERSION>.zip
```

日常定位问题可先运行 `python -X utf8 -m pytest tests/ -q -m "not slow"`。这只是一组明确排除长网格测试的快速检查，不能替代完整 CI/发布验收。CI 不排除 slow，Python 3.11/3.12 完整运行，Windows 另做安装、UTF-8 与历史时区检查。

唯一的测试入口是 pytest；原 `evals/run_checks.py` 的独有命令行黄金断言、Markdown 可达性和发行检查已迁入 `tests/test_harness_gates.py`，不再二次启动同一套检查。坏输入契约在 `test_cli_contract.py`，全库/安装验证分别在古籍测试与 `package_smoke.py`。

覆盖率通过 coverage 的 subprocess patch 计入脚本子进程，`source=["scripts", "evals"]`，总门槛仍为 80%；构建工具也计入分母。CI 另按运行时代码与维护工具报告同一份数据，不把分组报告当作新的较低门槛，也不据此宣称预测更准。

会改写共享源码的 `evals/mutate.py` 已删除。需要测试变异时，在临时副本或内存中完成；六爻宫序与世应已有 64 卦独立预期及内存错移回归，不能恢复原地改写后再尝试还原的维护方式。

Python 输出使用 utils 的 JSON 信封；失败包含 ok、tool、version、error、message，退出非零。错误不能被转换成看似成功的命盘。缺少必需依赖时明确报错，不用简化表补出结果。

当前时间统一从 request_time.py 取得，同次计算复用同一 UTC 时刻。出生地时区、当前所在地时区和查询目标时间分别处理。测试使用明确时间，不能依赖运行测试机器的日期。

JSON 使用 UTF-8、两空格缩进。代码需类型注解。测试应证明输入边界、来源完整性或实际行为，不能只搜索提示词或机械复制实现。

## 发布记录

记录提交、测试、包内验证与远端 CI。工程测试、实际模型回答评审和现实预测验证分别报告。30 个用例清单不是 30 次模型运行；协作 agent 的试跑也不是多个独立宿主的基准。

正式发布使用固定提交构建和受测 CI 的原始产物，不在发布步骤重新打包。流程见 [发布与来源归档](docs/RELEASE-PROCESS.md)。开发包会标明 development/dirty，不因无关未跟踪文档阻止构建。

提交说明写清具体问题、改后行为、验证结果和仍有限制。古籍原作与转录页面授权分别处理，代码 MIT 不覆盖所有第三方资料。

## English

The primary scope is the five declared BaZi classics, deterministic chart calculation and readable, conditional interpretation. Zi Ping Zhen Quan is the primary method; other texts are compared explicitly.

Every quotation needs an edition, chapter, passage and text layer. New interpretations need applicability conditions, exceptions and chart evidence. Do not turn engineering scores into classical authority or invent prediction probabilities.

Keep both READMEs, skill routing, CLI help, fixtures and migration notes aligned. Run the commands above. A local `-m "not slow"` run is only a quick subset; CI and releases require all tests. Verify the exact built archive in a fresh environment and publish the tested CI bytes, including their checksums and source archive.

Obtain request time once, using the user's present time zone; keep it separate from birth and target time zones. Preserve failures as explicit errors rather than fabricating successful charts.

Report code tests, actual model-response reviews and predictive validation separately. Preserve attribution and edition boundaries when importing texts. Respect the scope in [the output contract](references/22-output-contract.md) and [sensitive-topic guidance](references/20-disclaimer.md).
