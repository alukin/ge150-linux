#!/usr/bin/env python3
"""Download candidate photos of the real gear from Wikimedia Commons.

    python3 -I tools/fetch_photos.py OUTDIR [--only gid,gid] [--query gid="text"]

For every gear entry of ``src/ge150/data/gear.json`` with a ``query``, searches Commons
(file namespace, bitmaps only) and saves up to ``--per`` 500 px thumbnails as
``OUTDIR/<gid>/<n>.jpg`` with their author, licence and source page in ``meta.json``.
Pick the good ones with ``tools/pick_photo.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "ge150-linux-photo-fetch/0.1"
GEAR = Path(__file__).resolve().parents[1] / "src" / "ge150" / "data" / "gear.json"


def _get(url: str, tries: int = 5) -> bytes:
    """Fetch with curl: Wikimedia answers 429 to Python's HTTP client but not to curl."""
    for attempt in range(tries):
        result = subprocess.run(
            ["curl", "-sS", "-L", "-A", AGENT, "-w", "\n%{http_code}", url],
            capture_output=True, check=True, timeout=60)
        body, _, code = result.stdout.rpartition(b"\n")
        if code == b"200":
            return body
        if code != b"429" or attempt == tries - 1:
            raise OSError(f"HTTP {code.decode()} for {url}")
        time.sleep(10 * (attempt + 1))  # rate limited: back off
    raise AssertionError("unreachable")


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def search(query: str, limit: int) -> list[dict[str, str]]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
        "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": str(limit * 2),
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": "500",
    }
    data = json.loads(_get(f"{API}?{urllib.parse.urlencode(params)}"))
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p["index"])
    found = []
    for page in pages:
        info = page["imageinfo"][0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        found.append({
            "title": page["title"],
            "thumb": info["thumburl"].replace("//thumb.wikimedia.org/", "//upload.wikimedia.org/")
            .split("?")[0],
            "page": info["descriptionurl"],
            "license": meta.get("LicenseShortName", {}).get("value", "?"),
            "author": _plain(meta.get("Artist", {}).get("value", "?")),
        })
    return found[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--per", type=int, default=4)
    parser.add_argument("--only", default="", help="comma separated gear ids")
    parser.add_argument("--query", action="append", default=[], help='gid="search text"')
    args = parser.parse_args()
    gear = json.loads(GEAR.read_text())["gear"]
    overrides = dict(q.split("=", 1) for q in args.query)
    only = set(filter(None, args.only.split(","))) | set(overrides)
    for gid, entry in gear.items():
        query = overrides.get(gid, entry["query"])
        if not query or (only and gid not in only):
            continue
        target = args.out / gid
        if (target / "meta.json").exists() and gid not in overrides:
            continue  # already fetched
        target.mkdir(parents=True, exist_ok=True)
        try:
            hits = search(query, args.per)
        except OSError as exc:
            print(f"{gid}: search failed ({exc})")
            continue
        for n, hit in enumerate(hits):
            try:
                (target / f"{n}.jpg").write_bytes(_get(hit["thumb"]))
            except OSError as exc:
                print(f"{gid}: {exc}")
            time.sleep(3)
        (target / "meta.json").write_text(json.dumps({"query": query, "hits": hits}, indent=1))
        print(f"{gid:18} {len(hits)}  {query}")
        time.sleep(4)


if __name__ == "__main__":
    main()
