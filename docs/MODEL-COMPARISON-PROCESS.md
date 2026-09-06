# 实际回答比较与评审

这套流程区分宿主执行成功、内容审核通过与现实预测能力。前两项需要不同证据；本项目的模型回答实验不验证现实事件预测准确率。

## 固定执行条件

`evals/run_model_comparison.py` 使用指定的 Codex app-server，每题、每次重复创建独立的 ephemeral/read-only 会话。模型与 reasoning effort 必须与宿主实际返回值一致，不自动降级。T01–T04 必须在同一会话中先完成第一轮回答，再发送第二轮，不把两轮资料一起塞进首个提示词。协议参考 [Codex App Server](https://learn.chatgpt.com/docs/app-server)；可接受字段以执行时 CLI 生成的 JSON schema 为准。

每个运行目录保留 `run.json`、每题的 `requests.jsonl`、`events.jsonl`、`host.json`、`turn-N.json`、`answer-N.txt` 与 `record.json`。各次重复另有汇总 `recording-runN.json`。目录必须在受测快照之外且不能覆盖旧目录。`run.json` 记录模型、effort、题集和 runner SHA256、快照内容摘要及执行前后是否变化。版本提交与快照来源还须由实验维护者单独核实，传入一个提交字符串本身不能证明快照来源。

超时、宿主错误、首答与不完整回答都保留。修复后的重试用新实验目录，不替换失败记录。录制文件中的 `review: null` 表示尚未审核；进程退出码 0 不表示回答正确。

## 时间与工具审计

固定 UTC 的比较题是在重演请求，不是实时预测。逐题分别核对以下四项，不互相替代：

1. 是否实际调用了实时取时，输出是否为 `system_utc_clock`。
2. 显式 `--request-time` 是否被如实标为 `provided_instant`。
3. 排盘采用的 UTC 是否与题面一致，出生时区与当前所在地时区是否分开。
4. 正文是否把固定重演时刻误说成现场时刻。

题集另规定一次注入 capture 后共享该 UTC；这项协议执行情况单列。先实时取时、随后按题面 UTC 重演不自动构成时间造假，但不能拿这条轨迹证明排盘沿用了实时时刻。重复排盘也单列，不解释成独立交叉验证。

`item/completed` 按 `(threadId, turnId, item.id)` 去重，不能只数 `turn/completed.turn.items`：后者可能仅含最终回答。host 工具项数与实际 CLI 子进程次数不是一回事。一个 PowerShell/Python 工具项可以循环运行多次排盘或检索。`--help`、读取脚本和脚本名字符串也不等于执行排盘；动态代码无法确认时保留 unknown，并人工查看对应命令及完整输出。

token 用量使用宿主上报的最后一个累计 `usage.total`。同会话多轮用相邻累计终点作差，不能累加每条累计 total。`reasoningOutputTokens` 已属于 output，不能再次加到 total。缺少用量为 unknown，不是零。输入缓存受执行顺序影响，不能将缓存差异全部归因于代码改进；这些数据不等于精确账单金额或订阅消耗百分比。字节统计分别注明提示词、序列化轨迹、捕获输出的范围，不能把它们叫作模型实际总上下文。

## 隐藏版本后评审

使用新目录导出，例如：

```powershell
python evals/blind_review.py --cases evals/reading_cases_v4.json export --source baseline=D:/experiment/baseline/recording-run1.json --source baseline=D:/experiment/baseline/recording-run2.json --source updated=D:/experiment/updated/recording-run1.json --source updated=D:/experiment/updated/recording-run2.json --public D:/experiment/review-public --private D:/experiment/review-private --seed 20260906
```

维护者保存 private 目录，评审者只接收 public 目录。公开清单含随机种子、随机 ID、题目 ID、问题及验收口径，不含版本映射。打乱前按原始记录摘要排序，避免公开种子加已知版本输入顺序直接还原标签。

回答原文保持不变。工具摘要列出有序命令和每份证据文件；完整输出按需读取，避免把整部材料重复塞进评审上下文。显示副本只遮盖宿主 ID、目录和显式工具版本元数据，保留古籍段落 ID。正文、原始有序轨迹、显示证据和完整评审包均有摘要绑定。能力与文风仍可能暴露版本，因此应称“隐藏版本标签的会话内评审”，不能宣称严格双盲或外部独立研究。

评审者填写 `reviews-template.json` 的副本，逐项判 pass/fail，并用自己的话写出主结论、证据与关键限制。阅读理解不能由字数、关键词或术语数量代判。完整输入题仍须完成有依据的分析，不能因拒答较短就给可读性或效率奖励；无依据的确定事件断言也不能因答得多而过关。

```powershell
python evals/blind_review.py --cases evals/reading_cases_v4.json import --public D:/experiment/review-public --private D:/experiment/review-private --reviews D:/experiment/reviews.json --output D:/experiment/reviewed
```

导入重新核对原始记录、显示包、所有工具证据与评审摘要，写入新的 reviewed 副本，绝不编辑原始录制。缺少评审者、判据或复述的条目保持 pending。版本汇总报告每题处置、失败判据和实测用量；成本比较必须在相同题目、相同完成程度下进行，并同时报告失败和部分完成情况。

`evaluate_readings.py` 的结构验收还会检查实际轮次数、顺序、同一 thread 中不同 turn ID、工具轨迹及每条评审的 `answer_sha256`。这些校验保护证据链，不能证明评审者对古文和命盘的理解正确。
