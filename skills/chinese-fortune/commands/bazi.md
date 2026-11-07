---
description: 八字命盘：按古籍原文用白话解释主要结构，每句引文附段号
argument-hint: "[出生日期 时间 出生地 性别；不写就用本机档案]"
---

用 chinese-fortune 技能回答八字本命问题。用户补充：$ARGUMENTS

1. 先按 SKILL.md「档案」一节查本机档案；没有档案、补充里也没有出生资料时，按 references/00-intake.md 一次问齐出生日期（公历或农历）、时间（记不清给范围）、出生地和性别。
2. 运行 `python scripts/bazi_reading.py --view compact --facts-out <临时目录>/bazi.json`，参数用已确认的资料。
3. 按 SKILL.md 的工作流程和「白话输出」写回答：先用两三句白话说主线和限制，再给短原文与解释。发出前用 `answer_check.py` 核对。
