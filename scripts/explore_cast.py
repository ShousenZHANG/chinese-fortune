"""今日随机寻访点 — a QRNG-driven exploration prompt (Randonautica-inspired).

Generates a random nearby point from quantum/CSPRNG entropy, finds a
statistically anomalous spot (attractor = dense cluster, void = sparse,
power = strongest, blindspot = plain random), reports bearing + distance, and
notes how it lines up with today's almanac auspicious directions (黄历吉方).

HONEST FRAMING — read before use:
This is a randomized *walk / exploration prompt*, NOT a prediction and NOT a
"mind-matter interaction" (MMI) device. Attractor/void points are pure
statistical density fluctuations in random data; setting an intention does NOT
physically bias the entropy, and no point is "influenced by thought". The 黄历
alignment is a cultural overlay for fun, not a claim of efficacy. Output always
carries this disclaimer plus safety guidance — going to unfamiliar places has
real-world risk.

Usage:
    python explore_cast.py --lat -33.8688 --lon 151.2093 --radius 3000 \\
        --mode attractor --entropy quantum --intention "灵感"
"""
from __future__ import annotations

import argparse
import math
import sys

import entropy
from utils import json_print

EARTH_M_PER_DEG = 111_320.0  # metres per degree of latitude (mean)
MAX_PROJ_LAT = 89.9          # clamp for the cos(lat) longitude projection


def _cos_lat(lat: float) -> float:
    """cos(latitude) clamped away from the poles so the longitude projection
    never explodes (cos -> 0 at ±90 would blow dx/(cos) up to ~1e14)."""
    return math.cos(math.radians(max(-MAX_PROJ_LAT, min(MAX_PROJ_LAT, lat))))


def _norm_lon(lon: float) -> float:
    """Wrap longitude into [-180, 180)."""
    return ((lon + 180.0) % 360.0) - 180.0

# 后天八卦 -> compass bearing (degrees, 0=N clockwise).
BAGUA_BEARING: dict[str, float] = {
    "坎": 0.0, "艮": 45.0, "震": 90.0, "巽": 135.0,
    "离": 180.0, "坤": 225.0, "兑": 270.0, "乾": 315.0,
}

SAFETY = [
    "白天前往, 勿夜间独行",
    "结伴而行, 告知他人去向",
    "守法; 勿进入私人领地 / 危险区 / 工地 / 水域",
    "随机点仅为探索提示, 后果自负, 不适宜则折返",
]


def random_points(lat: float, lon: float, radius_m: float, n: int, rng):
    """n uniformly-distributed points within radius_m of (lat, lon)."""
    pts = []
    cos_lat = _cos_lat(lat) or 1e-9
    for _ in range(n):
        r = radius_m * math.sqrt(rng.random())   # sqrt for uniform area
        theta = 2 * math.pi * rng.random()
        dx = r * math.cos(theta)
        dy = r * math.sin(theta)
        pts.append((lat + dy / EARTH_M_PER_DEG,
                    lon + dx / (EARTH_M_PER_DEG * cos_lat)))
    return pts


def find_anomaly(pts, origin, radius_m, mode, grid=16):
    """Grid-density anomaly over the point cloud (dependency-free, honest about
    being grid-density, not gaussian KDE). Returns (target_lat, target_lon, z)."""
    olat, olon = origin
    span = radius_m / EARTH_M_PER_DEG  # half-extent in degrees lat
    cos_lat = _cos_lat(olat) or 1e-9
    span_lon = span / cos_lat

    if mode == "blindspot":
        # plain random point — no anomaly search.
        target = pts[len(pts) // 2]
        return target[0], target[1], 0.0

    # Bin into grid x grid cells; count per cell.
    counts: dict[tuple[int, int], int] = {}
    members: dict[tuple[int, int], list] = {}
    for (la, lo) in pts:
        gx = min(grid - 1, max(0, int((lo - (olon - span_lon)) / (2 * span_lon) * grid)))
        gy = min(grid - 1, max(0, int((la - (olat - span)) / (2 * span) * grid)))
        counts[(gx, gy)] = counts.get((gx, gy), 0) + 1
        members.setdefault((gx, gy), []).append((la, lo))

    def cell_center(x: int, y: int) -> tuple[float, float]:
        return ((olat - span) + (y + 0.5) / grid * 2 * span,
                (olon - span_lon) + (x + 0.5) / grid * 2 * span_lon)

    # Only cells whose centre is within the *circular* radius are candidates,
    # so the chosen point never escapes --radius (a square grid's corners do).
    in_circle = [
        (x, y) for x in range(grid) for y in range(grid)
        if haversine_m(olat, olon, *cell_center(x, y)) <= radius_m
    ]
    all_cells = [counts.get(c, 0) for c in in_circle]
    mean = sum(all_cells) / len(all_cells)
    var = sum((c - mean) ** 2 for c in all_cells) / len(all_cells)
    std = math.sqrt(var) or 1e-9

    if mode == "void":
        cell = min(in_circle, key=lambda c: counts.get(c, 0))
        tlat, tlon = cell_center(*cell)
        return tlat, tlon, (counts.get(cell, 0) - mean) / std

    # attractor -> densest in-circle cell; target = centroid of its points.
    cell = max(in_circle, key=lambda c: counts.get(c, 0))
    z = (counts.get(cell, 0) - mean) / std
    mem = members.get(cell) or [cell_center(*cell)]
    tlat = sum(p[0] for p in mem) / len(mem)
    tlon = sum(p[1] for p in mem) / len(mem)
    if mode == "power":
        vcell = min(in_circle, key=lambda c: counts.get(c, 0))
        vz = (counts.get(vcell, 0) - mean) / std
        if abs(vz) > abs(z):
            tlat, tlon = cell_center(*vcell)
            return tlat, tlon, vz
    return tlat, tlon, z


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def compass_16(bearing: float) -> str:
    dirs = ["北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
            "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北"]
    return dirs[int((bearing + 11.25) % 360 / 22.5)]


def huangli_directions(date_str: str | None) -> dict:
    """Today's 黄历 吉神方位 (八卦 -> bearing). Empty dict if lunar_python absent."""
    try:
        from datetime import datetime

        from lunar_python import Solar  # type: ignore
        if date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            dt = datetime(2026, 1, 1)  # deterministic default; pass --date for today
        lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0).getLunar()
        out = {}
        for name, method in (("喜神", "getDayPositionXi"), ("财神", "getDayPositionCai"),
                             ("福神", "getDayPositionFu")):
            try:
                gua = getattr(lunar, method)()
                if gua in BAGUA_BEARING:
                    out[name] = {"卦": gua, "bearing": BAGUA_BEARING[gua],
                                 "compass": compass_16(BAGUA_BEARING[gua])}
            except Exception:
                continue
        return out
    except Exception:
        return {}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="今日随机寻访点 (QRNG 探索提示)")
    p.add_argument("--lat", type=float, required=True, help="当前纬度")
    p.add_argument("--lon", type=float, required=True, help="当前经度")
    p.add_argument("--radius", type=float, default=3000.0, help="半径(米), 默认 3000")
    p.add_argument("--mode", choices=["attractor", "void", "power", "blindspot"],
                   default="attractor")
    p.add_argument("--points", type=int, default=10000, help="撒点数, 默认 10000")
    p.add_argument("--entropy", choices=["system", "quantum"], default="system")
    p.add_argument("--intention", type=str, default=None,
                   help="意图(概念性, 不影响随机数; 仅记录)")
    p.add_argument("--date", type=str, default=None, help="黄历日期 YYYY-MM-DD")
    p.add_argument("--seed", type=int, default=None, help="确定性种子 (测试/复现)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (-90 <= args.lat <= 90 and -180 <= args.lon <= 180):
        json_print({"ok": False, "error": "invalid_coords"})
        return 1
    if not (50 <= args.radius <= 100_000):
        json_print({"ok": False, "error": "radius_out_of_range",
                    "message": "radius 必须在 50-100000 米"})
        return 1
    n = max(100, min(50_000, args.points))

    rng = entropy.get_rng(args.seed, args.entropy)
    pts = random_points(args.lat, args.lon, args.radius, n, rng)
    tlat, tlon, z = find_anomaly(pts, (args.lat, args.lon), args.radius, args.mode)
    tlat = max(-90.0, min(90.0, tlat))
    tlon = _norm_lon(tlon)

    dist = haversine_m(args.lat, args.lon, tlat, tlon)
    brg = bearing_deg(args.lat, args.lon, tlat, tlon)

    out = {
        "ok": True,
        "tool": "explore",
        "mode": args.mode,
        "intention": args.intention,
        "entropy": entropy.describe(rng, args.entropy, args.seed),
        "origin": {"lat": args.lat, "lon": args.lon},
        "target": {"lat": round(tlat, 6), "lon": round(tlon, 6)},
        "distance_m": round(dist, 1),
        "bearing_deg": round(brg, 1),
        "compass": compass_16(brg),
        "anomaly_z": round(z, 2),
        "huangli_directions": huangli_directions(args.date),
        "safety": SAFETY,
        "disclaimer": (
            "随机探索散步提示。attractor/void 是纯统计密度涨落, "
            "非预兆、非念力(MMI)影响; 意图仅记录不改变随机数。黄历方位为文化叠加。"
            "前往陌生地点有现实风险, 注意安全, 后果自负。"
        ),
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
