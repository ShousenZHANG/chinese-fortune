# 可选方法

用户明确点名时才加载对应资料。以下方法不参与默认八字判断，也不为八字结果投票。资料覆盖与验证程度分别说明。

| 方法 | 资料 | 能力 |
|---|---|---|
| 紫微 | [紫微](02-ziwei.md) | ziwei_calc.py；完整盘面、宽松组合候选，解释需本方法独立条件 |
| 周易 | [周易](03-yijing.md) | yijing_cast.py；卦形、动变与文本阅读，取法分开 |
| 六爻 | [六爻](04-liuyao.md) | liuyao_cast.py；纳支、六亲、世应与动变，个人占断不由标签自动生成 |
| 梅花 | [梅花](05-meihua.md) | meihua_cast.py；取数、体用与条件解释 |
| 黄历 | [黄历](12-huangli.md) | huangli_query.py；历法及民俗宜忌，来源冲突并列 |
| 风水 | [风水](08-fengshui.md) | 资料说明，需现场资料，无自动完整风水盘 |
| 面相 | [面相](09-mianxiang.md) | 传统文本解释，不从外貌断性格、健康或命运 |
| 手相 | [手相](10-shouxiang.md) | 传统概念说明 |
| 测字 | [测字](11-cezi.md) | 字形、字义与文化联想 |
| 姓名 | [姓名](13-qiming.md) + [输入](00-intake.md) | name_analyze.py；近现代五格不等于古籍命理 |
| 合婚 | [合婚](14-hehun.md) + [输入](00-intake.md) | 两盘分别核验，生肖关系不等于婚姻结果 |
| 解梦 | [解梦](15-jiemeng.md) | jiemeng_lookup.py；不诊病或预测事件 |
| 生肖 | [生肖](16-shengxiao.md) | zodiac_compat.py；旧分数不是现实适配率 |
| 星座 | [星座](17-xingzuo.md) | 西方象征体系，未纳入中国古籍库 |
| 塔罗 | [塔罗](18-tarot.md) | tarot_draw.py；不作为八字证据 |
| 小六壬及扩展索引 | [扩展](21-extended-methods.md) | 小六壬有脚本，其余按实际覆盖说明 |
| 随机寻访 | [散步工具](../docs/OPTIONAL-TOOLS.md) | explore_cast.py；散步灵感，不参与预测 |

这些材料的具体引文需另行定位。尚未核验的材料只作查找线索，不直接套为个人结论。
