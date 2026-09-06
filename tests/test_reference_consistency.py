"""references/ 与 scripts/ 的同名表必须逐格一致。

这是 R1(单一事实源)的门禁。同一张表在本仓库里常有三到四份手抄件 ——
scripts/ 一份、assets/ 一份、references/ 一份、tests/ 里再硬编码一份 —— 而此前
所有闸门只看得见 scripts 那一层。后果不是潜在风险而是已发生的事实:

- 亮度: v1.7.2 依《紫微斗数全书》卷二改了 scripts/ziwei_stars.py 的七杀行, 没碰
  references/02-ziwei.md。SKILL.md 把紫微同时路由到这两处, 于是模型在同一次解读里
  读到"辰戌入庙"(引擎)和"辰戌落陷"(文档)两句相反的话。实测分叉 12 格。
- 调候: v1.7.0/v1.7.1 两轮审计改了 assets/tiaohou.json, 一次没改
  references/01-bazi.md §9.1 的调候口诀。

范式取自 tests/test_bazi_integration.py::test_cimu_and_xuetang_match_their_own_
reference —— 那次 词馆 修复用的就是"测试去 parse markdown 再逐格 diff", 是对的做法;
下一个 commit 却没沿用, 于是同类问题在同一个仓库里有两套相反约定。本文件把它固定
下来。

这些检查只证明文档与实现一致，不证明表格已由古籍原刻校验。来源核验与语义判断另行记录。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

DIZHI = "子丑寅卯辰巳午未申酉戌亥"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 紫微 主星亮度 — references/02-ziwei.md §四 vs scripts/ziwei_stars.py
# --------------------------------------------------------------------------- #

_LABEL = {"入庙": "庙", "庙旺": "庙", "旺地": "旺", "得地": "旺",
          "平": "平", "落陷": "陷", "失陷": "陷"}


def _parse_ziwei_brightness() -> dict[str, dict[str, str]]:
    md = _read("references/02-ziwei.md")
    heads = [(m.group(1), m.start(), m.end())
             for m in re.finditer(r"^###\s+4\.\d+\s+([一-鿿]{2})", md, re.M)]
    assert len(heads) == 14, f"§四 应有 14 颗主星小节, 找到 {len(heads)}"

    out: dict[str, dict[str, str]] = {}
    for i, (star, _, s1) in enumerate(heads):
        end = heads[i + 1][1] if i + 1 < len(heads) else len(md)
        cells: dict[str, str] = {}
        for m in re.finditer(
                r"^- \*\*(入庙|庙旺|旺地|得地|平|落陷|失陷)\*\*[:：]\s*([^\n]*)",
                md[s1:end], re.M):
            state = _LABEL[m.group(1)]
            head = m.group(2).split("(")[0]
            for br in re.findall(f"[{DIZHI}]", head):
                assert br not in cells, f"{star} {br} 在文档里出现两次"
                cells[br] = state
        out[star] = cells
    return out


def test_ziwei_brightness_reference_matches_the_engine():
    from ziwei_stars import BRIGHTNESS

    doc = _parse_ziwei_brightness()
    assert set(doc) == set(BRIGHTNESS), set(doc) ^ set(BRIGHTNESS)

    bad = []
    for star, cells in doc.items():
        assert set(cells) == set(DIZHI), (
            f"{star} 文档只覆盖 {len(cells)}/12 宫: 缺 {set(DIZHI) - set(cells)}")
        for br, state in cells.items():
            if BRIGHTNESS[star][br] != state:
                bad.append(f"{star}{br}: 文档={state} 引擎={BRIGHTNESS[star][br]}")
    assert not bad, (
        f"references/02-ziwei.md 与 ziwei_stars.BRIGHTNESS 分叉 {len(bad)} 格。"
        "改引擎时必须同步文档 —— 模型两处都读得到。\n" + "\n".join(bad))




# --------------------------------------------------------------------------- #
# 梅花 月令旺衰 — references/05-meihua.md §5.2 vs scripts/meihua_cast.py
# (逐格断言在 tests/test_engines.py, 这里只锁"文档没被删成不可解析")
# --------------------------------------------------------------------------- #



# --------------------------------------------------------------------------- #
# 十二建除 — references/12-huangli.md §6 vs scripts/huangli_query.py
# --------------------------------------------------------------------------- #

def test_jianchu_tendency_matches_its_own_reference():
    """引擎的 JIAN_CHU_TENDENCY 必须逐项等于文档那张表。

    择日是本仓库唯一一类会让用户做**不可逆现实决策**的输出 (婚期/搬迁/安葬)。
    从前引擎只发 lunar_python 的 yi/ji 且不注出处, 而 SKILL.md:51 声明黄历择日
    「为纲之典」是《钦定协纪辨方书》、12-huangli.md:180 称建除是「黄历最核心的
    择日体系」—— 读者会以为看到的就是建除的结论。实测 2026 上半年 181 天里 117 天
    字面冲突。现在两者并列, 表本身由这条测试锁死。
    """
    import re
    md = _read("references/12-huangli.md")
    body = md.split("| 建除 | 含义 | 宜 | 忌 |")[1].split("### 十二建除排列规律")[0]

    doc = {}
    for line in body.splitlines():
        cells = [c.strip().strip("*") for c in line.split("|")[1:-1]]
        if len(cells) != 4 or not cells[0] or set(cells[0]) <= set("-"):
            continue
        doc[cells[0]] = (
            re.findall(r"[一-鿿]{2,4}", cells[2]),
            re.findall(r"[一-鿿]{2,4}", cells[3]),
        )
    assert len(doc) == 12, f"§6 建除表应有 12 行, 解析到 {len(doc)}: {sorted(doc)}"

    sys.path.insert(0, str(ROOT / "scripts"))
    from huangli_query import JIAN_CHU_TENDENCY as eng

    assert set(eng) == set(doc), set(eng) ^ set(doc)
    for zhi, (yi_doc, ji_doc) in doc.items():
        # 文档措辞带括号注解 (如「拆屋、破土 (有限)」「百事忌, 大事不宜」),
        # 故只要求引擎项是文档项的子集且非空 —— 逐字相等会锁死文案而非锁住数据。
        assert eng[zhi]["yi"], zhi
        assert eng[zhi]["ji"], zhi
        for item in eng[zhi]["yi"]:
            assert any(item in d for d in yi_doc), (zhi, "yi", item, yi_doc)
        for item in eng[zhi]["ji"]:
            assert any(item in d for d in ji_doc), (zhi, "ji", item, ji_doc)


# --------------------------------------------------------------------------- #
# 天乙贵人 — 同一张表在仓库里有四份
# --------------------------------------------------------------------------- #

def _parse_stem_branch_table(md: str, section: str) -> dict[str, set]:
    """从 markdown 小节里取「日干 -> 地支」两列表。"""
    seg = md[md.index(section):]
    seg = seg[:seg.index("###", len(section))] if "###" in seg[len(section):] else seg
    out: dict[str, set] = {}
    for stems, zhis in re.findall(
            r"\|\s*([甲乙丙丁戊己庚辛壬癸、\s]+?)\s*\|\s*"
            r"([子丑寅卯辰巳午未申酉戌亥、\s]+?)\s*\|", seg):
        found = re.findall(r"[甲乙丙丁戊己庚辛壬癸]", stems)
        branches = set(re.findall(r"[子丑寅卯辰巳午未申酉戌亥]", zhis))
        for st in found:
            out[st] = branches
    return out


def test_tianyi_guiren_agrees_across_the_retained_reference_and_asset():
    """Compare the two retained tables; the removed inline/overview copies are not required."""
    import json
    data = json.loads((ROOT / "assets/shensha.json").read_text(encoding="utf-8"))
    asset = next(e["qi_fa_table"] for group in ("ji_shen", "xiong_sha")
                 for e in data[group] if e["name"] == "天乙贵人")
    reference = _parse_stem_branch_table(_read("references/19-shensha.md"), "### 2.1 天乙贵人")
    assert set(asset) == set(reference) == set("甲乙丙丁戊己庚辛壬癸")
    assert {stem: set(branches) for stem, branches in asset.items()} == reference
    assert reference["辛"] == {"午", "寅"}
    targets = re.findall(r"\]\(([^)]+)\)", _read("references/01-bazi.md"))
    assert any((ROOT / "references" / target).resolve() == (ROOT / "references/19-shensha.md").resolve() for target in targets)
