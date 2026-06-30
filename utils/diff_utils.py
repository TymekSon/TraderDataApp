"""Text comparison utilities using difflib."""

import difflib
import logging

logger = logging.getLogger(__name__)


def generate_diff_html(old_text: str, new_text: str) -> str:
    """Compare two texts and return an HTML string highlighting differences.

    * Removed text → red background + strikethrough.
    * Added text   → green background.
    * Uses <span> tags (not <del>/<ins>) to avoid conflicts with
      Markdown renderers.
    """
    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
    parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(_escape(old_text[i1:i2]))
        elif tag == "delete":
            parts.append(
                '<span style="background:#fdd;text-decoration:line-through;">'
                f"{_escape(old_text[i1:i2])}</span>"
            )
        elif tag == "insert":
            parts.append(
                '<span style="background:#dfd;text-decoration:none;">'
                f"{_escape(new_text[j1:j2])}</span>"
            )
        elif tag == "replace":
            parts.append(
                '<span style="background:#fdd;text-decoration:line-through;">'
                f"{_escape(old_text[i1:i2])}</span>"
            )
            parts.append(
                '<span style="background:#dfd;text-decoration:none;">'
                f"{_escape(new_text[j1:j2])}</span>"
            )

    return "".join(parts)


def _escape(text: str) -> str:
    """Minimal HTML escaping. Keeps \n as <br> for readability."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
