# Design notes: scoring, decision contracts and guardrails

This document specifies exactly how a run turns database records into a ranked target
list, so that every number in `report.md` can be recomputed by hand from the artefacts.

---

## 1. Decision contracts

Each agent call has a fixed JSON contract (see `mochi/prompts/*.yaml`). The
orchestrator never parses free prose for control flow.

| call | producer | consumer | required keys |
|---|---|---|---|
| `manager.plan` | Manager | core loop | `stages[4]`, `hypothesis`, `reasoning` |
| `dev.plan` | Dev | stage program | `steps`, `tools`, `params` |
| `critic.review` | Critic | Manager | `verdict` (accept/revise/evolve), `tool_requests`, `weight_adjustments` |
| `tool_creation.design` | Tool Creation | Tool Creation | `tool_name`, `algorithm`, `validation_plan` |
| `manager.weights` | Manager | core loop | `weights` (six keys, sum 1) |
| `manager.synthesize` | Manager | report | `text` |

Two invariants hold in both engine modes (offline and OpenAI-compatible):

1. **The audit has veto power.** `CriticAgent._audit()` is pure Python. If a hard
   check fails, the final verdict is the stricter of the LLM verdict and the audit
   verdict (`max` over accept < revise < evolve).
2. **The LLM never computes a statistic.** All numbers come from `workflows/stages.py`
   and `tools/*`.

---

## 2. The six evidence dimensions

For each candidate the raw evidence is stored in `stage4_evidence.json` and mapped to
[0,1] by the monotone transforms below (`tools/scoring.py`). Transforms are absolute
(anchored to biology), not min-max over the candidate list, so adding a candidate cannot
change another candidate's score.

### 2.1 Association with the anchor

Four independent channels are combined with a noisy-OR, so that one strong channel
establishes association and absent channels (no PPI record, no co-mention) do not dilute
a strong result the way a weighted mean would:

```
A = 1 - Π_channel (1 - reliability · evidence)
reliability:  PPI 0.90 · co-expression 0.70 · literature 0.50 · pathway 0.50
evidence:     PPI score | min(1,|r|/0.60) | min(1,co-mentions/5) | max(J/0.30, IC/20)
```

* `PPI` = max(STRING combined score, IntAct interaction-count score); 0 when the pair was
  queried and not found (that is information: the databases have no physical evidence).
* `r` = Pearson correlation of mRNA across TCGA-COADREAD (n≈592), `J` = Jaccard of
  Reactome term sets, `IC` = information content (below).

### 2.2 Signalling competence

Produced by the tool the system creates for itself (`score_signaling_potential`):

```
S = 0.50·topology + 0.30·domain + 0.12·annotation + 0.08·localisation
```

* topology: 1.0 for TM≥1 with ≥20 intracellular residues, 0.72 for a short ICD,
  0.45 for TM without ICD, 0.04 for GPI-only, 0.02 for secreted.
* domain: sum of family weights (kinase .34, 7TM/GPCR .32, Frizzled .30, TNFR .30,
  LDL-receptor .26, cytokine receptor .24, death domain .22, phosphatase .18, channel .16),
  **only counted when the protein is membrane-embedded**.
* hard caps: GPI-only ≤ 0.15, soluble ≤ 0.20.

Control set (re-run at every creation, `validate()`):
positives LRP6, FZD1, EGFR, TNFRSF1A, TGFBR1, NOTCH1, IL6ST ≥ 0.60;
negatives DPEP1, CEACAM5, ALB, INS, GAPDH, LYZ ≤ 0.35.

### 2.3 Disease evidence

```
C = ( 0.45·σ(z) + 0.25·min(1,-log10 p/3)·direction + 0.12·min(1,mut/0.10) + 0.18·min(1,amp/0.25) )
```

`σ` is a logistic on the tumour-vs-normal z-score (z=0 → 0.5), `direction` = 1 if the
hazard ratio > 1 (high expression worse) and 0.45 otherwise. Survival is computed
locally: median split, Kaplan–Meier, log-rank, Mantel–Haenszel hazard ratio.

### 2.4 Pathway centrality

```
P = ( 0.35·min(1,shared/3) + 0.35·min(1,IC/20) + 0.20·min(1,degree/10) + 0.10·centrality ) / Σw
```

`IC` = Σ −log2(|term| / |library|) over shared Reactome terms after removing generic
terms (set size > 300 or a curated blocklist: "Metabolism", "Disease", "Signal
Transduction", ...). Without this filter, sharing "Metabolism" (≈1800 genes) makes any
two genes look related.

### 2.5 Novelty

```
N = 1 / (1 + n_disease/30 + n_total/400)
```

A gene with 0 CRC papers but 800 general papers scores 0.33, not 1.0 — it is studied,
just not in CRC.

### 2.6 Druggability

```
D = 0.40·min(1,bioactivities/200) + 0.35·min(1,drugs/5) + 0.25·[tractability bucket exists]
```

### 2.7 Composite

```
score = Σ_i w_i x_i / Σ_i w_i        (over the dimensions that exist)
score *= 0.88 + 0.12·coverage        (thin evidence is penalised, never zeroed)
```

Default weights: association .24, signalling .20, disease .20, pathway .10, novelty .10,
druggability .16. The critic re-calibrates them after the ranking, weighting each
dimension by its observed coverage.

A candidate is reported as **consistent** when ≥3 dimensions are ≥0.60 and at most one is
< 0.35. If no candidate is consistent, the run says so explicitly instead of hiding it.

---

## 3. Candidate admission rule (stage 2)

A candidate enters the scoring pool only if it is nominated by **≥2 independent
channels**, or by one strong channel:

| channel | criterion |
|---|---|
| physical | STRING combined ≥ 0.4, or ≥1 IntAct interaction |
| co-expression | \|r\| ≥ 0.30 and BH-FDR ≤ 0.10 in TCGA-COADREAD |
| pathway | ≥1 shared specific Reactome term (after generic-term filtering) |
| literature | ≥1 PubMed co-mention with the anchor |
| strong single channel | PPI ≥ 0.40, or ≥2 co-mentions, or pathway IC ≥ 5 bits |

This is the critic's "two independent sources" standard applied *before* scoring, which
prevents pathway-only artefacts from climbing the ranking on novelty alone.

---

## 4. Guardrails

| risk | guardrail |
|---|---|
| hallucinated numbers | all figures from tool output; `provenance.jsonl` records every HTTP call |
| silent API failure | `call_tool` returns `{"ok": false, ...}`; stages mark evidence as missing rather than zero |
| missing data inflating scores | weights renormalise over *present* dimensions; coverage penalty |
| LLM overriding a failed control | audit veto (§1) |
| runaway loops | one tool creation per run; revise at most twice; stage 4 never re-runs for a verdict |
| unreproducible runs | seeded ordering, cached HTTP, full transcript, weights in `run_summary.json` |

---

## 5. Extending the system

* **New tool**: add `@tool(name, category, description)` in `mochi/tools/`, import it
  in `tools/__init__.py`, declare it in the template `tools_required`. If it has a control
  set, add a `validate()` and register it like a created tool.
* **New template**: drop a YAML in `mochi/templates/prebuilt/` following
  `downstream_effector_target_discovery.yaml` (workflow steps + tools + quality metrics).
* **New stage program**: implement a function in `workflows/stages.py` and register it in
  `STAGE_PROGRAMS`; the manager plan maps stages positionally onto the four programs.

---

## 6. Two engines, one code path

`settings.resolve_engine()` decides between `offline` (deterministic reference engine) and
`openai` (any OpenAI-compatible endpoint). Everything above — agents, prompts, JSON
contracts, audits, report — is identical; only `LLM.complete()` differs. This is verified by
`tests/test_online_mode.py`, which drives the full run against a local mock server.

Engine resolution order: `--engine` flag > `MOCHI_ENGINE` > `auto` (key present ? openai :
offline). `Settings.validate()` fails fast with an actionable message when `openai` is selected
without a key; `mochi doctor` performs a real one-token round-trip.

### Prior-knowledge candidates and hindcasting

`--seed-genes` injects hypothesis genes into the stage-2 candidate pool (marked
`sources=prior`, excluded from the "data-driven nomination" claim but scored identically).
`--expect` records, for each expected gene, whether it was nominated at stage 2, its
signalling score, whether it reached the ranking, its rank/composite, and its six dimension
scores — written to `known_answer.json` and to report section 5.1.

This separation matters: a gene can score 0.75 on signalling competence yet never be
nominated, which is a statement about the data (no PPI, no co-expression, no shared
specific pathway) rather than about the scorer's quality.
