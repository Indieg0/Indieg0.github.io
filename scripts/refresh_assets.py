#!/usr/bin/env python3
"""Refresh the cover / preview images used on the landing page from their sources.

Runs in CI (and locally). Keeps the page fully static — this just re-downloads
the latest images into assets/, and the workflow commits whatever changed:

  * App Store icons + a screenshot for each app   (iTunes lookup API)
  * Gumroad product covers                         (og:image on the product page)
  * ytdownload repo preview                        (GitHub Open Graph image)

All sources are reachable from datacenter IPs (no bot gate), so this works from
GitHub's runners. A failure on one source is logged and skipped; the others
still update.
"""
import json
import pathlib
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")
ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# App Store id -> (icon filename, screenshot filename)
APPS = {
    "1504476115": ("speedster-icon.jpg", "speedster-shot.png"),   # Speedster
    "6477580879": ("vinylover-icon.jpg", "vinylover-shot.png"),   # vinylover
}
# Gumroad product page -> cover filename
GUMROAD = {
    "https://kireal.gumroad.com/l/palettewallpapers": "wallpapers.png",
    "https://kireal.gumroad.com/l/indie-dev-cheatsheet": "cheatsheet.png",
}
# Static "always latest" endpoints -> filename
STATIC = {
    "https://opengraph.githubassets.com/1/Indieg0/ytdownload": "ytdownload.png",
}

updated, failed = 0, 0


def fetch(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read()


def save(url, name):
    global updated, failed
    try:
        data = fetch(url)
        if not data:
            raise ValueError("empty response")
        dest = ASSETS / name
        old = dest.read_bytes() if dest.exists() else b""
        dest.write_bytes(data)
        tag = "updated" if data != old else "unchanged"
        print(f"  {name:22} {tag}  ({len(data)} bytes)")
        updated += 1
    except Exception as ex:
        print(f"  {name:22} FAILED: {ex}", file=sys.stderr)
        failed += 1


def refresh_apps():
    print("App Store:")
    ids = ",".join(APPS)
    data = json.loads(fetch(f"https://itunes.apple.com/lookup?id={ids}&country=ua")
                      .decode("utf-8", "replace"))
    for item in data.get("results", []):
        tid = str(item.get("trackId"))
        if tid not in APPS:
            continue
        icon_name, shot_name = APPS[tid]
        icon = item.get("artworkUrl512") or item.get("artworkUrl100")
        if icon:
            save(icon, icon_name)
        shots = item.get("screenshotUrls") or item.get("ipadScreenshotUrls") or []
        if shots:
            save(shots[0], shot_name)


def refresh_gumroad():
    print("Gumroad:")
    for page, name in GUMROAD.items():
        try:
            html = fetch(page).decode("utf-8", "replace")
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if not m:
                raise ValueError("og:image not found")
            save(m.group(1), name)
        except Exception as ex:
            global failed
            print(f"  {name:22} FAILED: {ex}", file=sys.stderr)
            failed += 1


def refresh_static():
    print("Static previews:")
    for url, name in STATIC.items():
        save(url, name)


def main():
    refresh_apps()
    refresh_gumroad()
    refresh_static()
    print(f"\nDone: {updated} fetched, {failed} failed.")
    if updated == 0:
        sys.exit("ERROR: every source failed — not touching assets.")


if __name__ == "__main__":
    main()
