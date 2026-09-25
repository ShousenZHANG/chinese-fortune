"""The same input must print the same bytes in every process.

Python salts str hashes per process, so iterating a set of branches or stems
gives a different order each run. detect_interactions once printed the 子卯
互刑 pair as 卯子 or 子卯 depending on the process; nothing in a single test
run could see it. Each CLI here runs under several fixed hash seeds.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SEEDS = ("0", "1", "2", "3", "12345")

_READING = {
    "current_timezone": "Australia/Sydney", "request_time": "2026-09-17T02:00:00Z",
    "period": {"start": "2026-10-13", "end": "2026-10-17"},
    "event": {"scenario": "travel", "timezone": "Australia/Sydney", "longitude": 151.2},
    "participants": [{"id": "me", "confirmed": True, "person": {
        "birth": {"year": 1999, "month": 6, "day": 15, "hour": 0, "minute": 30, "gender": "female",
                  "timezone": "Asia/Shanghai", "longitude": 120.64}, "time_certainty": "exact"}}],
    "duration_minutes": 120, "granularity": "hour", "question": "哪天好？",
    "candidates": [{"id": "a", "start": "2026-10-13T09:00", "end": "2026-10-13T13:00"},
                   {"id": "b", "start": "2026-10-15T20:00", "end": "2026-10-16T12:00"}],
}

CASES = {
    # 己卯年 … 子时: the chart that carries the 子卯 互刑 pair.
    "bazi": (["bazi_calc.py", "--year", "1999", "--month", "6", "--day", "15", "--hour", "0",
              "--minute", "30", "--gender", "female", "--as-of-year", "2026"], None),
    "reading": (["fortune_reading.py", "--stdin"], json.dumps(_READING, ensure_ascii=False)),
    "reading_markdown": (["fortune_reading.py", "--stdin", "--markdown"], json.dumps(_READING, ensure_ascii=False)),
    "huangli": (["huangli_query.py", "--date", "2026-10-14", "--question", "这天结婚可以吗", "--markdown"], None),
}


def _run(args: list[str], stdin: str | None, seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONUTF8": "1"}
    proc = subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], input=stdin,
                          capture_output=True, text=True, encoding="utf-8", env=env)
    assert proc.returncode == 0, proc.stderr[-400:]
    return proc.stdout


@pytest.mark.parametrize("name", sorted(CASES))
def test_output_does_not_depend_on_the_hash_seed(name):
    args, stdin = CASES[name]
    outputs = {seed: _run(args, stdin, seed) for seed in SEEDS}
    assert len(set(outputs.values())) == 1, f"{name}: output differs across PYTHONHASHSEED {SEEDS}"


def test_the_xing_pair_reads_as_the_texts_write_it():
    chart = json.loads(_run(CASES["bazi"][0], None, "0"))
    pairs = [x["branches"] for x in chart["interactions"]["dizhi_xing"] if x["type"] == "互刑"]
    assert pairs == [["子", "卯"]]
