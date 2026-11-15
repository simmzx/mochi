# MOCHI — a self-evolving multi-agent system for end-to-end AI drug discovery

MOCHI (*Multi-agent Orchestrator for Chemical and biomedical Intelligence*) is a small, auditable
multi-agent platform for AI-driven drug discovery. Four agents — a **manager**, a **developer**, a
**critic** and a **tool creator** — collaborate over a shared ocean of 46 scientific tools and four
interchangeable scenario adapters.

**Repository:** <https://github.com/simmzx/mochi> · **Licence:** Apache-2.0

| Scenario | Input | What MOCHI produces |
|---|---|---|
| `target_discovery` | anchor gene + disease | ranked effector targets, six-dimension evidence dossier, wet-lab plan |
| `enzyme_design` | enzyme + round-1 mutational data | ranked variant library with QuikChange primers and a hindcast |
| `retrosynthesis` | target SMILES | shortest route to purchasable building blocks |
| `sdl_protocol` | natural-language protocol | validated, machine-executable SDL program + execution timeline |

The design principle is simple: **the model proposes, Python disposes.** The manager plans, the
developer executes a deterministic stage program, and the critic runs a hard audit that the language
model cannot override. When the audit finds a missing capability, the tool-creation agent writes,
tests and registers a new tool before the stage is re-run.

## Headline results

| Scenario | Result |
|---|---|
| Target discovery (DPEP1, CRC) | 34 candidates → 10 signalling-competent → ASIC1 0.496, NOTCH1 0.481, FZD7 0.459, ZNRF3 0.449, ACE2 0.443; the created competence scorer passed 13/13 controls |
| LRP6 hindcast | competence 0.754 (top tier) but association 0.098 → not data-nominated; the missing link is reported and the wet lab resolved it |
| Enzyme design (strictosidine synthase) | 2,773 variants scored, 15-variant library; published hit M276L ranked **1st**; 3/3 dead positions excluded |
| Retrosynthesis | 8/8 benchmark drugs solved (mean 1.62 planned vs 1.75 literature steps); lidocaine in 2 steps |
| Protocol → SDL | 6/6 clean protocols valid, 5/5 corrupted protocols caught; 48-minute simulated timeline |
| Ablations | no tool creation → 0 ranked targets; no experimental prior → M276L falls from rank 1 to 4 |

## Quick start

```bash
git clone https://github.com/simmzx/mochi.git
cd mochi
pip install -r requirements.txt          # requests, PyYAML (+ matplotlib for figures)
```

```bash
python cases/run_all.py --engine offline  # all four scenarios, deterministic engine, no key
python cases/run_all.py --engine mock     # all four scenarios against a local OpenAI-compatible mock
python cases/run_all.py --engine openai   # real endpoint (MOCHI_API_KEY / MOCHI_BASE_URL / MOCHI_MODEL)

python tests/run_checks.py                # 8 offline self-checks
```

One-shot reproduction (dependencies + checks + all scenarios + documents):

```powershell
pwsh ./scripts/reproduce.ps1               # Windows
```

```bash
./scripts/reproduce.sh                     # macOS / Linux
```

Every run writes a self-contained directory under `outputs/`: `report.md`, `run_summary.json`,
`stage*.json` / `*.csv`, figures, `transcript.jsonl`, `llm_calls.jsonl` and `provenance.jsonl`.

## Repository layout

```
mochi/
├── mochi/                     # the package
│   ├── core.py                # orchestrator: plan → execute → audit → evolve
│   ├── agents/                # manager, developer, critic, tool creation
│   ├── scenarios/             # the four stage programs + registry
│   ├── tools/                 # 46 tools (omics, chemistry, structure, retrosynthesis, SDL)
│   ├── workflows/stages.py    # the target-discovery stage programs
│   ├── prompts/               # YAML prompt templates per agent
│   ├── templates/             # prebuilt reasoning templates (YAML)
│   ├── knowledge.py           # TF-IDF template retrieval + learning
│   ├── llm.py / offline.py    # OpenAI-compatible client and deterministic engine
│   ├── report.py              # target-discovery report renderer
│   ├── report_generic.py      # scenario report renderer + figures
│   └── cli.py                 # `mochi` command line
├── cases/                     # run_all.py + one case script per scenario
├── data/                      # round-1/round-2 enzyme data, protocol corpus
├── docs/                      # design notes + tool manifest
├── tests/                     # offline self-checks + local mock model server
├── tools_created/             # the tool the system wrote at runtime (evidence)
├── outputs/                   # the four canonical runs cited in the report
├── paper/                     # report (DOCX/PDF/LaTeX), slides (PPTX/PDF), figures, build scripts
├── scripts/                   # reproduce.ps1 / reproduce.sh / upload_to_github.ps1
└── docs/                      # design notes, tool manifest, repository map, upload guide
```

Two helper documents sit next to this README: **[docs/STRUCTURE.md](docs/STRUCTURE.md)** maps every
folder and file, and **[docs/UPLOAD.md](docs/UPLOAD.md)** walks through publishing the repository.

## Report and slides

| File | What it is |
|---|---|
| `paper/MOCHI_Final_Project_Report_LaTeX.pdf` | final report, typeset with the MPU `mpThesis` LaTeX template (24 pp.) |
| `paper/latex/` | the LaTeX project: `main.tex`, chapters, bibliography, figures, class and style files |
| `paper/MOCHI_Final_Project_Report.docx` | editable Word version of the same text |
| `paper/MOCHI_Final_Project_Slides.pptx` / `.pdf` | 18-slide presentation (10 min + Q&A), fully editable |

Rebuild the documents:

```bash
cd paper
python make_report.py                      # DOCX (+ PDF via LibreOffice)
python build_deck.py                       # PPTX presentation
cd latex && tectonic -X compile main.tex   # or: latexmk -xelatex main.tex
```

## How it stays reproducible

* **Two engines, one interface.** An OpenAI-compatible client (the reported runs use
  `deepseek-V4.1-pro`) and a deterministic offline engine implementing the same JSON contracts. The
  engine changes the wording of the rationale, never a number.
* **Provenance by construction.** Every HTTP call goes through one cached layer that records URL,
  parameters, status, latency, payload hash and cache hit in `provenance.jsonl`.
* **Auditable decisions.** The critic's audit is Python, not prose: a failed hard check raises the
  verdict to *revise*, a missing capability to *evolve*, and the model cannot waive either.
* **Pinned evidence.** `outputs/` keeps the four canonical runs behind every table in the report;
  `paper/audit_numbers.py` re-checks the tables against those artefacts.

## Environment

* Python 3.10+ (developed on 3.12), no GPU required
* Runtime dependencies: `requests`, `PyYAML`; `matplotlib` for figures; `rdkit` for the
  retrosynthesis scenario (pre-built wheels on all platforms)
* Network access is needed for the public databases (UniProt, Open Targets, cBioPortal, STRING,
  IntAct, PubMed, KEGG, Reactome, ChEMBL, DGIdb); responses are cached for a week

## Licence and credits

Released under the Apache-2.0 licence (see `LICENSE`). MOCHI builds on ideas from tool-augmented
language models and agentic biomedical systems; the full reference list is in the report (§6).
