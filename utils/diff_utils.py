"""Text comparison utilities using difflib."""

import difflib
import logging
import re

logger = logging.getLogger(__name__)

# Regex to split text into tokens: words, whitespace, and punctuation.
# This ensures that we compare word‑by‑word so that no word is ever
# split in half by the diff algorithm.
_TOKEN_RE = re.compile(r"(\S+\s*)", re.UNICODE)


def generate_diff_html(old_text: str, new_text: str) -> str:
    """Compare two texts at word‑level and return HTML with highlights.

    * Removed words → red background + strikethrough.
    * Added words   → green background.
    * Uses <span> tags (no <del>/<ins>) for Dash 4.x compatibility.
    """
    old_tokens = _tokenize(old_text)
    new_tokens = _tokenize(new_text)

    matcher = difflib.SequenceMatcher(
        None, old_tokens, new_tokens, autojunk=False
    )
    parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.extend(_escape(t) for t in old_tokens[i1:i2])
        elif tag == "delete":
            chunk = "".join(old_tokens[i1:i2])
            parts.append(
                '<span style="background:#fdd;text-decoration:line-through;">'
                f"{_escape(chunk)}</span>"
            )
        elif tag == "insert":
            chunk = "".join(new_tokens[j1:j2])
            parts.append(
                '<span style="background:#dfd;text-decoration:none;">'
                f"{_escape(chunk)}</span>"
            )
        elif tag == "replace":
            old_chunk = "".join(old_tokens[i1:i2])
            new_chunk = "".join(new_tokens[j1:j2])
            if old_chunk:
                parts.append(
                    '<span style="background:#fdd;text-decoration:line-through;">'
                    f"{_escape(old_chunk)}</span>"
                )
            if new_chunk:
                parts.append(
                    '<span style="background:#dfd;text-decoration:none;">'
                    f"{_escape(new_chunk)}</span>"
                )

    return "".join(parts)


def _tokenize(text: str) -> list[str]:
    """Split text into tokens (word + following whitespace)."""
    tokens = _TOKEN_RE.findall(text)
    # If the text didn't match our pattern at all, fall back to the whole text
    return tokens if tokens else [text]


def _escape(text: str) -> str:
    """Minimal HTML escaping. Preserves newlines as <br> for readability."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
