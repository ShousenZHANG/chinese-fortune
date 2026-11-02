# 5.10 开发版：调用与核对

本轮基于 v5.9.1，尚未正式发布。新增字段和候选规则不代表已证明预测准确，也不代表全部传统规则已自动化。

## 八字入口

`bazi_reading.py` 完整结果 schema 从 2.0 升至 2.1。默认仍为完整 JSON，原字段保留；新增 `geju_review`，包括成格、败格、成中带忌、败中救应、变化线索和保留本格。46 条登记例式按实际月令与日主筛选，解释条件均独立列出。

```sh
python scripts/bazi_reading.py --year 2000 --month 1 --day 15 --hour 10 --minute 30 --gender male --city 北京 --as-of-year 2026 --question "看大运与格局" --view compact
```

这是虚构测试资料。纯原局和明确参考年不要求现居地；问“当前/今年/明年”则需现居地时区与同一请求时刻。出生时区仍依出生地处理，不以现居地替代。

`--view compact` 为显式选择：

- 四柱、结论、未知、反例、输出约束保留。`rule_assessment.routes[].condition_refs` 指向 `rule_assessment.conditions`，其详细事实路径在 full 中。
- `geju_review.cases[].unresolved_conditions_refs` 指向 `geju_review.unresolved_conditions`；观察项的 `groups_refs` 指向 `geju_review.groups`。引用为去重，不是删除条件。
- 大运 `scenario_ref` 指向 `luck_index.scenarios`；干支 `verdict_refs` 指向 `luck_index.verdicts`。当前/下一步运共用的原局前提和句子只传一次，展开后与 full 完全相同；必须读取引用，不能只取汇总词。
- `evidence_bundle` 改为 `evidence_index`（段号列表）；`observations` 替代重复的 `reading_support` 和 `observed_structure` 展示。通用十年流年列表及部分大运辅助字段只在 full 中。
- 引用或解释前运行 `classical_search.py --passage-id <段号>` 取原文及上下文。需要完整细节时，以相同出生资料、参考年、问题、request_time 运行 `--view full`；不要重新取当前时刻。
- `--markdown` 仍输出盘面说明骨架，优先于 JSON 的 view 选项；它不是已完成的个人推断。
- compact JSON 省去缩进空白；体积验收分别记录同格式数据大小与实际 CLI 字符量，不把字符减少当作模型 token 或费用同比减少。期间短答只给大运候选、未判原因与出处，`fortune_reading.py --detail` 展开完整条件和反例，JSON 始终保留完整结果。
- `reading_support.py --stdin` 同时接受 full/compact。未传 `packet` 时从同一 `chart_facts` 生成并检查事实记录；这不代表已审核宿主新增解释。审核新增主张须显式提供 `packet`，并继续做正文语义复核。

## 取运与格局语义

八家取运共 49 个候选配法，其中五家新增 30 个。原文及哈希固定在 `assets/luck_rules.json`；格局观察来源固定在 `assets/geju_rules.json`。引文哈希与完整段落哈希分开标注。对应《子平真诠》冻结转录，尚非影印逐字校勘。

- 运干与运支分别匹配；“透官/透杀”只匹配天干；地支本气仅作检索入口，不能代替刑冲会化核查。
- `conditional`：解释条件或例外未决。`mixed`：已列配法说法冲突。`partial`：只有部分配法提到。三者均不能合成共同喜忌；`not_mentioned` 不等于吉、平或没有风险。
- 新配法的 `unresolved_conditions` 未核实，匹配的句子保留为假设条件下的说法。`pending_actions` 保留不能直接映射成十神方向的作用，如“制伏”“植根”；七杀用伤官的继承映射仍须逐项核。
- `source_passage_ids` 包含主句、跨段反例和相关前提；完整八字证据包纳入这些段落。轻重、作用有效性、去留和句法分歧不由数量评分决定。
- 格局 `literal_state:met` 只说明所列字面条件齐；`verdict:unresolved`、`status:needs_interpretation` 仍保留。某条形态不符不代表整盘败格；有变化线索也须核 `preserves_original`。
- 原文“支全”按全成员核；“会午会戌”保留范围解释。未知时柱不能证明“无”，月支自藏一字不能直接证明原文“逢”字所说的作用。

## 报告与路由

同一次八字调用加 `--report <技能目录之外的新路径.html或.md>` 可显式保存；父目录须存在，已有文件不覆盖，解析后的路径不能位于技能/仓库内，避免个人资料混入发行包。失败返回 `ok:false/error:report_unavailable` 和非零退出码。报告包含工具事实、条件及完整资料，不冒充宿主已完成的解释。HTML 无脚本、字体或网络依赖，使用原生折叠、可见键盘焦点和可换行文本；Markdown 问题按普通文本转义。个人问答默认不落盘。

路由新增 `method`、`multi_method`、`knowledge`、`compatibility`。`needs` 表示输入要求，调用方必须扣除上下文中已有资料。多法按 `steps` 分别执行并保留分歧，不混算总分；合婚只准备各人的盘和核对流程，没有新增合婚分数。已有卦象或抽牌直接复用，命令模板不授权重新随机。

## 新增字段（可照抄的 say 句子与年龄）

均为新增键，旧键不变：

- `chart_facts.true_solar_time.say`：真太阳时比钟表读数多或少几分钟。
- 时辰未知时未定柱的 `candidate_windows` 与 `say`：各钟表时段对应的干支；夏令时回拨的重复钟点写明第一次、第二次各是哪一柱。
- `chart_facts.da_yun[].say`：每步大运的年份、周岁与虚岁起点。
- `chart_facts.age_at_request`：带 `--request-time` 与现居地时区时，请求当天的周岁和虚岁（按出生钟表日期与农历年）。
- `luck_reading[].scenarios[].say`：每个候选配法逐字判喜判忌，以及字面条件是否已满足。
- `geju_review.say`：格局只到候选。
- `classical_search` 结果的 `say`：零命中时说明只代表所查转录本或所限范围；有命中时为 null。
- `pair_facts.say`：按合、冲、刑、害、会、同柱、同类分组，最后一行日主互见。
- `derivation`：日柱手算（以 1900-01-01 甲戌日为基准）与起运换算。

宿主遇到 `say` 时照抄，不自行改写方向、对应关系或年龄。

## 验收边界

以虚构四柱、冻结原文和真实 CLI 验证：源引用、反向例外、作用范围、未知时辰、完整会支、保留本格、详简一致、报告转义及不覆盖。离线包还必须验证新资产和脚本实际可达。完整 pytest（含 slow）、ruff、mypy、原文验证和打包冒烟单列；实际宿主执行与语义审查单列，不继承旧版本成绩。
