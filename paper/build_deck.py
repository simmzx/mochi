"""Build the MOCHI presentation: academic, minimal, high-contrast deck.

All text, tables and shapes are native PowerPoint objects (editable); figures are imported
from paper/figures as separate pictures.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
OUT = HERE / "MOCHI_Final_Project_Slides.pptx"

W, H = Inches(13.333), Inches(7.5)
MX = Inches(0.72)

INK = RGBColor(0x12, 0x23, 0x2E)
NAVY = RGBColor(0x10, 0x2A, 0x3C)
NAVY_2 = RGBColor(0x1B, 0x3E, 0x56)
GOLD = RGBColor(0xB0, 0x8A, 0x3E)
TEAL = RGBColor(0x2C, 0x7A, 0x8C)
MUTED = RGBColor(0x5D, 0x6D, 0x7B)
LINE = RGBColor(0xDD, 0xE3, 0xE8)
BG = RGBColor(0xFB, 0xFC, 0xFD)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT = RGBColor(0xF2, 0xF5, 0xF7)

FONT = "Calibri"
FONT_LIGHT = "Calibri Light"
TOTAL = 18


def _spacing(run, spc):
    run.font._rPr.set("spc", str(int(spc * 100)))


def text(slide, x, y, w, h, s, size=14, bold=False, color=INK, font=FONT, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=None, line=None, italic=False):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, chunk in enumerate(s.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line is not None:
            p.line_spacing = line
        run = p.add_run()
        run.text = chunk
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
        run.font.name = font
        if spacing:
            _spacing(run, spacing)
    return box


def rect(slide, x, y, w, h, fill=None, line_color=None, line_w=1.0, shape=MSO_SHAPE.RECTANGLE,
         radius=None):
    shp = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line_color is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    sp = shp._element
    style = sp.find(qn("p:style"))
    if style is not None:
        sp.remove(style)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    return shp


def rule(slide, x, y, w, color=GOLD, thickness=2.5):
    rect(slide, x, y, w, Pt(thickness), fill=color)


def bg(slide, color=BG):
    rect(slide, 0, 0, W, H, fill=color)


def footer(slide, idx, label="MOCHI · AIDD8122 Final Project"):
    rect(slide, MX, Inches(7.02), W - 2 * MX, Pt(1), fill=LINE)
    text(slide, MX, Inches(7.12), Inches(7.0), Inches(0.3), label, 9, False, MUTED, spacing=0.4)
    text(slide, W - MX - Inches(1.2), Inches(7.12), Inches(1.2), Inches(0.3),
         f"{idx:02d} / {TOTAL:02d}", 9, False, MUTED, align=PP_ALIGN.RIGHT, spacing=0.4)


def header(slide, idx, eyebrow, title, subtitle=None):
    bg(slide)
    rect(slide, 0, 0, W, Pt(3), fill=NAVY)
    text(slide, MX, Inches(0.50), Inches(9.0), Inches(0.28), eyebrow.upper(), 10, True, GOLD,
         spacing=1.6)
    text(slide, MX, Inches(0.78), W - 2 * MX - Inches(0.4), Inches(0.6), title, 26, True, INK,
         font=FONT_LIGHT)
    rule(slide, MX, Inches(1.40), Inches(0.9), GOLD, 3)
    if subtitle:
        text(slide, MX, Inches(1.55), W - 2 * MX, Inches(0.34), subtitle, 12.5, False, MUTED)


def card(slide, x, y, w, h, title=None, body=None, accent=TEAL, body_size=12.5, title_size=14,
         fill=WHITE, foot=None):
    rect(slide, x, y, w, h, fill=fill, line_color=LINE, line_w=1)
    rect(slide, x, y, Pt(4), h, fill=accent)
    ty = y + Inches(0.20)
    if title:
        text(slide, x + Inches(0.24), ty, w - Inches(0.42), Inches(0.30), title, title_size, True, INK)
        ty = ty + Inches(0.38)
    if body:
        text(slide, x + Inches(0.24), ty, w - Inches(0.42), h - (ty - y) - Inches(0.42), body,
             body_size, False, MUTED, line=1.15)
    if foot:
        text(slide, x + Inches(0.24), y + h - Inches(0.36), w - Inches(0.42), Inches(0.24), foot, 8.5,
             True, accent, spacing=0.8)


def stat(slide, x, y, w, value, label, color=INK, vsize=38, lsize=11):
    text(slide, x, y, w, Inches(0.62), value, vsize, False, color, font=FONT_LIGHT)
    text(slide, x, y + Inches(0.58), w, Inches(0.55), label, lsize, False, MUTED, line=1.1)


def bullets(slide, x, y, w, h, items, size=13, color=INK, gap=8, bullet_color=TEAL):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.12
        dot = p.add_run()
        dot.text = "—  "
        dot.font.size = Pt(size)
        dot.font.bold = True
        dot.font.color.rgb = bullet_color
        dot.font.name = FONT
        run = p.add_run()
        run.text = item
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = FONT
    return box


def picture(slide, name, x, y, w):
    return slide.shapes.add_picture(str(FIG / name), x, y, width=w)


def table(slide, rows, x, y, w, col_widths, row_h=Inches(0.42), header_h=Inches(0.42),
          font=12, head_font=10.5):
    n_rows, n_cols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, x, y, w, header_h + row_h * (n_rows - 1))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False
    total = sum(col_widths)
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = Emu(int(w * cw / total))
    tbl.rows[0].height = header_h
    for r in range(1, n_rows):
        tbl.rows[r].height = row_h
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.10)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (WHITE if r % 2 else SOFT)
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(val)
            run.font.name = FONT
            run.font.size = Pt(head_font if r == 0 else font)
            run.font.bold = r == 0
            run.font.color.rgb = WHITE if r == 0 else INK
    return tbl


def s_cover(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s, NAVY)
    for cx, cy, d in [(-1.6, 4.2, 6.4), (9.4, -2.0, 6.0)]:
        shp = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(cy), Inches(d), Inches(d))
        shp.fill.solid()
        shp.fill.fore_color.rgb = NAVY_2
        shp.line.fill.background()
        shp.shadow.inherit = False
        sp = shp._element
        st = sp.find(qn("p:style"))
        if st is not None:
            sp.remove(st)
    rect(s, Inches(0.88), Inches(1.45), Pt(5), Inches(4.6), fill=GOLD)
    text(s, Inches(1.25), Inches(1.42), Inches(9.0), Inches(0.3), "AIDD8122  ·  FINAL PROJECT", 11.5,
         True, RGBColor(0xC9, 0xD3, 0xDA), spacing=2.2)
    text(s, Inches(1.22), Inches(1.78), Inches(10.5), Inches(1.1), "MOCHI", 72, True, WHITE,
         font=FONT_LIGHT)
    text(s, Inches(1.25), Inches(3.02), Inches(9.6), Inches(1.0),
         "A self-evolving multi-agent system\nfor end-to-end AI drug discovery", 24, False,
         RGBColor(0xE8, 0xEE, 0xF2), font=FONT_LIGHT, line=1.2)
    rule(s, Inches(1.25), Inches(4.40), Inches(2.6), GOLD, 2.5)
    text(s, Inches(1.25), Inches(4.60), Inches(9.0), Inches(0.9),
         "ZHANG XIANG   ·   P2600300   ·   GROUP 3\n16 November 2026", 13, False,
         RGBColor(0xB9, 0xC6, 0xCF), line=1.35)
    rect(s, Inches(11.42), Inches(5.80), Inches(1.30), Inches(1.30), fill=WHITE,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
    s.shapes.add_picture(str(FIG / "fig_logo.png"), Inches(11.50), Inches(5.86), height=Inches(1.16))


def s_agenda(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "Contents", "What this talk covers")
    items = [
        ("01", "The problem", "AIDD produces more evidence than anyone can triage"),
        ("02", "Why agents fall short", "Single-model tool use is not auditable science"),
        ("03", "MOCHI", "Four agents, one tool ocean, a deterministic veto"),
        ("04", "Four scenarios", "Targets · enzymes · routes · lab protocols"),
        ("05", "What it proves", "Hindcasts, benchmarks, ablations, reproducibility"),
    ]
    y = Inches(1.92)
    for num, title, sub in items:
        text(s, MX, y - Inches(0.02), Inches(0.7), Inches(0.4), num, 13, True, GOLD, spacing=1.0)
        text(s, MX + Inches(0.72), y - Inches(0.05), Inches(4.4), Inches(0.36), title, 16, True, INK)
        text(s, MX + Inches(4.95), y - Inches(0.01), Inches(6.9), Inches(0.36), sub, 13, False, MUTED)
        rect(s, MX, y + Inches(0.46), W - 2 * MX, Pt(1), fill=LINE)
        y = y + Inches(0.88)


def s_problem(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "01 · The problem", "Evidence is cheap; decisions are not",
           "A single decision needs heterogeneous data, explicit constraints and a written rationale")
    cards = [
        ("Targets", "A protein is worth pursuing only if it is disease-linked, mechanistically "
                    "plausible, druggable and still novel.", TEAL),
        ("Molecules", "A variant is worth synthesising only if it is close enough to the active site "
                      "yet conservative enough to fold.", GOLD),
        ("Routes & protocols", "A route needs purchasable leaves; a protocol needs every volume and "
                               "temperature to be physically feasible.", RGBColor(0x8C, 0x5A, 0x5A)),
    ]
    x = MX
    for title, body, accent in cards:
        card(s, x, Inches(2.02), Inches(3.86), Inches(1.92), title, body, accent=accent, body_size=12.5)
        x = x + Inches(4.16)
    rule(s, MX, Inches(4.30), W - 2 * MX, LINE, 1)
    text(s, MX, Inches(4.52), Inches(11.9), Inches(0.5),
         "Today each of these judgements is assembled by hand, from ten sources, with no audit trail.",
         17, False, INK, font=FONT_LIGHT)
    text(s, MX, Inches(5.20), Inches(11.9), Inches(0.9),
         "The engineering question is therefore not \u201ccan a model call a database?\u201d but "
         "\u201ccan a system make decisions that are reproducible and correctable?\u201d",
         13, False, MUTED, italic=True, line=1.2)


def s_why(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "02 · Gap", "Why a single LLM with tools is not enough",
           "Three failure modes that recur across agentic biomedical systems")
    cols = [
        ("01", "Single-task evaluation", "A chemistry agent is never shown to plan a CRISPR screen, "
                                         "so generality is asserted, not measured."),
        ("02", "The judge is a model", "A confident but wrong plan can pass review when the critic is "
                                       "the same kind of model that wrote the plan."),
        ("03", "No provenance", "The tool outputs behind a claim are rarely preserved, so the result "
                                "cannot be re-derived or audited."),
    ]
    x = MX
    for num, title, body in cols:
        rect(s, x, Inches(1.98), Inches(3.86), Inches(2.10), fill=WHITE, line_color=LINE)
        text(s, x + Inches(0.26), Inches(2.12), Inches(0.8), Inches(0.5), num, 20, False, GOLD,
             font=FONT_LIGHT)
        text(s, x + Inches(0.26), Inches(2.64), Inches(3.3), Inches(0.4), title, 14.5, True, INK)
        text(s, x + Inches(0.26), Inches(3.04), Inches(3.34), Inches(0.95), body, 11.5, False, MUTED,
             line=1.18)
        x = x + Inches(4.16)
    rect(s, MX, Inches(4.42), W - 2 * MX, Inches(1.00), fill=SOFT)
    rect(s, MX, Inches(4.42), Pt(4), Inches(1.00), fill=TEAL)
    text(s, MX + Inches(0.26), Inches(4.60), W - 2 * MX - Inches(0.5), Inches(0.7),
         "MOCHI's answer: a control plane with explicit stage contracts, a deterministic audit that can "
         "veto the model, and a provenance log for every external call.", 14, False, INK, line=1.2)
    text(s, MX, Inches(5.75), W - 2 * MX, Inches(0.6),
         "Each failure mode maps to one mechanism: contracts (evaluation), a deterministic critic "
         "(judging), and provenance (reproducibility).", 12, False, MUTED, italic=True)


def s_principle(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "03 · Design", "The model proposes, Python disposes",
           "Four agents with narrow contracts; every number is computed by code, not generated by text")
    pillars = [
        ("Manager", "Plans four stages, retrieves a reasoning template by TF-IDF, calibrates the final "
                    "weights.", TEAL, "contract  ·  stages[4] + weight vector"),
        ("Developer", "Executes a deterministic stage program; may only change whitelisted parameters.",
         GOLD, "contract  ·  steps + parameters"),
        ("Critic", "Runs the hard audit first, then asks the model; the stricter verdict wins.", TEAL,
         "contract  ·  verdict + gaps + tool requests"),
        ("Tool creator", "Searches, writes, tests and registers a missing tool, at most three repairs.",
         GOLD, "contract  ·  tool + control suite"),
    ]
    pos = [(MX, Inches(2.00)), (MX + Inches(6.18), Inches(2.00)),
           (MX, Inches(3.78)), (MX + Inches(6.18), Inches(3.78))]
    for (title, body, accent, foot), (x, y) in zip(pillars, pos):
        card(s, x, y, Inches(5.86), Inches(1.60), title, body, accent=accent, body_size=12.5,
             title_size=15, foot=foot)
    text(s, MX, Inches(5.72), W - 2 * MX, Inches(0.5),
         "A failed control cannot be waived by the language model — that single rule is what makes the "
         "outputs reportable.", 13, False, MUTED, italic=True)


def s_workflow(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "03 · Workflow", "One run, end to end",
           "The target-discovery case: plan, execute, audit, and build the missing tool")
    picture(s, "fig_workflow_ref.png", MX, Inches(1.98), Inches(8.05))
    x = MX + Inches(8.34)
    rect(s, x - Inches(0.18), Inches(1.98), Pt(1), Inches(4.25), fill=LINE)
    steps = [
        ("01", "Plan", "Four stages, each with goals, tools and success criteria."),
        ("02", "Execute", "Stage programs write JSON/CSV artefacts and figures."),
        ("03", "Audit", "Deterministic checks; the model cannot overrule a failure."),
        ("04", "Evolve", "A capability gap triggers a new tool, tested before use."),
    ]
    y = Inches(1.98)
    for num, name, body in steps:
        text(s, x, y, Inches(0.42), Inches(0.3), num, 10, True, GOLD, spacing=0.8)
        text(s, x + Inches(0.46), y - Inches(0.03), Inches(3.3), Inches(0.3), name, 12.5, True, INK)
        text(s, x + Inches(0.46), y + Inches(0.26), Inches(3.4), Inches(0.62), body, 10.5, False,
             MUTED, line=1.12)
        y = y + Inches(1.06)


def s_scenarios(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scope", "Four scenarios, one orchestrator",
           "Only the four stage programs and a template change between tasks")
    rows = [
        ["Scenario", "Input", "Core computation", "Output"],
        ["S1  Target discovery", "Anchor gene + disease", "Six-dimension evidence scoring",
         "Ranked effectors"],
        ["S2  Enzyme design", "Enzyme + round-1 data", "Structure- and prior-guided scoring",
         "15-variant library"],
        ["S3  Retrosynthesis", "Target SMILES", "Template AND-OR search to stock", "Synthesis route"],
        ["S4  Protocol → SDL", "Natural-language SOP", "Typed compilation + validation", "SDL program"],
    ]
    table(s, rows, MX, Inches(2.02), W - 2 * MX, [3.2, 3.0, 4.6, 2.9], row_h=Inches(0.62),
          header_h=Inches(0.42), font=13, head_font=11)
    text(s, MX, Inches(5.62), W - 2 * MX, Inches(0.8),
         "Same agents, same audit, same report machinery — a scenario supplies ~400 lines of scientific "
         "content and nothing else.", 13, False, MUTED, italic=True)


def s_tools(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "03 · Tool layer", "46 tools behind one cached, logged interface",
           "Eleven categories, one HTTP layer: cached, hashed, provenance-logged")
    picture(s, "fig_sankey.png", MX, Inches(1.98), Inches(7.85))
    x = MX + Inches(8.15)
    for i, (val, lab, col) in enumerate([("46", "deterministic tools", TEAL),
                                        ("11", "categories", INK),
                                        ("1", "tool created at runtime", GOLD)]):
        stat(s, x, Inches(2.05 + i * 1.32), Inches(4.4), val, lab, col, vsize=34)
    text(s, x, Inches(6.10), Inches(4.4), Inches(0.6),
         "Every call appends URL, status, latency and payload hash to provenance.jsonl.",
         10.5, False, MUTED, line=1.15)


def s_target(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scenario 1", "DPEP1 needs a receptor partner",
           "A GPI-anchored ectoenzyme (P16444: 411 aa, no TM helix, no intracellular domain)")
    rows = [
        ["Rank", "Gene", "Composite", "Competence", "Disease", "Druggability"],
        ["1", "ASIC1", "0.496", "0.69", "0.41", "0.72"],
        ["2", "NOTCH1", "0.481", "0.68", "0.36", "0.92"],
        ["3", "FZD7", "0.459", "0.85", "0.23", "0.84"],
        ["4", "ZNRF3", "0.449", "0.75", "0.49", "0.25"],
        ["5", "ACE2", "0.443", "0.45", "0.20", "1.00"],
    ]
    table(s, rows, MX, Inches(2.02), Inches(7.45), [1.0, 1.6, 1.7, 1.6, 1.3, 1.7],
          row_h=Inches(0.58), header_h=Inches(0.42), font=12.5, head_font=10)
    x = MX + Inches(7.85)
    stat(s, x, Inches(2.02), Inches(4.4), "34 → 10", "candidates → competence-passing", TEAL, vsize=32)
    stat(s, x, Inches(3.32), Inches(4.4), "13 / 13", "controls passed by the created scorer", GOLD,
         vsize=32)
    bullets(s, x, Inches(4.70), Inches(4.6), Inches(1.6), [
        "Top four are membrane signalling proteins co-expressed with DPEP1",
        "Scores are close: the top five span 0.053",
    ], size=11.5, gap=6)
    rect(s, MX, Inches(6.08), W - 2 * MX, Inches(0.62), fill=SOFT)
    rect(s, MX, Inches(6.08), Pt(4), Inches(0.62), fill=GOLD)
    text(s, MX + Inches(0.24), Inches(6.20), W - 2 * MX - Inches(0.5), Inches(0.4),
         "Top-1 flips between ASIC1 and NOTCH1 when the critic re-calibrates weights; the top-four set "
         "is stable, so the output is a prioritisation, not a verdict.", 11.5, False, INK)


def s_lrp6(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scenario 1, hindcast", "LRP6 is competent, but not data-nominated",
           "The published effector, scored on exactly the same terms as a hypothesis")
    stat(s, MX, Inches(1.98), Inches(3.1), "0.754", "signalling competence (highest tier)", TEAL, 44)
    stat(s, MX + Inches(3.25), Inches(1.98), Inches(3.1), "0.098", "association with DPEP1 "
         "(r = \u22120.084)", GOLD, 44)
    stat(s, MX + Inches(6.50), Inches(1.98), Inches(3.1), "11 / 11", "rank when forced into the "
         "candidate list", INK, 44)
    rule(s, MX, Inches(3.85), W - 2 * MX, LINE, 1)
    text(s, MX, Inches(4.05), Inches(5.9), Inches(0.35), "What the system reports", 14, True, INK)
    bullets(s, MX, Inches(4.45), Inches(5.8), Inches(1.8), [
        "The data-driven channels do not nominate LRP6: no PPI, no co-expression, no shared pathway",
        "The missing link is stated explicitly instead of being hidden",
    ], size=12, gap=8)
    text(s, MX + Inches(6.35), Inches(4.05), Inches(5.6), Inches(0.35), "What the wet lab then did",
         14, True, INK)
    bullets(s, MX + Inches(6.35), Inches(4.45), Inches(5.6), Inches(1.8), [
        "Co-IP, knockdown / overexpression, qPCR and Western blot",
        "Interface mutagenesis confirmed the DPEP1\u2013LRP6 dependency",
    ], size=12, gap=8, bullet_color=GOLD)
    text(s, MX, Inches(6.15), W - 2 * MX, Inches(0.5),
         "A system that manufactured support here would have been right for the wrong reason.",
         12, False, MUTED, italic=True)


def s_enzyme(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scenario 2", "A 15-variant library for strictosidine synthase",
           "154 positions within 12 \u00c5 of the catalytic cluster \u2192 2,773 single substitutions")
    picture(s, "fig_panel_a.png", MX, Inches(1.98), Inches(7.35))
    x = MX + Inches(7.70)
    for i, (val, lab, col) in enumerate([("1 / 2,773", "rank of the published hit M276L", TEAL),
                                        ("3 / 3", "dead positions excluded", GOLD),
                                        ("15", "variants, \u2264 2 per position", INK)]):
        stat(s, x, Inches(2.02 + i * 1.30), Inches(4.6), val, lab, col, vsize=32)
    text(s, x, Inches(6.10), Inches(4.6), Inches(0.6),
         "V176F (second shell) is missed and reported as a limitation, not hidden.",
         10.5, False, MUTED, italic=True, line=1.15)


def s_retro(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scenario 3", "A two-step route to a hindered local anaesthetic",
           "Lidocaine: the amide is cut first, then the non-stock glycine is assembled")
    picture(s, "fig_panel_b.png", MX, Inches(1.98), Inches(6.05))
    x0, bw, bh = MX + Inches(7.05), Inches(4.45), Inches(0.86)
    rows = [
        ("step 1 \u2014 amide coupling", "2,6-dimethylaniline  +  diethylamine\n+  bromoacetic acid",
         Inches(1.98), GOLD),
        ("step 2 \u2014 N-alkylation", "N,N-diethylglycine   (not in stock)", Inches(3.08), TEAL),
        ("product", "Lidocaine \u2014 every leaf is purchasable", Inches(4.18), NAVY),
    ]
    for tag, label, y, col in rows:
        rect(s, x0, y, bw, bh, fill=WHITE, line_color=col, line_w=1.5,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        text(s, x0 + Inches(0.14), y + Inches(0.12), bw - Inches(0.28), Inches(0.24), tag, 9, True,
             col, spacing=0.6)
        text(s, x0 + Inches(0.14), y + Inches(0.36), bw - Inches(0.28), bh - Inches(0.44), label, 11,
             True, INK, line=1.1)
    for y in (Inches(2.88), Inches(3.98)):
        arrow = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, x0 + bw / 2 - Inches(0.08),
                                   y + Inches(0.02), Inches(0.16), Inches(0.16))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = MUTED
        arrow.line.fill.background()
        arrow.shadow.inherit = False
        sp = arrow._element
        st = sp.find(qn("p:style"))
        if st is not None:
            sp.remove(st)
    text(s, MX, Inches(5.62), Inches(6.4), Inches(0.4),
         "8 / 8 solved  \u00b7  1.62 planned steps vs 1.75 in the literature", 13, True, INK)


def s_sdl(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "04 · Scenario 4", "From a written SOP to validated robot instructions",
           "Parse \u2192 compile to opcodes \u2192 static validation \u2192 digital-twin simulation")
    picture(s, "fig_panel_c.png", MX, Inches(1.98), Inches(7.55))
    x = MX + Inches(7.95)
    for i, (val, lab, col) in enumerate([("6 / 6", "clean protocols valid", TEAL),
                                        ("5 / 5", "corrupted protocols caught", GOLD)]):
        stat(s, x, Inches(2.05 + i * 1.30), Inches(4.4), val, lab, col, vsize=34)
    text(s, x, Inches(4.80), Inches(4.5), Inches(1.4),
         "Vessel overflow, over-temperature, flash point, missing volume, zero duration \u2014 each "
         "caught before execution.", 11.5, False, MUTED, line=1.15)
    text(s, MX, Inches(5.95), Inches(7.4), Inches(0.5),
         "The compiled program is executable as written: 48 min, 6 opcodes, no unresolved default.",
         12, False, MUTED, italic=True)


def s_ablation(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "05 · Evidence", "Both mechanisms are load-bearing",
           "Two ablations, one question each: does removing the mechanism remove a capability?")
    rows = [
        ["Configuration", "Stage 3", "Stage 4", "Key metric"],
        ["Full pipeline (S1)", "10 competent", "10 ranked", "top-1 ASIC1, 0.496"],
        ["No tool creation (S1)", "capability gap", "0 ranked", "no ranking produced"],
        ["Full pipeline (S2)", "2,773 scored", "15 designed", "M276L rank 1"],
        ["No experimental prior (S2)", "2,773 scored", "15 designed", "M276L rank 4"],
    ]
    table(s, rows, MX, Inches(2.02), W - 2 * MX, [4.2, 3.0, 2.6, 3.6], row_h=Inches(0.60),
          header_h=Inches(0.42), font=13, head_font=11)
    text(s, MX, Inches(5.55), W - 2 * MX, Inches(0.9),
         "Without the created scorer the target pipeline cannot enforce the effector constraint at all; "
         "without the experimental prior the true best variant falls from first to fourth.",
         13, False, INK, font=FONT_LIGHT, line=1.25)


def s_repro(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "05 · Engineering", "Reproducibility is a design choice",
           "Two engines behind one interface; every number computed from cached, hashed responses")
    cards = [
        ("Engine A", "OpenAI-compatible endpoint\n(deepseek-V4.1-pro)", TEAL),
        ("Engine B", "Deterministic offline engine\n(no key, same contracts)", GOLD),
        ("Provenance", "provenance.jsonl \u00b7 transcript\nllm_calls \u00b7 run_summary", NAVY_2),
    ]
    x = MX
    for title, body, accent in cards:
        card(s, x, Inches(1.98), Inches(3.86), Inches(1.70), title, body, accent=accent, body_size=12)
        x = x + Inches(4.16)
    rect(s, MX, Inches(3.98), W - 2 * MX, Inches(1.35), fill=NAVY)
    text(s, MX + Inches(0.30), Inches(4.16), Inches(7.0), Inches(0.32),
         "One command reproduces the whole suite", 12.5, True, WHITE)
    text(s, MX + Inches(0.30), Inches(4.58), Inches(11.5), Inches(0.5),
         "$  python cases/run_all.py --engine mock      # four scenarios, local endpoint",
         12, False, RGBColor(0xCF, 0xDC, 0xE4), font="Consolas")
    text(s, MX, Inches(5.65), W - 2 * MX, Inches(0.8),
         "41 modules \u00b7 ~9.6k lines \u00b7 3 runtime dependencies \u00b7 no GPU \u00b7 cold run ~2 min, "
         "warm ~20 s", 12.5, False, MUTED)


def s_limits(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "05 · Limits", "Where the system stops \u2014 and why that is useful",
           "Every limitation is a concrete next experiment, not a disclaimer")
    items = [
        ("Template coverage", "Six reaction classes; epoxide opening and Friedel\u2013Crafts are out of "
                              "scope and are the next tool to add.", TEAL),
        ("Second-shell chemistry", "V176F is missed because the scorer is physics-light; an energy "
                                   "model is the upgrade path.", GOLD),
        ("Panel-based search", "A 600-gene signalling panel, not the whole transcriptome.", TEAL),
        ("Imperative protocols", "The parser handles standard SOPs, not arbitrary prose.", GOLD),
    ]
    pos = [(MX, Inches(1.98)), (MX + Inches(6.18), Inches(1.98)),
           (MX, Inches(3.95)), (MX + Inches(6.18), Inches(3.95))]
    for (title, body, accent), (x, y) in zip(items, pos):
        card(s, x, y, Inches(5.86), Inches(1.72), title, body, accent=accent, body_size=12,
             title_size=14)
    text(s, MX, Inches(5.95), W - 2 * MX, Inches(0.6),
         "Each gap is exactly the kind of capability the tool-creation loop is designed to add.",
         13, False, MUTED, italic=True)


def s_conclusions(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, idx, "05 · Conclusions", "Three things to take away")
    items = [
        ("One orchestrator, four tasks", "Swapping the four stage programs was enough; no agent code "
                                         "was duplicated."),
        ("Self-evolution must be gated", "The tool the system wrote passed 13/13 controls before it "
                                         "entered the ocean \u2014 and the ablation proves it matters."),
        ("Auditability is the product", "A deterministic veto plus full provenance turns a plausible "
                                        "output into a reportable result."),
    ]
    y = Inches(2.00)
    for i, (title, body) in enumerate(items, 1):
        text(s, MX, y - Inches(0.06), Inches(0.9), Inches(0.6), f"0{i}", 28, False, GOLD,
             font=FONT_LIGHT)
        text(s, MX + Inches(0.95), y, Inches(5.4), Inches(0.4), title, 17, True, INK)
        text(s, MX + Inches(0.95), y + Inches(0.46), Inches(10.4), Inches(0.7), body, 12.5, False,
             MUTED, line=1.2)
        if i < 3:
            rect(s, MX, y + Inches(1.32), W - 2 * MX, Pt(1), fill=LINE)
        y = y + Inches(1.50)
    text(s, MX, Inches(6.35), W - 2 * MX, Inches(0.5),
         "The most useful result is a negative one: a target can be compelling and still unsupported by "
         "the available cohort.", 12, False, MUTED, italic=True)


def s_thanks(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s, NAVY)
    for cx, cy, d in [(-2.2, 4.8, 7.0), (9.0, -2.4, 7.0)]:
        shp = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(cy), Inches(d), Inches(d))
        shp.fill.solid()
        shp.fill.fore_color.rgb = NAVY_2
        shp.line.fill.background()
        shp.shadow.inherit = False
        sp = shp._element
        st = sp.find(qn("p:style"))
        if st is not None:
            sp.remove(st)
    rect(s, Inches(0.88), Inches(2.30), Pt(5), Inches(2.5), fill=GOLD)
    text(s, Inches(1.25), Inches(2.22), Inches(8.0), Inches(1.0), "Thank you", 60, True, WHITE,
         font=FONT_LIGHT)
    text(s, Inches(1.25), Inches(3.52), Inches(9.4), Inches(0.9),
         "Questions welcome \u2014 code, data and the one-command reproduction are online", 18, False,
         RGBColor(0xD5, 0xDF, 0xE6), font=FONT_LIGHT)
    rect(s, Inches(1.25), Inches(4.62), Inches(6.6), Pt(1), fill=RGBColor(0x3C, 0x55, 0x68))
    text(s, Inches(1.25), Inches(4.82), Inches(9.0), Inches(0.4), "github.com/simmzx/mochi", 14, True,
         RGBColor(0xE2, 0xC2, 0x7A), font="Consolas")
    text(s, Inches(1.25), Inches(5.45), Inches(8.0), Inches(0.4),
         "ZHANG XIANG \u00b7 P2600300 \u00b7 GROUP 3 \u00b7 AIDD8122", 11, False,
         RGBColor(0xA9, 0xB8, 0xC3), spacing=1.2)


def build(prs):
    builders = [s_cover, s_agenda, s_problem, s_why, s_principle, s_workflow, s_tools, s_scenarios,
                s_target, s_lrp6, s_enzyme, s_retro, s_sdl, s_ablation, s_repro, s_limits,
                s_conclusions, s_thanks]
    for idx, fn in enumerate(builders, 1):
        fn(prs, idx)


if __name__ == "__main__":
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    build(prs)
    prs.save(OUT)
    print("saved", OUT, "slides:", len(prs.slides._sldIdLst))
