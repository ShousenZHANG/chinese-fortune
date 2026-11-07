"""Pytest config: make scripts/ importable, and share the subprocess runner."""
import json
import subprocess
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
SCRIPTS = SKILLS / "chinese-fortune/scripts"
# Every skill's scripts are importable; chinese-fortune comes first, so its
# utils/entropy win over a same-named helper elsewhere.
SKILL_SCRIPTS = [SCRIPTS, SKILLS / "life-guide/scripts", SKILLS / "fortune-extras/scripts"]
for folder in reversed(SKILL_SCRIPTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))


def script_path(script: str) -> Path:
    """The skill folder that ships this script."""
    return next((folder / script for folder in SKILL_SCRIPTS if (folder / script).is_file()), SCRIPTS / script)


def run_cli(script: str, *args, expect_rc: int = 0) -> dict:
    """Run a CLI script and return its parsed JSON stdout.

    Asserts the exit code (default 0) so an exit-status regression cannot pass
    silently, and reports stderr when the output is not JSON.
    """
    proc = subprocess.run(
        [sys.executable, str(script_path(script)), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == expect_rc, (
        f"{script} exited {proc.returncode}, expected {expect_rc}\n"
        f"stderr={proc.stderr[:400]}\nstdout={proc.stdout[:400]}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"{script} emitted non-JSON (rc={proc.returncode})\n"
            f"stderr={proc.stderr[:400]}\nstdout={proc.stdout[:400]}"
        ) from e


def corpus_bytes(name: str) -> bytes:
    """A corpus file by its manifest path (books/..., sources/...), from the folder or its archive."""
    from classical_search import library_bytes
    data = library_bytes(SCRIPTS.parent / "knowledge", name)
    assert data is not None, name
    return data


def corpus_text(name: str) -> str:
    """Decoded like Path.read_text: universal newlines, so frozen CRLF sources read as before."""
    return corpus_bytes(name).decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
