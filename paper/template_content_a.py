"""Report body (§1–§7) for the AIDD8122 template build."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH

from build_template_report import bullets, caption, figure, h1, h2, p, table

# ---------------------------------------------------------------------------
# references: numbers are assigned in order of first citation
# ---------------------------------------------------------------------------
REFS = {
    "react": "Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., Cao, Y. ReAct: Synergizing "
             "reasoning and acting in language models. International Conference on Learning Representations "
             "(ICLR), 2023.",
    "toolformer": "Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., "
                  "Cancedda, N., Scialom, T. Toolformer: Language models can teach themselves to use tools. "
                  "Advances in Neural Information Processing Systems (NeurIPS), 2023.",
    "chemcrow": "M. Bran, A., Cox, S., Schilter, O., Baldassari, C., White, A. D., Schwaller, P. Augmenting "
                "large language models with chemistry tools. Nature Machine Intelligence, 6, 525–535, 2024.",
    "coscientist": "Boiko, D. A., MacKnight, R., Kline, B., Gomes, G. Autonomous chemical research with large "
                   "language models. Nature, 624, 570–578, 2023.",
    "biodiscovery": "Roohani, Y., Lee, A., Huang, Q., Vora, J., Steinhart, Z., Huang, K., Mars, P., Liang, P., "
                    "Leskovec, J. BioDiscoveryAgent: an AI agent for designing genetic perturbation experiments. "
                    "International Conference on Learning Representations (ICLR), 2025.",
    "stella": "Jin, R. et al. STELLA: towards a biomedical world model with self-evolving multimodal agents. "
              "bioRxiv 2025.07.01.662467, 2025.",
    "labos": "Cong, L. et al. LabOS: the AI-XR co-scientist that sees and works with humans. arXiv:2510.14861, "
             "2025.",
    "uniprot": "The UniProt Consortium. UniProt: the universal protein knowledgebase in 2023. Nucleic Acids "
               "Research, 51, D523–D531, 2023.",
    "opentargets": "Ochoa, D., Hercules, A., Carmona, M., Suveges, D., Baker, J., Malangone, C., et al. The "
                   "next-generation Open Targets Platform: reimagined, redesigned, rebuilt. Nucleic Acids "
                   "Research, 51, D1353–D1359, 2023.",
    "cbioportal": "Cerami, E., Gao, J., Dogrusoz, U., Gross, B. E., Sumer, S. O., et al. The cBioPortal for "
                  "cancer genomics opens new frontiers. Cancer Discovery, 2, 401–404, 2012.",
    "string": "Szklarczyk, D., Kirsch, R., Koutrouli, M., et al. The STRING database in 2023. Nucleic Acids "
              "Research, 51, D638–D646, 2023.",
    "intact": "Del Toro, N., Shrivastava, A., Ragueneau, E., et al. The IntAct database: efficient access to "
              "fine-grained molecular interaction data. Nucleic Acids Research, 50, D648–D653, 2022.",
    "alphafold": "Jumper, J., Evans, R., Pritzel, A., et al. Highly accurate protein structure prediction with "
                 "AlphaFold. Nature, 596, 583–589, 2021.",
    "attention": "Vaswani, A., Shazeer, N., Parmar, N., et al. Attention is all you need. Advances in Neural "
                 "Information Processing Systems (NeurIPS), 2017.",
    "blosum": "Henikoff, S., Henikoff, J. G. Amino acid substitution matrices from protein blocks. Proceedings "
              "of the National Academy of Sciences, 89, 10915–10919, 1992.",
    "kyte": "Kyte, J., Doolittle, R. F. A simple method for displaying the hydropathic character of a protein. "
            "Journal of Molecular Biology, 157, 105–132, 1982.",
    "str_eng": "Chen, R., et al. Enzyme engineering for alkaloid biosynthesis. Current Opinion in Biotechnology, "
               "2021.",
    "segler": "Segler, M. H. S., Preuss, M., Waller, M. P. Planning chemical syntheses with deep neural networks "
              "and symbolic AI. Nature, 555, 604–610, 2018.",
    "coley": "Coley, C. W., Thomas, D. A., Lummiss, J. A. M., et al. A robotic platform for flow synthesis of "
             "organic compounds informed by AI planning. Science, 365, eaax1566, 2019.",
    "rdkit": "Landrum, G. RDKit: open-source cheminformatics software. https://www.rdkit.org, 2024.",
    "pubchem": "Kim, S., Chen, J., Cheng, T., et al. PubChem 2023 update. Nucleic Acids Research, 51, "
               "D1373–D1380, 2023.",
    "biopython": "Cock, P. J. A., Antao, T., Chang, J. T., et al. Biopython: freely available Python tools for "
                 "computational molecular biology. Bioinformatics, 25, 1422–1423, 2009.",
}


class Citer:
    def __init__(self) -> None:
        self.order: list[str] = []

    def __call__(self, *keys: str) -> str:
        nums = []
        for k in keys:
            if k not in self.order:
                self.order.append(k)
            nums.append(self.order.index(k) + 1)
        return "[" + ", ".join(str(n) for n in nums) + "]"

    def reference_list(self) -> list[str]:
        return [f"[{i}]  {REFS[k]}" for i, k in enumerate(self.order, 1)]


# ---------------------------------------------------------------------------
# §1 Introduction
# ---------------------------------------------------------------------------
def section1(doc, c: Citer) -> None:
    h1(doc, "Introduction", page_break=True)

    p(doc, "Artificial-intelligence drug discovery (AIDD) now produces more candidate targets, molecules and "
           "protocols than any single researcher can triage, yet the tools that generate them are disjoint and "
           "the reasoning that connects them is rarely written down. This report describes MOCHI, a self-evolving "
           "multi-agent system that turns heterogeneous public evidence into four kinds of auditable decision: "
           "which effector target to pursue, which enzyme variants to build, which synthesis route to run, and "
           "which laboratory protocol can be executed by a robot. The guiding principle is deliberately "
           "conservative: language models propose, and deterministic Python disposes. Every number in this report "
           "is computed by code from a cached, hashed public response, so the claims can be re-derived by a reader "
           "who never runs the model.")

    h2(doc, "1.1  The decision bottleneck in AI-driven drug discovery")
    p(doc, "The methodological advances of the field have been remarkable. Deep networks predict molecular "
           "properties from structure; AlphaFold predicts protein structures at near-experimental accuracy "
           f"{c('alphafold')}; docking and generative models propose binders at scale; and public resources such "
           f"as UniProt, Open Targets, cBioPortal, STRING and IntAct {c('uniprot', 'opentargets', 'cbioportal', 'string', 'intact')} "
           "make it possible to interrogate a target from a dozen angles in minutes. What has not scaled is the "
           "translation of those data into a defensible decision.")
    p(doc, "Consider the questions a discovery programme actually asks. Is this receptor the effector through which "
           "my anchor protein signals, or merely co-expressed with it? Is this mutation close enough to the active "
           "site to matter, and conservative enough to fold? Does this route end in building blocks that can be "
           "bought? Will this protocol overflow a 2 mL vial or heat diethyl ether above its flash point? Each "
           "question needs three ingredients: heterogeneous evidence, an explicit constraint that cannot be "
           "argued away, and a written rationale. Today they are assembled by hand, and the assembly is rarely "
           "preserved.")

    h2(doc, "1.2  Why agency, and why auditability")
    p(doc, "Large language models are attractive precisely here, because they can plan, call tools and write the "
           f"rationale {c('react', 'toolformer')}. A single model with a bag of tools is nevertheless a poor fit "
           "for regulated scientific reasoning. It may invent a number, silently skip a control, or answer "
           "differently on two consecutive runs. Chemistry and biology agents have therefore moved towards "
           f"multi-step tool use and, more recently, towards self-evolving tool libraries {c('chemcrow', 'coscientist', 'biodiscovery', 'stella', 'labos')}. "
           "The evaluation of such systems, however, is usually a single task, the judge is frequently another "
           "language model, and the tool outputs behind a claim are rarely preserved.")
    p(doc, "MOCHI treats the orchestration layer as an engineering artefact with two separated planes. The control "
           "plane decides what to do next: a manager decomposes the task into four stages, a developer executes "
           "each stage program, and a critic audits the result. The data plane performs every computation that "
           "appears in the report. The critic's audit is deterministic Python and has veto power: a failed hard "
           "check raises the verdict to revise, and a missing capability raises it to evolve, regardless of what "
           "the model believes. That single rule is what makes the output reportable rather than merely plausible.")

    h2(doc, "1.3  Scope: four scenarios, one orchestrator")
    p(doc, "To test whether the architecture is a platform rather than a demo, the same orchestrator is applied "
           "to four tasks that stress different parts of the problem (Table 1). In S1, target discovery, the "
           "anchor is DPEP1 in colorectal cancer and the question is which signal-transducing membrane protein "
           "relays its effect. In S2, enzyme design, the question is which fifteen variants of strictosidine "
           "synthase should be built given a published first-round scan. In S3, retrosynthesis, the question is "
           "the shortest route from a drug molecule to purchasable building blocks. In S4, protocol "
           "compilation, the question is whether a written SOP can be lowered to a validated, machine-executable "
           "instruction program. Only the four stage programs change between scenarios; the agents, the audit, "
           "the tool layer and the report machinery are shared.")
    table(doc,
          ["Scenario", "Input", "Core computation", "Output", "Failure mode exercised"],
          [["S1 Target discovery", "anchor gene + disease", "six-dimension evidence scoring", "ranked effectors",
            "missing capability"],
           ["S2 Enzyme design", "enzyme + round-1 data", "structure/prior variant scoring", "library + primers",
            "knowledge a model lacks"],
           ["S3 Retrosynthesis", "target SMILES", "template AND-OR search to stock", "route", "dead ends"],
           ["S4 Protocol → SDL", "natural-language SOP", "typed compilation + validation", "SDL program",
            "silent unit errors"]],
          "Table 1. The four scenarios share one orchestrator and differ only in their stage programs and tools.",
          widths=[3.1, 2.9, 4.0, 2.9, 3.1], font_size=9)

    h2(doc, "1.4  Contributions")
    bullets(doc, [
        "A scenario-agnostic, self-evolving multi-agent architecture in which the critic's audit is deterministic "
        "and has veto power over the language model.",
        "A shared Tool Ocean of 46 tools spanning omics databases, structure analysis, cheminformatics, "
        "retrosynthesis and laboratory automation, all behind one cached, provenance-logged interface.",
        "Four independently runnable AIDD scenarios, each with a quantitative evaluation that combines a "
        "published hindcast, a literature benchmark, a baseline comparison and an ablation.",
        "Evidence that the two distinctive mechanisms are load-bearing: without runtime tool creation the target "
        "pipeline cannot enforce the effector constraint, and without the experimental prior the true best enzyme "
        "variant falls from first to fourth.",
        "A reproducibility contract: an offline deterministic engine, an OpenAI-compatible engine, pinned run "
        "artefacts and a single command that regenerates every table and figure.",
    ])

    h2(doc, "1.5  Report organisation and code availability")
    p(doc, "Section 2 reviews the literature the project builds on; Section 3 states the research questions and "
           "objectives; Section 4 describes the architecture, the tools and the decision models; Section 5 reports "
           "the results, the baseline comparisons and the ablations, and discusses strengths, limitations and "
           "future work; Section 6 concludes; Section 7 lists the references.")
    p(doc, "The complete implementation, the four canonical run directories that back every number, and the command "
           "that rebuilds the report are available at https://github.com/simmzx/mochi.")


# ---------------------------------------------------------------------------
# §2 Literature Review
# ---------------------------------------------------------------------------
def section2(doc, c: Citer) -> None:
    h1(doc, "Literature Review")
    p(doc, "This review moves from the methodological core of AIDD to the agentic layer that sits on top of it, and "
           "ends by identifying the four gaps that motivate the present work.")

    h2(doc, "2.1  From molecular property prediction to decision support")
    p(doc, "AIDD began with prediction: quantitative structure–activity relationships, then deep learning over "
           "molecular graphs and strings, now increasingly transformer-based representations "
           f"{c('attention')}. Structure prediction {c('alphafold')} and large public bioactivity resources "
           f"{c('pubchem')} have made the individual predictions cheap. The consequence is a shift in the "
           "bottleneck: the scarce resource is no longer a model but the judgement that selects among its outputs. "
           "A predicted pIC50 does not say whether a target is worth pursuing; a predicted pose does not say "
           "whether the series is novel; a predicted route does not say whether its leaves can be bought. Decision "
           "support therefore requires evidence integration, explicit constraints and traceability, which are "
           "exactly the properties that current pipelines lack.")

    h2(doc, "2.2  Tool-augmented language-model agents")
    p(doc, "ReAct interleaves reasoning traces with actions and established the plan–act–observe loop "
           f"{c('react')}, while Toolformer showed that a model can learn when to call an API {c('toolformer')}. "
           f"Chemistry-specific systems followed: ChemCrow combines eighteen expert tools under a language-model "
           f"planner {c('chemcrow')} and Coscientist closes the loop from literature search to robotic execution "
           f"{c('coscientist')}. In biology, BioDiscoveryAgent designs genetic perturbation experiments "
           f"{c('biodiscovery')}, and self-evolving frameworks that maintain a growing tool library have recently "
           f"been proposed for biomedical research {c('stella', 'labos')}.")
    p(doc, "These systems share a design pattern — a planner, a tool set, an evaluator — and differ in how much "
           "autonomy the model is given. Three weaknesses recur. First, evaluation is usually single-task, so "
           "generality is asserted rather than measured. Second, the evaluator is itself a model, so a confident "
           "but wrong plan can pass review. Third, reproducibility is rarely demonstrated: the tool outputs behind "
           "a claim are not preserved. MOCHI addresses all three by making the orchestration layer explicit, by "
           "replacing the model-as-judge with a deterministic audit, and by logging every external call.")

    h2(doc, "2.3  Target discovery and evidence integration")
    p(doc, "Target identification platforms integrate disease associations, expression, pathways and chemical "
           f"tractability {c('opentargets', 'cbioportal', 'string', 'intact')}. Their rankings are typically "
           "association-first: a gene rises because it is linked to the disease or to the anchor, not because it "
           "can mechanistically relay a signal. For an anchor that is a membrane receptor this is acceptable; for "
           "an anchor that is a GPI-anchored ectoenzyme with no intracellular domain it is not, because the "
           "effector must be a separate signal-transducing protein. The literature on effector biology is rich, but "
           "the corresponding constraint is rarely encoded in a computational pipeline, and the uncertainty of the "
           "inference — which link is supported and which is missing — is rarely reported.")

    h2(doc, "2.4  Structure- and prior-guided enzyme engineering")
    p(doc, f"Enzyme engineering has been transformed by accurate structure prediction {c('alphafold')} and by "
           f"decades of substitution statistics {c('blosum', 'kyte')}. Conservation across homologs remains one of "
           f"the strongest single predictors of tolerable substitutions {c('biopython')}, and experimental scans "
           f"provide position-level priors that no sequence model can infer {c('str_eng')}. Learned mutation "
           "predictors outperform hand-crafted scores when thousands of measurements exist for the family, but "
           "they are data-hungry and opaque. A common practical setting — one enzyme, one small round of screening, "
           "a budget of fifteen variants — is therefore better served by a transparent structural score that "
           "combines distance to the catalytic site, substitution chemistry, packing and the experimental prior, "
           "and that states its assumptions.")

    h2(doc, "2.5  Retrosynthesis planning")
    p(doc, "Retrosynthesis has two mature traditions. Learned policies, exemplified by three-step expansion with "
           f"Monte-Carlo tree search {c('segler')}, achieve broad coverage but are hard to audit; template-based "
           f"planners keep every step explainable and integrate naturally with robotic execution {c('coley')}. "
           f"Both rely on a stock of purchasable building blocks and on cheminformatics toolkits for sanitisation "
           f"and canonicalisation {c('rdkit')}. The trade-off is the one this project makes explicitly: a small, "
           "curated template set yields high-precision, inspectable routes and predictable failure modes, at the "
           "cost of coverage for reaction classes outside the set.")

    h2(doc, "2.6  Laboratory automation and protocol compilation")
    p(doc, "Self-driving laboratories require protocols as typed programs rather than prose. Compilation involves "
           "four separable steps — parsing sentences into operations, mapping operations to devices with SI units, "
           "statically validating feasibility and safety, and simulating the execution — and each step has its own "
           "failure mode: a missing unit, a vessel that overflows, a solvent heated above its flash point. "
           "Published automation platforms demonstrate execution once the program exists; the translation from a "
           "written SOP to that program remains largely manual, and the validation step is often implicit in the "
           "hardware rather than explicit in software.")

    h2(doc, "2.7  Gaps addressed by this work")
    bullets(doc, [
        "Generality: agentic systems are evaluated on one task; it is unclear whether one orchestration layer can "
        "serve evidence integration, combinatorial design, graph search and program compilation.",
        "Auditability: when the evaluator is a model, a failed control can be argued away; a deterministic veto is "
        "needed for a result to be reportable.",
        "Self-evolution: tool creation is usually demonstrated, not ablated; its contribution to a task should be "
        "measured by removing it.",
        "Reproducibility and baselines: claims are rarely checked against simpler alternatives, and the tool "
        "outputs behind them are rarely preserved.",
    ])
    p(doc, "These gaps translate directly into the research questions of Section 3.")


# ---------------------------------------------------------------------------
# §3 Research questions and objectives
# ---------------------------------------------------------------------------
def section3(doc, c: Citer) -> None:
    h1(doc, "Research Questions and Objectives")
    p(doc, "The project is organised around three questions that can be answered with the artefacts of a single "
           "run, rather than around one predictive benchmark. Each question is paired with a hypothesis and with "
           "the measurement that would falsify it.")

    h2(doc, "3.1  Research questions and hypotheses")
    p(doc, "RQ1 (generality). Can one orchestration layer drive four structurally different AIDD tasks — evidence "
           "integration, combinatorial design, graph search and program compilation — without task-specific agent "
           "code? Hypothesis H1: if stages are contracts rather than scripts, then swapping four stage programs "
           "should be sufficient, and no agent module should need to change. Falsified if any scenario requires "
           "editing an agent or the orchestrator.")
    p(doc, "RQ2 (self-evolution). Does the ability to create a tool at runtime add capability that a static tool "
           "library cannot provide, and is the created tool trustworthy? Hypothesis H2: the target-discovery task "
           "cannot be completed without a signalling-competence scorer, and a tool admitted only after passing a "
           "control suite will behave like a first-class tool. Falsified if the pipeline still ranks candidates "
           "when creation is disabled, or if the created tool fails its controls.")
    p(doc, "RQ3 (reliability). Does a deterministic critic audit combined with an explicit experimental prior "
           "improve the reliability of decisions compared with an unaudited, prior-free pipeline? Hypothesis H3: "
           "removing the prior degrades the top of the enzyme ranking, while the audit prevents unsupported claims "
           "from being reported. Falsified if the prior-free ranking is identical, or if a failed control is "
           "reported as a success.")

    h2(doc, "3.2  Objectives and success criteria")
    table(doc,
          ["Objective", "Deliverable", "Success criterion", "Reported in"],
          [["O1 Build the orchestrator", "4 agents, stage registry, templates", "one code path runs all four "
            "scenarios", "§4.1–4.4"],
           ["O2 Curate the tool ocean", "46 tools, cached, provenance-logged", "every number traceable to a call",
            "§4.3, §4.7"],
           ["O3 Reproduce published science", "two hindcasts against published results",
            "recover the published answer or explain the miss", "§5.1–5.3"],
           ["O4 Validate feasibility outputs", "route and SDL benchmarks", "solved routes end in stock; corrupted "
            "protocols are caught", "§5.6–5.7"],
           ["O5 Demonstrate self-evolution", "runtime tool creation", "created tool passes 13/13 controls",
            "§5.1, §5.8"]],
          "Table 2. Objectives are tied to a deliverable, a measurable success criterion and a results section.",
          widths=[4.2, 4.6, 5.6, 2.6], font_size=9.5)

    p(doc, "The motivation for O3 deserves emphasis. A target-discovery system judged only on whether it produces "
           "a plausible list is unfalsifiable. Published answers are therefore used as hindcasts: the system is "
           "given exactly the information a researcher would have had before the answer was known, and the report "
           "states whether, and at what rank, the known result is recovered.")

    h2(doc, "3.3  Motivation and expected contribution")
    p(doc, "The expected contribution is not a new predictor. It is a discipline: making the evidence behind a "
           "decision explicit, making the failure modes visible, and making the next experiment obvious. If the "
           "approach works, a reader should be able to take any number in Section 5, follow it to a run artefact, "
           "and disagree with the interpretation without having to re-run the model.")
