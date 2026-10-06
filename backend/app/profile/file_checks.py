"""ATS-readability checks on a resume file the user uploads (not one this app generated).

These are heuristics read from the file itself, so each message says what was seen and why it matters.
"""

from __future__ import annotations

import io
import re
from pathlib import PurePath

import docx
from pypdf import PdfReader

from ..checks import Check

# Substrings of font names that are common, widely supported and extract cleanly.
COMMON_FONT_HINTS = (
    "arial", "calibri", "carlito", "helvetica", "times", "georgia", "cambria", "garamond", "verdana", "tahoma",
    "courier", "segoe", "trebuchet", "liberation", "dejavu", "noto", "roboto", "opensans", "open sans", "lato",
    "sourcesans", "source sans", "symbol", "wingdings", "cmr", "lmroman", "latinmodern",
)  # fmt: skip
SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
MAX_PAGES = 2

# pypdf's layout mode reproduces the page with spaces between blocks of text that sit apart horizontally. In a single
# column a wide gap only separates a short item such as a date from the text beside it. In a multi-column page a wide gap
# separates two long runs of text. Several such lines, and a real share of the page, means columns.
GAP = re.compile(r"\s{6,}")
LONG_RIGHT_TEXT = 30
MIN_SIDE_BY_SIDE_LINES = 6
MIN_SIDE_BY_SIDE_SHARE = 0.2
PAGES_TO_INSPECT = 3


def check_upload(filename: str, data: bytes) -> list[Check]:
    """Checks for a PDF or DOCX; other file types and unreadable files return nothing."""
    suffix = PurePath(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            return check_pdf(data)
        if suffix == ".docx":
            return check_docx(data)
    except Exception:  # noqa: BLE001 - a file we cannot inspect must never block the import itself
        return []
    return []


# --- PDF ----------------------------------------------------------------------------------------


def _font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        resources = page.get("/Resources")
        fonts = resources.get_object().get("/Font") if resources else None
        if fonts is None:
            continue
        for font in fonts.get_object().values():
            base = str(font.get_object().get("/BaseFont", "")).lstrip("/")
            if base:
                names.add(SUBSET_PREFIX.sub("", base))
    return names


def _is_common_font(name: str) -> bool:
    lowered = name.lower().replace(" ", "")
    return any(hint.replace(" ", "") in lowered for hint in COMMON_FONT_HINTS)


def _side_by_side(page) -> tuple[int, int]:
    """(lines with long text on both sides of a wide gap, non-empty lines) for one page."""
    text = page.extract_text(extraction_mode="layout")
    lines = [line for line in text.splitlines() if line.strip()]
    side = 0
    for line in lines:
        segments = [part for part in GAP.split(line.strip()) if part]
        if len(segments) >= 2 and len(segments[-1]) >= LONG_RIGHT_TEXT and len(segments[0]) >= 3:
            side += 1
    return side, len(lines)


def check_pdf(data: bytes) -> list[Check]:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt("")
    pages = list(reader.pages)
    text = "\n".join(page.extract_text() or "" for page in pages)
    checks: list[Check] = []

    readable = len(text.strip())
    checks.append(
        Check(
            name="Text can be read",
            ok=readable >= 200,
            detail=f"{readable:,} characters extracted."
            if readable >= 200
            else "Very little text could be extracted. If this is a scan or a picture of a resume, a tracking system "
            "cannot read it.",
        )
    )

    counts = [_side_by_side(page) for page in pages[:PAGES_TO_INSPECT]]
    side_by_side = sum(side for side, _ in counts)
    total_lines = sum(total for _, total in counts)
    multi = side_by_side >= MIN_SIDE_BY_SIDE_LINES and side_by_side >= MIN_SIDE_BY_SIDE_SHARE * max(1, total_lines)
    checks.append(
        Check(
            name="Single column",
            ok=not multi,
            detail="No side-by-side blocks of text found."
            if not multi
            else f"{side_by_side} lines have long text side by side, which looks like a multi-column layout. Tracking "
            "systems often read columns across the page, mixing the text from both. Use one column.",
        )
    )

    try:
        images = sum(len(page.images) for page in pages)
    except Exception:  # noqa: BLE001 - pypdf raises many types for odd image filters
        images = 0
    checks.append(
        Check(
            name="No images",
            ok=images == 0,
            detail="No images found."
            if images == 0
            else f"{images} image{'s' if images != 1 else ''} found. Tracking systems ignore images, so anything "
            "written inside them (a logo, a skills graphic, a photo caption) is lost.",
        )
    )

    bad = sum(1 for name in _font_names(reader) if not _is_common_font(name))
    uncommon = sorted(name for name in _font_names(reader) if not _is_common_font(name))
    checks.append(
        Check(
            name="Standard fonts",
            ok=bad == 0,
            detail="Common fonts only."
            if bad == 0
            else f"Uncommon font{'s' if bad != 1 else ''}: {', '.join(uncommon[:4])}. The text may still read fine, but "
            "standard fonts such as Arial, Calibri or Times are the safest.",
        )
    )

    garbled = text.count("�") + 5 * text.count("(cid:")
    rate = garbled / max(1, len(text))
    checks.append(
        Check(
            name="Clean text encoding",
            ok=rate < 0.01,
            detail="Text extracts cleanly."
            if rate < 0.01
            else "The extracted text contains garbled characters (a broken font encoding). A tracking system would see "
            "the same garbage. Re-export the PDF from the original document.",
        )
    )

    checks.append(
        Check(
            name="Length",
            ok=len(pages) <= MAX_PAGES,
            detail=f"{len(pages)} page{'s' if len(pages) != 1 else ''}."
            + ("" if len(pages) <= MAX_PAGES else " Most recruiters read two at most."),
        )
    )
    return checks


# --- DOCX ---------------------------------------------------------------------------------------


def check_docx(data: bytes) -> list[Check]:
    document = docx.Document(io.BytesIO(data))
    body = document.element.xml
    checks: list[Check] = []

    columns = [int(n) for section in document.sections for n in section._sectPr.xpath("./w:cols/@w:num")]
    multi = any(n > 1 for n in columns)
    checks.append(
        Check(
            name="Single column",
            ok=not multi,
            detail="One text column."
            if not multi
            else "The page is set up with several text columns, which tracking systems often read across the page.",
        )
    )

    table_text = sum(1 for table in document.tables for row in table.rows for cell in row.cells if cell.text.strip())
    checks.append(
        Check(
            name="No tables",
            ok=len(document.tables) == 0,
            detail="Content is plain paragraphs."
            if not document.tables
            else f"{len(document.tables)} table{'s' if len(document.tables) != 1 else ''} holding {table_text} filled "
            "cells. Many systems read tables in the wrong order or skip them.",
        )
    )

    has_text_box = "<w:txbxContent" in body
    has_graphics = bool(document.inline_shapes) or "<w:drawing" in body or "<w:pict" in body
    checks.append(
        Check(
            name="No images or text boxes",
            ok=not has_graphics and not has_text_box,
            detail="None found."
            if not (has_graphics or has_text_box)
            else "Images and text boxes are usually skipped by tracking systems, so their content is lost.",
        )
    )

    header_text = [
        p.text.strip()
        for section in document.sections
        for part in (section.header, section.footer)
        if not part.is_linked_to_previous
        for p in part.paragraphs
        if p.text.strip()
    ]
    checks.append(
        Check(
            name="No header or footer text",
            ok=not header_text,
            detail="Everything is in the main body."
            if not header_text
            else "Text sits in the header or footer (often contact details). Many systems skip those areas.",
        )
    )

    fonts = {document.styles["Normal"].font.name} | {
        run.font.name for p in document.paragraphs for run in p.runs if run.font.name
    }
    uncommon = sorted(f for f in fonts if f and not _is_common_font(f))
    checks.append(
        Check(
            name="Standard fonts",
            ok=not uncommon,
            detail="Common fonts only."
            if not uncommon
            else f"Uncommon font{'s' if len(uncommon) != 1 else ''}: {', '.join(uncommon[:4])}. Standard fonts such as "
            "Arial, Calibri or Times are the safest.",
        )
    )
    return checks
