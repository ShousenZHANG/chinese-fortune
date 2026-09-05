# 个人信息采集 / 边界情形 / 必出字段

> 仅在需要个人生辰的方法 (八字 / 紫微 / 合婚 / 起名 / 择日) 中使用。
> 从 SKILL.md 路由表进入本篇；不需要生辰的方法 (周易/塔罗/解梦/星座等) 无须读。

## Information collection protocol

When a reading needs personal data (八字 / 紫微 / 合婚 / 起名 / 择日), **collect step-by-step**, not all at once. Use `AskUserQuestion` when there are discrete options (gender, calendar type); use plain text when free-form (name, location).

### 数据处理声明 — 先说清楚再问

这份表要采集九项个人信息（姓名、曾用名、生日、时辰、性别、出生地、现居地、
关心议题含健康与财务、在世状态）。**采集之前必须让用户知道这些数据会怎样被处理：**

- **本 skill 不落盘。** `scripts/` 与 `evals/` 全部代码零文件写入——无 logging、
  无临时文件、无缓存（`tests/test_harness_gates.py` 强制）。生辰只在一次进程调用
  里存在，进程结束即消失。
- **但它们仍在对话记录里。** 本 skill 管不到宿主对话的留存策略；用户若不希望
  生日留痕，应由用户自己决定说到多细（例如只给年月、或只给时辰不给日期）。
- **命令行可见。** 所有数据以命令行参数传给脚本，因此会出现在进程列表
  （`ps` / 任务管理器）与 shell 历史里。多用户共享的机器上尤须注意。
- **第三方盘**：见 §在世状态 与 `20-disclaimer.md` 的同意条款——未经本人同意
  不排他人盘。

**开口第一句就带上这条**，不要等用户问。一句话即可：
「这些信息只用于本次排盘、不会被保存；但会留在我们的对话记录里。」

| Step | Field | Required for | How to ask |
|---|---|---|---|
| 1 | 姓名 / 化名 | naming, calibration | plain text |
| 2 | 曾用名 + 改名年份 | naming, cross-check | plain text, optional |
| 3 | 阳历生日 (年-月-日) | BaZi, ZiWei, almanac | plain text |
| 4 | 农历生日 + 闰月否 | BaZi cross-check, ZiWei | plain text, ask if 3 not provided |
| 5 | 出生时辰 (HH:MM 或 子/丑/...) | BaZi 时柱, ZiWei 命宫 | AskUserQuestion (12 时辰) or HH:MM |
| 6 | 性别 (男/女) | 大运 顺逆, 紫微 排盘, 用神 | AskUserQuestion |
| 7 | 出生地 (省市) | 真太阳时 longitude + 时区 — 传 `--city 成都` 由 `assets/cities_cn.json` 解析经度与时区; **不要自己猜经度**; 表中无此地才改传 `--longitude` + `--timezone` | plain text |
| 8 | 当前所在地 + 关心议题 (财/感情/事业/健康/学业) | 流年 / 择日 / 解读权重 | AskUserQuestion + free text |
| 9 | 在世状态 (本人 / 已故 / 推他人盘) | ethics check, redirect if 3rd party | AskUserQuestion |

**Confirm collected info as a single block before computing**, e.g. `阳历 1990-05-10 14:30, 男, 北京 (经度 116.4°E), 农历未提供; 关心: 事业 + 感情. 是否正确?`

## Edge cases — input fallback dispatch

Apply these BEFORE casting. Never silently guess.

| Situation | Action |
|---|---|
| 时辰未知 | 仍可排年/月/日柱; 时柱缺如, 标注"时柱待补". 不揣测时辰. |
| 阳历未知, 仅农历 | 用 `lunar_convert.py lunar2solar` 反推; 闰月需用户确认. |
| 农历未知, 仅阳历 | 用 `lunar_convert.py solar2lunar` 自动换算. |
| 出生在节气当日 / 前后 | **必须**问到精确时辰再判月柱归属 (节为月柱分界, 不是初一). |
| 夜子时 (23:00-24:00) | 时柱用次日子时干支, 日柱仍用当日 (子初换日 vs 子正换日两派, 默认子正换日并说明). |
| 闰月 | 农历闰月按本月气论 (节气定月, 与闰月无关); 换算见 `scripts/lunar_convert.py`. |
| 已故亲属推盘 | 经直系亲属同意可推, 但避免预测在世事项; 重点在历史校准与纪念意义. |
| 海外出生 | 必收集出生地经度 + 当地时区; 真太阳时按出生地, 不按北京时间. |
| **夏令时时段出生** | 中国曾 14 次行夏令时 (1919、1940-1949、**1986-1991**), 钟表快 1 小时。时辰边界在整点, 故边界后一小时内出生者时柱整位偏移。传 `--timezone Asia/Shanghai` 由 tzdata 自动折算, **不要**手工减一小时。若用户报的是"户口本时间"或记不清是否夏令时, 明示此不确定性。 |
| 同卵双胞胎 | 同八字; 区分需另行 [紫微](references/02-ziwei.md) 或紫微+八字综合, 或时柱后半 (前/后子). |
| 收养 / 不知生父母 | 仅以已知信息推; 不强补"父母宫缺失"叙事. |

## Required output fields (BaZi readings)

When delivering BaZi readings, **always** surface these fields explicitly (script provides them):

- 四柱 (年/月/日/时, 含天干 + 地支 + 藏干 + 纳音)
- 日主 + 旺衰判定 + 月支司令
- 十神 per pillar (天干 + 地支主气)
- 五行得分 (含 月令加权)
- **用神 / 喜神 / 忌神** (扶抑 + 调候 综合)
- **格局** (正格 / 特殊格 自动判定)
- 神煞触发 (按 起法类别: 年/月/日/干 base)
- 大运 + 当前大运 + 流年
- 真太阳时校正信息 (经度 + 均时差 EOT + 时区/夏令时折算, 若适用)

不省略任何一项。如某项无法判定（如时柱缺）, 明示"待补"而非略过。
