"""Coverage for previously-untested deterministic subcommands.

yijing numbers/text, meihua name/time, xiaoliuren solar — all fully deterministic
(no RNG; time-based casts pin the clock with --datetime), so value-golden
assertions are stable. The yijing
numbers case is hand-verifiable: upper 3 = 离☲, lower 5 = 巽☴ → 火风鼎 (#50);
change line 1 (初爻, 阴) flips 巽 → 乾 → 火天大有 (#14).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import run_cli

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

pytest.importorskip("lunar_python")


def run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# 周易 numbers / text casts
# --------------------------------------------------------------------------- #

def test_yijing_numbers_hand_verified_ding():
    """先天卦数 3=离(上) 5=巽(下) → 火风鼎 #50; 动初爻 → 火天大有 #14.

    手工推导: 巽☴ 自下而上 阴阳阳, 离☲ 自下而上 阳阴阳 → 鼎 阴阳阳阳阴阳.
    初爻(阴)变阳 → 下卦成乾☰ → 火天大有 #14. 互卦 2,3,4=乾 / 3,4,5=兑 → 泽天夬 #43.
    v1.4.0 前此处曾断言 火水未济 #64 —— 那是爻序镜像造成的错值 (见 CHANGELOG 勘误).
    """
    d = run("yijing_cast.py", "numbers", "--upper", "3", "--lower", "5", "--change", "1")
    assert (d["main_hex"]["number"], d["main_hex"]["name"]) == (50, "火风鼎")
    assert [ln["value"] for ln in d["main_hex"]["lines"]] == [6, 7, 7, 7, 8, 7]
    assert d["active_lines"] == [1]
    assert d["changed_hex"]["name"] == "火天大有"
    assert d["nuclear_hex"]["name"] == "泽天夬"


def test_yijing_text_deterministic():
    a = run("yijing_cast.py", "text", "--text", "求财")
    b = run("yijing_cast.py", "text", "--text", "求财")
    assert a["main_hex"]["number"] == b["main_hex"]["number"] == 1
    assert a["main_hex"]["name"] == "乾为天"


# --------------------------------------------------------------------------- #
# 梅花 name cast
# --------------------------------------------------------------------------- #

def test_meihua_name_deterministic():
    d = run("meihua_cast.py", "name", "--text", "张三")
    assert d["main_hex"]["name"] == "乾为天"
    assert d["changing_line"] == 2
    assert d["changed_hex"]["name"] == "天火同人"


# --------------------------------------------------------------------------- #
# 小六壬 solar subcommand (auto lunar conversion path)
# --------------------------------------------------------------------------- #

def test_xiaoliuren_solar_golden():
    d = run("xiaoliuren_cast.py", "solar", "--date", "2026-06-24", "--time", "13:00")
    assert d["result"]["palace"] == "速喜"
    assert d["result"]["tone"] == "吉"


def test_xiaoliuren_solar_hai_to_zi_boundary():
    """亥→子 边界 golden: 22:59 属亥, 23:00/23:01 同属子, 三者不得同宫.

    旧断言只查返回值在六宫之内 —— 对任何返回值都成立, 锁不住边界.
    """
    def palace(t):
        return run("xiaoliuren_cast.py", "solar",
                   "--date", "2026-06-24", "--time", t)["result"]["palace"]

    hai, zi_start, zi_next = palace("22:59"), palace("23:00"), palace("23:01")
    assert hai == "大安"
    assert zi_start == zi_next == "留连"
    assert hai != zi_start, "23:00 必须已跨入子时"


# --------------------------------------------------------------------------- #
# 黄历 传统时辰 boundary regression
# --------------------------------------------------------------------------- #

def test_huangli_shichen_traditional_boundaries():
    """REGRESSION: 时辰 blocks use classical odd-start boundaries and每块的
    干支地支必须等于其时辰 (旧的偶数块横跨两个时辰).

    v1.4.0 起子时分早子/夜子两行, 故 13 行且按时钟顺序排列.
    """
    d = run("huangli_query.py", "--date", "2026-06-24")
    detail = d["shichen_detail"]
    assert len(detail) == 13
    assert [s["shichen"] for s in detail] == [
        "早子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "夜子"]
    assert detail[0]["hour_range"] == "00:00-01:00"
    assert detail[5]["shichen"] == "巳"
    assert detail[5]["hour_range"] == "09:00-11:00"
    assert detail[-1]["hour_range"] == "23:00-24:00"
    for s in detail:
        assert s["ganzhi"][1] == s["branch"], (
            f"{s['hour_range']} 干支 {s['ganzhi']} != 时辰 {s['branch']}")


# --------------------------------------------------------------------------- #
# 爻位约定 oracle — 卦名往返自洽掩盖了爻序镜像, 故断言爻值而非卦名
# --------------------------------------------------------------------------- #

def _yy(lines: list[int]) -> list[int]:
    """Reduce raw line values to yin/yang (1=阳, 0=阴)."""
    return [1 if v in (7, 9) else 0 for v in lines]


def test_from_numbers_lines_match_trigram_definition():
    """每组 (上卦, 下卦): 生成的 6 爻自下而上必须等于八卦的经典爻画.

    BAGUA[x]["lines"] 自上而下, 故自下而上取 reversed().
    """
    import yijing_cast as yj
    from utils import BAGUA, XIANTIAN_NUM_TO_TRIGRAM

    for upper in range(1, 9):
        for lower in range(1, 9):
            lines = _yy(yj.from_numbers(upper, lower, 1))
            up_tri = XIANTIAN_NUM_TO_TRIGRAM[upper]
            low_tri = XIANTIAN_NUM_TO_TRIGRAM[lower]
            want = (list(reversed(BAGUA[low_tri]["lines"]))
                    + list(reversed(BAGUA[up_tri]["lines"])))
            # 动爻已把 7->9 / 8->6, 阴阳不变, 故可直接比阴阳
            assert lines == want, (
                f"上{up_tri}/下{low_tri}: 爻画自下而上 {lines} != 经典 {want}"
            )


def test_main_hex_lines_match_asset_line_types():
    """全 64 卦: 引擎输出的爻阴阳必须与 assets/64hex.json 的 六/九 一致.

    资产的 lines[].type 自下而上 (position 1 = 初爻), 是独立于代码位序约定的
    经典基准 —— 卦名对而爻画反的错误只能被这条断言抓到.
    """
    import yijing_cast as yj

    assets = yj.load_hex_assets()
    raw = json.loads(
        (SCRIPTS.parent / "assets" / "64hex.json").read_text(encoding="utf-8")
    )
    by_num = {h["number"]: h for h in raw["hexagrams"]}
    seen = set()
    for upper in range(1, 9):
        for lower in range(1, 9):
            lines = yj.from_numbers(upper, lower, 1)
            info = yj.hex_info(lines, assets)
            num = info["number"]
            seen.add(num)
            want = [1 if ln["type"] == "九" else 0
                    for ln in sorted(by_num[num]["lines"],
                                     key=lambda x: x["position"])]
            assert _yy(lines) == want, (
                f"#{num} {info['name']}: 爻画 {_yy(lines)} != 资产 {want}"
            )
    assert len(seen) == 64, f"应覆盖全 64 卦, 实际 {len(seen)}"


def test_active_lines_equal_positions_where_main_and_changed_differ():
    """动爻下标必须等于本卦与变卦逐爻相异的位置集合 (全 384 组)."""
    import yijing_cast as yj

    for upper in range(1, 9):
        for lower in range(1, 9):
            for change in range(1, 7):
                lines = yj.from_numbers(upper, lower, change)
                changed = yj.changed_lines(lines)
                diff = [i + 1 for i, (a, b) in enumerate(zip(_yy(lines), _yy(changed), strict=True))
                        if a != b]
                assert diff == [change], (
                    f"上{upper}/下{lower}/动{change}: 相异爻位 {diff} != [{change}]"
                )


# --------------------------------------------------------------------------- #
# 黄历 时辰 — 早子/夜子 分列, 天干须合五鼠遁
# --------------------------------------------------------------------------- #

def test_huangli_shichen_pillars_follow_wushu_dun():
    """13 行: 早子(本日干) → 亥 为连续 60 甲子段, 夜子(次日干) 另计.

    只断地支等于时辰名的旧断言无法发现"子行报次日时柱", 故此处断天干.
    """
    from utils import WUSHU_DUN, jiazi_index

    d = run_cli("huangli_query.py", "--date", "2026-06-24")
    detail = d["shichen_detail"]
    day_stem = d["ganzhi"]["day"][0]

    assert len(detail) == 13, "早子 00:00-01:00 与 夜子 23:00-24:00 必须分列"
    assert detail[0]["shichen"] == "早子"
    assert detail[0]["hour_range"] == "00:00-01:00"
    assert detail[-1]["shichen"] == "夜子"
    assert detail[-1]["hour_range"] == "23:00-24:00"

    # 早子 天干 = 五鼠遁(本日干)
    assert detail[0]["ganzhi"][0] == WUSHU_DUN[day_stem], (
        f"早子时干应为 {WUSHU_DUN[day_stem]}, 实际 {detail[0]['ganzhi']}"
    )
    # 早子 → 亥 连续 60 甲子
    run12 = detail[:12]
    idxs = [jiazi_index(r["ganzhi"][0], r["ganzhi"][1]) for r in run12]
    for a, b in zip(idxs, idxs[1:], strict=False):
        assert (a + 1) % 60 == b, f"时柱非连续六十甲子: {idxs}"
    # 夜子 天干 = 五鼠遁(次日干), 即比早子晚一轮
    nxt = run_cli("huangli_query.py", "--date", "2026-06-25")
    assert detail[-1]["ganzhi"][0] == WUSHU_DUN[nxt["ganzhi"]["day"][0]]


def test_huangli_shichen_labels_match_branches():
    """每块的时柱地支必须等于其时辰名 (子/丑/…/亥); 早子与夜子同为 子."""
    d = run_cli("huangli_query.py", "--date", "2026-06-24")
    for row in d["shichen_detail"]:
        want = "子" if row["shichen"] in ("早子", "夜子") else row["shichen"]
        assert row["ganzhi"][1] == want, f"{row['shichen']}: {row['ganzhi']}"


# --------------------------------------------------------------------------- #
# 时间起卦可复现性 — --datetime 注入
# --------------------------------------------------------------------------- #

def test_meihua_datetime_injection_is_reproducible():
    """固定 --datetime 后三个子命令都必须逐字段稳定.

    梅花的 体用旺衰 由「当下月令」决定, 三个子命令都吃 now.month, 故
    --datetime 挂在顶层而非 time 之下. 此前 body_strength 随真实月份漂移,
    无法 golden, 是 100% 未测字段.
    """
    args = ("--datetime", "2026-06-24T13:05")
    a = run_cli("meihua_cast.py", *args, "time")
    b = run_cli("meihua_cast.py", *args, "time")
    assert a == b
    assert a["main_hex"]["name"] == "坤为地"
    assert a["ti_yong"]["body_strength"] == "相"

    # numbers / name 也吃月令, 同样必须被 --datetime 固定
    n1 = run_cli("meihua_cast.py", *args, "numbers", "--upper", "3", "--lower", "5")
    n2 = run_cli("meihua_cast.py", *args, "numbers", "--upper", "3", "--lower", "5")
    assert n1 == n2
    x1 = run_cli("meihua_cast.py", *args, "name", "--text", "张三")
    x2 = run_cli("meihua_cast.py", *args, "name", "--text", "张三")
    assert x1 == x2


def test_yijing_time_datetime_injection_is_reproducible():
    a = run_cli("yijing_cast.py", "time", "--datetime", "2026-06-24T13:05")
    b = run_cli("yijing_cast.py", "time", "--datetime", "2026-06-24T13:05")
    assert a["main_hex"] == b["main_hex"]
    assert a["main_hex"]["name"] == "坤为地"


def test_bad_datetime_reports_error_and_exits_1():
    for script, tail in (("meihua_cast.py", ("time",)),
                         ("yijing_cast.py", ())):
        argv = (("--datetime", "nope") + tail if script.startswith("meihua")
                else ("time", "--datetime", "nope"))
        d = run_cli(script, *argv, expect_rc=1)
        assert d["error"] == "bad_datetime"


# --------------------------------------------------------------------------- #
# 卦辞查阅 — 取代整读 references/64hex-full.md
# --------------------------------------------------------------------------- #

def test_yijing_lookup_single_hexagram():
    """lookup 必须给出 64hex-full.md 曾提供的全部内容: 卦名/卦辞/大象/六爻辞/白话.

    此前周易路由强制整读 43 KB 的 64hex-full.md, 而其 卦辞 64/64、象辞 64/64、
    爻辞 384/384 与 assets/64hex.json 逐条相同 —— 脚本本就能给。
    """
    d = run_cli("yijing_cast.py", "lookup", "--number", "50")
    assert d["number"] == 50
    assert d["name"] == "火风鼎"
    assert d["judgment"].startswith("元吉")
    assert "木上有火" in d["image"]
    assert len(d["lines"]) == 6
    assert "鼎颠趾" in d["lines"][0]
    assert d["summary"]


def test_yijing_lookup_all_covers_64():
    """--all 保留"全卦浏览"能力, 不因删除参考文档而丢失功能."""
    d = run_cli("yijing_cast.py", "lookup", "--all")
    assert len(d["hexagrams"]) == 64
    nums = sorted(h["number"] for h in d["hexagrams"])
    assert nums == list(range(1, 65))
    for h in d["hexagrams"]:
        assert h["judgment"] and h["image"] and len(h["lines"]) == 6


def test_yijing_lookup_rejects_out_of_range():
    d = run_cli("yijing_cast.py", "lookup", "--number", "65", expect_rc=1)
    assert d["error"] == "bad_hexagram_number"


def test_lines_visual_rows_carry_their_position_label():
    """The drawing is 上爻-first while lines/active_lines number 初爻=1, so the
    ○ marker lands on visual row (7 - position). Without row labels a reader
    counting from the top reads a 三爻 move as 四爻 — and v1.4.0 already had to
    fix a real mirrored-爻位 bug in this same file, so the hazard is not
    hypothetical. references/04-liuyao.md §3.1 labels every row; so do we.
    """
    d = run_cli("yijing_cast.py", "numbers", "--upper", "3", "--lower", "5",
                "--change", "3")
    rows = d["main_hex"]["lines_visual"].split("\n")
    assert len(rows) == 6
    assert [r.split()[0] for r in rows] == ["上爻", "五爻", "四爻", "三爻", "二爻", "初爻"]
    # the marked row must be the one active_lines names
    marked = [r for r in rows if "○" in r or "✕" in r]
    assert len(marked) == 1
    assert marked[0].startswith("三爻"), marked[0]
    assert d["active_lines"] == [3]
