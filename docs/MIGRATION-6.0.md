# 6.0 迁移说明

6.0 合并了原计划的 5.11（紫微、流派开关、回答骨架，见 [MIGRATION-5.11](MIGRATION-5.11.md)）和后续出生资料、关系、卦课及报告条目。无独立算法依据的流派、未转录的林辞和人工判断项仍明确保留。下面只列调用方要知道的变化。

## 所有工具

- **成功结果多一个 `envelope`**：`version`（`cf-result/1`）、`method`（方法快照）、`conventions`（时区、真太阳时、日界等约定）、`replay`（种子、原始爻、请求时刻，或指向顶层 `input`）、`next_step`。只从结果已有字段摘出，不新算。原有字段不变。
- **失败信封多两个键**：`error_class`（`input` 改输入、`context` 补时区、`choice` 从 `candidates` 选、`unsupported` 如实说不支持、`environment` 跑 `doctor.py`、`integrity` 规则链断开须修数据而非改输入）和对应的 `next_step`。
- `rule_registry.py` 是维护工具，不进运行包，也不经 MCP。

## 八字与出生资料

- `birth_candidates.py`：出生时间是一段范围或几个候选时，列出不变的柱、会变的柱，以及各自影响哪些结论。
- `birth_correction.py`：资料更正后列出改了哪项、哪几柱跟着变、哪些旧结论作废。
- 两个入口的成功结果新增可直接回放的 `input`、`method`、`time_context` 和实际计算上下文。更正的 before、after 都须明确提供年月日与性别；时辰仍可未知。可选默认设置经规范化后比较，同义输入不再形成伪更正。
- 候选格式严格为出生地当地公历分钟 `YYYY-MM-DDTHH:MM`。带 offset、Z 或秒的字符串明确失败。`birth.fold` 保留两次重复钟点的选择；跨夏令时偏移变化或含不存在钟点的范围须分开提交。范围端点包含在内，最长72小时。不变的是柱的干支，十神等相关判断仍须随变化的日主重核；段内起运只记录段首样本。
- 农历闰月支持负月份。更正入口的正月数加 `leap:true` 规范为负月数；负月数与显式 `leap:false` 冲突，公历不接受闰月标记。历算库核实该年是否确有该闰月。
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
- 择时现在覆盖完整当地日期，包括23点至午夜。`start`、`end`、`sampled_at` 为含日期和 offset 的 ISO 时刻，区间左闭右开；`window` 仅供显示。交节、时辰与时区变化处拆段，按 UTC 排序，重复钟点列两次，不存在的钟点不编造，跳过的日期列在 `skipped_dates`。`candidates` 与 `excluded_windows` 合起来覆盖请求，`excluded` 按分段区间计数。
- 起盘取各段起点，节气按真实瞬间、日时按有效当地钟面。与 `qimen_cast` 比较须显式指定 `--plate-method dunjia-zhuanpan --ju-method futou`；默认 `yuanling-core` 不变。秒级切点属于随包历算模型，不是绝对天文精度保证。

## 紫微运限

- `--year-divide` 同时控制本命与目标流年。选定的年干支驱动流年四化、流曜、宫位、十二神、斗君与流月五虎遁月干；目标原始农历资料另列，不被改写。流月仍按农历月，虚岁和大限仍按农历年，`age_basis` 写明此口径。
- 各活动层的 `twelve_gods` 随本层地支安将前、岁前十二神；未到大限或未请求流时仍为 null。依据固定 Renhuai 现代软件口径，来源与 anchor 随结果提供，不冒称《全书》直接记载。其第七岁前标签是岁破，本项目保留大耗兼容名称并披露位置命名差异。
- 本命立春年界使用原始出生瞬间转为历库的固定 UTC+8，再判断交节。真太阳时和晚子换日仍只处理对应的排盘日期与时辰，不能移动天文交节；海外出生时区也参与瞬间转换。默认农历年取法不变。
- 目标运限 API 的 `--horoscope-date`、`--horoscope-time` 仍是无时区的当地钟面，不做目标时区转换。只给日期时以正午代表并披露；目标立春年界先于晚子时的日界调整。输出标明历算库。不同软件的秒值与时间标度不能直接互当真值。

## 大六壬

- 涉害、昴星、别责、遥克俱比俱不比都已实现，720 种盘全部给出三传。`method_profile.inferred` 标出遥克转涉害时计克方向是推定。

## 风水

- 新增 `fengshui_measure.py`：测量角度换二十四山坐向；`measurement`（测量事实）与 `tradition`（二十四山分类）分开，误差跨山时 `ambiguous: true`，要求复测。

## 焦氏易林

- 新增 `yilin_lookup.py --from 本卦 [--to 之卦]`：返回 `versions[]`（`yilin` 四部叢刊本、`yilin_siku` 四库本）的原文、`passage_id`、`sha256` 和注文；某本缺这一林时 `text` 为 null 并给 `reason`。古籍库多了 `yilin`、`yilin_siku` 两部书，`search_with_scope` 的检索范围随之变为 15 部。
- 四库切分在去换行前识别标题，保留可核对的 `source_span`。维护者可用 `import_classics.py --yilin-siku-frozen-from knowledge --output-dir <新目录>` 从现有冻结来源离线重建四库本。四部缺林、未定归属与版本异文照列。
- 三份采集来源文件由 `metadata.json` 按原字节改名为 `capture-metadata.json`，避免 skills 安装器过滤该保留文件名。清单路径同步，原始摘要与严格来源校验保留。

## 姓名

- `characters[].stroke_source` 标出笔画来自康熙表、内置简表还是默认估算；`layers` 列出算了的层与没算的层及原因。

## 回答核对

- 省略号删掉「不可以」这类否定加情态、删掉「忌」「畏」、引文开头截掉否定字，都报 `elision_drops_negation`；省略号删掉「而隔位」「須要旺相」这类条件、只留后面的「則…」「方…」结论，报 `elision_drops_condition`。
- 「不要把……理解成必然……」这类否定框架不再误报确定性断言。
- 公共 `answer_check` 的 facts 须保留实际成功工具 JSON 的身份和结构。`facts_loaded` 计准入结果，`chart_facts_loaded` 单列可用命盘；失败兄弟仍报错，A/B 人物不混用。结构准入不能认证 JSON 作者或算法正确性。
- 资料更正的前后盘保留阶段身份。支持的“更正前／原来”和“更正后／当前”等断言分别核对；未标阶段的当前断言采用输入顺序最后一份更正的 after。该机制不理解任意跨句指代，仍须语义复核。
- 引文只由冻结语料核对，书名、段号和文字须属于同一来源。任意检索文字、备注或错误消息不能替原文作证。条件省略检查是有界启发式，机械通过仍须语义核对。
- `yilin_lookup` 的双版本单林与64林列表可作为来源 facts，计入 `facts_loaded`，不计为命盘。缺文与未定归属须保留原 `reason`；准入这些来源结构不扩大引文权威。
- `lunar_convert`、`jiemeng_lookup` 新增成功身份和通用信封，原 payload 字段保留。公历换算在历库归一化前拒绝不存在的日期，沿用公共日期校验的1900至2100年支持范围；反向农历仍由历库核实。
- 录制检查优先使用真实 argv。旧文本只解析可确认的字面 Python 调用和 stdout 重定向；动态命令或未支持的包装记 `unverified_command`。flags 按选项元数核验，问题里的参数名、help、读源码均不能冒充执行。
