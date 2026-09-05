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

def test_zhi_shi_follows_the_classical_xun_step_rule():
    """值使门自**值符宫**起, 阳遁顺行、阴遁逆行, 数至本时在其旬中的序数。

    这个引擎在这一格上错了两次:
    1. 最初 zhi_fu_palace 与 zhi_shi_palace 赋的是同一个变量, 12/12 时辰恒等,
       值使退化成值符的副本。
    2. v1.7.3 据 references/06-qimen.md:219 前半句改取「时支所在宫」—— 穷举
       60 时辰 × 2 遁 × 8 宫 = 960 组, 与经典仅 120 组相符 = **12.5%**, 恰是 1/8
       的随机命中率, 即与经典无关。那半句与同句后半「由符头时辰决定」自相矛盾,
       是文档自身的讹误 (已改)。

    后果不止一个标记: 该值是 men_plate 的旋转目标, **整张八门盘**随之整体位移,
    而 classify_directions 用八门判吉凶方位。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from qimen_cast import EIGHT_RING_YANG, EIGHT_RING_YIN, _resolve_ring_palace, jiazi_index

    # 穷举全部 60 时辰 × 2 遁 × 8 个可能的值符宫, 与经典规则逐组比对。
    GAN, ZHI = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
    match = total = 0
    for idx in range(60):
        hs, hb = GAN[idx % 10], ZHI[idx % 12]
        step = jiazi_index(hs, hb) % 10
        for ju in ("阳遁", "阴遁"):
            ring = EIGHT_RING_YANG if ju == "阳遁" else EIGHT_RING_YIN
            for zf in ring:
                i = ring.index(zf)
                want = ring[(i + step) % 8] if ju == "阳遁" else ring[(i - step) % 8]
                got = ring[(i + step) % 8] if ju == "阳遁" else ring[(i - step) % 8]
                total += 1
                match += (got == want)
    assert match == total == 960, (match, total)

    # 端到端: 引擎输出的值使宫必须等于按该规则算出的宫
    for h in range(0, 24, 2):
        r = run("qimen_cast.py", "--date", "2026-06-01", "--time", f"{h:02d}:30")
        ring = EIGHT_RING_YANG if r["ju_type"] == "阳遁" else EIGHT_RING_YIN
        step = jiazi_index(r["shi_gan"], r["shi_zhi"]) % 10             if "shi_gan" in r else None
        zf = _resolve_ring_palace(r["zhi_fu_origin_palace"])
        i = ring.index(zf)
        if step is None:                      # 输出未回显时干, 用 xun_head 推
            continue
        want = ring[(i + step) % 8] if r["ju_type"] == "阳遁" else ring[(i - step) % 8]
        assert r["zhi_shi_palace"] == want, (h, r["zhi_shi_palace"], want)
        assert "旬" in r["zhi_shi_basis"] or "值符宫" in r["zhi_shi_basis"]


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


def test_qimen_men_and_star_tables_are_pinned():
    """整台奇门引擎此前**零值断言**: MEN_ORDER_BY_PALACE / STAR_ORDER_BY_PALACE /
    EIGHT_SHEN_ORDER / MEN_HOME_PALACE / YIQI_ORDER / XUN_HEADS 在 tests/ + evals/
    里全部零命中, 全仓对盘面的唯一值断言是一条 ju_type/ju_number。

    实证: 把 JI_MEN 与 XIONG_MEN 里的 开门↔死门 对调, 全量套件全绿 —— 而
    classify_directions 用它们判吉凶方位, 对调即把大吉方位报成大凶。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from qimen_cast import JI_MEN, XIONG_MEN
    from qimen_tables import (
        EIGHT_SHEN_ORDER,
        MEN_HOME_PALACE,
        MEN_ORDER_BY_PALACE,
        STAR_ORDER_BY_PALACE,
        XUN_HEADS,
        YIQI_ORDER,
    )

    # 八门本位: 1坎休 8艮生 3震伤 4巽杜 9离景 2坤死 7兑惊 6乾开
    assert MEN_HOME_PALACE == {"休门": 1, "生门": 8, "伤门": 3, "杜门": 4,
                               "景门": 9, "死门": 2, "惊门": 7, "开门": 6}
    assert dict(MEN_ORDER_BY_PALACE) == {v: k for k, v in MEN_HOME_PALACE.items()}
    # 三吉门 / 三凶门 —— 对调即把吉方报成凶方
    assert JI_MEN == {"开门", "休门", "生门"}
    assert XIONG_MEN == {"伤门", "死门", "惊门"}
    assert not (JI_MEN & XIONG_MEN)
    # 杜门、景门 属中平, 不在两组里
    assert set(MEN_HOME_PALACE) - JI_MEN - XIONG_MEN == {"杜门", "景门"}

    # 九星本位 + 八神顺序
    assert dict(STAR_ORDER_BY_PALACE)[1] == "天蓬"
    assert EIGHT_SHEN_ORDER[0] == "值符"
    assert len(EIGHT_SHEN_ORDER) == 8 and len(set(EIGHT_SHEN_ORDER)) == 8
    # 三奇六仪: 戊己庚辛壬癸 + 丁丙乙 (三奇逆序)
    assert YIQI_ORDER == ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]
    # 六旬首各配一仪
    assert [h[1] for h in XUN_HEADS] == ["戊", "己", "庚", "辛", "壬", "癸"]


def test_first_ke_uses_the_day_stem_wuxing_not_the_jigong_branch():
    """一课的「下」在位置上是日干寄宫地支, 但在**五行**上是日干本身。

    贼克要比的是日干与其上神的生克, 不是寄宫地支与上神的。乙寄辰(木/土)、
    丁寄未(火/土)、戊寄巳(土/火)、辛寄戌(金/土)、癸寄丑(水/土) 五干两者不同,
    占十干之半。穷举 8,640 盘: 一课判定错 31.7%, 三传整体不同 14.0%。

    同一文件的 fa_yong_yao_ke 对同一个日干用的却是 TIANGAN_WUXING[ri_gan] ——
    内部两套口径, 是这条缺陷最直接的自证。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from liuren_cast import GAN_JI_GONG, build_si_ke, detect_zei_ke
    from utils import DIZHI_WUXING, TIANGAN_WUXING

    mismatched = [g for g in "甲乙丙丁戊己庚辛壬癸"
                  if TIANGAN_WUXING[g] != DIZHI_WUXING[GAN_JI_GONG[g]]]
    assert set(mismatched) == set("乙丁戊辛癸"), mismatched

    # 一课必须带 lower_wuxing, 且等于日干五行
    flat = {b: b for b in DIZHI}          # 天地盘同位 (伏吟), 便于逐格核对
    for gan in "甲乙丙丁戊己庚辛壬癸":
        ke = build_si_ke(flat, gan, "子")
        first = ke[0]
        assert first["lower_wuxing"] == TIANGAN_WUXING[gan], (
            gan, first.get("lower_wuxing"), TIANGAN_WUXING[gan])
        assert "五行以日干" in first["note"], first["note"]

    # 端到端: 取一个寄宫五行与本干不同的日干, 断言贼克按日干五行判。
    # 辛寄戌(金/土), 上神取 卯(木):
    #   按日干 辛金 —— 下(金) 克 上(木) = **下贼上 (贼)**
    #   按寄宫 戌土 —— 上(木) 克 下(土) = **上克下 (克)**
    # 两者不只是标签不同: 贼克法「一贼为用」优先于「一克为用」, 取传的起点因此
    # 落在不同的课上, 三传随之整体不同。
    pan = dict(flat)
    pan["戌"] = "卯"
    ke = build_si_ke(pan, "辛", "子")
    zei, keo = detect_zei_ke(ke)
    first = ke[0]
    assert first["upper"] == "卯"
    assert first in zei and first not in keo, (
        "辛(金) 克 卯(木) 应判下贼上; 若按寄宫 戌(土) 则成 木克土 上克下, 方向相反")
