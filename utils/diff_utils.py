"""Text comparison utilities using difflib."""

import difflib
import logging

logger = logging.getLogger(__name__)


def generate_diff_html(old_text: str, new_text: str) -> str:
    """Compare two texts and return an HTML string highlighting differences.

    * Deleted text is wrapped in ``<del style="background:#fdd">``.
    * Added text is wrapped in ``<ins style="background:#dfd">``.
    * Unchanged parts are kept as plain text.
    """
    matcher = difflib.SequenceMatcher(None, old_text, new_text)
    parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(_escape(old_text[i1:i2]))
        elif tag == "delete":
            parts.append(
                f'<del style="background:#fdd;text-decoration:line-through;">'
                f"{_escape(old_text[i1:i2])}</del>"
            )
        elif tag == "insert":
            parts.append(
                f'<ins style="background:#dfd;text-decoration:none;">'
                f"{_escape(new_text[j1:j2])}</ins>"
            )
        elif tag == "replace":
            parts.append(
                f'<del style="background:#fdd;text-decoration:line-through;">'
                f"{_escape(old_text[i1:i2])}</del>"
            )
            parts.append(
                f'<ins style="background:#dfd;text-decoration:none;">'
                f"{_escape(new_text[j1:j2])}</ins>"
            )

    return "".join(parts)


def _escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
