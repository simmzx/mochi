"""Convert the report DOCX into LaTeX chapters for the MPU mpThesis template.

The DOCX remains the single source of prose; this converter preserves paragraph text, maps
headings to chapter/section/subsection, converts tables into floats (wide ones resized to the
text width), groups bullet paragraphs into itemize blocks and maps inline images to the PNGs in
paper/figures/.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(r"D:\deepseek\workshop\mochi")
DOCX = ROOT / "paper" / "MOCHI_Final_Project_Report.docx"
OUT = ROOT / "paper" / "latex" / "chapters"
OUT.mkdir(parents=True, exist_ok=True)

FIG_BY_NUMBER = {
    "1": "fig_workflow_ref.png",
    "2": "fig_sankey.png",
    "3": "fig_target_heatmap.png",
    "4": "fig_panels.png",
}
REPO_URL = "https://github.com/simmzx/mochi"

UNICODE = {
    "→": r"$\rightarrow$",
    "←": r"$\leftarrow$",
    "×": r"$\times$",
    "≥": r"$\geq$",
    "≤": r"$\leq$",
    "≈": r"$\approx$",
    "°C": r"$^{\circ}$C",
    "°": r"$^{\circ}$",
    "µ": r"$\mu$",
    "μ": r"$\mu$",
    "–": "--",
    "—": "---",
    "’": "'",
    "‘": "`",
    "“": "``",
    "”": "''",
    "…": r"\ldots{}",
    "α": r"$\alpha$",
    "β": r"$\beta$",
    "±": r"$\pm$",
    "·": r"$\cdot$",
}


# long chemical names need explicit break points, otherwise justified lines stretch badly
HYPHENATE = {
    "diethylglycine": r"di\-ethyl\-gly\-cine",
    "dimethylaniline": r"di\-methyl\-an\-i\-line",
    "immunoprecipitation": r"im\-mu\-no\-pre\-cip\-i\-ta\-tion",
    "co-immunoprecipitation": r"co-im\-mu\-no\-pre\-cip\-i\-ta\-tion",
    "strictosidine": r"stric\-to\-si\-dine",
    "secologanin": r"se\-co\-lo\-ga\-nin",
    "tryptamine": r"tryp\-ta\-mine",
    "benorilate": r"ben\-or\-i\-late",
    "chemoselectivity": r"chemo\-se\-lec\-tiv\-ity",
}
CHAPTER_TITLE_OVERRIDE = {"Introduction and Literature Review": "Introduction"}


REPO_LINK = r"\href{https://github.com/simmzx/mochi}{\texttt{github.com/simmzx/mochi}}"


def hyphenate(text: str) -> str:
    for word, broken in HYPHENATE.items():
        text = text.replace(word, broken)
    return text.replace("https://github.com/simmzx/mochi", REPO_LINK)


def escape(text: str) -> str:
    # protect command-line flags such as --seed-genes from becoming an en dash
    text = text.replace("--", "\x00")
    text = text.replace("\\", r"\textbackslash{}")
    for ch, rep in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                    ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                    ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        text = text.replace(ch, rep)
    for a, b in UNICODE.items():
        text = text.replace(a, b)
    text = text.replace("\x00", "-{}-")
    return hyphenate(text)


def run_size(p: Paragraph) -> float:
    sizes = [r.font.size.pt for r in p.runs if r.font.size is not None]
    return max(sizes) if sizes else 0.0


def is_bold(p: Paragraph) -> bool:
    return any(r.bold for r in p.runs if r.text.strip())


def has_image(p: Paragraph) -> bool:
    return bool(p._p.findall(".//" + qn("w:drawing")))


def is_bullet(p: Paragraph) -> bool:
    return p.style is not None and p.style.name.lower().startswith("list")


def chapter_title(text: str) -> str:
    title = re.sub(r"^§\d+\s*", "", text).strip()
    return CHAPTER_TITLE_OVERRIDE.get(title, title)


def emit_table(tbl: Table, caption: str) -> str:
    rows = []
    for row in tbl.rows:
        rows.append([escape(" ".join(p.text for p in cell.paragraphs).strip()) for cell in row.cells])
    ncol = max(len(r) for r in rows)
    body = [r"\hline"]
    for i, row in enumerate(rows):
        body.append(" & ".join(row) + r" \\")
        if i == 0:
            body.append(r"\hline")
    body.append(r"\hline")
    joined = "\n".join(body)
    header = [c.strip() for c in rows[0]] if rows else []
    if len(header) == 3 and header[1].lower() == "n":
        # the tool table: a narrow count column and a wide descriptive column
        tabular = ("\\begin{tabularx}{\\textwidth}{l c >{\\raggedright\\arraybackslash}X}\n"
                   + joined + "\n\\end{tabularx}\n")
        cap = escape(re.sub(r"^(Table|Figure)\s+[A-Z]?\d+\.\s*", "", caption))
        return ("\\begin{table}[htbp]\n\\centering\n\\small\n"
                f"\\caption{{{cap}}}\n" + tabular + "\n\\end{table}\n")
    if ncol >= 6:
        # many columns: keep them on one line and scale the whole table to the text width
        spec = "l" + "c" * (ncol - 1)
        tabular = "\\begin{tabular}{" + spec + "}\n" + joined + "\n\\end{tabular}\n"
        inner = "\\resizebox{\\textwidth}{!}{%\n" + tabular + "}"
    else:
        # few columns: let the cells wrap so long text does not run into the margin
        spec = "l" + ">{\\raggedright\\arraybackslash}X" * (ncol - 1)
        tabular = "\\begin{tabularx}{\\textwidth}{" + spec + "}\n" + joined + "\n\\end{tabularx}\n"
        inner = tabular
    cap = escape(re.sub(r"^(Table|Figure)\s+[A-Z]?\d+\.\s*", "", caption))
    return ("\\begin{table}[htbp]\n\\centering\n\\small\n"
            f"\\caption{{{cap}}}\n" + inner + "\n\\end{table}\n")


def main() -> None:
    doc = Document(str(DOCX))
    items: list[tuple[str, object]] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            items.append(("p", Paragraph(child, doc)))
        elif child.tag == qn("w:tbl"):
            items.append(("t", Table(child, doc)))

    chapters: list[tuple[str, list[str]]] = []
    current = None
    i = 0
    while i < len(items):
        kind, obj = items[i]
        if kind == "p":
            p = obj
            text = p.text.strip()
            if not text and not has_image(p):
                i += 1
                continue
            size = run_size(p)
            if text.startswith("§") and size >= 14:
                current = (chapter_title(text), [])
                chapters.append(current)
                i += 1
                continue
            if current is None:
                i += 1
                continue
            blocks = current[1]

            if is_bullet(p):
                bitems = []
                while i < len(items) and items[i][0] == "p" and is_bullet(items[i][1]):
                    q = items[i][1]
                    if q.text.strip():
                        bitems.append(escape(q.text.strip()))
                    i += 1
                if bitems:
                    blocks.append("\\begin{itemize}\n\\setlength{\\itemsep}{0pt}"
                                  "\\setlength{\\parskip}{0pt}\n"
                                  + "\n".join(f"\\item {x}" for x in bitems) +
                                  "\n\\end{itemize}\n")
                continue

            if text.startswith(("Table ", "Figure ")):
                i += 1
                continue

            if has_image(p):
                cap = ""
                if i + 1 < len(items) and items[i + 1][0] == "p":
                    cap = items[i + 1][1].text.strip()
                num = re.search(r"Figure\s+(\d+)", cap)
                fig = FIG_BY_NUMBER.get(num.group(1)) if num else None
                caption = escape(re.sub(r"^Figure\s+[A-Z]?\d+\.\s*", "", cap))
                if fig:
                    blocks.append("\\begin{figure}[htbp]\n\\centering\n"
                                  f"\\includegraphics[width=0.99\\textwidth]{{figures/{fig}}}\n"
                                  f"\\caption{{{caption}}}\n\\end{{figure}}\n")
                i += 1
                continue

            if is_bold(p) and 11.5 <= size < 14:
                m = re.match(r"^(\d+(?:\.\d+)*|A\.\d+)\s+(.*)$", text)
                if m:
                    number, rest = m.group(1), m.group(2)
                    depth = number.count(".")
                    cmd = "section" if depth <= 1 else ("subsection" if depth == 2 else "subsubsection")
                    blocks.append(f"\\{cmd}{{{escape(rest)}}}\n")
                    i += 1
                    continue

            blocks.append(escape(text) + "\n")
        else:
            tbl = obj
            cap = ""
            if i + 1 < len(items) and items[i + 1][0] == "p":
                cap = items[i + 1][1].text.strip()
            if current is not None:
                current[1].append(emit_table(tbl, cap))
        i += 1

    for idx, (title, blocks) in enumerate(chapters, 1):
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(blocks))
        path = OUT / f"Chapter{idx}.tex"
        path.write_text(f"\\chapter{{{escape(title)}}}\\label{{ch:{idx}}}\n\n{text}\n",
                        encoding="utf-8")
        print("wrote", path.name, len(text), "chars")


if __name__ == "__main__":
    main()
