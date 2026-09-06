"""Structure + invariant tests for the non-bazi engines.

Closes the biggest coverage gap: before this, only bazi/name/utils were
tested. Each engine here is exercised via subprocess with deterministic args
(seeds / fixed dates) and asserted to emit valid JSON with its contract keys.

These are CONTRACT tests (shape + determinism + a few domain invariants), not
interpretation tests — interpretation correctness needs a validated golden
corpus (see README / market-research notes), which is out of scope here.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

needs_lunar = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")


def run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"{script} emitted non-JSON (rc={proc.returncode})\n"
            f"stderr={proc.stderr[:400]}\nstdout={proc.stdout[:400]}"
        ) from e


def has(d, *keys):
    for k in keys:
        assert k in d, f"missing key {k!r}; got {list(d)[:12]}"


# --------------------------------------------------------------------------- #
# 周易 — coins cast, seeded => deterministic
# --------------------------------------------------------------------------- #

def test_yijing_structure_and_determinism():
    a = run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    b = run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    has(a, "main_hex", "changed_hex", "nuclear_hex", "active_lines")
    assert a["main_hex"]["number"] == b["main_hex"]["number"]  # seed stable
    assert 1 <= a["main_hex"]["number"] <= 64
    assert len(a["raw_lines"]) == 6


# --------------------------------------------------------------------------- #
# 梅花易数 — numbers cast (fully deterministic)
# --------------------------------------------------------------------------- #

def test_meihua_structure():
    d = run("meihua_cast.py", "numbers", "--upper", "3", "--lower", "5", "--question", "x")
    has(d, "main_hex", "changed_hex", "nuclear_hex", "ti_yong")
    assert 1 <= d["main_hex"]["number"] <= 64
    # body/use relation must be one of the 5 五行 relations (not just truthy).
    rel = d["ti_yong"]["relation"]
    assert any(rel.startswith(r) for r in
               ("体生用", "用生体", "体克用", "用克体", "比和")), rel


# --------------------------------------------------------------------------- #
# 六爻 — coins, seeded
# --------------------------------------------------------------------------- #

@needs_lunar
def test_liuyao_structure_and_determinism():
    a = run("liuyao_cast.py", "coins", "--seed", "7", "--date", "2026-06-01", "--time", "10:00")
    b = run("liuyao_cast.py", "coins", "--seed", "7", "--date", "2026-06-01", "--time", "10:00")
    has(a, "main_chart", "changed_chart", "nuclear_chart", "active_lines")
    assert a["raw_lines"] == b["raw_lines"]
    assert len(a["raw_lines"]) == 6


# --------------------------------------------------------------------------- #
# 小六壬 — fully deterministic lunar input
# --------------------------------------------------------------------------- #

def test_xiaoliuren_structure():
    d = run("xiaoliuren_cast.py", "lunar", "--month", "3", "--day", "15", "--hour-branch", "午")
    has(d, "result")
    assert d["result"]["palace"] in {"大安", "留连", "速喜", "赤口", "小吉", "空亡"}
    assert d["result"]["tone"] in {"吉", "凶", "中"}


# --------------------------------------------------------------------------- #
# 塔罗 — REGRESSION: the curated 78-card asset must actually load (the dict-vs-
# list check used to discard it, silently degrading to placeholder text).
# --------------------------------------------------------------------------- #

def test_tarot_loads_real_asset_not_placeholder():
    d = run("tarot_draw.py", "three", "--seed", "42", "--question", "x")
    assert len(d["cards"]) == 3
    for c in d["cards"]:
        assert c["card_name_zh"]
        assert c["meaning_brief"]
        # The degraded fallback emits "...第N阶: 见详细解读"; real asset never does.
        assert "见详细解读" not in c["meaning_brief"]

def test_tarot_seed_reproducible():
    a = run("tarot_draw.py", "celtic", "--seed", "7", "--question", "x")
    b = run("tarot_draw.py", "celtic", "--seed", "7", "--question", "x")
    assert [c["card_name_zh"] for c in a["cards"]] == [c["card_name_zh"] for c in b["cards"]]


# --------------------------------------------------------------------------- #
# 生肖合婚 — deterministic; 虎申 must be 相冲 (score low)
# --------------------------------------------------------------------------- #

def test_zodiac_compat_chong():
    d = run("zodiac_compat.py", "compat", "--a", "虎", "--b", "猴")
    has(d, "score", "verdict", "summary")
    assert "冲" in d["summary"]            # 寅申相冲
    assert d["score"] <= 3                  # 六冲 => low compatibility

def test_zodiac_compat_sanhe_high():
    # 寅午戌三合 — 虎与马 should score high.
    d = run("zodiac_compat.py", "compat", "--a", "虎", "--b", "马")
    assert d["score"] >= 6

def test_zodiac_same_sign_not_sanhe():
    # 同生肖(鼠-鼠)是比和/自刑, 不能误判为三合 (子∈申子辰).
    d = run("zodiac_compat.py", "compat", "--a", "鼠", "--b", "鼠")
    assert "三合" not in d["relations"]


# --------------------------------------------------------------------------- #
# 奇门遁甲 — deterministic by date/time
# --------------------------------------------------------------------------- #

@needs_lunar
def test_qimen_structure():
    d = run("qimen_cast.py", "--date", "2026-06-01", "--time", "14:30")
    assert d["ok"] is True
    has(d, "ju_type", "ju_number", "ganzhi")
    assert d["ju_type"] in {"阳遁", "阴遁"}
    assert 1 <= d["ju_number"] <= 9
    # Value golden — 芒种前 阳遁, this date/time resolves to 阳遁 8局.
    assert (d["ju_type"], d["ju_number"]) == ("阳遁", 8)


# --------------------------------------------------------------------------- #
# 大六壬 — deterministic by date/time
# --------------------------------------------------------------------------- #

@needs_lunar
def test_liuren_structure():
    d = run("liuren_cast.py", "--date", "2026-06-01", "--time", "14:30", "--question", "x")
    assert d["ok"] is True
    has(d, "ri_gan", "ri_zhi", "month_zhi")
    # Value golden — 2026-06-01 is 丙午 day, 占时 within 巳 month-general window.
    assert (d["ri_gan"], d["ri_zhi"]) == ("丙", "午")


# --------------------------------------------------------------------------- #
# 黄历 — deterministic by date
# --------------------------------------------------------------------------- #

@needs_lunar
def test_huangli_structure():
    d = run("huangli_query.py", "--date", "2026-06-01")
    has(d, "yi", "ji", "ganzhi", "zhi_shen_12jianchu")
    assert isinstance(d["yi"], list)
    assert isinstance(d["ji"], list)


@needs_lunar
def test_huangli_jishi_uses_huangdao_not_all12():
    """REGRESSION: 吉时/凶时 must come from 时辰黄黑道 (吉/凶), not "has any 宜".
    The old logic marked all 时辰 吉 and 0 凶.

    13 blocks since v1.4.0 (子时 split into 早子/夜子)."""
    d = run("huangli_query.py", "--date", "2026-06-01")
    ji, xiong = d["ji_shi"], d["xiong_shi"]
    assert len(ji) + len(xiong) == 13          # every 时辰 classified
    assert 0 < len(ji) < 13                     # not all-吉 (the bug)
    assert len(xiong) > 0                       # 凶时 exist
    assert all(s.get("luck") == "吉" for s in ji)
    assert all(s.get("huang_hei_dao") == "黄道" for s in ji)


@needs_lunar
def test_ziwei_clock_school_golden_and_solar_correction():
    """The old clock-time golden is preserved under an explicit school option."""
    d = run("ziwei_calc.py", "--year", "1995", "--month", "7", "--day", "20",
            "--hour", "1", "--gender", "female", "--lunar", "--time-standard", "clock")
    assert (d["ming_gong"]["branch"], d["shen_gong"]["branch"],
            d["wuxing_ju"]["name"]) == ("未", "酉", "木三局")
    # Explicit far-west longitude near midnight DOES correct (different 命宫).
    near = run("ziwei_calc.py", "--year", "2000", "--month", "6", "--day", "15",
               "--hour", "23", "--minute", "30", "--gender", "male")
    west = run("ziwei_calc.py", "--year", "2000", "--month", "6", "--day", "15",
               "--hour", "23", "--minute", "30", "--longitude", "75", "--gender", "male")
    assert near["ming_gong"]["branch"] != west["ming_gong"]["branch"]


# --------------------------------------------------------------------------- #
# 紫微斗数 — structure of the hand-rolled engine
# --------------------------------------------------------------------------- #

@needs_lunar
def test_ziwei_structure():
    d = run("ziwei_calc.py", "--year", "1995", "--month", "7", "--day", "20",
            "--hour", "1", "--gender", "female", "--lunar")
    assert d["ok"] is True
    has(d, "ming_gong", "shen_gong", "wuxing_ju", "ziwei_position")


# --------------------------------------------------------------------------- #
# 五鼠遁 invariant — hour-stem is fixed by day-stem (table-free oracle).
# 甲己日->甲子时, 乙庚->丙子, 丙辛->戊子, 丁壬->庚子, 戊癸->壬子.
# Verified through the real bazi engine at 00:30 (早子时, unambiguous).
# --------------------------------------------------------------------------- #

WUSHU_DUN = {
    "甲": "甲", "己": "甲",
    "乙": "丙", "庚": "丙",
    "丙": "戊", "辛": "戊",
    "丁": "庚", "壬": "庚",
    "戊": "壬", "癸": "壬",
}

@needs_lunar
@pytest.mark.parametrize("y,m,dd", [
    (2020, 6, 15), (2021, 3, 9), (2022, 11, 1), (1990, 5, 10), (2000, 1, 15),
])
def test_wushu_dun_hour_stem_invariant(y, m, dd):
    d = run("bazi_calc.py", "--year", y, "--month", m, "--day", dd,
            "--hour", 0, "--minute", 30, "--gender", "male", "--as-of-year", 2026)
    day_stem = d["four_pillars"]["day"]["stem"]
    hour_gz = d["four_pillars"]["hour"]["ganzhi"]
    assert hour_gz[1] == "子"                     # 00:30 is 子时
    assert hour_gz[0] == WUSHU_DUN[day_stem], (
        f"五鼠遁 violated: 日干{day_stem} -> 时干 should be "
        f"{WUSHU_DUN[day_stem]}子, got {hour_gz}")


# --------------------------------------------------------------------------- #
# --help 在非 UTF-8 控制台 / 管道下必须可用
# --------------------------------------------------------------------------- #

def _is_cli(path) -> bool:
    """A CLI has an argparse entry point; helper modules do not."""
    return '__main__' in path.read_text(encoding="utf-8")


CLI_SCRIPTS = sorted(
    p.name for p in SCRIPTS.glob("*.py")
    if p.name not in {"utils.py", "build_skill.py"} and _is_cli(p)
)


@pytest.mark.parametrize("script", CLI_SCRIPTS)
def test_help_survives_non_utf8_console(script):
    """中文 help 在 cp1252 环境下不得崩溃, 且 stdout 必须仍是合法 UTF-8.

    真实失效场景是 stdout 走管道 (agent 调用方式) 与非 CJK 控制台, 此时
    Python 回退到 ANSI 代码页, argparse 写 help 时抛 UnicodeEncodeError.
    """
    import os
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--help"],
        capture_output=True, env=env,
    )
    assert proc.returncode == 0, (
        f"{script} --help rc={proc.returncode} under cp1252\n"
        f"stderr={proc.stderr[:400]!r}"
    )
    proc.stdout.decode("utf-8")  # raises UnicodeDecodeError if mojibake


@pytest.mark.parametrize("script", CLI_SCRIPTS)
def test_help_documents_output_keys(script):
    """`--help` must carry the output schema: callers (Claude included) have no
    other place to learn that bazi emits `four_pillars` not `pillars`, or that
    huangli emits `ji_shi`/`shichen_detail`. Deliberately in the epilog rather
    than a docs/ file."""
    if script == "entropy.py":
        pytest.skip("entropy.py is a helper module, not a CLI")
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / script), "--help"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "Top-level JSON keys" in proc.stdout, f"{script} --help has no schema"


@needs_lunar
def test_ziwei_full_output_snapshot():
    """Value-level lock ahead of the ziwei_calc module split.

    evals only asserts has_keys for this engine, so 命宫/身宫/五行局/星位/四化/
    大限 values were unguarded — the same gap the bazi snapshot closed."""
    import json
    from pathlib import Path

    from conftest import run_cli

    got = run_cli("ziwei_calc.py", "--year", 2000, "--month", 1, "--day", 15,
                  "--hour", 10, "--gender", "male")
    got.pop("version", None)
    want = json.loads(
        (Path(__file__).resolve().parent / "data" /
         "ziwei_snapshot_20000115.json").read_text(encoding="utf-8"))
    assert got == want


@needs_lunar
def test_ziwei_leap_month_splits_at_the_fifteenth():
    """02-ziwei-paipan.md:15 — 闰月处理: 十五日前算上月, 十五日后算下月 (主流).

    ziwei_calc took abs(lunar.getMonth()), so the whole leap month counted as
    the base month and a birth on 闰四月十六 produced a chart identical to
    闰四月初十. 命宫/身宫/斗君/辅星 all key off the lunar month, so the entire
    chart was shifted one palace for such births.
    """
    from conftest import run_cli

    early = run_cli("ziwei_calc.py", "--lunar", "--year", 2020, "--month", 4,
                    "--day", 10, "--hour", 10, "--gender", "male", "--leap")
    late = run_cli("ziwei_calc.py", "--lunar", "--year", 2020, "--month", 4,
                   "--day", 16, "--hour", 10, "--gender", "male", "--leap")

    assert early["ming_gong"]["branch"] != late["ming_gong"]["branch"], (
        "闰月 before and after the 15th must not yield the same 命宫")
    assert early["input"]["effective_lunar_month"] == 4
    assert late["input"]["effective_lunar_month"] == 5
    assert "闰月" in late["notes"][0]


@needs_lunar
def test_non_leap_month_is_unaffected_by_the_split():
    from conftest import run_cli
    d = run_cli("ziwei_calc.py", "--lunar", "--year", 2020, "--month", 4,
                "--day", 16, "--hour", 10, "--gender", "male")
    assert d["input"]["effective_lunar_month"] == 4
    assert not any("闰月" in n for n in d["notes"])


@needs_lunar
def test_ming_zhu_is_keyed_by_ming_gong_branch():
    """《紫微斗数全书·安命主诀》: 子宫贪狼丑亥巨门, 寅戌禄存卯酉文曲, 辰申廉贞巳未武曲,
    午宫破军 — keyed by the 命宫 branch. ziwei_calc looked it up by 年支, so
    every chart whose 命宫 branch differed from its 年支 (most of them) carried
    the wrong 命主. Found by differential comparison against iztro-py, which
    agreed with us on 56 of 57 fields across 7 charts — this was the 57th.
    身主 IS keyed by 年支, and was already right.
    """
    from conftest import run_cli

    table = {"子": "贪狼", "丑": "巨门", "亥": "巨门", "寅": "禄存", "戌": "禄存",
             "卯": "文曲", "酉": "文曲", "辰": "廉贞", "申": "廉贞",
             "巳": "武曲", "未": "武曲", "午": "破军"}
    births = [(2000, 1, 15, 10, "male"), (1985, 6, 30, 22, "male"),
              (1992, 11, 11, 0, "female"), (2010, 3, 5, 12, "female"),
              (1975, 9, 1, 5, "male")]
    for y, m, d, h, g in births:
        out = run_cli("ziwei_calc.py", "--year", y, "--month", m, "--day", d,
                      "--hour", h, "--gender", g)
        want = table[out["ming_gong"]["branch"]]
        assert out["ming_zhu"] == want, (y, m, d, h, out["ming_gong"], out["ming_zhu"])


@needs_lunar
def test_ziwei_sect_shares_the_bazi_convention():
    """One --sect for both engines. Under 子正换日 (2, default) a 23:30 birth keeps
    its calendar day; under 子初换日 (1) the whole date rolls forward, so 命宫
    and the 紫微 star-table day both move. Mixing schools across the two engines
    for the same birth would be self-contradictory."""
    from conftest import run_cli
    s2 = run_cli("ziwei_calc.py", "--year", 1985, "--month", 6, "--day", 30,
                 "--hour", 23, "--minute", 30, "--gender", "male")
    s1 = run_cli("ziwei_calc.py", "--year", 1985, "--month", 6, "--day", 30,
                 "--hour", 23, "--minute", 30, "--gender", "male", "--sect", 1)
    assert s2["sect"]["value"] == 2 and s1["sect"]["value"] == 1
    assert s2["lunar_date"]["day"] + 1 == s1["lunar_date"]["day"]
    assert s2["ziwei_position"] != s1["ziwei_position"]
    assert any("子初换日" in n for n in s1["notes"])


@needs_lunar
def test_ziwei_leap_month_and_late_zi_do_not_double_shift():
    """闰月十六 23:30. Sect 2: month attribution flips (day 16 > 15), day stays.
    Sect 1: the date rolls to 十七 first, then the same >15 rule applies — one
    month shift, never two."""
    from conftest import run_cli
    for sect in (1, 2):
        d = run_cli("ziwei_calc.py", "--lunar", "--leap", "--year", 2020,
                    "--month", 4, "--day", 16, "--hour", 23, "--minute", 30,
                    "--gender", "male", "--sect", sect)
        assert d["input"]["effective_lunar_month"] == 5, (sect, d["input"])
        assert d["lunar_date"]["day"] == (17 if sect == 1 else 16)


@needs_lunar
def test_da_xian_direction_follows_the_classic():
    """《紫微斗数全书》卷二·安大限诀:「阳男阴女从命前一宫起顺行，是父母宫；
    阴男阳女从命后一宫起逆行，是兄弟宫。」

    assign_palaces puts 父母宫 (index 11) at mg_idx+1 and 兄弟宫 (index 1) at
    mg_idx-1, so 顺行 must be branch-INCREASING and 逆行 branch-DECREASING.
    The code had the two branches swapped: a 阳男 walked into 兄弟宫 and a 阴男
    into 父母宫. references/02-ziwei.md:517 states the same worked example —
    水二局阳年男命 命宫午 → 第二大限 顺一 父母宫 未 (午→未, increasing).

    The iztro differential could not catch this: it covers 命宫/身宫/五行局/
    命主/身主/14主星/十二宫, not 大限.
    """
    from conftest import run_cli
    from utils import DIZHI

    # 庚午 year (阳), male -> 阳男 -> 顺行 -> 父母宫, branch mg+1
    yang = run_cli("ziwei_calc.py", "--year", 1990, "--month", 8, "--day", 10,
                   "--hour", 10, "--gender", "male")
    mg = DIZHI.index(yang["ming_gong"]["branch"])
    assert yang["da_xian"][1]["palace_name"] == "父母宫", yang["da_xian"][:2]
    assert yang["da_xian"][1]["palace_branch"] == DIZHI[(mg + 1) % 12]

    # 己卯 year (阴), male -> 阴男 -> 逆行 -> 兄弟宫, branch mg-1
    yin = run_cli("ziwei_calc.py", "--year", 2000, "--month", 1, "--day", 15,
                  "--hour", 10, "--gender", "male")
    mg2 = DIZHI.index(yin["ming_gong"]["branch"])
    assert yin["da_xian"][1]["palace_name"] == "兄弟宫", yin["da_xian"][:2]
    assert yin["da_xian"][1]["palace_branch"] == DIZHI[(mg2 - 1) % 12]

    # first limit is always 命宫 itself
    for d in (yang, yin):
        assert d["da_xian"][0]["palace_name"] == "命宫"


@needs_lunar
def test_dou_jun_is_not_a_copy_of_ming_gong():
    """《紫微斗数全书》卷二·安斗君诀:「于流年太岁宫起正月逆至本生月，又从本生月
    起子顺数至本生时安斗君。」

    calc_dou_jun was character-for-character identical to calc_ming_gong —
    寅-anchored, 顺 to the month, 逆 to the hour — i.e. the 安身命例 rule copied
    under the wrong name, so the chart reported 命宫 twice. 斗君 is also a
    流年-indexed quantity, and a function taking no 流年 cannot express one.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from utils import DIZHI
    from ziwei_palaces import calc_dou_jun
    from ziwei_tables import calc_ming_gong

    # 流年 must actually move the answer
    a = calc_dou_jun("子", 5, 10)
    b = calc_dou_jun("午", 5, 10)
    assert a != b, "斗君 does not depend on 流年"

    # and it must not simply reproduce 命宫
    same = sum(1 for m in range(1, 13) for h in (0, 6, 12, 18)
               if calc_dou_jun("寅", m, h) == calc_ming_gong(m, h))
    assert same < 48, "斗君 still mirrors 命宫 for every input"

    # the rule itself: 太岁宫起正月逆至生月, 再从生月起子顺至生时
    for yb in ("子", "卯", "午", "酉"):
        for m in (1, 5, 11):
            for h in (0, 7, 23):
                from utils import hour_branch_index
                want = DIZHI[(DIZHI.index(yb) - (m - 1) + hour_branch_index(h)) % 12]
                assert calc_dou_jun(yb, m, h) == want, (yb, m, h)


@needs_lunar
def test_qisha_brightness_follows_the_classic():
    """《紫微斗数全书》卷二·七杀: 子午旺、卯酉旺、辰戌庙、丑未庙、寅申庙、巳亥和平
    — six clauses covering all twelve palaces with no gap.

    The table had 丑卯辰未酉戌 as 陷, two to three levels off, and 庙→陷 is not
    producible by any 七级→四级 folding. The same file's 破军 (also 杀破狼) has
    辰庙 戌庙 丑旺 未旺, so 七杀's four 墓 reading 陷 looked like a bulk mis-fill.
    Brightness is reader-facing — Claude narrates it — so this told users their
    七杀 was afflicted where the classic calls it 庙.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from ziwei_stars import BRIGHTNESS

    want = {"子": "旺", "午": "旺", "卯": "旺", "酉": "旺",
            "辰": "庙", "戌": "庙", "丑": "庙", "未": "庙",
            "寅": "庙", "申": "庙", "巳": "平", "亥": "平"}
    assert BRIGHTNESS["七杀"] == want, BRIGHTNESS["七杀"]


def test_tiankui_tianyue_xin_row_is_ma_hu_not_hu_ma():
    """辛 shipped 天魁寅/天钺午 — copied from an electronic text whose last line
    reads 「辛逢虎马」. That witness is corrupt in the same breath (「丙丁猪狗」;
    戌 is nobody's 丙丁贵人), and this very table already takes 猪鸡 over 猪狗
    for 丙丁, so the 辛 row was an unfixed leftover, not a chosen edition.
    《三命通会》 puts 辛's 阴贵 at 午 (「丙德在午，丙与辛合，辛以马」) and every
    line of the couplet lists 阴贵 first, so 辛 must read 马虎.

    This swapped two of the six 吉星 on every 辛-year chart — 10% of charts.
    The iztro differential missed it because the grid only compared 14 主星;
    it now compares 六吉 and 禄存/羊陀 too, and 87 of 903 cases fail on the old
    values.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from ziwei_stars import TIAN_KUI, TIAN_YUE

    assert TIAN_KUI["辛"] == "午" and TIAN_YUE["辛"] == "寅"
    # 阴贵 and 阳贵 are the two 天乙 seats of one stem and can never coincide.
    assert all(TIAN_KUI[g] != TIAN_YUE[g] for g in TIAN_KUI)
    assert set(TIAN_KUI) == set(TIAN_YUE) == set("甲乙丙丁戊己庚辛壬癸")


def test_meihua_wangshuai_matches_its_own_reference_table():
    """ti_state 必须逐格等于 references/05-meihua.md §5.2 那张表。

    上一版测试只断言「八卦 x 12 月能取遍 旺相休囚死」—— 集合式断言, 对标签置换
    结构性失明: 把 休/囚 两个 return 对调后全量套件仍全绿, 正是同一个 commit
    后半段自己指认的缺陷类, 就留在它刚改过的上一个函数里。月份→五行的映射同样
    只钉了 土 的 {1,4,7,10}, 把 8/9 月改成水、11/12 改成金也全绿 —— 12 个月里
    7 个零覆盖。

    改为从文档解析整张表再逐格 diff (范式同 test_cimu_and_xuetang_match_their_own
    _reference)。96 格全部钉死, 任何一次标签置换或月份错配都会红。
    """
    import re
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import meihua_cast
    from utils import BAGUA

    md = (root / "references" / "05-meihua.md").read_text(encoding="utf-8")
    body = md.split("### 5.2")[1].split("### 5.3")[0]

    # | 月令 | 公历约当 | 旺卦 | 相卦 | 休卦 | 囚卦 | 死卦 |
    want: dict[tuple[str, int], str] = {}
    states = ["旺", "相", "休", "囚", "死"]
    rows = 0
    for line in body.splitlines():
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) != 7 or cells[0] in ("月令", "") or set(cells[1]) <= set("-"):
            continue
        months = [int(x) for x in re.findall(r"\d+", cells[1])]
        assert months, line
        rows += 1
        for state, cell in zip(states, cells[2:], strict=True):
            for tri in BAGUA:
                if tri in cell:
                    for mo in months:
                        want[(tri, mo)] = state
    assert rows == 5, f"§5.2 应有 5 行月令, 解析到 {rows}"
    assert len(want) == 8 * 12, f"表不完整: {len(want)}/96 格"

    for (tri, mo), state in sorted(want.items()):
        got = meihua_cast.ti_state(tri, mo)
        assert got == state, f"{tri}({BAGUA[tri]['wuxing']}) {mo}月: 引擎={got} 文档={state}"


def test_meihua_season_table_covers_every_month_exactly_once():
    """月份不重不漏 —— 旧表把 辰未戌丑 同时列进四季行和「四季月末」行, 同一个月
    出现两次, 引擎只能站一边, 于是文档必然与引擎有一半对不上。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import meihua_cast

    assert set(meihua_cast.SEASON_WX_BY_MONTH) == set(range(1, 13))
    assert set(meihua_cast.SEASON_WX_BY_MONTH.values()) == {"木", "火", "土", "金", "水"}
    assert {m for m, wx in meihua_cast.SEASON_WX_BY_MONTH.items()
            if wx == "土"} == {1, 4, 7, 10}


def test_meihua_tiyong_labels_are_not_interchangeable():
    """体用关系的结论标签可以整体倒置而无人察觉: 把 用生体(吉) 与 体生用(耗体)
    对调, 全量套件仍 2145 passed。这是梅花唯一的判断性输出, 会被直接叙述给用户。
    原有断言只检查 startswith 属于五个关系名之一, 对调后仍然属于。

    这里逐对锁死方向: 生我者为「用生体」, 我生者为「体生用」, 克我者凶, 我克者吉。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from meihua_cast import ti_yong_relation
    from utils import BAGUA

    # 五行相生: 木生火 生土 生金 生水 生木; 相克: 木克土 克水 克火 克金 克木
    by_wx = {}
    for tri, info in BAGUA.items():
        by_wx.setdefault(info["wuxing"], tri)
    T = by_wx  # 木=震 火=离 土=艮/坤 金=乾/兑 水=坎

    assert ti_yong_relation(T["火"], T["木"]).startswith("用生体")   # 木生火, 体火
    assert ti_yong_relation(T["木"], T["火"]).startswith("体生用")   # 体木生用火
    assert ti_yong_relation(T["木"], T["金"]).startswith("用克体")   # 金克木, 体木
    assert ti_yong_relation(T["金"], T["木"]).startswith("体克用")   # 体金克用木
    assert ti_yong_relation(T["木"], T["木"]) == "比和"
    assert "吉" in ti_yong_relation(T["火"], T["木"])
    assert "凶" in ti_yong_relation(T["木"], T["金"])


@pytest.mark.parametrize("script", sorted(
    p.name for p in SCRIPTS.glob("*.py")
    if "argparse" in p.read_text(encoding="utf-8")))
def test_argparse_help_strings_escape_percent(script):
    """argparse 对 help 字符串做 %-格式化, 未转义的 % 会让 --help 直接崩栈。

    实测: 给 ziwei_calc 加「占载荷约 53%; …」后 `--help` 抛
    ValueError: unsupported format character ';' —— 而 --help 正是调用方了解
    输出契约的入口。写百分比必须用 %%。

    用 AST 取 help= 的字面值 (正则取字符串字面量在转义上太脆)。
    """
    import ast
    tree = ast.parse((SCRIPTS / script).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg not in ("help", "description", "epilog"):
                continue
            try:
                value = ast.literal_eval(kw.value)
            except Exception:
                continue                       # 拼接出来的, 交给运行时检查
            if not isinstance(value, str):
                continue
            # 合法写法: %% 转义, 以及 %(default)s 这类命名占位
            stripped = value.replace("%%", "")
            for name in ("default", "prog", "choices", "type", "metavar"):
                stripped = stripped.replace(f"%({name})s", "")
            if "%" in stripped:
                offenders.append(f"{kw.arg}={value[:60]!r}")
    assert not offenders, (
        f"{script} 的 help/description 里有未转义的 %, --help 会崩: {offenders}")
