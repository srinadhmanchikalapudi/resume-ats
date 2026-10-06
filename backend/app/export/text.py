"""Making text safe for the PDF's standard fonts (Windows-1252)."""

from __future__ import annotations

import re
import unicodedata

# Built with chr() so the source holds no invisible or look-alike characters.
_INVISIBLE = re.compile("[" + "".join(chr(code) for code in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)) + "]")
_SPECIAL = {
    chr(0x00A0): " ",  # no-break space
    chr(0x2192): "->",
    chr(0x2190): "<-",
    chr(0x2265): ">=",
    chr(0x2264): "<=",
    chr(0x2212): "-",  # minus sign
}


def _encodable(char: str) -> bool:
    try:
        char.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


def pdf_safe(text: str) -> tuple[str, int]:
    """Returns text the standard PDF fonts can draw, and how many characters had to become "?".

    Typographic characters (bullets, en dashes, curly quotes, accents) are already in Windows-1252 and pass through.
    Others fall back to a plain base letter where one exists, for example a letter with an unusual accent.
    """
    out: list[str] = []
    replaced = 0
    for char in _INVISIBLE.sub("", text):
        if _encodable(char):
            out.append(char)
            continue
        if char in _SPECIAL:
            out.append(_SPECIAL[char])
            continue
        base = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
        if base and all(_encodable(c) for c in base):
            out.append(base)
        else:
            out.append("?")
            replaced += 1
    return "".join(out), replaced


def slug(text: str, limit: int = 40) -> str:
    """A file-system-safe name part: letters, digits and single hyphens."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", unicodedata.normalize("NFKD", text)).strip("-")
    return cleaned[:limit].strip("-")
