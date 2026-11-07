---
description: 本月运势：按《协纪辨方书》相主逐日分等级，列出这个月最好和要避开的日子，可带事项
argument-hint: "[可选：事项，如 搬家、开业；或「下个月」]"
---

用 chinese-fortune 技能回答本月运势。用户补充：$ARGUMENTS

1. 出生资料先查本机档案（SKILL.md「档案」）；需要当前所在城市来确定这个月是哪几天。
2. 运行 `python scripts/fortune_reading.py --stdin`，`intent: period`，`period` 填「这个月」（用户说下个月就填「下个月」）；有事项时加 `event.scenario`。
3. 首句直接说最好和要避开的日子，再按 references/24-personalized-forecast.md 写理由；整月主题不能代替逐日等级。
