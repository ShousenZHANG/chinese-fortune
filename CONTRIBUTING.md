# Contributing · 贡献指南

> [English](#english) · [中文](#中文)

---

## English

### Welcome

`chinese-fortune` aims to be the most complete, accurate, and ethically-bounded Chinese metaphysics skill for AI assistants. Contributions are welcome across:

- **Reference depth** — expand classical citations, fix translation errors, add worked examples
- **New methods** — currently `奇门遁甲`, `大六壬`, `太乙神数`, `铁板神数`, `称骨` lack computational scripts
- **Data quality** — `assets/jiemeng.json` (dream symbols) is at ~80 entries; classical 周公解梦 has 1000+. Same for `assets/name_bihua.json` (currently 2,594 chars).
- **Translation** — currently 简体中文 only; we welcome 繁體中文 and English content in `references/`
- **Test coverage** — add cases to `evals/evals.json` and assertions
- **Bug fixes** — see open issues

### Before you start

1. **Read the disclaimer** in [references/20-disclaimer.md](references/20-disclaimer.md). Any contribution that broadens or removes red lines (death prediction, medical diagnosis, etc.) will be rejected.
2. **Cite sources** — for classical content, point to the source text. Don't fabricate 卦辞 or 神煞 起法.
3. **Stay neutral on superstition** — frame readings as cultural / psychological / probabilistic, not deterministic prophecy.
4. **No commercial nudging** — don't recommend purchase of charms, products, or fee-based services.

### Development workflow

```bash
# 1. Fork & clone
git clone https://github.com/<your-fork>/chinese-fortune.git
cd chinese-fortune

# 2. Install dev dependency
pip install lunar_python

# 3. Make changes on a branch
git checkout -b feat/your-change

# 4. Run the release checks
PYTHONDONTWRITEBYTECODE=1 python -X utf8 evals/run_checks.py

# 5. All 4 checks must pass:
#    ok check_skill_metadata
#    ok check_core_scripts
#    ok check_reference_coverage
#    ok check_release_cleanliness

# 6. Commit and push
git add .
git commit -m "feat: add X to references/Y.md"
git push origin feat/your-change

# 7. Open PR with: what changed, why, sources cited, validation output
```

### Style

**Markdown references**
- Simplified Chinese as the primary language (translations welcome alongside)
- Use markdown tables for tabular data
- Quote classical sources verbatim with attribution: e.g., `《滴天髓·通神论》："五行不可逆..."` then a 白话 translation
- Sections in this order: 概述 → 原理 → 排法 → 解读 → 案例 → 误区 → 出处
- No emojis in reference files

**Python scripts**
- Python 3.10+, type hints required
- `from __future__ import annotations`
- Argparse subcommands; `--help` must work without dependencies
- Output: pretty UTF-8 JSON via `utils.json_print()`; warnings to stderr only
- Errors as `{"error": ..., "message": ...}` JSON (exit 1) — never tracebacks
- Each script standalone: `python scripts/<name>.py` runs

**JSON assets**
- 2-space indent
- UTF-8 (no `\u` escapes for CJK)
- For ambiguous entries (e.g., unusual stroke counts), include `"note_uncertain": true`

### PR checklist

- [ ] `evals/run_checks.py` passes
- [ ] Changes are scoped (no drive-by reformatting)
- [ ] Classical sources cited
- [ ] No red lines crossed
- [ ] No emojis added to release files
- [ ] If adding new method: SKILL.md router updated + reference file + (optionally) script
- [ ] If adding new script: graceful degradation when dependencies missing
- [ ] If adding/changing data: validate with `python -c "import json; json.load(open('assets/X.json', encoding='utf-8'))"`

### Code of conduct

- Be respectful of different schools (流派) — don't claim one is universally correct.
- Be sensitive to cultural context — readings about marriage, fertility, gender should not enforce traditional restrictions on modern users.
- Be inclusive — LGBTQ+ users, single-parent families, non-traditional living arrangements are welcome. Don't apply 男命/女命 conventions inflexibly.
- Disagree on PRs via classical texts and reasoning, not authority claims.

---

## 中文

### 欢迎

`chinese-fortune` 的目标是做一份**最完整、最准确、伦理边界清晰**的中国命理 AI skill。欢迎以下贡献：

- **加深参考文档** — 扩充经典出处、修正翻译错误、增加案例
- **新方法脚本** — 当前 `奇门遁甲`、`大六壬`、`太乙神数`、`铁板神数`、`称骨` 暂无脚本
- **数据扩充** — `assets/jiemeng.json` 仅约 80 条 (周公解梦原本 1000+)，`assets/name_bihua.json` 当前 2594 字，可加深
- **翻译** — 当前仅简体中文，欢迎繁體中文、English 翻译
- **测试用例** — 扩充 `evals/evals.json` + 断言
- **Bug 修复** — 见 open issues

### 开始前

1. **先读免责声明** — [references/20-disclaimer.md](references/20-disclaimer.md)。任何放宽或移除红线 (预测死亡、诊断疾病等) 的 PR 会被拒绝。
2. **引用要有出处** — 经典内容必须能指到原文，不要编造卦辞或神煞起法。
3. **不评判迷信问题** — 把读盘表述为文化 / 心理 / 概率视角，不做决定论预言。
4. **不商业推销** — 不推荐购买物品、招财符、付费法事。

### 开发流程

```bash
# 1. Fork & clone
git clone https://github.com/<你的 fork>/chinese-fortune.git
cd chinese-fortune

# 2. 装开发依赖
pip install lunar_python

# 3. 切分支
git checkout -b feat/你的改动

# 4. 跑发布检查
PYTHONDONTWRITEBYTECODE=1 python -X utf8 evals/run_checks.py

# 5. 必须 4/4 过:
#    ok check_skill_metadata
#    ok check_core_scripts
#    ok check_reference_coverage
#    ok check_release_cleanliness

# 6. 提交 + 推
git add .
git commit -m "feat: 给 references/Y.md 加 X"
git push origin feat/你的改动

# 7. 开 PR 注明: 改了什么、为何、引用出处、验收输出
```

### 风格

**Markdown 参考文档**
- 简体中文为主语言 (欢迎并列翻译版)
- 表格化数据用 markdown table
- 经典原文逐字引用 + 出处：如 `《滴天髓·通神论》："五行不可逆..."` 后接白话
- 段落顺序：概述 → 原理 → 排法 → 解读 → 案例 → 误区 → 出处
- 参考文档**不**用 emoji

**Python 脚本**
- Python 3.10+，必须类型注解
- `from __future__ import annotations`
- argparse 子命令；`--help` 必须无依赖也能跑
- 输出：`utils.json_print()` 出 UTF-8 JSON；警告只走 stderr
- 报错出 `{"error": ..., "message": ...}` JSON (exit 1)，绝不抛 traceback
- 每个脚本独立可跑：`python scripts/<名>.py`

**JSON 资产**
- 2 空格缩进
- UTF-8 (中文不用 `\u` 转义)
- 含糊条目 (例如非标准笔画) 加 `"note_uncertain": true`

### PR Checklist

- [ ] `evals/run_checks.py` 通过
- [ ] 改动有范围 (不顺手大改格式)
- [ ] 经典出处可查
- [ ] 没踩红线
- [ ] 没在发布文件加 emoji
- [ ] 加新方法: SKILL.md 路由表 + 参考文档 + (可选) 脚本
- [ ] 加新脚本: 依赖缺失时优雅降级
- [ ] 改/加数据: 用 `python -c "import json; json.load(open('assets/X.json', encoding='utf-8'))"` 验证

### 行为准则

- **尊重流派差异** — 不宣称某派绝对正确，明示"某派如此取法"。
- **文化敏感** — 涉婚姻、生育、性别的解读不应把传统约束强加给现代用户。
- **包容** — LGBTQ+ 用户、单亲家庭、非传统居住安排均欢迎；不死板套男命/女命。
- **争议靠经典与推理决定** — PR 讨论中拒绝"权威诉求" (我师父说 / 某大师说)，请引经典 + 推理。
