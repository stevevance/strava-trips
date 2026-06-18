"""
Shared helpers for the Strava trips site.

Pure-Python utilities (polyline decoding, slugs, formatting, dataset loading)
plus a lazily-imported geometry helper. Kept dependency-light at import time so
the HTML builder can use it without geopandas/matplotlib installed.

A "dataset" is one activity type (kayaking, mountain biking, ...) described by a
JSON file in data/. The site is fully activity-agnostic: add a new data/<slug>.json
and rebuild, and a new page appears with no code changes.
"""
import json
import os
import re

# Repo root = parent of this tools/ directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BASEMAP_DIR = os.path.join(ROOT, "basemap")
MAPS_DIR = os.path.join(ROOT, "maps")


def decode_polyline(s, precision=5):
    """
    Decode a Google/Strava encoded polyline into (lng, lat) tuples (x, y order
    for shapely). Each coordinate delta is a zig-zag varint in 5-bit chunks,
    ASCII-shifted by 63.
    """
    coords = []
    index = lat = lng = 0
    n = len(s)
    factor = 10 ** precision
    while index < n:
        incomplete = False
        for axis in range(2):
            shift = result = 0
            while True:
                # A well-formed polyline always has complete lat/lng pairs; a
                # dangling partial chunk at the very end (e.g. a stray trailing
                # character) would otherwise overrun the string, so stop cleanly.
                if index >= n:
                    incomplete = True
                    break
                b = ord(s[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            if incomplete:
                break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if axis == 0:
                lat += delta
            else:
                lng += delta
        if incomplete:
            break
        coords.append((lng / factor, lat / factor))
    return coords


def slugify(text):
    """Lowercase, alphanumeric-with-hyphens slug."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def load_dataset(path):
    """Load one activity dataset JSON, filling in derived slugs if missing."""
    with open(path) as fh:
        ds = json.load(fh)
    ds.setdefault("slug", slugify(ds.get("activity", "activity")))
    for t in ds["trips"]:
        t.setdefault("slug", slugify(t["name"]))
    return ds


def list_datasets():
    """All activity dataset paths in data/, sorted."""
    return sorted(
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.endswith(".json")
    )


# ---- formatting -----------------------------------------------------------

def miles(distance_m):
    return distance_m / 1609.344


def km(distance_m):
    return distance_m / 1000.0


def fmt_duration(seconds):
    """Seconds -> 'Xh Ym' (or 'Ym' when under an hour)."""
    h = int(seconds // 3600)
    m = int(round((seconds % 3600) / 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h}h {m}m" if h else f"{m}m"


def avg_speed_mph(distance_m, seconds):
    return miles(distance_m) / (seconds / 3600.0) if seconds else 0.0


# ---- geometry (lazy heavy imports) ----------------------------------------

def route_bounds_3857(polyline):
    """(minx, miny, maxx, maxy) of a decoded route in Web Mercator meters."""
    import geopandas as gpd
    from shapely.geometry import LineString
    line = gpd.GeoSeries([LineString(decode_polyline(polyline))], crs=4326).to_crs(3857)
    return tuple(line.total_bounds)


def common_half(trips, pad=1.35, floor=450.0):
    """
    Shared square half-window (meters) so every map in a dataset is the same
    scale: the largest route's padded extent, with a minimum floor.
    """
    best = floor
    for t in trips:
        minx, miny, maxx, maxy = route_bounds_3857(t["polyline"])
        best = max(best, max(maxx - minx, maxy - miny) / 2 * pad)
    return best
