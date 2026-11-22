from pathlib import Path

from ge150.services.chat_history import Chat, ChatEntry, ChatStore, new_id, title_for


def test_save_list_rename_delete(tmp_path: Path) -> None:
    store = ChatStore(tmp_path)
    first = Chat(ChatEntry(new_id(), "panel", "Tono de Slash", "claude", 1.0, 0.0, 24,
                           "Av83 Clean-AMP"), ["<p>hola</p>"], {"claude": "s-1"})
    store.save(first)
    other = Chat(ChatEntry("tab-1", "asistente", "Av83", "codex", 2.0, 0.0))
    store.save(other)
    assert [e.id for e in store.entries("panel")] == [first.entry.id]
    assert [e.id for e in store.entries()] == ["tab-1", first.entry.id]  # newest first
    loaded = store.load(first.entry.id)
    assert loaded is not None and loaded.blocks == ["<p>hola</p>"]
    assert loaded.sessions == {"claude": "s-1"} and loaded.entry.slot == 24
    store.rename(first.entry.id, "Slash solo")
    assert store.entries("panel")[0].title == "Slash solo"
    store.delete(first.entry.id)
    assert store.load(first.entry.id) is None and not (tmp_path / f"{first.entry.id}.json").exists()
    assert (tmp_path / "index.json").stat().st_mode & 0o777 == 0o600


def test_hostile_ids_and_old_entries_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "index.json").write_text(
        '[{"id": "../x", "scope": "panel", "title": "", "provider": "claude", "created": 1,'
        ' "updated": 1}, {"id": "old", "scope": "panel", "title": "t", "provider": "claude",'
        ' "created": 1, "updated": 1}]')
    entries = ChatStore(tmp_path).entries()
    assert [e.id for e in entries] == ["old"] and entries[0].slot == 0


def test_title_is_the_first_request_on_one_line() -> None:
    assert title_for("  tono de\nSlash  ") == "tono de Slash"
    assert len(title_for("x" * 200)) == 70
