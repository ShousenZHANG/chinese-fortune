"""The release harness must fail loudly, never vacuously.

evals/run_checks.py is the release gate, but nothing tested the gate itself.
These cover the failure paths: a gate that silently degrades to "nothing to
check" is worse than no gate, because it reports PASS.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

import run_checks  # noqa: E402  # isort: skip


# --------------------------------------------------------------------------- #
# check_release_cleanliness — the committed-.pyc gate must not degrade to a
# loop over an empty list when git is unavailable
# --------------------------------------------------------------------------- #

def test_cleanliness_fails_when_git_ls_files_fails(monkeypatch):
    """A non-zero `git ls-files` must fail the check, not empty the list."""
    def fake_run(*a, **kw):
        return subprocess.CompletedProcess(
            args=a[0] if a else [], returncode=128,
            stdout="", stderr="fatal: not a git repository")

    monkeypatch.setattr(run_checks.subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="git ls-files"):
        run_checks.check_release_cleanliness()


def test_cleanliness_fails_when_git_missing(monkeypatch):
    """An OSError (git not on PATH) must also fail loudly."""
    def boom(*a, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(run_checks.subprocess, "run", boom)
    with pytest.raises(AssertionError, match="git ls-files"):
        run_checks.check_release_cleanliness()


# --------------------------------------------------------------------------- #
# check_interpretive_discipline — both files must be locked symmetrically
# --------------------------------------------------------------------------- #

FIVE_CLASSICS = ["子平真诠", "滴天髓", "穷通宝鉴", "三命通会", "渊海子平"]


def test_agent_discipline_needles_cover_all_five_classics():
    """agents/openai.yaml was guarded by a single substring, so four of the
    five classics and both discipline clauses could be stripped with the gate
    still green. The needle list must be symmetric with SKILL.md's."""
    needles = run_checks.AGENT_DISCIPLINE_NEEDLES
    for classic in FIVE_CLASSICS:
        assert classic in needles, f"agent lock missing classic: {classic}"
    assert any("古籍无据" in n for n in needles), "agent lock missing 不妄断 clause"


def test_agent_discipline_actually_fails_on_a_missing_classic(monkeypatch):
    """Not just the constant — the check must act on it."""
    real = Path.read_text

    def stripped(self, *a, **kw):
        text = real(self, *a, **kw)
        if self.name == "openai.yaml":
            return text.replace("滴天髓", "")
        return text

    monkeypatch.setattr(Path, "read_text", stripped)
    with pytest.raises(AssertionError, match="滴天髓"):
        run_checks.check_interpretive_discipline()


# --------------------------------------------------------------------------- #
# check_unit_tests — the failure path itself must not crash
# --------------------------------------------------------------------------- #

def test_unit_test_failure_reports_output_instead_of_crashing(monkeypatch):
    """pytest failing used to raise TypeError inside the harness: stdout was
    None after a decode error, so the gate reported its own stack trace rather
    than the test failure."""
    def fake_run(*a, **kw):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout=None)

    monkeypatch.setattr(run_checks.subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="pytest failed"):
        run_checks.check_unit_tests()


# --------------------------------------------------------------------------- #
# eval assertions must be able to tell a correct asset from a truncated one
# --------------------------------------------------------------------------- #

def test_jiemeng_eval_asserts_structure_not_one_character():
    """eval #7's only needle was 蛇 — a single CJK character in a 38 KB file,
    which cannot distinguish a correct dream dictionary from a broken one."""
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    ev = next(e for e in spec["evals"] if e["id"] == 7)
    needles = [n for a in ev["assertions"] for n in a.get("needles", [])]
    assert len(needles) >= 3, f"eval #7 still thin: {needles}"
    assert "traditional" in needles and "modern_psychology" in needles, (
        "must assert the dual-reading structure the eval's expected_output promises"
    )


def test_qimen_school_note_is_locked():
    """The 三元 honesty note added in v1.3.0 carried no invariant lock, unlike
    every other honesty text in the project."""
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    needles = [
        n for e in spec["evals"] for a in e.get("assertions", [])
        if a.get("file", "").endswith("06-qimen.md") for n in a.get("needles", [])
    ]
    assert "拆补置闰" in needles, "qimen 流派注 unlocked"


# --------------------------------------------------------------------------- #
# 渐进式披露的可达性 — 搬走的内容必须仍能被路由到
# --------------------------------------------------------------------------- #

PERSONAL_DATA_REFS = ["01-bazi.md", "02-ziwei.md", "12-huangli.md",
                      "13-qiming.md", "14-hehun.md"]


def test_intake_reachable_from_every_personal_data_route():
    """00-intake.md holds the collection protocol, the 边界情形 table and the
    step-9 在世状态 ethics check. Moving it out of SKILL.md only works if every
    method that needs birth data still routes to it."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert (ROOT / "references" / "00-intake.md").exists()
    for line in skill.splitlines():
        if any(ref in line for ref in PERSONAL_DATA_REFS) and line.startswith("|"):
            assert "00-intake.md" in line, f"route misses intake: {line[:70]}"


def test_moved_reference_files_all_exist_and_are_linked():
    """Every references/*.md must be reachable from SKILL.md or from another
    reference — an unreachable file is dead weight that progressive disclosure
    can never surface."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = sorted((ROOT / "references").glob("*.md"))
    corpus = skill + "".join(
        f.read_text(encoding="utf-8") for f in refs)
    for f in refs:
        assert corpus.count(f.name) >= 2, f"{f.name} is unreachable (only self-reference)"


def test_every_asset_is_reachable_from_a_script():
    """assets/*.json are consumed by scripts, never opened by Claude, so an
    asset no script reads is unreachable data.

    Moving the SKILL.md asset table out silently orphaned jiemeng.json until
    jiemeng_lookup.py was added — this test is what should have caught it.
    """
    scripts = "".join(
        f.read_text(encoding="utf-8") for f in (ROOT / "scripts").glob("*.py"))
    orphans = [f.name for f in sorted((ROOT / "assets").glob("*.json"))
               if f.name not in scripts]
    assert not orphans, f"assets no script reads: {orphans}"


def test_no_script_exceeds_the_size_limit():
    """The project's own limit is 200-400 lines typical, 800 max. bazi_calc was
    2.1x that and ziwei_calc 1.3x before the v1.5.1 split; keep them there."""
    oversize = {
        f.name: sum(1 for _ in f.open(encoding="utf-8"))
        for f in sorted((ROOT / "scripts").glob("*.py"))
        if sum(1 for _ in f.open(encoding="utf-8")) > 800
    }
    assert not oversize, f"scripts over the 800-line maximum: {oversize}"


def test_interpretive_discipline_names_an_anchor_for_every_scripted_method():
    """解读纪律 says it governs 所有方法 but named canons for only 八字/周易/紫微.
    An evaluation agent doing a tarot reading reported the rule as inoperative
    there — tarot has no 古籍, and pretending otherwise would itself breach
    凡古籍无据者不妄断. Every method with an engine must be named, and the two
    that genuinely have no Chinese canon must say so rather than be omitted.
    """
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    block = skill.split("## 解读纪律")[1].split("\n## ")[0]
    for method in ["周易", "紫微", "六爻", "梅花", "奇门", "六壬", "黄历"]:
        assert method in block, f"解读纪律 names no anchor for {method}"
    # the two without a Chinese canon must be named AND labelled as such
    assert "塔罗" in block and "姓名" in block
    assert "无古籍" in block or "非中土古籍" in block or "无中土古籍" in block


def test_contains_assertion_accepts_non_string_values(monkeypatch):
    """`contains` did `substr not in str(got)`, which raises TypeError the
    moment an eval pins a numeric field (hex_number, a score, a count). The
    gate crashed instead of comparing, so numeric goldens were unusable."""
    run_checks._run_assertion(
        {"kind": "file_contains", "file": "CHANGELOG.md", "needles": ["1.7.0"]},
        "self-test")
    got = {"n": 33, "s": "天山遁"}
    assert run_checks._contains_ok(got, "n", 33)
    assert run_checks._contains_ok(got, "n", "33")
    assert run_checks._contains_ok(got, "s", "天山")
    assert not run_checks._contains_ok(got, "n", 34)


def test_every_cli_engine_has_a_release_eval():
    """The harness is the release gate, but six of fifteen CLIs never ran in
    it — 六爻, 大六壬, 小六壬, 解梦, 历法换算 and 探索. liuyao is the pointed
    example: its hexagram naming was wrong on 48 of 64 hexagrams until v1.4.0
    and no eval would have caught it."""
    import os
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    covered = {
        os.path.basename(a["cmd"][0])
        for e in spec["evals"] for a in e.get("assertions", [])
        if a.get("kind") == "script" and a.get("cmd")
    }
    # 「哪些是 CLI」由结构判定, 不再手维护名单: 定义了 main() 的才是入口。
    # 从前这里是一个硬编码的 helpers 集合, 每拆一次表就得记得往里加一个名字 ——
    # qimen_tables.py 拆出来时就漏了, 门禁于是报「这个库模块没有发布 eval」。
    import ast
    build_only = {"build_skill.py"}      # 打包器, 不是占卜引擎
    clis = set()
    for f in (ROOT / "scripts").glob("*.py"):
        if f.name in build_only:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        if any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body):
            clis.add(f.name)
    assert len(clis) >= 14, f"入口识别异常, 只找到 {sorted(clis)}"
    missing = sorted(clis - covered)
    assert not missing, f"CLIs with no release eval: {missing}"


def test_harness_reports_a_timeout_as_a_failed_check_not_a_traceback():
    """main() only caught AssertionError. subprocess.TimeoutExpired is not one,
    so a slow pytest ended the harness with a bare traceback *before any check
    reported*: no per-check verdict, no "x/7" line, and the checks after it
    never ran. The gate's own contract ("7/7") did not hold on that path.

    The margin was real, not theoretical: the timeout was 180s while the suite
    had grown from 1013 to 2150 tests and now includes a 58,440-day sxtwl sweep.
    """
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "evals"))
    import run_checks

    assert run_checks.UNIT_TEST_TIMEOUT_S >= 600, run_checks.UNIT_TEST_TIMEOUT_S

    def boom():
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    after_ran = []

    def later():
        after_ran.append(True)

    boom.__name__, later.__name__ = "check_boom", "check_later"
    results = []
    for check in (boom, later):
        try:
            check()
            results.append((check.__name__, True, ""))
        except AssertionError as exc:
            results.append((check.__name__, False, str(exc)))
        except subprocess.TimeoutExpired as exc:
            results.append((check.__name__, False, f"timed out after {exc.timeout}s"))

    assert results[0] == ("check_boom", False, "timed out after 1s")
    assert after_ran == [True], "checks after a timeout must still run"

    # 上面复刻的是 main() 的循环; 确认 main() 真的带了这个 except 分支。
    src = (root / "evals" / "run_checks.py").read_text(encoding="utf-8")
    assert "except subprocess.TimeoutExpired" in src


def test_mutation_gate_is_wired_and_fails_on_a_survivor():
    """变异门禁本身必须会红。

    这道门禁的价值全在「有存活就失败」这一条上; 如果它只是跑一遍就放行, 那和没有
    一样。这里检查两件事: (a) 它确实进了 checks 清单; (b) mutate.py 在有存活时
    退出码非 0 —— 用一个必然存活的假变异 (改注释) 实测。
    """
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "evals"))
    import mutate
    import run_checks

    src = (root / "evals" / "run_checks.py").read_text(encoding="utf-8")
    assert "check_mutation_score," in src, "变异门禁没进 checks 清单"
    assert run_checks.MUTATION_TIMEOUT_S >= 900

    # 每处变异都必须写明「这个值错了用户会看到什么」, 否则存活清单读不出轻重。
    assert len(mutate.MUTATIONS) >= 10
    for m in mutate.MUTATIONS:
        assert len(m.why) > 15, f"{m.name} 的 why 太空泛: {m.why!r}"
        assert (root / m.path).exists(), f"{m.name} 指向不存在的文件 {m.path}"

    # 一个必然存活的假变异: 只改注释, 任何测试都不会红。
    probe = root / "evals" / "_mutate_probe.py"
    probe.write_text(
        "from mutate import Mutation, main\n"
        "import mutate\n"
        "mutate.MUTATIONS = [Mutation('probe:注释', 'scripts/utils.py',\n"
        "    '# --------------------------------------------------------------------------- #',\n"
        "    '# ---- probe ---- #', 'a comment-only change nothing can catch',\n"
        "    ['tests/test_utils.py'])]\n"
        "raise SystemExit(main([]))\n",
        encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(probe)],
            cwd=root / "evals", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        if "另一个 mutate.py 正在运行" in proc.stderr:
            # 真的有一轮变异在跑 (例如后台的 run_checks)。锁正确挡住了我们 ——
            # 这本身就是并发保护生效的证据, 但这次探针跑不成, 跳过。
            pytest.skip("mutate.py 被另一进程占用, 探针无法运行 (锁生效中)")
        assert proc.returncode != 0, (
            "必然存活的变异没有让 mutate.py 失败 —— 门禁是摆设\n" + proc.stdout[-500:])
        assert "SURVIVED" in proc.stdout
    finally:
        probe.unlink(missing_ok=True)

    # 探针跑完后工作树必须干净 —— mutate.py 的 finally 还原必须可靠。
    st = subprocess.run(["git", "status", "--short"], cwd=root,
                        capture_output=True, text=True, encoding="utf-8")
    assert "scripts/utils.py" not in st.stdout, (
        "变异后没有还原 scripts/utils.py:\n" + st.stdout)


def test_version_is_consistent_across_all_four_sources():
    """版本有四个来源: scripts/utils.py 的常量、CHANGELOG 的最新条目、git tag、
    dist 里的 zip 文件名。从前没有任何门禁把它们绑在一起 —— 而历史记录显示这个
    流程已经实际失效过 8 次: CHANGELOG 有 22 个版本条目, git tag 只有 16 个,
    1.1.1/1.1.2/1.1.4/1.1.5/1.1.6/1.1.8/1.2.0 七个从未打 tag, 而 tag v1.1.7
    在 CHANGELOG 里根本不存在。

    本测试只管**当前**版本的一致性 —— 历史断裂已在 CHANGELOG 里如实记明,
    不追溯补 tag (那会改写发布史)。
    """
    import re
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from utils import __version__ as code_version

    cl = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = re.search(r"^## \[([0-9.]+)\]", cl, re.M).group(1)
    assert latest == code_version, (
        f"CHANGELOG 最新条目 {latest} != scripts/utils.py 的 {code_version}")

    tags = subprocess.run(["git", "tag", "-l"], cwd=root,
                          capture_output=True, text=True).stdout.split()
    if tags:                       # 浅 clone / 无 tag 的 CI 环境跳过
        assert f"v{code_version}" in tags, (
            f"当前版本 {code_version} 没有对应的 git tag v{code_version}")


def test_changelog_and_tags_drift_is_recorded_not_silent():
    """CHANGELOG 与 tag 的历史断裂必须写在 CHANGELOG 里, 而不是只存在于
    「谁去比对过才知道」的状态。
    """
    import re
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    cl = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    entries = set(re.findall(r"^## \[([0-9.]+)\]", cl, re.M))
    tags = {t.lstrip("v") for t in
            subprocess.run(["git", "tag", "-l"], cwd=root,
                           capture_output=True, text=True).stdout.split()}
    if not tags:
        return
    untagged = entries - tags
    if untagged:
        assert "未打 tag" in cl or "无 tag" in cl, (
            f"这些 CHANGELOG 版本没有 tag 却也没在文件里说明: {sorted(untagged)}")


def test_contributing_lists_every_ci_gate():
    """贡献者文档只写了 run_checks.py 一道; ruff / mypy / coverage 三道 CI 门
    全文零提及 —— 照文档走完的贡献者能复现 6 道 CI 门里的 1 道。
    COVERAGE_PROCESS_START 同样只在 ci.yml/pyproject 里出现, 而不带它跑
    `pytest --cov=scripts` 得 29.9%, 直接触发 fail_under 80 报红。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    doc = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for gate in ("ruff", "mypy", "pytest", "COVERAGE_PROCESS_START",
                 "run_checks", "mutate"):
        assert gate in doc, f"CONTRIBUTING 未提及 CI 门 {gate}"


def test_contributing_does_not_contradict_the_shipped_contract():
    """两处矛盾, 三份文件都在发布包里:
    - PR checklist 要求「加新脚本: 依赖缺失时优雅降级」, 而 SKILL.md:118 明写
      lunar_python is REQUIRED, scripts exit 1, there is no table fallback。
      照 checklist 写降级逻辑会直接违反发布文档承诺的行为契约。
    - 声称支持 Python 3.10+, 而 ci.yml 矩阵是 3.11/3.12, pyproject 的
      target-version 与 mypy python_version 都是 3.11 —— 声明的支持下限既没测过,
      又被 ruff 的 UP 规则反向推着走。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    doc = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "优雅降级" not in doc or "lunar_python` 除外" in doc, (
        "checklist 仍要求依赖缺失时优雅降级, 与 SKILL.md 的 REQUIRED 契约矛盾")
    assert "3.10+" not in doc, (
        "仍声称支持 3.10, 而 CI 矩阵与 pyproject 都是 3.11+")


def test_evals_do_not_pin_the_timezone_less_longitude_path():
    """evals 是「黄金基准」—— 把一条错误的调用方式钉进去, 等于把它变成标准。

    eval#1 的 prompt 明写「出生在北京」(--city 北京 可直接解析), 而 assertion 的
    cmd 用 --longitude 116.4 且不带 --timezone。生日 1990-05-10 正落在
    00-intake.md:38 点名的 1986-1991 夏令时窗口内: --city 北京 得真太阳时 13:19,
    --longitude 无 tz 得 14:19 —— 整整差一小时。即使有人照 00-intake.md 修正了
    SKILL.md 的示例, 这条 eval 仍会把旧路径锁死。
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = json.loads((root / "evals" / "evals.json").read_text(encoding="utf-8"))
    offenders = []
    for e in spec.get("evals", spec):
        for a in e.get("assertions", []):
            cmd = a.get("cmd") or []
            if not cmd or a.get("kind") != "script":
                continue
            if "--longitude" in cmd and "--timezone" not in cmd and "--city" not in cmd:
                offenders.append((e.get("id"), " ".join(map(str, cmd))))
    assert not offenders, (
        "这些 eval 用 --longitude 而不给 --timezone/--city, 会漏掉历史夏令时, "
        f"却被当成黄金基准: {offenders}")


def test_intake_declares_how_personal_data_is_handled():
    """00-intake.md 是一份九项个人信息的采集协议 (姓名、生日、时辰、出生地、
    现居地、关心议题含健康与财务、在世状态), 而全库此前没有任何一句数据处理声明
    —— grep 隐私/privacy/保存/删除/数据保留 在 references + SKILL.md + README +
    CONTRIBUTING 里零命中。

    好消息是实现本身是干净的: scripts/ 与 evals/ 零文件写入, 生辰从不落盘。
    但「事实上不保存」和「告诉用户不保存」是两件事, 而且还有一个真实的暴露通道:
    所有数据以命令行参数传入, 会出现在 ps / 任务管理器 与 shell 历史里。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    md = (root / "references" / "00-intake.md").read_text(encoding="utf-8")
    assert "数据处理声明" in md
    assert "不落盘" in md or "零文件写入" in md
    assert "对话记录" in md, "必须说明 skill 管不到宿主对话的留存"
    assert "命令行" in md and ("ps" in md or "进程列表" in md), (
        "必须提到命令行参数会出现在进程列表与 shell 历史里")


def test_engines_really_do_not_write_files():
    """上一条声明的事实基础 —— 引擎确实不落盘。声明与实现必须一起被守住,
    否则哪天有人加了个缓存, 声明就变成了假话。
    """
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    writers = []
    for f in sorted((root / "scripts").glob("*.py")):
        if f.name == "build_skill.py":       # 打包器, 本来就要写文件
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name in ("write_text", "write_bytes", "mkdir", "makedirs"):
                    writers.append(f"{f.name}:{node.lineno} {name}")
                if name == "open":
                    for a in list(node.args[1:2]) + [k.value for k in node.keywords
                                                     if k.arg == "mode"]:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                                and any(c in a.value for c in "wax+"):
                            writers.append(f"{f.name}:{node.lineno} open({a.value!r})")
    assert not writers, (
        "这些引擎会写文件, 与 00-intake.md 的「不落盘」声明矛盾: " + str(writers))
