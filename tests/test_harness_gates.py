"""Unique release protections run under pytest, not a second test runner.

CLI failure envelopes live in test_cli_contract; package installation lives in
package_smoke. Source completeness and archive bytes have dedicated tests.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_no_generated_python_cache_is_tracked():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", check=True, timeout=15)
    assert not [p for p in result.stdout.split("\0") if p.endswith(".pyc") or "__pycache__" in p]


def _script_assertions():
    spec = json.loads((ROOT / "evals/evals.json").read_text(encoding="utf-8"))
    return [(f"eval-{case['id']}-{index}", assertion) for case in spec["evals"]
            for index, assertion in enumerate(case["assertions"]) if assertion["kind"] == "script"]


def _resolve(data, dotted):
    for part in dotted.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


@pytest.mark.parametrize("case_id,assertion", _script_assertions(), ids=lambda value: value if isinstance(value, str) else None)
def test_cli_release_examples(case_id, assertion):
    """Migrated deterministic goldens: each command executes once under pytest."""
    proc = subprocess.run([sys.executable, "-X", "utf8", *assertion["cmd"]], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, (case_id, proc.stdout[-1000:], proc.stderr[-1000:])
    data = json.loads(proc.stdout)
    assert data.get("ok") is not False and not data.get("error")
    for path, value in assertion.get("paths", {}).items():
        assert _resolve(data, path) == value, (case_id, path)
    for path, value in assertion.get("contains", {}).items():
        assert str(value) in str(_resolve(data, path)), (case_id, path)
    for path in assertion.get("has_keys", []):
        _resolve(data, path)
    for path, count in assertion.get("count", {}).items():
        assert isinstance(_resolve(data, path), list) and len(_resolve(data, path)) == count


def test_moved_reference_files_all_exist_and_are_linked():
    """每个 references/*.md 都必须从 SKILL.md **可达** —— 顺着链接走得到。

    旧断言是 `corpus.count(name) >= 2`, 而一条 markdown 链接
    `[X.md](references/X.md)` 本身就贡献 2 次出现 —— 一个只链接自己的孤儿文件
    计数就是 2, 直接 PASS, 而函数 docstring 恰恰声称能抓 "only self-reference"。
    它也从不要求「从 SKILL.md 出发」: 两个互相链接的孤岛同样满分。

    改为真的走链接图: 从 SKILL.md 出发做 BFS, 未被访问到的即不可达。
    """
    import re
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = {f.name: f.read_text(encoding="utf-8")
            for f in sorted((ROOT / "references").glob("*.md"))}

    def links_in(text: str) -> set:
        # 只认真正的 markdown 链接目标, 不认正文里顺口提到的文件名
        return {m.split("/")[-1] for m in
                re.findall(r"\]\(([^)]*?\.md)\)", text)} & set(refs)

    seen: set = set()
    frontier = links_in(skill_text)
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        frontier |= links_in(refs[cur]) - seen

    unreachable = sorted(set(refs) - seen)
    assert not unreachable, (
        f"这些 reference 从 SKILL.md 顺着链接走不到, 渐进披露永远呈现不了: "
        f"{unreachable}")


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
    if not tags:                   # 浅 clone / 无 tag 的 CI 环境
        return

    def key(v: str) -> tuple:
        return tuple(int(x) for x in v.lstrip("v").split("."))

    if f"v{code_version}" in tags:
        return
    # 「改版本号」这一步合法地先于「打 tag」。待发布状态的判据是: 当前版本严格
    # 大于已有的每一个 tag。若它小于或等于某个 tag, 那就是真的漏打了。
    newest = max((key(x) for x in tags if x.startswith("v")), default=(0,))
    assert key(code_version) > newest, (
        f"版本 {code_version} 既没有 tag, 又不比已有的最新 tag "
        f"{'.'.join(map(str, newest))} 新 —— 这是漏打 tag, 不是待发布")


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
        if f.name in ("build_skill.py", "import_classics.py"):  # 构建与古籍采集需写文件
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


def test_ci_does_not_cancel_main_branch_runs():
    """cancel-in-progress 同时作用于 push:main 时, 连推两个 commit 会取消前一个的
    CI —— 而发布 tag 恰恰打在这类 commit 上, 那次运行的结果就永远没有了。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    line = next((ln for ln in ci.splitlines() if "cancel-in-progress" in ln), "")
    assert line, "ci.yml 没有 concurrency 设置"
    assert "pull_request" in line, (
        f"cancel-in-progress 无条件为真, push:main 的运行会被后一次推送取消: {line}")


def test_actions_are_pinned_and_dependency_pr_creation_is_paused():
    """Main-only maintenance must not silently change Actions or recreate bot branches."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    ci = (root / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    actions = re.findall(r'uses:\s+([^\s#]+)', ci)
    assert actions and all(re.fullmatch(r'[\w.-]+/[\w.-]+@[0-9a-f]{40}', a) for a in actions)
    dep = root / ".github" / "dependabot.yml"
    assert dep.exists()
    text = dep.read_text(encoding="utf-8")
    blocks = text.split('- package-ecosystem:')[1:]
    assert {block.splitlines()[0].strip() for block in blocks} == {'github-actions', 'pip'}
    assert all(re.search(r'^\s+open-pull-requests-limit:\s*0\s*$', block, re.M) for block in blocks)


def test_ci_coverage_does_not_override_the_config_source():
    """裸 `--cov` 才用 [tool.coverage.run] 的 source; `--cov=scripts` 会覆盖它。

    9e2191d 把 source 改成 ["scripts","evals"] 并在提交标题宣称「覆盖率含发布
    链路」, 而 ci.yml 跑的是 --cov=scripts —— 改动在 CI 里完全空转, 分母
    3303 vs 3595 (差 292 条 evals 语句), fail_under=80 对 发布工具没有约束。CHANGELOG 里「86.6%, 分母现含发布链路代码」当时也是错的。
    """
    import re
    import tomllib
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    # 只看真正的 run: 行, 不看解释这条规则的注释本身
    cov_lines = [ln for ln in ci.splitlines()
                 if "--cov" in ln and not ln.strip().startswith("#")]
    assert cov_lines, "ci.yml 没有覆盖率步骤"
    for ln in cov_lines:
        assert not re.search(r"--cov=\S", ln), (
            f"--cov=<值> 会覆盖 config 的 source, 使 pyproject 的设置失效: {ln.strip()}")

    cfg = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    src = cfg["tool"]["coverage"]["run"]["source"]
    assert "evals" in src, (
        "仍保留的发布工具必须在覆盖率分母里 —— "
        "它们决定发什么货")
