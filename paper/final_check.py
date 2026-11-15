import re

import pypdf

for f in ["MOCHI_Final_Project_Report_LaTeX.pdf", "MOCHI_Final_Project_Report.pdf"]:
    r = pypdf.PdfReader(f)
    flat = re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in r.pages))
    links = []
    for page in r.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            uri = (obj.get("/A") or {}).get("/URI")
            if uri:
                links.append(str(uri))
    print("==", f, len(r.pages), "pages")
    print("   blank pages:", [i + 1 for i, p in enumerate(r.pages) if len((p.extract_text() or "").strip()) < 40])
    print("   external links:", len(links), sorted(set(links))[:3])
    print("   figures:", sorted({int(m) for m in re.findall(r"Figure (\d)", flat)}))
    for bad in ["45 tools", "Figure 5", "doubles as", "The code, the run"]:
        if bad in flat:
            print("   STALE:", bad)
    for good in ["46 tools", "capability domains", "Keywords", "BIBLIOGRAPHY"]:
        print("   ok" if good in flat else "   MISSING", good)
