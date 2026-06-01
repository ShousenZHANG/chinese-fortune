"""Entropy sources for divination casts (起卦 / 洗牌).

Three sources, selected per cast:

  * ``seed``   — ``random.Random(seed)``: deterministic, for tests / reproducible casts.
  * ``system`` — ``random.SystemRandom``: OS CSPRNG (default). Cryptographically
                 strong pseudo-randomness.
  * ``quantum``— ``QuantumRandom``: physical randomness from quantum vacuum noise
                 (ANU QRNG). Falls back to ``os.urandom`` (flagged ``degraded``)
                 if the quantum source is unreachable.

HONEST FRAMING — read this before using ``quantum``:
A quantum entropy source does NOT make a divination "more accurate" or "more
true". Hexagram/card outcomes are uniform regardless of whether the bits come
from a CPU CSPRNG or a photon beam-splitter; accuracy of a reading has no
physical dependence on the entropy source. ``quantum`` is offered only as a
*physically-true randomness* option (philosophically meaningful to some
practitioners), never as an accuracy improvement. Output always labels the
source so the distinction stays transparent.
"""
from __future__ import annotations

import json
import os
import random
import urllib.request

# ANU Quantum Random Number Generator (quantum vacuum fluctuations).
# Modern authenticated endpoint needs an API key (env ANU_QRNG_API_KEY);
# the legacy free endpoint is attempted as a fallback. Either may be down —
# QuantumRandom degrades to os.urandom rather than ever blocking a cast.
_ANU_AUTH_URL = "https://api.quantumnumbers.anu.edu.au"
_ANU_LEGACY_URL = "https://qrng.anu.edu.au/API/jsonI.php"
_BLOCK = 256  # bytes fetched per refill


def _fetch_quantum_bytes(n: int, timeout: float = 6.0) -> bytes | None:
    """Return ``n`` quantum-random bytes, or None if unavailable."""
    key = os.environ.get("ANU_QRNG_API_KEY")
    try:
        if key:
            req = urllib.request.Request(
                f"{_ANU_AUTH_URL}?length={n}&type=uint8",
                headers={"x-api-key": key},
            )
        else:
            req = urllib.request.Request(
                f"{_ANU_LEGACY_URL}?length={n}&type=uint8"
            )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            # Cap the read: a compromised/misbehaving endpoint ignoring length=
            # must not stream an unbounded body into memory.
            payload = json.loads(resp.read(1 << 20).decode("utf-8"))
        if payload.get("success") and isinstance(payload.get("data"), list):
            data = bytes(int(b) & 0xFF for b in payload["data"])
            return data[:n] if len(data) >= n else None
    except Exception:
        return None
    return None


class QuantumRandom(random.Random):
    """``random.Random`` backed by a quantum entropy pool.

    Consumes bytes from the ANU QRNG; refills on demand. Any fetch failure
    flips ``degraded = True`` and the pool is topped up from ``os.urandom``
    (still a CSPRNG) so a cast never blocks or crashes.
    """

    def __init__(self) -> None:
        self._pool = bytearray()
        self.degraded = False
        super().__init__()

    def _ensure(self, n: int) -> None:
        while len(self._pool) < n:
            qb = _fetch_quantum_bytes(_BLOCK)
            if qb:
                self._pool.extend(qb)
            else:
                self.degraded = True
                self._pool.extend(os.urandom(_BLOCK))

    def _take(self, n: int) -> int:
        self._ensure(n)
        chunk = bytes(self._pool[:n])
        del self._pool[:n]
        return int.from_bytes(chunk, "big")

    def getrandbits(self, k: int) -> int:
        if k <= 0:
            raise ValueError("number of bits must be greater than zero")
        nbytes = (k + 7) // 8
        value = self._take(nbytes)
        return value >> (nbytes * 8 - k)  # trim to exactly k bits

    def random(self) -> float:
        # 53-bit mantissa float in [0, 1), per CPython convention.
        return self.getrandbits(53) / (1 << 53)

    def seed(self, *args, **kwargs) -> None:  # noqa: D401
        """No-op: entropy is externally sourced, not seedable."""
        return None


def get_rng(seed: int | None = None, source: str = "system"):
    """Return an RNG for a cast.

    seed given         -> deterministic random.Random(seed) (source ignored)
    source == quantum  -> QuantumRandom (physical, degrades to os.urandom)
    otherwise          -> random.SystemRandom (OS CSPRNG, default)
    """
    if seed is not None:
        return random.Random(seed)
    if source == "quantum":
        return QuantumRandom()
    return random.SystemRandom()


def describe(rng, source: str, seed: int | None) -> dict:
    """Structured, honest provenance for the output JSON."""
    if seed is not None:
        return {"source": "seed", "seed": seed, "reproducible": True,
                "note": "确定性种子, 仅供复现/测试"}
    if source == "quantum":
        degraded = getattr(rng, "degraded", False)
        return {
            "source": "os_urandom_fallback" if degraded else "quantum_vacuum_anu",
            "degraded": degraded,
            "note": ("量子源不可达, 已降级到 OS CSPRNG" if degraded
                     else "ANU 量子真空噪声物理真随机; 不影响卦象准确度, 仅熵源差异"),
        }
    return {"source": "system_csprng",
            "note": "OS 加密级伪随机 (random.SystemRandom)"}
