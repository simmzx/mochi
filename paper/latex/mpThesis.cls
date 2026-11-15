%%
%% MPU Doctoral Thesis Class
%% by Ka-Hou Chan and Wei Ke
%%

\NeedsTeXFormat{LaTeX2e}
\gdef\mp@thesis@class@version{6.1} % 2023-04-03
\gdef\mp@thesis@class@disp@code{MPU Thesis Template v\mp@thesis@class@version}
\ProvidesClass{mpThesis}[MPU Doctoral Thesis Class, Version \mp@thesis@class@version]

\gdef\NoCM{\let\IfCM\iffalse}
\gdef\NoTimes{\let\IfTimes\iffalse}
\gdef\NoUtopia{\let\IfUtopia\iffalse}
\gdef\NoGaramond{\let\IfGaramond\iffalse}
\gdef\NoPalatino{\let\IfPalatino\iffalse}
\gdef\NoLibertine{\let\IfLibertine\iffalse}

\NoCM
\NoTimes
\NoUtopia
\NoGaramond
\NoPalatino
\let\IfLibertine\iftrue % default
\DeclareOption{CM}{\let\IfCM\iftrue}
\DeclareOption{Times}{\let\IfTimes\iftrue}
\DeclareOption{Utopia}{\let\IfUtopia\iftrue}
\DeclareOption{Garamond}{\let\IfGaramond\iftrue}
\DeclareOption{Palatino}{\let\IfPalatino\iftrue}
\DeclareOption{Libertine}{\let\IfLibertine\iftrue}

\let\IfPCAT\iffalse
\DeclareOption{PCAT}{\let\IfPCAT\iftrue}
\DeclareOption{PCOM}{\let\IfPCAT\iftrue}

\let\IfThesis\iftrue % default
\DeclareOption{Thesis}{\let\IfThesis\iftrue}
\DeclareOption{Proposal}{\let\IfThesis\iffalse}

\let\IfReview\iftrue % default
\DeclareOption{Review}{\let\IfReview\iftrue}
\DeclareOption{Final}{\let\IfReview\iffalse}

\let\IfHardback\iffalse % default
\DeclareOption{Hardback}{\let\IfHardback\iftrue}
\DeclareOption{NoHardback}{\let\IfHardback\iffalse}

\let\IfOneHalfSpacing\iftrue
\DeclareOption{OneHalfSpacing}{\let\IfOneHalfSpacing\iftrue}
\DeclareOption{DoubleSpacing}{\let\IfOneHalfSpacing\iffalse}

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{book}}
\ProcessOptions

\IfCM
  \NoTimes
  \NoUtopia
  \NoGaramond
  \NoPalatino
  \NoLibertine
\fi

\IfTimes
  \NoCM
  \NoUtopia
  \NoGaramond
  \NoPalatino
  \NoLibertine
\fi

\IfUtopia
  \NoCM
  \NoTimes
  \NoGaramond
  \NoPalatino
  \NoLibertine
\fi

\IfGaramond
  \NoCM
  \NoTimes
  \NoUtopia
  \NoPalatino
  \NoLibertine
\fi

\IfPalatino
  \NoCM
  \NoTimes
  \NoUtopia
  \NoGaramond
  \NoLibertine
\fi

\IfLibertine
  \NoCM
  \NoTimes
  \NoUtopia
  \NoGaramond
  \NoPalatino
\fi

\LoadClass[12pt,a4paper]{book}

\newcommand\hide[1]{}

\RequirePackage[left=40mm, right=25mm, top=25mm, bottom=25mm, heightrounded]{geometry}

\RequirePackage[T1]{fontenc}
\RequirePackage{amsmath,amsthm,amssymb}
\RequirePackage{mathtools}
\RequirePackage{array}
\RequirePackage{bm}

\IfTimes
  \RequirePackage{newtxtext,newtxmath}
\fi

\IfUtopia
  \RequirePackage{utopia}
  \RequirePackage[utopia]{newtxmath}
\fi

\IfPalatino
  \RequirePackage{mathpazo}
\fi

\IfGaramond
  \RequirePackage{ebgaramond}
  \RequirePackage[cmintegrals,cmbraces]{newtxmath}
  \RequirePackage{ebgaramond-maths}
  \DeclareSymbolFont{ntxletters}{OML}{ntxmi}{m}{it}
  \SetSymbolFont{ntxletters}{bold}{OML}{ntxmi}{b}{it}
  \re@DeclareMathSymbol{\leftharpoonup}{\mathrel}{ntxletters}{"28}
  \re@DeclareMathSymbol{\leftharpoondown}{\mathrel}{ntxletters}{"29}
  \re@DeclareMathSymbol{\rightharpoonup}{\mathrel}{ntxletters}{"2A}
  \re@DeclareMathSymbol{\rightharpoondown}{\mathrel}{ntxletters}{"2B}
  \re@DeclareMathSymbol{\triangleleft}{\mathbin}{ntxletters}{"2F}
  \re@DeclareMathSymbol{\triangleright}{\mathbin}{ntxletters}{"2E}
  \re@DeclareMathSymbol{\partial}{\mathord}{ntxletters}{"40}
  \re@DeclareMathSymbol{\flat}{\mathord}{ntxletters}{"5B}
  \re@DeclareMathSymbol{\natural}{\mathord}{ntxletters}{"5C}
  \re@DeclareMathSymbol{\star}{\mathbin}{ntxletters}{"3F}
  \re@DeclareMathSymbol{\smile}{\mathrel}{ntxletters}{"5E}
  \re@DeclareMathSymbol{\frown}{\mathrel}{ntxletters}{"5F}
  \re@DeclareMathSymbol{\sharp}{\mathord}{ntxletters}{"5D}
  \re@DeclareMathAccent{\vec}{\mathord}{ntxletters}{"7E}
\fi

\IfLibertine
  \RequirePackage{libertine}
  \RequirePackage[libertine]{newtxmath}
\fi

\RequirePackage[dvipsnames,x11]{xcolor}
\definecolor{MPUGreen}{HTML}{046A38}

\RequirePackage[switch]{lineno}
\IfReview
  \RequirePackage[colorlinks]{hyperref}
  \hypersetup{
    citecolor = SeaGreen,
    filecolor = NavyBlue,
    urlcolor  = NavyBlue,
  }
\else
  \RequirePackage[hidelinks]{hyperref}
\fi

\RequirePackage{tabu,booktabs}
\RequirePackage{multirow,multicol}

\RequirePackage{wrapfig}
\RequirePackage{eso-pic,graphicx}
\RequirePackage{caption,subcaption}

\RequirePackage{minitoc}
\let\orig@minitoc\minitoc
\renewcommand{\minitoc}{{\nolinenumbers\singlespacing\orig@minitoc}}

\RequirePackage[style=long4col,toc,automake]{glossaries}
\makeglossaries
\newglossaryentry{MPU}{name={MPU}, description={Macao Polytechnic University}}
\newglossaryentry{MPI}{name={MPI}, description={Macao Polytechnic Institute}}

\RequirePackage[noindentafter]{titlesec}
\RequirePackage{titletoc}
\RequirePackage{tocbibind}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{2}
\setcounter{minitocdepth}{3}
\RequirePackage{notoccite}

\RequirePackage{setspace}
\RequirePackage{fancyhdr}
\RequirePackage{etoolbox}

\RequirePackage{stmaryrd}
\RequirePackage{marvosym}
\RequirePackage{enumitem}
\RequirePackage[en-GB,calc]{datetime2}
\RequirePackage{varwidth}
\RequirePackage{keyval}
\RequirePackage{qrcode}

%%
%% commands to define variables
%%

\newcommand{\StudentName}[2][]{%
  \gdef\mp@student@name{#2}\author{#2}%
  \ifstrempty{#1}{\gdef\mp@student@name@break{#2}}{\xdef\mp@student@name@break{#1}}%
}
\newcommand{\StudentNumber}[1]{\gdef\mp@student@number{#1}}
\newcommand{\AcademicUnit}[1]{\gdef\mp@academic@unit{#1}}
\newcommand{\Programme}[2][]{%
  \gdef\mp@programme{#2}%
  \ifstrempty{#1}{\gdef\mp@programme@break{#2}}{\xdef\mp@programme@break{#1}}%
}
\newcommand{\Cosupervisor}[1]{\gdef\mp@cosupervisor{#1}}
\newcommand{\Supervisor}[1]{\gdef\mp@supervisor{#1}}
\newcommand{\Date}[1]{\DTMsavedate{mp@date}{#1}}
\newcommand{\DateToday}{%
  \DTMsavenow{mp@date}%
  \DTMsavenow{mp@defence@datetime}%
}
\newcommand{\DefenceDateTime}[2]{%
  \DTMsavedate{mp@defence@datetime}{#1}%
  \DTMsavetime{mp@defence@datetime}{#2}%
}

\newcommand{\Title}[2][]{%
  \gdef\mp@title{#2}\title{#2}%
  \ifstrempty{#1}{\gdef\mp@title@break{#2}}{\gdef\mp@title@break{{\def\\{\hfil\break}#1}}}%
}

\newcommand{\ThesisNumber}[5]{%
  \IfThesis\gdef\mp@thesis@number@ty{TH}\else\gdef\mp@thesis@number@ty{RP}\fi%
  \gdef\mp@thesis@number@seq{#1}%
  \gdef\mp@thesis@number@prg{#2}%
  \gdef\mp@thesis@number@acu{#3}%
  \lowercase{\gdef\mp@thesis@number@acu@lo{#3}}%
  \gdef\mp@thesis@number@lna{#4}%
  \gdef\mp@thesis@number@ftw{#5}%
}

\newcommand{\ThesisKeywords}[1]{\gdef\mp@thesis@keywords{#1}}

\newcommand{\PanelChair}[1]{\gdef\mp@panel@chair{#1}}
\newcommand{\PanelExternal}[1]{\gdef\mp@panel@external{#1}}
\newcommand{\PanelExaminer}[1]{\gdef\mp@panel@examiner{#1}}
\newcommand{\PanelExaminerA}[1]{\gdef\mp@panel@examiner@a{#1}}
\newcommand{\PanelExaminerB}[1]{\gdef\mp@panel@examiner@b{#1}}

\newcommand{\InsertThesisType}{\IfThesis{Thesis}\else{Research Proposal}\fi}
\newcommand{\InsertStudentName}{\mp@student@name}
\newcommand{\InsertStudentNameBreak}{\mp@student@name@break}
\newcommand{\InsertStudentNumber}{\mp@student@number}
\newcommand{\InsertAcademicUnit}{\mp@academic@unit}
\newcommand{\InsertProgramme}{\mp@programme}
\newcommand{\InsertProgrammeBreak}{\mp@programme@break}
\newcommand{\InsertCosupervisor}{\mp@cosupervisor}
\newcommand{\InsertSupervisor}{\mp@supervisor}
\newcommand{\InsertDefenceDate}{\DTMsetstyle{en-GB}\DTMlangsetup{showdayofmonth=true,ord=raise}\DTMusedate{mp@defence@datetime}}
\newcommand{\InsertDefenceTime}{\DTMsettimestyle{default}\DTMsetup{showseconds=false}\DTMusetime{mp@defence@datetime}}
\newcommand{\InsertLongDate}{\DTMsetstyle{en-GB}\DTMlangsetup{showdayofmonth=true,ord=raise}\DTMusedate{mp@date}}
\newcommand{\InsertMonthYear}{\DTMsetstyle{en-GB}\DTMlangsetup{showdayofmonth=false}\DTMusedate{mp@date}}
\newcommand{\InsertYear}{\DTMfetchyear{mp@date}}
\newcommand{\InsertDate}{\DTMsetstyle{default}\DTMusedate{mp@date}}
\newcommand{\InsertTitle}{\mp@title}
\newcommand{\InsertTitleBreak}{\mp@title@break}
\newcommand{\InsertThesisNumber}{\mp@thesis@number@ty\mp@thesis@number@seq/\mp@thesis@number@prg/\mp@thesis@number@acu/\InsertYear}
\newcommand{\InsertThesisNumberBreak}{\mp@thesis@number@ty\mp@thesis@number@seq/\mp@thesis@number@prg\linebreak\mp@thesis@number@acu/\InsertYear}
\newcommand{\InsertThesisNumberStyle}{{\small\fontfamily{zi4}\selectfont\InsertThesisNumber}}
\newcommand{\InsertThesisNumberBreakStyle}{{\small\fontfamily{zi4}\selectfont\InsertThesisNumberBreak}}
\newcommand{\InsertThesisUrl}{https://\mp@thesis@number@acu@lo.mpu.edu.mo/doc-db?%
  ty=\mp@thesis@number@ty\&%
  seq=\mp@thesis@number@seq\&%
  prg=\mp@thesis@number@prg\&%
  acu=\mp@thesis@number@acu\&%
  year=\InsertYear\&%
  lna=\mp@thesis@number@lna\&%
  ftw=\mp@thesis@number@ftw%
}
\newcommand{\InsertThesisKeywords}{\mp@thesis@keywords}
\newcommand{\InsertPanelChair}{\mp@panel@chair}
\newcommand{\InsertPanelExternal}{\mp@panel@external}
\newcommand{\InsertPanelExaminer}{\mp@panel@examiner}
\newcommand{\InsertPanelExaminerA}{\mp@panel@examiner@a}
\newcommand{\InsertPanelExaminerB}{\mp@panel@examiner@b}

\StudentName[<<Student Name>>]{<<Student Name>>}
\StudentNumber{<<Student Number>>} %P-XX-XXXX-X
\AcademicUnit{<<Academic Unit>>} %Faculty of Applied Sciences
\Programme[<<Programme>>]{<<Programme>>} %Doctor of Philosophy in Computer Applied Technology
\Supervisor{<<Supervisor>>}
\Cosupervisor{<<Co-supervisor>>}
\DateToday

\Title{<<Title>>}
\ThesisNumber{0000}{PCOM}{FCA}{lastname}{titlefirst}
\ThesisKeywords{}
\Date{9999-01-02} %Submission Date

\DefenceDateTime{9999-01-02}{23:59:00} %Defence Date and Time YYYY-MM-DD, hh:mm:ss
\PanelChair{<<Chair>>}
\PanelExternal{<<External>>}
\PanelExaminer{<<Examiner>>}
\PanelExaminerA{<<Examiner A>>}
\PanelExaminerB{<<Examiner B>>}

\IfPCAT
  \AcademicUnit{Faculty of Applied Sciences}
  \Programme%
    [Doctor of Philosophy in\\Computer Applied Technology]%
    {Doctor of Philosophy in Computer Applied Technology}
\fi

%%
%% emphasize bib names
%%

\newcommand{\EmphasizeAuthors}[1]{\nocite{#1}}

%%
%% redefine font sizes
%%

%\renewcommand{\huge}{\fontsize{22}{22}\selectfont}
%\renewcommand{\LARGE}{\fontsize{18}{18}\selectfont}
%\renewcommand{\Large}{\fontsize{16}{16}\selectfont}
%\renewcommand{\large}{\fontsize{14}{14}\selectfont}
%\renewcommand{\small}{\fontsize{10}{10}\selectfont}
%\renewcommand{\footnotesize}{\fontsize{8}{8}\selectfont}
%\renewcommand{\scriptsize}{\fontsize{6}{6}\selectfont}

%%
%% redefine cross-reference prefix
%%

\def\equationautorefname~#1\null{(#1)\null}
\def\chapterautorefname{Chapter}
\def\sectionautorefname{Section}
\def\subsectionautorefname{\sectionautorefname}
\def\subsubsectionautorefname{\sectionautorefname}
\def\figureautorefname{Figure}
\def\tableautorefname{Table}
\def\algorithmautorefname{Algorithm}

%%
%% format section titles
%%

\titlespacing{\chapter}{0pt}{-2.5em}{1.5em}
\titleformat{\section}{\Large}{\thesection}{2ex}{\sc}
\titleformat{\subsection}{\large\it}{\thesubsection}{1ex}{}
\titleformat{\chapter}[display]{\doublespacing\filcenter\LARGE\scshape}{\chaptertitlename~\thechapter.}{0ex}{\bf\MakeUppercase}

%%
%% Hardback
%%
\newcommand{\HardbackFontStyle}{\fontfamily{ntxtlf}\selectfont\bfseries\large}
\newcommand{\MakeHardback}{%
%%
%%
\vspace*{0.25in}
\begin{center}
\includegraphics[width=0.5\linewidth]{MPU-Logo-BW.pdf}
\vfill
{\HardbackFontStyle\InsertTitle}
\vfill
{\HardbackFontStyle\InsertStudentName}
\vspace*{1.0in}
\end{center}
\cleardoublepage

\singlespacing
\newgeometry{left=40mm, right=25mm, top=20mm, bottom=20mm}
\setbox0\hbox{f}% use the current font to measure the top-baseline height
\centerline{%
\raisebox{\ht0}{% lift the box from baseline to top
\rotatebox[origin=c]{-90}{\HardbackFontStyle% the relative box height is [297 (A4 paperheight) - 20x2]/paperheight = 0.865
\begin{tabular}{
  @{}
  >{\raggedright\arraybackslash}m{0.40\paperheight}
  @{}
  >{\raggedleft\arraybackslash}m{0.315\paperheight}
  @{}
  >{\raggedleft\arraybackslash}m{0.15\paperheight}
  @{}
}
\InsertTitleBreak & \InsertStudentName & \InsertYear
\end{tabular}%
}}}
\restoregeometry
\cleardoublepage
%%
%%
\null
\clearpage
\AddToShipoutPictureBG*{
	\hspace*{15cm}
	\rotatebox[y=0.5\paperheight]{-90}{
		\includegraphics[width=0.98\paperheight]{MPU-calligraphy-ol.pdf}
	}
}
\cleardoublepage
%%
%%
}%% end of \MakeHardback

%%
%% Cover Page
%%
\newcommand{\MakeCover}{%
%%
%%
\begin{center}
\includegraphics[width=0.6\linewidth]{MPU-Logo.pdf}
\vfill
{\Large\bf\InsertAcademicUnit}
\vfill
{\large\bf\InsertTitle}
\vfill
\large\InsertStudentName, \InsertStudentNumber
\vfill
{\it
\InsertProgramme \\
AIDD8122 -- Advanced Topics in Artificial Intelligence \& Drug Discovery \\
Final Project Report
}
\vfill
\InsertMonthYear
\end{center}%
%%
%%
}%% end of \MakeCover

\newlength{\left@col@width}
\newlength{\left@col@maxwidth}
\newlength{\name@col@width}
\newlength{\name@col@maxwidth}

%%
%% Copyright Page
%%
\newcommand{\MakeCopyright}{%
%%
%%
\noindent%
\begin{minipage}[t]{0.45\textwidth}
\vspace{0pt}%
\raggedright\InsertThesisNumberStyle%
\end{minipage}%
\hfill%
\begin{minipage}[t]{0.45\textwidth}
\vspace{0pt}%
\raggedleft\qrcode[hyperlink,height=1in]{\InsertThesisUrl}%
\end{minipage}

\vspace{-0.25in}%

\begin{center}
\singlespacing
\begin{tabular}{c|c}
\begin{minipage}[c]{0.465\linewidth}{
~\\
\includegraphics[width=\linewidth]{MPU-Logo-CPE.pdf}
\\
}\end{minipage}
&
\begin{minipage}[c]{0.465\linewidth}{
{\large\bf\InsertAcademicUnit}
}\end{minipage}
\end{tabular}

\vspace*{0.25in}

%%
\def\left@programme{Programme}
\def\left@thesis{\InsertThesisType}
\def\left@student@name{Name}
\def\left@student@number{Student Number}
\def\left@supervisor{Supervisor}
\def\left@cosupervisor{Co-supervisor}
\def\left@chair{Chair}
\def\left@examiners{\IfThesis{Examiners}\else{Examiner}\fi}
\def\left@defence@date{\IfThesis{Oral Defence Date}\else{Examination Date}\fi}
\def\left@defence@time{Time}
\def\left@signatures{Signatures}
\def\left@date{Date}
\setlength{\left@col@maxwidth}{0.39\linewidth}
%%
\setlength{\left@col@width}{\widthof{%
\begin{varwidth}{\left@col@maxwidth}
\raggedleft%
{\it\left@programme}\\
{\it\left@thesis}\\
{\it\left@student@name}\\
{\it\left@student@number}\\
{\it\left@supervisor}\\
{\it\left@cosupervisor}\\
{\it\left@defence@date}\\
{\it\left@defence@time}\\
{\it\left@chair}\\
{\it\left@examiners}\\
{\it\left@signatures}\\
{\it\left@date}\\
\end{varwidth}}}
\setlength{\name@col@width}{0.60\linewidth}
%%

\onehalfspacing
\renewcommand\arraystretch{1.125}
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@programme & \InsertProgrammeBreak \\
\cline{2-2}
\end{tabular}
\vfill
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@thesis & \InsertTitleBreak \\
\cline{2-2}
\left@student@name & \InsertStudentName \\
\cline{2-2}
\left@student@number & \InsertStudentNumber \\
\cline{2-2}
\left@supervisor & \InsertSupervisor \\
\cline{2-2}
\left@cosupervisor & \InsertCosupervisor \\
\cline{2-2}
\end{tabular}
\vfill
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@defence@date & \InsertDefenceDate \\
\cline{2-2}
\left@defence@time & \InsertDefenceTime \\
\cline{2-2}
\left@chair & \InsertPanelChair \\
\cline{2-2}
\IfThesis
  \left@examiners & \InsertPanelExternal \\
  \cline{2-2}
  & \InsertPanelExaminerA \\
  \cline{2-2}
  & \InsertPanelExaminerB \\
  \cline{2-2}
\else
  \left@examiners & \InsertPanelExaminer \\
\fi
\end{tabular}
\vfill
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@signatures &  \\[-1ex]
\cline{2-2}
& (\InsertStudentName) \\[3ex]
&  \\[-1ex]
\cline{2-2}
& (\InsertSupervisor) \\
\end{tabular}
\vfill
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@date & \InsertLongDate \\
\cline{2-2}
\end{tabular}

\vspace{0.125in}
{\it Copyright \copyright{} \InsertStudentName, \InsertYear.}
\end{center}
%%
%%
}%% end of \MakeCopyright

%%
%% Title Page
%%
\newcommand{\MakeTitle}{%
%%
%%
\setlength{\name@col@maxwidth}{0.4\linewidth}
%%
\setlength{\name@col@width}{\widthof{%
\begin{varwidth}{\name@col@maxwidth}
\InsertStudentNameBreak\\
\InsertStudentNumber\\
\InsertAcademicUnit\\
\InsertProgrammeBreak\\
\InsertSupervisor\\
\InsertCosupervisor\\
\end{varwidth}}}
%%
\def\left@student@name{Name}
\def\left@student@number{Student Number}
\def\left@academic@unit{Academic Unit}
\def\left@programme{Programme}
\def\left@supervisor{Supervisor}
\def\left@cosupervisor{Co-supervisor}
%\def\left@mp@submission@date{Submission Date}
%\def\left@mp@defence@date{Defence Date}
\def\left@date{Date}
\setlength{\left@col@maxwidth}{0.4\linewidth}
%%
\setlength{\left@col@width}{\widthof{%
\begin{varwidth}{\left@col@maxwidth}
\raggedleft%
{\it\left@student@name}\\
{\it\left@student@number}\\
{\it\left@academic@unit}\\
{\it\left@programme}\\
{\it\left@supervisor}\\
{\it\left@cosupervisor}\\
{\it\left@date}
\end{varwidth}}}
%%

\begin{center}
\includegraphics{MPU-Logo-green-small.pdf}

\vspace*{1in}
{\Large\sc\InsertThesisType}%
\vfill
{\Large \InsertTitle}
\vfill
\onehalfspacing
\renewcommand\arraystretch{1.275}
\hspace*{\name@col@width-\left@col@width}
\begin{tabular}{
  >{\it\raggedleft\arraybackslash}b{\left@col@width}|
  >{\raggedright\arraybackslash}b{\name@col@width}
}
\left@student@name & {\mp@student@name@break} \\
\hline
\left@student@number & \InsertStudentNumber \\
\hline
\left@academic@unit & \InsertAcademicUnit \\
\hline
\left@programme & {\mp@programme@break} \\
\hline
\left@supervisor & \InsertSupervisor \\
\hline
\left@cosupervisor & \InsertCosupervisor \\
\hline
\left@date & \InsertLongDate
\end{tabular}
\end{center}%
%%
%%
}%% end of \MakeTitle

%%
%% MPU calligraphy
%%

\newsavebox{\mp@calligraphy@box}
\sbox{\mp@calligraphy@box}{\raisebox{-0.225\headheight}[0pt][0pt]{\includegraphics[height=\headheight]{MPU-calligraphy.pdf}}}
\gdef\mp@calligraphy{\usebox{\mp@calligraphy@box}}

%%
%% begin document
%%

\AtBeginDocument{%
%%
%%
\hypersetup{
  pdftitle={\InsertTitle},
  pdfauthor={\InsertStudentName},
  pdfsubject={\InsertProgramme, \InsertThesisType},
  pdfkeywords={\InsertThesisKeywords}
}
%%
\appto\appendix{\addtocontents{toc}{\gdef\protect\@chapapp{\protect\appendixname}}}
\appto\contentsfinish{\gdef\@chapapp{\chaptername}}
\titlecontents{chapter}[0pt]{\addvspace{1.0pc}}{\bf\chaptertitlename~\thecontentslabel.\quad}{\bf}{\hfill\contentspage}

\DeclareRobustCommand{\template@mark}{\makebox[0pt][l]{\hspace*{-1.75cm}\sffamily\scriptsize\color{SeaGreen}\raisebox{-0.85cm}{\mp@thesis@class@disp@code}}}

\fancypagestyle{cover}{
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[LE]{\template@mark}%
}

\fancypagestyle{empty}{
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[LE]{\IfReview\template@mark\fi}%
}

\begin{titlepage}
\pagestyle{cover}
\doublespacing\MakeCover
\end{titlepage}
\clearpage

\fancypagestyle{plain}{
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\thepage}%
\fancyfoot[LE]{\IfReview\template@mark\fi}%
}

\pagestyle{fancy}

\fancyhf{}

\fancyhead[LE]{}
\fancyhead[CE]{\small\sc\nouppercase\leftmark}
\fancyhead[RE]{}
\fancyhead[LO]{\mp@calligraphy}
\fancyhead[CO]{}
\fancyhead[RO]{\small\sc\nouppercase\rightmark}

\fancyfoot[C]{\small\thepage}%
\fancyfoot[LE]{\IfReview\template@mark\fi}%
%%
%%
}%% end of \AtBeginDocument

\newcommand{\Keywords}[1]{\par\noindent{\bfseries\itshape Keywords} --- #1}

%%
%% document parts (matters)
%%

\let\IfFigureList\iftrue
\define@key{FrontMatter}{FigLs}[true]{\ifstrequal{#1}{true}{\let\IfFigureList\iftrue}{\let\IfFigureList\iffalse}}
\let\IfTableList\iftrue
\define@key{FrontMatter}{TabLs}[true]{\ifstrequal{#1}{true}{\let\IfTableList\iftrue}{\let\IfTableList\iffalse}}
\let\IfAlgorithmList\iffalse
\define@key{FrontMatter}{AlgoLs}[true]{\ifstrequal{#1}{true}{\let\IfAlgorithmList\iftrue}{\let\IfAlgorithmList\iffalse}}
\let\IfAbbreviationList\iftrue
\define@key{FrontMatter}{AbbreLs}[true]{\ifstrequal{#1}{true}{\let\IfAbbreviationList\iftrue}{\let\IfAbbreviationList\iffalse}}

\newenvironment{FrontMatter}[1][]{%
%%
%%
\setkeys{FrontMatter}{#1}%

\dominitoc

\frontmatter
%%
%%
\pagenumbering{roman}
\renewcommand{\chaptermark}[1]{\markboth{##1}{}}
\renewcommand{\contentsname}{Table of Contents}
\doublespacing
%%
%%
}{
%%
%%
\onehalfspacing
\tableofcontents\markboth{\contentsname}{}%
\IfFigureList%
  \listoffigures\adjustmtc
\fi%
\IfTableList%
  \listoftables\adjustmtc
\fi%
\IfAlgorithmList%
  \listofalgorithms\addcontentsline{toc}{chapter}{\listalgorithmname}\markboth{\listalgorithmname}{}\adjustmtc
\fi%
\IfAbbreviationList%
  \printglossary[nopostdot,nonumberlist,title={List of Abbreviations}]\adjustmtc
\fi%
\mtcfixglossary%
%%
%%
}%% end of FrontMatter

\newenvironment{MainMatter}{%
%%
%%
\mainmatter
%%
%%
\IfReview%
  \renewcommand\linenumberfont{\normalfont\footnotesize\color{magenta}}%
  \linenumbers%
%  \setpagewiselinenumbers%
\fi%
%%
%%
\pagenumbering{arabic}
\IfOneHalfSpacing%
  \onehalfspacing%
\else%
  \doublespacing%
\fi%
%%
%%
}{
%%
%%
}%% end of MainMatter

\newenvironment{BackMatter}{%
%%
%%
\backmatter
%%
%%
\renewcommand{\chaptermark}[1]{\markboth{##1}{}}
\onehalfspacing
%%
%%
}{
%%
%%
}%% end of BackMatter

\newenvironment{Appendix}{
%%
%%
\appendix
\onehalfspacing
%%
%%
}{
%%
%%
}%% end of Appendix



\endinput
