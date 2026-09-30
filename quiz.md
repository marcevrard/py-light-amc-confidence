---
pagetitle: "Scannable quiz with certainty degrees"
lang: en
documentclass: article
classoption: [a4paper, 11pt]
geometry: [margin=2cm]
header-includes:
  - |
    ```{=latex}
    \usepackage[T1]{fontenc}
    \usepackage[table]{xcolor}
    \usepackage{array,amssymb,fancyhdr,titlesec,eso-pic,tikz}
    \definecolor{smart}{HTML}{E5543B}
    \definecolor{paper}{HTML}{F4F4F0}
    \pagestyle{fancy}\fancyhf{}
    \renewcommand{\headrulewidth}{0.6pt}
    \fancyhead[L]{\small\textbf{SMART}-style quiz}
    \fancyhead[R]{\small Certainty degrees}
    \titleformat{\section}{\large\bfseries\color{smart}}{}{0pt}{}
    \titlespacing*{\section}{0pt}{1.4em}{.5em}
    \setlength{\parindent}{0pt}
    \renewcommand{\arraystretch}{1.35}
    \newcommand{\code}[1]{\textbf{\textcolor{smart}{#1}}}
    \newcommand{\opt}[2]{\hspace{2em}\textbf{#1}\,#2}
    %% =====================================================================
    %% SCANNABLE ANSWER SHEET. All coordinates are in millimetres from the
    %% TOP-LEFT corner of the A4 page. smart_scan_reader.py uses the same
    %% numbers: if you move anything here, change the constants there too.
    %%   registration marks : 6 mm squares centred on (10,10) (200,10) (10,287) (200,287)
    %%   student ID bubbles : x = 50 + 10*i (i=0..7), y = 68 + 6*d (d=0..9)
    %%   answer bubbles     : x = 42 + 9*k, codes 1 2 3 4 6 7
    %%   certainty bubbles  : x = 112 + 9*j, DC 0..5
    %%   row of question q  : y = 146 + 22*q (first line), +9 (correction line)
    %% Bubble radius 2 mm.
    %% =====================================================================
    \newcommand{\bub}[2]{\draw[line width=.4pt] (#1,#2) circle[radius=2mm];}
    \newcommand{\sheet}{%
    \begin{tikzpicture}[overlay,x=1mm,y=-1mm,every node/.style={font=\sffamily}]
      % registration marks
      \foreach \px/\py in {10/10,200/10,10/287,200/287}{\fill[black] (\px-3,\py-3) rectangle (\px+3,\py+3);}
      % title and name
      \node[font=\sffamily\bfseries\Large] at (105,20) {Answer sheet};
      \node[font=\sffamily\footnotesize,gray] at (105,27) {Fill the bubbles completely, with a dark pen. Do not fold.};
      \draw[smart,fill=paper] (20,32) rectangle (190,44);
      \node[anchor=west,font=\sffamily\small\bfseries] at (22,38) {Name and first name:};
      \node[anchor=west,font=\sffamily\small\bfseries] at (140,38) {Date:};
      % student ID
      \node[anchor=west,font=\sffamily\small\bfseries,text=smart] at (20,50) {Student ID (8 digits)};
      \foreach \i in {0,...,7}{
        \draw (50+10*\i-3.5,53) rectangle (50+10*\i+3.5,60);
        \foreach \d in {0,...,9}{ \bub{50+10*\i}{68+6*\d} }
      }
      \foreach \d in {0,...,9}{ \node[font=\sffamily\scriptsize] at (40,68+6*\d) {\d}; }
      \draw[smart] (45,64.5) -- (125,64.5);
      % instructions box
      \node[anchor=north west,text width=52mm,font=\sffamily\scriptsize,align=left] at (135,54)
        {\textbf{Student ID:} write your 8 digits in the boxes, then fill one bubble per column.\\[2mm]
         \textbf{Answers:} one bubble per line for the answer (1--4, 6 = none, 7 = all) and one for the certainty (DC 0--5).\\[2mm]
         \textbf{Changing your mind:} fill the \emph{second line} of the question. It replaces the first line. Only one change is allowed.\\[2mm]
         \textbf{Do not} erase or use correction fluid on the first line.};
      % answer grid header
      \node[font=\sffamily\small\bfseries,text=smart] at (63.5,132) {Answer};
      \node[font=\sffamily\small\bfseries,text=smart] at (133.5,132) {Certainty (DC)};
      \foreach \c [count=\k from 0] in {1,2,3,4,6,7}{ \node[font=\sffamily\small] at (42+9*\k,139) {\c}; }
      \foreach \j in {0,...,5}{ \node[font=\sffamily\small] at (112+9*\j,139) {\j}; }
      \draw[smart] (24,142) -- (166,142);
      % rows
      \foreach \q in {0,...,4}{
        \pgfmathsetmacro{\ya}{146+22*\q}
        \pgfmathsetmacro{\yb}{155+22*\q}
        \fill[paper] (24,\yb-4.5) rectangle (166,\yb+4.5);
        \node[font=\sffamily\bfseries\large] at (17,\ya+4.5) {\the\numexpr\q+1\relax};
        \node[font=\sffamily\tiny,gray] at (30,\ya) {1st};
        \node[font=\sffamily\tiny,gray] at (30,\yb) {2nd};
        \foreach \k in {0,...,5}{ \bub{42+9*\k}{\ya} \bub{42+9*\k}{\yb} }
        \foreach \j in {0,...,5}{ \bub{112+9*\j}{\ya} \bub{112+9*\j}{\yb} }
        \draw[smart!40] (24,\yb+8.5) -- (166,\yb+8.5);
      }
      \node[font=\sffamily\tiny,gray] at (105,262) {Print at 100\% (no page scaling). Scan flat, all four corner squares visible.};
      \IfFileExists{filled.tex}{\input{filled.tex}}{}
    \end{tikzpicture}}
    ```
---

```{=latex}
\begin{center}
{\LARGE\bfseries Quiz with certainty degrees}\\[2pt]
{\color{gray}Scannable version: answers and student ID are marked on the last page}
\end{center}
```

# Instructions {-}

Each question has **four proposed answers** (1 to 4) and **one and only one**
correct solution. Two *implicit solutions* apply to **every** question, even
though they are not printed under it:

```{=latex}
\begin{center}
\begin{tabular}{@{}cl@{}}
\code{6} & \textit{None} : no proposed answer is correct\\
\code{7} & \textit{All} : all four proposed answers are correct\\
\end{tabular}
\end{center}
```

For **each** question, mark on the answer sheet one answer (1, 2, 3, 4, 6 or 7)
**and** one certainty degree (DC). If you change your mind, use the **second
line** of that question: it replaces the first one.

```{=latex}
\begin{center}
\begin{tabular}{|c|c|c|c|}
\hline
\rowcolor{paper}
\textbf{DC} & \textbf{Probability of being correct} & \textbf{If correct} & \textbf{If wrong}\\
\hline
0 & 0 -- 25\,\%   & $+13$ & $+4$\\
1 & 25 -- 50\,\%  & $+16$ & $+3$\\
2 & 50 -- 70\,\%  & $+17$ & $+2$\\
3 & 70 -- 85\,\%  & $+18$ & $0$\\
4 & 85 -- 95\,\%  & $+19$ & $-6$\\
5 & 95 -- 100\,\% & $+20$ & $-20$\\
\hline
\end{tabular}
\end{center}
```

# Questions {-}

**Question 1.** The capital of France is\
\opt{1}{Lille}\opt{2}{Lyon}\opt{3}{Paris}\opt{4}{Nice}

**Question 2.** The capital of Italy is\
\opt{1}{Berlin}\opt{2}{Prague}\opt{3}{Tokyo}\opt{4}{Madrid}

**Question 3.** The United Kingdom comprises\
\opt{1}{England}\opt{2}{Scotland}\opt{3}{Wales}\opt{4}{Northern Ireland}

**Question 4.** The largest planet of the Solar System is\
\opt{1}{Mars}\opt{2}{Venus}\opt{3}{Saturn}\opt{4}{Jupiter}

**Question 5.** The chemical symbol of gold is\
\opt{1}{Ag}\opt{2}{Au}\opt{3}{Gd}\opt{4}{Go}

```{=latex}
\newpage
\thispagestyle{empty}
\AddToShipoutPictureBG*{\AtPageUpperLeft{\sheet}}
\mbox{}
```
