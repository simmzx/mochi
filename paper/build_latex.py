"""Assemble the LaTeX project (MPU mpThesis template) and compile it with tectonic."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(r"D:\deepseek\workshop\mochi")
PAPER = ROOT / "paper"
TEX = PAPER / "latex"
TPL = Path(r"D:\browser download\MPU_AIDD_Proposal_Template_v6_1")
TECTONIC = Path(r"D:\deepseek\workshop\tmp\tectonic\tectonic.exe")

for d in [TEX, TEX / "chapters", TEX / "figures"]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- template assets
shutil.copy(TPL / "mpUnsrt.bst", TEX / "mpUnsrt.bst")
for name in ["MPU-Logo.pdf", "MPU-Logo-BW.pdf", "MPU-Logo-CPE.pdf", "MPU-Logo-green-small.pdf",
             "MPU-calligraphy.pdf", "MPU-calligraphy-ol.pdf"]:
    shutil.copy(TPL / name, TEX / name)

cls = (TPL / "mpThesis.cls").read_text(encoding="utf-8", errors="ignore")
cls = cls.replace("[pdftex,colorlinks]", "[colorlinks]").replace("[pdftex,hidelinks]", "[hidelinks]")

# --- cover: course cover instead of a thesis submission statement, name + student number
cls = cls.replace(
    "{\\it\nA \\textbf{\\InsertThesisType} submitted for the Examination \\\\\nin partial fulfillment of the requirements for the degree of \\\\\n\\InsertProgramme\n}",
    "{\\it\n\\InsertProgramme \\\\\nAIDD8122 -- Advanced Topics in Artificial Intelligence \\& Drug Discovery \\\\\nFinal Project Report\n}",
)
cls = cls.replace("\\large\\InsertStudentName\n\\vfill",
                  "\\large\\InsertStudentName, \\InsertStudentNumber\n\\vfill")

# --- only one title page: drop the hardback page, the copyright page and the second title page
cls = cls.replace(
    "\\begin{titlepage}\n\\IfHardback\\IfReview\\else\n\\pagestyle{empty}\n\\doublespacing\\MakeHardback \\cleardoublepage\n\\fi\\fi\n\\pagestyle{cover}\n\\doublespacing\\MakeCover \\cleardoublepage\n\\IfReview\\else%\n\\pagestyle{empty}\n\\doublespacing\\MakeCopyright \\cleardoublepage%\n\\fi\n\\pagestyle{empty}\n\\doublespacing\\MakeTitle \\cleardoublepage\n\\end{titlepage}",
    "\\begin{titlepage}\n\\pagestyle{cover}\n\\doublespacing\\MakeCover\n\\end{titlepage}\n\\clearpage",
)
cls = cls.replace("\\AtEndDocument{\n  \\cleardoublepage\\thispagestyle{empty}\n  \\null\n}", "")
(TEX / "mpThesis.cls").write_text(cls, encoding="utf-8")
print("cover patched:", "AIDD8122 -- Advanced Topics" in cls)
print("single title page:", "MakeCopyright" not in cls[cls.find("begin{titlepage}"):cls.find("begin{titlepage}") + 700])


for png in (PAPER / "figures").glob("*.png"):
    shutil.copy(png, TEX / "figures" / png.name)

# ---------------------------------------------------------------- citations
NUM_CITES = 22
CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def to_cite(match: re.Match) -> str:
    nums = [int(x) for x in match.group(1).split(",")]
    if any(n < 1 or n > NUM_CITES for n in nums):
        return match.group(0)
    keys = ",".join(f"r{n:02d}" for n in nums)
    return rf"\cite{{{keys}}}"


for path in sorted((TEX / "chapters").glob("Chapter*.tex")):
    text = path.read_text(encoding="utf-8")
    text = CITE_RE.sub(to_cite, text)
    path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------- appendix from chapter 7
ch7 = TEX / "chapters" / "Chapter7.tex"
if ch7.exists():
    body = ch7.read_text(encoding="utf-8")
    # drop the \chapter{...}\label{...} line that the converter put first
    lines = body.splitlines()
    body = "\n".join(lines[1:]) if lines and lines[0].startswith("\\chapter") else body
    body = body.replace("\\section{One-command reproduction}", "\\section{One-command reproduction}")
    (TEX / "chapters" / "AppendixA.tex").write_text("\\chapter{Reproducibility and Artefact Map}\n" + body,
                                                    encoding="utf-8")
    ch7.unlink()
ch6 = TEX / "chapters" / "Chapter6.tex"
if ch6.exists():
    ch6.unlink()

# ---------------------------------------------------------------- abstract
ABSTRACT = r"""\chapter{Abstract}

Artificial-intelligence drug discovery (AIDD) now generates more candidate targets, molecules and protocols than any single researcher can triage, yet the tools that produce them are disjoint and the reasoning that connects them is rarely auditable. We present MOCHI (Multi-agent Orchestrator for Chemical and biomedical Intelligence), a self-evolving multi-agent system in which a manager, a developer, a critic and a tool-creation agent collaborate over a shared ocean of 46 scientific tools. MOCHI is deliberately scenario-agnostic: four interchangeable stage programs cover (i) downstream effector-target discovery, (ii) structure-guided enzyme variant design, (iii) multi-step retrosynthesis planning and (iv) compilation of wet-lab protocols into validated self-driving-laboratory (SDL) instructions. A deterministic critic audit, a provenance record of every database call and a dual offline/online engine make every run reproducible and inspectable.

On four real tasks MOCHI recovers a Wnt/Notch receptor-class shortlist that motivated the experimental validation of the Wnt co-receptor LRP6, ranks the experimentally validated best strictosidine-synthase variant first out of 2,773 candidates, plans a two-step synthesis of lidocaine and a three-step synthesis of benorilate (all eight benchmark drugs solved), and compiles six clean protocols while catching five of five deliberately corrupted ones. Ablations show that dynamic tool creation is required for the target task and that the experimental prior is required to place the true best variant first. The run artefacts and the command that rebuilds every table and figure are available at \url{https://github.com/simmzx/mochi}, and a single command reproduces the whole suite.

\Keywords{multi-agent systems, AI drug discovery, retrosynthesis, enzyme engineering, laboratory automation, reproducibility}
"""
(TEX / "Abstract.tex").write_text(ABSTRACT, encoding="utf-8")

# ---------------------------------------------------------------- bibliography
BIB = r"""@inproceedings{r01,
  author = {Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and Du, Nan and Shafran, Izhak and Narasimhan, Karthik and Cao, Yuan},
  title = {{ReAct}: Synergizing Reasoning and Acting in Language Models},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2023}
}
@inproceedings{r02,
  author = {Schick, Timo and Dwivedi-Yu, Jane and Dess{\`i}, Roberto and Raileanu, Roberta and Lomeli, Maria and Zettlemoyer, Luke and Cancedda, Nicola and Scialom, Thomas},
  title = {Toolformer: Language Models Can Teach Themselves to Use Tools},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year = {2023}
}
@article{r03,
  author = {M. Bran, Andres and Cox, Sam and Schilter, Oliver and Baldassari, Carlo and White, Andrew D. and Schwaller, Philippe},
  title = {Augmenting large language models with chemistry tools},
  journal = {Nature Machine Intelligence},
  volume = {6},
  pages = {525--535},
  year = {2024}
}
@article{r04,
  author = {Boiko, Daniil A. and MacKnight, Robert and Kline, Ben and Gomes, Gabe},
  title = {Autonomous chemical research with large language models},
  journal = {Nature},
  volume = {624},
  pages = {570--578},
  year = {2023}
}
@inproceedings{r05,
  author = {Roohani, Yusuf and Lee, Andrew and Huang, Qian and Vora, Jian and Steinhart, Zachary and Huang, Kexin and Mars, Peter and Liang, Percy and Leskovec, Jure},
  title = {{BioDiscoveryAgent}: An {AI} Agent for Designing Genetic Perturbation Experiments},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2025}
}
@misc{r06,
  author = {Jin, R. and others},
  title = {{STELLA}: Towards a Biomedical World Model with Self-Evolving Multimodal Agents},
  howpublished = {bioRxiv 2025.07.01.662467},
  year = {2025}
}
@misc{r07,
  author = {Cong, L. and others},
  title = {{LabOS}: The {AI-XR} Co-Scientist That Sees and Works with Humans},
  howpublished = {arXiv:2510.14861},
  year = {2025}
}
@article{r08,
  author = {{The UniProt Consortium}},
  title = {{UniProt}: the universal protein knowledgebase in 2023},
  journal = {Nucleic Acids Research},
  volume = {51},
  pages = {D523--D531},
  year = {2023}
}
@article{r09,
  author = {Ochoa, David and Hercules, Andrew and Carmona, Miguel and Suveges, Daniel and Baker, Jarrod and Malangone, Cinzia and others},
  title = {The next-generation {Open Targets} Platform: reimagined, redesigned, rebuilt},
  journal = {Nucleic Acids Research},
  volume = {51},
  pages = {D1353--D1359},
  year = {2023}
}
@article{r10,
  author = {Cerami, Ethan and Gao, Jianjiong and Dogrusoz, Ugur and Gross, Benjamin E. and Sumer, Selcuk O. and others},
  title = {The {cBioPortal} for Cancer Genomics Opens New Frontiers},
  journal = {Cancer Discovery},
  volume = {2},
  pages = {401--404},
  year = {2012}
}
@article{r11,
  author = {Szklarczyk, Damian and Kirsch, Rebecca and Koutrouli, Mikaela and others},
  title = {The {STRING} database in 2023},
  journal = {Nucleic Acids Research},
  volume = {51},
  pages = {D638--D646},
  year = {2023}
}
@article{r12,
  author = {Del Toro, Noemi and Shrivastava, Anjali and Ragueneau, Eliot and others},
  title = {The {IntAct} database: efficient access to fine-grained molecular interaction data},
  journal = {Nucleic Acids Research},
  volume = {50},
  pages = {D648--D653},
  year = {2022}
}
@article{r13,
  author = {Jumper, John and Evans, Richard and Pritzel, Alexander and others},
  title = {Highly accurate protein structure prediction with {AlphaFold}},
  journal = {Nature},
  volume = {596},
  pages = {583--589},
  year = {2021}
}
@inproceedings{r14,
  author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and others},
  title = {Attention Is All You Need},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year = {2017}
}
@article{r15,
  author = {Henikoff, Steven and Henikoff, Jorja G.},
  title = {Amino acid substitution matrices from protein blocks},
  journal = {Proceedings of the National Academy of Sciences},
  volume = {89},
  pages = {10915--10919},
  year = {1992}
}
@article{r16,
  author = {Kyte, Jack and Doolittle, Russell F.},
  title = {A simple method for displaying the hydropathic character of a protein},
  journal = {Journal of Molecular Biology},
  volume = {157},
  pages = {105--132},
  year = {1982}
}
@article{r17,
  author = {Chen, R. and others},
  title = {Enzyme engineering for alkaloid biosynthesis},
  journal = {Current Opinion in Biotechnology},
  year = {2021}
}
@article{r18,
  author = {Segler, Marwin H. S. and Preuss, Mike and Waller, Mark P.},
  title = {Planning chemical syntheses with deep neural networks and symbolic {AI}},
  journal = {Nature},
  volume = {555},
  pages = {604--610},
  year = {2018}
}
@article{r19,
  author = {Coley, Connor W. and Thomas, Dale A. and Lummiss, Justin A. M. and others},
  title = {A robotic platform for flow synthesis of organic compounds informed by {AI} planning},
  journal = {Science},
  volume = {365},
  pages = {eaax1566},
  year = {2019}
}
@misc{r20,
  author = {Landrum, Greg},
  title = {{RDKit}: Open-Source Cheminformatics Software},
  howpublished = {\url{https://www.rdkit.org}},
  year = {2024}
}
@article{r21,
  author = {Kim, Sunghwan and Chen, Jie and Cheng, Tiejun and others},
  title = {{PubChem} 2023 update},
  journal = {Nucleic Acids Research},
  volume = {51},
  pages = {D1373--D1380},
  year = {2023}
}
@article{r22,
  author = {Cock, Peter J. A. and Antao, Tiago and Chang, Jacek T. and others},
  title = {{Biopython}: freely available {Python} tools for computational molecular biology},
  journal = {Bioinformatics},
  volume = {25},
  pages = {1422--1423},
  year = {2009}
}
"""
(TEX / "Bibliography.bib").write_text(BIB, encoding="utf-8")

# ---------------------------------------------------------------- main.tex
MAIN = r"""\documentclass[Thesis,Final,NoHardback]{mpThesis}

\usepackage{longtable}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{siunitx}
\usepackage{graphicx}
\usepackage{float}
\usepackage{tabularx}
\usepackage{array}
\usepackage[final]{microtype}
\setlength{\emergencystretch}{3em}
\let\cleardoublepage\clearpage
\geometry{left=22mm,right=22mm,top=24mm,bottom=24mm,heightrounded}
\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=black,citecolor=black}
\captionsetup[table]{justification=raggedright,singlelinecheck=false}
\captionsetup[figure]{justification=raggedright,singlelinecheck=false}
% keep table/figure numbers continuous so the in-text references (Table 1 ... Table 12)
% match the captions exactly
\counterwithout{table}{chapter}
\counterwithout{figure}{chapter}
\renewcommand{\thetable}{\arabic{table}}
\renewcommand{\thefigure}{\arabic{figure}}
\renewcommand{\labelitemi}{\textbullet}

\StudentName{ZHANG XIANG}
\StudentNumber{P2600300}
\AcademicUnit{Faculty of Applied Sciences}
\Programme[Doctor of Philosophy in Artificial Intelligence Driven Drug Discovery]{Doctor of Philosophy in Artificial Intelligence Driven Drug Discovery}
\Supervisor{\textemdash}
\Cosupervisor{\textemdash}

\Title[MOCHI: A Self-Evolving Multi-Agent System for End-to-End AI Drug Discovery]{MOCHI: A Self-Evolving Multi-Agent System for End-to-End AI Drug Discovery}
\ThesisNumber{0000}{AIDD}{FCA}{zhang}{mochi}
\ThesisKeywords{multi-agent systems, AI drug discovery, retrosynthesis, enzyme engineering, laboratory automation}
\Date{2026-11-16}

\begin{document}
\nocite{r01,r02,r03,r04,r05,r06,r07,r08,r09,r10,r11,r12,r13,r14,r15,r16,r17,r18,r19,r20,r21,r22}

\begin{FrontMatter}[FigLs=false,TabLs=false,AbbreLs=false]
\input{Abstract.tex}
\end{FrontMatter}

\begin{MainMatter}
\input{chapters/Chapter1.tex}
\input{chapters/Chapter2.tex}
\input{chapters/Chapter3.tex}
\input{chapters/Chapter4.tex}
\input{chapters/Chapter5.tex}
\end{MainMatter}

\begin{BackMatter}
\bibliographystyle{mpUnsrt.bst}
\bibliography{Bibliography.bib}
\end{BackMatter}

\begin{Appendix}
\input{chapters/AppendixA.tex}
\end{Appendix}

\end{document}
"""
(TEX / "main.tex").write_text(MAIN, encoding="utf-8")

# declaration (template copy)
(TEX / "chapters" / "Declaration.tex").write_text((TPL / "Declaration.tex").read_text(encoding="utf-8"),
                                                 encoding="utf-8")

print("project assembled in", TEX)
