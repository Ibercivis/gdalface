"""
Probe NASA's public image archive for ISS frames that are actually night shots.

Run inside the web container, where Pillow and network access are both present:

    docker compose -f docker-compose.local.yml exec web \
        python local_dev/find_night_frames.py ISS046-E-13036 ISS069-E-27396

A night frame over a city is almost entirely black with small bright points,
so mean luminance and the fraction of near-black pixels separate night from
day reliably without needing the metadata API (which requires a key).
"""

import io
import sys

import requests
from PIL import Image

BASE = "https://eol.jsc.nasa.gov/DatabaseImages"


def check(frame_id):
    mission = frame_id.split("-")[0]
    url = f"{BASE}/ESC/small/{mission}/{frame_id}.JPG"
    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as error:
        return frame_id, None, f"error: {error}"
    if response.status_code != 200:
        return frame_id, None, f"http {response.status_code}"
    if not response.headers.get("Content-Type", "").startswith("image/"):
        return frame_id, None, "not an image"

    grey = Image.open(io.BytesIO(response.content)).convert("L")
    pixels = list(grey.getdata())
    mean = sum(pixels) / len(pixels)
    dark = sum(1 for value in pixels if value < 30) / len(pixels)
    # City lights: a useful frame is mostly black but has bright points in it.
    # An all-black frame passes the darkness test and is worthless to
    # georeference, so it has to be excluded explicitly.
    lit = sum(1 for value in pixels if value > 150) / len(pixels)
    if mean < 45 and dark > 0.75 and lit > 0.002:
        verdict = "NIGHT+LIGHTS"
    elif mean < 45 and dark > 0.75:
        verdict = "night, too dark"
    else:
        verdict = "day"
    return frame_id, (mean, dark, lit), verdict


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for frame_id in sys.argv[1:]:
        name, stats, verdict = check(frame_id)
        if stats is None:
            print(f"{name:20s} {verdict}")
        else:
            mean, dark, lit = stats
            print(
                f"{name:20s} mean={mean:6.1f} dark={dark:.2f} lit={lit:.4f}  {verdict}"
            )


if __name__ == "__main__":
    main()
