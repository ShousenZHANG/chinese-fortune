# 中国传统命理 · Claude Skill

> 一个 Claude skill 集成 20+ 种中国传统命理方法 · MIT · [English](README.md)

覆盖五术（山医命相卜）的 Claude Code / Agent SDK 技能：八字、紫微斗数、周易、六爻、奇门遁甲、风水、黄历、姓名学、塔罗等。繁重的历法计算交给确定性 Python 脚本，Claude 依据参考文档解读结果。

用于**文化研习与自我反思**，不构成医疗、法律、金融建议。

## 快速开始

```bash
git clone https://github.com/<your-org>/chinese-fortune.git
cp -r chinese-fortune ~/.claude/skills/chinese-fortune   # 安装到 Claude Code
pip install "lunar_python>=1.4.4,<2.0"                    # 精确农历/八字/黄历
```

之后直接对 Claude 说话即可，技能会根据中英文请求自动触发：

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

`python scripts/<名>.py --help` 查看完整参数。

## 方法

| 分类 | 方法 | 有脚本 |
|---|---|---|
| 命 | 八字、紫微斗数、称骨、河洛理数、七政四余 | 八字、紫微 |
| 卜 | 周易、六爻、梅花易数、奇门遁甲、大六壬、小六壬、太乙、灵签、杯筊 | 周易、六爻、梅花、奇门、大六壬、小六壬 |
| 相 | 风水（八宅/玄空）、面相、手相、测字 | —（文档解读） |
| 术 | 黄历择日、姓名学、合婚、解梦、生肖、星座、塔罗 | 黄历、姓名、合婚/生肖、塔罗 |

每种方法对应 `references/` 中的参考文档，需要计算的另配 `scripts/` 脚本。完整路由表见 [SKILL.md](SKILL.md)。

## 工作原理

```
SKILL.md          路由：frontmatter 触发词 + 方法表
references/  (23)  命理正文：理论 + 各方法解读指南
scripts/     (13)  确定性计算（lunar_python + SystemRandom）
assets/      (12)  JSON 查表（干支、64卦、神煞、塔罗、笔画 …）
evals/            发布校验 + 12 场景断言
tests/            pytest 黄金值 + 边界用例
```

渐进式披露：Claude 先加载小路由，再按需加载对应方法的文档/脚本。历法正确性（真太阳时、节气定月、立春年界、夜子时、闰月）交给 `lunar_python`，技能在其上叠加格局/用神/解读层。

## 安全边界

硬红线（见 [references/20-disclaimer.md](references/20-disclaimer.md)）：不预测死亡日期、不做医疗/法律/金融决断、不接诅咒加害、不归咎他人、不推销付费“化解”。每次解读都以“启发性倾向”呈现并附简短免责；遇急性危机信号转介求助资源。

## 校验

```bash
python -X utf8 evals/run_checks.py     # 6 项发布校验
python -m pytest tests/                # 单元 + 集成测试
```

`run_checks.py` 校验：SKILL.md frontmatter、每个脚本输出合法 JSON、参考文档覆盖、12 个评测场景的机器断言、pytest 套件、发布洁净度。末尾打印 PASS/FAIL 汇总，任一失败即非零退出。

## 贡献 / 许可

欢迎 PR——更深的紫微/玄空飞星逻辑、更多 `evals` 场景、繁體/英文翻译。提交前请跑 `evals/run_checks.py` 和 `pytest`，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

[MIT](LICENSE)。基于经典文献（《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》…）与 [`6tail/lunar-python`](https://github.com/6tail/lunar-python)。仅供文化/教育参考——结果是概率性倾向，非确定性预言。
