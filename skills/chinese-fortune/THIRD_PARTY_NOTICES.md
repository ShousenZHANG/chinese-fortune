# Third-party notices

The project's own code and documentation use the [MIT license](LICENSE). That grant does not replace the terms for the third-party material below. The [product disclaimer](DISCLAIMER.md) adds no license restrictions.

## Distribution scope

This document and every linked license text accompany the installable skill folder, runtime ZIP, and corpus-source ZIP. The corpus-source ZIP contains the frozen corpus and its source records, not the runtime packages, life-guide dataset, or adapted application code. Paths for those runtime-only components appear as code literals below. Keeping their notices in the source ZIP does not imply that their code or data is present there.

[The bundled provenance index](knowledge/manifest.json) records the selected editions, each chapter's source URL and fixed revision or content hash, licensing statements, and supporting sources. In the runtime ZIP, raw-source paths in that index refer to the companion source ZIP. The source ZIP and checkout contain the archived raw inputs. The index is an attribution and provenance record, not a blanket grant of rights.

## lunar-python 1.4.8

Copyright (c) 2020 6tail. Upstream is [6tail/lunar-python](https://github.com/6tail/lunar-python), distributed as `lunar-python==1.4.8`.

The runtime includes `scripts/lunar_python/` and `scripts/lunar_python-1.4.8.dist-info/` without local source edits. The complete upstream [MIT notice](licenses/lunar-python-MIT.txt) is copied here so it is also readable without the runtime vendor directory. The original notice and RECORD remain in that directory.

## tzdata 2026.3

Copyright (c) 2020, Paul Ganssle (Google). Copyright (c) 2026, Stan Ulbrych. Upstream is [python/tzdata](https://github.com/python/tzdata), distributed as `tzdata==2026.3`.

The runtime includes `scripts/tzdata/` and `scripts/tzdata-2026.3.dist-info/` without local edits. Preserve the upstream [copyright and license notice](licenses/tzdata-NOTICE.txt) and [complete Apache License 2.0](licenses/tzdata-Apache-2.0.txt). These standalone copies retain the vendor notice bytes. The upstream package contains the IANA time-zone data. This notice does not assert ownership of that data.

## HowToLiveBetter text and adapted code

《高性价比人生指南》，eternity4719，https://github.com/eternity4719/HowToLiveBetter.

The fixed source is [commit 842e11c9d51fac7943e5abb4e332e29b460b5061](https://github.com/eternity4719/HowToLiveBetter/tree/842e11c9d51fac7943e5abb4e332e29b460b5061), snapshot date 2026-10-05. The text in runtime `assets/life_guide.json` is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The [complete CC BY 4.0 text](licenses/CC-BY-4.0.txt) accompanies this notice.

Changes to the text are recorded in the dataset. It was frozen at that commit and converted to JSON. Three entries and the paragraph that retells them in the section 6 introduction were omitted to fit the product scope. The remaining entries, introductions, and long articles retain their wording. Corrections are separate `errata` fields and do not replace the source wording. Local region-review fields and resolved cross references are separate from that text.

The search and ranking algorithms were ported from `index.html`, the reference checks from `tools/check-refs.mjs`, and the decision workflow from `skills/life-decision-guide`. The local adaptations are in `scripts/life_guide.py`, `scripts/life_search.py`, `scripts/life_decision.py`, and `scripts/life_guide_refs.py`. They use Python data structures and the project's CLI and result conventions. Upstream code is MIT, Copyright (c) 2026 eternity4719. Preserve its [complete MIT notice](licenses/HowToLiveBetter-MIT.txt) independently of the text's CC BY terms.

## Frozen historical corpus

The following 15 book entries identify selected transcriptions, not all editions of each work. Runtime chapter JSON and the companion source archive retain the provenance described in [knowledge/manifest.json](knowledge/manifest.json). Each entry's chapter list supplies the fixed chapter revisions and URLs. Keep those records with redistributed excerpts or adaptations and identify the particular book, chapter, and passage used.

| Book ID | Title | Source index | Fixed revision or index hash |
| --- | --- | --- | --- |
| `ditian` | 滴天髓 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E6%BB%B4%E5%A4%A9%E9%AB%93&oldid=844410) | `844410` |
| `dunjia` | 遁甲演义 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E9%81%81%E7%94%B2%E6%BC%94%E7%BE%A9+%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=625948) | `625948` |
| `liuren` | 六壬大全 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E5%85%AD%E5%A3%AC%E5%A4%A7%E5%85%A8+%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=1788462) | `1788462` |
| `meihua` | 梅花易数 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E6%A2%85%E8%8A%B1%E6%98%93%E6%95%B8&oldid=2188971) | `2188971` |
| `qiongtong` | 穷通宝鉴 | [fixed source](https://www.gushiwen.cn/guwen/book_112f16f9deeb.aspx) | `sha256:0bb1de935709c129e79f61fe287365a91a10f8b49070056f970d8f0fb0188c5f` |
| `sanming` | 三命通会 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E4%B8%89%E5%91%BD%E9%80%9A%E6%9C%83+%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=657391) | `657391` |
| `xieji` | 协纪辨方书 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E6%AC%BD%E5%AE%9A%E5%8D%94%E7%B4%80%E8%BE%A8%E6%96%B9%E6%9B%B8+%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=627189) | `627189` |
| `xuanze` | 选择要略 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E9%81%B8%E6%93%87%E8%A6%81%E7%95%A5&oldid=2414024) | `2414024` |
| `yilin` | 焦氏易林 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E7%84%A6%E6%B0%8F%E6%98%93%E6%9E%97+%28%E5%9B%9B%E9%83%A8%E5%8F%A2%E5%88%8A%E6%9C%AC%29&oldid=1398264) | `1398264` |
| `yilin_siku` | 焦氏易林（四库本） | [fixed source](https://zh.wikisource.org/w/index.php?title=%E6%98%93%E6%9E%97+%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29&oldid=657341) | `657341` |
| `yuanhai` | 淵海子平 | [fixed source](https://luckclub.cn/bazi/001/) | `sha256:8568837f98036c79d44b32b3cb7aebc746c260a87f661333cdc41ca6c6768633` |
| `yuanling` | 奇门遁甲元灵经 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E5%A5%87%E9%96%80%E9%81%81%E7%94%B2%E5%85%83%E9%9D%88%E7%B6%93&oldid=8259389) | `8259389` |
| `zengshan` | 增删卜易 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E5%A2%9E%E5%88%AA%E5%8D%9C%E6%98%93&oldid=2572918) | `2572918` |
| `ziping` | 子平真詮 | [fixed source](https://www.donglishuzhai.net/books/63.html) | `sha256:c5e5f8820f381d2ee94c717394d0a8867210e67caa0d6a566c86e8712685b3dc` |
| `ziwei` | 紫微斗数全书 | [fixed source](https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8&oldid=850736) | `850736` |

### Wikisource transcriptions and contributor attribution

For `ditian`, `dunjia`, `liuren`, `meihua`, `sanming`, `xieji`, `xuanze`, `yilin`, `yilin_siku`, `yuanling`, `zengshan`, and `ziwei`, attribution is to Wikisource contributors. Follow the fixed Wikisource source URLs in the manifest. Each page's history identifies the contributors to that revision. Retain those source links and the contributor attribution when sharing the transcribed material.

The recorded distinction is "Public domain: historical work" for the historical original and "Wikisource attribution retained; CC BY-SA 4.0 where applicable" for its transcription. The latter is qualified. It does not assert that every historical character is copyrighted or that every jurisdiction treats a transcription identically. Where CC BY-SA 4.0 applies, preserve attribution, identify changes, and share adapted material under the applicable ShareAlike terms. The [complete CC BY-SA 4.0 license](licenses/CC-BY-SA-4.0.txt) and [upstream license page](https://creativecommons.org/licenses/by-sa/4.0/) accompany that statement.

The project extracts chapter and passage JSON, assigns stable IDs, separates text layers and commentary, and adds quality and provenance fields. It preserves source characters and records uncertain or unencoded characters. Template expansion, paragraph separation, and the two distinct 焦氏易林 versions have the limitations recorded in the manifest. Collection completeness does not establish image collation or textual accuracy.

### Three historical-only HTML sources

- `qiongtong`, 穷通宝鉴. Attribution is 古文岛/古诗文网，各卷附原始来源地址. The selected historical original text is extracted from the original-text HTML nodes. Modern translations and commentary are excluded. The particular printed edition is not stated by the source.
- `yuanhai`, 淵海子平. Attribution is 古籍典藏 luckclub.cn; each chapter retains its source URL. The source requests attribution. The import selects historical original text and excludes modern materials. Its source records retain the selected readings and punctuation.
- `ziping`, 子平真詮. Attribution is 沈孝瞻题署正文；胡焜、赵舒翘、李星科古序跋；网络来源东里书斋. This is the site's editorial version using the 1923 绍兴育新书局 edition and 中州本 comparisons. It retains the editor's selected characters and punctuation. The import excludes the modern introduction, editorial guidelines, modern afterword, example appendix, and explicitly marked modern notes. Removing those notes cannot restore the original printed characters. The captured article HTML was reconstructed from returned source paragraphs after direct HTTP retrieval failed, as recorded in the source metadata.

For these three sources, the recorded scope is public-domain historical original text only. No CC license or general permission for a site's modern editorial work is asserted. The archived HTML and capture metadata in the source ZIP document extraction and provenance. Their inclusion does not grant rights in excluded site content or resolve any rights in modern editing, selection, or punctuation. Reusers must preserve these editorial-version boundaries and assess the rights applicable to their use.

### Supporting SKchar material

The supporting source is Wikisource contributors' [Module:SKchar revision 9013306](https://zh.wikisource.org/w/index.php?title=Module%3ASKchar&oldid=9013306), recorded in `supporting_sources` in the manifest. The source archive contains `knowledge/sources/skchar.json`. The importer uses that character table to represent otherwise unencoded source glyphs in chapter JSON, retaining explicit glyph markers. The module's recorded license is CC BY-SA 4.0; Wikisource contributors. Retain the module link and contributor attribution, indicate adaptations, and apply the relevant ShareAlike terms. The [full license](licenses/CC-BY-SA-4.0.txt) is bundled.

## OpenCC-derived character mapping

The runtime `assets/han-variants.json` is a changed, single-character subset derived using `opencc-python-reimplemented==0.1.7`, whose distribution includes OpenCC dictionary data and configurations. Upstream [OpenCC-Python](https://github.com/yichen0831/opencc-python) identifies [OpenCC](https://github.com/BYVoid/OpenCC) as their source. The project's maintenance generator `scripts/build_han_variants.py` uses the `t2s` configuration. All 1803 stored mappings reproduce with the pinned converter and dictionaries.

Changes select characters occurring in the frozen corpus, convert each character separately, discard unchanged and multi-character results, and store the remaining mappings as JSON with corpus coverage metadata. This is a dictionary-derived subset. Preserve the exact [OpenCC-Python LICENSE](licenses/OpenCC-Python-Apache-2.0.txt) and [NOTICE](licenses/OpenCC-Python-NOTICE.txt), including "OpenCC-Python", "Copyright 2016", and its attribution to OpenCC. The applicable upstream distribution terms are Apache License 2.0.

The converter program and full dictionaries are maintenance dependencies and are not shipped in the runtime or corpus-source ZIP. This attribution concerns the incorporated dictionary-derived subset. It does not infer a license for arbitrary converter output solely from the converter program's license.

## iztro 2.6.3 adapted tables and algorithms

Upstream is [SylarLong/iztro at commit f24f2d9f21c37a3d48aa06c76d73372e4cc9bc94](https://github.com/SylarLong/iztro/tree/f24f2d9f21c37a3d48aa06c76d73372e4cc9bc94), the commit resolved from annotated tag v2.6.3. Copyright (c) 2023 All Contributors. Preserve its [complete MIT notice](licenses/iztro-MIT.txt).

Runtime `scripts/ziwei_brightness.py` uses the seven-level star-brightness table, including the three cells selected to follow iztro 2.6.3. `scripts/ziwei_minor.py` uses its default miscellaneous-star tables and the zhongzhou 天伤/天使 algorithm. The runtime's Zi Wei star and horoscope modules also implement conventions compared with iztro, as described in `references/02-ziwei.md`. These are Python adaptations of tables and placement logic, with local naming, selectable conventions, and source disclosures. The full iztro program is not bundled. A successful differential comparison alone is not claimed as evidence of code incorporation or as a grant over a historical source.

## Renhuai123/ziwei-doushu adapted tables and algorithms

Upstream is [Renhuai123/ziwei-doushu at commit 495b79ecb3524b20b2edc026067d7d0b0f407319](https://github.com/Renhuai123/ziwei-doushu/tree/495b79ecb3524b20b2edc026067d7d0b0f407319). Copyright (c) 2026 紫微研究. Preserve its [complete MIT notice](licenses/Renhuai-MIT.txt).

Runtime adaptations occur in `scripts/ziwei_palaces.py`, `scripts/ziwei_stars.py`, `scripts/ziwei_minor.py`, `scripts/ziwei_gods.py`, `scripts/ziwei_horoscope.py`, and the school presets used by `scripts/ziwei_calc.py`, documented in `references/02-ziwei.md`. Incorporated material includes the alternative 庚干四化 and 魁钺 tables, single 截空 tables, school choices, and the 将前/岁前十二神 placement logic from `lib/ziwei/shier-shen.ts`. Local Python functions expose these as named options and retain the 大耗 compatibility name where the upstream table uses 岁破. Classical starting-point citations and modern choices remain separately identified.

The upstream program is not bundled. This project does not include the separately licensed 倪海厦 course quotations. Their CC BY-NC-SA terms are not represented as MIT, and the software's school preset does not grant rights to those quotations.

## License capture provenance

[License capture records](licenses/README.md) identify the fixed upstream source or vendored member and SHA-256 for every copied fulltext. Those records describe captured bytes and do not expand the rights granted by any upstream license.
