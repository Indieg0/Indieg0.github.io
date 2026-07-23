#!/usr/bin/env python3
"""Refresh the cover / preview images used on the landing page from their sources.

Runs in CI (and locally). Keeps the page fully static — this just re-downloads
the latest images into assets/, and the workflow commits whatever changed:

  * App Store icons + a screenshot for each app   (iTunes lookup API)
  * Gumroad product covers                         (og:image on the product page)
  * ytdownload repo preview                        (GitHub Open Graph image)

Change detection is by SOURCE URL, not raw bytes: Apple's CDN returns
byte-different data for the same image on each request, which would otherwise
produce a spurious commit on every run. App Store artwork/screenshot URLs and
Gumroad og:image URLs are content-addressed — they only change when the app or
product is actually updated — so we re-download only when the URL changes. The
GitHub preview has a fixed URL, so for it we fall back to a byte comparison.

The resolved URLs are tracked in assets/sources.json. All sources are reachable
from datacenter IPs (no bot gate). Fails loudly only if nothing resolves.
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
MANIFEST = ASSETS / "sources.json"

APPS = {
    "1504476115": ("speedster-icon.jpg", "speedster-shot.png"),   # Speedster
    "6477580879": ("vinylover-icon.jpg", "vinylover-shot.png"),   # vinylover
}
GUMROAD = {
    "https://kireal.gumroad.com/l/palettewallpapers": "wallpapers.png",
    "https://kireal.gumroad.com/l/indie-dev-cheatsheet": "cheatsheet.png",
}
STATIC = {
    "https://opengraph.githubassets.com/1/Indieg0/ytdownload": "ytdownload.png",
}

manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
resolved, failed, wrote = 0, 0, 0


def fetch(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read()


def by_url(name, url):
    """Download only if the content-addressed URL changed since last time."""
    global resolved, failed, wrote
    resolved += 1
    dest = ASSETS / name
    if manifest.get(name) == url and dest.exists():
        print(f"  {name:22} unchanged")
        return
    try:
        data = fetch(url)
        if not data:
            raise ValueError("empty response")
        dest.write_bytes(data)
        manifest[name] = url
        wrote += 1
        print(f"  {name:22} updated  ({len(data)} bytes)")
    except Exception as ex:
        print(f"  {name:22} FAILED: {ex}", file=sys.stderr)
        failed += 1


def by_bytes(name, url):
    """Fixed URL — fetch and write only if the bytes actually differ."""
    global resolved, failed, wrote
    resolved += 1
    dest = ASSETS / name
    try:
        data = fetch(url)
        if not data:
            raise ValueError("empty response")
        if dest.exists() and dest.read_bytes() == data:
            print(f"  {name:22} unchanged")
            return
        dest.write_bytes(data)
        wrote += 1
        print(f"  {name:22} updated  ({len(data)} bytes)")
    except Exception as ex:
        print(f"  {name:22} FAILED: {ex}", file=sys.stderr)
        failed += 1


def refresh_apps():
    print("App Store:")
    try:
        data = json.loads(fetch(
            f"https://itunes.apple.com/lookup?id={','.join(APPS)}&country=ua"
        ).decode("utf-8", "replace"))
    except Exception as ex:
        print(f"  lookup FAILED: {ex}", file=sys.stderr)
        return
    for item in data.get("results", []):
        tid = str(item.get("trackId"))
        if tid not in APPS:
            continue
        icon_name, shot_name = APPS[tid]
        icon = item.get("artworkUrl512") or item.get("artworkUrl100")
        if icon:
            by_url(icon_name, icon)
        shots = item.get("screenshotUrls") or item.get("ipadScreenshotUrls") or []
        if shots:
            by_url(shot_name, shots[0])


def refresh_gumroad():
    print("Gumroad:")
    for page, name in GUMROAD.items():
        try:
            html = fetch(page).decode("utf-8", "replace")
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if not m:
                raise ValueError("og:image not found")
        except Exception as ex:
            global failed
            print(f"  {name:22} FAILED: {ex}", file=sys.stderr)
            failed += 1
            continue
        by_url(name, m.group(1))


def refresh_static():
    print("Static previews:")
    for url, name in STATIC.items():
        by_bytes(name, url)


def main():
    refresh_apps()
    refresh_gumroad()
    refresh_static()
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"\nDone: {resolved} resolved, {wrote} written, {failed} failed.")
    if resolved and failed == resolved:
        sys.exit("ERROR: every source failed — leaving assets untouched.")


if __name__ == "__main__":
    main()
