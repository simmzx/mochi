# Repository map

```
mochi/                              the project (this folder is the git repository)
│
├── README.md                       project overview, results, quick start, layout
├── LICENSE                         Apache-2.0
├── .gitattributes / .gitignore     LF normalisation, ignored build caches
├── requirements.txt                requests, PyYAML, matplotlib, rdkit
├── pyproject.toml                  packaging (`pip install -e .`) and `mochi` entry point
├── .env.example                    engine / endpoint configuration template
│
├── mochi/                          the Python package (41 modules, ~9.6k lines)
│   ├── __init__.py                 public API: `initialize()`, `Mochi`
│   ├── core.py                     orchestrator: retrieve → plan → execute → audit → evolve
│   ├── settings.py                 environment-driven configuration
│   ├── llm.py                      OpenAI-compatible client (60-line requests wrapper)
│   ├── offline.py                  deterministic reference engine (same JSON contracts)
│   ├── knowledge.py                TF-IDF template library + learning
│   ├── memory.py / stats.py        run memory, statistics helpers
│   ├── report.py                   target-discovery report renderer (markdown + figures)
│   ├── report_generic.py           scenario report renderer + panels
│   ├── cli.py                      `mochi run | config | doctor | tools`
│   ├── agents/
│   │   ├── manager.py              plan, calibrate weights, synthesise the narrative
│   │   ├── dev.py                  execute a stage program, apply whitelisted parameters
│   │   ├── critic.py               deterministic audit + review, veto power
│   │   └── tool_creation.py        design → write → test → register a new tool
│   ├── workflows/stages.py         target-discovery stage programs (S1)
│   ├── scenarios/
│   │   ├── __init__.py             scenario registry (stage programs, audit, renderer)
│   │   ├── enzyme_design.py        S2: structure- and prior-guided variant design
│   │   ├── retrosynthesis.py       S3: template AND-OR search to purchasable stock
│   │   └── sdl_protocol.py         S4: protocol → SDL compiler + validator + simulator
│   ├── tools/                      46 tools, one decorator, cached + provenance-logged HTTP
│   │   ├── registry.py             registration, manifests, dynamic loading
│   │   ├── http.py                 cache, retries, provenance.jsonl
│   │   ├── uniprot.py …            database tools (UniProt, Open Targets, cBioPortal, …)
│   │   ├── protein_structure.py    AlphaFold geometry, conservation, primer design
│   │   ├── retrosynthesis.py       disconnection templates, stock list, route search
│   │   └── sdl.py                  protocol parser, compiler, validator, simulator
│   ├── prompts/                    manager / dev / critic / tool-creation YAML prompts
│   └── templates/prebuilt/         reasoning templates (one per scenario)
│
├── cases/                          entry points
│   ├── run_all.py                  runs all four scenarios (offline | mock | openai)
│   └── dpep1_crc_effector_target.py   the target-discovery case with CLI options
│
├── data/
│   ├── enzyme_round1_prior.csv     the published round-1 scan (6 positions)
│   ├── enzyme_round2_truth.csv     the published round-2 variants (hindcast truth)
│   └── protocols.json              six clean + five corrupted wet-lab protocols
│
├── tests/
│   ├── run_checks.py               8 offline self-checks
│   ├── test_online_mode.py         contract tests against a model endpoint
│   └── mock_llm_server.py          local OpenAI-compatible mock
│
├── tools_created/
│   └── score_signaling_potential.py   the tool the system wrote at runtime (evidence)
│
├── outputs/                        the four canonical runs cited in the report
│   ├── 20261116_002640_target_discovery_DPEP1/
│   ├── 20261116_enzyme_design_P68175/
│   ├── 20261116_retrosynthesis_lidocaine/
│   └── 20261116_002702_sdl_protocol_str_activity_assay/
│
├── paper/                          the deliverables and their build scripts
│   ├── MOCHI_Final_Project_Report_LaTeX.pdf    final report (24 pp., MPU template)
│   ├── MOCHI_Final_Project_Report.docx/.pdf    editable Word version
│   ├── MOCHI_Final_Project_Slides.pptx/.pdf    18-slide presentation
│   ├── latex/                      main.tex, chapters, bibliography, class, figures
│   ├── figures/                    source PNGs used by the report and the slides
│   ├── make_report.py              builds the DOCX from the report text
│   ├── build_deck.py               builds the PPTX presentation
│   ├── docx_to_tex.py, build_latex.py   DOCX → LaTeX project
│   ├── figures_v2.py, figures_slides.py  report panels and slide panels
│   └── audit_numbers.py            cross-checks every table against outputs/
│
├── docs/
│   ├── design.md                   scoring, decision contracts, guardrails
│   ├── tool_manifest.json          machine-readable tool inventory
│   └── UPLOAD.md                   how to publish the repository
│
└── scripts/
    ├── reproduce.ps1 / .sh         one-shot reproduction
    └── upload_to_github.ps1        init + commit + push helper
```
