"""Validation checks for the chinese-fortune skill.

Run from the repository root:
    python -X utf8 chinese-fortune/evals/run_checks.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        fail("SKILL.md must start with YAML frontmatter")
    try:
        _, body, _ = text.split("---", 2)
    except ValueError as exc:
        raise AssertionError("SKILL.md frontmatter is not closed") from exc

    parsed: dict[str, str] = {}
    for line in body.strip().splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


MUTATION_TIMEOUT_S = 1800


def check_skill_metadata() -> None:
    skill_md = ROOT / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    meta = parse_frontmatter(content)
    if set(meta) != {"name", "description"}:
        fail(f"frontmatter keys must be name+description only, got {sorted(meta)}")
    if meta["name"] != "chinese-fortune":
        fail("skill name must be chinese-fortune")
    if len(meta["description"]) > 1024:
        fail(f"description too long: {len(meta['description'])} > 1024")
    for needle in ["算命", "八字", "紫微", "周易", "六爻", "奇门", "风水", "择日", "起名"]:
        if needle not in meta["description"]:
            fail(f"description missing trigger: {needle}")


def run_json(args: list[str]) -> dict:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        fail(
            f"{args[0]} exited {completed.returncode}\n"
            f"stdout={completed.stdout[:500]}\nstderr={completed.stderr[:500]}"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{args[0]} did not emit JSON: {completed.stdout[:500]}") from exc
    if isinstance(parsed, dict) and parsed.get("error"):
        fail(f"{args[0]} returned error JSON: {parsed}")
    return parsed


def check_core_scripts() -> None:
    cases = [
        ["scripts/yijing_cast.py", "coins", "--seed", "42", "--question", "测试"],
        ["scripts/meihua_cast.py", "numbers", "--upper", "3", "--lower", "5", "--question", "测试"],
        ["scripts/tarot_draw.py", "three", "--seed", "42", "--question", "测试"],
        ["scripts/name_analyze.py", "--name", "张子涵"],
        ["scripts/zodiac_compat.py", "compat", "--a", "虎", "--b", "猴"],
        ["scripts/lunar_convert.py", "solar2lunar", "--year", "1990", "--month", "5", "--day", "10"],
        [
            "scripts/bazi_calc.py",
            "--year",
            "1990",
            "--month",
            "5",
            "--day",
            "10",
            "--hour",
            "14",
            "--gender",
            "male",
            "--longitude",
            "116.4",
        ],
        ["scripts/huangli_query.py", "--date", "2026-06-01"],
        ["scripts/liuyao_cast.py", "coins", "--seed", "42", "--date", "2026-06-01", "--time", "10:00"],
        ["scripts/ziwei_calc.py", "--year", "1995", "--month", "7", "--day", "20", "--hour", "1", "--gender", "female", "--lunar"],
        ["scripts/xiaoliuren_cast.py", "lunar", "--month", "3", "--day", "15", "--hour-branch", "午"],
        ["scripts/qimen_cast.py", "--date", "2026-05-16", "--time", "14:30"],
        ["scripts/liuren_cast.py", "--date", "2026-05-16", "--time", "14:30", "--question", "感情"],
        ["scripts/liuren_cast.py", "--date", "2026-12-25", "--time", "03:00"],
        ["scripts/liuren_cast.py", "--date", "2026-03-01", "--time", "11:30", "--question", "出行"],
    ]
    for case in cases:
        run_json(case)


def check_reference_coverage() -> None:
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    required_refs = [
        "00-foundations.md",
        "01-bazi.md",
        "02-ziwei.md",
        "03-yijing.md",
        "04-liuyao.md",
        "05-meihua.md",
        "06-qimen.md",
        "07-daliuren.md",
        "08-fengshui.md",
        "12-huangli.md",
        "13-qiming.md",
        "21-extended-methods.md",
    ]
    for ref in required_refs:
        if ref not in skill_text:
            fail(f"SKILL.md does not route to {ref}")
        if not (ROOT / "references" / ref).exists():
            fail(f"missing reference file: {ref}")


FIVE_CLASSICS = ["子平真诠", "滴天髓", "穷通宝鉴", "三命通会", "渊海子平"]

SKILL_DISCIPLINE_NEEDLES = [
    "解读纪律",
    *FIVE_CLASSICS,
    "凡古籍无据者不妄断",
    "禁止套话和迎合",
    "可验证性最高",
]

# Kept symmetric with SKILL.md's list on purpose: guarding openai.yaml with a
# single substring let four of the five classics and both discipline clauses
# be stripped while this gate still reported PASS.
AGENT_DISCIPLINE_NEEDLES = [*FIVE_CLASSICS, "凡古籍无据者不妄断"]


def check_interpretive_discipline() -> None:
    """SKILL.md and agents/openai.yaml must carry the classical-source
    interpretive discipline: judgments anchored in the five classics, no
    unsupported claims, no platitudes/flattery, strongest evidence only."""
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for needle in SKILL_DISCIPLINE_NEEDLES:
        if needle not in skill_text:
            fail(f"SKILL.md missing interpretive-discipline element: {needle!r}")
    agent_text = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for needle in AGENT_DISCIPLINE_NEEDLES:
        if needle not in agent_text:
            fail(f"agents/openai.yaml missing interpretive-discipline element: {needle!r}")


def check_mutation_score() -> None:
    """测试套件必须**抓得到 bug**, 而不只是数量多。

    两轮独立审计各自实测出同一件事: 把关键常量或判断标签改坏, 2100+ 条测试照样
    全绿, 存活率 77%。覆盖率对此无感 —— liuyao_cast 行覆盖 88.8%, 却没有任何
    断言检查排出来的爻装了什么。

    evals/mutate.py 施加一组人为缺陷 (每处都注明「这个值错了用户会看到什么」),
    逐一确认套件会红。零存活是门禁条件: 存活即意味着该类缺陷能进主干而无人察觉。
    """
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "evals" / "mutate.py")],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=MUTATION_TIMEOUT_S,
    )
    if proc.returncode != 0:
        output = (proc.stdout or "")[-2000:] or "(no output captured)"
        fail("变异测试有存活项 (这些缺陷能进主干而无人察觉):\n" + output)


def check_release_cleanliness() -> None:
    forbidden = re.compile(r"\b(TODO|TBD|placeholder|not implemented)\b", re.IGNORECASE)
    for path in [ROOT / "SKILL.md", *sorted((ROOT / "scripts").glob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        match = forbidden.search(text)
        if match:
            fail(f"release marker {match.group(0)!r} left in {path.relative_to(ROOT)}")
    # Only TRACKED generated artifacts are a problem; gitignored runtime
    # __pycache__/*.pyc regenerate on every import and must not fail the suite.
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8",
            errors="replace", capture_output=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"git ls-files could not run, so tracked .pyc files cannot be "
             f"verified: {exc}")
    if proc.returncode != 0:
        fail(f"git ls-files failed (rc={proc.returncode}), so tracked .pyc "
             f"files cannot be verified: {(proc.stderr or '')[:200]}")
    tracked = (proc.stdout or "").splitlines()
    committed_cache = [p for p in tracked if p.endswith(".pyc") or "__pycache__" in p]
    if committed_cache:
        fail(f"generated Python cache files committed: {committed_cache}")


# --------------------------------------------------------------------------- #
# Eval assertions — machine-verify the deterministic substrate
# --------------------------------------------------------------------------- #

_MISSING = object()


def _resolve_path(obj, dotted: str):
    """Resolve 'a.b.0.c' against nested dict/list; return _MISSING if absent."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        elif isinstance(cur, dict):
            if part not in cur:
                return _MISSING
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _contains_ok(data, path: str, substr) -> bool:
    """Substring match that tolerates a non-string needle or value.

    An eval pinning a numeric field (hex_number, a count, a score) used to
    crash the gate with TypeError, because `substr not in str(got)` requires a
    string on the left. Coerce both sides: the assertion is "the rendered value
    contains the rendered needle".
    """
    got = _resolve_path(data, path)
    if got is _MISSING:
        return False
    return str(substr) in str(got)


def _run_assertion(a: dict, label: str) -> None:
    kind = a.get("kind")
    if kind == "file_contains":
        path = ROOT / a["file"]
        if not path.exists():
            fail(f"{label}: file_contains target missing: {a['file']}")
        text = path.read_text(encoding="utf-8")
        for needle in a["needles"]:
            if needle not in text:
                fail(f"{label}: {a['file']} missing required text {needle!r}")
        return
    if kind == "script":
        data = run_json(a["cmd"])
        for path, expected in a.get("paths", {}).items():
            got = _resolve_path(data, path)
            if got != expected:
                fail(f"{label}: path {path!r} expected {expected!r}, got {got!r}")
        for path, substr in a.get("contains", {}).items():
            if not _contains_ok(data, path, substr):
                got = _resolve_path(data, path)
                fail(f"{label}: path {path!r} must contain {substr!r}, got {got!r}")
        for path in a.get("has_keys", []):
            if _resolve_path(data, path) is _MISSING:
                fail(f"{label}: missing required key/path {path!r}")
        for path, n in a.get("count", {}).items():
            got = _resolve_path(data, path)
            if not isinstance(got, list) or len(got) != n:
                fail(f"{label}: path {path!r} expected list len {n}, got {got!r}")
        return
    fail(f"{label}: unknown assertion kind {kind!r}")


def check_eval_assertions() -> None:
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    evals = spec.get("evals", [])
    total = 0
    for ev in evals:
        assertions = ev.get("assertions", [])
        if not assertions:
            fail(f"eval #{ev['id']} ({ev['name']}) has no assertions")
        for i, a in enumerate(assertions):
            _run_assertion(a, f"eval #{ev['id']} [{i}]")
            total += 1
    if total < len(evals):
        fail(f"only {total} assertions for {len(evals)} evals")


UNIT_TEST_TIMEOUT_S = 900


def check_unit_tests() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        # errors="replace": pytest output can carry bytes that are not
        # valid UTF-8 on a CJK console, and a decode error here used to
        # mask the real test failure with the harness's own traceback.
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        # 180s left under 2x headroom once the suite passed 90s, and it now runs
        # a 58,440-day sxtwl sweep. A timeout here is not an AssertionError, so
        # it used to escape main()'s handler and kill the harness before any
        # check reported — see the try/except there.
        timeout=UNIT_TEST_TIMEOUT_S,
    )
    if proc.returncode != 0:
        output = (proc.stdout or "")[-1500:] or "(no output captured)"
        fail(f"pytest failed:\n{output}")


def main() -> int:
    checks = [
        check_skill_metadata,
        check_core_scripts,
        check_reference_coverage,
        check_interpretive_discipline,
        check_eval_assertions,
        check_unit_tests,
        check_mutation_score,
        check_release_cleanliness,
    ]
    results: list[tuple[str, bool, str]] = []
    for check in checks:
        try:
            check()
            results.append((check.__name__, True, ""))
        except AssertionError as exc:
            results.append((check.__name__, False, str(exc)))
        except subprocess.TimeoutExpired as exc:
            # Not an AssertionError, so this used to propagate out of main() and
            # end the run with a bare traceback: no per-check verdict, no "x/7"
            # line, and the remaining checks never ran. A timeout is a failed
            # check, and the checks after it still deserve to report.
            results.append((check.__name__, False,
                            f"timed out after {exc.timeout}s"))

    passed = sum(1 for _, ok, _ in results if ok)
    print("=" * 60)
    for name, ok, msg in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"       -> {msg.splitlines()[0] if msg else ''}")
    print("=" * 60)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
