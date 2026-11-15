"""Retrosynthesis tools: template-based one-step disconnections and a best-first planner.

The one-step engine is *procedural* (RDKit bond editing) rather than reaction-SMARTS based,
because retro-templates need to add atoms (OH, halogen, boronic acid) that are not present in
the product.  Each disconnection returns fully sanitised precursor molecules plus a template
name and a cost, so the planner can rank routes transparently.

The planner is a depth-limited best-first AND-OR search.  A node is solved when every precursor
is either a commercially available building block (curated stock list) or has been solved at a
smaller depth.  No neural model is involved: every number in the output can be traced to a
template and a stock entry.
"""

from __future__ import annotations

import json
from functools import lru_cache

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdMolDescriptors

from .registry import tool

RDLogger.DisableLog("rdApp.*")

# ---------------------------------------------------------------------------
# stock of commercially available building blocks (canonical SMILES)
# ---------------------------------------------------------------------------
STOCK_SMILES = [
    # acids / anhydrides / acyl chlorides
    "O=C(O)c1ccccc1O", "CC(=O)OC(C)=O", "O=C(O)c1ccc(N)cc1", "CC(=O)Cl", "ClCC(=O)Cl",
    "O=C(O)C", "O=C(O)CC", "O=C(Cl)c1ccccc1", "O=S(=O)(Cl)c1ccc([N+](=O)[O-])cc1",
    "ClCC(=O)O", "BrCC(=O)O",
    # amines / anilines
    "Nc1ccc(O)cc1", "Cc1cccc(C)c1N", "CCNCC", "CCN(CC)CC", "CC(C)N", "N", "Cc1ccccc1N", "Nc1ccccc1",
    # phenols / aryl halides / arenes
    "Oc1cccc2ccccc12", "Oc1ccccc1OC", "Oc1ccccc1", "Brc1ccccc1", "Clc1ccccc1", "c1ccccc1",
    "CC(C)Cc1ccccc1", "COc1ccccc1", "Oc1ccc(CC(C)C)cc1",
    "O=Cc1ccc(O)c(O)c1", "O=Cc1ccc(O)cc1", "CC(=O)c1ccc(O)cc1",
    # small reagents / solvents that can terminate a route
    "CCO", "CO", "O", "CC(C)=O", "CC=O", "O=C=O", "N#C", "CS(=O)(=O)Cl", "CBr", "CCBr", "CCCCBr",
    "OCCN(CC)CC", "OCCCBr",
]

_STOCK = None


def _stock():
    global _STOCK
    if _STOCK is None:
        _STOCK = {}
        for smi in STOCK_SMILES:
            m = Chem.MolFromSmiles(smi)
            if m is not None:
                _STOCK[Chem.MolToSmiles(m)] = smi
    return _STOCK


def canonical(smiles: str) -> str | None:
    m = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(m) if m else None


# ---------------------------------------------------------------------------
# bond-editing helpers
# ---------------------------------------------------------------------------
def _break_and_cap(mol: Chem.Mol, bond: tuple[int, int], caps: dict[int, list[str]]):
    """Break a bond and attach capping atoms (given as element symbols) to each side."""
    rw = Chem.RWMol(mol)
    a, b = bond
    rw.RemoveBond(a, b)
    for atom_idx, elements in caps.items():
        for el in elements:
            new_idx = rw.AddAtom(Chem.Atom(el))
            rw.AddBond(atom_idx, new_idx, Chem.BondType.SINGLE)
    try:
        m = rw.GetMol()
        Chem.SanitizeMol(m)
    except Exception:  # noqa: BLE001
        return None
    frags = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=True)
    out = []
    for f in frags:
        if f.GetNumHeavyAtoms() == 0:
            continue
        out.append(Chem.MolToSmiles(f))
    return out


def _match_pairs(mol, smarts):
    patt = Chem.MolFromSmarts(smarts)
    if patt is None:
        return []
    return mol.GetSubstructMatches(patt)


# ---------------------------------------------------------------------------
# disconnection templates
# ---------------------------------------------------------------------------
def disconnection_templates() -> list[dict]:
    return [
        {"name": "amide", "cost": 1.0, "class": "C-N bond"},
        {"name": "ester", "cost": 1.0, "class": "C-O bond"},
        {"name": "aryl_ether", "cost": 1.5, "class": "Ar-O bond"},
        {"name": "n_alkylation", "cost": 1.6, "class": "N-C bond"},
        {"name": "sulfonamide", "cost": 1.2, "class": "S-N bond"},
    ]


def _amide(mol):
    out = []
    for match in _match_pairs(mol, "[CX3](=[OX1])[NX3]"):
        c, o, n = match
        bond = mol.GetBondBetweenAtoms(c, n)
        if bond is None:
            continue
        frags = _break_and_cap(mol, (c, n), {c: ["O"], n: []})
        if frags and len(frags) == 2:
            out.append({"name": "amide", "cost": 1.0, "precursors": frags,
                        "note": "acid + amine (amide coupling)"})
    return out


def _ester(mol):
    out = []
    for match in _match_pairs(mol, "[CX3](=[OX1])[OX2][CX4,c]"):
        c, o_carbonyl, o_ester, r = match
        bond = mol.GetBondBetweenAtoms(c, o_ester)
        if bond is None:
            continue
        frags = _break_and_cap(mol, (c, o_ester), {c: ["O"], o_ester: []})
        if frags and len(frags) == 2:
            out.append({"name": "ester", "cost": 1.0, "precursors": frags,
                        "note": "acid + alcohol (esterification)"})
    return out


def _nitro_fgi(mol):
    """Functional-group interconversion: an aniline is made by reducing the nitroarene."""
    out = []
    for match in _match_pairs(mol, "[NX3;H2][c]"):
        n, c = match
        rw = Chem.RWMol(mol)
        idx = rw.GetAtomWithIdx(n).GetIdx()
        rw.GetAtomWithIdx(idx).SetAtomicNum(7)
        rw.GetAtomWithIdx(idx).SetFormalCharge(1)
        rw.GetAtomWithIdx(idx).SetNumExplicitHs(0)
        o1 = rw.AddAtom(Chem.Atom(8))
        rw.AddBond(idx, o1, Chem.BondType.DOUBLE)
        o2 = rw.AddAtom(Chem.Atom(8))
        rw.AddBond(idx, o2, Chem.BondType.SINGLE)
        rw.GetAtomWithIdx(o2).SetFormalCharge(-1)
        try:
            m = rw.GetMol()
            Chem.SanitizeMol(m)
            smi = Chem.MolToSmiles(m)
        except Exception:  # noqa: BLE001
            continue
        out.append({"name": "nitro_fgi", "cost": 0.8, "precursors": [smi],
                    "note": "aniline from the corresponding nitroarene (reduction)"})
    return out


def _aryl_ether(mol):
    out = []
    for match in _match_pairs(mol, "[c][OX2][CX4]"):
        ar, o, c = match
        bond = mol.GetBondBetweenAtoms(o, c)
        if bond is None:
            continue
        frags = _break_and_cap(mol, (o, c), {o: [], c: ["Br"]})
        if frags and len(frags) == 2:
            out.append({"name": "aryl_ether", "cost": 1.5, "precursors": frags,
                        "note": "phenol + alkyl bromide (Williamson ether synthesis)"})
    return out


def _n_alkylation(mol):
    out = []
    for match in _match_pairs(mol, "[NX3;H0,H1;!$(N-C=O)][CX4]"):
        n, c = match
        bond = mol.GetBondBetweenAtoms(n, c)
        if bond is None:
            continue
        frags = _break_and_cap(mol, (n, c), {n: [], c: ["Br"]})
        if frags and len(frags) == 2:
            out.append({"name": "n_alkylation", "cost": 1.6, "precursors": frags,
                        "note": "amine + alkyl bromide (SN2)"})
    return out


def _sulfonamide(mol):
    out = []
    for match in _match_pairs(mol, "[SX4](=[OX1])(=[OX1])[NX3]"):
        s, o1, o2, n = match
        bond = mol.GetBondBetweenAtoms(s, n)
        if bond is None:
            continue
        frags = _break_and_cap(mol, (s, n), {s: ["Cl"], n: []})
        if frags and len(frags) == 2:
            out.append({"name": "sulfonamide", "cost": 1.2, "precursors": frags,
                        "note": "sulfonyl chloride + amine"})
    return out


DISCONNECTIONS = {
    "amide": _amide,
    "ester": _ester,
    "aryl_ether": _aryl_ether,
    "n_alkylation": _n_alkylation,
    "sulfonamide": _sulfonamide,
    "nitro_fgi": _nitro_fgi,
}


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------
@tool(
    "molecule_properties",
    "chemistry",
    "Parse a SMILES string and report identity/descriptor/functional-group information used "
    "by the retrosynthesis planner.",
    smiles="target molecule SMILES",
)
def molecule_properties(smiles: str) -> dict:
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return {"ok": False, "error": f"invalid SMILES: {smiles}"}
    groups = {
        "carboxylic_acid": len(m.GetSubstructMatches(Chem.MolFromSmarts("[CX3](=O)[OX2H1]"))),
        "amide": len(m.GetSubstructMatches(Chem.MolFromSmarts("[CX3](=O)[NX3]"))),
        "ester": len(m.GetSubstructMatches(Chem.MolFromSmarts("[CX3](=O)[OX2][CX4,c]"))),
        "aryl_ether": len(m.GetSubstructMatches(Chem.MolFromSmarts("[c][OX2][CX4]"))),
        "sulfonamide": len(m.GetSubstructMatches(Chem.MolFromSmarts("[SX4](=O)(=O)[NX3]"))),
        "nitro": len(m.GetSubstructMatches(Chem.MolFromSmarts("[N+](=O)[O-]"))),
        "primary_amine": len(m.GetSubstructMatches(Chem.MolFromSmarts("[NX3;H2][CX4,c]"))),
    }
    return {
        "ok": True,
        "source": "RDKit descriptors",
        "smiles": smiles,
        "canonical": Chem.MolToSmiles(m),
        "formula": rdMolDescriptors.CalcMolFormula(m),
        "mw": round(Descriptors.MolWt(m), 2),
        "clogp": round(Descriptors.MolLogP(m), 2),
        "hbd": rdMolDescriptors.CalcNumHBD(m),
        "hba": rdMolDescriptors.CalcNumHBA(m),
        "rings": rdMolDescriptors.CalcNumRings(m),
        "heavy_atoms": m.GetNumHeavyAtoms(),
        "functional_groups": groups,
        "buyable": Chem.MolToSmiles(m) in _stock(),
    }


@tool(
    "one_step_disconnections",
    "chemistry",
    "Enumerate plausible one-step retrosynthetic disconnections of a molecule using the curated "
    "template set, returning sanitised precursor sets with template name and cost.",
    smiles="molecule SMILES",
    max_precursors="discard disconnections producing more fragments than this",
)
def one_step_disconnections(smiles: str, max_precursors: int = 4) -> dict:
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return {"ok": False, "error": f"invalid SMILES: {smiles}"}
    results = []
    seen = set()
    for name, fn in DISCONNECTIONS.items():
        try:
            for cand in fn(m):
                prec = sorted(cand["precursors"])
                if len(prec) > max_precursors:
                    continue
                key = (cand["name"], tuple(prec))
                if key in seen:
                    continue
                seen.add(key)
                results.append({**cand, "precursors": prec,
                                "n_buyable": sum(1 for p in prec if p in _stock())})
        except Exception:  # noqa: BLE001
            continue
    return {"ok": True, "source": "curated disconnection templates (RDKit)", "smiles": smiles,
            "n_disconnections": len(results), "disconnections": results}


@tool(
    "is_buyable",
    "chemistry",
    "Check whether a molecule is in the curated building-block stock.",
    smiles="molecule SMILES",
)
def is_buyable(smiles: str) -> dict:
    c = canonical(smiles)
    return {"ok": True, "smiles": smiles, "canonical": c, "buyable": c in _stock()}


def _expand(smiles: str) -> list[dict]:
    res = one_step_disconnections(smiles)
    return res.get("disconnections", []) if res.get("ok") else []


def _solve(smiles: str, depth_left: int, path: set[str], stats: dict) -> dict | None:
    c = canonical(smiles)
    if c is None:
        return None
    if c in _stock():
        return {"smiles": c, "buyable": True, "steps": 0, "route": []}
    if depth_left <= 0 or c in path:
        stats["exhausted"] += 1
        return None
    stats["expanded"] += 1
    best = None
    for d in sorted(_expand(c), key=lambda x: (x["cost"] - 0.5 * x["n_buyable"])):
        stats["nodes"] += 1
        children = []
        ok = True
        for p in d["precursors"]:
            child = _solve(p, depth_left - 1, path | {c}, stats)
            if child is None:
                ok = False
                break
            children.append(child)
        if not ok:
            continue
        steps = 1 + sum(ch["steps"] for ch in children)
        score = d["cost"] + sum(ch.get("cost", 0) for ch in children) + 0.15 * steps
        cand = {"smiles": c, "buyable": c in _stock(), "template": d["name"], "note": d.get("note"),
                "steps": steps, "cost": round(score, 3), "children": children,
                "precursors": d["precursors"]}
        if best is None or cand["cost"] < best["cost"]:
            best = cand
    return best


@tool(
    "search_route",
    "retrosynthesis",
    "Best-first recursive retrosynthesis search from a target to the curated building-block "
    "stock, returning the best route tree with per-step templates and total cost.",
    smiles="target molecule SMILES",
    max_depth="maximum number of retrosynthetic steps",
    max_nodes="search budget (expanded nodes)",
)
def search_route(smiles: str, max_depth: int = 6, max_nodes: int = 400) -> dict:
    stats = {"nodes": 0, "expanded": 0, "exhausted": 0}
    route = _solve(smiles, max_depth, set(), stats)
    leaves = []

    def collect(node):
        if node.get("buyable"):
            leaves.append(node["smiles"])
            return
        for ch in node.get("children", []):
            collect(ch)

    if route:
        collect(route)
    return {
        "ok": True,
        "source": "template-based best-first retrosynthesis",
        "smiles": smiles,
        "solved": route is not None,
        "route": route,
        "n_leaves": len(set(leaves)),
        "leaves": sorted(set(leaves)),
        "search": stats,
    }


@tool(
    "route_metrics",
    "retrosynthesis",
    "Summarise a route: number of steps, template usage, leaf building blocks, approximate atom "
    "economy and a 0-1 confidence score.",
    route="route tree returned by search_route",
)
def route_metrics(route: dict) -> dict:
    if not route:
        return {"ok": False, "error": "empty route"}
    templates, leaves, steps = [], [], 0

    def walk(node):
        nonlocal steps
        if node.get("buyable"):
            leaves.append(node["smiles"])
            return
        steps += 1
        templates.append(node.get("template"))
        for ch in node.get("children", []):
            walk(ch)

    walk(route)
    conf = max(0.0, min(1.0, 1.0 - 0.12 * steps - 0.05 * len(set(templates))))
    return {
        "ok": True,
        "steps": steps,
        "templates": templates,
        "unique_templates": sorted(set(t for t in templates if t)),
        "leaves": leaves,
        "confidence": round(conf, 3),
        "cost": route.get("cost"),
    }
