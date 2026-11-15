"""Report sections for the MOCHI final project."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH

from build_report import bullets, caption, figure, h1, h2, para, table

# ---------------------------------------------------------------------------
# references (body text cites them only by number)
# ---------------------------------------------------------------------------
REFS = [
    "Yao, S. et al. ReAct: Synergizing reasoning and acting in language models. ICLR (2023).",
    "Schick, T. et al. Toolformer: Language models can teach themselves to use tools. NeurIPS (2023).",
    "M. Bran, A. et al. Augmenting large language models with chemistry tools (ChemCrow). Nature Machine "
    "Intelligence 6, 525-535 (2024).",
    "Boiko, D. A., MacKnight, R., Kline, B. & Gomes, G. Autonomous chemical research with large language "
    "models (Coscientist). Nature 624, 570-578 (2023).",
    "Roohani, Y. et al. BioDiscoveryAgent: an AI agent for designing genetic perturbation experiments. "
    "ICLR (2025).",
    "Jin, R. et al. STELLA: towards a biomedical world model with self-evolving multimodal agents. "
    "bioRxiv 2025.07.01.662467 (2025).",
    "Cong, L. et al. LabOS: the AI-XR co-scientist that sees and works with humans. arXiv:2510.14861 (2025).",
    "The UniProt Consortium. UniProt: the universal protein knowledgebase in 2023. Nucleic Acids Res. 51, "
    "D523-D531 (2023).",
    "Ochoa, D. et al. The next-generation Open Targets Platform: reimagined, redesigned, rebuilt. Nucleic "
    "Acids Res. 51, D1353-D1359 (2023).",
    "Cerami, E. et al. The cBioPortal for cancer genomics opens new frontiers. Cancer Discov. 2, 401-404 (2012).",
    "Szklarczyk, D. et al. The STRING database in 2023. Nucleic Acids Res. 51, D638-D646 (2023).",
    "Del Toro, N. et al. The IntAct database: efficient access to fine-grained molecular interaction data. "
    "Nucleic Acids Res. 50, D648-D653 (2022).",
    "Jumper, J. et al. Highly accurate protein structure prediction with AlphaFold. Nature 596, 583-589 (2021).",
    "Vaswani, A. et al. Attention is all you need. NeurIPS (2017).",
    "Henikoff, S. & Henikoff, J. G. Amino acid substitution matrices from protein blocks (BLOSUM62). PNAS 89, "
    "10915-10919 (1992).",
    "Kyte, J. & Doolittle, R. F. A simple method for displaying the hydropathic character of a protein. "
    "J. Mol. Biol. 157, 105-132 (1982).",
    "Rauen, H. et al. (strictosidine synthase engineering) - see also: Chen, R. et al. Enzyme engineering for "
    "alkaloid biosynthesis. Curr. Opin. Biotechnol. (2021).",
    "Segler, M. H. S., Preuss, M. & Waller, M. P. Planning chemical syntheses with deep neural networks and "
    "symbolic AI. Nature 555, 604-610 (2018).",
    "Coley, C. W. et al. A robotic platform for flow synthesis of organic compounds informed by AI planning. "
    "Science 365, eaax1566 (2019).",
    "Landrum, G. RDKit: open-source cheminformatics software. https://www.rdkit.org (2024).",
    "Kim, S. et al. PubChem 2023 update. Nucleic Acids Res. 51, D1373-D1380 (2023).",
    "Cock, P. J. A. et al. Biopython: freely available Python tools for computational molecular biology. "
    "Bioinformatics 25, 1422-1423 (2009).",
]


# ---------------------------------------------------------------------------
# section 1
# ---------------------------------------------------------------------------
def section1(doc) -> None:
    h1(doc, "§1  Introduction and Literature Review")

    h2(doc, "1.1  The data-to-decision bottleneck in AIDD")
    para(doc,
         "Drug discovery has been transformed by data: a modern programme can query a protein's structure, its "
         "expression across thousands of tumours, its interaction partners, its chemical ligands and its "
         "literature within minutes. What has not scaled is the translation of those data into a defensible "
         "decision. A target is worth pursuing only if it is linked to the disease, mechanically plausible, "
         "druggable and still novel; a mutation is worth synthesising only if it is close enough to the active "
         "site to matter yet conservative enough to fold; a route is worth running only if every leaf is "
         "purchasable; a protocol is worth automating only if every volume and temperature is physically "
         "feasible. Each of these judgements requires the same three ingredients - heterogeneous evidence, "
         "explicit domain constraints and a written rationale - and each is currently assembled by hand.")
    para(doc,
         "Large language models (LLMs) are attractive precisely here, because they can plan, call tools and write "
         "the rationale [1,2]. Yet a single model with a bag of tools is a poor fit for regulated scientific "
         "reasoning: it may hallucinate a number, silently skip a control, or change its answer between runs. "
         "The engineering question of this project is therefore not 'can an LLM call a database?' but 'can a "
         "multi-agent system make scientific decisions that are reproducible, auditable and correctable?'")

    h2(doc, "1.2  Agentic systems for biomedical research")
    para(doc,
         "Tool-augmented LLMs were formalised by ReAct, which interleaves reasoning traces with actions [1], and "
         "by Toolformer, which learns when to call APIs [2]. Chemistry-specific systems followed: ChemCrow "
         "combines 18 expert tools under an LLM planner [3], and Coscientist closed the loop from literature to "
         "robotic execution [4]. In biology, BioDiscoveryAgent designs genetic perturbation experiments [5], and "
         "self-evolving frameworks that maintain a growing tool library have recently been proposed for "
         "biomedical research [6,7]. These systems share a design pattern - a planner, a set of tools, an "
         "evaluator - but differ in how much autonomy the model is given.")
    para(doc,
         "Three weaknesses recur across this literature. First, evaluation is usually a single task: a system "
         "tuned for chemistry is not shown to plan a CRISPR screen. Second, the evaluator is itself an LLM, so a "
         "confident but wrong plan can pass review. Third, reproducibility is rarely demonstrated: the tool "
         "outputs behind a claim are usually not preserved. The present work addresses all three by treating the "
         "orchestration layer as a first-class engineering artefact: explicit stage contracts, a deterministic "
         "audit with veto power, and a provenance log for every external call.")

    h2(doc, "1.3  Why four scenarios")
    para(doc,
         "We deliberately chose four tasks that stress different parts of the same orchestration problem "
         "(Table 1). Target discovery is evidence integration under uncertainty; enzyme design is "
         "structure-constrained combinatorial search with experimental feedback; retrosynthesis is graph search "
         "with hard feasibility constraints; protocol compilation is translation from natural language into a "
         "typed, checkable program. If one orchestrator handles all four, it is a platform rather than a demo.")

    table(doc,
          ["Scenario", "Input", "Core computation", "Output", "Failure mode exercised"],
          [["S1 Target discovery", "anchor gene + disease", "6-dimension evidence scoring over public omics",
            "ranked effectors + dossier", "missing capability (no competence scorer)"],
           ["S2 Enzyme design", "enzyme + round-1 data", "structure/prior-guided variant scoring",
            "15-variant library + primers", "experimental knowledge that a model lacks"],
           ["S3 Retrosynthesis", "target SMILES", "template-based best-first AND-OR search",
            "shortest route to stock", "combinatorial explosion / dead ends"],
           ["S4 Protocol → SDL", "natural-language protocol", "typed compilation + static validation",
            "validated SDL program", "silent unit/safety errors"]],
          "Table 1. The four scenarios share one orchestrator and differ only in their stage programs and tools.",
          widths=[3.2, 3.0, 4.4, 3.2, 3.6])

    h2(doc, "1.4  Contributions")
    bullets(doc, [
        "A scenario-agnostic, self-evolving multi-agent architecture (manager, developer, critic, tool creator) "
        "in which the critic's audit is deterministic Python and has veto power over the language model.",
        "A shared Tool Ocean of 46 tools spanning omics databases, structure analysis, cheminformatics and "
        "laboratory automation, with cached, provenance-logged access and a validation gate for generated tools.",
        "Four independently runnable AIDD scenarios, each with a quantitative evaluation that includes a "
        "published ground truth (hindcast), a literature benchmark, or deliberately corrupted inputs.",
        "A reproducibility contract: an offline deterministic engine, an OpenAI-compatible engine, and a "
        "single command that regenerates every number in this report from cached public data.",
    ])



# ---------------------------------------------------------------------------
# section 2
# ---------------------------------------------------------------------------
def section2(doc) -> None:
    h1(doc, "§2  Research Questions and Objectives")

    para(doc,
         "The project is organised around three research questions that are answerable with the artefacts of a "
         "single run, rather than around a single predictive benchmark.")
    bullets(doc, [
        "RQ1 (generality). Can one orchestration layer drive four structurally different AIDD tasks - evidence "
        "integration, combinatorial design, graph search and program compilation - without task-specific agent "
        "code?",
        "RQ2 (self-evolution). Does the ability to create a tool at runtime add capability that a static tool "
        "library cannot provide, and is the created tool trustworthy?",
        "RQ3 (reliability). Does a deterministic critic audit combined with an explicit experimental prior "
        "improve the reliability of decisions compared with an unaudited, prior-free pipeline?",
    ])

    h2(doc, "2.1  Objectives and success criteria")
    table(doc,
          ["Objective", "Deliverable", "Success criterion", "Where reported"],
          [["O1  Build the orchestrator", "4 agents + stage registry + templates", "one code path runs all four "
            "scenarios", "§3, §4"],
           ["O2  Curate the tool ocean", "46 tools, cached, provenance-logged", "every claim traceable to a call",
            "§3.3, §7"],
           ["O3  Reproduce published science", "hindcasts against two published results",
            "recover the published answer or explain the miss", "§4.1, §4.2"],
           ["O4  Validate feasibility outputs", "route + SDL benchmarks", "solved routes terminate in stock; "
            "corrupted protocols are caught", "§4.3, §4.4"],
           ["O5  Demonstrate self-evolution", "runtime tool creation", "created tool passes 13/13 controls",
            "§4.1, §4.5"]],
          "Table 2. Objectives are tied to a deliverable, a measurable success criterion and a results section.",
          widths=[3.4, 4.2, 5.2, 2.6])

    para(doc,
         "The motivation for O3 deserves emphasis. A target-discovery system that is only judged on whether it "
         "produces 'a plausible list' is unfalsifiable. We therefore use published answers as a hindcast: the "
         "system is given exactly the information a researcher would have had before the answer was known, and "
         "we report whether, and at what rank, it recovers the known result.")


# ---------------------------------------------------------------------------
# section 3
# ---------------------------------------------------------------------------
def section3(doc) -> None:
    h1(doc, "§3  Methods and Materials")

    h2(doc, "3.1  Architecture")
    para(doc,
         "MOCHI separates the control plane from the data plane (Figure 1). The control plane decides what to do "
         "next; the data plane performs every computation that appears in the report. The manager is the only "
         "agent that sees the user's instruction; it retrieves a reasoning template by TF-IDF similarity, "
         "decomposes the task into four stages and delegates execution. The developer executes a stage program "
         "and may only change parameters from a whitelist. The critic runs a scenario-specific, deterministic "
         "audit and then asks the language model for a verdict; the stricter of the two wins, so the model "
         "cannot waive a failed control. When the audit reports a missing capability, the tool-creation agent "
         "researches, writes, tests and registers a new tool, and the affected stage is re-run.")
    figure(doc, "fig_workflow_ref.png", 16.0,
           "Figure 1. The target-discovery workflow. The manager decomposes the DPEP1 task into profile "
           "construction, candidate generation, multi-evidence scoring and summarisation; the developer runs the "
           "stage programs and writes the artefacts; the critic audits each stage and asks for a new tool when a "
           "capability is missing; the tool-creation agent searches, builds and tests that tool before the stage "
           "is re-run. The final panel shows the hypothesis that the wet lab then tested; the quantitative "
           "evidence behind each step is reported in Section 4.")

    h2(doc, "3.2  Agents and their contracts")
    para(doc,
         "Every agent call is a JSON contract, and the orchestrator parses only JSON. This is what allows the "
         "same agent classes to run against a real model, a local mock, or a rule-based engine: the contract, "
         "not the prose, carries the information.")
    table(doc,
          ["Call", "Producer → consumer", "Required fields"],
          [["manager.plan", "manager → orchestrator", "stages[4] (name, goal, tools, criteria), hypotheses, "
            "reasoning"],
           ["dev.plan", "developer → stage program", "steps, tools, parameter overrides (whitelisted)"],
           ["critic.review", "critic → manager", "verdict (accept/revise/evolve), gaps, tool_requests, weights"],
           ["tool_creation.design", "tool creator → tool creator", "tool name, algorithm, validation plan"],
           ["manager.weights", "manager → orchestrator", "six weights summing to one"],
           ["manager.synthesize", "manager → report", "narrative paragraph"]],
          "Table 3. Agent contracts. The audit (Python) is evaluated separately from the verdict (model) and can "
          "override it.",
          widths=[3.6, 5.4, 6.4])

    h2(doc, "3.3  Tool Ocean")
    para(doc,
         "The Tool Ocean contains 46 deterministic tools in eleven categories (Table 4). Every tool returns a "
         "structured dictionary with an ok flag and a source string, never raises, and routes network access "
         "through one HTTP layer that caches responses for a week, retries with back-off, and appends the URL, "
         "parameters, status, latency and payload hash to provenance.jsonl. This single design decision is what "
         "makes the 'every number is traceable' claim in this report true.")
    table(doc,
          ["Category", "n", "Representative tools"],
          [["database", "12", "query_uniprot, query_opentargets_associations, query_cbioportal_survival, "
            "query_pubmed, query_kegg_pathways, resolve_gene_ids"],
           ["chemistry", "6", "molecule_properties, drugability_score, query_chembl_target, query_dgidb"],
           ["literature", "5", "query_pubmed_cooccurrence, query_pubmed_novelty, citation_network_score"],
           ["pathway / annotation", "8", "pathway_coannotation, query_quickgo, query_interpro, "
            "pathway_enrichment"],
           ["network", "3", "query_string, query_intact, build_ppi_union"],
           ["structure / sequence", "5", "fetch_alphafold_model, pocket_geometry, conserve_profile, primers, CDS mapping"],
           ["retrosynthesis", "2", "one_step_disconnections, search_route, route_metrics"],
           ["laboratory automation", "4", "parse_protocol, compile_sdl, validate_sdl, simulate_sdl"],
           ["scoring", "1", "multi_evidence_scoring (plus the runtime-created competence scorer)"]],
          "Table 4. Tool Ocean by category. Counts exclude the runtime-created signalling-competence scorer.",
          widths=[3.2, 0.8, 12.2], font_size=8.4)

    figure(doc, "fig_sankey.png", 16.0,
           "Figure 2. How the 46 tools of the Tool Ocean are distributed over five capability domains and the "
           "eleven categories. Ribbon width is proportional to the number of tools and the colour identifies "
           "the domain; the individual tools behind each category are listed in Table 4.")

    h2(doc, "3.4  Scenario adapters")
    para(doc,
         "A scenario supplies four stage programs, an optional audit and an optional report renderer; nothing "
         "else changes. This is the entire mechanism by which MOCHI becomes a platform rather than a single-task "
         "agent. Table 5 summarises the stages.")
    table(doc,
          ["Stage", "S1 target discovery", "S2 enzyme design", "S3 retrosynthesis", "S4 protocol → SDL"],
          [["Stage 1", "anchor profile: topology, expression, disease links",
            "sequence, catalytic residues, AlphaFold model, homologs",
            "target descriptors and functional-group inventory",
            "sentence segmentation and typed step extraction"],
           ["Stage 2", "candidate pool from PPI, co-expression, pathways, literature",
            "all single substitutions within 12 A of the catalytic cluster",
            "one-step disconnections from a curated template set",
            "lowering to typed opcodes with SI units and devices"],
           ["Stage 3", "signalling-competence scoring (created tool)",
            "structure + chemistry + prior scoring",
            "best-first AND-OR search to purchasable stock",
            "static validation and bounded repair"],
           ["Stage 4", "six-dimension ranking and evidence dossier",
            "budgeted library, primers, hindcast",
            "route ranking and literature benchmark",
            "digital-twin simulation and corrupted-protocol benchmark"]],
          "Table 5. The four scenarios share the same four-stage skeleton.",
          widths=[1.8, 4.0, 4.0, 3.6, 3.6], font_size=8.0, align_first_left=True)

    h2(doc, "3.5  Decision models")
    para(doc,
         "No stage delegates a computation to the language model. The models below are the actual decision "
         "rules; they were designed before the validation data were consulted and were not tuned on it.")
    para(doc,
         "Target discovery. Each candidate receives six dimension scores in [0,1] - association with the anchor, "
         "signalling competence, disease evidence, pathway centrality, novelty and druggability - and a weighted "
         "mean is taken over the dimensions that exist, multiplied by a coverage factor. Association combines "
         "physical interaction, expression co-variation, literature co-mention and specific pathway sharing with "
         "a noisy-OR, so that one strong channel is sufficient and absent channels do not dilute a real signal. "
         "Novelty is a saturating function of the number of PubMed records for the gene in the disease and "
         "overall, so a gene with no disease literature but 800 general papers is not counted as unexplored.")
    para(doc,
         "Enzyme design. A variant at position p with substitution wt→mut receives "
         "score = leverage(d) × [0.55·chemistry + 0.45·prior] × (0.7 + 0.3·packing) − 0.15·conservation, where "
         "leverage = exp(−d/12) with d the minimum heavy-atom distance to the catalytic cluster, chemistry is a "
         "rescaled BLOSUM62 [15], prior is the round-1 outcome for that position (hit 1.0 / reduced 0.5 / "
         "untested 0.5 / dead 0), packing penalises volume change and buried-glycine substitutions, and the "
         "conservation penalty comes from a Needleman-Wunsch alignment against 39 UniProt homologs.")
    para(doc,
         "Retrosynthesis. Six disconnection templates (amide, ester, aryl ether, N-alkylation, sulfonamide, "
         "nitro-to-amine interconversion) are applied by direct bond editing; the resulting fragments are "
         "sanitised, and a depth-limited best-first search terminates when every leaf is in a curated stock of "
         "commercially available building blocks [18,20].")
    para(doc,
         "Protocol compilation. A rule-based parser maps sentences to verbs and parameters, the compiler emits "
         "ten opcodes with SI units and device assignments, the validator checks vessel capacity, device "
         "temperature limits, unit completeness, ordering and flammable-solvent hazards, and the simulator "
         "produces a timeline on a digital twin of the platform.")

    h2(doc, "3.6  Audit, veto and self-evolution")
    para(doc,
         "Each scenario defines a small set of hard checks (for example: was a sequence retrieved, is a route "
         "terminating in stock, is every parsed step mapped to an opcode, are all corrupted protocols caught). "
         "A failed hard check raises the verdict to at least 'revise'; a missing capability raises it to "
         "'evolve'. The model is then asked for its own verdict and the two are reconciled by taking the "
         "stricter. On 'evolve', the manager issues a tool request containing the name, purpose, inputs, "
         "algorithm and - importantly - the positive and negative controls that the new tool must satisfy. The "
         "tool-creation agent researches the request (PubMed and GitHub), writes a single Python file, runs the "
         "controls, and is allowed at most three repair iterations. Only a tool that passes its controls is "
         "registered.")

    h2(doc, "3.7  Data, engines and reproducibility")
    para(doc,
         "All external data are public: UniProt [8], Open Targets [9], cBioPortal/TCGA [10], STRING [11], "
         "IntAct [12], AlphaFold DB [13], PubMed, KEGG, Reactome, QuickGO, InterPro, ChEMBL and DGIdb. The "
         "system has two interchangeable engines behind one interface: an OpenAI-compatible client (all "
         "experiments reported here use deepseek-V4.1-pro through a local compatible endpoint) and a "
         "deterministic reference engine that reproduces the same JSON contracts without a key. Because every "
         "computation lives in the stage programs, the choice of engine changes the wording of the rationale but "
         "not a single number in the results.")
    para(doc,
         "Reproducibility is enforced at three levels: HTTP responses are cached and hashed; each run writes "
         "task.txt, transcript.jsonl, llm_calls.jsonl (including the exact user message sent to the model), "
         "provenance.jsonl and run_summary.json; and all four scenarios can be re-executed with one command. "
         "The implementation is 41 Python modules (~9.6k lines) with three runtime dependencies (requests, "
         "PyYAML, matplotlib) and no GPU requirement.")

    h2(doc, "3.8  Evaluation protocol")
    bullets(doc, [
        "S1 (hindcast): run the pipeline on DPEP1 in colorectal cancer and check whether the published effector "
        "LRP6 is nominated and at what rank, with and without a prior seed.",
        "S2 (hindcast): run on strictosidine synthase with round-1 data only, then compare the designed library "
        "with the five published round-2 variants at variant and position level, and check exclusion of the "
        "three experimentally dead positions.",
        "S3 (benchmark): plan routes for eight drugs with literature syntheses; report solved fraction, planned "
        "versus literature step count and failures.",
        "S4 (benchmark): compile six clean protocols and five deliberately corrupted variants; report validity "
        "of clean inputs and detection of the injected faults.",
        "Ablations: (a) disable runtime tool creation for S1; (b) disable the experimental prior for S2.",
    ])
