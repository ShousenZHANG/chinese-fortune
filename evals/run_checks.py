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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        tracked = []
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
            got = _resolve_path(data, path)
            if got is _MISSING or substr not in str(got):
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


def check_unit_tests() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=ROOT, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180,
    )
    if proc.returncode != 0:
        fail(f"pytest failed:\n{proc.stdout[-1500:]}")


def main() -> int:
    checks = [
        check_skill_metadata,
        check_core_scripts,
        check_reference_coverage,
        check_eval_assertions,
        check_unit_tests,
        check_release_cleanliness,
    ]
    results: list[tuple[str, bool, str]] = []
    for check in checks:
        try:
            check()
            results.append((check.__name__, True, ""))
        except AssertionError as exc:
            results.append((check.__name__, False, str(exc)))

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
