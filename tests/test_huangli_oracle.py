"""黄历引擎的独立 oracle。

黄历此前是**零校验**的六个引擎之一: yi/ji/值神/二十八宿 全部原样透传
lunar_python, 没有任何断言检查它们对不对。而择日是本仓库唯一一类会让用户做
不可逆现实决策 (婚期、搬迁、安葬) 的输出。

这里不引入第二个第三方库 —— 值神与二十八宿都是**可机械推导**的, 用生成规则重算
再与引擎逐日比对, 是比"再装一个库"更强的 oracle: 它检验的是规则本身, 不是两个
实现是否碰巧同源。
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")

DIZHI = "子丑寅卯辰巳午未申酉戌亥"
JIAN_CHU = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]


def run_day(d: date) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "huangli_query.py"),
         "--date", d.isoformat()],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def derive_zhi_shen(d: date) -> str:
    """按 references/12-huangli.md §6 的排列规律独立推导值神。

    「每月以节令之后第一天为『建』, 其后依次循环」——
    等价于: 值神 = JIAN_CHU[(日支序 - 月支序) mod 12]。
    寅月寅日为建、卯月卯日为建, 即日支与月建同支之日为「建」。
    """
    from lunar_python import Solar
    lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
    day_branch = lunar.getDayInGanZhi()[1]
    month_branch = lunar.getMonthInGanZhiExact()[1]      # 按节气定月
    return JIAN_CHU[(DIZHI.index(day_branch) - DIZHI.index(month_branch)) % 12]


def _grid(start: date, days: int, step: int = 1):
    return [start + timedelta(days=i * step) for i in range(days)]


@pytest.mark.parametrize("d", _grid(date(2026, 1, 1), 60, 6),
                         ids=lambda d: d.isoformat())
def test_zhi_shen_matches_the_documented_rule(d):
    """引擎透传的 getZhiXing 必须等于文档规则推出的值神。"""
    got = run_day(d)["zhi_shen_12jianchu"]
    want = derive_zhi_shen(d)
    assert got == want, f"{d}: 引擎={got} 规则推导={want}"


def test_zhi_shen_cycles_without_gap_across_a_month():
    """值神必须逐日推进一位, 只在交节处重复一日 (节令换月时同支两日皆为建之类)。

    这条抓的是「整段错位」——单日比对抓不到的那种。
    """
    days = _grid(date(2026, 3, 1), 45)
    seq = [run_day(d)["zhi_shen_12jianchu"] for d in days]
    steps = [(JIAN_CHU.index(b) - JIAN_CHU.index(a)) % 12
             for a, b in zip(seq, seq[1:], strict=False)]
    assert set(steps) <= {0, 1}, f"值神跳位: {sorted(set(steps))}\n{list(zip(days, seq, strict=True))}"
    assert steps.count(0) <= 2, f"45 天内重复 {steps.count(0)} 次, 交节至多 2 次"
    assert set(seq) == set(JIAN_CHU), f"45 天未走满十二值神: {sorted(set(seq))}"


def test_huangdao_heidao_split_matches_the_reference():
    """黄道/黑道 六六分, 且十二值神不重不漏。"""
    md = (ROOT / "references" / "12-huangli.md").read_text(encoding="utf-8")
    import re
    rows = {}
    for category in ('黄道类', '黑道类'):
        match = re.search(rf'^\|\s*{category}\s*\|([^|]+)\|', md, re.MULTILINE)
        assert match, f'缺少 {category} 十二值神分类'
        names = re.sub(r'（[^）]*）', '', match.group(1)).strip().split('、')
        assert len(names) == len(set(names)) == 6, names
        rows[category] = set(names)
    huang, hei = rows['黄道类'], rows['黑道类']
    assert huang == {'青龙', '明堂', '金匮', '天德', '玉堂', '司命'}
    assert hei == {'天刑', '朱雀', '白虎', '天牢', '玄武', '勾陈'}
    assert len(huang | hei) == 12
    assert not (huang & hei)


@pytest.mark.parametrize("d", _grid(date(2026, 1, 1), 30, 11),
                         ids=lambda d: d.isoformat())
def test_jianchu_conflicts_are_surfaced_not_hidden(d):
    """引擎必须并列 通书结论 与 建除倾向, 并显式列出二者字面冲突之处。

    2026 上半年 181 天里 117 天存在这种冲突 (58 天引擎宜含表忌、59 天反之)。
    从前只发 yi/ji 且不注出处, 而 SKILL.md:51 声明择日「为纲之典」是《协纪辨方书》,
    读者会以为看到的就是建除的结论。
    """
    r = run_day(d)
    assert "通书" in r["yi_ji_source"] and "lunar_python" in r["yi_ji_source"]
    zs = r["zhi_shen_12jianchu"]
    assert r["jian_chu_tendency"], zs
    yi, ji = set(r["yi"] or []), set(r["ji"] or [])
    tend = r["jian_chu_tendency"]
    真冲突 = sorted(yi & set(tend["ji"])), sorted(ji & set(tend["yi"]))
    if any(真冲突):
        c = r["jian_chu_conflicts"]
        assert c, f"{d} 有冲突却没有列出: {真冲突}"
        assert c.get("engine_yi_but_jianchu_ji", []) == 真冲突[0]
        assert c.get("engine_ji_but_jianchu_yi", []) == 真冲突[1]
        assert "以 yi/ji (通书结论) 为准" in "".join(c["note"])
    else:
        assert not r["jian_chu_conflicts"], (d, r["jian_chu_conflicts"])
