"""Assemble the MOCHI report DOCX."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build_report import front_matter, new_document, OUT, title_page  # noqa: E402
from sections import section1, section2, section3  # noqa: E402
from sections2 import section4, section5, section6, section7  # noqa: E402


def main() -> int:
    doc = new_document()
    title_page(doc)
    front_matter(doc)
    section1(doc)
    section2(doc)
    section3(doc)
    section4(doc)
    section5(doc)
    section6(doc)
    section7(doc)
    doc.save(OUT)
    print("saved", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
