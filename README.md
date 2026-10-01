# py-light-amc-confidence

**A lightweight Python take on Auto Multiple Choice (AMC): scannable
multiple-choice quizzes with degrees of confidence.**
Inspired by [AMC](https://www.auto-multiple-choice.net/).

Multiple-choice quizzes with **degrees of confidence**, written in Markdown,
printed as a PDF with a **scannable answer sheet**, and graded automatically
from scanned images with a small OpenCV script.

- Write the questions, and mark the correct answers, in one Markdown file.
- Unique **shuffled copy for each student** (questions and answers in a different
  order), identified by a printed code on the answer sheet.
- The PDF has three pages: instructions, questions, and a machine-readable
  answer sheet (student ID, one answer and one confidence degree per question,
  plus a second line to change their mind once).
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
py-light-amc-confidence/
├── README.md
├── LICENSE                CC BY 4.0
├── CITATION.cff           citation metadata (GitHub "Cite this repository")
├── Makefile               make [QUIZ=folder]  ->  <folder>/quiz.pdf
├── defaults.yaml          pandoc settings shared by all quizzes
├── scan_reader.py         scan -> student ID, copy, answers, scores, CSV
├── build_copies.py        one shuffled PDF per student
├── quizcopy.py            shuffle logic shared by the two scripts
├── content/
│   ├── instructions.md      rules shown to students (page 1)
│   └── questions-begin.md   questions page heading and spacing (page 2)
├── template/              LaTeX shared by all quizzes
│   ├── style.tex            colours, header/footer, \opt \optc \correct macros
│   ├── title.tex            title block
│   ├── implicit-answers.tex table of the n / all answers
│   ├── dc-table.tex         degree-of-confidence table (booktabs)
│   ├── answer-sheet.tex     scannable sheet (TikZ), geometry documented in its header
│   └── answer-page.tex      last page carrying the sheet
├── examples/
│   └── simple/            small general-knowledge example, kept in the repo
│       ├── meta.tex         title, headers, footer
│       ├── seed.txt         master seed of the shuffle
│       ├── questions.md     questions + answer key
│       └── quiz.pdf         example output
└── quizzes/               your real quizzes (ignored by git, see below)
    └── quiz-1/
        ├── meta.tex
        ├── questions.md
        ├── seed.txt         master seed (keep it!)
        ├── quiz.pdf         unshuffled version (copy 0)
        └── copies/          shuffled copies, made by `make copies`
```

A quiz is just a folder with two files: `meta.tex` and `questions.md`
(`seed.txt` is added when you make shuffled copies).

## Requirements

**To build the PDF**
- [pandoc](https://pandoc.org/) and `make`
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

## Build a quiz

From the repository root (the `\input{template/...}` paths are relative):

```
make                       # builds examples/simple/quiz.pdf
make QUIZ=quizzes/quiz-1   # builds quizzes/quiz-1/quiz.pdf
make clean QUIZ=quizzes/quiz-1
```

The PDF has three pages:

1. **Instructions**: the rules and the degree-of-confidence table.
2. **Questions**: one question per block, with room between questions and
   between the proposed answers.
3. **Answer sheet**: the scannable page (no header or footer).

Extra pandoc options can be passed with `PANDOC_FLAGS="..."`.

## Shuffled copies, one per student

```
make copies QUIZ=quizzes/quiz-1 N=30     # copies 1..30
```

or `python3 build_copies.py quizzes/quiz-1 30 [--first 31]`. This writes, in
`quizzes/quiz-1/copies/`: `copy-001.pdf` ..., `all-copies.pdf` (the copies of the
run merged in one file for printing, with a **blank page after each copy** so
that double-sided printing starts every copy on a front side; made by default
with `pdfunite` from poppler, or `qpdf` if that is missing; `MERGE=0` skips the
merge and `BLANK=0` the blank pages) and `index.csv` (the
order of each copy).

- **What is shuffled:** the order of the questions, and the order of the four
  proposed answers A to D inside each question. `n` and `all` never move.
  Numbering and letters are printed again from 1 and from A in each copy.
- **Copy number:** copy 0 is the quiz as written (this is what plain `make`
  builds). Copies 1 to 1023 are shuffled. The number is printed in the footer of
  the question pages and on the answer sheet, as a small **binary strip** along
  the top edge (a sentinel, 10 bits and a parity bit). It is pre-printed, so
  students have nothing to fill in, and the reader checks the sentinel and the
  parity.
- **Master seed:** the shuffle only depends on the master seed in
  `<quiz folder>/seed.txt` and on the copy number. The file is created (random)
  the first time you make copies. **Keep it**: the reader needs it to undo the
  shuffle, and without it the copies cannot be regenerated. The `examples/simple`
  seed is public, so use your own seed for a real exam.
- **Marking:** `scan_reader.py` decodes the copy number of each sheet, rebuilds
  its shuffle from the seed, maps the student's letters back to the original
  questions and answers, and scores them with the key in `questions.md`. The key
  is written only once, in the original order.

Give each student a different copy (for example by seat number) and keep a list
of who got which number. The ID the student writes on the sheet is independent of
the copy number.

## Create your own quiz

1. Copy the example folder: `cp -r examples/simple quizzes/my-quiz`
2. Edit `quizzes/my-quiz/meta.tex`: title, left and right header, footer.

   ```latex
   \newcommand{\quiztitle}{Quiz 1}
   \newcommand{\quizlhead}{Master 1 -- Artificial Intelligence}
   \newcommand{\quizrhead}{Hands-on Machine Learning}
   \newcommand{\quizlfoot}{Universit\'e Paris-Saclay --- Marc Evrard}
   ```

3. Edit `quizzes/my-quiz/questions.md`. One question looks like this:

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
   with an error. The answer sheet has **5 question rows**, so the file must
   hold 5 questions.
4. Build it: `make QUIZ=quizzes/my-quiz`.

The colour `upsaclay` and the spacing are defined in `template/style.tex` and
`content/questions-begin.md`.

### Keep real quizzes private

`quizzes/.gitignore` ignores everything in that folder except itself: the examples
are published, but your real questions and answer keys (which sit in
`questions.md`) stay out of the repository. Edit or delete `quizzes/.gitignore`
if you do want to publish them.

## Print and scan

1. Print `quiz.pdf` (or the copies) on A4 at **100 %** (no page scaling). The four black squares
   in the corners of the answer sheet are the registration marks and must be
   printed.
2. Students fill the bubbles completely with a dark **pen**: the 8-digit student
   ID, then per question one answer and one DC. **A pen is strongly preferred
   over a pencil**: pencil marks are faint, scan unevenly and are the main cause
   of unread or flagged bubbles (see `--pencil` below if you must accept them).
   To change their mind they fill the **2nd line** of that question: it replaces
   the 1st line (answer and/or DC, each separately). Only one change is allowed
   and the 1st line must not be erased.
3. Scan the answer sheet page (page 3) flat, all four corner squares visible,
   about 200 dpi, grey or colour. The reader corrects rotation and perspective.
4. PDFs must be converted to images first:

```
pdftoppm -r 200 -gray -png scans.pdf scans/scan
```

## Read the scans

```
python scan_reader.py scans/ --quiz quizzes/quiz-1 --csv results.csv
```

`--quiz` is the quiz folder (or its `questions.md`): the answer key is read
from it, and the master seed from its `seed.txt`.

| Option | Effect |
|--------|--------|
| `inputs…` | image files and/or folders (`.png .jpg .jpeg .tif .tiff .bmp`) |
| `--quiz PATH` | quiz folder, or the questions file, holding the answer key |
| `--key C,n,all,D,B` | give the key directly instead of `--quiz` (copy 0 only, no shuffle) |
| `--seed S` | master seed, if `seed.txt` is not in the quiz folder |
| `--copy N` | force the copy number when the printed code cannot be read |
| `--recursive` | also search sub-folders |
| `--csv FILE` | write the results; the name gets a timestamp, `results_20260930-142530.csv` |
| `--no-timestamp` | keep the CSV name as given |
| `--debug` | write `<name>.debug.png` with every bubble circled (green = ticked) |
| `--pencil` | preset for light pencil or faint scans (less reliable than pen) |
| `--ink-delta N` | grey levels below the paper that count as ink (default 40) |
| `--fill-min X` | share of a bubble that must be inked to count as ticked (default 0.25) |

The console prints one line per sheet (ID, copy, total, grade and flags) and the
CSV has one row per sheet: file, student ID, copy number, then answer / DC /
points for each question, the total and the flags. The answer shown is the
letter the student marked on **their own copy**; the points are computed after
mapping it back to the original question. Try it on the example:
`python scan_reader.py scans/ --quiz examples/simple`.

### What the reader decides

- Ink is measured **relative to the paper grey of each scan**, so grey or
  shadowed scans work. `--pencil` lowers the thresholds further.
- A bubble counts as ticked when enough of its inner disk is inked. A faint
  isolated mark is **not** counted and is flagged.
- Several bubbles ticked in the same group give "multiple marks": no answer for
  that group (flagged). An unreadable ID digit is shown as `?`.
- A missing or unreadable DC is scored as **DC 3** and flagged.
- If the copy code cannot be read (damaged strip, wrong parity, sheet printed
  before the strip existed), the sheet is **not scored** and flagged
  `not scored: use --copy N`. Look at the copy number printed next to the strip
  and rerun that sheet with `--copy N`.
- Debug images (`*.debug.png`) are skipped automatically on later runs.

## Sheet geometry

The reader locates bubbles from fixed millimetre coordinates on the A4 page,
relative to the four registration squares. The numbers are documented at the top
of `template/answer-sheet.tex` and repeated as constants at the top of
`scan_reader.py` (`id_xy`, `ans_xy`, `dc_xy`, `code_xy`, `MARKS`). **If you move anything on
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

## Inspiration

The project is inspired by [Auto Multiple Choice (AMC)](https://www.auto-multiple-choice.net/),
the free software for creating and automatically marking multiple-choice
questionnaires from scanned answer sheets. This repository keeps the same
overall workflow (print the quiz, scan the filled sheets, mark automatically)
in a much smaller Python code base, and adds the degrees of confidence that AMC
does not provide out of the box. It does not reuse AMC's code or file formats,
and it is not affiliated with the AMC project.

## License and how to cite

This work is licensed under the
[Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
You may share and adapt it for any purpose, including commercially, as long as
you give appropriate credit, link to the license and indicate changes. See
[`LICENSE`](LICENSE).

Please cite it as:

> Evrard, M. (2026). *py-light-amc-confidence: scannable multiple-choice
> quizzes with degrees of confidence*.
> <https://github.com/marcevrard/py-light-amc-confidence>. CC BY 4.0.

```bibtex
@software{evrard2026pylightamcconfidence,
  author  = {Evrard, Marc},
  title   = {py-light-amc-confidence: scannable multiple-choice quizzes with degrees of confidence},
  year    = {2026},
  url     = {https://github.com/marcevrard/py-light-amc-confidence},
  license = {CC-BY-4.0}
}
```

If you use the degree-of-confidence scoring, please also cite the SMART
references below. Every source file carries a short copyright and license header.

## Limitations

- Fixed to 5 questions and 8 ID digits (constants `N_Q`, `N_DIGITS`, and the
  sheet template).
- Tested on rendered sheets with simulated marks, distortion and noise, and on
  one real pencil scan of an earlier version of the sheet. Do a full print, fill,
  scan and read run with your printer and scanner before a real exam.
- Sheets printed from an older layout (numbered answers, ID digit 0 first, ID
  matrix at the old position, or without the copy strip) are not read
  correctly by the current reader.
- The shuffle is a function of the seed and the copy number, using Python's
  `random` module. Keep `seed.txt` with the quiz; do not mix copies made with
  different seeds in one batch of scans.
- Questions that refer to other options ("A and B", "all of the above" written
  as an option) do not survive shuffling: use the implicit `n` and `all`.
- Scans must show all four corner squares; otherwise the sheet is skipped.
