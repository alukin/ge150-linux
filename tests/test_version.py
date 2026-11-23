"""The version lives in three places (PUBLISH.md §3): they must agree."""

import re
import tomllib
from pathlib import Path

from ge150 import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_the_three_versions_agree() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    pkgbuild = (ROOT / "packaging" / "PKGBUILD").read_text()
    pkgver = re.search(r"^pkgver=(\S+)", pkgbuild, re.MULTILINE)
    prefix = re.search(r'printf "([0-9.]+)\.r%s', pkgbuild)
    assert pkgver and prefix
    assert project == __version__ == pkgver.group(1) == prefix.group(1)


def test_the_changelog_has_this_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"## [{__version__}]" in changelog
