import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from ge150.ui import scale


@pytest.mark.parametrize(("size", "factor"), [
    ((1366, 768), 1.0), ((1920, 1080), 1.0), ((2560, 1440), 1.25), ((3440, 1440), 1.25),
    ((3840, 2160), 2.0), ((3840, 2066), 1.75), ((7680, 4320), 2.5),
])
def test_auto_factor(size: tuple[int, int], factor: float) -> None:
    assert scale.auto_factor(*size) == factor


def test_preference_is_remembered(monkeypatch: pytest.MonkeyPatch) -> None:
    assert scale.preference() == scale.AUTO
    scale.set_preference("1.5")
    assert scale.preference() == "1.5"
    scale.set_preference("nonsense")
    assert scale.preference() == scale.AUTO


def test_no_restart_when_already_scaled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr(scale, "_exec", calls.append)
    monkeypatch.setenv("QT_SCALE_FACTOR", "2")  # the user's own choice wins
    scale.apply(None)  # type: ignore[arg-type]
    monkeypatch.delenv("QT_SCALE_FACTOR")
    monkeypatch.setenv(scale.MARK, "2")  # already restarted once: no loop
    scale.apply(None)  # type: ignore[arg-type]
    assert calls == []
