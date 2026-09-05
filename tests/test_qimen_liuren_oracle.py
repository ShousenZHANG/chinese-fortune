"""奇门 / 大六壬 的独立 oracle。

这两个引擎此前**零校验**, 且各有一处确定性缺陷 —— 都是「输出恒定/退化」型, 单看
一次起局看不出来, 扫一遍网格立刻现形:

- 奇门: zhi_fu_palace 与 zhi_shi_palace 赋的是同一个变量, 12/12 个时辰恒等,
  值使退化成值符的副本, 而它本该是八门盘独立的枢。
- 大六壬: 伏吟时 天地盘各居本位 (tian_pan[x]==x), 于是「末=中传上神」恒等于中传;
  反吟时 tian_pan[x]==冲(x), 于是「末=中传上神」恒等于初传。两处都是数学必然,
  不是偶发。另有八专课 (干支同宫) 根本没实现, 落进反吟后三传得 寅/寅/寅。

这里同样不引入第二个第三方库 —— 用规则本身验算。
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


def run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# 奇门 — 值符随时干, 值使随时支
# --------------------------------------------------------------------------- #

def test_zhi_fu_and_zhi_shi_are_not_the_same_thing():
    """两者从前赋的是同一个变量, 于是恒等。

    references/06-qimen.md:215 「以时干所遁之六仪为枢 … 飞至时干所在宫」——
    值符随时干; :219 「以时支所在宫为『值使门』起点」—— 值使随时支。
    同文 :358 注明「值使门起法: 以日干起还是时干起, 各派不一」, 本实现依本仓库
    自己的参考文档取时支, 并在输出的 zhi_shi_basis 里注明。
    """
    from qimen_tables import PALACE_INFO  # noqa: F401  (确认表可导入)
    sys.path.insert(0, str(ROOT / "scripts"))
    from qimen_cast import DIZHI_TO_PALACE

    same = 0
    for h in range(0, 24, 2):
        r = run("qimen_cast.py", "--date", "2026-06-01", "--time", f"{h:02d}:30")
        assert r["zhi_shi_palace"] == DIZHI_TO_PALACE[r["shi_zhi"]], (
            f"{h}时 时支{r['shi_zhi']}: 值使宫={r['zhi_shi_palace']}, "
            f"时支宫应为 {DIZHI_TO_PALACE[r['shi_zhi']]}")
        assert "时支" in r["zhi_shi_basis"]
        same += r["zhi_fu_palace"] == r["zhi_shi_palace"]
    assert same <= 3, f"12 个时辰里 {same} 次值符值使同宫, 疑似又退化成同一变量"


def test_zhi_shi_men_is_constant_within_a_xun():
    """值使门 = 旬首宫的本门, 故一旬之内恒定, 换旬才变 —— 这条同时验证它确实由
    旬首决定, 而不是随手取的。
    """
    seen: dict[str, set] = {}
    for h in range(0, 24, 2):
        r = run("qimen_cast.py", "--date", "2026-06-01", "--time", f"{h:02d}:30")
        seen.setdefault(r["xun_head"], set()).add(r["zhi_shi_men"])
    assert seen, "没有取到任何旬首"
    for head, men in seen.items():
        assert len(men) == 1, f"旬首{head} 之内值使门有 {men}, 应恒定"
    assert len(seen) >= 2, f"一天内只覆盖 {list(seen)} 一个旬, 检验不到换旬"


# --------------------------------------------------------------------------- #
# 大六壬 — 三传不得退化
# --------------------------------------------------------------------------- #

def _grid(days: int, step: int):
    d0 = date(2026, 1, 1)
    return [(d0 + timedelta(days=i * step), h)
            for i in range(days) for h in (2, 8, 14, 20)]


@pytest.mark.parametrize("d,h", _grid(12, 13),
                         ids=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
def test_san_chuan_never_collapses_to_one_branch(d, h):
    """三传全同是任何一门取法都产生不了的结果。

    从前 2026-04-16 08:00 (庚申日 — 庚寄申, 日支申, 即八专课) 得 寅/寅/寅。
    """
    r = run("liuren_cast.py", "--date", d.isoformat(), "--time", f"{h:02d}:00",
            "--question", "x")
    s = r["san_chuan"]
    tri = [s["chu_chuan"], s["zhong_chuan"], s["mo_chuan"]]
    assert len(set(tri)) > 1, f"{d} {h}时 三传全同: {tri} (取法 {s['method']})"
    assert all(x in DIZHI for x in tri), tri


def test_fu_yin_uses_xing_not_the_upper_god():
    """伏吟 (月将==占时): 天地盘各居本位, tian_pan[x]==x, 所以「末=中传上神」
    **恒等于中传**。经典伏吟课以「刑」取传正是为避开这种原地打转。
    """
    hits = 0
    for i in range(0, 200, 3):
        d = date(2026, 1, 1) + timedelta(days=i)
        for h in (2, 8, 14, 20):
            r = run("liuren_cast.py", "--date", d.isoformat(),
                    "--time", f"{h:02d}:00", "--question", "x")
            if "伏吟" not in r["san_chuan"]["method"]:
                continue
            hits += 1
            s = r["san_chuan"]
            sys.path.insert(0, str(ROOT / "scripts"))
            from liuren_cast import _xing_or_chong
            # 直接验算刑链, 而不是只查「中末不相等」—— 后者对部分变异免疫。
            assert s["zhong_chuan"] == _xing_or_chong(s["chu_chuan"]), (d, h, s)
            assert s["mo_chuan"] == _xing_or_chong(s["zhong_chuan"]), (d, h, s)
            assert s["zhong_chuan"] != s["mo_chuan"], (d, h, s)
            assert "刑" in s["method"], s["method"]
            if hits >= 3:
                return
    assert hits >= 1, "网格里没排到伏吟课, 无法检验"


def test_fan_yin_uses_yima_not_the_upper_god():
    """反吟 (月将冲占时): tian_pan[x]==冲(x), 所以「末=中传上神」**恒等于初传**。
    无亲反吟课取驿马为初传, 正是经典为此准备的出路。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from liuren_cast import YI_MA
    from utils import chong_branch

    # 四孟 (寅申巳亥) 的驿马**恰好等于其冲**, 所以在这些日子上「取驿马」与
    # 「取支上神(即冲)」结果相同 —— 拿它们检验等于没检验。必须排到一个
    # 驿马 != 冲 的日支才算数。这是本会话第四次「碰运气覆盖不算覆盖」。
    discriminating = {b for b in YI_MA if YI_MA[b] != chong_branch(b)}
    assert len(discriminating) == 8, sorted(discriminating)

    hits, discriminated = 0, 0
    collisions: list = []
    # 步长必须与 12 互质, 否则日支只会取到 12 个里的少数几个 —— 步长 3 时
    # 日支只覆盖 4 种, 实测 40 个反吟课日支全是四孟, 恰好是不可鉴别的那一组。
    for i in range(0, 400, 5):
        d = date(2026, 1, 1) + timedelta(days=i)
        for h in (2, 8, 14, 20):
            r = run("liuren_cast.py", "--date", d.isoformat(),
                    "--time", f"{h:02d}:00", "--question", "x")
            if "反吟" not in r["san_chuan"]["method"]:
                continue
            hits += 1
            s = r["san_chuan"]
            # 初传必须真的是日支的驿马, 而不是碰巧不等于末传。
            assert s["chu_chuan"] == YI_MA[r["ri_zhi"]], (
                d, h, r["ri_zhi"], s["chu_chuan"], YI_MA[r["ri_zhi"]])
            assert "驿马" in s["method"], s["method"]
            # 初==末 在这里是**偶合**而非恒等: 只有当 冲(干寄宫) 恰好等于
            # 驿马(日支) 时才发生, 实测 24 个反吟课里 5 个 (21%)。旧实现该比例
            # 是 100% —— mo = 冲(冲(chu)) == chu 是数学恒等。这条不作断言,
            # 由下面的整体比率断言把关。
            if s["chu_chuan"] == s["mo_chuan"]:
                collisions.append((d, h))
            if r["ri_zhi"] in discriminating:
                discriminated += 1
            if discriminated >= 2 and hits >= 12:
                break
        else:
            continue
        break
    assert hits >= 8, f"只排到 {hits} 个反吟课, 样本不足以看比率"
    assert len(collisions) / hits < 0.5, (
        f"{hits} 个反吟课里 {len(collisions)} 个 初==末 —— 旧实现是 100% 的"
        f"数学恒等, 超过一半说明退化又回来了: {collisions[:5]}")
    assert discriminated >= 1, (
        f"排到 {hits} 个反吟课, 但日支全是四孟 (驿马==冲), "
        "检验不到「取驿马」与「取支上神」的差别")


def test_san_chuan_method_is_reported():
    """取法从前算出来却没进输出 —— 而「这三传是哪一门排出来的」正是六壬解读的核心
    (贼克/比用/遥克/八专/伏吟/反吟 各有断法)。

    同时要求兜底路径不能成为常态: 它是「需人工排盘」的自认简化。
    """
    import collections
    methods = collections.Counter()
    for i in range(0, 120, 5):
        d = date(2026, 1, 1) + timedelta(days=i)
        for h in (2, 14):
            m = run("liuren_cast.py", "--date", d.isoformat(),
                    "--time", f"{h:02d}:00", "--question", "x")["san_chuan"]["method"]
            assert m and m != "?", (d, h)
            methods[m.split(" (")[0]] += 1
    total = sum(methods.values())
    fallback = sum(v for k, v in methods.items() if "昴星" in k)
    assert len(methods) >= 5, f"只用到 {len(methods)} 门取法: {dict(methods)}"
    assert fallback / total < 0.10, (
        f"兜底路径占 {fallback/total:.0%}, 它是自认的简化, 不该成为常态: "
        f"{dict(methods)}")
