#!/usr/bin/env python3
"""Download product photos from manufacturer or shop pages, as photo candidates.

    python3 -I tools/fetch_product_photo.py OUTDIR gid=URL [gid=URL ...] [--per 4]

For every ``gid=URL`` the page is fetched with curl and the product images are taken from
``og:image`` / ``twitter:image`` and the page's ``<img>`` tags (logos, icons and tiny
images are skipped). They are saved as ``OUTDIR/<gid>/<n>.jpg`` with a ``meta.json`` in the
same format as ``tools/fetch_photos.py``, so ``tools/pick_photo.py`` can review and
install them. These photos belong to the site owner: the credit records the page.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
SKIP = re.compile(r"logo|icon|share|sprite|avatar|banner|flag|payment|/s\.png|\.svg|\.gif",
                  re.IGNORECASE)
META = re.compile(r'<meta[^>]+(?:property|name)="(?:og:image|twitter:image)"[^>]+content="([^"]+)"',
                  re.IGNORECASE)
IMG = re.compile(r'<img[^>]+(?:data-src|src)="([^"]+\.(?:jpe?g|png|webp)[^"]*)"', re.IGNORECASE)


def curl(url: str, referer: str = "") -> bytes:
    command = ["curl", "-sS", "-L", "--compressed", "-A", AGENT, "--max-time", "60"]
    if referer:
        command += ["-e", referer]
    result = subprocess.run([*command, "-w", "\n%{http_code}", url], capture_output=True,
                            check=True, timeout=90)
    body, _, code = result.stdout.rpartition(b"\n")
    if code != b"200":
        raise OSError(f"HTTP {code.decode()} for {url}")
    return body


def image_urls(page_url: str, page: str) -> list[str]:
    found = [*META.findall(page), *IMG.findall(page)]
    urls: list[str] = []
    for raw in found:
        url = urllib.parse.urljoin(page_url, html.unescape(raw))
        key = url.split("?")[0]
        if SKIP.search(url) or any(u.split("?")[0] == key for u in urls):
            continue
        urls.append(url)
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("pages", nargs="+", help="gid=URL")
    parser.add_argument("--per", type=int, default=4)
    args = parser.parse_args()
    for item in args.pages:
        gid, url = item.split("=", 1)
        site = urllib.parse.urlparse(url).netloc.removeprefix("www.")
        target = args.out / gid
        target.mkdir(parents=True, exist_ok=True)
        try:
            page = curl(url).decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"{gid}: page failed ({exc})")
            continue
        hits = []
        for image in image_urls(url, page):
            if len(hits) == args.per:
                break
            try:
                data = curl(image, referer=url)
            except (OSError, subprocess.SubprocessError):
                continue
            if len(data) < 8000:  # thumbnails and placeholders
                continue
            (target / f"{len(hits)}.jpg").write_bytes(data)
            name = urllib.parse.unquote(Path(urllib.parse.urlparse(image).path).name)
            hits.append({"title": f"{site}: {name}", "thumb": image, "page": url,
                         "license": f"© {site} (product photo)", "author": site})
            time.sleep(0.5)
        (target / "meta.json").write_text(json.dumps({"query": url, "hits": hits}, indent=1))
        print(f"{gid:20} {len(hits)}  {url}")


if __name__ == "__main__":
    main()
