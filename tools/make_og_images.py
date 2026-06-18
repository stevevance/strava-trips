"""
Generate Open Graph link-preview images (1200x630) for each page.

For each activity dataset: a titled banner plus a montage of up to three of its
route maps -> og/<slug>.png. For the index: the site title plus one map per
activity -> og/index.png. These are referenced by the og:image / twitter:image
meta tags emitted by build_site.py.

Run after render_maps.py (it reads the rendered maps in maps/):
  uv run --python 3.12 --with pillow --with matplotlib python tools/make_og_images.py
"""
import os

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

import routelib as rl

W, H = 1200, 630
DARK = (44, 62, 80)
GRAY = (107, 122, 136)
LINE = (227, 230, 232)
BG = (255, 255, 255)
PAD = 44

OG_DIR = os.path.join(rl.ROOT, "og")
os.makedirs(OG_DIR, exist_ok=True)

# Reliable TrueType fonts via matplotlib's bundled DejaVu family.
_REG = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans"))
_BOLD = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold"))


def font(size, bold=False):
    return ImageFont.truetype(_BOLD if bold else _REG, size)


def map_thumb(activity_slug, trip_slug, side):
    """Center-crop a rendered map to a square (dropping its baked-in title/footer) and resize."""
    path = os.path.join(rl.MAPS_DIR, activity_slug, f"{trip_slug}.png")
    img = Image.open(path).convert("RGB")
    w, h = img.size
    # The map body sits between the title band (~top 8%) and footer (~bottom 4%).
    crop = int(w * 0.78)
    left = (w - crop) // 2
    top = int(h * 0.14)
    img = img.crop((left, top, left + crop, top + crop))
    return img.resize((side, side), Image.LANCZOS)


def paste_card(canvas, thumb, x, y):
    """Paste a thumbnail with a thin rounded border."""
    canvas.paste(thumb, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x, y, x + thumb.width, y + thumb.height), radius=14,
                        outline=LINE, width=2)


def activity_og(ds):
    n = len(ds["trips"])
    dist_mi = sum(t["distance_m"] for t in ds["trips"]) / 1609.344
    secs = sum(t["duration_s"] for t in ds["trips"])
    subtitle = f"{n} trips  ·  {dist_mi:.0f} mi  ·  {rl.fmt_duration(secs)}"

    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((PAD, 40), ds["title"], font=font(58, bold=True), fill=DARK)
    d.text((PAD, 116), subtitle, font=font(30), fill=GRAY)

    # Up to three map thumbnails in a row.
    picks = ds["trips"][:3]
    gap = 24
    side = (W - 2 * PAD - gap * (len(picks) - 1)) // len(picks)
    side = min(side, 360)
    row_w = side * len(picks) + gap * (len(picks) - 1)
    x = (W - row_w) // 2
    y = 185
    for t in picks:
        paste_card(canvas, map_thumb(ds["slug"], t["slug"], side), x, y)
        x += side + gap

    brand = "stevevance.github.io/strava-trips"
    bw = d.textlength(brand, font=font(24))
    d.text(((W - bw) / 2, 588), brand, font=font(24), fill=GRAY)

    out = os.path.join(OG_DIR, f"{ds['slug']}.png")
    canvas.save(out)
    print(f"  {out}")


def index_og(datasets):
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    title = "Strava trips"
    tw = d.textlength(title, font=font(64, bold=True))
    d.text(((W - tw) / 2, 44), title, font=font(64, bold=True), fill=DARK)
    sub = "GPS routes from my Strava activities, mapped on OpenStreetMap"
    sw = d.textlength(sub, font=font(28))
    d.text(((W - sw) / 2, 126), sub, font=font(28), fill=GRAY)

    # One map per activity, labeled.
    side = 360
    gap = 70
    row_w = side * len(datasets) + gap * (len(datasets) - 1)
    x = (W - row_w) // 2
    y = 185
    for ds in datasets:
        if not ds["trips"]:
            continue
        paste_card(canvas, map_thumb(ds["slug"], ds["trips"][0]["slug"], side), x, y)
        label = ds["activity"]
        lw = d.textlength(label, font=font(30, bold=True))
        d.text((x + (side - lw) / 2, y + side + 10), label, font=font(30, bold=True), fill=DARK)
        x += side + gap

    out = os.path.join(OG_DIR, "index.png")
    canvas.save(out)
    print(f"  {out}")


if __name__ == "__main__":
    datasets = [rl.load_dataset(p) for p in rl.list_datasets()]
    print(f"Generating OG images for {len(datasets)} activities + index")
    for ds in datasets:
        activity_og(ds)
    index_og(datasets)
