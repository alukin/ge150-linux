from pathlib import Path

import pytest

from ge150.model import gear
from ge150.model.catalog import load_catalog


def test_every_model_has_gear() -> None:
    for index, info in enumerate(load_catalog()):
        for model in info.models:
            found = gear.gear_for(index, model.number)
            assert found is not gear.FALLBACK, (info.name, model.name)
            assert found.kind in ("wah", "stomp", "boss", "round", "bigbox", "micro", "eq",
                                  "head", "combo", "cab", "acoustic")


def test_known_origins() -> None:
    assert gear.gear_for(1, 2).name == "Ibanez TS808 Tube Screamer"
    assert gear.gear_for(2, 9).gid == "plexi"
    assert gear.gear_for(3, 6).speakers == "4x12"
    assert gear.gear_for(2, 60).gid == "user_nr"  # AMP 56-65: NR slots


def test_user_photo_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folder = tmp_path / "ge150" / "photos"
    folder.mkdir(parents=True)
    (folder / "ts808.png").write_bytes(b"x")
    assert gear.photo_path("ts808") == folder / "ts808.png"
    assert gear.photo_path("does-not-exist") is None


def test_every_shipped_photo_is_credited() -> None:
    photos = Path(gear.__file__).resolve().parents[1] / "data" / "photos"
    credits = (photos / "CREDITS.md").read_text()
    known = gear.all_gear()
    for photo in photos.glob("*.jpg"):
        assert photo.stem in known, photo.name
        assert f"| `{photo.stem}` |" in credits, photo.name
