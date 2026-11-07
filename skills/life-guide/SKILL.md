---
name: life-guide
description: 按冻结的《高性价比人生指南》回答现实生活问题，每条注明第几节第几条，急症和自伤念头先给第一个动作。用于：胸痛、倒地、燃气泄漏、不想活了等正在发生的急症；收到传票、被起诉；该不该、值不值、划不划算、怎么选、出事了先做什么、能领什么钱、犯不犯法；失业了先做什么、工伤怎么赔、替朋友担保签不签、押金不退怎么办、拖欠工资、保险要不要买、通勤值不值、留学签证。Answers everyday life questions (emergencies first) from a frozen copy of the life-advice book, citing section and entry. 命理、运势、择日问题用 chinese-fortune。
license: MIT (code); book text CC BY 4.0, see THIRD_PARTY_NOTICES.md
compatibility: Requires Python 3.9+ (python3, python or py -3). No packages to install and no network.
---

# 人生决策：按《高性价比人生指南》查了再答

用户问一件具体的现实事情时，先用工具从冻结的《高性价比人生指南》里取条目，再回答。书里没写的部分照实说是常识或没有覆盖，不替书补结论。完整流程见 [人生决策](references/life-decision.md)。

## 工作流程

1. 取当前所在地的 IANA 时区（`--current-timezone`），用来判断条目适用的地区。不知道就问城市，不用电脑时区代替。
2. 运行：

```bash
python scripts/life_guide.py --decide "<用户原话>" --current-timezone <时区> --markdown
```

3. 结果里有 `stop` 时，先写 `stop.first_action`，再写 `stop.entries`，不讲性价比、不补别的条目。
4. 其余按 `do`（先做）和 `dont`（别做）分段，每条照抄标题、节号和条号、性价比和证据等级；书里的数字照抄，不改写成「大部分」。
5. 要再查别的条目用 `--query`，可按 `--section --grade --ratio --lens --money --time --will --disputed` 筛选。

## 回答写法

- 先用一两句白话直接回答，再列条目；每条后面写它为什么适用于用户的情形。
- 条目的适用人群、争议和例外在备注里，抽出来的条目要整条读完。
- 书只给通用口径。个案（诉讼、治疗、投资）提醒找当地专业人员。

## 边界

- 急症、自杀念头、正在进行的法律程序先给第一个动作。求助电话只给在中国大陆的人（120、119、12356，未成年人 12355），不在中国大陆就说按所在地官方急救和危机援助信息求助，不编号码。
- 不诊断疾病，不给买卖指令，不预测官司胜败。
- 这个技能不算命。用户同时问命理时，命理部分交给 chinese-fortune，两段分开答。

## 运行环境

只需 Python 3.9 以上，不用安装任何包，不联网。时区地区判断用随包的 IANA 文本表（`assets/tz/`）。书的来源、提交和授权见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
