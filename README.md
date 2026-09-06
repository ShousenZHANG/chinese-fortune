<div align="center">

# 中国传统命理 · Chinese Fortune

**一个 Claude Skill，把中国五术（山·医·命·相·卜）的 20+ 种命理方法装进一个可移植技能。**

[![CI](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml/badge.svg)](https://github.com/ShousenZHANG/chinese-fortune/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-2461%20passing-brightgreen)](tests)
[![coverage](https://img.shields.io/badge/coverage-88%25-brightgreen)](#质量保障)
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
- **确定性计算** — 15 个 Python 引擎在 `lunar_python`（[寿星天文历](https://github.com/6tail/lunar-python) 算法移植，节气误差 < 1 秒）上排盘起卦，而非让大模型手算（易错）。
- **历法严谨** — 真太阳时、节气定月、立春年界、夜子时、闰月等业余易错处全部正确，并经**独立引擎 sxtwl 跨库对照**：本仓库引擎端到端逐盘比对 1920–2080 （每 97 天 × 3 个时辰，含夜子/早子两侧）约 1,800 盘，零分歧。
- **渐进式披露** — Claude 先加载小路由，再按需调用对应方法的文档与脚本，上下文最小化。
- **解读纪律 (CI 锁定)** — 八字论断严格以《子平真诠》《滴天髓》《穷通宝鉴》《三命通会》《渊海子平》五大古籍为准绳：凡古籍无据者不妄断、禁套话迎合、只出可验证性最高的结论。纪律文本被发布校验断言，删改即构建失败。
- **量子熵源（可选）** — 起卦/抽牌可用 `--entropy quantum` 接入 ANU 量子真空噪声（物理真随机，源不可达时优雅降级并如实标注；不声称提升准确度）。
- **随机寻访** — `explore_cast.py`：QRNG 撒点 + 密度异常（attractor/void）+ 黄历吉方对照 + 安全提示，Randonautica 式散步灵感（明确非预测、非念力）。
- **安全护栏** — 硬红线（不预测死亡、不做医疗法律金融决断、不接诅咒）+ 危机转介，内建于技能。
- **工程化** — 2461 测试 / 86% 覆盖 / `ruff` + `mypy` + CI 五道质量门 + 7 项发布校验。

## 快速开始

从 [Releases](https://github.com/ShousenZHANG/chinese-fortune/releases) 下载 `chinese-fortune-v*.zip`，按平台导入：

| 平台 | 导入方式 |
|---|---|
| **Claude Code** | 解压到 `~/.claude/skills/` → 重启。压缩包内 `chinese-fortune/` 文件夹即技能。 |
| **Claude.ai** | 设置 → Capabilities → Skills → **上传技能** → 选该 zip。 |
| **OpenAI / 其他** | 解压到任意位置；agent 指向 `agents/openai.yaml`，把 `scripts/` 当工具调用。 |

```bash
pip install "lunar_python>=1.4.4,<2.0"   # 所有平台：精确农历 / 八字 / 黄历
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

| 分类 | 方法 | 配套脚本 |
|---|---|---|
| **命** | 八字、紫微斗数、称骨、河洛理数、七政四余 | 八字、紫微 |
| **卜** | 周易、六爻、梅花易数、奇门遁甲、大六壬、小六壬、太乙、灵签、杯筊 | 周易、六爻、梅花、奇门、大六壬、小六壬 |
| **相** | 风水（八宅 / 玄空）、面相、手相、测字 | —（文档解读） |
| **术** | 黄历择日、姓名学、合婚、解梦、生肖、星座、塔罗 | 黄历、姓名、合婚 / 生肖、塔罗 |
| **游** | 随机寻访（QRNG 探索点 + 黄历吉方，非占卜） | 随机寻访 |

除随机寻访（纯工具，无参考文档）外，每种方法对应 `references/` 中的参考文档，需要计算的另配 `scripts/` 脚本。完整路由表见 [SKILL.md](SKILL.md)。

## 工作原理

```
SKILL.md           路由：frontmatter 触发词 + 方法表
references/  (23)   命理正文：理论 + 各方法解读指南
scripts/     (15)   确定性计算引擎（lunar_python + SystemRandom + 可选 QRNG）
assets/      (12)   JSON 查表（干支、64卦、神煞、塔罗、笔画 …）
evals/             发布校验 + 19 场景机器断言
tests/             pytest 黄金值 + 边界 + 独立引擎差分
```

历法正确性（真太阳时、节气定月、立春年界、夜子时、闰月）交给 `lunar_python`，技能在其上叠加格局 / 用神 / 解读层。

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
| `pytest` | **2461 测试** — 黄金值、立春 / 夜子时 / 闰月边界、五鼠遁不变量、引擎对 sxtwl 端到端差分（约 1,800 盘）、对 iztro 紫微 903 例差分 |
| coverage | 子进程追踪 **88%**，低于 80% 即失败 |
| harness | SKILL.md 校验 + 解读纪律锁 + 19 场景机器断言 + 脚本 JSON 合法性（7 项） |

## 贡献

欢迎 PR——更深的紫微 / 玄空飞星逻辑、更多 `evals` 场景、繁體翻译。提交前请跑 `evals/run_checks.py` 与 `pytest`，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可与来源

[MIT](LICENSE)。基于经典文献（《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》…）与 [`6tail/lunar-python`](https://github.com/6tail/lunar-python)。仅供文化 / 教育参考——结果是概率性倾向，非确定性预言。
