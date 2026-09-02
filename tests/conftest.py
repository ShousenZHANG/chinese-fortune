"""Pytest config: make scripts/ importable, and share the subprocess runner."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def run_cli(script: str, *args, expect_rc: int = 0) -> dict:
    """Run a CLI script and return its parsed JSON stdout.

    Asserts the exit code (default 0) so an exit-status regression cannot pass
    silently, and reports stderr when the output is not JSON.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
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
