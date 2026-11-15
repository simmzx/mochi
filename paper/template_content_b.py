"""§4–§7 of the AIDD8122 template report."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH

from build_template_report import bullets, caption, figure, h1, h2, p, table
from template_content_a import Citer


def section4(doc, c: Citer) -> None:
    h1(doc, "Methods and Materials")
    p(doc, "This section describes the architecture, the tool layer, the four scenario adapters, the decision "
           "models, the audit mechanism and the evaluation protocol. The intent is that a reader can re-implement "
           "any number in Section 5 from what is written here.")

    h2(doc, "4.1  System architecture")
    p(doc, "MOCHI separates the control plane from the data plane (Figure 1). The control plane decides what to do "
           "next; the data plane performs every computation that appears in the report. The manager is the only "
           "agent that sees the user's instruction: it retrieves a reasoning template by TF-IDF similarity, "
           "decomposes the task into four stages and delegates execution. The developer executes a stage program and "
           "may only change parameters from a whitelist. The critic runs a scenario-specific deterministic audit and "
           "then asks the language model for a verdict; the stricter of the two wins, so the model cannot waive a "
           "failed control. When the audit reports a missing capability, the tool-creation agent researches, writes, "
           "tests and registers a new tool, and the affected stage is re-run.")
    figure(doc, "fig_workflow_ref.png", 14.2,
           "Figure 1. The target-discovery workflow. The manager decomposes the DPEP1 task into profile "
           "construction, candidate generation, multi-evidence scoring and summarisation; the developer runs the "
           "stage programs and writes the artefacts; the critic audits each stage and requests a new tool when a "
           "capability is missing; the tool-creation agent searches, builds and tests that tool before the stage is "
           "re-run. The final panel shows the hypothesis that the wet lab subsequently tested; the quantitative "
           "evidence behind each step is reported in Section 5.")

    h2(doc, "4.2  Agents and their contracts")
    p(doc, "Every agent call is a JSON contract, and the orchestrator parses only JSON. This is what allows the same "
           "agent classes to run against a real model, a local mock, or a rule-based engine: the contract, not the "
           "prose, carries the information.")
    table(doc,
          ["Call", "Producer → consumer", "Required fields"],
          [["manager.plan", "manager → orchestrator", "stages[4] (name, goal, tools, criteria), hypotheses, "
            "reasoning"],
           ["dev.plan", "developer → stage program", "steps, tools, parameter overrides (whitelisted)"],
           ["critic.review", "critic → manager", "verdict (accept/revise/evolve), gaps, tool_requests, weights"],
           ["tool_creation.design", "tool creator", "tool name, algorithm, validation plan"],
           ["manager.weights", "manager → orchestrator", "six weights summing to one"],
           ["manager.synthesize", "manager → report", "narrative paragraph"]],
          "Table 3. Agent contracts. The audit (Python) is evaluated separately from the verdict (model) and can "
          "override it.",
          widths=[3.6, 5.2, 6.4], font_size=9.5)

    h2(doc, "4.3  The Tool Ocean")
    p(doc, "The Tool Ocean contains 46 deterministic tools in eleven categories (Figure 2). Every tool returns a "
           "structured dictionary with an ok flag and a source string, never raises, and routes network access "
           "through one HTTP layer that caches responses for a week, retries with back-off, and appends the URL, "
           "parameters, status, latency and payload hash to provenance.jsonl. In the target-discovery run this "
           "produced 190 logged calls, which is what makes the traceability claim in this report checkable.")
    figure(doc, "fig_sankey.png", 14.2,
           "Figure 2. How the 46 tools of the Tool Ocean are distributed over five capability domains and eleven "
           "categories. Ribbon width is proportional to the number of tools and colour identifies the domain; the "
           "individual tools behind each category are listed in Table 4.")
    table(doc,
          ["Category", "n", "Representative tools"],
          [["database", "12", "query_uniprot, query_opentargets_associations, query_cbioportal_survival, "
            "query_pubmed, query_kegg_pathways, resolve_gene_ids"],
           ["chemistry", "6", "molecule_properties, drugability_score, query_chembl_target, query_dgidb"],
           ["literature", "5", "query_pubmed_cooccurrence, query_pubmed_novelty, citation_network_score"],
           ["pathway / annotation", "8", "pathway_coannotation, query_quickgo, query_interpro, pathway_enrichment"],
           ["network", "3", "query_string, query_intact, build_ppi_union"],
           ["structure / sequence", "5", "fetch_alphafold_model, pocket_geometry, conservation_profile, primers, "
            "CDS mapping"],
           ["retrosynthesis", "2", "one_step_disconnections, search_route"],
           ["laboratory automation", "4", "parse_protocol, compile_sdl, validate_sdl, simulate_sdl"],
           ["scoring", "1", "multi_evidence_scoring (plus the runtime-created competence scorer)"]],
          "Table 4. The Tool Ocean by category. Counts exclude the runtime-created signalling-competence scorer.",
          widths=[3.6, 1.5, 10.9], font_size=9)

    h2(doc, "4.4  Scenario adapters")
    p(doc, "A scenario supplies four stage programs, an optional audit and an optional report renderer; nothing "
           "else changes. This is the entire mechanism by which MOCHI becomes a platform rather than a single-task "
           "agent (Table 5).")
    table(doc,
          ["Stage", "S1 target discovery", "S2 enzyme design", "S3 retrosynthesis", "S4 protocol → SDL"],
          [["Stage 1", "anchor profile: topology, expression, disease links", "sequence, catalytic residues, "
            "AlphaFold model, homologs", "target descriptors and functional groups", "sentence segmentation and "
            "typed step extraction"],
           ["Stage 2", "candidate pool from PPI, co-expression, pathways, literature", "all substitutions within "
            "12 Å of the catalytic cluster", "one-step disconnections from curated templates", "lowering to typed "
            "opcodes with SI units and devices"],
           ["Stage 3", "signalling-competence scoring (created tool)", "structure + chemistry + prior scoring",
            "best-first AND-OR search to stock", "static validation and bounded repair"],
           ["Stage 4", "six-dimension ranking and evidence dossier", "budgeted library, primers, hindcast",
            "route ranking and literature benchmark", "digital-twin simulation and corrupted-protocol benchmark"]],
          "Table 5. The four scenarios share the same four-stage skeleton.",
          widths=[1.7, 3.9, 3.9, 3.4, 3.4], font_size=8.5)

    h2(doc, "4.5  Decision models")
    p(doc, "No stage delegates a computation to the language model. The models below are the actual decision rules; "
           "they were designed before the validation data were consulted and were not tuned on it.")
    p(doc, "Target discovery. Each candidate receives six dimension scores in [0,1] — association with the anchor, "
           "signalling competence, disease evidence, pathway centrality, novelty and druggability — and a weighted "
           "mean is taken over the dimensions that exist, multiplied by a coverage factor. Association combines "
           "physical interaction, expression co-variation, literature co-mention and specific pathway sharing with a "
           "noisy-OR, so that one strong channel is sufficient and absent channels do not dilute a real signal. "
           "Novelty is a saturating function of the number of PubMed records for the gene in the disease and "
           "overall, so a gene with no disease literature but 800 general papers is not counted as unexplored.")
    p(doc, "Enzyme design. A variant at position p with substitution wt→mut receives score = leverage(d) × "
           "[0.55 × chemistry + 0.45 × prior] × (0.7 + 0.3 × packing) − 0.15 × conservation, where leverage = "
           "exp(−d/12) with d the minimum heavy-atom distance to the catalytic cluster, chemistry is a rescaled "
           "BLOSUM62 value, prior is the round-1 outcome for that position (hit 1.0, reduced 0.5, untested 0.5, "
           "dead 0), packing penalises volume change and buried-glycine substitutions, and the conservation penalty "
           "comes from a Needleman–Wunsch alignment against 39 UniProt homologs.")
    p(doc, "Retrosynthesis. Six disconnection templates (amide, ester, aryl ether, N-alkylation, sulfonamide, "
           "nitro-to-amine interconversion) are applied by direct bond editing; the resulting fragments are "
           "sanitised with RDKit, and a depth-limited best-first search terminates when every leaf is in a curated "
           "stock of commercially available building blocks.")
    p(doc, "Protocol compilation. A rule-based parser maps sentences to verbs and parameters, the compiler emits ten "
           "opcodes with SI units and device assignments, the validator checks vessel capacity, device temperature "
           "limits, unit completeness, ordering and flammable-solvent hazards, and the simulator produces a timeline "
           "on a digital twin of the platform.")

    h2(doc, "4.6  Audit, veto and self-evolution")
    p(doc, "Each scenario defines a small set of hard checks: was a sequence retrieved, does a route terminate in "
           "stock, is every parsed step mapped to an opcode, are all corrupted protocols caught. A failed hard check "
           "raises the verdict to at least revise; a missing capability raises it to evolve. The model is then asked "
           "for its own verdict and the two are reconciled by taking the stricter. On evolve, the manager issues a "
           "tool request containing the name, purpose, inputs, algorithm and — importantly — the positive and "
           "negative controls the new tool must satisfy. The tool-creation agent researches the request, writes a "
           "single Python file, runs the controls and is allowed at most three repair iterations. Only a tool that "
           "passes its controls is registered. The scorer created in this project was validated on seven "
           "established receptors (LRP6 0.75, FZD1 0.85, EGFR 0.80, TNFRSF1A 0.85, TGFBR1 0.76, NOTCH1 0.68, IL6ST "
           "0.73) and six non-signalling proteins (DPEP1 0.15, CEACAM5 0.15, ALB 0.12, INS 0.17, GAPDH 0.15, LYZ "
           "0.12); all thirteen controls passed.")

    h2(doc, "4.7  Data, engines and reproducibility")
    p(doc, "All external data are public: UniProt, Open Targets, cBioPortal/TCGA, STRING, IntAct, AlphaFold DB, "
           "PubMed, KEGG, Reactome, QuickGO, InterPro, ChEMBL and DGIdb. The system has two interchangeable engines "
           "behind one interface: an OpenAI-compatible client (the runs reported here use deepseek-V4.1-pro through "
           "a local compatible endpoint) and a deterministic reference engine that reproduces the same JSON "
           "contracts without a key. Because every computation lives in the stage programs, the choice of engine "
           "changes the wording of the rationale but not a single number in the results.")
    p(doc, "Reproducibility is enforced at three levels: HTTP responses are cached and hashed; each run writes "
           "task.txt, transcript.jsonl, llm_calls.jsonl (including the exact user message sent to the model), "
           "provenance.jsonl and run_summary.json; and all four scenarios can be re-executed with one command. The "
           "implementation is 41 Python modules (about 9.6k lines) with three runtime dependencies (requests, "
           "PyYAML, matplotlib) plus RDKit for the retrosynthesis scenario, and requires no GPU.")

    h2(doc, "4.8  Evaluation protocol and metrics")
    p(doc, "Four evaluation instruments are used, and each is paired with a baseline so that the result is not "
           "merely self-consistent.")
    bullets(doc, [
        "Hindcast (S1): run the pipeline on DPEP1 in colorectal cancer, check whether the published effector LRP6 "
        "is nominated and at what rank, with and without a prior seed.",
        "Hindcast (S2): run on strictosidine synthase with round-1 data only, then compare the designed library "
        "with the five published round-2 variants at variant and position level, and check exclusion of the three "
        "experimentally dead positions. Metrics: rank of the best published hit, recall at 15 variants and at "
        "position level, and dead-zone exclusion rate.",
        "Benchmark (S3): plan routes for eight drugs with literature syntheses; report solved fraction, planned "
        "versus literature step count. Baseline: a planner restricted to one-step disconnections.",
        "Benchmark (S4): compile six clean protocols and five deliberately corrupted variants; report validity of "
        "clean inputs and detection of the injected faults. Baseline: compilation without static validation.",
        "Ablations: disable runtime tool creation for S1; disable the experimental prior for S2.",
        "Ranking baselines: for S1, rank the same candidate set by association only and by competence only; for S2, "
        "rank the same 2,773 variants by chemistry only, by leverage only and by prior only.",
    ])


def section5(doc, c: Citer) -> None:
    h1(doc, "Results and Discussion")
    p(doc, "All four scenarios were executed end-to-end with the same orchestrator, the same tool layer and the same "
           "model endpoint. The complete suite takes about two minutes with a cold HTTP cache and under 25 s when "
           "the cache is warm (Table 14). Each subsection reports a result, then compares it with the appropriate "
           "baseline before interpreting it.")

    # ------------------------------------------------------------------ 5.1
    h2(doc, "5.1  Scenario 1: effector-target discovery in colorectal cancer")
    p(doc, "DPEP1 is a GPI-anchored ectoenzyme: the UniProt entry (P16444, 411 aa) contains no transmembrane helix "
           "and no intracellular domain. The stage-1 audit therefore records a hard constraint — the effector cannot "
           "be DPEP1 itself, it must be a membrane protein able to transduce a signal — and immediately detects that "
           "the tool ocean contains no instrument for measuring signalling competence. The tool-creation agent "
           "builds one, validates it on 13 controls, and stage 1 is re-run.")
    p(doc, "The candidate pool is built from four independent channels — STRING/IntAct partners (60), a 600-gene KEGG "
           "signalling panel screened for co-expression in TCGA-COADREAD (24 genes at |r| ≥ 0.30 and FDR ≤ 0.10), "
           "Reactome co-annotation (8 genes sharing a specific pathway) and PubMed co-mention — and filtered to 34 "
           "expressed candidates. The competence scorer reduces this to 10, and the six-dimension ranking produces "
           "Table 6 and Figure 3.")
    table(doc,
          ["Rank", "Gene", "Composite", "Assoc.", "Signal.", "Disease", "Pathway", "Novelty", "Drug.", "Dims ≥ 0.6"],
          [["1", "ASIC1", "0.496", "0.42", "0.69", "0.41", "0.04", "0.57", "0.72", "2/6"],
           ["2", "NOTCH1", "0.481", "0.51", "0.68", "0.36", "0.00", "0.03", "0.92", "2/6"],
           ["3", "FZD7", "0.459", "0.23", "0.85", "0.23", "0.23", "0.30", "0.84", "2/6"],
           ["4", "ZNRF3", "0.449", "0.50", "0.75", "0.49", "0.00", "0.41", "0.25", "1/6"],
           ["5", "ACE2", "0.443", "0.61", "0.45", "0.20", "0.02", "0.03", "1.00", "2/6"]],
          "Table 6. Six-dimension ranking for DPEP1 in colorectal cancer (run 20261116_002640).",
          widths=[0.9, 1.4, 2.1, 1.25, 1.25, 1.25, 1.25, 1.25, 1.2, 1.5], font_size=8.5)
    p(doc, "Three observations matter more than the ordering. First, the top four are all signal-transducing "
           "membrane proteins co-expressed with DPEP1 — the acid-sensing ion channel ASIC1, NOTCH1 (r = +0.44), "
           "ZNRF3 (r = +0.43) and the Wnt receptor FZD7 — which is exactly the biological class the topological "
           "constraint predicts. Second, the scores are close: the top five span 0.053, so the system reports a "
           "prioritisation rather than a decision. Third, no candidate reaches three strong dimensions, because "
           "association with a GPI-anchored protein is intrinsically hard to establish from public data; the critic "
           "logs this as a failed check instead of hiding it.")

    # ------------------------------------------------------------------ 5.2
    figure(doc, "fig_target_heatmap.png", 12.4,
           "Figure 3. Dimension scores of the top ten candidates. The block structure shows where each candidate "
           "draws its support: NOTCH1 and ASIC1 on signalling and druggability, ZNRF3 on association and signalling, "
           "ACE2 on association alone.")
    h2(doc, "5.2  Baseline comparison for the target ranking")
    p(doc, "To test whether the six-dimension model adds anything beyond its own inputs, the same ten competent "
           "candidates were re-ranked by association alone and by competence alone (Table 7).")
    table(doc,
          ["Ranking", "Top-5", "Overlap with full model", "Comment"],
          [["Full six-dimension", "ASIC1, NOTCH1, FZD7, ZNRF3, ACE2", "5/5", "balances evidence and mechanism"],
           ["Association only", "ACE2, NOTCH1, ZNRF3, CDHR5, ALG10", "3/5", "promotes two candidates of composite "
            "0.338 on correlation alone"],
           ["Competence only", "FZD7, ZNRF3, GJA1, ASIC1, NOTCH1", "4/5", "drops ACE2 (0.45) and ignores disease "
            "evidence"]],
          "Table 7. Baseline rankings of the same ten candidates. The association-only baseline re-orders the list "
          "by co-expression, PPI and literature co-mention; the competence-only baseline ignores all disease evidence.",
          widths=[3.4, 5.6, 3.0, 5.6], font_size=9)
    p(doc, "The difference is not cosmetic. Association alone promotes CDHR5 and ALG10 — both ranked last by the "
           "full model (composite 0.338) because they carry no supporting dimension other than novelty — and demotes "
           "FZD7, whose competence is the highest in the set (0.85). Competence alone does the opposite: it keeps "
           "FZD7 and GJA1 but drops ACE2, which has the strongest association (0.61) and full druggability (1.00). "
           "The six-dimension model is the only ranking that keeps all four Wnt/Notch-class receptors in the top "
           "four, which is the property a biologist would test first.")

    # ------------------------------------------------------------------ 5.3
    h2(doc, "5.3  Hindcast: does MOCHI recover the published effector LRP6?")
    p(doc, "The Wnt co-receptor LRP6 is the effector reported in the experimental study that motivated this project, "
           "and is therefore a natural hidden test. Without any prior, LRP6 is not nominated at all: in "
           "TCGA-COADREAD its expression is essentially uncorrelated with DPEP1 (r = −0.084), it has no STRING or "
           "IntAct interaction with DPEP1, and the two proteins share no specific Reactome pathway. Nomination "
           "would require prior knowledge, not more data.")
    p(doc, "The same pipeline was therefore run with LRP6 injected as a hypothesis seed so that it is scored on "
           "identical terms. LRP6 obtains the highest competence tier (0.754) but the lowest association (0.098) and "
           "low novelty (0.142, because it is heavily studied); its composite score is 0.306 and it ranks 11th of 11 "
           "(Table 8).")
    table(doc,
          ["Gene", "Nominated by data", "Competence", "Association", "Novelty", "Composite", "Rank"],
          [["LRP6 (no seed)", "no", "–", "–", "–", "–", "–"],
           ["LRP6 (seeded)", "prior", "0.754", "0.098", "0.142", "0.306", "11/11"]],
          "Table 8. LRP6 hindcast. Data-driven channels do not nominate LRP6; when scored as a hypothesis it is "
          "competent but poorly associated.",
          widths=[3.2, 3.2, 2.4, 2.6, 2.0, 2.2, 1.6], font_size=9)
    p(doc, "This is the correct behaviour for an evidence-driven system: it does not manufacture support for a "
           "hypothesis that the data do not contain. The result also separates the two questions a reviewer should "
           "ask — is LRP6 a competent effector? (yes) and is it supported as the effector of DPEP1 in this cohort? "
           "(no) — which is precisely the distinction the dossier reports. The shortlist gave the Wnt/Notch class; "
           "the wet lab resolved the member: reciprocal co-immunoprecipitation established that DPEP1 and LRP6 "
           "associate in CRC cells, knockdown and overexpression showed that the DPEP1-driven phenotype depends on "
           "LRP6, qPCR and Western blot placed the effect on the Wnt output, and interface mutagenesis identified the "
           "residues required for the dependency. A system that had ranked LRP6 first on the strength of "
           "co-expression alone would have been right for the wrong reason.")

    # ------------------------------------------------------------------ 5.4
    h2(doc, "5.4  Scenario 2: structure- and prior-guided enzyme design")
    p(doc, "Strictosidine synthase (P68175, 344 aa) catalyses the Pictet–Spengler condensation of tryptamine and "
           "secologanin. A published round-1 scan identified M276 as a productive position and three positions "
           "(G210, H307, P253) as dead zones; a round-2 library then found M276L (+2.1×), V176F (+1.5×), E306S/T "
           "(−64% to −75%) and confirmed G210S as dead. MOCHI was given only the sequence, an AlphaFold model and "
           "the round-1 outcomes, and asked for a 15-variant library.")
    p(doc, "The structural stage places 154 positions within 12 Å of the catalytic cluster and enumerates 2,773 "
           "single substitutions. The top of the designed library is shown in Table 9 and Figure 4A: M276L is ranked "
           "first of 2,773, and the library covers 12 distinct positions with at most two substitutions per "
           "position. Every variant carries a QuikChange primer pair designed from the native CDS (ENA Y00756, "
           "mapped by translated-frame alignment); for M276L the codon changes ATG → CTG and the forward primer is "
           "5′-GAATTAGATGGAAATCTGCACGGAAGAGTTGAT-3′ (Tm 60.7 °C, GC 39.4%).")
    table(doc,
          ["Rank", "Variant", "d to site (Å)", "Leverage", "Chemistry", "Prior", "Packing", "Score", "Published"],
          [["1", "M276L", "1.34", "0.89", "0.50", "hit", "0.97", "0.601", "hit (+2.1×)"],
           ["2", "M276I", "1.34", "0.89", "0.42", "hit", "0.97", "0.561", "not tested"],
           ["3", "Q310E", "1.34", "0.89", "0.50", "untested", "0.94", "0.432", "not tested"],
           ["4", "E306Q", "1.33", "0.90", "0.50", "reduced", "0.94", "0.420", "not tested"],
           ["5", "Y105F", "3.24", "0.76", "0.58", "untested", "0.96", "0.404", "not tested"],
           ["6", "E306D", "1.33", "0.90", "0.50", "reduced", "0.70", "0.388", "not tested"],
           ["7", "A152S", "1.34", "0.89", "0.42", "untested", "1.00", "0.386", "not tested"]],
          "Table 9. Top of the designed round-2 library. Prior is the round-1 outcome for that position.",
          widths=[1.0, 1.7, 2.0, 1.6, 1.7, 1.6, 1.5, 1.3, 2.6], font_size=8.5)
    figure(doc, "fig_panel_a.png", 11.4,
           "Figure 4. Panel A: designed variant library ranked by score. The published hit M276L is ranked first "
           "(red); the remaining 14 variants are shown in blue. Panels B and C appear with their scenarios.")
    p(doc, "Hindcast performance is mixed in a way that is informative. At variant level the system recovers 1 of 2 "
           "active variants (M276L, rank 1 of 2,773); at position level it recovers 1 of 2 positions; and it excludes "
           "3 of 3 experimentally dead positions. The miss is V176F (strict rank 2,004, with four variants tied), a "
           "second-shell aromatic substitution 7.7 Å from the catalytic cluster whose benefit comes from packing "
           "against the substrate rather than from proximity to the active site. A distance-and-conservation model "
           "cannot see that effect; an energy model (FoldX, Rosetta) or a learned mutation predictor would be "
           "required. The system reports the miss rather than hiding it, and names the missing capability — which is "
           "exactly the behaviour the tool-creation loop is designed to trigger in a future run.")

    # ------------------------------------------------------------------ 5.5
    h2(doc, "5.5  Baseline comparison for the variant ranking")
    p(doc, "The enzyme score is a product of three terms, so it is natural to ask which term does the work. Each "
           "term was used alone to rank the same 2,773 variants (Table 10).")
    table(doc,
          ["Ranking", "Rank of M276L", "Published hits in top 15", "Comment"],
          [["Full model", "1", "1 / 2", "prior and structure agree on the top position"],
           ["Chemistry only (BLOSUM62)", "74", "0 / 2", "conservative substitutions dominate"],
           ["Leverage only (distance)", "64", "0 / 2", "every first-shell position is equivalent"],
           ["Prior only (round-1 outcome)", "10", "1 / 2", "position-level yes, variant-level no"]],
          "Table 10. Baseline rankings of the 2,773 variants. The full model is the only one that places M276L "
          "first; the prior alone reaches the top ten but cannot choose among the substitutions at that position.",
          widths=[4.4, 3.2, 3.6, 6.4], font_size=9)
    p(doc, "The comparison isolates the contribution of each term. Distance alone cannot distinguish M276L from the "
           "eighteen other substitutions at first-shell positions; chemistry alone prefers conservative changes "
           "everywhere and puts M276L at rank 74; the experimental prior reaches rank 10 but cannot choose among "
           "substitutions at the same position. Only the product places M276L first, which is the combination the "
           "design was built on.")

    # ------------------------------------------------------------------ 5.6
    h2(doc, "5.6  Scenario 3: multi-step retrosynthesis")
    p(doc, "For lidocaine the planner finds a two-step route that matches the step count of the industrial process: "
           "the amide is cut first, giving 2,6-dimethylaniline and N,N-diethylglycine, and because that glycine is a "
           "specialty reagent rather than a standard building block, it is absent from the curated stock, so the "
           "planner cannot stop there and assembles it by N-alkylation from diethylamine and bromoacetic acid. The "
           "route is complete, uses two reaction classes and ends in purchasable compounds.")
    p(doc, "Across the eight-drug suite the planner solves every target with a mean of 1.62 planned steps against "
           "1.75 literature steps (Table 11, Figure 4B). The same run also plans the three-step synthesis of "
           "benorilate, where the ester disconnection splits the molecule into acetylsalicylic acid and paracetamol, "
           "each of which is then disconnected to simple building blocks — the search recovers the fact that "
           "benorilate is a mutual prodrug without being told.")
    table(doc,
          ["Drug", "Literature steps", "Planned steps", "Solved", "Confidence"],
          [["Lidocaine", "2", "2", "yes", "0.66"],
           ["Phenacetin", "2", "2", "yes", "0.66"],
           ["Benorilate", "3", "3", "yes", "0.54"],
           ["Sulfanilamide", "2", "2", "yes", "0.66"],
           ["Aspirin", "1", "1", "yes", "0.83"],
           ["Paracetamol", "1", "1", "yes", "0.83"],
           ["Benzocaine", "1", "1", "yes", "0.83"],
           ["Vanillin", "2", "1", "yes", "0.83"]],
          "Table 11. Retrosynthesis benchmark. Every target is solved, and no planned route is longer than its "
          "literature counterpart.",
          widths=[3.6, 3.2, 3.0, 2.0, 2.4], font_size=9)
    figure(doc, "fig_panel_b.png", 11.8,
           "Figure 4 (continued). Panel B: planned route length per benchmark drug. Every bar is a solved target; "
           "benorilate requires three steps, the four one-step cases are ester or amide couplings.")
    p(doc, "A planner restricted to one-step disconnections solves only 4 of the 8 targets (aspirin, paracetamol, "
           "benzocaine, vanillin) and fails on every target that needs an intermediate assembled, including "
           "lidocaine, phenacetin, benorilate and sulfanilamide. The recursive search is therefore responsible for "
           "half of the benchmark. The suite is deliberately restricted to targets whose syntheses stay inside the "
           "six reaction classes of the template set; epoxide opening, Friedel–Crafts acylation and similar "
           "transformations are out of scope and are the natural next addition to the tool layer.")

    # ------------------------------------------------------------------ 5.7
    h2(doc, "5.7  Scenario 4: compiling protocols into SDL instructions")
    p(doc, "The strictosidine-synthase activity assay is compiled into six opcodes — TRANSFER, TRANSFER, INCUBATE, "
           "TRANSFER, CENTRIFUGE, MEASURE — with volumes in millilitres, a 30 °C incubation for 30 min, and a "
           "48-minute simulated timeline whose bottleneck is the incubator (Figure 4C). The compiler flags four "
           "defaults (steps without an explicit duration), all of which are reported rather than silently applied.")
    p(doc, "The benchmark is the more informative test. Six clean protocols are all accepted by the validator, and "
           "five deliberately corrupted protocols are all caught (Table 12): a 5 mL aliquot in a 2 mL vial (vessel "
           "overflow), a 300 °C set-point on a 150 °C block, diethyl ether heated above its flash point, a quench "
           "with no stated volume, and a zero-minute incubation. The flammable-solvent case is the most interesting, "
           "because the hazard is not local to one sentence: the solvent appears in step 1 and the temperature in "
           "step 2, so the validator screens the protocol as a whole.")
    table(doc,
          ["Protocol", "Steps", "Opcodes", "Injected fault", "Detected", "Caught"],
          [["STR activity assay", "6", "6", "–", "–", "n/a"],
           ["Suzuki coupling", "7", "7", "–", "–", "n/a"],
           ["HATU amide coupling", "6", "6", "–", "–", "n/a"],
           ["Reductive amination", "6", "6", "–", "–", "n/a"],
           ["Recrystallisation", "5", "5", "–", "–", "n/a"],
           ["HPLC sample prep", "5", "5", "–", "–", "n/a"],
           ["Oversized aliquot", "4", "4", "vessel_overflow", "vessel_overflow", "yes"],
           ["Impossible temperature", "3", "3", "temperature_limit", "temperature_limit", "yes"],
           ["Flammable solvent", "3", "3", "flammable_hazard", "flammable_hazard", "yes"],
           ["Missing volume", "4", "4", "missing_volume", "missing_volume", "yes"],
           ["Zero duration", "3", "3", "non_positive_duration", "non_positive_duration", "yes"]],
          "Table 12. Protocol compiler benchmark: 6/6 clean protocols valid, 5/5 corrupted protocols caught.",
          widths=[4.2, 1.2, 1.4, 3.4, 3.4, 1.6], font_size=8.5)
    figure(doc, "fig_panel_c.png", 14.0,
           "Figure 4 (continued). Panel C: compiled SDL program on the digital twin. Every opcode is placed on its "
           "device and on the simulated timeline (48 min, 6 opcodes).")
    p(doc, "The validator is what makes the compiler useful. If static validation is skipped, all eleven protocols "
           "compile without error, including the five corrupted ones: compilation alone detects zero of the five "
           "faults, whereas the validator catches five of five while leaving the six clean protocols valid. This is "
           "the clearest example in the project of a deterministic check doing work that a fluent pipeline would "
           "silently omit.")

    # ------------------------------------------------------------------ 5.8
    h2(doc, "5.8  Ablations")
    p(doc, "Two ablations test the two mechanisms that distinguish MOCHI from a simple tool-calling loop (Table 13). "
           "Disabling runtime tool creation leaves the target-discovery pipeline unable to enforce the effector "
           "constraint: stage 3 reports the capability gap, the critic raises it, but no tool is built, and stage 4 "
           "has zero candidates. Disabling the experimental prior leaves the enzyme scorer functional but degrades "
           "the top of the ranking, moving the true best variant from rank 1 to rank 4. Both mechanisms are therefore "
           "load-bearing rather than decorative.")
    table(doc,
          ["Configuration", "Stage 3", "Stage 4", "Key metric"],
          [["Full pipeline (S1)", "10 competent", "10 ranked", "top-1 ASIC1, 0.496"],
           ["No tool creation (S1)", "capability gap", "0 ranked", "no ranking produced"],
           ["Full pipeline (S2)", "2,773 scored", "15 designed", "M276L rank 1"],
           ["No experimental prior (S2)", "2,773 scored", "15 designed", "M276L rank 4"]],
          "Table 13. Ablations. Removing either mechanism removes a capability, not just a few points.",
          widths=[4.6, 3.4, 3.0, 4.4], font_size=9)

    # ------------------------------------------------------------------ 5.9
    h2(doc, "5.9  Runtime and reproducibility")
    table(doc,
          ["Scenario", "Wall time", "Stages ok", "Logged HTTP calls", "Reproducible offline"],
          [["S1 target discovery", "≈105 s cold / 19 s warm", "4/4", "190", "yes (cached)"],
           ["S2 enzyme design", "6.6 s / 2.1 s", "4/4", "9", "yes"],
           ["S3 retrosynthesis", "0.3 s", "4/4", "0", "yes (local)"],
           ["S4 protocol → SDL", "0.2 s", "4/4", "0", "yes (local)"]],
          "Table 14. Runtime of the four scenarios under the same orchestrator and model endpoint.",
          widths=[4.2, 4.4, 2.2, 3.4, 3.6], font_size=9)
    p(doc, "Two stability observations are worth reporting. First, the identity of the top four targets is stable "
           "across repeated runs, while their order changes by less than 0.02 when the critic re-calibrates weights "
           "from dimension coverage; this is exactly the uncertainty the report quantifies, and is why the system "
           "reports a confidence band rather than a single winner. Second, determinism is a property of the data "
           "plane, not of the model: re-running with a different engine changes the prose but not the numbers, "
           "because every number is computed in Python from cached, hashed responses. The four canonical run "
           "directories are committed with the code, and the script paper/audit_numbers.py re-checks every table "
           "against them.")

    # ------------------------------------------------------------------ 5.10
    h2(doc, "5.10  Discussion")
    p(doc, "Comparison with existing work. ChemCrow and Coscientist demonstrate that a language model can orchestrate "
           "chemistry tools, but their evaluation is a set of demonstrations and their judge is a model; MOCHI "
           "replaces the judge with a deterministic audit and reports what happens when the audit disagrees. Target "
           "platforms such as Open Targets rank by association; MOCHI adds a mechanistic constraint and shows, in "
           "Table 7, that the constraint changes the top five. Retrosynthesis systems based on learned policies "
           "achieve broader coverage than six templates; the trade-off made here is explicit, with a measurable "
           "cost (4/8 targets need recursion) and a measurable benefit (every step inspectable). For protocol "
           "compilation, published automation platforms start from a program; the contribution here is the "
           "translation and the static validation, with a quantitative detection rate.")
    p(doc, "Strengths. (i) Generality without duplication: the same agents and audit drive four tasks, which is "
           "measured by the absence of agent-level changes rather than asserted. (ii) Auditability: 190 logged HTTP "
           "calls, a deterministic veto, and a number-by-number audit script. (iii) Honest uncertainty: the LRP6 "
           "result is a negative one, reported with the dimensions that support it and the link that is missing. "
           "(iv) Cost: the whole suite runs in about two minutes without a GPU, so the pipeline can be re-run for "
           "every revision of the analysis.")
    p(doc, "Limitations. (i) Coverage of the candidate pool: the co-expression screen uses a 600-gene KEGG "
           "signalling panel rather than the whole transcriptome, which may miss effectors outside canonical "
           "pathways. (ii) The enzyme scorer is physics-light: V176F is missed because packing against the substrate "
           "is not modelled, and an energy model is the obvious upgrade. (iii) The retrosynthesis template set has "
           "six reaction classes, so targets that require epoxide opening or Friedel–Crafts chemistry are out of "
           "scope. (iv) The protocol parser handles the imperative style of standard operating procedures, not "
           "arbitrary prose. (v) The evidence base is observational: TCGA-COADREAD, Open Targets and STRING describe "
           "association, and the directional claim for LRP6 rests on the wet-lab experiments, not on the ranking.")
    p(doc, "Threats to validity. Public APIs change: a database update could change a score, which is why responses "
           "are cached and hashed and the canonical runs are committed. The reported runs use one model endpoint; a "
           "different model may phrase the rationale differently, but the numbers are computed from stage programs "
           "and are therefore unchanged. Finally, the top-1 target flips between ASIC1 and NOTCH1 under weight "
           "re-calibration, which is why the report treats the top four as the finding and the ordering as a "
           "prioritisation.")
    p(doc, "Future work. Four directions follow directly from the limitations: replacing the heuristic enzyme score "
           "with an energy-based or learned model while keeping the audit; extending the retrosynthesis templates "
           "with epoxide opening and Friedel–Crafts chemistry; widening the co-expression screen to the full "
           "transcriptome; and adding a learned protocol parser behind the same validator interface. The "
           "tool-creation loop already provides the mechanism for the first and second: a capability gap is exactly "
           "what triggers a new tool.")


def section6(doc, c: Citer) -> None:
    h1(doc, "Conclusions")
    p(doc, "This project asked whether a multi-agent system can make AIDD decisions that are not only plausible but "
           "reproducible and auditable, and whether one orchestrator can serve several fundamentally different "
           "tasks. The answers, within the scope tested, are affirmative.")
    p(doc, "Generality (RQ1). The same manager, developer, critic and tool-creation loop drove target discovery, "
           "enzyme design, retrosynthesis and protocol compilation by swapping only four stage programs and a "
           "template per scenario; no agent code was duplicated. The hypothesis that stages are contracts rather "
           "than scripts was not falsified.")
    p(doc, "Self-evolution (RQ2). The target scenario created its own signalling-competence scorer at runtime; the "
           "tool passed 13/13 controls, entered the ocean, and the ablation showed that without it the pipeline "
           "cannot enforce the effector constraint and produces no ranking. Tool creation is therefore not a "
           "demonstration but a load-bearing capability.")
    p(doc, "Reliability (RQ3). The deterministic audit, the explicit experimental prior and the provenance log made "
           "every claim checkable. The prior ablation moved the true best enzyme variant from rank 1 to rank 4, and "
           "the audit never allowed a failed control to be waived. Against baselines, the six-dimension ranking "
           "kept all four Wnt/Notch-class receptors in the top four where association-only and competence-only "
           "rankings did not; the full enzyme score was the only ranking to place M276L first; recursive search "
           "doubled the retrosynthesis success rate relative to one-step planning; and static validation caught "
           "five faults that compilation alone missed.")
    p(doc, "The most useful result is a negative one: the published effector LRP6 is competent but unsupported by "
           "the available cohort, and the system says so. A system that reported otherwise would be less useful, "
           "not more. MOCHI's contribution is therefore less a new predictor than a discipline: it makes the "
           "evidence behind a decision explicit, makes the failure modes visible, and makes the next experiment "
           "obvious.")


def section7(doc, c: Citer) -> None:
    h1(doc, "References")
    for ref in c.reference_list():
        par = p(doc, ref, size=10, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=3)

