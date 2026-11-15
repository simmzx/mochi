"""Protein-structure and sequence-analysis tools (no ML weights required).

Used by the enzyme-engineering scenario:

* AlphaFold DB model retrieval and CA-based structural features (contact number,
  burial, distance to annotated active/binding-site residues, pLDDT);
* homolog retrieval from UniProt plus Needleman-Wunsch alignment to build a
  position-specific conservation profile;
* substitution chemistry (BLOSUM62, residue volume, Kyte-Doolittle hydropathy);
* QuikChange-style mutagenesis primer design with a nearest-neighbour T_m estimate.

Everything is deterministic and works offline once the HTTP cache is warm.
"""

from __future__ import annotations

import math
from functools import lru_cache

from .http import request_json, request_text
from .registry import tool

AF_API = "https://alphafold.ebi.ac.uk/api/prediction"
UNIPROT = "https://rest.uniprot.org/uniprotkb"

# ---------------------------------------------------------------------------
# residue chemistry
# ---------------------------------------------------------------------------
BLOSUM62 = {
    ("A", "A"): 4, ("A", "R"): -1, ("A", "N"): -2, ("A", "D"): -2, ("A", "C"): 0, ("A", "Q"): -1,
    ("A", "E"): -1, ("A", "G"): 0, ("A", "H"): -2, ("A", "I"): -1, ("A", "L"): -1, ("A", "K"): -1,
    ("A", "M"): -1, ("A", "F"): -2, ("A", "P"): -1, ("A", "S"): 1, ("A", "T"): 0, ("A", "W"): -3,
    ("A", "Y"): -2, ("A", "V"): 0,
    ("R", "R"): 5, ("R", "N"): 0, ("R", "D"): -2, ("R", "C"): -3, ("R", "Q"): 1, ("R", "E"): 0,
    ("R", "G"): -2, ("R", "H"): 0, ("R", "I"): -3, ("R", "L"): -2, ("R", "K"): 2, ("R", "M"): -1,
    ("R", "F"): -3, ("R", "P"): -2, ("R", "S"): -1, ("R", "T"): -1, ("R", "W"): -3, ("R", "Y"): -2,
    ("R", "V"): -3,
    ("N", "N"): 6, ("N", "D"): 1, ("N", "C"): -3, ("N", "Q"): 0, ("N", "E"): 0, ("N", "G"): 0,
    ("N", "H"): 1, ("N", "I"): -3, ("N", "L"): -3, ("N", "K"): 0, ("N", "M"): -2, ("N", "F"): -3,
    ("N", "P"): -2, ("N", "S"): 1, ("N", "T"): 0, ("N", "W"): -4, ("N", "Y"): -2, ("N", "V"): -3,
    ("D", "D"): 6, ("D", "C"): -3, ("D", "Q"): 0, ("D", "E"): 2, ("D", "G"): -1, ("D", "H"): -1,
    ("D", "I"): -3, ("D", "L"): -4, ("D", "K"): -1, ("D", "M"): -3, ("D", "F"): -3, ("D", "P"): -1,
    ("D", "S"): 0, ("D", "T"): -1, ("D", "W"): -4, ("D", "Y"): -3, ("D", "V"): -3,
    ("C", "C"): 9, ("C", "Q"): -3, ("C", "E"): -4, ("C", "G"): -3, ("C", "H"): -3, ("C", "I"): -1,
    ("C", "L"): -1, ("C", "K"): -3, ("C", "M"): -1, ("C", "F"): -2, ("C", "P"): -3, ("C", "S"): -1,
    ("C", "T"): -1, ("C", "W"): -2, ("C", "Y"): -2, ("C", "V"): -1,
    ("Q", "Q"): 5, ("Q", "E"): 2, ("Q", "G"): -2, ("Q", "H"): 0, ("Q", "I"): -3, ("Q", "L"): -2,
    ("Q", "K"): 1, ("Q", "M"): 0, ("Q", "F"): -3, ("Q", "P"): -1, ("Q", "S"): 0, ("Q", "T"): -1,
    ("Q", "W"): -2, ("Q", "Y"): -1, ("Q", "V"): -2,
    ("E", "E"): 5, ("E", "G"): -2, ("E", "H"): 0, ("E", "I"): -3, ("E", "L"): -3, ("E", "K"): 1,
    ("E", "M"): -2, ("E", "F"): -3, ("E", "P"): -1, ("E", "S"): 0, ("E", "T"): -1, ("E", "W"): -3,
    ("E", "Y"): -2, ("E", "V"): -2,
    ("G", "G"): 6, ("G", "H"): -2, ("G", "I"): -4, ("G", "L"): -4, ("G", "K"): -2, ("G", "M"): -3,
    ("G", "F"): -3, ("G", "P"): -2, ("G", "S"): 0, ("G", "T"): -2, ("G", "W"): -2, ("G", "Y"): -3,
    ("G", "V"): -3,
    ("H", "H"): 8, ("H", "I"): -3, ("H", "L"): -3, ("H", "K"): -1, ("H", "M"): -2, ("H", "F"): -1,
    ("H", "P"): -2, ("H", "S"): -1, ("H", "T"): -2, ("H", "W"): -2, ("H", "Y"): 2, ("H", "V"): -3,
    ("I", "I"): 4, ("I", "L"): 2, ("I", "K"): -3, ("I", "M"): 1, ("I", "F"): 0, ("I", "P"): -3,
    ("I", "S"): -2, ("I", "T"): -1, ("I", "W"): -3, ("I", "Y"): -1, ("I", "V"): 3,
    ("L", "L"): 4, ("L", "K"): -2, ("L", "M"): 2, ("L", "F"): 0, ("L", "P"): -3, ("L", "S"): -2,
    ("L", "T"): -1, ("L", "W"): -2, ("L", "Y"): -1, ("L", "V"): 1,
    ("K", "K"): 5, ("K", "M"): -1, ("K", "F"): -3, ("K", "P"): -2, ("K", "S"): 0, ("K", "T"): -1,
    ("K", "W"): -3, ("K", "Y"): -2, ("K", "V"): -2,
    ("M", "M"): 5, ("M", "F"): 0, ("M", "P"): -2, ("M", "S"): -1, ("M", "T"): -1, ("M", "W"): -1,
    ("M", "Y"): -1, ("M", "V"): 1,
    ("F", "F"): 6, ("F", "P"): -4, ("F", "S"): -2, ("F", "T"): -2, ("F", "W"): 1, ("F", "Y"): 3,
    ("F", "V"): -1,
    ("P", "P"): 7, ("P", "S"): -1, ("P", "T"): -1, ("P", "W"): -4, ("P", "Y"): -3, ("P", "V"): -2,
    ("S", "S"): 4, ("S", "T"): 1, ("S", "W"): -3, ("S", "Y"): -2, ("S", "V"): -2,
    ("T", "T"): 5, ("T", "W"): -2, ("T", "Y"): -2, ("T", "V"): 0,
    ("W", "W"): 11, ("W", "Y"): 2, ("W", "V"): -3,
    ("Y", "Y"): 7, ("Y", "V"): -1,
    ("V", "V"): 4,
}

RESIDUE_VOLUME = {  # A^3, Zamyatnin
    "A": 88.6, "R": 173.4, "N": 114.1, "D": 111.1, "C": 108.5, "Q": 143.8, "E": 138.4,
    "G": 60.1, "H": 153.2, "I": 166.7, "L": 166.7, "K": 168.6, "M": 162.9, "F": 189.9,
    "P": 112.7, "S": 89.0, "T": 116.1, "W": 227.8, "Y": 193.6, "V": 140.0,
}

HYDROPATHY = {  # Kyte & Doolittle
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5, "G": -0.4,
    "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8,
    "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

AA3 = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU",
    "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE",
    "P": "PRO", "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}


def blosum(wt: str, mut: str) -> int:
    if wt == mut:
        return BLOSUM62.get((wt, wt), 0)
    return BLOSUM62.get((wt, mut), BLOSUM62.get((mut, wt), -4))


# ---------------------------------------------------------------------------
# AlphaFold structure
# ---------------------------------------------------------------------------
@tool(
    "fetch_alphafold_model",
    "structure",
    "Download and parse the AlphaFold DB model for a UniProt accession: per-residue CA "
    "coordinates, contact numbers (burial), and pLDDT confidence.",
    uniprot_id="UniProt accession, e.g. P68175",
)
def fetch_alphafold_model(uniprot_id: str) -> dict:
    meta = request_json("GET", f"{AF_API}/{uniprot_id}", service="alphafold", timeout=60)
    if not meta:
        return {"ok": False, "error": f"no AlphaFold model for {uniprot_id}"}
    pdb_url = meta[0].get("pdbUrl")
    pdb = request_text("GET", pdb_url, service="alphafold", timeout=120)
    ca, plddt = {}, {}
    for line in (pdb or "").splitlines():
        if not line.startswith("ATOM") or line[12:16].strip() != "CA":
            continue
        resi = int(line[22:26])
        ca[resi] = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        try:
            plddt[resi] = float(line[60:66])
        except ValueError:
            plddt[resi] = None
    if len(ca) < 30:
        return {"ok": False, "error": "parsed model has too few CA atoms"}
    contacts = {}
    for i, ci in ca.items():
        contacts[i] = sum(1 for j, cj in ca.items() if j != i and math.dist(ci, cj) < 8.0)
    return {
        "ok": True,
        "source": "AlphaFold DB (EBI)",
        "uniprot_id": uniprot_id,
        "pdb_url": pdb_url,
        "n_residues": len(ca),
        "mean_plddt": round(sum(v for v in plddt.values() if v) / max(1, sum(1 for v in plddt.values() if v)), 1),
        "ca": ca,
        "plddt": plddt,
        "contact_number": contacts,
    }


@tool(
    "pocket_geometry",
    "structure",
    "Heavy-atom geometry of positions relative to the annotated active/binding-site cluster: "
    "minimum side-chain-to-site distance (A), burial (CA contact number) and pLDDT. This is the "
    "structure signal used by the enzyme-engineering scorer.",
    uniprot_id="UniProt accession",
    positions="residue numbers to analyse",
    site_positions="annotated active/binding-site residue numbers",
)
def pocket_geometry(uniprot_id: str, positions: list[int], site_positions: list[int]) -> dict:
    meta = request_json("GET", f"{AF_API}/{uniprot_id}", service="alphafold", timeout=60)
    if not meta:
        return {"ok": False, "error": f"no AlphaFold model for {uniprot_id}"}
    pdb = request_text("GET", meta[0]["pdbUrl"], service="alphafold", timeout=120)
    atoms: dict[int, list[tuple[float, float, float]]] = {}
    ca: dict[int, tuple[float, float, float]] = {}
    plddt: dict[int, float] = {}
    for line in (pdb or "").splitlines():
        if not line.startswith("ATOM"):
            continue
        resi = int(line[22:26])
        xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        atoms.setdefault(resi, []).append(xyz)
        if line[12:16].strip() == "CA":
            ca[resi] = xyz
            try:
                plddt[resi] = float(line[60:66])
            except ValueError:
                pass
    site_xyz = [xyz for s in site_positions for xyz in atoms.get(s, [])]
    out = {}
    for pos in positions:
        if pos not in atoms:
            continue
        d = min((math.dist(a, s) for a in atoms[pos] for s in site_xyz), default=float("nan"))
        contacts = sum(1 for j, c in ca.items() if j != pos and math.dist(ca[pos], c) < 8.0)
        out[str(pos)] = {"min_heavy_dist": round(d, 2), "contacts": contacts, "plddt": plddt.get(pos)}
    return {
        "ok": True,
        "source": "AlphaFold DB (heavy atoms) + UniProt site annotations",
        "uniprot_id": uniprot_id,
        "n_sites": len(site_positions),
        "geometry": out,
    }


# ---------------------------------------------------------------------------
# homologs + conservation
# ---------------------------------------------------------------------------
def needleman_wunsch(a: str, b: str, gap: int = -8, mismatch: int = -2, match: int = 2) -> tuple[str, str]:
    """Global alignment (compact implementation, returns padded strings)."""
    n, m = len(a), len(b)
    prev = [i * gap for i in range(m + 1)]
    ptr = [[0] * (m + 1) for _ in range(n + 1)]
    for j in range(1, m + 1):
        ptr[0][j] = 2  # left
    for i in range(1, n + 1):
        cur = [i * gap] + [0] * m
        ptr[i][0] = 1  # up
        ai = a[i - 1]
        for j in range(1, m + 1):
            diag = prev[j - 1] + (match if ai == b[j - 1] else mismatch)
            up = prev[j] + gap
            left = cur[j - 1] + gap
            best, p = diag, 0
            if up > best:
                best, p = up, 1
            if left > best:
                best, p = left, 2
            cur[j] = best
            ptr[i][j] = p
        prev = cur
    i, j = n, m
    aa, bb = [], []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ptr[i][j] == 0:
            aa.append(a[i - 1]); bb.append(b[j - 1]); i -= 1; j -= 1
        elif i > 0 and (j == 0 or ptr[i][j] == 1):
            aa.append(a[i - 1]); bb.append("-"); i -= 1
        else:
            aa.append("-"); bb.append(b[j - 1]); j -= 1
    return "".join(reversed(aa)), "".join(reversed(bb))


@tool(
    "fetch_homologs",
    "database",
    "Retrieve homolog sequences from UniProt for conservation analysis.",
    uniprot_id="query accession (excluded from the result)",
    query="UniProt query selecting the homolog family",
    size="maximum number of sequences",
)
def fetch_homologs(uniprot_id: str, query: str = '(protein_name:"strictosidine synthase") AND (taxonomy_id:33090)',
                   size: int = 30) -> dict:
    payload = request_json(
        "GET",
        f"{UNIPROT}/search",
        service="uniprot",
        params={"query": query, "format": "json", "size": size,
                "fields": "accession,organism_name,length,sequence"},
        timeout=90,
    )
    seqs = []
    for e in (payload or {}).get("results", []):
        acc = e.get("primaryAccession")
        seq = (e.get("sequence") or {}).get("value")
        if acc and seq and acc != uniprot_id:
            seqs.append({"accession": acc, "organism": e.get("organism", {}).get("scientificName"), "sequence": seq})
    return {"ok": True, "source": "UniProt REST", "query": query, "n": len(seqs), "homologs": seqs}


@tool(
    "conservation_profile",
    "annotation",
    "Position-specific conservation from homologs: align every homolog to the query with "
    "Needleman-Wunsch and report the WT frequency and Shannon entropy per position.",
    query_sequence="query protein sequence",
    homolog_sequences="list of homolog sequences",
)
def conservation_profile(query_sequence: str, homolog_sequences: list[str]) -> dict:
    q = query_sequence.strip().upper()
    counts = [dict() for _ in q]
    aligned = 0
    for h in homolog_sequences[:60]:
        if not h:
            continue
        try:
            a, b = needleman_wunsch(q, h.strip().upper())
        except Exception:
            continue
        qi = 0
        for ca_, cb_ in zip(a, b):
            if ca_ != "-":
                if cb_ != "-":
                    counts[qi][cb_] = counts[qi].get(cb_, 0) + 1
                qi += 1
        aligned += 1
    profile = []
    for i, wt in enumerate(q):
        total = sum(counts[i].values())
        freq = counts[i].get(wt, 0) / total if total else None
        ent = None
        if total:
            ent = -sum((c / total) * math.log2(c / total) for c in counts[i].values())
        profile.append({"pos": i + 1, "wt": wt, "wt_freq": None if freq is None else round(freq, 3),
                        "entropy": None if ent is None else round(ent, 3), "n": total})
    return {
        "ok": True,
        "source": "Needleman-Wunsch alignment against UniProt homologs",
        "n_homologs": aligned,
        "profile": profile,
    }


# ---------------------------------------------------------------------------
# primers
# ---------------------------------------------------------------------------
def _tm_nn(seq: str) -> float:
    """Wallace/GC T_m estimate for a 50 mM Na+ primer (valid for 20-40 mers)."""
    seq = seq.upper()
    gc = sum(1 for c in seq if c in "GC")
    return round(64.9 + 41.0 * (gc - 16.4) / max(1, len(seq)), 1)


@tool(
    "design_quikchange_primers",
    "sequence",
    "Design a QuikChange site-directed mutagenesis primer pair for a codon change, with GC "
    "content and T_m, using the coding sequence and the target position.",
    sequence="coding nucleotide sequence",
    position="1-based residue position to mutate",
    wt="wild-type amino-acid letter",
    mut="mutant amino-acid letter",
    flank="number of flanking nucleotides on each side",
)
def design_quikchange_primers(sequence: str, position: int, wt: str, mut: str,
                              flank: int = 15) -> dict:
    """Return a QuikChange forward primer and its reverse complement for a codon change.

    ``sequence`` must be a **coding DNA** sequence and ``position`` the codon index
    (1-based).  Use :func:`design_primers_from_cds` when you only have a protein
    sequence and a full CDS.
    """
    codons = {
        "A": "GCT", "R": "CGT", "N": "AAT", "D": "GAT", "C": "TGT", "Q": "CAA", "E": "GAA",
        "G": "GGT", "H": "CAT", "I": "ATT", "L": "CTG", "K": "AAA", "M": "ATG", "F": "TTT",
        "P": "CCT", "S": "TCT", "T": "ACT", "W": "TGG", "Y": "TAT", "V": "GTT",
    }
    idx = position - 1
    if idx < flank or idx >= len(sequence) - flank or sequence[idx] != wt:
        return {"ok": False, "error": "position out of range or WT mismatch"}
    left = sequence[idx - flank: idx]
    right = sequence[idx + 1: idx + 1 + flank]
    fwd = left + codons[mut] + right
    comp = str.maketrans("ACGT", "TGCA")
    rev = fwd.translate(comp)[::-1]
    return {
        "ok": True,
        "position": position,
        "wt": wt,
        "mut": mut,
        "forward": fwd,
        "reverse": rev,
        "gc_forward": round(100 * (fwd.count("G") + fwd.count("C")) / len(fwd), 1),
        "tm_forward": round(_tm_nn(fwd), 1),
        "length": len(fwd),
    }


CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M", "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*", "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R", "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def translate(seq: str) -> str:
    seq = seq.upper().replace("U", "T")
    return "".join(CODON_TABLE.get(seq[i:i + 3], "X") for i in range(0, len(seq) - 2, 3))


@tool(
    "fetch_nucleotide_sequence",
    "sequence",
    "Download a CDS/mRNA sequence from ENA by accession (e.g. the EMBL id cross-referenced by UniProt).",
    accession="ENA/EMBL accession",
)
def fetch_nucleotide_sequence(accession: str) -> dict:
    fasta = request_text("GET", f"https://www.ebi.ac.uk/ena/browser/api/fasta/{accession}",
                         service="ena", timeout=90, headers={"Accept": "text/plain"})
    lines = [l for l in (fasta or "").splitlines() if l and not l.startswith(">")]
    seq = "".join(lines).replace(" ", "").upper()
    if len(seq) < 30:
        return {"ok": False, "error": f"could not retrieve {accession}"}
    return {"ok": True, "source": "ENA browser API", "accession": accession,
            "length": len(seq), "sequence": seq}


@tool(
    "design_primers_from_cds",
    "sequence",
    "Map a protein position onto a coding sequence (by translated-frame matching) and design the "
    "corresponding QuikChange primer pair with GC content and T_m.",
    cds="coding DNA sequence",
    protein_sequence="protein sequence the positions refer to",
    positions="list of protein positions (1-based)",
    mutations="list of 'wt>mut' strings, parallel to positions",
    flank="flanking nucleotides on each side of the codon",
)
def design_primers_from_cds(cds: str, protein_sequence: str, positions: list[int],
                            mutations: list[str], flank: int = 15) -> dict:
    cds = cds.upper().replace("U", "T")
    prot = protein_sequence.strip().upper()
    probe = prot[:12]
    frame_off = None
    for f in range(3):
        translated = translate(cds[f:])
        idx = translated.find(probe)
        if idx >= 0:
            frame_off = f + idx * 3
            break
    if frame_off is None:
        return {"ok": False, "error": "could not locate the protein start in the CDS frame"}
    out = []
    for pos, mut in zip(positions, mutations):
        wt, alt = mut.split(">")
        codon_start = frame_off + (pos - 1) * 3
        codon = cds[codon_start:codon_start + 3]
        native = CODON_TABLE.get(codon, "X")
        if native != wt:
            out.append({"ok": False, "position": pos, "error": f"codon {codon} translates to {native}, not {wt}"})
            continue
        codons = {
            "A": "GCT", "R": "CGT", "N": "AAT", "D": "GAT", "C": "TGT", "Q": "CAA", "E": "GAA",
            "G": "GGT", "H": "CAT", "I": "ATT", "L": "CTG", "K": "AAA", "M": "ATG", "F": "TTT",
            "P": "CCT", "S": "TCT", "T": "ACT", "W": "TGG", "Y": "TAT", "V": "GTT",
        }
        fwd = cds[codon_start - flank: codon_start] + codons[alt] + cds[codon_start + 3: codon_start + 3 + flank]
        comp = str.maketrans("ACGT", "TGCA")
        rev = fwd.translate(comp)[::-1]
        out.append({
            "ok": True,
            "position": pos,
            "mutation": f"{wt}{pos}{alt}",
            "native_codon": codon,
            "new_codon": codons[alt],
            "forward": fwd,
            "reverse": rev,
            "gc_forward": round(100 * (fwd.count("G") + fwd.count("C")) / len(fwd), 1),
            "tm_forward": _tm_nn(fwd),
            "length": len(fwd),
        })
    return {"ok": True, "source": "CDS frame mapping + QuikChange design",
            "frame_offset": frame_off, "primers": out}

