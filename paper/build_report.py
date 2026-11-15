"""Build the MOCHI final-project report (DOCX → PDF via LibreOffice)."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
OUT = ROOT / "MOCHI_Final_Project_Report.docx"

INK = RGBColor(0x2F, 0x3E, 0x4E)
ACCENT = RGBColor(0x2E, 0x5E, 0x8C)
GREY = RGBColor(0x66, 0x6F, 0x7A)

BODY_FONT = "Times New Roman"
HEAD_FONT = "Calibri"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _set_cell_shading(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _page_number_footer(section) -> None:
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    run.font.name = BODY_FONT
    run.font.size = Pt(9)
    run.font.color.rgb = GREY


def new_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)
    _page_number_footer(section)

    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(11)
    style.font.color.rgb = INK
    style.paragraph_format.line_spacing = 1.35
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return doc


def h1(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = HEAD_FONT
    run.font.size = Pt(15)
    run.bold = True
    run.font.color.rgb = ACCENT


def h2(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = HEAD_FONT
    run.font.size = Pt(12)
    run.bold = True
    run.font.color.rgb = INK


def para(doc, text: str, *, size: float = 11, italic: bool = False, align=None, space_after: float = 6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.italic = italic
    return p


def bullets(doc, items: list[str], style: str = "List Bullet") -> None:
    for item in items:
        p = doc.add_paragraph(style=style)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(item)
        run.font.name = BODY_FONT
        run.font.size = Pt(10.6)


def caption(doc, text: str, *, before: float = 2, after: float = 10) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    run = p.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(9)
    run.italic = True
    run.font.color.rgb = GREY


def figure(doc, name: str, width_cm: float, cap: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(FIG / name), width=Cm(width_cm))
    caption(doc, cap)


def table(doc, headers: list[str], rows: list[list[str]], cap: str, *, widths=None,
          font_size: float = 8.8, align_first_left: bool = True) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    # repeat the header row when a table breaks across pages
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)
    hdr = t.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.name = BODY_FONT
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _set_cell_shading(hdr[i], "2E5E8C")
    for r_i, row in enumerate(rows):
        new_row = t.add_row()
        # keep a row on one page instead of splitting it across a page break
        row_pr = new_row._tr.get_or_add_trPr()
        row_pr.append(OxmlElement("w:cantSplit"))
        cells = new_row.cells
        for c_i, text in enumerate(row):
            cells[c_i].text = ""
            p = cells[c_i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if (c_i == 0 and align_first_left) else WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(text))
            run.font.size = Pt(font_size)
            run.font.name = BODY_FONT
            if r_i % 2 == 1:
                _set_cell_shading(cells[c_i], "F2F5F9")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    caption(doc, cap)


def page_break(doc) -> None:
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ---------------------------------------------------------------------------
# title page + front matter
# ---------------------------------------------------------------------------
def title_page(doc) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("FACULTY OF APPLIED SCIENCES")
    run.bold = True
    run.font.size = Pt(12.5)
    run.font.name = HEAD_FONT
    run.font.color.rgb = INK

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("DOCTOR OF PHILOSOPHY IN ARTIFICIAL INTELLIGENCE DRIVEN DRUG DISCOVERY")
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.name = HEAD_FONT
    run.font.color.rgb = INK

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run("AIDD8122 – Advanced Topics in Artificial Intelligence & Drug Discovery")
    run.font.size = Pt(10)
    run.italic = True
    run.font.name = BODY_FONT
    run.font.color.rgb = GREY

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    p.add_run().add_picture(str(FIG / "fig_logo.png"), width=Cm(4.2))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(14)
    run = p.add_run("MOCHI: A Self-Evolving Multi-Agent System\nfor End-to-End AI Drug Discovery")
    run.bold = True
    run.font.size = Pt(21)
    run.font.name = HEAD_FONT
    run.font.color.rgb = ACCENT

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Validated on colorectal-cancer effector-target discovery, enzyme activity\n"
                    "engineering, multi-step retrosynthesis and self-driving-laboratory protocol compilation")
    run.italic = True
    run.font.size = Pt(10.5)
    run.font.name = BODY_FONT
    run.font.color.rgb = GREY

    for text, size, bold in [
        ("", 10, False),
        ("Final Project Report", 12, True),
        ("", 10, False),
        ("Student:  Xiang Zhang   (P2600300)", 11, False),
        ("Group:    GROUP 3", 11, False),
        ("Date:     16 November 2026", 11, False),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        if text:
            run = p.add_run(text)
            run.font.size = Pt(size)
            run.bold = bold
            run.font.name = BODY_FONT
            run.font.color.rgb = INK

    page_break(doc)


def front_matter(doc) -> None:
    h1(doc, "Abstract")
    para(doc,
         "Artificial-intelligence drug discovery (AIDD) now generates more candidate targets, molecules and "
         "protocols than any single researcher can triage, yet the tools that produce them are disjoint and the "
         "reasoning that connects them is rarely auditable. We present MOCHI (Multi-agent Orchestrator for "
         "Chemical and biomedical Intelligence), a self-evolving multi-agent system in which a manager, a "
         "developer, a critic and a tool-creation agent collaborate over a shared ocean of 46 scientific tools. "
         "MOCHI is deliberately scenario-agnostic: four interchangeable stage programs cover (i) downstream "
         "effector-target discovery, (ii) structure-guided enzyme variant design, (iii) multi-step "
         "retrosynthesis planning and (iv) compilation of wet-lab protocols into validated self-driving-laboratory "
         "(SDL) instructions. A deterministic critic audit, a provenance record of every database call and a "
         "dual offline/online engine make every run reproducible and inspectable. On four real tasks MOCHI "
         "recovers a Wnt/Notch receptor-class shortlist that motivated the experimental validation of the "
         "Wnt co-receptor LRP6, ranks the "
         "experimentally validated best strictosidine-synthase variant first out of 2,773 candidates, plans "
         "syntheses for all eight benchmark drugs, and compiles six clean protocols while catching five of five "
         "deliberately corrupted ones. Ablations show that dynamic tool creation is required for the target "
         "task and that the experimental prior is required to place the true best variant first. The run "
         "artefacts and the command that rebuilds every table and figure are available at "
         "https://github.com/simmzx/mochi, and a single command reproduces the whole suite.")
    page_break(doc)

    h1(doc, "Contents")
    entries = [
        ("§1  Introduction and Literature Review", ""),
        ("§2  Research Questions and Objectives", ""),
        ("§3  Methods and Materials", ""),
        ("§4  Results and Discussion", ""),
        ("§5  Conclusions", ""),
        ("§6  References", ""),
        ("§7  Appendix: reproducibility and artefact map", ""),
    ]
    for name, _ in entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(name)
        run.font.size = Pt(10.5)
        run.font.name = BODY_FONT
        run.font.color.rgb = INK
    page_break(doc)
