#!/usr/bin/env python3
"""Feature the newest channel upload longer than MIN_SECONDS in index.html.

Runs in CI (GitHub Actions), where direct YouTube access is reliable — unlike
the browser, which can't read video durations (CORS + huge watch pages). The
page itself stays fully static; this script just rewrites the embedded video id
and title, and the workflow commits the change when it differs.
"""
import html as htmllib
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


def get(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def update_index(vid, title):
    html = INDEX.read_text(encoding="utf-8")
    html = re.sub(r"(youtube-nocookie\.com/embed/)[A-Za-z0-9_-]+",
                  lambda m: m.group(1) + vid, html, count=1)
    safe = htmllib.escape(title)
    html = re.sub(r'(<span class="vt">).*?(</span>)',
                  lambda m: m.group(1) + safe + m.group(2), html, count=1, flags=re.S)
    INDEX.write_text(html, encoding="utf-8")
    print(f"Featured video set to {vid} — {title}")


def main():
    feed = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}")
    for entry in re.findall(r"<entry>.*?</entry>", feed, re.S)[:MAX_CHECK]:
        vid = re.search(r"<yt:videoId>([^<]+)", entry).group(1)
        title = htmllib.unescape(re.search(r"<title>([^<]+)", entry).group(1))
        try:
            page = get(f"https://www.youtube.com/watch?v={vid}")
        except Exception as ex:  # transient fetch error — skip this one
            print(f"skip {vid}: fetch error: {ex}", file=sys.stderr)
            continue
        m = re.search(r'"lengthSeconds":"(\d+)"', page)
        if not m:
            print(f"skip {vid}: duration not found", file=sys.stderr)
            continue
        secs = int(m.group(1))
        print(f"{vid}  {secs:>5}s  {title}", file=sys.stderr)
        if secs > MIN_SECONDS:
            update_index(vid, title)
            return
    print("No qualifying video (>3 min) found; index.html left unchanged.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
