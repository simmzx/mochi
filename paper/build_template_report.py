"""Build the AIDD8122 final report on the official DOCX template.

The template supplies the title page, the logo, the Table of Contents layout and the footer
("Page X of Y"); this module fills the title table, rewrites the TOC and writes §1–§7 with
native Word styles so the document stays editable.

Page numbers in the TOC are back-filled by a second pass: build → PDF → locate headings → rebuild.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
TEMPLATE = Path(r"D:\browser download\AIDD8122_Final_Project_Report_Template.docx")
OUT = HERE / "MOCHI_AIDD8122_Report.docx"

BODY_FONT = "Times New Roman"
INK = RGBColor(0x00, 0x00, 0x00)
GREY = RGBColor(0x44, 0x44, 0x44)

SECTIONS = [
    ("§1.", "Introduction"),
    ("§2.", "Literature Review"),
    ("§3.", "Research Questions and Objectives"),
    ("§4.", "Methods and Materials"),
    ("§5.", "Results and Discussion"),
    ("§6.", "Conclusions"),
    ("§7.", "References"),
]


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------
def _set_cell_shading(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def _no_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def _strip_numbering(style) -> None:
    """The template's headings carry automatic §-numbering; we supply explicit numbers instead."""
    p_pr = style.element.pPr
    if p_pr is None:
        return
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)


def body_style(doc: Document) -> None:
    # Heading 1 keeps the template numbering (renders as "§N."); sub-headings use explicit numbers
    for name in ("Heading 2", "Heading 3"):
        _strip_numbering(doc.styles[name])
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    pf = normal.paragraph_format
    pf.line_spacing = 1.3
    pf.space_after = Pt(6)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    h1 = doc.styles["Heading 1"]
    h1.font.name = BODY_FONT
    h1.font.size = Pt(15)
    h1.font.bold = True
    h1.font.color.rgb = INK
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(8)
    h1.paragraph_format.keep_with_next = True

    h2 = doc.styles["Heading 2"]
    h2.font.name = BODY_FONT
    h2.font.size = Pt(12.5)
    h2.font.bold = True
    h2.font.color.rgb = INK
    h2.paragraph_format.space_before = Pt(12)
    h2.paragraph_format.space_after = Pt(3)
    h2.paragraph_format.keep_with_next = True


def p(doc, text: str, size: float = 12, italic: bool = False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
      space_after: float = 6, bold: bool = False, first_line_indent: bool = False):
    par = doc.add_paragraph()
    par.alignment = align
    par.paragraph_format.space_after = Pt(space_after)
    if first_line_indent:
        par.paragraph_format.first_line_indent = Cm(0.75)
    run = par.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.italic = italic
    run.bold = bold
    return par


def bullets(doc, items: list[str], size: float = 11.5) -> None:
    for item in items:
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.75)
        par.paragraph_format.first_line_indent = Cm(-0.45)
        par.paragraph_format.space_after = Pt(3)
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = par.add_run("•  " + item)
        run.font.name = BODY_FONT
        run.font.size = Pt(size)


def h1(doc, text: str, page_break: bool = True) -> None:
    """Add a section heading. The template's Heading 1 style supplies the "§N." prefix."""
    if page_break:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    par = doc.add_paragraph(style="Heading 1")
    run = par.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(15)
    run.bold = True
    run.font.color.rgb = INK


def h2(doc, text: str) -> None:
    par = doc.add_paragraph(style="Heading 2")
    run = par.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(12.5)
    run.bold = True
    run.font.color.rgb = INK


def caption(doc, text: str, before: float = 4, after: float = 8) -> None:
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.LEFT
    par.paragraph_format.space_before = Pt(before)
    par.paragraph_format.space_after = Pt(after)
    par.paragraph_format.keep_with_next = True
    run = par.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(10)
    run.italic = True
    run.font.color.rgb = GREY


def figure(doc, name: str, width_cm: float, cap: str) -> None:
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.keep_with_next = True
    par.add_run().add_picture(str(FIG / name), width=Cm(width_cm))
    caption(doc, cap)


def table(doc, headers: list[str], rows: list[list[str]], cap: str, widths: list[float] | None = None,
          font_size: float = 9.5, left_first: bool = True) -> None:
    caption(doc, cap, before=8, after=4)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _repeat_header(t.rows[0])
    hdr = t.rows[0].cells
    for i, text_ in enumerate(headers):
        hdr[i].text = ""
        par = hdr[i].paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.space_after = Pt(1)
        run = par.add_run(text_)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.name = BODY_FONT
        _set_cell_shading(hdr[i], "E8EDF2")
    for r_i, row in enumerate(rows):
        cells = t.add_row().cells
        _no_split(t.rows[-1])
        for c_i, val in enumerate(row):
            cells[c_i].text = ""
            par = cells[c_i].paragraphs[0]
            par.paragraph_format.space_after = Pt(1)
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT if (c_i == 0 and left_first) else WD_ALIGN_PARAGRAPH.CENTER
            run = par.add_run(str(val))
            run.font.size = Pt(font_size)
            run.font.name = BODY_FONT
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
