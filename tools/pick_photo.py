#!/usr/bin/env python3
"""Review and install gear photo candidates downloaded by ``tools/fetch_photos.py``.

    python3 tools/pick_photo.py sheet CANDIDATES OUT.png [gid,gid...]   # contact sheet
    python3 tools/pick_photo.py pick CANDIDATES gid=N [gid=other:N ...] # install choices

``pick`` copies ``CANDIDATES/<gid>/<N>.jpg`` to ``src/ge150/data/photos/<gid>.jpg``
(downscaled to 640 px at most) and records the author, licence and source page in
``src/ge150/data/photos/CREDITS.md``. ``gid=other:N`` uses a candidate of another gear
(e.g. the same amp for its clean and drive models). Needs PySide6 (run with the project's venv).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "src" / "ge150" / "data" / "photos"
CREDITS = PHOTOS / "CREDITS.md"
HEADER = """# Gear photos

Photos of the original gear each model is based on. Wikimedia Commons photos belong to
their authors under the licence listed for each one; product photos (licence "©") belong
to the manufacturer or shop whose page is linked. None of them is covered by the project's
MIT licence. Brand and product names belong to their owners.

| Gear | Photo | Author | Licence |
|---|---|---|---|
"""


def sheet(candidates: Path, out: Path, only: list[str]) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dirs = sorted(d for d in candidates.iterdir() if d.is_dir() and (not only or d.name in only))
    cell, cols = 200, 4  # one row per gear: label + up to 3 candidates
    img = QImage(cols * cell, max(1, len(dirs)) * cell, QImage.Format.Format_RGB32)
    img.fill(QColor("#1e2228"))
    p = QPainter(img)
    for row, folder in enumerate(dirs):
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(4, row * cell, cell - 8, cell), int(Qt.AlignmentFlag.AlignCenter
                   | Qt.TextFlag.TextWordWrap), folder.name)
        for n in range(3):
            path = folder / f"{n}.jpg"
            if not path.exists():
                continue
            photo = QImage(str(path))
            if photo.isNull():
                continue
            box = QRectF((n + 1) * cell + 4, row * cell + 4, cell - 8, cell - 24)
            scaled = photo.scaled(box.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            p.drawImage(box.topLeft(), scaled)
            p.setPen(QColor("#ffcc66"))
            p.drawText(QRectF(box.left(), box.bottom() + 2, 30, 18), str(n))
    p.end()
    img.save(str(out))
    del app


def trim(image: QImage, tolerance: int = 24, margin: float = 0.04) -> QImage:
    """Crop the plain background around a product photo (colour of the corners)."""
    from PySide6.QtCore import QRect, Qt

    small = image.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
    w, h = small.width(), small.height()
    corners = [small.pixelColor(x, y) for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    bg = [sum(c.getRgb()[i] for c in corners) // 4 for i in range(3)]

    def differs(x: int, y: int) -> bool:
        rgb = small.pixelColor(x, y).getRgb()
        return max(abs(rgb[i] - bg[i]) for i in range(3)) > tolerance

    cols = [x for x in range(w) if any(differs(x, y) for y in range(0, h, 2))]
    rows = [y for y in range(h) if any(differs(x, y) for x in range(0, w, 2))]
    if not cols or not rows:
        return image
    sx, sy = image.width() / w, image.height() / h
    left, right = min(cols) * sx, (max(cols) + 1) * sx
    top, bottom = min(rows) * sy, (max(rows) + 1) * sy
    pad = margin * max(right - left, bottom - top)
    box = QRect(int(max(0, left - pad)), int(max(0, top - pad)),
                int(min(image.width(), right + pad) - max(0, left - pad)),
                int(min(image.height(), bottom + pad) - max(0, top - pad)))
    return image.copy(box)


def pick(candidates: Path, choices: list[str]) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    PHOTOS.mkdir(parents=True, exist_ok=True)
    rows: dict[str, str] = {}
    if CREDITS.exists():
        for line in CREDITS.read_text().splitlines():
            if line.startswith("| `"):
                rows[line.split("`")[1]] = line
    for choice in choices:
        gid, source = choice.split("=")
        folder, _, n = source.rpartition(":")
        folder = folder or gid
        meta = json.loads((candidates / folder / "meta.json").read_text())
        hit = meta["hits"][int(n)]
        image = trim(QImage(str(candidates / folder / f"{n}.jpg")))
        if image.width() > 640 or image.height() > 640:
            image = image.scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        image.save(str(PHOTOS / f"{gid}.jpg"), "JPG", 88)
        author = " ".join(hit["author"].split()).replace("|", "/")[:80]
        rows[gid] = (f"| `{gid}` | [{hit['title']}]({hit['page']}) | {author} | "
                     f"{hit['license']} |")
        print(f"{gid}: {hit['title']} ({hit['license']})")
    CREDITS.write_text(HEADER + "\n".join(rows[k] for k in sorted(rows)) + "\n")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("sheet", "pick"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "sheet":
        only = sys.argv[4].split(",") if len(sys.argv) > 4 else []
        sheet(Path(sys.argv[2]), Path(sys.argv[3]), only)
    else:
        pick(Path(sys.argv[2]), sys.argv[3:])


if __name__ == "__main__":
    main()
