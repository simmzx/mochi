"""Two-pass build of the official report: body first, then TOC page numbers."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pypdf  # noqa: E402

import make_official_report as M  # noqa: E402

SNIPPETS = {
    "§1.": "now produces more candidate targets",
    "§2.": "This review moves from the methodological core",
    "§3.": "The project is organised around three questions",
    "§4.": "This section describes the architecture",
    "§5.": "All four scenarios were executed end-to-end",
    "§6.": "This project asked whether a multi-agent system",
    "§7.": "Yao, S., Zhao, J.",
}


def locate(pdf: Path) -> dict[str, str]:
    reader = pypdf.PdfReader(str(pdf))
    found: dict[str, str] = {}
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").replace("\u00a0", " ")
        flat = re.sub(r"\s+", " ", text)
        for num, snippet in SNIPPETS.items():
            if num not in found and snippet in flat:
                found[num] = str(i)
    missing = [k for k in SNIPPETS if k not in found]
    if missing:
        print("WARNING: could not locate", missing)
    return found


def main() -> int:
    docx = M.build({})
    pdf = M.to_pdf(docx)
    pages = locate(pdf)
    print("pass 1 pages:", pages, "| pdf pages:", len(pypdf.PdfReader(str(pdf)).pages))

    (HERE / "toc_pages.json").write_text(json.dumps(pages, indent=1), encoding="utf-8")
    docx = M.build(pages)
    pdf = M.to_pdf(docx)
    total = len(pypdf.PdfReader(str(pdf)).pages)
    print("pass 2 pages:", locate(pdf), "| pdf pages:", total)
    print("saved:", docx.name, "and", pdf.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
