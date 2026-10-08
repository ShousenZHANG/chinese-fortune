"""5.9.0: the skill runs with nothing but a Python 3.9+ interpreter.

lunar_python and tzdata ship inside scripts/ with their own dist-info (RECORD,
licence). A host that cannot pip install -- the Claude API sandbox has no
network and no runtime package installation -- still computes every chart, and
a local agent never installs packages into the user's global Python.
"""
import ast
import base64
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
VENDORED = {"lunar_python": "1.4.8", "tzdata": "2026.3"}
LICENCES = {"lunar_python": ["LICENSE"], "tzdata": ["licenses/LICENSE", "licenses/licenses/LICENSE_APACHE"]}
BARE = {**os.environ, "PYTHONTZPATH": ""}      # no system zoneinfo: tzdata must come from scripts/


def _record(package: str, version: str) -> list:
    text = (SCRIPTS / f"{package}-{version}.dist-info" / "RECORD").read_text(encoding="utf-8")
    return [row for row in csv.reader(text.splitlines()) if row]


@pytest.mark.parametrize("package,version", VENDORED.items())
def test_vendored_files_are_the_published_ones(package, version):
    """Every file under scripts/<package>/ is listed in RECORD with its hash, and nothing else is there."""
    payload = {path: digest for path, digest, _ in _record(package, version)
               if path.startswith(package + "/") and digest}
    assert payload
    for path, digest in payload.items():
        algorithm, expected = digest.split("=", 1)
        actual = hashlib.new(algorithm, (SCRIPTS / path).read_bytes()).digest()
        assert base64.urlsafe_b64encode(actual).rstrip(b"=").decode() == expected, path
    shipped = {p.relative_to(SCRIPTS).as_posix() for p in (SCRIPTS / package).rglob("*")
               if p.is_file() and "__pycache__" not in p.parts}
    assert shipped == set(payload)


@pytest.mark.parametrize("package,version", VENDORED.items())
def test_vendored_packages_carry_their_licences(package, version):
    info = SCRIPTS / f"{package}-{version}.dist-info"
    assert f"Version: {version}" in (info / "METADATA").read_text(encoding="utf-8")
    for name in LICENCES[package]:
        assert (info / name).read_text(encoding="utf-8").strip(), name


def test_a_bare_interpreter_imports_the_vendored_copies():
    """-S drops site-packages, as in a fresh venv where nothing was installed."""
    probe = ("import sys; sys.path.insert(0, sys.argv[1]); import lunar_python, tzdata, zoneinfo; "
             "print(lunar_python.__file__); print(tzdata.__file__); "
             "print(zoneinfo.ZoneInfo('Australia/Sydney').key)")
    run = subprocess.run([sys.executable, "-S", "-c", probe, str(SCRIPTS)],
                         capture_output=True, encoding="utf-8", env=BARE)
    assert run.returncode == 0, run.stderr
    lunar, tz, key = run.stdout.splitlines()
    assert Path(lunar).resolve().is_relative_to(SCRIPTS) and Path(tz).resolve().is_relative_to(SCRIPTS)
    assert key == "Australia/Sydney"


@pytest.mark.parametrize("script,args", [
    ("bazi_calc.py", ["--year", "1990", "--month", "5", "--day", "10", "--hour", "14",
                      "--gender", "male", "--timezone", "Asia/Shanghai", "--as-of-year", "2026"]),
    ("request_time.py", ["--current-timezone", "Australia/Sydney"]),
])
def test_a_bare_interpreter_runs_the_tools(script, args):
    run = subprocess.run([sys.executable, "-S", str(SCRIPTS / script), *args],
                         capture_output=True, encoding="utf-8", env=BARE)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["ok"]


@pytest.mark.parametrize("path", sorted(SCRIPTS.glob("*.py")), ids=lambda p: p.name)
def test_runtime_scripts_parse_as_python_39(path):
    """Syntax floor. mypy (3.10 at the lowest) catches 3.11-only calls; the CI py3.9 job runs the rest."""
    ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))


@pytest.mark.parametrize("text,expected", [
    ("2026-10-06T01:00:00Z", "2026-10-06T01:00:00+00:00"),       # 3.9/3.10 refuse the Z
    ("2026-10-06T09:00:00.5+08:00", "2026-10-06T09:00:00.500000+08:00"),   # and a 1-digit fraction
    ("2026-10-06T09:00", "2026-10-06T09:00:00"),
    ("2026-10-06T01:00:00.123456789Z", "2026-10-06T01:00:00.123456+00:00"),  # Go/Java nanoseconds
    ("2026-10-06T09:00:00+0530", "2026-10-06T09:00:00+05:30"),
    ("2026-10-06T09:00-05", "2026-10-06T09:00:00-05:00"),
    ("2026-10-06 09:00:00,5+08:00", "2026-10-06T09:00:00.500000+08:00"),
    ("2026-10-06", "2026-10-06T00:00:00"),
])
def test_iso_input_reads_the_same_on_every_supported_python(text, expected):
    from utils import parse_iso
    assert parse_iso(text).isoformat() == expected


def test_no_runtime_requirement_file_invites_a_pip_install():
    assert not (SCRIPTS / "requirements.txt").exists()
    assert not (SCRIPTS / "constraints-runtime.txt").exists()


def _frontmatter() -> dict:
    head = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    return dict(line.split(": ", 1) for line in head.strip().splitlines())


def test_the_skill_states_what_it_needs_and_never_asks_for_pip():
    meta = _frontmatter()
    assert "Python 3.9" in meta["compatibility"] and len(meta["compatibility"]) <= 500
    assert meta["license"] == "MIT"
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "pip install" not in skill and "python3" in skill and "py -3" in skill
    for readme in ("README.md", "README.en.md"):
        text = (ROOT / readme).read_text(encoding="utf-8")
        assert "pip install -r scripts/requirements.txt" not in text, readme
        assert "npx skills add ShousenZHANG/chinese-fortune" in text, readme
        assert "/plugin marketplace add ShousenZHANG/chinese-fortune" in text, readme


def test_the_plugin_marketplace_installs_this_skill_at_this_version():
    from utils import __version__
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["name"] == "chinese-fortune" and market["owner"]["name"]
    (plugin,) = market["plugins"]
    assert plugin["name"] == "chinese-fortune" and plugin["source"] == "./"
    assert plugin["version"] == __version__
    assert (ROOT / "SKILL.md").is_file() and not (ROOT / "skills").exists()   # root SKILL.md = one skill
