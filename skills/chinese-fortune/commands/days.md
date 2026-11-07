---
description: 哪天对我好：按《协纪辨方书》相主给一段时间逐日分等级，可带事项（搬家、结婚、开业、出行、面试）
argument-hint: "[时间范围和事项，如 下周 面试 / 下个月 搬家]"
---

用 chinese-fortune 技能回答择日问题。用户补充：$ARGUMENTS

1. 先运行 `python scripts/question_router.py --question "<用户原话>"`，按返回的流程和请求骨架走。
2. 出生资料先查本机档案（SKILL.md「档案」）；还需要当前所在城市来确定「今天」「下周」。
3. 运行 `python scripts/fortune_reading.py --stdin`，首句直接说最好和要避开的日子；借用相主的事项照工具写明「借用相主比较」，不说成已证的吉凶。
