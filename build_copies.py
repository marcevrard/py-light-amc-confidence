#!/usr/bin/env python3
# Copyright (c) 2026 Marc Evrard. Licensed under CC BY 4.0
# (https://creativecommons.org/licenses/by/4.0/). Attribution required: cite
# Evrard, M. (2026), py-light-amc-confidence,
# https://github.com/marcevrard/py-light-amc-confidence
"""Build one shuffled PDF per student (see quizcopy.py).

  python3 build_copies.py quizzes/quiz-1 30            # copies 1..30
  python3 build_copies.py quizzes/quiz-1 10 --first 31  # copies 31..40
  make copies QUIZ=quizzes/quiz-1 N=30                  # same, through make

Output, in <quiz folder>/copies/:
  copy-001.pdf ...   one 3-page PDF per copy (instructions, questions, answer sheet)
  all-copies.pdf     the copies of this run in one file for printing (pdfunite, or qpdf)
  index.csv          for each copy: original question printed at each position
  src/               the generated markdown and header of each copy

The master seed is read from <quiz folder>/seed.txt; it is created (random) if it
does not exist. KEEP IT: the scan reader needs it to undo the shuffle.
Run from the repository root (the LaTeX templates are found by relative paths).
"""

import argparse
import csv
import os
import secrets
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import quizcopy as qc

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quiz", help="quiz folder (meta.tex, questions.md)")
    ap.add_argument("count", type=int, help="number of copies to build")
    ap.add_argument("--first", type=int, default=1, help="first copy number (1)")
    ap.add_argument("--pandoc-flags", default=os.environ.get("PANDOC_FLAGS", ""))
    ap.add_argument("--no-merge", action="store_true", help="skip all-copies.pdf")
    args = ap.parse_args()

    quiz = Path(args.quiz)
    if not (quiz / "questions.md").is_file() or not (quiz / "meta.tex").is_file():
        sys.exit(f"{quiz}: needs questions.md and meta.tex")
    last = args.first + args.count - 1
    if args.first < 1 or args.count < 1 or last > qc.MAX_COPY:
        sys.exit(f"copy numbers must stay between 1 and {qc.MAX_COPY}")
    try:
        questions = qc.parse_questions((quiz / "questions.md").read_text(encoding="utf-8"), str(quiz / "questions.md"))
    except ValueError as e:
        sys.exit(str(e))

    seed = qc.read_seed(quiz)
    if seed is None:
        seed = str(secrets.randbelow(10**9))
        (quiz / "seed.txt").write_text(seed + "\n")
        print(f"new master seed {seed} written to {quiz / 'seed.txt'}: keep it")

    out = quiz / "copies"
    src = out / "src"
    src.mkdir(parents=True, exist_ok=True)
    index_rows, pdfs = [], []
    for copy in range(args.first, last + 1):
        name = f"copy-{copy:03d}"
        (src / f"{name}.md").write_text(qc.render_copy(questions, seed, copy), encoding="utf-8")
        bits = ",".join(map(str, qc.code_bits(copy)))
        (src / f"{name}.tex").write_text(f"\\def\\quizcopy{{{copy:03d}}}\n\\def\\quizbits{{{bits}}}\n")
        pdf = out / f"{name}.pdf"
        cmd = ["pandoc", *shlex.split(args.pandoc_flags), "-d", "defaults.yaml",
               "-H", str(quiz / "meta.tex"), "-H", str(src / f"{name}.tex"),
               "content/instructions.md", "content/questions-begin.md",
               str(src / f"{name}.md"), "-o", str(pdf)]
        if subprocess.run(cmd, cwd=ROOT).returncode:
            sys.exit(f"pandoc failed for copy {copy}")
        pdfs.append(pdf)
        qorder, oorders = qc.layout(len(questions), seed, copy)
        row = [copy]
        for o in qorder:
            row.append(f"{o + 1}:" + "".join(qc.LETTERS[idx] for idx in oorders[o]))
        index_rows.append(row)
        print(f"{pdf}")

    index = out / "index.csv"
    new = not index.exists()
    with index.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["copy"] + [f"printed_q{i}=orig:options" for i in range(1, len(questions) + 1)])
        w.writerows(index_rows)
    if not args.no_merge:
        merged = out / "all-copies.pdf"
        files = [str(p) for p in pdfs]
        if shutil.which("pdfunite"):
            cmd = ["pdfunite", *files, str(merged)]
        elif shutil.which("qpdf"):
            cmd = ["qpdf", "--empty", "--pages", *files, "--", str(merged)]
        else:
            cmd = None
            print("pdfunite (poppler) or qpdf not found: all-copies.pdf not made")
        if cmd:
            subprocess.run(cmd, check=True)
            print(merged)

if __name__ == "__main__":
    main()
