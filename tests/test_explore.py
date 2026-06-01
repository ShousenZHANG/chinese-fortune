"""Tests for explore_cast — QRNG exploration point (Randonautica-inspired).

All deterministic via --seed; no network (uses seed/system entropy).
"""
import json
import subprocess
import sys
from pathlib import Path

import explore_cast as ex
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def run(*args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "explore_cast.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("mode", ["attractor", "void", "power", "blindspot"])
def test_target_within_radius(mode):
    d = run("--lat", -33.8688, "--lon", 151.2093, "--radius", 3000,
            "--mode", mode, "--seed", 1)
    assert d["ok"] is True
    assert d["distance_m"] <= 3000.1, f"{mode} escaped radius: {d['distance_m']}"
    assert 0 <= d["bearing_deg"] <= 360


def test_determinism_with_seed():
    a = run("--lat", -33.8688, "--lon", 151.2093, "--seed", 7)
    b = run("--lat", -33.8688, "--lon", 151.2093, "--seed", 7)
    assert a["target"] == b["target"]


def test_entropy_and_safety_and_disclaimer_present():
    d = run("--lat", 1.0, "--lon", 1.0, "--seed", 3)
    assert d["entropy"]["source"] == "seed"
    assert isinstance(d["safety"], list) and len(d["safety"]) >= 3
    # Honest framing must be explicit — no MMI / prediction claims.
    assert "MMI" in d["disclaimer"] or "念力" in d["disclaimer"]
    assert "非预兆" in d["disclaimer"]


def test_huangli_directions_with_date():
    d = run("--lat", -33.8688, "--lon", 151.2093, "--seed", 1, "--date", "2026-06-01")
    hd = d["huangli_directions"]
    assert "财神" in hd and "bearing" in hd["财神"]


def test_invalid_coords_rejected():
    d = run("--lat", 200, "--lon", 0, "--seed", 1)
    assert d["ok"] is False and d["error"] == "invalid_coords"


def test_radius_out_of_range_rejected():
    d = run("--lat", 0, "--lon", 0, "--radius", 10, "--seed", 1)
    assert d["ok"] is False and d["error"] == "radius_out_of_range"


# --------------------------------------------------------------------------- #
# Unit-level geometry checks
# --------------------------------------------------------------------------- #

def test_random_points_within_radius():
    import random
    rng = random.Random(0)
    pts = ex.random_points(-33.0, 151.0, 1000.0, 500, rng)
    for la, lo in pts:
        assert ex.haversine_m(-33.0, 151.0, la, lo) <= 1000.5


def test_bearing_cardinals():
    # due north / east of origin
    assert abs(ex.bearing_deg(0, 0, 1, 0) - 0.0) < 1.0
    assert abs(ex.bearing_deg(0, 0, 0, 1) - 90.0) < 1.0


def test_compass_16_buckets():
    assert ex.compass_16(0) == "北"
    assert ex.compass_16(90) == "东"
    assert ex.compass_16(180) == "南"
    assert ex.compass_16(270) == "西"
