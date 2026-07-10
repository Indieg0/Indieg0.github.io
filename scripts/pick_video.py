#!/usr/bin/env python3
"""Feature the newest channel upload longer than MIN_SECONDS in index.html.

Durations are not in the RSS feed, so they must be resolved per video.

Two sources, in order:
  1. YouTube Data API v3, if YOUTUBE_API_KEY is set. One request covers every
     candidate. This is the only source that works from a datacenter IP.
  2. Scraping the watch page. Works from an ordinary residential IP, but from
     CI runners YouTube serves a "Sign in to confirm you're not a bot"
     interstitial that contains no duration.

The key is read from the environment — never hardcoded. If not a single
duration can be resolved, the script exits non-zero rather than quietly
leaving the page stale.
"""
import html as htmllib
import json
import os
import pathlib
import re
import sys
import urllib.request

CHANNEL_ID = "UCsI3yL_FWMJxbvaXCWQvjLQ"
MIN_SECONDS = 180          # "more than 3 minutes"
MAX_CHECK = 12             # only inspect the newest N feed entries

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"


def get_text(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def iso8601_to_seconds(s):
    """PT1H2M3S -> 3723"""
    m = re.fullmatch(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    h, mi, sec = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + sec


def durations_via_data_api(vids, key):
    """One request -> {videoId: seconds}. Requires a YouTube Data API v3 key."""
    url = ("https://www.googleapis.com/youtube/v3/videos"
           f"?part=contentDetails&id={','.join(vids)}&key={key}")
    data = json.loads(get_text(url))
    out = {}
    for item in data.get("items", []):
        secs = iso8601_to_seconds(item["contentDetails"].get("duration"))
        if secs:
            out[item["id"]] = secs
    return out


def duration_via_watch_page(vid):
    m = re.search(r'"lengthSeconds":"(\d+)"',
                  get_text(f"https://www.youtube.com/watch?v={vid}"))
    return int(m.group(1)) if m else None


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

    candidates = [(re.search(r"<yt:videoId>([^<]+)", e).group(1),
                   htmllib.unescape(re.search(r"<title>([^<]+)", e).group(1)))
                  for e in entries]

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    lengths = {}
    if key:
        try:
            lengths = durations_via_data_api([v for v, _ in candidates], key)
            print(f"Resolved {len(lengths)} durations via YouTube Data API.", file=sys.stderr)
        except Exception as ex:
            print(f"Data API failed ({ex}); falling back to watch pages.", file=sys.stderr)
    else:
        print("No YOUTUBE_API_KEY set; falling back to watch pages.", file=sys.stderr)

    for vid, title in candidates:
        secs = lengths.get(vid)
        if secs is None:
            try:
                secs = duration_via_watch_page(vid)
            except Exception as ex:
                print(f"  {vid}: watch page failed: {ex}", file=sys.stderr)
        if secs is None:
            print(f"{vid}  duration unknown  {title}", file=sys.stderr)
            continue
        lengths[vid] = secs
        print(f"{vid}  {secs:>5}s  {title}", file=sys.stderr)
        if secs > MIN_SECONDS:
            update_index(vid, title)
            return

    if not lengths:
        sys.exit("ERROR: could not resolve the duration of any video "
                 "(set YOUTUBE_API_KEY when running from CI) — "
                 "refusing to leave the page silently stale.")
    print(f"No video over {MIN_SECONDS}s among the {len(lengths)} checked; "
          "index.html left unchanged.", file=sys.stderr)


if __name__ == "__main__":
    main()
