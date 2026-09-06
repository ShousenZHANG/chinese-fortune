# 输出验证与 v4 迁移

## 默认接口

`bazi_reading.py` 的 schema 2.0：

| 字段 | 说明 |
|---|---|
| chart_facts | 可固定盘面及时间口径，供同一次审核引用 |
| observed_structure | 月藏、明透与同字藏根的位置 |
| rule_assessment | 八家候选、25条路径、可计算与解释条件 |
| evidence_bundle | 完整段落与例外，按书章复用来源信息 |
| climate_review | 问调候、用神或喜忌时的逐格来源审核；其他问题为空 |
| reading_support | 初始盘面事实，宿主继续完成本题解释 |

`source_passages` 已由 evidence_bundle 替代。`ge_ju` 与 `yong_shen` 不在默认返回中；不要为它们再算一次。三个 `--no-*` 诊断开关从默认入口删除，内部保持关闭。明确诊断需求才用 bazi_calc.py。

八家条件分 met / not_met / unknown。存在和明透不同，月令候选与成格不同。审核器从盘面重算可计算条件；解释条件须附理由、盘面路径值和真实段落 ID。旧三条概念框架可作待核记录，不能只把条件全填 met 就认证个人解释。

`reading_support.py --stdin` 接收 `{"chart": 完整默认结果, "packet": 审核记录}`。不传 packet 时检查初始事实，无需另排盘。它能查结构、盘面引用、原文和可计算前提，不能认证任意自然语言推理。

## 调候与其他方法

调候 120 格已按当前冻结转录分别记录。新候选来自审计中的一般分支与有条件分支，旧表不再直接驱动结果。“次候选”不是固定次优列表；缺当月专段时不据季节论冒充月度结论。

紫微去掉组合的上格/凶格标签，保留实际触发组合与来源边界。亮度、自化、年四化不混为一个判断。六爻使用本方法的宫序、世应、六亲和动变条款。两者的基础条款范围见 [内容覆盖](CONTENT-COVERAGE.md)。

奇门默认 `--ju-method futou`，采用实交节和符头三元；`legacy-days` 仅为旧日数法对比。方位综合分和裸吉凶列表删除。值使按九宫计数，不能沿八宫环计数。

六壬可能返回 `ok:true` 且 `completion_status:partial`，表示天地盘、四课已得而三传取法未支持。遇到 `san_chuan.status:unsupported` 及空值时，不能补传或作依赖三传的解释。两方法细节见 [方法规格](QIMEN-LIUREN-METHODS.md)。

## 时间

先用 request_time.py 获取用户现居地时间，同请求复用 UTC 和 current-timezone。出生地点与时区、现居地、所问目标时间分别处理。历史/未来的时级问题需完整时分，不能借用当前时分。

未知时辰只保留候选时刻之间不变的柱，不保证一定有三柱。真太阳时还可能改变公历或农历日期，相关日期用 candidate_dates 表示，不保留内部正午的单一日期。隐藏占位时刻、精确起运日期和不可靠岁运结果。缺当前所在地仍可核原局，不猜当年参照。

起运采用固定 lunar_python 的 Yun sect=1，qi_yun.algorithm_sect 与 day_boundary_sect 分开；后者才对应 CLI 日界开关。真太阳时、时区和真实交节是不同转换，说明以实际返回的时间口径为准。

## 包与验证范围

知识库清单 schema 2.0 显式声明 source 或 runtime。源码校验包含原始来源；运行包校验全部运行文件、章节及来源索引，原始 HTML/wiki 在独立 sources ZIP。不能以 sources 目录缺失为由跳过验证。搜索结果另有 retrieval_schema_version，原段落接口保持 1.0。

五书所选目录齐全不等于所有原文已影像校勘。已有五处 [异版短句影像见证](FACSIMILE-COLLATION.md)，与默认底本分开，不提升全书状态。

## 三类验证分别报告

1. 确定性回归：盘面、时间、错误路径、来源完整性和发行包。完整 CI 使用 scripts 与 evals 的合并覆盖率，保留 80% 门槛，同时报告分组。
2. 实际回答评估：固定题目、版本、模型与设置，保存正文和全部工具轨迹，再审核事实、条件、完成程度、相关性与可读性。
3. 现实预测验证：需要前瞻记录、事件与时间窗口定义、独立结果和失败标准。前两类通过不证明这一类。

旧 [v3 开发试跑](https://github.com/ShousenZHANG/chinese-fortune/blob/main/docs/MODEL-PILOT.md) 保留首答和修订，其代码在过程中变动，不能当作冻结版本盲测。v4 另有 24 道完整任务能力集和保留的挑战集。测试题目本身不是运行记录。

本次实验状态、实际结果和成本见 [v4 对照报告](https://github.com/ShousenZHANG/chinese-fortune/blob/main/evals/v4/REPORT.md)。该报告属于开发评审材料，不放入运行包；未完成评审时不得把题目数量称为通过数量。

新记录 schema 2.0 的评审必须绑定正文、工具轨迹与证据摘要；内容改变后旧评审失效。评审者与实现的关系应披露，模型审查不冒称人类专家。记录检查器通过不等于语义评审结论可信。

## 开发验证

```sh
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q --cov --cov-report=term-missing
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

run_checks.py 的独有黄金断言已迁移到 pytest，不再重复启动整套测试。源码原地变异器已删除，反例或变异在内存和临时目录验证。正式发布流程见 [RELEASE-PROCESS.md](RELEASE-PROCESS.md)。

时区数据由固定依赖约束管理；CI 设置 PYTHONTZPATH=""，避免系统数据库绕过该版本。升级时重新检查夏令时和交节边界。
