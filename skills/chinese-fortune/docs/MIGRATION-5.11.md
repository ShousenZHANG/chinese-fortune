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
| — | 新增 `required`、`bonus`、`breaking`、`to_check` 四组条件；`to_check` 收两类原文没说死的地方：一是「吉多」「凶多」这类没给数量的说法，只列见到的星；二是原文用词范围未定，如禄马交驰「忌见杀」的「杀」可指七杀或诸煞，只列同宫见到的，多不多、算不算都不替原文定 |

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

## 六爻 `fu_shen`（新增）

`liuyao_cast.py coins` 顶层新增 `fu_shen` 列表，问题对应的用神六亲在本卦都出现时为空列表。每项一个六亲：

- `status: "taken_from_calendar"`：月建或日辰就是这个六亲，按《增删卜易》先以日月为用神（zengshan:c032:p0049），`calendar` 写是哪一个，`fu_shen` 为空。
- `status: "hidden"`：到本宫首卦（`pure_hexagram` 为卦序）找同一六亲的爻，`fu_shen` 每项给伏爻位置与干支五行、同位本卦飞神（`fei_shen`）以及 `relation`（飞神生伏神、飞神克伏神、伏神生飞神、伏神克飞神、飞伏比和）。

只给位置与生克，伏神得不得用不判；`source_ids` 列出所据段落，含野鹤不用伏神、主张再占的一段（c032:p0094）。Markdown 两种状态都写明这一点。

## 个人运势

- `period` 新增 `近期`（别名 `最近`、`这段时间`：今天到年底，剩不到一个月时算一个月）与 `年底前`；路由遇到「最近」不再要求追问时间范围。
- `intent: period` 的阶段运势（显式 `event.scenario: outlook`，或省略 `event`）即使窗口不足一年，也列出窗口所在年份的 `annual_reading`。
- 阶段运势的 `host_notes` 多一条回答顺序提示，窗口按实际起止写：整日窗口写两端日期，带时刻的窗口写到分钟并说明终点不含。
