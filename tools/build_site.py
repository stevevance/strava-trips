"""
Build the static site from the activity datasets in data/.

Generates one page per activity (<slug>.html) plus an index.html linking them.
Pure templating — no heavy dependencies. Run after render_maps.py:

  python tools/build_site.py

Activity-agnostic: every dataset in data/ becomes a page automatically.
"""
import datetime
import html
import os

import routelib as rl

# Public source repository, linked from the index page.
REPO_URL = "https://github.com/stevevance/strava-trips"


def fmt_date(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d, %Y")


def totals(trips):
    dist_m = sum(t["distance_m"] for t in trips)
    secs = sum(t["duration_s"] for t in trips)
    return len(trips), rl.miles(dist_m), secs


# Absolute base URL for Open Graph image/url tags (social scrapers require
# absolute URLs).
BASE_URL = "https://stevevance.github.io/strava-trips/"


def head(title, description, page_path, image_name):
    """<head> with Open Graph + Twitter link-preview meta tags."""
    e = html.escape
    url = BASE_URL + page_path          # "" -> the index
    img = BASE_URL + "og/" + image_name
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(img)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{e(img)}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
"""

FOOT = """<footer>
  Routes &amp; statistics from Strava &middot; basemap data &copy; OpenStreetMap contributors
</footer>
</body>
</html>
"""


def trip_card(trip, activity, e):
    """One trip row: map on the left, statistics on the right."""
    img = f"maps/{e(activity['slug'])}/{e(trip['slug'])}.png"
    dist_mi = rl.miles(trip["distance_m"])
    dist_km = rl.km(trip["distance_m"])
    dur = rl.fmt_duration(trip["duration_s"])
    mph = rl.avg_speed_mph(trip["distance_m"], trip["duration_s"])
    # Top speed is hidden for activities where GPS max-speed is unreliable
    # (e.g. kayaking, where momentary GPS spikes produce nonsense values).
    show_top = activity.get("show_top_speed", True) and trip.get("max_speed_ms") is not None
    top = rl.mph(trip["max_speed_ms"]) if show_top else None
    top_stat = (f'<div class="stat"><div class="v">{top:.1f} mph</div>'
                f'<div class="k">Top speed</div></div>') if show_top else ""
    alt = e(f"Map of the GPS route for {trip['name']} at {trip['location']}, "
            f"an orange track over an OpenStreetMap-based basemap.")
    strava = (f'<a class="btn" href="https://www.strava.com/activities/{e(trip["strava_id"])}" '
              f'target="_blank" rel="noopener">View on Strava</a>') if trip.get("strava_id") else ""
    return f"""  <article class="trip">
    <div class="map"><img src="{img}" alt="{alt}"></div>
    <div class="info">
      <h2>{e(trip['name'])}</h2>
      <p class="where">{e(trip['location'])} &middot; {fmt_date(trip['date'])}</p>
      <div class="stats">
        <div class="stat"><div class="v">{dist_mi:.1f} mi</div><div class="k">Distance ({dist_km:.1f} km)</div></div>
        <div class="stat"><div class="v">{dur}</div><div class="k">{e(activity['duration_label'])}</div></div>
        <div class="stat"><div class="v">{mph:.1f} mph</div><div class="k">Avg speed (incl. stops)</div></div>
        {top_stat}
        <div class="stat"><div class="v">{e(activity['activity'])}</div><div class="k">Activity type</div></div>
      </div>
      {strava}
    </div>
  </article>
"""


def build_activity_page(ds):
    e = html.escape
    n, dist_mi, secs = totals(ds["trips"])
    description = f"{n} {ds['activity'].lower()} trips · {dist_mi:.0f} mi · mapped GPS routes from Strava."
    parts = [head(ds["title"], description, f"{ds['slug']}.html", f"{ds['slug']}.png")]
    parts.append(f"""<header>
  <p class="crumb"><a href="index.html">&larr; All activities</a></p>
  <h1>{e(ds['title'])}</h1>
  <p class="intro">{e(ds['intro'])}</p>
  <div class="summary">
    <div><div class="num">{n}</div><div class="lbl">Trips</div></div>
    <div><div class="num">{dist_mi:.1f} mi</div><div class="lbl">Total distance</div></div>
    <div><div class="num">{rl.fmt_duration(secs)}</div><div class="lbl">{e(ds['total_duration_label'])}</div></div>
  </div>
</header>
<main>
""")
    for trip in ds["trips"]:
        parts.append(trip_card(trip, ds, e))
    parts.append("</main>\n")
    parts.append(FOOT)
    out = os.path.join(rl.ROOT, f"{ds['slug']}.html")
    with open(out, "w") as fh:
        fh.write("".join(parts))
    print(f"  {out}")


def build_index(datasets):
    e = html.escape
    names = ", ".join(ds["activity"].lower() for ds in datasets)
    description = f"GPS routes from my Strava activities ({names}), mapped on an OpenStreetMap basemap."
    parts = [head("Strava trips", description, "", "index.png")]
    parts.append("""<header>
  <h1>Strava trips</h1>
  <p class="intro">GPS routes from my Strava activities, mapped on an OpenStreetMap-based basemap.</p>
  <p class="repo-link"><a href="{repo}" target="_blank" rel="noopener">View source on GitHub &rarr;</a></p>
</header>""".replace("{repo}", e(REPO_URL)) + """
<main class="cards">
""")
    for ds in datasets:
        n, dist_mi, secs = totals(ds["trips"])
        # Thumbnail: the first trip's map.
        thumb = f"maps/{e(ds['slug'])}/{e(ds['trips'][0]['slug'])}.png" if ds["trips"] else ""
        parts.append(f"""  <a class="activity-card" href="{e(ds['slug'])}.html">
    <div class="thumb"><img src="{thumb}" alt="{e(ds['activity'])} route map"></div>
    <div class="meta">
      <h2>{e(ds['activity'])}</h2>
      <p>{n} trips &middot; {dist_mi:.1f} mi &middot; {rl.fmt_duration(secs)}</p>
    </div>
  </a>
""")
    parts.append("</main>\n")
    parts.append(FOOT)
    out = os.path.join(rl.ROOT, "index.html")
    with open(out, "w") as fh:
        fh.write("".join(parts))
    print(f"  {out}")


if __name__ == "__main__":
    datasets = [rl.load_dataset(p) for p in rl.list_datasets()]
    print(f"Building {len(datasets)} activity page(s) + index")
    for ds in datasets:
        build_activity_page(ds)
    build_index(datasets)
