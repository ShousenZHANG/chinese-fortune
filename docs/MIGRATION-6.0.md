# 6.0 迁移说明

6.0 合并了原计划的 5.11（紫微按《全书》补全、流派开关、回答骨架，见 [MIGRATION-5.11](MIGRATION-5.11.md)）和 5.12–6.0 的全部条目。下面只列调用方要知道的变化。

## 所有工具

- **成功结果多一个 `envelope`**：`version`（`cf-result/1`）、`method`（方法快照）、`conventions`（时区、真太阳时、日界等约定）、`replay`（种子、原始爻、请求时刻，或指向顶层 `input`）、`next_step`。只从结果已有字段摘出，不新算。原有字段不变。
- **失败信封多两个键**：`error_class`（`input` 改输入、`context` 补时区、`choice` 从 `candidates` 选、`unsupported` 如实说不支持、`environment` 跑 `doctor.py`）和对应的 `next_step`。
- `rule_registry.py` 是维护工具，不进运行包，也不经 MCP。

## 八字与出生资料

- `birth_candidates.py`：出生时间是一段范围或几个候选时，列出不变的柱、会变的柱，以及各自影响哪些结论。
- `birth_correction.py`：资料更正后列出改了哪项、哪几柱跟着变、哪些旧结论作废。
- `pillars_to_dates.py`：由四柱反查可能的出生日期与时间窗口。
- `--city` 遇到同名区县（朝阳、鼓楼、通州……）返回 `ambiguous_city` 和 `candidates`，查不到返回 `unknown_city` 和相近名；不再静默取一个。
- `bazi_calc.py --death-date`：已故者的大运、流年截到去世那年，输出 `deceased` 和享年。
- 「补什么」：`colour_advice.layers` 分 `traditional`、`practical`、`unsupported` 三层。
- `bazi_reading.py --report-style professional` 报告加四柱表、离线 SVG 命盘图和条款核查表；`--report-redact` 生成分享预览，隐去干支（含单个天干地支）、出生日期时间地点、问题原话和公历年份，不附完整 JSON。

## 合婚与关系

- `pair_facts` 增加 `relation`（`marriage`、`parent_child`、`partnership`、`friendship`），条款按关系筛选；合婚另给 `sanyuan_jiugong`（《选择要略》三元九宫合卦，附《协纪辨方书》驳议）。MCP `pair_facts` 同步加 `relation`。
- 路由在关系未明时先问关系，再分轮收集两人资料。

## 六爻

- `rule_checks`：47 条规则里能由盘面判定的条件自动判，分 `met`、`met_pending_manual`、`not_met`、`manual_only`；`--target-position` 指定主事爻。
- `reading_plan`：先主判（用神），再旁证（元神、忌神、仇神、世应、卦形），神煞卦辞只作参考；宽泛问题先请用户点名一件事。

## 奇门

- 新增 `--plate-method dunjia-zhuanpan`：《遁甲演义》转盘全盘（八宫环转、中五寄坤二、八神阳顺阴逆），`patterns` 按卷二原文判七类格局，每条带 `passage_id` 与原字 `quote`，异说标 `variant`；原文写不清的列在 `patterns_not_computed`。
- `rotating-compat` 不再判格局（旧判定把青龙返首与飞鸟跌穴颠倒，已删除），`patterns` 恒为空。
- 新增 `qimen_select.py`：一段日子里逐时辰列出有吉格又不犯原文禁忌的时辰，按时间排列，不分高下。

## 大六壬

- 涉害、昴星、别责、遥克俱比俱不比都已实现，720 种盘全部给出三传。`method_profile.inferred` 标出遥克转涉害时计克方向是推定。

## 风水

- 新增 `fengshui_measure.py`：测量角度换二十四山坐向；`measurement`（测量事实）与 `tradition`（二十四山分类）分开，误差跨山时 `ambiguous: true`，要求复测。

## 姓名

- `characters[].stroke_source` 标出笔画来自康熙表、内置简表还是默认估算；`layers` 列出算了的层与没算的层及原因。

## 回答核对

- 省略号删掉「不可以」这类否定加情态、删掉「忌」「畏」、引文开头截掉否定字，都报 `elision_drops_negation`。
- 「不要把……理解成必然……」这类否定框架不再误报确定性断言。
