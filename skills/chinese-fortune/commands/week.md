---
description: 本周运势：按《协纪辨方书》相主逐日分等级，首句说最好和要避开的日子，可带事项
argument-hint: "[可选：事项，如 面试、出行；或「下周」]"
---

用 chinese-fortune 技能回答本周运势。用户补充：$ARGUMENTS

1. 出生资料先查本机档案（SKILL.md「档案」）；需要当前所在城市来确定这一周是哪几天。
2. 运行 `python scripts/fortune_reading.py --stdin`，`intent: period`，`period` 填「这周」（用户说下周就填「下周」）；有事项时加 `event.scenario`。
3. 首句直接说最好和要避开的日子，再按 references/24-personalized-forecast.md 写理由；不把十神、冲合改写成每日节奏。
