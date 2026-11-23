"""What the AI assistant may do with the pedal, chosen by the user (all allowed by default).

Kept in ``$XDG_CONFIG_HOME/ge150/ai_permissions.json`` and read on every tool call, so a
change applies at once, also to ``ge150-mcp`` running on its own. Reading the pedal is
always allowed; writing its memory still asks the user each time even when allowed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Permission:
    key: str
    group: str
    label: str
    detail: str


PERMISSIONS = (
    Permission("live", "Pedalera", "Cambiar el sonido en vivo",
               "Ajusta módulos, deshace y cambia de preset. No guarda nada."),
    Permission("edit_presets", "Presets guardados", "Proponer cambios de efectos",
               "En varios presets a la vez. Los revisas antes de aplicar."),
    Permission("rename", "Presets guardados", "Renombrar presets",
               "Dentro de una propuesta. La revisas antes de aplicar."),
    Permission("move", "Presets guardados", "Mover y reordenar presets",
               "Copia un preset a otra ranura, dentro de una propuesta."),
    Permission("save", "Presets guardados", "Guardar presets",
               "Guarda el sonido actual. Siempre te pregunta antes."),
    Permission("tone3000", "TONE3000", "Buscar en TONE3000",
               "Consulta IR de gabinete en internet."),
    Permission("load_ir", "TONE3000", "Cargar IR en la pedalera",
               "Guarda una IR en una ranura de usuario. Te pregunta antes."),
)
LABELS = {p.key: p.label for p in PERMISSIONS}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ge150" / "ai_permissions.json"


@dataclass
class Permissions:
    denied: frozenset[str] = frozenset()

    def allows(self, key: str) -> bool:
        return key not in self.denied

    def missing(self, keys: Iterable[str]) -> list[str]:
        """Labels of the ``keys`` that are not allowed."""
        return [LABELS.get(k, k) for k in keys if not self.allows(k)]


def load(path: Path | None = None) -> Permissions:
    """Unknown or unreadable file = everything allowed."""
    try:
        data = json.loads((path or config_path()).read_text())
    except (OSError, ValueError):
        return Permissions()
    if not isinstance(data, dict):
        return Permissions()
    return Permissions(frozenset(k for k in LABELS if data.get(k) is False))


def save(permissions: Permissions, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({p.key: permissions.allows(p.key) for p in PERMISSIONS},
                               indent=2) + "\n")
