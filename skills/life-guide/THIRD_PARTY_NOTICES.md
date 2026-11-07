# Third-party notices

The skill's own code and documentation use the [MIT license](LICENSE). That grant does not replace the terms for the third-party material below.

## HowToLiveBetter text and adapted code

《高性价比人生指南》，eternity4719，https://github.com/eternity4719/HowToLiveBetter.

The fixed source is [commit 842e11c9d51fac7943e5abb4e332e29b460b5061](https://github.com/eternity4719/HowToLiveBetter/tree/842e11c9d51fac7943e5abb4e332e29b460b5061), snapshot date 2026-10-05. The text in runtime `assets/life_guide.json` is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The [complete CC BY 4.0 text](licenses/CC-BY-4.0.txt) accompanies this notice.

Changes to the text are recorded in the dataset. It was frozen at that commit and converted to JSON. Three entries and the paragraph that retells them in the section 6 introduction were omitted to fit the product scope. The remaining entries, introductions, and long articles retain their wording. Corrections are separate `errata` fields and do not replace the source wording. Local region-review fields and resolved cross references are separate from that text.

The search and ranking algorithms were ported from `index.html`, the reference checks from `tools/check-refs.mjs`, and the decision workflow from `skills/life-decision-guide`. The local adaptations are in `scripts/life_guide.py`, `scripts/life_search.py`, `scripts/life_decision.py`, and `scripts/life_guide_refs.py`. They use Python data structures and the project's CLI and result conventions. Upstream code is MIT, Copyright (c) 2026 eternity4719. Preserve its [complete MIT notice](licenses/HowToLiveBetter-MIT.txt) independently of the text's CC BY terms.

## IANA time zone tables

`assets/tz/zone.tab` and `assets/tz/tzdata.zi` are copied unchanged from `tzdata==2026.3`, which packages the IANA time zone database. They are read as text to tell which country a time zone belongs to. Preserve the upstream [copyright and license notice](licenses/tzdata-NOTICE.txt) and [Apache License 2.0](licenses/tzdata-Apache-2.0.txt) of that distribution. This notice does not assert ownership of the IANA data.
