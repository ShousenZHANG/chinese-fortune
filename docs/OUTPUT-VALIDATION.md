# 输出验证与迁移

可读正文示例见 [OUTPUT-EXAMPLE.md](OUTPUT-EXAMPLE.md)，与实际评估记录分开保存。

## 2.0 迁移

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

古籍注册表目前只核部分网络转录，尚未进行全书原刻影像校勘。调候旧表逐格核验状态不因本次结构改造自动升级。

时区数据发布基线采用 [tzdata 2026.3](https://pypi.org/project/tzdata/2026.3/)（2026-09-06 核查 PyPI）。CI 设 `PYTHONTZPATH=""`，避免 Linux 系统时区库绕过固定版本；自行运行可采用系统数据，升级时应复查边界用例。
