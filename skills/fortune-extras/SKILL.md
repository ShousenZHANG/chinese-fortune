---
name: fortune-extras
description: 塔罗抽牌、西方星座、周公解梦，作为娱乐与文化参考。用于：抽塔罗、塔罗占卜、今日塔罗、牌阵、凯尔特十字；星座性格、星座配对、上升星座；梦见蛇、梦见掉牙、梦到考试是什么意思、解梦。Tarot draws, Western sun signs and dream symbols, as entertainment and cultural reference. 八字、紫微、六爻、择日等中国术数用 chinese-fortune。
license: MIT
compatibility: Requires Python 3.9+ (python3, python or py -3). No packages to install. Network is used only when the user opts into the quantum randomness source for a draw.
---

# 塔罗、星座与解梦

三种方法都只作象征和文化参考：不预测具体事件，不当作心理测验，也不推断他人的想法或忠诚。

| 用户问 | 读 | 运行 |
|---|---|---|
| 抽塔罗、牌阵 | [塔罗](references/tarot.md) | `python scripts/tarot_draw.py one\|three\|celtic\|relationship\|daily` |
| 星座性格、配对 | [星座](references/xingzuo.md) | 不需要脚本，按参考文档说明 |
| 解梦 | [解梦](references/jiemeng.md) | `python scripts/jiemeng_lookup.py --symbol 蛇`（或 `--search`、`--categories`） |

抽牌结果里有 `seed` 和 `entropy`，用户要求复看时用同一个 seed 重放，不重新抽。解梦词条没有经过核验的解释时字段为空，照说「没有可靠出处」，不自己补。

## 回答写法

先用一两句白话回答所问，再给牌面、星座或梦境意象的象征含义；象征只说到「常被理解为」，不写成必然。牌义、星座性格是现代通行说法，不冒充中国古籍。

## 边界

- 不从牌面、星座、梦境推断疾病、寿命、怀孕、事故或他人的想法。
- 梦境或焦虑持续困扰、影响睡眠和生活时，建议找专业人员；提到自伤念头时先给求助信息。
- 不诱导购买化解物品或付费服务。
