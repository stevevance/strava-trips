"""
Fetch detailed OpenStreetMap water + land/parks for each trip in a dataset.

Issues one Overpass query per trip over the shared render window, assembles the
result with osm2geojson (so multi-way relations become proper multipolygons),
and derives open-water fill from any coastline. Writes per-trip layers to
basemap/osm/<activity>/<trip>_water.geojson and _land.geojson, which
render_maps.py overlays for a crisp, correctly-aligned shoreline.

Run after adding or editing a dataset:
  uv run --python 3.12 --with osm2geojson --with shapely --with geopandas \
    python tools/fetch_basemap.py --data data/mountain-biking.json
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import osm2geojson
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union, polygonize

import routelib as rl

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def trip_bbox(polyline, half, margin=1.12):
    """(s, w, n, e) in EPSG:4326 of the shared window, with a fetch margin."""
    import geopandas as gpd
    from shapely.geometry import Point
    minx, miny, maxx, maxy = rl.route_bounds_3857(polyline)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    h = half * margin
    corners = gpd.GeoSeries([Point(cx - h, cy - h), Point(cx + h, cy + h)],
                            crs=3857).to_crs(4326)
    xs = [p.x for p in corners]
    ys = [p.y for p in corners]
    return (min(ys), min(xs), max(ys), max(xs))


def overpass(bbox):
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    q = f"""[out:json][timeout:60];
(
  way["natural"="water"]{b};
  relation["natural"="water"]{b};
  way["waterway"="riverbank"]{b};
  relation["waterway"="riverbank"]{b};
  way["natural"="coastline"]{b};
  way["leisure"~"park|nature_reserve"]{b};
  relation["leisure"~"park|nature_reserve"]{b};
  way["landuse"="forest"]{b};
  relation["landuse"="forest"]{b};
  way["natural"="wood"]{b};
  relation["natural"="wood"]{b};
  way["boundary"="protected_area"]{b};
  relation["boundary"="protected_area"]{b};
);
out geom;"""
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for attempt in range(6):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        req = urllib.request.Request(endpoint, data=data,
                                     headers={"User-Agent": "strava-trips/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as ex:
            last = ex
            if ex.code in (429, 502, 503, 504):
                wait = 8 * (attempt + 1)
                print(f"    {ex.code}; retry in {wait}s")
                time.sleep(wait)
                continue
            raise
    raise last


def classify(feat):
    t = feat.get("properties", {}).get("tags", {})
    if t.get("natural") == "coastline":
        return "coast"
    if t.get("natural") == "water" or t.get("waterway") == "riverbank":
        return "water"
    if (t.get("leisure") in ("park", "nature_reserve")
            or t.get("landuse") == "forest"
            or t.get("natural") == "wood"
            or t.get("boundary") == "protected_area"):
        return "land"
    return None


def lake_from_coast(coast_geoms, bbox, pad=0.012):
    """Open-water polygon east of the coastline (Lake Michigan is coastline, not fill)."""
    if not coast_geoms:
        return []
    s, w, n, e = bbox
    bx = box(w - pad, s - pad, e + pad, n + pad)
    clipped = unary_union(coast_geoms).intersection(bx)
    if clipped.is_empty:
        return []
    regions = list(polygonize(unary_union([bx.boundary, clipped])))
    if len(regions) < 2:
        return []
    cx = clipped.centroid.x
    return [r for r in regions if r.representative_point().x > cx]


def fetch_dataset(path):
    ds = rl.load_dataset(path)
    half = rl.common_half(ds["trips"])
    out_dir = os.path.join(rl.BASEMAP_DIR, "osm", ds["slug"])
    os.makedirs(out_dir, exist_ok=True)
    print(f"{ds['activity']}: {len(ds['trips'])} trips, {2 * half:,.0f} m window")
    for trip in ds["trips"]:
        gj = osm2geojson.json2geojson(overpass(trip_bbox(trip["polyline"], half)))
        water, land, coast = [], [], []
        for f in gj["features"]:
            kind = classify(f)
            if kind is None:
                continue
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            (water if kind == "water" else land if kind == "land" else coast).append(g)
        water += lake_from_coast(coast, trip_bbox(trip["polyline"], half))

        def dump(geoms, suffix):
            feats = []
            if geoms:
                feats = [{"type": "Feature", "properties": {},
                          "geometry": mapping(unary_union(geoms))}]
            with open(os.path.join(out_dir, f"{trip['slug']}_{suffix}.geojson"), "w") as fh:
                json.dump({"type": "FeatureCollection", "features": feats}, fh)

        dump(water, "water")
        dump(land, "land")
        print(f"  {trip['slug']:40s} water={len(water):3d} land={len(land):3d}")
        time.sleep(3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch OSM basemap layers for a dataset")
    ap.add_argument("--data", help="one dataset JSON (default: every file in data/)")
    args = ap.parse_args()
    for p in ([args.data] if args.data else rl.list_datasets()):
        fetch_dataset(p)
