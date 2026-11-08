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
| 生肖 | [生肖](16-shengxiao.md) | zodiac_compat.py；旧分数不是现实适配率 |
| 小六壬及扩展索引 | [扩展](21-extended-methods.md) | 小六壬有脚本，其余按实际覆盖说明 |
| 随机寻访 | [散步工具](../docs/OPTIONAL-TOOLS.md) | explore_cast.py；散步灵感，不参与预测 |

这些材料的具体引文需另行定位。尚未核验的材料只作查找线索，不直接套为个人结论。

塔罗、星座和解梦不属于中国术数，已移到同一仓库的 **fortune-extras** 技能；用户点名时用它回答，没装就照实说明，并给安装命令 `npx skills add ShousenZHANG/chinese-fortune --skill fortune-extras`。

## 点名方法索引

从 SKILL.md 逐字移来（v6.1）。用户点名下列方法时按这张表找资料和脚本。

| 用户点名 | 资料 | 脚本 |
|---|---|---|
| 短期运势 / 面试择时 | [个人未来时段](24-personalized-forecast.md) | fortune_reading.py |
| 八字 / 四柱 / 用神 | [八字](01-bazi.md)；排盘口径 [复核](01-bazi-paipan.md) | bazi_reading.py |
| 穿什么颜色、戴什么对自己有利 | [八字](01-bazi.md)（颜色按《穷通宝鉴》这一格调候的一般取法换算，例外未逐盘核对） | bazi_reading.py --question … --markdown |
| 紫微 | [紫微](02-ziwei.md)；排盘推导 [口径](02-ziwei-paipan.md) | ziwei_calc.py |
| 周易 / 易经 | [周易](03-yijing.md) | yijing_cast.py |
| 六爻 | [六爻](04-liuyao.md) | liuyao_cast.py（用神不上卦看 `fu_shen`，不另起首卦） |
| 梅花 | [梅花](05-meihua.md) | meihua_cast.py |
| 连续行程 | [个人时段](24-personalized-forecast.md)的连续行程字段 | fortune_reading.py --stdin |
| 奇门 | [奇门](06-qimen.md) | qimen_cast.py（默认已核核心；旧全盘须显式选择） |
| 六壬 | [大六壬](07-daliuren.md) | liuren_cast.py |
| 黄历 / 择日 | [黄历](12-huangli.md) | huangli_query.py |
| 五行 / 天干地支 | [基础](00-foundations.md) | 按需查表 |
| 神煞 | [神煞](19-shensha.md) | 解释起法和实际位置 |

其他点名方法见 [可选方法](23-optional-methods.md)，纯八字不加载；点名时直接读对应一篇：[风水](08-fengshui.md)、[起名](13-qiming.md)、[合婚](14-hehun.md)、[生肖](16-shengxiao.md)、[扩展术数](21-extended-methods.md)、[面相](09-mianxiang.md)、[手相](10-shouxiang.md)、[测字](11-cezi.md)。无完整工具或条款时按实际覆盖回答，不编造盘面。各书收录以所选转录目录为界；紫微、六爻等解释规则仍未达到全书覆盖。
