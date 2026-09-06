# 输出验证与迁移

可读正文示例见 [OUTPUT-EXAMPLE.md](OUTPUT-EXAMPLE.md)，与实际评估记录分开保存。

## 3.0 迁移

默认解读入口改为 `bazi_reading.py`。它只提供盘面事实、透藏位置、固定主体系和原文检索结果；完整个人解释由宿主阅读条款后生成。`bazi_calc.py` 是保留的诊断接口，工程旺衰与旧调候候选不能作为古籍已核结论。

每次计算先运行 `request_time.py --current-timezone <用户所在地时区>`，后续复用返回的 UTC 时刻作为 `--request-time`。出生 `--timezone` 与当前 `--current-timezone` 分开。无当前所在地也无 `--as-of-year` 时，八字仍给原局，但不猜流年参考年。显式历史/未来时级目标必须完整，不能用现在时分补历史日期。

读取 `liu_nian_status` 判断参考年份来源。`liu_nian_scope=calendar_year_reference_list` 表示公历年度列表，不是当前瞬间已生效的年柱；立春前后需按目标时刻另核。未知时辰的默认解释只保留首尾时间核对后共同的柱，变化柱列候选；不输出占位时分和精确起运日期。

`reading_support.py --chart` 和 stdin 审核都接收完整 `bazi_reading` 成功结果，内部按 chart_facts 校验路径。保存实际模型记录时保留完整原始结果，不自行补造 ok 字段。

梅花与周易时间起卦默认 `--calendar-profile classical`：年支序数、农历月日与时支序数；闰月需明确 `--leap-month-policy repeat/next`。旧公历整数算法仅保留为 `legacy-gregorian`，不能冒充古法。梅花默认 `body_strength=null`，旧公历月旺衰只在兼容模式用于诊断。

神煞结果只保留起法与命中位置，不再提供 `meaning` 断语。姓名旧表分类、生肖旧分数不再产生个人结论；解梦保留主题与场景索引，尚未核验的解释为空。可选方法不参与默认八字推断。

古籍通过 `classical_search.py --validate` 检查选定版本目录与文件；`--query` 检索、`--passage-id` 定位原文。正文引用记录可带 `passage_quotes`，每项保存 `passage_id`、`text`、`layer`，审核器检查它与冻结原文相符。它仍不认证自然语言解释是否正确。

### 沿用的 2.0 数据约定

`yong_shen.primary`、`xi_shen.primary`、`ji_shen.primary` 可为 null。调用方读取 status 和 views，不能用候选第一项填补。格局纯破是程序启发式标记，须核成败救应后解释。

八字和紫微统一默认真太阳时；钟表时请用 `--time-standard clock`。源自旧版本的紫微基准盘若采用钟表时，应显式补此参数。重复当地时间需指定 `--fold`。

Python 调用示例：

```python
from bazi_calc import build_parser, calculate_bazi
from reading_support import review_claims

args = build_parser().parse_args([
    '--year', '2000', '--month', '1', '--day', '15',
    '--hour', '10', '--gender', 'male', '--as-of-year', '2026',
])
chart = calculate_bazi(args)
assert chart['ok']
errors = review_claims(chart, chart['reading_support'])
```

两个 calculate 函数不写 stdout，也不修改传入 Namespace。CLI 继续支持旧参数并输出错误 JSON。

## 三种验证不能混称

1. **确定性回归**：盘面、时间、格式和错误路径。原文注册与记录校验也属于这一层。
2. **实际回答审核**：运行宿主模型，记录原始回答、工具轨迹、模型和提示词版本，再审核是否忠实回答用户。结构校验不理解所有自然语言，不能替代这一层。
3. **现实预测验证**：另需前瞻记录、固定成功失败标准、独立结果和基线。本项目的测试通过不证明这一层。

## 真实回答记录（需源码仓库）

本轮已有 [实际试跑说明](https://github.com/ShousenZHANG/chinese-fortune/blob/main/docs/MODEL-PILOT.md) 与 [逐条评审](https://github.com/ShousenZHANG/chinese-fortune/blob/main/docs/MODEL-PILOT-REVIEW.md)：原始 30 题复审后为 21 个完整回答、3 个部分完成、6 个待补资料；另有 3 个时间场景。首轮错误与修订均保留。这是会话内协作 agent 的开发试跑，不是冻结版本盲测或预测命中率验证。

`evals/reading_cases.json` 提供 30 个场景。对候选技能在真实宿主中运行后保存以下形式，文件内容由实际运行填入，不能把预期答案当成运行记录：

```json
{
  "model": "实际模型及设置",
  "prompt_version": "实际技能提交或内容摘要",
  "responses": [{
    "case_id": "R01-full_bazi",
    "text": "实际最终回答",
    "tool_calls": [],
    "review": {
      "reviewer": "实际评审者；明确人工、模型或自评",
      "disposition": "partial",
      "criteria": {
        "chart_fidelity": "pass",
        "source_fidelity": "pass",
        "conditions": "pass",
        "scope": "pass",
        "correction_honesty": "pass",
        "relevance": "pass"
      },
      "notes": "逐条说明依据；不能只写通过"
    }
  }]
}
```

有排盘时还应附 chart 与 packet。评估命令：

`disposition` 必填 `answered / partial / deferred`，报告分别统计，防止靠全部拒答取得虚高表现；完整资料与未知时辰的排盘场景还必须保留真实工具轨迹及成功盘面。

```text
python -X utf8 evals/evaluate_readings.py --responses recording.json
```

记录缺失、语义审核缺失或失败都会使验收失败。该程序验证记录，不认证评审者判断的诚实或正确。推荐同题旧版/新版盲评，保留失败，不让同一模型的自评冒充独立结论。

## 本地验证命令（需源码仓库）

```text
python -m pip install -r requirements-dev.txt -c constraints-dev.txt
python -m ruff check .
python -m mypy scripts/
python -X utf8 -m pytest tests/ -q
python -X utf8 evals/run_checks.py --checks-only
python scripts/build_skill.py
python -X utf8 evals/package_smoke.py
```

完整 pytest 已在前一步通过才使用 checks-only；独立执行发布入口时省略该选项。覆盖率用配置中的 scripts+evals，两类均计入分母。CI 另在 Windows 验证依赖、时区与解压后运行。

pytest-cov 7 的子进程追踪由 coverage `patch = ["subprocess"]` 开启，不能仅设置环境变量就假定 CLI 已被计入。此配置随仓库提供，干净环境也应能复现。

五书所选转录版目录已收齐，详见来源说明；用于自动判断的规则注册表仍只有部分经核条款，尚未进行全书原刻影像校勘。调候旧表逐格核验状态不因全文收录自动升级。

时区数据发布基线采用 [tzdata 2026.3](https://pypi.org/project/tzdata/2026.3/)（2026-09-06 核查 PyPI）。CI 设 `PYTHONTZPATH=""`，避免 Linux 系统时区库绕过固定版本；自行运行可采用系统数据，升级时应复查边界用例。
