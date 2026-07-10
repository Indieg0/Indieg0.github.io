#!/usr/bin/env python3
"""Temporary probe: which YouTube duration sources work from a CI runner?"""
import json, re, urllib.request, urllib.error

VID = "ynq9xIqH5OY"  # 803s
KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")

CLIENTS = {
    "WEB": {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "en"},
    "MWEB": {"clientName": "MWEB", "clientVersion": "2.20240101.00.00", "hl": "en"},
    "IOS": {"clientName": "IOS", "clientVersion": "19.09.3", "hl": "en"},
    "TVHTML5": {"clientName": "TVHTML5", "clientVersion": "7.20240101.16.00", "hl": "en"},
    "WEB_EMBEDDED_PLAYER": {"clientName": "WEB_EMBEDDED_PLAYER", "clientVersion": "1.20240101.00.00", "hl": "en"},
    "ANDROID_VR": {"clientName": "ANDROID_VR", "clientVersion": "1.60.19", "androidSdkVersion": 32, "hl": "en"},
}

for name, client in CLIENTS.items():
    try:
        body = json.dumps({"videoId": VID, "context": {"client": client}}).encode()
        req = urllib.request.Request(
            f"https://www.youtube.com/youtubei/v1/player?key={KEY}", data=body,
            headers={"Content-Type": "application/json", "User-Agent": UA})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
        ps = d.get("playabilityStatus", {})
        secs = (d.get("videoDetails") or {}).get("lengthSeconds")
        print(f"innertube {name:22} len={secs!r:8} status={ps.get('status')!r} reason={str(ps.get('reason'))[:45]!r}")
    except Exception as e:
        print(f"innertube {name:22} ERROR {e}")

for label, url in [("embed-page", f"https://www.youtube.com/embed/{VID}"),
                   ("watch-page", f"https://www.youtube.com/watch?v={VID}")]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'"lengthSeconds":"(\d+)"', html)
        m2 = re.search(r'itemprop="duration" content="([^"]+)"', html)
        print(f"{label:32} len={m.group(1) if m else None!r:8} itemprop={m2.group(1) if m2 else None!r} bytes={len(html)}")
    except Exception as e:
        print(f"{label:32} ERROR {e}")
