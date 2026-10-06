"""ATS-safe PDF: one column, standard Helvetica with a real text layer, no images, no headers or footers."""

from __future__ import annotations

from dataclasses import dataclass

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos

from .blocks import Block
from .models import Paper
from .text import pdf_safe

MARGIN_X = 19.0  # mm
MARGIN_Y = 16.0
LINE = 4.7  # mm per line of body text
BULLET_INDENT = 5.0
BULLET = chr(0x2022)  # in Windows-1252, so the standard fonts can draw it


@dataclass(frozen=True)
class PdfResult:
    data: bytes
    pages: int
    replaced_characters: int


def build_pdf(blocks: list[Block], *, name: str, paper: Paper) -> PdfResult:
    pdf = FPDF(unit="mm", format="A4" if paper == "a4" else "Letter")
    pdf.core_fonts_encoding = "cp1252"  # bullets, en dashes, curly quotes and accents work in standard fonts
    pdf.set_margins(MARGIN_X, MARGIN_Y, MARGIN_X)
    pdf.set_auto_page_break(True, margin=MARGIN_Y)
    pdf.set_title(f"{name} - Resume" if name else "Resume")
    pdf.set_author(name)
    pdf.set_creator("Resume ATS")
    pdf.set_lang("en-US")
    pdf.add_page()

    replaced = 0

    def safe(text: str) -> str:
        nonlocal replaced
        cleaned, count = pdf_safe(text)
        replaced += count
        return cleaned

    def room_for(height: float) -> None:
        if pdf.get_y() + height > pdf.page_break_trigger:
            pdf.add_page()

    def paragraph(text: str, width: float = 0) -> None:
        lines = pdf.multi_cell(width, LINE, text, align="L", dry_run=True, output=MethodReturnValue.LINES)
        room_for(LINE * max(len(lines), 1))
        pdf.multi_cell(width, LINE, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for block in blocks:
        text = safe(block.text)
        if block.kind == "name":
            pdf.set_font("Helvetica", "B", 18)
            room_for(9)
            pdf.multi_cell(0, 8, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif block.kind == "contact":
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(64)
            paragraph(text)
            pdf.set_text_color(0)
        elif block.kind == "heading":
            room_for(LINE * 4)  # keep a heading with at least a few lines of what follows
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.cell(0, 5.5, text.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            y = pdf.get_y()
            pdf.set_draw_color(128)
            pdf.set_line_width(0.2)
            pdf.line(MARGIN_X, y, pdf.w - MARGIN_X, y)
            pdf.ln(1.5)
        elif block.kind == "item_title":
            room_for(LINE * 3)
            pdf.ln(1.5)
            pdf.set_font("Helvetica", "B", 10)
            paragraph(text)
        elif block.kind == "item_meta":
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(64)
            paragraph(text)
            pdf.set_text_color(0)
        elif block.kind == "bullet":
            pdf.set_font("Helvetica", "", 10)
            width = pdf.epw - BULLET_INDENT
            lines = pdf.multi_cell(width, LINE, text, align="L", dry_run=True, output=MethodReturnValue.LINES)
            room_for(LINE * max(len(lines), 1))
            top = pdf.get_y()
            pdf.set_x(MARGIN_X)
            pdf.cell(BULLET_INDENT, LINE, BULLET)
            pdf.set_xy(MARGIN_X + BULLET_INDENT, top)
            pdf.multi_cell(width, LINE, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:  # text
            pdf.set_font("Helvetica", "", 10)
            paragraph(text)

    return PdfResult(data=bytes(pdf.output()), pages=pdf.page_no(), replaced_characters=replaced)
