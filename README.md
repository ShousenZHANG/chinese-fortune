<div align="center">

# 中国传统命理 · Chinese Fortune

**一个 Claude Skill，把中国五术（山·医·命·相·卜）的 20+ 种命理方法装进一个可移植技能。**

[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![release](https://img.shields.io/github/v/release/ShousenZHANG/chinese-fortune)](https://github.com/ShousenZHANG/chinese-fortune/releases)

**简体中文** ｜ [English](README.en.md)

</div>

---

八字、紫微斗数、周易、六爻、奇门遁甲、风水、黄历、姓名学、塔罗……繁重的历法计算交给确定性 Python 脚本，Claude 依据参考文档解读。**仅供文化研习与自我反思，不构成医疗、法律、金融建议。**

## 目录

- [特性](#特性)
- [快速开始](#快速开始)
- [覆盖方法](#覆盖方法)
- [工作原理](#工作原理)
- [安全边界](#安全边界)
- [质量保障](#质量保障)
- [贡献](#贡献)
- [许可与来源](#许可与来源)

## 特性

- **20+ 种方法，一个技能** — 命卜相术全覆盖，单一自包含 skill，无需后端、无需联网。
- **确定性计算** — Python 脚本基于 lunar_python 排盘，模型负责条件化解释；数值启发式不冒充古籍定理。
- **历法验证** — 八字与紫微共享时间归一化，支持显式真太阳时/钟表时、跨日与夏令时歧义。独立差分验证指定口径的四柱，时间处理另有边界回归；测试范围不等于证明所有输入或现实预测都正确。
- **渐进式披露** — Claude 先加载小路由，再按需调用对应方法的文档与脚本，上下文最小化。
- **有依据的解读** — 事实、古籍条款与候选解释分开，见 [输出契约](references/22-output-contract.md)。机器审核结构与引文；语义与现实预测效果需要独立评估。
- **量子熵源（可选）** — 起卦/抽牌可用 `--entropy quantum` 接入 ANU 量子真空噪声（物理真随机，源不可达时优雅降级并如实标注；不声称提升准确度）。
- **随机寻访** — `explore_cast.py`：QRNG 撒点 + 密度异常（attractor/void）+ 黄历吉方对照 + 安全提示，Randonautica 式散步灵感（明确非预测、非念力）。
- **安全护栏** — 硬红线（不预测死亡、不做医疗法律金融决断、不接诅咒）+ 危机转介，内建于技能。
- **工程化** — pytest、ruff、mypy、覆盖率门槛和发布校验；测试数量与覆盖率以对应提交的 CI 实际报告为准。

## 快速开始

从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载 `chinese-fortune-v*.zip`，按平台导入：

| 平台 | 导入方式 |
|---|---|
| **Claude Code** | 解压到 `~/.claude/skills/` → 重启。压缩包内 `chinese-fortune/` 文件夹即技能。 |
| **Claude.ai** | 设置 → Capabilities → Skills → **上传技能** → 选该 zip。 |
| **OpenAI / 其他** | 解压到任意位置；agent 指向 `agents/openai.yaml`，把 `scripts/` 当工具调用。 |

```bash
pip install -r scripts/requirements.txt -c scripts/constraints-runtime.txt
```

导入后直接对 Claude 说话即可，技能按中英文请求自动触发：

```text
我 1990 年 5 月 10 日下午 2 点半出生，男，北京。详细批一下八字。
帮我用铜钱起一卦，问要不要跳槽。
2026 年 6 月想搬家，我属龙，哪几天合适？
```

脚本也可独立运行（输出结构化 JSON）：

```bash
python scripts/bazi_calc.py --year 1990 --month 5 --day 10 --hour 14 --gender male
python scripts/yijing_cast.py coins --question "要不要接这个 offer？"
python scripts/huangli_query.py --date 2026-06-15
```

`python scripts/<名>.py --help` 查看完整参数。从源码自行打包：`python scripts/build_skill.py`。

## 覆盖方法

方法、资料和可调用脚本统一维护在 [SKILL.md 的路由表](SKILL.md#quick-router--pick-the-right-method)。Script 列为 `—` 的项目仅有资料支持；有脚本表示可计算表中所述范围，不表示涵盖所有流派或已经验证预测效果。具体流派限制见对应参考文档。

## 工作原理

```
SKILL.md           路由：frontmatter 触发词 + 方法表
references/        按需加载的传统资料与输出契约
scripts/           计算引擎、共享模块与证据审核
assets/            规则查表与古籍条款注册表
evals/             发布校验、安装冒烟与真实回答评估（源码仓库）
tests/             pytest 黄金值 + 边界 + 独立引擎差分
```

项目在 `lunar_python` 历法计算上实现时间归一化、格局候选与解读证据。2.0 的用神、喜忌最终值允许为空，调用方须检查状态与条件，详见 [迁移和验证说明](docs/OUTPUT-VALIDATION.md)。

## 安全边界

硬红线（见 [references/20-disclaimer.md](references/20-disclaimer.md)）：不预测死亡日期、不做医疗 / 法律 / 金融决断、不接诅咒加害、不归咎他人、不推销付费“化解”。每次解读都以“启发性倾向”呈现并附简短免责；遇急性危机信号转介求助资源。

## 质量保障

```bash
python -X utf8 evals/run_checks.py     # 发布校验（7 项）
python -m pytest tests/                # 单元 + 集成 + 独立引擎差分
```

CI（Python 3.11 / 3.12）强制执行五道门：

| 门 | 内容 |
|---|---|
| `ruff` | 代码规范，0 容忍 |
| `mypy` | 静态类型检查 |
| `pytest` | 规则、边界、CLI、独立引擎差分与内容审核回归；具体通过/跳过数见 CI |
| coverage | 追踪 scripts 与 evals（含子进程），低于 80% 失败；实际值见 CI |
| harness | SKILL.md 校验 + 解读纪律锁 + 19 场景机器断言 + 脚本 JSON 合法性（7 项） |

## 贡献

欢迎 PR——更深的紫微 / 玄空飞星逻辑、更多 `evals` 场景、繁體翻译。提交前请跑 `evals/run_checks.py` 与 `pytest`，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可与来源

[MIT](LICENSE)。基于经典文献（《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》…）与 [`6tail/lunar-python`](https://github.com/6tail/lunar-python)。解读属于有条件的传统解释，仅供文化 / 教育参考，不代表经过统计验证的事件概率。

## 2.0 输出与验证

用神与喜忌可能返回 `primary: null`，先读 `status` 与 `yong_shen.views`。这表示候选条件未核实，不是字段缺失。古籍的正文、注文和项目整理分开，见 `assets/classical_evidence.json`。

八字/紫微默认 `--time-standard true-solar`，需要钟表时请显式指定 `clock`。有重复当地时间时用 `--fold 0/1`。

内存接口：`calculate_bazi(build_parser().parse_args(argv))`，紫微对应 `calculate_ziwei`。CLI 仍输出 UTF-8 JSON。

真实回答评估：`evals/reading_cases.json` 有 30 个场景；`python -X utf8 evals/evaluate_readings.py --responses recording.json` 检查实际回答及审核记录。没有实际回答或语义评审即不通过，场景文件自身不代表模型已通过。详见 [验证说明](docs/OUTPUT-VALIDATION.md)。
