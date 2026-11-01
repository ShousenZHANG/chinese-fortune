# 5.11 输出迁移

面向直接读 `ziwei_calc.py`、`bazi_reading.py`、`fortune_reading.py` JSON 的调用方。只列改了形状或含义的字段；新增字段旧调用方可以忽略。

## 紫微格局 `patterns[]`（不兼容）

| 5.10 | 5.11 |
|---|---|
| `status: "candidate_only"` | 去掉。格局按《全书》原句判，不再一律标候选 |
| `recognition_basis: "project_star_combination"` | 去掉 |
| `source_status: "classical_conditions_not_verified"` | 改为三值：`quanshu_definition`（条件照原句）、`quanshu_reading`（书中有此格，读法有歧义，本项目取一种）、`modern_convention`（所选转录查不到） |
| `evidence` | 保留，内容是 `required` 用「；」串起来 |
| — | 新增 `passage_id`、`quote`（原句，可直接引用）、`extra_passage_ids`（加减条件出处）、`reading_note`（选读说明，仅 `quanshu_reading` 有） |
| — | 新增 `required`、`bonus`、`breaking`、`to_check` 四组条件；`to_check` 是原文说「吉多」「凶多」而没给数量的地方 |

格局名单也变了：旧的「火贪格」「铃贪格」「武贪格」分别由「贪火相逢」「火贵格」「贪狼遇火铃于四墓」「贪武同行」按原句代替；「马头带箭」改名「马头带剑」并改用卷三读法；「辅弼夹命」改名「左右夹命」。旧版「机月同梁」三颗星也报，现在须命在寅申、四星齐会。

## 紫微其他字段

- `miscellaneous_stars_positions` 从 9 颗增到 39 颗；新增 `miscellaneous_stars_basis`：按出处分组，键是段号、「通行表」或「流派选项：…」。
- `school` 从 4 个键增到 14 个，新增 `preset`、`kui_yue`、`tian_ma`、`tianshi_tianshang`、`jie_kong`、`changsheng`、`changsheng_direction`、`year_divide`、`self_transformations`、`da_xian_transformations`。
- `--school nihai` 时 `da_xian[]` 没有 `transformations`，各宫 `self_transformations` 为空列表。
- `horoscope` 新增 `da_xian` 层；各层新增 `stars`，`liu_nian` 新增 `twelve_gods`。
- 新增 `self_check`（`ok`、`checked`、`failed`、`scope`）、`say`（句子列表）、`focus`（未传 `--focus-palace` 时为 null）。
- `--brief-palaces` 时 `twelve_gods_sources` 为 null。
- `--leap-month` 的默认值在解析器里变成 null，算盘时才定为 `split`（`--school nihai` 时为 `next`）；输出的 `input.leap_month` 与 `school.leap_month` 都是最终值。

## `--facts-out PATH.json`（八字与个人运势）

给了这个参数时，JSON 写进文件，屏幕只输出白话草稿和一行文件路径，不再打印 JSON。文件比屏幕版多一个 `facts_file` 标记（`written_by`、`tool`）；同一路径只有带同一标记的文件会被替换，其他程序的 JSON 一律不覆盖。核对正文用 `answer_check.py --answer - --facts PATH`。

## 个人运势

- `intent: period` 的阶段运势（显式 `event.scenario: outlook`，或省略 `event`）即使窗口不足一年，也列出窗口所在年份的 `annual_reading`。
- 阶段运势的 `host_notes` 多一条回答顺序提示，窗口按实际起止写：整日窗口写两端日期，带时刻的窗口写到分钟并说明终点不含。
