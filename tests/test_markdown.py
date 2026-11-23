import pytest

pytest.importorskip("markdown_it")
pytest.importorskip("PySide6")

from ge150.ui.markdown import to_html

REPLY = """Quedan ordenadas para usarlas en vivo:
| Slot | Nombre sugerido | Qué es |
|---|---|---|
| 18 | **OPETH CLEAN** | Reemplaza a KokySpaceSolo |
| 21 | **OPETH HEAVY** | Para Master's Apprentices |
**Los cambios y por qué:**

- **21 Heavy:** amplificador J900. Le puse:
  - una puerta de ruido rápida;
  - un EQ que baja 100 Hz.
"""


def test_tables_and_nested_lists() -> None:
    out = to_html(REPLY)
    assert "<table cellspacing='0' cellpadding='0'>" in out
    assert "<th>Nombre sugerido</th>" in out and "<strong>OPETH CLEAN</strong>" in out
    assert "|" not in out
    # The line after the table is a paragraph, not one more row.
    assert "<p><strong>Los cambios y por qué:</strong></p>" in out
    assert out.count("<ul>") == 2 and "<li>una puerta de ruido rápida;</li>" in out


def test_headings_code_and_links() -> None:
    out = to_html("## Ajustes\n\nUsa `GAIN 40`.\n\n```\nAMP J800\n```\n[TONE3000](https://www.tone3000.com)")
    assert "<h2>Ajustes</h2>" in out and "<code>GAIN 40</code>" in out
    assert "<pre><code>AMP J800" in out and 'href="https://www.tone3000.com"' in out


def test_raw_html_is_shown_as_text() -> None:
    out = to_html("<img src=x onerror=alert(1)> **ok**")
    assert "<img" not in out and "&lt;img" in out and "<strong>ok</strong>" in out


def test_old_conversations_are_rendered_again() -> None:
    from ge150.ui.ai_chat import upgrade_blocks

    tool = "<div style='color:#8b95a3'>· revisa el catálogo</div>"
    old_reply = (
        "<p style='margin-top:12px'><b style='color:#7fd3ff'>Claude</b></p><div>"
        "Quedan ordenadas:<br>| Slot | Nombre |<br>|---|---|<br>| 18 | <b>OPETH CLEAN</b> |<br>"
        "<b>Los cambios:</b><br><ul><li><b>18 Clean:</b> 65 US TW &amp; chorus.</li>"
        "<li>un EQ.</li></ul>Tu Ibanez es semihueca.<br></div>")
    user = "<p style='margin-top:12px'><b style='color:#ff8a1f'>Tú</b></p><div>hola</div>"
    out = upgrade_blocks([user, tool, tool, tool, old_reply])
    assert out[0] == user and len(out) == 3
    assert "revisa el catálogo \u00d73" in out[1] and "\u2713" in out[1]
    assert "<table" in out[2] and "<strong>OPETH CLEAN</strong>" in out[2] and "|" not in out[2]
    assert "<li><strong>18 Clean:</strong> 65 US TW &amp; chorus.</li>" in out[2]
    assert "<p>Tu Ibanez es semihueca.</p>" in out[2]
    assert upgrade_blocks(out) == out  # new blocks are left alone
