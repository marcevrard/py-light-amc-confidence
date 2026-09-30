# scan-quiz

Multiple-choice quizzes with **degrees of confidence**, written in Markdown,
printed as a PDF with a **scannable answer sheet**, and graded automatically
from scanned images with a small OpenCV script.

- Write the questions in Markdown (pandoc + LaTeX builds `quiz.pdf`).
- Students answer on a machine-readable sheet: student ID, one answer and one
  confidence degree per question, plus a second line to change their mind once.
- `scan_reader.py` reads the scans, recovers the ID and the answers, scores them
  with the confidence scale and writes a CSV.

## Quiz format

Each question has four proposed answers (**A to D**) and exactly one correct
solution. Two implicit solutions apply to every question, although they are not
printed under it:

| Code | Meaning |
|------|---------|
| `n`   | none of the proposed answers is correct |
| `all` | all four proposed answers are correct |

For every question the student marks one answer and one **degree of confidence
(DC)** from 0 to 5. If an answer is ticked without a DC, **DC 3** is applied.

| DC | Probability of being correct | If correct | If wrong |
|----|------------------------------|-----------:|---------:|
| 0  | 0 – 25 %                     | +13 | +4  |
| 1  | 25 – 50 %                    | +16 | +3  |
| 2  | 50 – 70 %                    | +17 | +2  |
| 3  | 70 – 85 %                    | +18 | 0   |
| 4  | 85 – 95 %                    | +19 | −6  |
| 5  | 95 – 100 %                   | +20 | −20 |

Stating your real probability of being right maximises the expected score.
The scale and the implicit answers follow the certainty-degree method of the
SMART service of the University of Liège (see [References](#references)).
The total is out of 100 (5 × 20); the grade out of 20 is `max(0, total) / 5`.
A blank answer scores 0.

## Repository layout

```
scan-quiz/
├── Makefile               make  ->  quiz.pdf
├── defaults.yaml          pandoc settings (input files, page layout, includes)
├── content/
│   ├── 01-instructions.md   rules shown to students
│   └── 02-questions.md      the questions AND the answer key
├── template/
│   ├── style.tex            colours, header/footer, \opt \optc \correct macros
│   ├── title.tex            title block
│   ├── implicit-answers.tex table of the n / all answers
│   ├── dc-table.tex         degree-of-confidence table (booktabs)
│   ├── answer-sheet.tex     scannable sheet (TikZ), geometry documented in its header
│   └── answer-page.tex      last page carrying the sheet
├── scan_reader.py         scan -> student ID, answers, scores, CSV
└── quiz.pdf               example output
```

## Requirements

**To build the PDF**
- [pandoc](https://pandoc.org/)
- a LaTeX distribution with `pdflatex` and the packages `tikz`, `eso-pic`,
  `fancyhdr`, `lastpage`, `titlesec`, `booktabs`, `array`, `xcolor`, `amssymb`
  (TeX Live / MacTeX include them)

**To read scans**
- Python 3 with `opencv` (`import cv2`) and `numpy`
- `pdftoppm` from poppler, only if your scans are PDFs

```
conda create -n scanquiz -c conda-forge python opencv numpy poppler pandoc
conda activate scanquiz
# or: pip install opencv-python numpy
```

## Build the quiz

From inside the folder (the `\input{template/...}` paths are relative):

```
make                 # or: pandoc -d defaults.yaml
```

This produces `quiz.pdf`: page 1 holds the instructions and the questions
(with header and footer), page 2 is the answer sheet.

## Write your own questions

Edit `content/02-questions.md`. One question looks like this:

```latex
**Question 1.** The capital of France is
\opt{A}{Lille}
\opt{B}{Lyon}
\optc{C}{Paris}
\opt{D}{Nice}
```

The answer key lives in the same file and is **invisible in the PDF**:

| Syntax | Meaning |
|--------|---------|
| `\optc{C}{Paris}` | proposed answer that is the correct one (prints like `\opt`) |
| `\correct{n}`     | the correct answer is "none of the above" |
| `\correct{all}`   | the correct answer is "all of the above" |

Each question must have **exactly one** of these, otherwise the reader stops
with an error. The answer sheet has **5 question rows**, so the file must hold
5 questions.

Headers, footer and title are plain LaTeX in `template/style.tex` and
`template/title.tex`. The accent colour is `upsaclay`, defined in
`template/style.tex`.

## Print and scan

1. Print `quiz.pdf` on A4 at **100 %** (no page scaling). The four black squares
   in the page corners are the registration marks and must be printed.
2. Students fill the bubbles completely (pen or pencil): the 8-digit student
   ID, then per question one answer and one DC.
   To change their mind they fill the **2nd line** of that question: it replaces
   the 1st line (answer and/or DC, each separately). Only one change is allowed
   and the 1st line must not be erased.
3. Scan the answer sheet page flat, all four corner squares visible, about
   200 dpi, grey or colour. The reader corrects rotation and perspective.
4. PDFs must be converted to images first:

```
pdftoppm -r 200 -gray -png scans.pdf scans/scan
```

## Read the scans

```
python scan_reader.py scans/ --csv results.csv
```

The answer key is read from `content/02-questions.md` next to the script.

| Option | Effect |
|--------|--------|
| `inputs…` | image files and/or folders (`.png .jpg .jpeg .tif .tiff .bmp`) |
| `--recursive` | also search sub-folders |
| `--csv FILE` | write the results; the name gets a timestamp, `results_20260930-142530.csv` |
| `--no-timestamp` | keep the CSV name as given |
| `--debug` | write `<name>.debug.png` with every bubble circled (green = ticked) |
| `--questions FILE` | read the key from another question file |
| `--key C,n,all,D,B` | override the key (letters, or the digits 1–4, 6, 7) |
| `--pencil` | preset for light pencil or faint scans |
| `--ink-delta N` | grey levels below the paper that count as ink (default 40) |
| `--fill-min X` | share of a bubble that must be inked to count as ticked (default 0.25) |

The console prints one line per sheet (ID, total, grade and flags) and the CSV
has one row per sheet: file, student ID, then answer / DC / points for each
question, the total and the flags.

### What the reader decides

- Ink is measured **relative to the paper grey of each scan**, so grey or
  shadowed scans work. `--pencil` lowers the thresholds further.
- A bubble counts as ticked when enough of its inner disk is inked. A faint
  isolated mark is **not** counted and is flagged.
- Several bubbles ticked in the same group give "multiple marks": no answer for
  that group (flagged). An unreadable ID digit is shown as `?`.
- A missing or unreadable DC is scored as **DC 3** and flagged.
- Debug images (`*.debug.png`) are skipped automatically on later runs.

## Sheet geometry

The reader locates bubbles from fixed millimetre coordinates on the A4 page,
relative to the four registration squares. The numbers are documented at the top
of `template/answer-sheet.tex` and repeated as constants at the top of
`scan_reader.py` (`id_xy`, `ans_xy`, `dc_xy`, `MARKS`). **If you move anything on
the sheet, change both places.** Student ID digits are ordered 1 to 9 then 0
(0 is the last row).

## References

The degrees of confidence (called *degrés de certitude* there), their points
table and the implicit answers come from:

- **SMART**, University of Liège, *Questions fermées / degrés de certitude*.
  <https://smart.uliege.be/> (consulted 30 September 2026). The scale is taken
  from the service's instruction sheet *SMART consignes DC*
  (<https://smart.uliege.be/wp-content/uploads/formuloms/documents/SMART_consignes_DC.pdf>).
  The SMART publications are listed on the site (ORBi).
- Leclercq, D. (2006). *L'évolution des QCM*. In G. Figari & L. Mottier-Lopez
  (Eds.). Open access on ORBi:
  <https://orbi.uliege.be/bitstream/2268/10124/1/LECLERCQ_evolution_qcm_in_figari_mottier-1.pdf>
  (background on multiple-choice tests with degrees of certainty).

This repository is an independent implementation and is not affiliated with or
endorsed by SMART or the University of Liège.

## Limitations

- Fixed to 5 questions and 8 ID digits (constants `N_Q`, `N_DIGITS`, and the
  sheet template).
- Tested on rendered sheets with simulated marks, distortion and noise, and on
  one real pencil scan of an earlier version of the sheet. Do a full print, fill,
  scan and read run with your printer and scanner before a real exam.
- Sheets printed from an older layout (numbered answers, ID digit 0 first) are
  not read correctly by the current reader.
- Scans must show all four corner squares; otherwise the sheet is skipped.
