#!/usr/bin/env python3
"""Feature the newest channel upload longer than MIN_SECONDS in index.html.

Durations are not in the RSS feed, so each candidate's length is resolved via
YouTube's innertube `player` JSON endpoint. That endpoint is used in preference
to scraping the watch page: from datacenter IPs (like GitHub's runners) YouTube
serves a consent/bot interstitial that contains no `lengthSeconds`.

If not a single duration can be resolved, the script exits non-zero rather than
quietly leaving the page stale.
"""
import html as htmllib
import json
import pathlib
import re
import sys
import urllib.request

CHANNEL_ID = "UCsI3yL_FWMJxbvaXCWQvjLQ"
MIN_SECONDS = 180          # "more than 3 minutes"
MAX_CHECK = 12             # only inspect the newest N feed entries

INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # public web client key
INNERTUBE_CLIENT = {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "en"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"


def _open(req):
    return urllib.request.urlopen(req, timeout=30).read()


def get_text(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return _open(req).decode("utf-8", "replace")


def duration_via_innertube(vid):
    body = json.dumps({"videoId": vid, "context": {"client": INNERTUBE_CLIENT}}).encode()
    req = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/player?key={INNERTUBE_KEY}",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA})
    data = json.loads(_open(req))
    secs = (data.get("videoDetails") or {}).get("lengthSeconds")
    return int(secs) if secs else None


def duration_via_watch_page(vid):
    m = re.search(r'"lengthSeconds":"(\d+)"',
                  get_text(f"https://www.youtube.com/watch?v={vid}"))
    return int(m.group(1)) if m else None


def duration(vid):
    """Resolve a video's length in seconds, trying the JSON API then the page."""
    for name, fn in (("innertube", duration_via_innertube),
                     ("watch-page", duration_via_watch_page)):
        try:
            secs = fn(vid)
            if secs:
                return secs
        except Exception as ex:
            print(f"  {vid}: {name} failed: {ex}", file=sys.stderr)
    return None


def update_index(vid, title):
    html = INDEX.read_text(encoding="utf-8")
    before = html
    html = re.sub(r"(youtube-nocookie\.com/embed/)[A-Za-z0-9_-]+",
                  lambda m: m.group(1) + vid, html, count=1)
    safe = htmllib.escape(title)
    html = re.sub(r'(<span class="vt">).*?(</span>)',
                  lambda m: m.group(1) + safe + m.group(2), html, count=1, flags=re.S)
    if html == before:
        print(f"Already featuring {vid} — no change.")
        return
    INDEX.write_text(html, encoding="utf-8")
    print(f"Featured video set to {vid} — {title}")


def main():
    feed = get_text(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}")
    entries = re.findall(r"<entry>.*?</entry>", feed, re.S)[:MAX_CHECK]
    if not entries:
        sys.exit("ERROR: channel feed returned no entries.")

    resolved = 0
    for entry in entries:
        vid = re.search(r"<yt:videoId>([^<]+)", entry).group(1)
        title = htmllib.unescape(re.search(r"<title>([^<]+)", entry).group(1))
        secs = duration(vid)
        if secs is None:
            print(f"{vid}  duration unknown  {title}", file=sys.stderr)
            continue
        resolved += 1
        print(f"{vid}  {secs:>5}s  {title}", file=sys.stderr)
        if secs > MIN_SECONDS:
            update_index(vid, title)
            return

    # Distinguish "everything is short" from "we couldn't read any durations".
    if resolved == 0:
        sys.exit("ERROR: could not resolve the duration of any video — "
                 "refusing to leave the page silently stale.")
    print(f"No video over {MIN_SECONDS}s among the {resolved} checked; "
          "index.html left unchanged.", file=sys.stderr)


if __name__ == "__main__":
    main()
