"""六爻引擎的独立 oracle。

固定八宫与世应预期不从生产表导出；其余检查分别验证纳甲序列、六亲与六神。
这些测试能发现指定计算错误，不验证规则的历史真实性或现实预测效果。
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


# Independent fixtures: 卜筮正宗卷一「六十四卦名」「安世应诀」.
# https://www.shidianguji.com/book/AMNL0060/chapter/1ma05akk4w74j
# Network transcription checked 2026-09-06; not a facsimile-collation claim.
# No production palace, role, or shi/ying table is imported to derive expectations.
PALACE_SEQUENCE = {
    "乾": (1, 44, 33, 12, 20, 23, 35, 14),
    "坎": (29, 60, 3, 63, 49, 55, 36, 7),
    "艮": (52, 22, 26, 41, 38, 10, 61, 53),
    "震": (51, 16, 40, 32, 46, 48, 28, 17),
    "巽": (57, 9, 37, 42, 25, 21, 27, 18),
    "离": (30, 56, 50, 64, 4, 59, 6, 13),
    "坤": (2, 24, 19, 11, 34, 43, 5, 8),
    "兑": (58, 47, 45, 31, 39, 15, 62, 54),
}
ROLE_SEQUENCE = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
SHI_YING_SEQUENCE = ((6, 3), (1, 4), (2, 5), (3, 6), (4, 1), (5, 2), (4, 1), (3, 6))
# Change first through fifth lines in order; 游魂 restores line four;
# 归魂 restores the entire lower trigram. Inputs are generated independently.
CHANGE_MASKS = (0, 1, 3, 7, 15, 31, 23, 16)
PALACE_CASES = [(palace, index, number) for palace, row in PALACE_SEQUENCE.items()
                for index, number in enumerate(row)]


def _oracle_chart(palace, index):
    from liuyao_cast import dress_chart
    base = [int(bit) for bit in _tri_bottom_up(palace)] * 2
    mask = CHANGE_MASKS[index]
    lines = [7 if bit ^ ((mask >> position) & 1) else 8 for position, bit in enumerate(base)]
    return dress_chart(lines, "甲", "子", "午")


def _assert_oracle_chart(chart, palace, index, number):
    assert chart["hex_number"] == number
    assert chart["palace"] == palace + "宫"
    assert chart["palace_role"] == ROLE_SEQUENCE[index]
    shi, ying = SHI_YING_SEQUENCE[index]
    assert (chart["shi_position"], chart["ying_position"]) == (shi, ying)
    assert [line["position"] for line in chart["lines"] if line["is_shi"]] == [shi]
    assert [line["position"] for line in chart["lines"] if line["is_ying"]] == [ying]


@pytest.mark.parametrize("palace,index,number", PALACE_CASES)
def test_full_eight_palace_sequence_and_exact_shi_ying(palace, index, number):
    _assert_oracle_chart(_oracle_chart(palace, index), palace, index, number)


def test_shifted_shi_and_ying_mutant_is_rejected_without_touching_files(monkeypatch):
    import liuyao_cast
    actual = liuyao_cast.shi_yao_position
    monkeypatch.setattr(liuyao_cast, "shi_yao_position", lambda role: actual(role) % 6 + 1)
    for palace, index, number in PALACE_CASES:
        chart = _oracle_chart(palace, index)
        # This mutant still satisfies the old test's relative-distance/marker checks.
        assert (chart["ying_position"] - chart["shi_position"]) % 6 == 3
        assert [line["position"] for line in chart["lines"] if line["is_shi"]] == [chart["shi_position"]]
        with pytest.raises(AssertionError):
            _assert_oracle_chart(chart, palace, index, number)


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


@pytest.mark.parametrize('raw,main_name,changed_name,main_palace,changed_palace,relatives', [
    ([7, 8, 6, 8, 8, 7], '山雷颐', '山火贲', '巽宫', '艮宫',
     ['兄弟', '妻财', '父母', '妻财', '父母', '兄弟']),
    ([9, 7, 7, 7, 7, 6], '泽天夬', '天风姤', '坤宫', '乾宫',
     ['兄弟', '妻财', '子孙', '父母', '子孙', '兄弟']),
])
def test_changed_relatives_keep_the_original_palace(
        monkeypatch, capsys, raw, main_name, changed_name, main_palace, changed_palace, relatives):
    """增刪卜易/7 oldid=2100290: 變出之爻安六親者仍照正卦而推。

    Fixed examples cross palace elements. Expectations do not use production
    六亲 tables: 颐属木, 亥水生木为父母; 夬属土, 丑戌土为兄弟.
    """
    import json

    import liuyao_cast

    monkeypatch.setattr(liuyao_cast, 'cast_coins', lambda rng: raw)
    assert liuyao_cast.main(['coins', '--seed', '4', '--date', '2026-06-01',
                             '--time', '12:00', '--target-timezone', 'Asia/Shanghai']) == 0
    result = json.loads(capsys.readouterr().out)
    main, changed = result['main_chart'], result['changed_chart']
    assert (main['hex_name'], changed['hex_name']) == (main_name, changed_name)
    assert (main['palace'], changed['palace']) == (main_palace, changed_palace)
    assert main['palace_wuxing'] != changed['palace_wuxing']
    assert changed['liu_qin_basis'] == {
        'palace': main_palace, 'wuxing': main['palace_wuxing'], 'scope': 'main_hexagram_palace',
    }
    assert [line['liu_qin'] for line in changed['lines']] == relatives

    # The auxiliary nuclear chart still belongs to its own palace; it is not
    # a second set of changed lines and must not inherit this override.
    nuclear = result['nuclear_chart']
    assert nuclear['liu_qin_basis'] == {
        'palace': nuclear['palace'], 'wuxing': nuclear['palace_wuxing'],
        'scope': 'own_hexagram_palace',
    }


def test_standalone_bi_keeps_its_own_palace_relatives():
    """贲 as an independent main hexagram is 艮土, so its third 亥水 is 妻财."""
    from liuyao_cast import dress_chart

    chart = dress_chart([7, 8, 7, 8, 8, 7], '甲', '子', '午')
    assert chart['hex_name'] == '山火贲'
    assert chart['liu_qin_basis'] == {
        'palace': '艮宫', 'wuxing': '土', 'scope': 'own_hexagram_palace',
    }
    assert chart['lines'][2]['branch'] == '亥'
    assert chart['lines'][2]['liu_qin'] == '妻财'
