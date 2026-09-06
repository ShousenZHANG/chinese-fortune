"""每个 CLI 入口的**失败契约**: 坏输入不许崩栈, 更不许编造答案。

前六轮审计和 903 例差分全部假定输入合法, 所以这一层从没被任何门禁碰过。实测出的
四个洞:

- ``ziwei_calc --month 2 --day 31`` 返回 ok:true 加一张凭空归一化出来的命盘
- ``zodiac_compat year --year 99999`` 崩栈, stdout 无 JSON, stderr 是带绝对路径的
  traceback
- ``qimen_cast --time 99:99`` 同样崩栈 —— "99:99" 是两个正经整数, 解析成功,
  一路走到 Solar.fromYmdHms 才炸
- ``name_analyze --name "John Smith"`` 返回 ok:true, 把 10 个拉丁字母连同空格
  逐个按默认 8 画计, 输出 总格 80(大凶)「辛苦无功, 事与愿违」

前两种失败模式对调用方 (Claude) 是等价的灾难: 从 traceback 里读不出发生了什么,
从一张编造的盘里更看不出它是编的。本文件把两者都收敛成一个信封。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")


def run(script: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# (script, argv, 一句话说明这个输入为什么不可能成立)
IMPOSSIBLE_INPUTS = [
    ('bazi_reading.py', ['--year', 1990, '--month', 2, '--day', 31, '--gender', 'male'], '无效生日'),
    ('classical_search.py', ['--passage-id', 'missing:chapter:p0001'], '未知古籍段落'),
    ("request_time.py", ["--current-timezone", "Invalid/Zone"], "不存在时区"),
    ('reading_support.py', ['--chart', 'assets/classical_evidence.json'], '证据库不是命盘'),
    ('reading_support.py', ['--chart', 'does-not-exist.json'], '输入文件不存在'),
    ('method_rules.py', ['--method', 'ziwei', '--rule', 'liuyao-support-roles'], '跨方法条款'),
    ('method_rules.py', ['--method', 'ziwei', '--rule', 'missing-rule'], '未知条款'),
    ('tiaohou_provenance.py', ['--key', '甲|X'], '不是月支'),
    ('tiaohou_provenance.py', ['--key', '甲寅'], '缺少格键分隔符'),
    ("bazi_calc.py", ["--year", 1990, "--month", 2, "--day", 31, "--hour", 10,
                      "--gender", "male"], "公历 2 月没有 31 日"),
    ("bazi_calc.py", ["--year", 1990, "--month", 13, "--day", 1, "--hour", 10,
                      "--gender", "male"], "没有 13 月"),
    ("bazi_calc.py", ["--year", 99999, "--month", 5, "--day", 10, "--hour", 10,
                      "--gender", "male"], "超出历表范围"),
    ("bazi_calc.py", ["--year", 1990, "--month", 5, "--day", 10, "--hour", 99,
                      "--gender", "male"], "没有 99 时"),
    ("ziwei_calc.py", ["--year", 1990, "--month", 2, "--day", 31, "--hour", 10,
                       "--gender", "male"], "公历 2 月没有 31 日"),
    ("ziwei_calc.py", ["--year", 1990, "--month", 5, "--day", 99, "--hour", 10,
                       "--gender", "male"], "没有 99 日"),
    ("ziwei_calc.py", ["--year", 99999, "--month", 5, "--day", 10, "--hour", 10,
                       "--gender", "male"], "超出历表范围"),
    ("zodiac_compat.py", ["year", "--year", 99999], "超出历表范围"),
    ("zodiac_compat.py", ["taisui", "--year", 1000], "超出历表范围"),
    ("zodiac_compat.py", ["info", "--zodiac", "麒麟"], "不是十二生肖"),
    ("zodiac_compat.py", ["compat", "--a", "鼠", "--b", "麒麟"], "不是十二生肖"),
    ("qimen_cast.py", ["--date", "2026-06-01", "--time", "99:99"], "没有 99 时 99 分"),
    ("qimen_cast.py", ["--date", "2026-06-01", "--time", "14:60"], "没有 60 分"),
    ("qimen_cast.py", ["--date", "2026-02-31", "--time", "14:30"], "2 月没有 31 日"),
    ("qimen_cast.py", ["--date", "notadate", "--time", "14:30"], "不是日期"),
    ("liuren_cast.py", ["--date", "2026-02-31", "--time", "14:30"], "2 月没有 31 日"),
    ("liuyao_cast.py", ["coins", "--date", "2026-02-31", "--time", "14:30"],
     "2 月没有 31 日"),
    ("huangli_query.py", ["--date", "2026-02-31"], "2 月没有 31 日"),
    ("huangli_query.py", ["--date", "notadate"], "不是日期"),
    ("xiaoliuren_cast.py", ["lunar", "--month", 13, "--day", 40,
                            "--hour-branch", "午"], "没有 13 月 40 日"),
    ("meihua_cast.py", ["--datetime", "2026-02-31T13:05", "time"], "2 月没有 31 日"),
    ("name_analyze.py", ["--name", "John Smith"], "五格按康熙笔画计, 拉丁字母无笔画"),
    ("name_analyze.py", ["--name", "王A明"], "混入非汉字"),
    ("name_analyze.py", ["--name", "阿依古丽·买买提"], "间隔号无笔画"),
    ("name_analyze.py", ["--name", "张"], "姓名至少两个字"),
]


@pytest.mark.parametrize("script,argv,why", IMPOSSIBLE_INPUTS,
                         ids=[f"{s.split('.')[0]}:{w}" for s, _, w in IMPOSSIBLE_INPUTS])
def test_impossible_input_is_refused_not_fabricated(script, argv, why):
    proc = run(script, *argv)

    assert "Traceback" not in proc.stderr, (
        f"{script} {argv} ({why}) 崩栈了 —— 调用方拿到的是 traceback 不是答案:\n"
        f"{proc.stderr[-600:]}")

    assert proc.stdout.strip(), (
        f"{script} {argv} ({why}) 什么都没输出到 stdout (rc={proc.returncode})\n"
        f"stderr={proc.stderr[-400:]}")

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"{script} {argv} ({why}) 的 stdout 不是 JSON: {exc}\n"
            f"{proc.stdout[:400]}") from exc

    assert payload.get("ok") is not True, (
        f"{script} {argv} ({why}) 返回了 ok:true —— 这是**编造**, 比崩栈更糟, "
        f"因为调用方分辨不出来:\n{json.dumps(payload, ensure_ascii=False)[:500]}")
    assert "error" in payload, f"{script} {argv}: 失败信封缺 error 键: {payload}"
    assert payload.get("message") or payload.get("expected"), (
        f"{script} {argv}: 失败信封没有任何人类可读的说明: {payload}")
    assert proc.returncode != 0, (
        f"{script} {argv}: 报了错却以 0 退出, 只看退出码的调用方会当成成功")


# 合法输入必须依旧 ok —— 否则上面的契约可以靠"一律拒绝"作弊满足。
VALID_INPUTS = [
    ('method_rules.py', ['--method', 'ziwei']),
    ('tiaohou_provenance.py', ['--key', '甲|寅']),
    ("bazi_calc.py", ["--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
                      "--gender", "male"]),
    ("ziwei_calc.py", ["--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
                       "--gender", "male"]),
    ("zodiac_compat.py", ["year", "--year", 2026]),
    ("zodiac_compat.py", ["taisui", "--year", 2026]),
    ("qimen_cast.py", ["--date", "2026-06-01", "--time", "14:30"]),
    ("huangli_query.py", ["--date", "2026-06-01"]),
    ("name_analyze.py", ["--name", "张子涵"]),
    ("name_analyze.py", ["--name", "李小龍"]),          # 繁体必须照收
    ("meihua_cast.py", ["--datetime", "2026-06-01T13:05", "time"]),
]


@pytest.mark.parametrize("script,argv", VALID_INPUTS,
                         ids=[s.split(".")[0] + ":" + str(i)
                              for i, (s, _) in enumerate(VALID_INPUTS)])
def test_valid_input_still_succeeds(script, argv):
    """防止上面那组契约被『一律拒绝』这种作弊实现满足。"""
    proc = run(script, *argv)
    assert proc.returncode == 0, f"{script} {argv} rc={proc.returncode}\n{proc.stderr[-400:]}"
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True, payload


def test_every_engine_entry_point_is_covered_by_the_contract():
    """新增一个引擎却不给它写契约用例, 这里会红 —— 否则这份清单会慢慢过期。"""
    import ast
    entry_points = set()
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name in ("utils.py", "build_skill.py", "import_classics.py"):
            # import_classics is a maintenance importer, excluded from the runtime package.
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        has_main = any(isinstance(n, ast.FunctionDef) and n.name == "main"
                       for n in tree.body)
        if has_main:
            entry_points.add(f.name)

    covered = {s for s, _, _ in IMPOSSIBLE_INPUTS}
    # 这些没有任何日期/数值边界可越 —— 输入是自由文本或纯随机, 故不在契约清单里。
    exempt = {
        "tarot_draw.py",        # 只有 --seed/--question
        "jiemeng_lookup.py",    # 自由文本查词
        "yijing_cast.py",       # --datetime 由 argparse type= 兜住
        "lunar_convert.py",     # 同上
        "explore_cast.py",      # 同上
        "liuren_cast.py",       # 已在清单里 (下面断言会确认)
    }
    missing = entry_points - covered - exempt
    assert not missing, (
        f"这些引擎入口没有失败契约用例: {sorted(missing)}。"
        "加两条 IMPOSSIBLE_INPUTS (一条越界、一条格式错) 再提交。")


def test_no_engine_hand_rolls_an_error_envelope():
    """失败信封必须一律走 utils.error_envelope。

    utils.py 明写「ok/tool/version/error/message 五个键恒定存在, 调用方可无条件
    读取」, 而 bazi_calc 手搓了 7 处, 其中 unknown_city 与 invalid_timezone 两条
    **漏掉 version 键** —— 契约当场破在自己的旗舰引擎里。逐个跑不可能输入只能碰到
    走到的那几条分支, 所以这里改为静态扫描源码。
    """
    import ast
    offenders = []
    for f in sorted((ROOT / "scripts").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", None) == "json_print"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Dict):
                continue                      # 走的是 error_envelope/ok_envelope
            keys = {k.value for k in node.args[0].keys
                    if isinstance(k, ast.Constant)}
            if "error" not in keys:
                continue                      # 成功载荷, 由 ok_envelope 管
            missing = {"ok", "tool", "version", "error", "message"} - keys
            if missing:
                offenders.append(f"{f.name}:{node.lineno} 缺 {sorted(missing)}")
    assert not offenders, (
        "这些失败信封是手搓的且不完整 —— 应改用 utils.error_envelope(): "
        + str(offenders))
