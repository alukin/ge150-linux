"""Register ``ge150-mcp`` in Claude Code and/or Codex (``ge150ctl mcp-install``)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

NAME = "ge150"


def server_command(sim: bool = False) -> list[str]:
    """Absolute command that starts the server (the venv's script, else the module)."""
    script = Path(sys.executable).with_name("ge150-mcp")
    found = str(script) if script.exists() else shutil.which("ge150-mcp")
    command = [found] if found else [sys.executable, "-m", "ge150.mcp_server.server"]
    return [*command, "--sim"] if sim else command


def install_commands(client: str, sim: bool = False) -> list[list[str]]:
    """The CLI calls that (re)register the server for ``client`` ("claude" or "codex")."""
    command = server_command(sim)
    if client == "claude":
        return [["claude", "mcp", "remove", "--scope", "user", NAME],
                ["claude", "mcp", "add", "--scope", "user", NAME, "--", *command]]
    if client == "codex":
        return [["codex", "mcp", "remove", NAME], ["codex", "mcp", "add", NAME, "--", *command]]
    raise ValueError(f"unknown client {client!r}")


def install(client: str, sim: bool = False) -> str:
    if shutil.which(client) is None:
        raise FileNotFoundError(f"{client} is not installed")
    remove, add = install_commands(client, sim)
    subprocess.run(remove, capture_output=True, check=False)  # absent the first time
    result = subprocess.run(add, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(add[:3])}: {(result.stderr or result.stdout).strip()}")
    return " ".join(add)
