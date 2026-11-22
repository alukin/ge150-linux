"""Share the GE150 editor's pedal with ``ge150-mcp`` (docs/plan-ia-tone3000.md §3).

Only one program can own the USB device. While the editor runs it serves its
:class:`~ge150.mcp_server.tools.PedalTools` on ``127.0.0.1`` (random port, random token) and
writes ``$XDG_RUNTIME_DIR/ge150/mcp.json`` (mode 0600). ``ge150-mcp`` finds that file and
forwards every tool call to the editor through :class:`RemoteTools`, so the AI and the GUI
edit the same sound and the GUI shows each change at once. Plain JSON over HTTP, standard
library only: the editor does not need the ``mcp`` package.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import tempfile
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ge150.mcp_server.tools import ToolError

#: Methods a client may call (everything else is refused).
TOOLS = ("get_catalog", "get_current_patch", "get_guitar", "list_presets", "get_preset",
         "list_user_irs", "get_settings", "set_module", "apply_patch", "undo", "select_preset",
         "save_preset", "tone3000_search", "tone3000_get", "load_tone3000_ir")
#: Long enough for the user to answer a confirmation or pick an IR in the browser.
CALL_TIMEOUT_S = 330


def discovery_path() -> Path:
    """``$XDG_RUNTIME_DIR/ge150/mcp.json``. AI clients may start ``ge150-mcp`` with a trimmed
    environment (Codex drops ``XDG_RUNTIME_DIR``), so also derive it from the user id."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        run = Path(f"/run/user/{os.getuid()}")
        base = str(run) if run.is_dir() else tempfile.gettempdir()
    return Path(base) / "ge150" / "mcp.json"


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    tools: Any
    token: str
    on_call: Callable[[str], None] | None


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def do_POST(self) -> None:
        given = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(given.encode(), self.server.token.encode()):
            self._reply(401, {"error": "bad token"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            request = json.loads(self.rfile.read(length))
            name, args = str(request["tool"]), dict(request.get("args") or {})
        except (ValueError, KeyError, TypeError):
            self._reply(400, {"error": "bad request"})
            return
        if name not in TOOLS:
            self._reply(404, {"error": f"unknown tool {name}"})
            return
        if self.server.on_call is not None:
            self.server.on_call(name)
        try:
            result = getattr(self.server.tools, name)(**args)
        except ToolError as exc:
            self._reply(200, {"error": str(exc)})
        except TypeError as exc:
            self._reply(200, {"error": f"bad arguments: {exc}"})
        except Exception as exc:  # the editor keeps running; the AI sees the reason
            self._reply(200, {"error": f"{type(exc).__name__}: {exc}"})
        else:
            self._reply(200, {"result": result})

    def _reply(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class LocalServer:
    """The editor side: serve ``tools`` until :meth:`stop`."""

    def __init__(self, tools: Any, on_call: Callable[[str], None] | None = None,
                 path: Path | None = None) -> None:
        self.path = path or discovery_path()
        self.httpd = _Server(("127.0.0.1", 0), _Handler)
        self.httpd.tools, self.httpd.on_call = tools, on_call
        self.httpd.token = secrets.token_urlsafe(32)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="ge150-mcp-bridge",
                                       daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_port}/call"

    def start(self) -> LocalServer:
        self.thread.start()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"url": self.url, "token": self.httpd.token, "pid": os.getpid()}, handle)
        return self

    def stop(self) -> None:
        try:
            if json.loads(self.path.read_text()).get("pid") == os.getpid():
                self.path.unlink()
        except (OSError, ValueError):
            pass
        self.httpd.shutdown()
        self.httpd.server_close()


class RemoteTools:
    """The ``ge150-mcp`` side: the same methods as ``PedalTools``, run by the editor."""

    def __init__(self, url: str, token: str) -> None:
        self.url, self.token = url, token

    def call(self, tool: str, timeout: float = CALL_TIMEOUT_S, **args: Any) -> Any:
        body = json.dumps({"tool": tool, "args": args}).encode()
        request = urllib.request.Request(self.url, body, {
            "Content-Type": "application/json", "Authorization": f"Bearer {self.token}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise ToolError(f"GE150 editor: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ToolError(f"the GE150 editor does not answer ({exc}); is it still open?") \
                from exc
        if "error" in data:
            raise ToolError(str(data["error"]))
        return data["result"]

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name not in TOOLS:
            raise AttributeError(name)
        return lambda *args, **kwargs: self.call(name, **_named(name, args, kwargs))


#: Positional parameter names, so ``tools.set_module("DS", False)`` works like PedalTools.
_PARAMS = {"get_catalog": ("module",), "list_presets": ("query",), "get_preset": ("slot",),
           "set_module": ("module", "on", "model", "params"), "apply_patch": ("modules", "name"),
           "select_preset": ("slot", "discard_changes"), "save_preset": ("slot", "name"),
           "tone3000_search": ("query",), "tone3000_get": ("tone_id",),
           "load_tone3000_ir": ("slot", "tone_id", "model_id", "name", "use")}


def _named(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    named = dict(zip(_PARAMS.get(name, ()), args, strict=False))
    if len(args) > len(named):
        raise TypeError(f"{name}: too many arguments")
    return {**named, **kwargs}


def find_editor(path: Path | None = None) -> RemoteTools | None:
    """The running editor's tools, or None (no editor, or a stale file)."""
    try:
        info = json.loads((path or discovery_path()).read_text())
        os.kill(int(info["pid"]), 0)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    remote = RemoteTools(str(info["url"]), str(info["token"]))
    try:
        remote.call("list_presets", timeout=5, query="\x00")
    except ToolError:
        return None
    return remote
