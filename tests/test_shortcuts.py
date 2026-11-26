import os
from pathlib import Path

import pytest

from ge150.services import shortcuts


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(shortcuts, "_run", lambda *args: None)  # no real cache tools
    home = tmp_path / "home"
    (home / "Escritorio").mkdir(parents=True)
    config = home / ".config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text('XDG_DESKTOP_DIR="$HOME/Escritorio"\n')
    return {"HOME": str(home), "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_DATA_DIRS": str(tmp_path / "system")}


@pytest.mark.parametrize(("variables", "desktop", "icons", "tiling"), [
    ({"XDG_CURRENT_DESKTOP": "KDE"}, "kde", True, False),
    ({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, "gnome", False, False),
    ({"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, "x-cinnamon", True, False),
    ({"XDG_CURRENT_DESKTOP": "XFCE"}, "xfce", True, False),
    ({"XDG_CURRENT_DESKTOP": "Hyprland"}, "hyprland", False, True),
    ({"SWAYSOCK": "/run/sway.sock"}, "sway", False, True),
    ({"I3SOCK": "/run/i3"}, "i3", False, True),
    ({}, "", False, False),
])
def test_detects_the_desktop(variables: dict[str, str], desktop: str, icons: bool,
                             tiling: bool) -> None:
    found = shortcuts.detect(variables)
    assert (found.desktop, found.desktop_icons, found.tiling) == (desktop, icons, tiling)


def test_kde_gets_a_menu_entry_and_a_trusted_desktop_icon(env: dict[str, str]) -> None:
    env["XDG_CURRENT_DESKTOP"] = "KDE"
    plan = shortcuts.plan(env)
    assert "menú de aplicaciones de KDE Plasma y en el escritorio" in plan.describe()
    written = shortcuts.install(env)
    home = Path(env["HOME"])
    menu = home / ".local/share/applications/ge150.desktop"
    desktop = home / "Escritorio/ge150.desktop"
    icon = home / ".local/share/icons/hicolor/scalable/apps/ge150.svg"
    assert set(written) == {menu, desktop, icon}
    text = menu.read_text()
    assert "Exec=" in text and "Icon=ge150" in text and "StartupWMClass=ge150" in text
    assert os.access(desktop, os.X_OK) and icon.read_text().startswith("<")
    assert shortcuts.installed(env)
    assert set(shortcuts.remove(env)) == {menu, desktop, icon}
    assert not shortcuts.installed(env)


def test_tiling_window_managers_get_only_the_launcher_entry(env: dict[str, str]) -> None:
    env["XDG_CURRENT_DESKTOP"] = "Hyprland"
    plan = shortcuts.plan(env)
    assert plan.desktop is None
    assert plan.describe() == "el lanzador de aplicaciones de Hyprland (rofi, wofi, fuzzel…)"
    shortcuts.install(env)
    assert not (Path(env["HOME"]) / "Escritorio/ge150.desktop").exists()


def test_never_a_desktop_icon_in_the_home_folder(env: dict[str, str]) -> None:
    env["XDG_CURRENT_DESKTOP"] = "KDE"
    Path(env["XDG_CONFIG_HOME"], "user-dirs.dirs").write_text('XDG_DESKTOP_DIR="$HOME/"\n')
    assert shortcuts.plan(env).desktop is None


def test_a_system_entry_is_not_duplicated(env: dict[str, str]) -> None:
    env["XDG_CURRENT_DESKTOP"] = "GNOME"
    system = Path(env["XDG_DATA_DIRS"]) / "applications"
    system.mkdir(parents=True)
    (system / "ge150.desktop").write_text("[Desktop Entry]\n")
    assert shortcuts.plan(env).menu is None and shortcuts.installed(env)


def test_entry_matches_the_packaged_desktop_file() -> None:
    """The Arch package installs packaging/ge150.desktop: the same entry, but with ``ge150``
    from the PATH instead of an absolute path."""
    packaged = (Path(__file__).parent.parent / "packaging" / "ge150.desktop").read_text()
    made = shortcuts.entry_text("ge150")

    def lines(text: str) -> set[str]:
        return {line for line in text.splitlines()
                if line and not line.startswith("StartupWMClass")}

    assert lines(made) == lines(packaged)
