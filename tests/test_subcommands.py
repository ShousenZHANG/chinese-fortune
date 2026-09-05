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


@pytest.mark.parametrize("dt,hexagram,body,state", [
    ("2026-04-24T13:05", "坎为水", "坎", "死"),   # 辰月, 土克水
    ("2026-07-24T13:05", "乾为天", "乾", "相"),   # 未月, 土生金
    ("2026-10-24T13:05", "震为雷", "震", "囚"),   # 戌月, 木克土
    ("2026-01-24T13:05", "离为火", "离", "休"),   # 丑月, 火生土
])
def test_meihua_body_strength_golden_in_the_four_earth_months(dt, hexagram, body, state):
    """四季月 (公历 4/7/10/1) 的端到端黄金值。

    上面那条唯一的 body_strength 黄金值把体卦钉在 坤(土) —— 正是「永远不可能旺」
    那个缺陷的当事卦 —— 却挑了 6 月, 是 SEASON_WX_BY_MONTH 里未被改动的 8 个月
    之一, 新旧引擎在该用例都返回「相」。于是那次改动动了 96 格里的 32 格 (33%),
    一条快照都没红。

    这四个日期落在被改动的四个月上, 且四个值在改动前后全部不同
    (休→死、死→相、死→囚、死→休), 下一次同类漂移会立刻现形。
    """
    d = run_cli("meihua_cast.py", "--datetime", dt, "time")
    assert d["main_hex"]["name"] == hexagram
    assert d["ti_yong"]["body_trigram"] == body
    assert d["ti_yong"]["body_strength"] == state
    # 精度标注必须随输出一起交付 —— 月令粒度不足以定 18 天的土王四季分界。
    assert "月令粗略" in d["ti_yong"]["body_strength_granularity"]


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


def test_64hex_binary_field_is_derivable_from_lines_and_trigrams():
    """assets/64hex.json 的 `binary` 是 上→初 编码, 但 28 条 (14 组两两互换)
    写的是另一个真实存在的卦: 小畜↔夬、履↔姤、随↔益、蛊↔损、临↔升、观↔萃、
    大过↔中孚、咸↔渐、恒↔归妹、家人↔革、睽↔鼎、困↔涣、井↔节、巽↔兑。

    没有代码消费这个字段, 所以没有任何测试或差分能碰到它 —— 但它随发布包分发
    (tests/test_build.py 证明 assets/ 整个进 zip), Claude 可以直接读到并据以说
    "此卦为⋯"。权威数据是 lines[].type 与 upper/lower_trigram, 这两者 64/64
    自洽; binary 是它们的冗余副本, 因此可以逐卦重算而非人工校对。
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    d = json.loads((root / "assets" / "64hex.json").read_text(encoding="utf-8"))
    items = list(d["hexagrams"].values()) if isinstance(d.get("hexagrams"), dict) \
        else (d.get("hexagrams") or d)
    assert len(items) == 64

    # 八卦三爻, 写作 上→初 (乾三连=111, 兑上缺=011, 艮覆碗=100 ...)
    tri = {"乾": "111", "兑": "011", "离": "101", "震": "001",
           "巽": "110", "坎": "010", "艮": "100", "坤": "000"}
    for h in items:
        bottom_up = "".join("1" if ln["type"] == "九" else "0" for ln in h["lines"])
        lower, upper = tri[h["lower_trigram"]][::-1], tri[h["upper_trigram"]][::-1]
        # lines 必须与上下卦一致 (这是权威来源, 单独锁一次)
        assert bottom_up == lower + upper, (h["number"], h["name_zh"])
        assert h["binary"] == bottom_up[::-1], (
            h["number"], h["name_zh"], h["binary"], bottom_up[::-1])

    # 唯一性只抓「重复/手滑写错一个」, **抓不到本 bug 类**: 原缺陷是 14 组两两
    # 互换, 互换是置换, 置换保持唯一性 —— 实测把 #9 小畜 与 #43 夬 的 binary
    # 对调, 这里仍然是 64 个不同值。真正承重的是上面那条推导断言。
    # (我在 4f8e9f6 的提交信息里把这条写成「任何一次互换都会留下重复」, 是错的。)
    assert len({h["binary"] for h in items}) == 64


def test_meihua_reference_worked_example_matches_the_engine():
    """references/05-meihua.md §2.3 的双数法算例 (37、98) 原本声称变卦是「风雷益」,
    而益为巽上震下须二爻动; 三爻动实得巽上乾下「风天小畜」, 引擎给的也是小畜 ——
    即引擎对、文档错。

    这批 references 从未与引擎比对过, 而 SKILL.md 让 Claude 照着它们解读。这条
    测试把这一个算例钉住; references 层的整体一致性检查见 P1。
    """
    import json
    import re
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    md = (root / "references" / "05-meihua.md").read_text(encoding="utf-8")

    # 从文档里抓出算例的两个数, 不写死 —— 文档改数字, 测试跟着改。
    m = re.search(r'友人报"(\d+)、(\d+)"', md)
    assert m, "算例格式变了"
    upper, lower = m.group(1), m.group(2)

    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "meihua_cast.py"), "numbers",
         "--upper", upper, "--lower", lower, "--question", "x"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    d = json.loads(proc.stdout)

    assert d["main_hex"]["name"] == "风泽中孚"
    assert d["changed_hex"]["name"] == "风天小畜"
    # 文档必须写着引擎给出的那个变卦, 且不再写旧的错误答案。
    assert "风天小畜" in md
    assert '三爻动 → 变卦"风雷益"' not in md


def test_liuyao_najia_pins_every_line_branch():
    """纳甲定每一爻的地支, 进而定 六亲/世应/旺衰/空亡 —— 即整个断卦层。
    liuyao_cast.py 行覆盖 88.8%, 却没有任何断言检查排出来的爻装了什么;
    变异测试实证: 乾宫 lower ["子","寅","辰"] 改成 ["子","寅","午"] 全量全绿。
    这是「覆盖率高而无 oracle」的干净样本。

    乾宫纳甲 (《卜筮正宗》): 内卦 甲子寅辰, 外卦 壬午申戌; 本例起于丙 (随日辰),
    故取 丙辰/丙午/丙申 … 下三爻地支必为 辰午申。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from liuyao_cast import NAJIA_TABLE

    # 先锁整张表 —— 端到端断言只覆盖某一次起卦碰到的那一宫, 而缺陷可以落在
    # 另外七宫的任何一行。八宫纳甲 (《卜筮正宗》): 乾甲壬、坎戊、艮丙、震庚、
    # 巽辛、离己、坤乙癸、兑丁; 地支自内卦初爻起隔位顺(阳)/逆(阴)行。
    want = {
        "乾": ("甲", "壬", ["子", "寅", "辰"], ["午", "申", "戌"]),
        "坎": ("戊", "戊", ["寅", "辰", "午"], ["申", "戌", "子"]),
        "艮": ("丙", "丙", ["辰", "午", "申"], ["戌", "子", "寅"]),
        "震": ("庚", "庚", ["子", "寅", "辰"], ["午", "申", "戌"]),
        "巽": ("辛", "辛", ["丑", "亥", "酉"], ["未", "巳", "卯"]),
        "离": ("己", "己", ["卯", "丑", "亥"], ["酉", "未", "巳"]),
        "坤": ("乙", "癸", ["未", "巳", "卯"], ["丑", "亥", "酉"]),
        "兑": ("丁", "丁", ["巳", "卯", "丑"], ["亥", "酉", "未"]),
    }
    assert set(NAJIA_TABLE) == set(want), set(NAJIA_TABLE) ^ set(want)
    for tri, (lo_s, up_s, lo_b, up_b) in want.items():
        row = NAJIA_TABLE[tri]
        assert (row["lower_stem"], row["upper_stem"]) == (lo_s, up_s), tri
        assert row["lower_branches"] == lo_b, (tri, row["lower_branches"], lo_b)
        assert row["upper_branches"] == up_b, (tri, row["upper_branches"], up_b)

    d = run_cli("liuyao_cast.py", "coins", "--seed", "7",
                "--date", "2026-06-01", "--time", "10:00")
    lines = d["main_chart"]["lines"]
    assert [ln["position"] for ln in lines] == [1, 2, 3, 4, 5, 6]
    assert [ln["branch"] for ln in lines[:3]] == ["辰", "午", "申"], \
        [ln["branch"] for ln in lines]
    # 地支必须真的驱动五行与六亲, 而不是各算各的
    assert [ln["wuxing"] for ln in lines[:3]] == ["土", "火", "金"]
    assert lines[0]["liu_qin"] == "父母"
    # 世爻有且只有一个, 应爻同理 —— 世应错位是纳甲错的第一个下游症状
    assert sum(1 for ln in lines if ln["is_shi"]) == 1
    assert sum(1 for ln in lines if ln["is_ying"]) == 1


def test_64hex_judgments_are_pinned_per_hexagram():
    """全仓从前对 64hex.json 内容的值断言只有第 50 卦三条; 其余 63 卦卦辞、64 条
    大象、378 条爻辞零断言。变异实证: 第 3、4 卦的 judgment 对调 -> 全量全绿。
    这些正是脚本交付给用户的解读主体。
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    d = json.loads((root / "assets" / "64hex.json").read_text(encoding="utf-8"))
    items = list(d["hexagrams"].values()) if isinstance(d.get("hexagrams"), dict) \
        else d["hexagrams"]
    by_num = {h["number"]: h for h in items}

    # 通行本卦辞, 逐字锁 —— 挑的是彼此相邻、最容易被整体错位的几卦。
    golden = {
        1:  ("乾", "元亨利贞。"),
        2:  ("坤", "元亨,利牝马之贞。"),
        3:  ("屯", "元亨,利贞。勿用有攸往,利建侯。"),
        4:  ("蒙", "亨。匪我求童蒙,童蒙求我。"),
        11: ("泰", "小往大来,吉亨。"),
        12: ("否", "否之匪人,不利君子贞,大往小来。"),
        63: ("既济", "亨小,利贞。初吉终乱。"),
        64: ("未济", "亨。小狐汔济,濡其尾,无攸利。"),
    }
    for num, (name, judgment) in golden.items():
        h = by_num[num]
        assert h["name_zh"] == name, (num, h["name_zh"], name)
        assert h["judgment"].startswith(judgment[:6]), (num, h["judgment"], judgment)

    # 64 条卦辞两两互异 —— 任何一次整体错位都会在这里留下重复。
    judgments = [h["judgment"] for h in items]
    assert len(set(judgments)) == 64, "有卦辞重复, 疑似整体错位"


def test_xiaoliuren_closed_form_matches_the_step_by_step_walk():
    """小六壬的闭式 (month_index + day - 1 + hour_branch_index) mod 6 必须等于
    逐宫步进的结果。

    古法是三段走: 从大安起正月, 数至本月; 从该宫起初一, 数至本日; 从该宫起子时,
    数至本时。引擎把它压成一个取模式 —— 压对了没有, 从前无人验算。这里用步进法
    独立走一遍, 覆盖 12 月 x 30 日 x 12 时辰 = 4320 组全枚举。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from xiaoliuren_cast import PALACES, cast

    names = [p["name"] for p in PALACES]
    assert len(names) == 6 and len(set(names)) == 6, names
    assert names[0] == "大安", names

    for month in range(1, 13):
        for day in range(1, 31):
            for hi in range(12):
                # 步进法: 起大安数月 -> 接着数日 -> 接着数时, 每段都含起点
                pos = 0
                for _ in range(month - 1):
                    pos = (pos + 1) % 6
                for _ in range(day - 1):
                    pos = (pos + 1) % 6
                for _ in range(hi):
                    pos = (pos + 1) % 6
                got = cast(month, day, "子丑寅卯辰巳午未申酉戌亥"[hi])
                assert got["result"]["palace"] == names[pos], (
                    month, day, hi, got["result"]["palace"], names[pos])


def test_xiaoliuren_intermediate_palaces_are_consistent():
    """输出的 month_palace / day_palace 必须与最终宫位处在同一条步进链上 ——
    否则它们只是装饰, 而 Claude 会照着它们讲「起于速喜、转小吉」。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from xiaoliuren_cast import PALACES, cast

    names = [p["name"] for p in PALACES]
    for month, day, hb, hi in [(3, 15, "午", 6), (1, 1, "子", 0),
                               (12, 30, "亥", 11), (7, 8, "卯", 3)]:
        d = cast(month, day, hb)
        c = d["calculation"]
        mp, dp = names.index(c["month_palace"]), names.index(c["day_palace"])
        assert mp == (month - 1) % 6, (month, c["month_palace"])
        assert dp == (mp + day - 1) % 6, (month, day, c["day_palace"])
        assert names.index(d["result"]["palace"]) == (dp + hi) % 6, d
