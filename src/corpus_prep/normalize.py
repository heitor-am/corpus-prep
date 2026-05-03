"""Text normalization: encoding fix + Unicode NFC + cleanup.

Covers Q4 of UFPI activity 03 (ftfy) and cleans up control chars / whitespace
introduced by PDFs and OCR. Applied to each Document before filtering.
"""

from __future__ import annotations

import re
import unicodedata

import ftfy

# Control characters (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F).
# Tab (0x09), LF (0x0A) and CR (0x0D) are preserved.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

# Multiple spaces/tabs collapse to a single space (newlines are not affected here).
_INLINE_WHITESPACE_RE = re.compile(r"[ \t]+")

# 3+ consecutive newlines collapse to a single paragraph break (\n\n).
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """Run the normalization pipeline.

    Steps (in order):
        1. ftfy.fix_text — fix mojibake (e.g. ``Ã©`` -> ``é``).
        2. NFC — normalize decomposed Unicode (combining marks -> composed form).
        3. Strip control characters (preserves tab/LF/CR).
        4. Collapse runs of spaces/tabs into a single space.
        5. Collapse 3+ newlines into a single paragraph break (\\n\\n).
        6. Strip leading/trailing whitespace.
    """
    if not text:
        return ""
    text = ftfy.fix_text(text)
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()
