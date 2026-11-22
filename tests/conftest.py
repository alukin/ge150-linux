"""Every test runs with its own data, config and cache folders: nothing a test saves
(AI conversations, guitars, IR sources, TONE3000 session) may reach the user's real ones."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _private_folders(tmp_path_factory: pytest.TempPathFactory,
                     monkeypatch: pytest.MonkeyPatch) -> None:
    base: Path = tmp_path_factory.mktemp("xdg")
    for name in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(name, str(base / name.lower()))
