# Strava trips

A small static website that maps GPS routes from my Strava activities. Each
activity type (kayaking, mountain biking, ...) gets its own page showing every
trip as a route map alongside its statistics, with an index page linking them
all. Published with GitHub Pages.

**Live site:** https://stevevance.github.io/strava-trips/

Each map draws the GPS track over a vector basemap built from cached Chicago
layers plus detailed [OpenStreetMap](https://www.openstreetmap.org/) water and
parkland, zoomed so that every trip within an activity is shown at the same
scale for easy comparison.

## How it works

The site is **data-driven and activity-agnostic** — there is no code specific
to any one sport. Everything comes from a JSON file per activity in `data/`.
Adding a new activity is just adding a new dataset and rebuilding; a new page
appears automatically.

```
data/<activity>.json     one activity: metadata + a list of trips
tools/fetch_basemap.py   fetch detailed OSM water/land for each trip (Overpass)
tools/render_maps.py     draw each trip's route map -> maps/<activity>/<trip>.png
tools/build_site.py      generate <activity>.html pages + index.html
tools/routelib.py        shared helpers (polyline decode, formatting, scale)
basemap/                 cached vector basemap layers (+ per-trip OSM cache)
assets/style.css         shared styles
maps/<activity>/*.png    rendered route maps
index.html, *.html       the generated site (served by GitHub Pages)
```

## Adding a new activity (e.g. mountain biking)

1. Create `data/mountain-biking.json` (see the schema below).
2. Fetch its basemap layers:
   ```bash
   uv run --python 3.12 --with osm2geojson --with shapely --with geopandas \
     python tools/fetch_basemap.py --data data/mountain-biking.json
   ```
3. Render its maps:
   ```bash
   uv run --python 3.12 --with geopandas --with matplotlib --with shapely \
     python tools/render_maps.py --data data/mountain-biking.json
   ```
4. Rebuild the pages (regenerates every activity page + the index):
   ```bash
   python3 tools/build_site.py
   ```
5. Commit and push — GitHub Pages redeploys automatically.

## Dataset schema

```jsonc
{
  "activity": "Kayaking",                  // label shown as the activity type
  "title": "Kayaking trips",               // page <title> and heading
  "intro": "GPS routes from Strava ...",   // sub-heading line
  "duration_label": "Time on water",       // per-trip duration label
  "total_duration_label": "Total time on water",
  "route_color": "#e8602c",                // route line color
  "trips": [
    {
      "name": "Downtown paddle",
      "date": "2025-09-28",                // YYYY-MM-DD
      "location": "North Branch Chicago River",
      "distance_m": 11040.2,               // meters (mi/km derived)
      "duration_s": 6957,                  // seconds (h/m derived)
      "strava_id": "15968372062",          // optional; builds the "View on Strava" link
      "start": [41.906321, -87.651501],    // [lat, lng], sanity-checks the polyline
      "base_water": false,                 // true for open-lake routes (fills the lake under OSM detail)
      "polyline": "oyw~F|l~uO..."          // Strava encoded polyline
    }
  ]
}
```

`slug` fields are derived from names automatically but can be set explicitly.

### Where the trip data comes from

Each trip's encoded `polyline` and stats come from a Strava activity. Export
them however you prefer (for example the Strava API's activity and
`map.polyline` fields, or a GPX export converted to an encoded polyline) and
fill in the dataset JSON. No credentials or account linkage are stored in this
repo.

## Basemap

The vector basemap combines cached Chicago layers (`basemap/*.geojson`) with
per-trip OpenStreetMap water and parkland fetched on demand. It looks best in
and around Chicago; outside that area the Chicago layers simply contribute
nothing and the OSM water/parkland still provide context.

## Requirements

- Python 3.12 with [uv](https://docs.astral.sh/uv/) (pulls `geopandas`,
  `matplotlib`, `shapely`, `osm2geojson` per-command as shown above)
- No build step is needed to *view* the site — it is plain static HTML.

## Credits

Basemap data © OpenStreetMap contributors. Routes and statistics from Strava.
