import json
import threading
import urllib.parse
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ge150.cli import main
from ge150.formats import wav_ir
from ge150.services import tone3000

WAV = wav_ir.ir_to_wav([4_000_000] + [0] * 511)
TONE = {"id": 42, "title": "Mesa 4x12 V30", "format": "ir", "gear": "cab", "license": "cc-by",
        "description": "", "user": {"username": "irmaker", "display_name": None,
                                    "avatar_url": "https://x/a.png", "url": "https://x/u"}}


class FakeTone3000(BaseHTTPRequestHandler):
    tokens_issued = 0

    def _json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "").startswith("Bearer tok")

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/v1/tones/42" and self._authorized():
            self._json(TONE)
        elif url.path == "/api/v1/models" and self._authorized():
            base = f"http://127.0.0.1:{self.server.server_port}"
            self._json({"data": [{"id": 7, "name": "SM57 cap", "size": "standard",
                                  "model_url": f"{base}/files/7.wav"}], "page": 1})
        elif url.path == "/files/7.wav" and self._authorized():
            self.send_response(200)
            self.end_headers()
            self.wfile.write(WAV)
        elif url.path == "/api/v1/user" and self._authorized():
            self._json({"username": "me"})
        else:
            self._json({"error": "nope"}, 401)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        form = dict(urllib.parse.parse_qsl(self.rfile.read(length).decode()))
        if self.path == "/api/v1/oauth/token" and form.get("code") == "abc" \
                and form.get("code_verifier") and form.get("client_id") == "pk_test":
            FakeTone3000.tokens_issued += 1
            self._json({"access_token": "tok1", "refresh_token": "ref1", "expires_in": 3600,
                        "token_type": "bearer"})
        elif form.get("grant_type") == "refresh_token" and form.get("refresh_token") == "ref1":
            self._json({"access_token": "tok2", "expires_in": 3600})
        else:
            self._json({"error": "invalid_grant"}, 400)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def api() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), FakeTone3000)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, str(tmp_path / name))


def browser_that_selects(tone_id: str = "42", state_ok: bool = True):  # type: ignore[no-untyped-def]
    """Stands in for the user: follows the authorize URL straight to the callback."""

    def open_url(url: str) -> None:
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        assert query["code_challenge_method"] == "S256" and query["response_type"] == "code"
        state = query["state"] if state_ok else "forged"
        callback = query["redirect_uri"] + "?" + urllib.parse.urlencode(
            {"code": "abc", "state": state, "tone_id": tone_id})
        threading.Thread(target=urllib.request.urlopen, args=(callback,), daemon=True).start()

    return open_url


def client(api: str, browser=None, port: int = 0) -> tone3000.Tone3000Client:  # type: ignore[no-untyped-def]
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    c = tone3000.Tone3000Client(base_url=api, open_browser=browser or browser_that_selects(),
                                redirect_port=port or free)
    c.set_client_id("pk_test")
    return c


def test_select_download_and_attribution(api: str) -> None:
    c = client(api)
    assert c.select_tone() == 42
    assert c.creds.access_token == "tok1"
    assert oct(c.store.path.stat().st_mode & 0o777) == "0o600"
    download = c.download(42)
    assert download.tone.author == "irmaker" and download.tone.license == "cc-by"
    assert download.path.read_bytes() == WAV
    sources = tone3000.IrSources()
    sources.record(3, download)
    assert sources.load()["3"]["author"] == "irmaker"


def test_state_mismatch_is_rejected(api: str) -> None:
    with pytest.raises(tone3000.Tone3000Error, match="state"):
        client(api, browser_that_selects(state_ok=False)).login()


def test_expired_token_is_refreshed(api: str) -> None:
    c = client(api)
    c.login()
    c.creds.expires_at = 0
    assert c.user() == {"username": "me"}
    assert c.creds.access_token == "tok2"


def test_needs_key_and_session(api: str) -> None:
    c = tone3000.Tone3000Client(base_url=api)
    with pytest.raises(tone3000.Tone3000Error, match="publishable key"):
        c.authorize_url("x", "y")
    with pytest.raises(tone3000.Tone3000Error, match="sign in"):
        c.tone(42)


def test_cli_loads_a_tone3000_ir_into_a_slot(api: str, monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    from ge150 import cli_t3k

    signed_in = client(api)
    signed_in.login()
    monkeypatch.setattr(cli_t3k, "Tone3000Client", lambda: signed_in)
    assert main(["--sim", "t3k-load", "4", "--tone", "42", "-y"]) == 0
    out = capsys.readouterr().out
    assert "by irmaker" in out and "IR slot 4 (CAB 30): Mesa 4x12 V30" in out
    assert tone3000.IrSources().load()["4"]["tone_id"] == 42
