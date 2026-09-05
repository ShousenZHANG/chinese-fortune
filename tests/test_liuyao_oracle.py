"""六爻引擎的独立 oracle。

六爻此前是**零校验**的六个引擎之一: 行覆盖 88.8%, 却没有任何断言检查排出来的爻
装了什么 —— 变异实证, 乾宫纳甲 子寅辰 改成 子寅午 全量套件仍全绿。
「覆盖率高而无 oracle」的干净样本。

这里不引入第二个第三方库。京房八宫、世应位、纳甲、六亲、六神 **全部可由生成规则
独立重算**, 用规则重算再与引擎逐卦比对, 比"再装一个库"更强: 它检验的是规则本身,
而不是两个实现是否碰巧同源。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")

DIZHI = "子丑寅卯辰巳午未申酉戌亥"
# 八卦 上→初 三爻编码
TRI = {"乾": "111", "兑": "011", "离": "101", "震": "001",
       "巽": "110", "坎": "010", "艮": "100", "坤": "000"}


def _tri_bottom_up(name: str) -> str:
    return TRI[name][::-1]


def test_najia_branches_follow_the_generating_rule():
    """纳甲地支不是随手抄的表, 而是由「乾坤两卦定阴阳, 隔位取支」生成的:

    阳卦 (乾震坎艮) 内卦自 子 起, 阴卦 (坤巽离兑) 内卦自 未/丑/卯/巳 起,
    地支每爻隔一位 —— 阳顺 (子寅辰), 阴逆 (未巳卯)。外卦续接同一序列再隔六位。

    这条把整张表压成一条规则: 抄错任何一格都会与生成式对不上。
    """
    from liuyao_cast import NAJIA_TABLE

    yang = {"乾", "震", "坎", "艮"}
    for tri, row in NAJIA_TABLE.items():
        lo, up = row["lower_branches"], row["upper_branches"]
        assert len(lo) == 3 and len(up) == 3, tri
        step = 2 if tri in yang else -2
        for seq in (lo, up):
            for a, b in zip(seq, seq[1:], strict=False):
                got = (DIZHI.index(b) - DIZHI.index(a)) % 12
                assert got == step % 12, (
                    f"{tri} {seq}: {a}->{b} 隔 {got} 位, 阳顺阴逆应隔 {step % 12}")
        # 外卦接内卦: 同一序列再推进 6 位 (三爻 x 隔二)
        want_up0 = DIZHI[(DIZHI.index(lo[0]) + 3 * step) % 12]
        assert up[0] == want_up0, (tri, lo, up, want_up0)


def test_shi_ying_positions_follow_the_eight_palace_rule():
    """世爻位由京房八宫「本宫→一世→…→五世→游魂→归魂」决定, 应爻恒隔三位。

    引擎输出 shi_position / ying_position, 从前无人断言二者的关系。
    """
    import json
    import subprocess
    seen = set()
    for seed in range(24):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "liuyao_cast.py"), "coins",
             "--seed", str(seed), "--date", "2026-06-01", "--time", "10:00"],
            capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 0, proc.stderr[-300:]
        c = json.loads(proc.stdout)["main_chart"]
        shi, ying = c["shi_position"], c["ying_position"]
        assert 1 <= shi <= 6 and 1 <= ying <= 6, c
        # 应爻与世爻恒隔三位 (1↔4, 2↔5, 3↔6)
        assert (ying - shi) % 6 == 3, (c["hex_name"], shi, ying)
        # lines 里的标记必须与这两个数字一致, 且各只有一个
        marks_shi = [ln["position"] for ln in c["lines"] if ln["is_shi"]]
        marks_ying = [ln["position"] for ln in c["lines"] if ln["is_ying"]]
        assert marks_shi == [shi] and marks_ying == [ying], c["hex_name"]
        seen.add(c["palace"])
    assert len(seen) >= 4, f"24 次起卦只覆盖 {seen}, 样本不足以检验八宫"


def test_liu_qin_is_derived_from_palace_wuxing_not_guessed():
    """六亲 = 爻支五行 与 宫五行 的生克关系:
    同我兄弟、生我父母、我生子孙、我克妻财、克我官鬼。
    从前引擎输出 liu_qin 却无人验算过。
    """
    import json
    import subprocess

    from utils import WUXING_GEN, WUXING_KE

    for seed in range(12):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "liuyao_cast.py"), "coins",
             "--seed", str(seed), "--date", "2026-06-01", "--time", "10:00"],
            capture_output=True, text=True, encoding="utf-8")
        c = json.loads(proc.stdout)["main_chart"]
        pw = c["palace_wuxing"]
        for ln in c["lines"]:
            lw, got = ln["wuxing"], ln["liu_qin"]
            if lw == pw:
                want = "兄弟"
            elif WUXING_GEN.get(lw) == pw:
                want = "父母"
            elif WUXING_GEN.get(pw) == lw:
                want = "子孙"
            elif WUXING_KE.get(pw) == lw:
                want = "妻财"
            elif WUXING_KE.get(lw) == pw:
                want = "官鬼"
            else:
                raise AssertionError((pw, lw))
            assert got == want, (
                f"{c['hex_name']} 第{ln['position']}爻 {ln['branch']}({lw}) "
                f"宫五行{pw}: 引擎={got} 生克推导={want}")


def test_liu_shen_starts_from_the_day_stem():
    """六神起于日干: 甲乙起青龙、丙丁起朱雀、戊起勾陈、己起腾蛇、庚辛起白虎、
    壬癸起玄武, 自初爻顺布。从前无人断言起点。
    """
    import json
    import subprocess
    order = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]
    start_by_stem = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
                     "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}
    # 必须走遍十干。先前只取 4 天, 日干恰好都不是 甲乙 —— 于是把
    # LIU_SHEN_START 的 甲乙 改成朱雀, 这条测试照样绿。碰运气覆盖不算覆盖。
    from datetime import date, timedelta
    days = [(date(2026, 6, 1) + timedelta(days=i)).isoformat() for i in range(12)]
    covered = set()
    for day in days:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "liuyao_cast.py"), "coins",
             "--seed", "3", "--date", day, "--time", "10:00"],
            capture_output=True, text=True, encoding="utf-8")
        d = json.loads(proc.stdout)
        day_stem = d["cast_time"]["day_stem"]
        got = [ln["liu_shen"] for ln in d["main_chart"]["lines"]]
        s = start_by_stem[day_stem]
        want = [order[(s + i) % 6] for i in range(6)]
        assert got == want, f"{day} 日干{day_stem}: 引擎={got} 规则={want}"
        covered.add(day_stem)
    assert covered == set("甲乙丙丁戊己庚辛壬癸"), (
        f"未走遍十干, 只覆盖 {sorted(covered)} —— 漏掉的那几干可以随便改坏")
