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
def test_ziwei_value_golden_and_longitude_optin():
    """ziwei standard chart value golden + longitude correction is opt-in
    (default longitude must NOT shift the 时辰-granular chart)."""
    d = run("ziwei_calc.py", "--year", "1995", "--month", "7", "--day", "20",
            "--hour", "1", "--gender", "female", "--lunar")
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
