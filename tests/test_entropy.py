"""Tests for the entropy module (seed / system / quantum sources).

Network is NOT required: the quantum path is tested via the forced-degrade
fallback so CI is deterministic and offline-safe.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import entropy

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


# --------------------------------------------------------------------------- #
# get_rng source selection
# --------------------------------------------------------------------------- #

def test_seed_is_deterministic_plain_random():
    rng = entropy.get_rng(seed=42, source="quantum")  # seed overrides source
    assert isinstance(rng, random.Random)
    a = entropy.get_rng(seed=42).random()
    b = entropy.get_rng(seed=42).random()
    assert a == b


def test_system_is_systemrandom():
    rng = entropy.get_rng(source="system")
    assert isinstance(rng, random.SystemRandom)


def test_quantum_returns_quantumrandom():
    rng = entropy.get_rng(source="quantum")
    assert isinstance(rng, entropy.QuantumRandom)


# --------------------------------------------------------------------------- #
# QuantumRandom — forced offline degrade (no network)
# --------------------------------------------------------------------------- #

def test_quantum_degrades_to_urandom_when_source_down(monkeypatch):
    monkeypatch.setattr(entropy, "_fetch_quantum_bytes", lambda *a, **k: None)
    rng = entropy.QuantumRandom()
    # Consuming entropy must still work, flipping degraded=True.
    vals = [rng.random() for _ in range(50)]
    assert rng.degraded is True
    assert all(0.0 <= v < 1.0 for v in vals)


def test_quantum_getrandbits_in_range(monkeypatch):
    monkeypatch.setattr(entropy, "_fetch_quantum_bytes", lambda *a, **k: None)
    rng = entropy.QuantumRandom()
    for k in (1, 3, 8, 16, 53):
        v = rng.getrandbits(k)
        assert 0 <= v < (1 << k)


def test_quantum_shuffle_and_choice_work(monkeypatch):
    monkeypatch.setattr(entropy, "_fetch_quantum_bytes", lambda *a, **k: None)
    rng = entropy.QuantumRandom()
    deck = list(range(52))
    rng.shuffle(deck)
    assert sorted(deck) == list(range(52))      # permutation preserved
    assert rng.choice(deck) in deck


def test_quantum_uses_fetched_bytes_when_available(monkeypatch):
    # Feed a known block; getrandbits must consume from it (not urandom).
    monkeypatch.setattr(entropy, "_fetch_quantum_bytes",
                        lambda *a, **k: bytes([0xAB]) * 256)
    rng = entropy.QuantumRandom()
    assert rng.degraded is False
    assert rng.getrandbits(8) == 0xAB


# --------------------------------------------------------------------------- #
# describe() provenance
# --------------------------------------------------------------------------- #

def test_describe_seed():
    d = entropy.describe(entropy.get_rng(seed=1), "system", 1)
    assert d["source"] == "seed" and d["reproducible"] is True


def test_describe_system():
    d = entropy.describe(entropy.get_rng(source="system"), "system", None)
    assert d["source"] == "system_csprng"


def test_describe_quantum_degraded(monkeypatch):
    monkeypatch.setattr(entropy, "_fetch_quantum_bytes", lambda *a, **k: None)
    rng = entropy.QuantumRandom()
    rng.random()  # force a fetch attempt -> degrade
    d = entropy.describe(rng, "quantum", None)
    assert d["source"] == "os_urandom_fallback" and d["degraded"] is True


# --------------------------------------------------------------------------- #
# Script wiring — entropy field present, seed still reproducible (offline)
# --------------------------------------------------------------------------- #

def _run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(proc.stdout)


def test_yijing_entropy_field_and_seed_reproducible():
    a = _run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    b = _run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    assert a["meta"]["entropy"]["source"] == "seed"
    assert a["main_hex"]["number"] == b["main_hex"]["number"]


def test_tarot_default_entropy_is_system():
    d = _run("tarot_draw.py", "three", "--question", "x")
    assert d["entropy"]["source"] == "system_csprng"
