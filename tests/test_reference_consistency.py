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

**方向**: 引擎是权威, 文档跟随。文档是给模型读的措辞, 引擎是算出来的值; 两者不一致
时用户看到的是引擎的数、听到的是文档的话。
"""
import re
import sys
from pathlib import Path

import pytest

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


def test_ziwei_brightness_reference_states_the_engine_is_authoritative():
    """文档必须写明它是跟随方, 否则下一个人会以为可以随手改文档。"""
    md = _read("references/02-ziwei.md")
    assert "ziwei_stars.py" in md and "BRIGHTNESS" in md
    assert "四级" in md and "七级" in md, "必须说明这是一次有损折叠"


# --------------------------------------------------------------------------- #
# 梅花 月令旺衰 — references/05-meihua.md §5.2 vs scripts/meihua_cast.py
# (逐格断言在 tests/test_engines.py, 这里只锁"文档没被删成不可解析")
# --------------------------------------------------------------------------- #

def test_meihua_season_table_is_still_parseable():
    md = _read("references/05-meihua.md")
    body = md.split("### 5.2")[1].split("### 5.3")[0]
    rows = [ln for ln in body.splitlines()
            if len(ln.split("|")) == 9 and "月令" not in ln
            and not set(ln.split("|")[1].strip()) <= set("-")]
    assert len(rows) == 5, f"§5.2 应有 5 行月令, 解析到 {len(rows)}"


# --------------------------------------------------------------------------- #
# 覆盖面 — 哪些共享表**还没有**门禁
# --------------------------------------------------------------------------- #

KNOWN_UNGATED = {
    "references/01-bazi.md §9.1 调候口诀 vs assets/tiaohou.json":
        "13 格 primary_yongshen 与口诀相反, 其中 8 格在 audit.verified_cells 名单里",
    "references/12-huangli.md §建除 vs huangli_query.py 的 yi/ji":
        "180 天里 57 天引擎宜含表中忌、58 天引擎忌含表中宜; 择日是唯一会让用户做"
        "不可逆现实决策(婚期/搬迁/安葬)的输出",
    "references/19-shensha.md vs assets/shensha.json 的其余条目":
        "词馆/学堂两条已有门禁, 其余 30+ 条没有",
    "六冲表 (scripts 4 份 + references 4 份 = 8 份)":
        "参考层那 4 份同样是 reader-facing, 模型直接照着措辞; scripts 侧已有 4 份副本, 改一处漏一处无人察觉",
}


def test_ungated_shared_tables_are_recorded_not_forgotten():
    """这份清单是欠账簿, 不是装饰。

    R1 的门禁目前只覆盖 亮度、词馆/学堂、梅花月令 三处。其余共享表仍可能静默分叉,
    在补上之前必须显式记录 —— 否则"references 已纳入机检"会被读成"全部覆盖"。
    """
    assert len(KNOWN_UNGATED) >= 4
    for key, why in KNOWN_UNGATED.items():
        assert why and len(why) > 20, f"{key} 缺少具体说明"


@pytest.mark.parametrize("path", [
    "references/02-ziwei.md",
    "references/05-meihua.md",
    "references/01-bazi.md",
    "references/12-huangli.md",
    "references/19-shensha.md",
])
def test_gated_references_exist(path):
    assert (ROOT / path).exists(), f"门禁引用了不存在的文件: {path}"
