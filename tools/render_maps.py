"""
Render GPS route maps for one or all activity datasets.

For each trip in a dataset this decodes the Strava polyline and draws it over a
vector basemap (cached Chicago layers + per-trip OpenStreetMap water/land
fetched by fetch_basemap.py), zoomed to a shared scale so every map in the
dataset is directly comparable. Output: maps/<activity>/<trip>.png

Activity-agnostic: nothing here is specific to kayaking. The route color and
which trips exist come entirely from the dataset JSON.

Run (one activity or all):
  uv run --python 3.12 --with geopandas --with matplotlib --with shapely \
    python tools/render_maps.py --data data/kayaking.json
  uv run ... python tools/render_maps.py            # all datasets
"""
import argparse
import datetime
import os

import routelib as rl

# Palette (Bootstrap Flatly-ish)
DARK = "#2c3e50"
GRAY = "#6b7a88"
LAND = "#f5f4f1"
LAND_EDGE = "#dcdcd8"
WATER = "#cfe0ea"
PARK = "#dde7d3"
START = "#18bc9c"


def fmt_date(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d, %Y")


def render_trip(trip, dataset, half, layers):
    """Draw one trip to maps/<activity>/<trip>.png."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd
    from shapely.geometry import LineString

    areas, water, roads = layers
    pts = rl.decode_polyline(trip["polyline"])

    # Transcription / data sanity check against the recorded start point.
    s_lat, s_lng = trip["start"]
    assert abs(pts[0][1] - s_lat) < 0.02 and abs(pts[0][0] - s_lng) < 0.02, \
        f"{trip['slug']}: decoded start {pts[0][::-1]} != {trip['start']}"

    line = gpd.GeoSeries([LineString(pts)], crs=4326).to_crs(3857)
    minx, miny, maxx, maxy = line.total_bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    xlim = (cx - half, cx + half)
    ylim = (cy - half, cy + half)
    win = (xlim[0], xlim[1], ylim[0], ylim[1])

    fig, ax = plt.subplots(figsize=(9, 9), dpi=330)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.05)
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_axis_off()
    ax.set_facecolor(LAND)

    # Layer order: community-area land -> open water (citywide lake, lakefront
    # only) -> detailed OSM parks/forest -> detailed OSM water -> streets ->
    # route. Detailed OSM sits above the simplified citywide lake so the crisp
    # shoreline hides the coarse cached edge.
    a = areas.cx[win[0]:win[1], win[2]:win[3]]
    if not a.empty:
        a.plot(ax=ax, facecolor=LAND, edgecolor=LAND_EDGE, linewidth=0.5, zorder=1)

    if trip.get("base_water"):
        w = water.cx[win[0]:win[1], win[2]:win[3]]
        if not w.empty:
            w.plot(ax=ax, facecolor=WATER, edgecolor="none", zorder=2)

    osm = os.path.join(rl.BASEMAP_DIR, "osm", dataset["slug"])
    for fname, color, z in ((f"{trip['slug']}_land.geojson", PARK, 2.2),
                            (f"{trip['slug']}_water.geojson", WATER, 2.3)):
        path = os.path.join(osm, fname)
        if os.path.exists(path):
            g = gpd.read_file(path)
            if not g.empty:
                g = g.to_crs(3857)
                g.geometry = g.geometry.make_valid()
                g.plot(ax=ax, facecolor=color, edgecolor="none", zorder=z)

    r = roads.cx[win[0]:win[1], win[2]:win[3]]
    if not r.empty:
        r[r["class"].isin(["2", "3"])].plot(ax=ax, color="#e2e2dc", linewidth=0.6, zorder=2.4)
        r[r["class"] == "1"].plot(ax=ax, color="#b9b9b2", linewidth=1.4, zorder=2.5)

    line.plot(ax=ax, color=dataset["route_color"], linewidth=2.6, zorder=5,
              capstyle="round", joinstyle="round")
    sx, sy = line.iloc[0].coords[0]
    ex, ey = line.iloc[0].coords[-1]
    ax.scatter([sx], [sy], s=130, c=START, edgecolors="white", linewidths=1.8, zorder=6)
    ax.scatter([ex], [ey], s=110, c=DARK, edgecolors="white", linewidths=1.6, zorder=6)

    subtitle = (f"{fmt_date(trip['date'])}  ·  {rl.miles(trip['distance_m']):.1f} mi  ·  "
                f"{rl.fmt_duration(trip['duration_s'])}  ·  {trip['location']}")
    fig.suptitle(trip["name"], fontsize=17, fontweight="bold", color=DARK, y=0.965)
    fig.text(0.5, 0.925, subtitle, ha="center", fontsize=10.5, color=GRAY)
    fig.text(0.5, 0.02, "Source: Strava GPS track", ha="center", fontsize=8.5, color="#8a8a8a")

    out_dir = os.path.join(rl.MAPS_DIR, dataset["slug"])
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{trip['slug']}.png")
    plt.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"  {out}  ({len(pts)} pts)")


def render_dataset(path):
    import geopandas as gpd
    ds = rl.load_dataset(path)
    print(f"{ds['activity']}: {len(ds['trips'])} trips")
    half = rl.common_half(ds["trips"])
    print(f"  shared scale: {2 * half:,.0f} m window")
    areas = gpd.read_file(os.path.join(rl.BASEMAP_DIR, "communityareas.geojson")).to_crs(3857)
    water = gpd.read_file(os.path.join(rl.BASEMAP_DIR, "water.geojson")).to_crs(3857)
    water.geometry = water.geometry.make_valid()
    roads = gpd.read_file(os.path.join(rl.BASEMAP_DIR, "roads.geojson")).to_crs(3857)
    for trip in ds["trips"]:
        render_trip(trip, ds, half, (areas, water, roads))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Render route maps for activity datasets")
    ap.add_argument("--data", help="one dataset JSON (default: every file in data/)")
    args = ap.parse_args()
    for path in ([args.data] if args.data else rl.list_datasets()):
        render_dataset(path)
