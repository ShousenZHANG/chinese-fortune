# 前瞻验证：先记录，再看结果

仅在用户授权跟踪时使用；已有授权直接沿用。默认路径为用户目录下 `.local/share/chinese-fortune/predictions/records.sqlite3`，可用 `CHINESE_FORTUNE_DATA_DIR` 或 `--data-dir` 指定仓库外目录。数据不进入技能包。采用本机 SQLite 事务和修订号防止覆盖，不自动联网。

## 分析顺序

1. 先固定可观察的事件定义、地点时区、起止时间、主方法与版本。例如“在当地周一零点至下周一零点前，收到至少一封新的面试邀请”；Offer、面试邀请分别记录，不用“有好事”作可变标准。同一跟踪范围内所有问题均先登记，不能只挑有把握的问题。
2. `begin` 在分析前登记。原始资料已确认后，生成匿名随机 `subject_id`（32位小写十六进制），对规范化输入计算 SHA256 作 `input_fingerprint`，不写姓名、生辰、雇主或整段问答。自由文本不会自动脱敏，宿主必须避免写个人详情。摘要也不是加密。
3. 固定主方法后核实际盘面、原文条件、例外和时间粒度。原文相反时依上下文及例外处理；分歧无法解决直接说明。不得改用另一方法、重复起卦、投票直到得到喜欢的答案。
4. 窗口开始前 `seal` 冻结判断。证据不足仍记录 `unable`；未完成的草稿也留在分母。确定结论只表示所述条件下的传统判断，不保证现实发生。无事件粒度依据就不能把命局背景升级成具体事件预测。
5. 窗口结束后按用户明确反馈 `observe`；没有反馈不等于未发生。发生时间采用左闭右开区间 `[start,end)`。中途已有成功反馈可以保存，但到期后才进入命中率。
6. `show` 查看、`correct` 添加更正说明；更正实际结果用新的 `observe`，保留旧结果和理由。方法与原预测不可覆盖。误登记可说明或按用户要求删除，不能偷偷改写为命中。

## CLI 与数据字段

所有操作：`python scripts/prediction_log.py <action> --stdin`，以标准输入发送 JSON，检查退出码及 `ok`。不要把个人数据放在命令行或仓库里的临时文件。`--help` 列出动作。工具不会自行判断用户是否真的同意，`consent`/`confirmed` 由宿主依据真实授权填写。

`begin` 接受且仅接受：

```json
{"consent":true,"subject_id":"0123456789abcdef0123456789abcdef","event_definition":"收到至少一封新的面试邀请","timezone":"Australia/Sydney","start":"2099-10-05T00:00:00+11:00","end":"2099-10-12T00:00:00+11:00","method":"事前选定的主方法","method_version":"已固定版本","input_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
```

以上是格式示例，时间、随机编号、指纹、方法必须来自本次真实处理，不能照抄。开始和结束均须含 UTC 偏移，按所给 IANA 时区保存，开始必须晚于当前时间。

写操作外层统一为 `{"id":"begin返回的id","expected_revision":1,"payload":{...}}`。每次使用最新修订号；过期修订失败后先读取，不能盲目重试覆盖。

| 动作 | payload |
|---|---|
| seal | `prediction`：`happens` / `not_happens` / `unable`；`reason`：理由；`evidence` 和 `conflicts`：列表 |
| observe | `confirmed:true`，`result`：`happened` / `not_happened` / `unknown`，`occurred_at`：带时区发生时间或 null，`note`：用户反馈依据或更正原因 |
| correct | `note`：更正说明，不能覆盖原预测 |
| delete | `confirmed:true`，删除该条及全部历史，保留匿名删除总数 |

`show` 输入 `{"id":"记录id"}`；`list` 与 `stats` 输入 `{}`，都返回状态汇总，`show` 才返回单条详情。

每条 `evidence`：`passage_id`、`quote`（不超过500字的原文短句）、`condition`（条件与例外核查说明）、`state`（`met` / `not_met` / `unknown`）、`personal_fields`（实际核查的输入路径列表，如 `birth.day`，不含原始值）、`scope`（`event` / `background`）。每条代表所需支持条件；排除条件写成“已确认不触犯某例外”并核实，不能将未查写成已满足。程序核引文是否属于指定段落并存原文摘要，但不会认证路径与条件的语义对应，也不会认证现实预测有效。

每条 `conflicts`：`issue`、`resolution`、`evidence_indices`（本次 evidence 的从0起索引）。空 resolution 表示未解决；解决说明必须引用对应证据。明确事件判断要求所有支持条件为 met、至少一项事件粒度依据、无未解决分歧。仅填写 `scope:event` 不会创造事件依据，宿主仍须审查原文原义和本人的适用性。

临时补查来源先完成候选库审核；未进入可核对的固定段落库时，不伪造 passage_id 或借用无关段落。已支持部分可在正文回答，当前记录不能通过核查就用 `unable` 并说明缺口。

## 怎样读统计

- `answer_coverage`：到期且给出事件判断 / 全部到期记录，未完成和无法判断仍在分母。
- `outcome_confirmation_coverage`：已确认结果 / 到期且给出事件判断。
- `observed_hit_rate`：命中 / 已确认结果；没样本是 null，不是100%。必须同时展示前两项、样本数、待确认及删除数量。
- `cohorts` 按方法、版本、事件定义分别计算。总览只是描述汇总，不用于比较不同问题或版本优劣。同一事件定义应复用一致文字，不能改名拆走失败样本。

这是用户自选样本和自报结果，既非因果试验，也不是术数有效性证明。选中日期成功不能证明比没尝试的日期更好。现有命中率不能用于保证下一次结果。

本机数据库不是防篡改公证，也未加密；操作系统权限、备份和对话历史由各自系统管理。删除会清除本数据库中的记录和历史，但不承诺清除外部备份或宿主聊天。无记录时查询不创建数据库。
