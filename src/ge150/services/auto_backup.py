"""Automatic full backups before the editor writes many presets at once.

Before «Aplicar» (and its undo) in the «Asistente» tab, the whole pedal is read (the same
read-only dumps as «Backup completo», so the sound being heard is not touched) and saved as
a vendor-compatible ``.mbf`` in ``$XDG_DATA_HOME/ge150/backups/``. «Restaurar backup» brings
it back. Only the newest :data:`KEEP` automatic backups are kept; other files there (the
user's own) are never touched.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from ge150.formats import mbf
from ge150.services import backup as backup_service
from ge150.services.editor import Editor

KEEP = 20
PREFIX = "auto-"


def backup_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "ge150" / "backups"


def save_before(editor: Editor, reason: str) -> Path:
    """Read the whole pedal and save it; raises if the backup is not complete."""
    data = backup_service.create_backup(editor)
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = directory / f"{PREFIX}{stamp}-{reason}.mbf"
    n = 1
    while path.exists():  # two in the same second
        n += 1
        path = directory / f"{PREFIX}{stamp}-{reason}-{n}.mbf"
    tmp = path.with_suffix(".tmp")
    mbf.save(tmp, data)
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    prune(directory)
    return path


def prune(directory: Path, keep: int = KEEP) -> list[Path]:
    """Delete the oldest automatic backups beyond ``keep``; returns what was deleted."""
    autos = sorted(directory.glob(f"{PREFIX}*.mbf"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    old = autos[keep:]
    for path in old:
        path.unlink(missing_ok=True)
    return old


def short(path: Path) -> str:
    """The path with ``~`` for the home folder, for messages."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)
