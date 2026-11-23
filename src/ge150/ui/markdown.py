"""Agent replies (Markdown) as the rich text a QTextBrowser shows.

``markdown-it-py`` (CommonMark + GitHub tables and strikethrough). Raw HTML in a reply is
shown as text, never rendered: the agent's output is not trusted markup.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

from ge150.ui.theme import ACCENT, BORDER, MUTED, RAISED

_MD = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable(
    ["table", "strikethrough"])
_TABLE_ROW = re.compile(r"^\s*\|")

#: Default style sheet of the chat document (Qt's rich text CSS subset).
STYLE = f"""
p {{ margin-top: 4px; margin-bottom: 4px; }}
ul, ol {{ margin-top: 2px; margin-bottom: 4px; }}
li {{ margin-top: 1px; margin-bottom: 1px; }}
h1, h2, h3, h4, h5, h6 {{ margin-top: 10px; margin-bottom: 4px; font-weight: 800; }}
h1 {{ font-size: 17px; }} h2 {{ font-size: 15px; }} h3, h4, h5, h6 {{ font-size: 14px; }}
code {{ font-family: monospace; background-color: {RAISED}; color: #ffcf99; }}
pre {{ font-family: monospace; background-color: {RAISED}; margin-top: 6px;
       margin-bottom: 6px; }}
blockquote {{ color: {MUTED}; margin-left: 12px; }}
a {{ color: {ACCENT}; }}
table {{ border-collapse: collapse; margin-top: 6px; margin-bottom: 6px; }}
th {{ background-color: {RAISED}; font-weight: 700; border: 1px solid {BORDER};
      padding: 4px 10px; }}
td {{ border: 1px solid {BORDER}; padding: 4px 10px; }}
hr {{ background-color: {BORDER}; }}
"""


def _close_tables(text: str) -> str:
    """A line right after a table ends it (GitHub would make it one more row)."""
    out: list[str] = []
    in_table = False
    for line in text.splitlines():
        row = bool(_TABLE_ROW.match(line))
        if in_table and line.strip() and not row:
            out.append("")
        in_table = row
        out.append(line)
    return "\n".join(out)


def to_html(text: str) -> str:
    rendered = _MD.render(_close_tables(text))
    # Qt ignores CSS cell spacing: the attributes keep the borders single.
    return rendered.replace("<table>", "<table cellspacing='0' cellpadding='0'>")
