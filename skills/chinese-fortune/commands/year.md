---
description: 今年、明年或某一年的运势：当步大运加这一年的流年关系，逐条附原文，不合成总分
argument-hint: "[年份，如 2027；不写就是今年]"
---

用 chinese-fortune 技能回答年度运势。用户补充：$ARGUMENTS

1. 出生资料先查本机档案（SKILL.md「档案」）；问「今年」时需要当前所在城市，用 `request_time.py` 固定当前时刻。
2. 运行 `python scripts/bazi_reading.py --view compact --question "<年份>年运势" --facts-out <临时目录>/bazi.json`。
3. 大运与流年分开说：流年只列原文说的冲、克、合关系和原文的说法，不细到月份；想看这一年哪几个月好，再用 `/chinese-fortune:days` 按月份问。
