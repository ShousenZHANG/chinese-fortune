# 五部核心古籍全文库

截至 2026-09-06，`knowledge/` 收齐五部书各自锁定来源的全部选定目录：416 个章节或卷单元、8,385 个可检索段落。这里的“完整”仅指下表网络转录版本的目录已收齐，不指所有版本汇编，不指原刻逐页校勘完成，也不代表其中命理断语已经得到经验验证。

## 所选版本与真实边界

| 书与 ID | 本库所选来源版本 | 已获取单元 / 段落 | 核验边界 |
| --- | --- | ---: | --- |
| 子平真诠 `ziping` | 东里书斋网络整理本，声明以 1923 年绍兴育新书局本为底本、中州本参校 | 47 篇正文 + 4 篇古序跋 / 314 | 保留整理者已选字；剥除显式现代校记不能还原底本原字。未核原刻影像。 |
| 滴天髓 `ditian` | 维基文库《滴天髓辑要》逐节转录 | 42 节 / 259 | 题署与辑者按来源保留；正文与注文分层，未校影像。 |
| 穷通宝鉴 `qiongtong` | 古文岛六卷网络转录 | 6 卷 / 1,140 | 五行总论、木、火、土、金、水齐；具体印本未注明，未校影像。 |
| 三命通会 `sanming` | 维基文库文渊阁四库全书本 | 提要 + 12 卷 / 986 | 全卷转录已获取；尚有无 Unicode 编码的源字形，显式标记，未校影像。 |
| 渊海子平 `yuanhai` | 古籍典藏七卷网络转录选本 | 304 篇 / 5,686 | 具体印本未确认，不能称某一五卷刻本全文；疑似转录误字保留，未校影像。 |

来源分别为：[子平真诠目录及版本说明](https://www.donglishuzhai.net/books/63.html)、[滴天髓锁定目录 revision 844410](https://zh.wikisource.org/w/index.php?title=%E6%BB%B4%E5%A4%A9%E9%AB%93&oldid=844410)、[穷通宝鉴六卷目录](https://www.gushiwen.cn/guwen/book_112f16f9deeb.aspx)、[三命通会四库本锁定目录 revision 657391](https://zh.wikisource.org/w/index.php?title=%E4%B8%89%E5%91%BD%E9%80%9A%E6%9C%83%20%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=657391)、[渊海子平来源目录](https://luckclub.cn/bazi/001/)。逐章来源地址与 revision 见 `knowledge/manifest.json` 及章节 JSON。

没有以异本补洞后拼成无版本标识的全集。未采用的候选包括：缺卷十至十二的维基文库普通《三命通会》条目；缺独立“论金”总论的《穷通宝鉴》候选转录；被标记未完成、来源不明的维基文库《渊海子平》候选。选用完整目录版本后，仍如实保留该版本本身的书目不确定性。详细候选调查保存在 `CLASSICAL-SOURCES-RESEARCH.md`；本文件和 manifest 为最终收录范围，调查笔记里的候选 ID 不作为运行接口。

## 保存的是什么

`knowledge/books/<book>/cNNN.json` 保存全段原字、段落层级、章内小标题、固定 passage ID、段落哈希和出处。搜索返回整段及前后相邻段，不把条件删掉后只留吉凶断语。

`knowledge/sources/` 是复核和重建所需的锁定来源材料，**不是完整网站镜像**：

- `.wiki` 是 MediaWiki 固定 revision 的原始 wikitext；正文模板按明确规则展开，未识别标记不静默丢弃。
- `.html` 只含公版原文节点或由已读取原文段落重建的节点。古文岛取 `contson`，古籍典藏取 `#pane-original article#article-content`。现代译文、广告、导航、关键词、现代评注不收录。
- 子平来源因本地 HTTP 超时，经 `web.open/click` 读取后重建文章节点，`extraction_kind=web_open_rendered_text_reconstructed_article`。其 `raw_path` 不是原始 HTTP 响应；已剥除 172 条显式现代夹注，以及现代引言、凡例、读后附记与重新编排的命例附录。正文仍保留网络整理本择字，绝不标成“1923 年影印本忠实转录”。
- `_index.*` 保存所选目录；HTML 目录可为只保留链接与标题的提取结果。`metadata.json` 记录采集时间、目录数量、选择器或提取方法、质量局限；不嵌入整页现代译文。
- `sources/skchar.json` 只保存《三命通会》实际用到的 83 个字形 ID 及源模块映射。57 个有明确 Unicode 对应；其余 26 个保留 `〔字形SK编号：源描述〕` 标记，影响 69 个段落。描述不是擅定的正文字符。映射锁定于 [维基文库 Module:SKchar revision 9013306](https://zh.wikisource.org/w/index.php?title=Module%3ASKchar&oldid=9013306)，带来源哈希和 CC BY-SA 署名。

所有古籍按公版历史原文收录；维基文库转录及映射适用时保留 CC BY-SA 4.0 归属与来源链接。第三方现代译注没有被当作公版复制。项目代码许可证不覆盖来源材料各自的授权。本次没有据网站可访问就推定其全部现代内容可再分发。

## 版本、分层与完整性验收

顶层 `library_id=bazi-five-classics-v1`，清单 `schema_version=2.0`，显式声明 `distribution_kind=source/runtime`。书级信息包括版本、来源、revision 或片段 SHA-256、预期目录、逐章路径/哈希、授权与质量状态。章节另保留来源档案内的原始路径/哈希和段落哈希，既有段落格式没有随发行清单改变。

`passage_id` 形如 `ziping:c008:p0001`，在当前锁定库版本内稳定；不能把新版、重新分段或改字结果冒充同一锁定版本。升级来源须单独审查目录差异、段落 ID 变化、来源 revision 和哈希，不在搜索时自动更新。

已识别的层级包括 `base_text`、`commentary`、`base_text_with_commentary`、`paratext`。子平四篇古序跋单列 `paratext`；三命提要含源注文的段落仍标混合层。渊海明确“眉批”等段落标 `historical_commentary`，夹注段标 `historical_work_transcription_with_commentary`，`commentary_spans` 标出原文字符偏移和括号是否闭合。未独立校核的其余渊海段落保守标 `historical_work_transcription`，不称纯正文；跨段未闭合的注释不用于猜定后段层次。层级标识不等于五书所有古注已经校勘完成。

同一检索词优先匹配章题，再优先已识别正文，避免序跋因多次出现“用神”而压过论用神正文。常见术语与书名支持简繁查询别名；这是有限别名表，不是通用简繁转换，返回原字不变。

`validate_library()` 从实际文件重算以下条件，不盲信 manifest 中写着 `complete`：

1. 五书存在，预期目录非空且无重复；获取章节集合必须与预期集合相等。
2. 目录、来源元数据、字形映射、章节、来源片段和段落哈希一致；路径不能逃逸知识库目录。
3. 每章非空，段落数量、书章身份、段落 ID 不重复。
4. 声明缺章、来源缺口或缺影像页时不能通过完整性验收；未进行影像检查写 `not_assessed`，不写“无缺页”。

完整获取、原文已校与实际应用可靠性是三个不同状态。本库现为 `acquired_not_collated`、`facsimile_status=not_checked`、`historical_edition_verified=false`。哈希只能证明冻结后未改动，不能证明网络转录无错、出处题署正确或个人预测有效。

构建先验证完整源码目录闭包，再把 425 个 HTML/wiki 等原始来源文件移入独立 sources ZIP，运行包保留五书全部章节及来源索引。运行清单逐一校验运行文件和来源档案索引；原始路径明确属于 source_archive/knowledge，不假装文件在运行包内。外部 SHA256SUMS 覆盖两包，清单不做循环自哈希。源码缺来源失败，运行包缺正文失败，目录消失不能自动切换较弱模式。

## 离线使用

```powershell
python -X utf8 scripts/classical_search.py --validate
python -X utf8 scripts/classical_search.py --query 用神 --book 子平真诠 --limit 2
python -X utf8 scripts/classical_search.py --query 庚金 --book qiongtong --chapter 卷五
python -X utf8 scripts/classical_search.py --passage-id ditian:c006:p0008
```

Python 接口为 `search_classics(query, book=None, chapter=None, limit=5)`、`get_passage(passage_id)` 和 `validate_library()`；另可传 `library_root` 供隔离测试。结果包含整段 `text`、`section`、`layer`、`passage_id`、书章、版本、source URL、revision、授权、相邻段 `context`、当前段 `issues` 和校勘状态。

可供解释规则引用的固定起点：

| passage ID | 内容定位 | 使用边界 |
| --- | --- | --- |
| `ziping:c008:p0001` | 八字用神专求月令、顺用逆用 | 是用神定义与条件框架，不能直接生成个人喜忌。 |
| `ziping:c009:p0001` | 用神成败 | 必须配合四柱实际条件与后文救应，不孤取“成”或“败”。 |
| `ziping:c014:p0001` | 气候配合 | 保留所选网络整理本择字，不等同各底本一致。 |
| `ditian:c006:p0007` | 伤官见官原句 | 对应正文；不能省略“可见不可见”的条件差别。 |
| `ditian:c006:p0008` | 同句的注文 | 明确 `commentary`，不得冒充原句或当作条件已成立。 |

全文检索允许研究古籍全部历史材料，但检索命中不自动提高为已核规则，也不直接成为对人的断语。宿主解释层应先核事实和适用条件，再使用可追溯段落；无条件推富贵、寿夭、疾病、性别等级或机械定用神的材料不能仅因“古籍有写”就绕过这一步。

## 维护与验证

`scripts/import_classics.py` 是维护工具，**不进入 runtime skill 包**。正常检索完全离线；显式 `--wikisource` 会重新请求来源，不可把它当只读验证。已冻结的三个 HTML 来源可用 `--captured-html ziping --captured-html qiongtong --captured-html yuanhai` 离线重建；重建前后仍需审查变化。采集新版本或取得原刻后，应保留新的独立版本与校勘记录，不能静默覆盖既有版本边界。

`tests/test_classical_library.py` 覆盖真实五书目录、固定引用、正文/注文分层、简繁术语、整段上下文、正文排序、字形保留、文件篡改、目录缺项、缺页、支持来源哈希及路径逃逸。测试通过表示这些软件约束成立，不代替五书逐字校勘或宿主输出盲评。
