"""Assemble the official AIDD8122 report: template + body + TOC backfill."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_template_report as B  # noqa: E402
from template_content_a import Citer, section1, section2, section3  # noqa: E402
from template_content_b import section4, section5, section6, section7  # noqa: E402

NODE = Path(r"D:\deepseek\resources\runtime\primary-runtime\dependencies\node\bin\node.exe")
CLI = Path(r"D:\deepseek\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js")
PDF = HERE / "MOCHI_AIDD8122_Report.pdf"

TITLE = ("MOCHI: A Self-Evolving Multi-Agent System for End-to-End AI Drug Discovery")
STUDENT_ID = "P2600300"
STUDENT_NAME = "ZHANG XIANG"
DATE = "16/11/2026"


def fill_title_page(doc: Document) -> None:
    t = doc.tables[0]
    t.rows[0].cells[1].text = TITLE
    for par in t.rows[0].cells[1].paragraphs:
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in par.runs:
            run.font.name = B.BODY_FONT
            run.font.size = Pt(14)
            run.bold = True
    t.rows[3].cells[1].text = STUDENT_ID
    t.rows[4].cells[1].text = STUDENT_NAME
    t.rows[9].cells[1].text = DATE
    for r in (3, 4, 9):
        for par in t.rows[r].cells[1].paragraphs:
            for run in par.runs:
                run.font.name = B.BODY_FONT
                run.font.size = Pt(12)


def scrub_title_page(doc: Document) -> None:
    """Drop the empty filler paragraphs between the title table and the TOC heading."""
    body = doc.element.body
    seen_table = False
    for child in list(body.iterchildren()):
        if child.tag.endswith("}tbl"):
            seen_table = True
            continue
        if not seen_table or not child.tag.endswith("}p"):
            continue
        text = "".join(node.text or "" for node in child.iter(qn("w:t"))).strip()
        if text.startswith("Table of Contents"):
            break
        if not text:
            body.remove(child)


def drop_stray_controls(doc: Document) -> None:
    """The template carries a bibliography content control that renders as a lone "[1]"."""
    body = doc.element.body
    for child in list(body.iterchildren()):
        if not child.tag.endswith("}sdt"):
            continue
        text = "".join(node.text or "" for node in child.iter(qn("w:t"))).strip()
        if text in {"[1]", ""}:
            body.remove(child)


def rewrite_toc(doc: Document, pages: dict[str, str]) -> None:
    toc = [par for par in doc.paragraphs if par.style is not None and par.style.name == "toc 1"]
    for par, (num, title) in zip(toc, B.SECTIONS):
        for run in list(par.runs):
            run._element.getparent().remove(run._element)
        par.paragraph_format.tab_stops.clear_all()
        par.paragraph_format.tab_stops.add_tab_stop(Cm(1.3), WD_TAB_ALIGNMENT.LEFT)
        par.paragraph_format.tab_stops.add_tab_stop(Cm(15.9), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        page = pages.get(num, "0")
        run = par.add_run(f"{num}\t{title}\t{page}")
        run.font.name = B.BODY_FONT
        run.font.size = Pt(11)

    # drop everything after the last TOC entry (empty paragraphs and the template's heading)
    last = toc[-1]._p
    body = doc.element.body
    drop = False
    for child in list(body.iterchildren()):
        if child is last:
            drop = True
            continue
        if drop and child.tag.endswith("}p"):
            body.remove(child)


def fix_footer(doc: Document) -> None:
    """The template footer counts pages per section; a report needs the document total."""
    for section in doc.sections:
        for instr in section.footer._element.iter(qn("w:instrText")):
            if "SECTIONPAGES" in (instr.text or ""):
                instr.text = instr.text.replace("SECTIONPAGES", "NUMPAGES")


def build(pages: dict[str, str] | None = None) -> Path:
    doc = Document(str(B.TEMPLATE))
    B.body_style(doc)
    fill_title_page(doc)
    scrub_title_page(doc)
    drop_stray_controls(doc)
    rewrite_toc(doc, pages or {})
    fix_footer(doc)

    c = Citer()
    section1(doc, c)
    section2(doc, c)
    section3(doc, c)
    section4(doc, c)
    section5(doc, c)
    section6(doc, c)
    section7(doc, c)

    doc.save(B.OUT)
    return B.OUT


def to_pdf(docx: Path) -> Path:
    if PDF.exists():
        PDF.unlink()
    subprocess.run([str(NODE), str(CLI), "convert", "--input", str(docx), "--output", str(PDF)],
                   check=True, capture_output=True)
    return PDF


def heading_pages(pdf: Path) -> dict[str, str]:
    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    found: dict[str, str] = {}
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").replace("\u00a0", " ")
        for num, title in B.SECTIONS:
            if num in found:
                continue
            pattern = rf"{re.escape(num)}\s+{re.escape(title)}"
            if re.search(pattern, text):
                found[num] = str(i)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=str, default="", help="JSON file with section page numbers")
    parser.add_argument("--pdf", action="store_true", help="also convert to PDF")
    args = parser.parse_args()

    pages = json.loads(Path(args.pages).read_text(encoding="utf-8")) if args.pages else {}
    docx = build(pages)
    print("saved", docx.name)
    if args.pdf:
        pdf = to_pdf(docx)
        print("pdf", pdf.name, "pages", len(__import__("pypdf").PdfReader(str(pdf)).pages))
        print("headings on pages:", heading_pages(pdf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
