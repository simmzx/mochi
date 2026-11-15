"""Drop a trailing blank page (no text, no images) from the compiled PDF."""

from __future__ import annotations

import sys
from pathlib import Path

import pypdf

pdf = Path(sys.argv[1])
reader = pypdf.PdfReader(str(pdf))
if len(reader.pages) < 2:
    raise SystemExit("nothing to do")

last = reader.pages[-1]
text = (last.extract_text() or "").strip()
images = 0
try:
    images = len(last.images)
except Exception:
    images = 0
if text or images:
    print(f"last page is not blank (text={len(text)}, images={images}); keeping it")
    raise SystemExit(0)

writer = pypdf.PdfWriter()
for page in reader.pages[:-1]:
    writer.add_page(page)
with pdf.open("wb") as fh:
    writer.write(fh)
print(f"dropped trailing blank page; {len(reader.pages)} -> {len(reader.pages) - 1}")
