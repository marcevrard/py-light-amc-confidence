#!/usr/bin/env python3
# Copyright (c) 2026 Marc Evrard. Licensed under CC BY 4.0
# (https://creativecommons.org/licenses/by/4.0/). Attribution required: cite
# Evrard, M. (2026), py-light-amc-confidence,
# https://github.com/marcevrard/py-light-amc-confidence
# Degrees of confidence: SMART, University of Liege, https://smart.uliege.be/
# Inspired by Auto Multiple Choice, https://www.auto-multiple-choice.net/
"""Read scanned answer sheets made from this quiz project and score them
with the degree-of-confidence scale.

Usage:
  pdftoppm -r 200 -gray -png scans.pdf scan          # PDF scans -> PNG
  python3 scan_reader.py scan-*.png --quiz quizzes/quiz-1 --csv results.csv
  python3 scan_reader.py scans/ --quiz quizzes/quiz-1 --csv results.csv
  python3 scan_reader.py scans/ --quiz quizzes/quiz-1 --recursive --debug
  python3 scan_reader.py scans/ --quiz quizzes/quiz-1 --pencil     # faint pencil marks

The answer key is read from the quiz folder given with --quiz (its questions.md:
\\optc{C}{...} marks the correct proposed answer, \\correct{n} or \\correct{all}
the implicit ones). --quiz also accepts the questions file itself. Alternatively
give the key directly with --key C,n,all,D,B (unshuffled copy 0 only).

Shuffled copies: every sheet carries its copy number as a printed binary strip.
The reader decodes it and, with the master seed from <quiz folder>/seed.txt (or
--seed), undoes the shuffle of questions and answers before scoring (quizcopy.py).
A sheet whose strip cannot be read is not scored: rerun it with --copy N.

Inputs can be image files and/or folders; a folder is scanned for images
(add --recursive to include its sub-folders). With --debug, a
<name>.debug.png is written next to each scan and skipped on later runs.

Requires: python3, opencv (import cv2), numpy.
All geometry (millimetres from the top-left of the A4 page) mirrors the
constants documented in the header of template/answer-sheet.tex.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import quizcopy

# ---- geometry (must match template/answer-sheet.tex) ---------------------------
MARKS = [(10, 10), (200, 10), (10, 287), (200, 287)]  # TL, TR, BL, BR centres
PAGE_W, PAGE_H = 210, 297
PX_PER_MM = 8
R_READ = 1.5  # mm, inner disk that is read (the bubble radius is 2 mm)
ANS_CODES = [1, 2, 3, 4, 6, 7]  # internal codes, in the order of the sheet columns
LABELS = {1: "A", 2: "B", 3: "C", 4: "D", 6: "n", 7: "all"}  # what the sheet prints
CODE_OF = {v.lower(): k for k, v in LABELS.items()}
N_Q, N_DIGITS = 5, 8
CODE_R = 1.0  # mm, inner disk read in each 3 mm square of the copy code strip


def code_xy(j):
    """Square j (0..11) of the copy code strip: sentinel, 10 bits, parity."""
    return 61 + 8 * j, 10


def id_xy(i, d):
    """Bubble of digit d in column i. Rows are ordered 1..9 then 0 (0 is last)."""
    return 40 + 10 * i, 68 + 6 * ((d - 1) % 10)


def load_quiz(path):
    """Questions (parsed) and master seed from a quiz folder or its questions.md."""
    path = Path(path)
    qfile = path / "questions.md" if path.is_dir() else path
    questions = quizcopy.parse_questions(qfile.read_text(encoding="utf-8"), str(qfile))
    return questions, quizcopy.read_seed(qfile.parent)


def key_from_questions(path):
    """Answer key (codes 1-4, 6, 7) of the original questions, from questions.md."""
    return [parse_answer(q.key) for q in load_quiz(path)[0]]


def parse_answer(text):
    """'C' -> 3, 'n' -> 6, 'all' -> 7; the digits 1-4, 6, 7 are accepted as well."""
    t = text.strip().lower()
    code = CODE_OF.get(t) or (int(t) if t.isdigit() else None)
    if code not in LABELS:
        raise ValueError(f"bad answer {text!r}: use A, B, C, D, n or all")
    return code


def ans_xy(q, line, k):
    return 42 + 9 * k, 146 + 22 * q + 9 * line


def dc_xy(q, line, j):
    return 112 + 9 * j, 146 + 22 * q + 9 * line


# ---- degree-of-confidence scale: DC -> (points if correct, if wrong) --
SCALE = {0: (13, 4), 1: (16, 3), 2: (17, 2), 3: (18, 0), 4: (19, -6), 5: (20, -20)}
DEFAULT_DC = 3  # confidence used when the student gives none (or an unreadable one)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass(frozen=True)
class Tuning:
    """How dark and how full a bubble must be to count as ticked.

    A pixel is "ink" when it is at least `ink_delta` grey levels darker than the
    paper (measured on each sheet, so grey scans are handled). A bubble is ticked
    when the inked share of its inner disk reaches `filled`; between `doubt` and
    `filled` the mark is reported as faint and not counted.
    """

    ink_delta: int = 40
    filled: float = 0.25
    doubt: float = 0.12


PENCIL = Tuning(ink_delta=20, filled=0.15, doubt=0.08)  # light pencil, faint scans


def find_marks(gray):
    """Locate the 4 black registration squares (one per image quadrant)."""
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (1e-4 * h * w < a < 4e-3 * h * w):
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        if not (0.75 < cw / ch < 1.33) or a / (cw * ch) < 0.85:
            continue
        cands.append((x + cw / 2, y + ch / 2))
    found = []
    for cx, cy in [(0, 0), (w, 0), (0, h), (w, h)]:
        if not cands:
            raise ValueError("registration squares not found")
        best = min(cands, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        found.append(best)
    if len(set(found)) < 4:
        raise ValueError("could not find 4 distinct registration squares")
    return np.float32(found)


def rectify(img):
    """Warp the scan so that 1 mm of paper = PX_PER_MM pixels, page upright."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    src = find_marks(gray)
    dst = np.float32([(x * PX_PER_MM, y * PX_PER_MM) for x, y in MARKS])
    matrix = cv2.getPerspectiveTransform(src, dst)
    size = (PAGE_W * PX_PER_MM, PAGE_H * PX_PER_MM)
    return cv2.warpPerspective(
        gray, matrix, size, flags=cv2.INTER_AREA, borderValue=255
    )


def paper_level(page):
    """Grey level of the blank paper (the page is mostly white)."""
    return float(np.median(page))


def fill_ratio(page, x_mm, y_mm, level, radius=R_READ):
    """Share of pixels darker than `level` in the disk centred at (x_mm, y_mm)."""
    cx, cy = int(x_mm * PX_PER_MM), int(y_mm * PX_PER_MM)
    mask = np.zeros(page.shape, np.uint8)
    cv2.circle(mask, (cx, cy), int(radius * PX_PER_MM), 255, -1)
    return float((page[mask > 0] < level).mean())


def pick(ratios, tuning):
    """Turn the fill ratios of one group of bubbles into (index or None, flag)."""
    ticked = [i for i, r in enumerate(ratios) if r >= tuning.filled]
    doubt = [i for i, r in enumerate(ratios) if tuning.doubt <= r < tuning.filled]
    if len(ticked) == 1 and not doubt:
        return ticked[0], ""
    if not ticked and not doubt:
        return None, ""
    if len(ticked) == 1:
        return ticked[0], "faint extra mark"
    if not ticked and len(doubt) == 1:
        return None, "faint mark, not counted"
    return None, "multiple marks"


def read_copy_code(page, level):
    """Decode the printed copy strip -> (copy number or None, flag)."""
    ratios = [fill_ratio(page, *code_xy(j), level, CODE_R) for j in range(quizcopy.N_BITS + 2)]
    if any(0.25 < r < 0.6 for r in ratios):
        return None, "copy code unclear"
    copy = quizcopy.decode_bits([int(r >= 0.6) for r in ratios])
    return copy, "" if copy is not None else "copy code invalid"


def read_sheet(img, tuning):
    """Return (student ID, rows, flags, rectified page, copy number) for one sheet."""
    page = rectify(img)
    level = paper_level(page) - tuning.ink_delta
    flags = []
    digits = []
    for i in range(N_DIGITS):
        ratios = [fill_ratio(page, *id_xy(i, d), level) for d in range(10)]
        d, flag = pick(ratios, tuning)
        digits.append("?" if d is None else str(d))
        if d is None:
            flags.append(f"ID digit {i + 1}: {flag or 'blank'}")
        elif flag:
            flags.append(f"ID digit {i + 1}: {flag}")
    rows = []
    for q in range(N_Q):
        line = []
        for ln in (0, 1):
            ratios_a = [fill_ratio(page, *ans_xy(q, ln, k), level) for k in range(6)]
            ratios_c = [fill_ratio(page, *dc_xy(q, ln, j), level) for j in range(6)]
            a, flag_a = pick(ratios_a, tuning)
            c, flag_c = pick(ratios_c, tuning)
            line.append((None if a is None else ANS_CODES[a], c, flag_a, flag_c))
        rows.append(line)
    copy, copy_flag = read_copy_code(page, level)
    if copy is None:
        flags.append(copy_flag)
    return "".join(digits), rows, flags, page, copy


def final_choice(line):
    """The 2nd line replaces the 1st one, for the answer and/or the confidence."""
    (a1, c1, fa1, fc1), (a2, c2, fa2, fc2) = line
    ans = a2 if a2 is not None else a1
    dc = c2 if c2 is not None else c1
    notes = [
        f"1st answer {fa1}" if fa1 else "",
        f"1st DC {fc1}" if fc1 else "",
        f"2nd answer {fa2}" if fa2 else "",
        f"2nd DC {fc2}" if fc2 else "",
    ]
    return ans, dc, [n for n in notes if n]


def score(ans, dc, key):
    """Blank answer = 0 point. Missing or unreadable DC = DEFAULT_DC."""
    if ans is None:
        return 0
    right, wrong = SCALE[DEFAULT_DC if dc is None else dc]
    return right if ans == key else wrong


def debug_image(page, path, tuning):
    """Save the rectified page with every bubble circled (green = ticked)."""
    level = paper_level(page) - tuning.ink_delta
    out = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)
    pts = [id_xy(i, d) for i in range(N_DIGITS) for d in range(10)]
    for q in range(N_Q):
        for ln in (0, 1):
            pts += [ans_xy(q, ln, k) for k in range(6)]
            pts += [dc_xy(q, ln, j) for j in range(6)]
    pts += [code_xy(j) for j in range(quizcopy.N_BITS + 2)]
    for x, y in pts:
        r = fill_ratio(page, x, y, level)
        if r >= tuning.filled:
            color = (0, 160, 0)
        elif r >= tuning.doubt:
            color = (0, 165, 255)
        else:
            color = (200, 200, 200)
        centre = (int(x * PX_PER_MM), int(y * PX_PER_MM))
        cv2.circle(out, centre, int(R_READ * PX_PER_MM), color, 2)
    cv2.imwrite(str(path), out)


def collect_images(inputs, recursive=False):
    """Expand files and folders into a sorted, de-duplicated list of image paths."""
    found = []
    for item in map(Path, inputs):
        if item.is_dir():
            candidates = item.rglob("*") if recursive else item.glob("*")
            found += sorted(candidates, key=lambda p: p.parts)
        elif item.is_file():
            found.append(item)
        else:
            print(f"{item}: not found")
    images = []
    for path in found:
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.stem.endswith(".debug") or path in images:
            continue
        images.append(path)
    return images


def timestamped(path, now=None):
    """results.csv -> results_20260930-142530.csv"""
    now = now or datetime.now()
    return path.with_name(f"{path.stem}_{now:%Y%m%d-%H%M%S}{path.suffix}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="image files and/or folders")
    ap.add_argument("--recursive", action="store_true", help="also search sub-folders")
    ap.add_argument("--quiz", help="quiz folder (or its questions.md) holding the key")
    ap.add_argument("--key", help="override the key, e.g. C,n,all,D,B (copy 0 only)")
    ap.add_argument("--seed", help="master seed (default: <quiz folder>/seed.txt)")
    ap.add_argument("--copy", type=int, help="force the copy number instead of reading it")
    ap.add_argument("--csv", help="write results to this CSV file")
    ap.add_argument("--debug", action="store_true", help="save <image>.debug.png")
    ap.add_argument("--no-timestamp", action="store_true", help="keep the CSV name")
    ap.add_argument("--pencil", action="store_true", help="preset for faint marks")
    ap.add_argument("--ink-delta", type=int, help="grey levels below paper = ink (40)")
    ap.add_argument("--fill-min", type=float, help="ink share to count a tick (0.25)")
    args = ap.parse_args()

    tuning = PENCIL if args.pencil else Tuning()
    if args.ink_delta is not None:
        tuning = replace(tuning, ink_delta=args.ink_delta)
    if args.fill_min is not None:
        tuning = replace(tuning, filled=args.fill_min, doubt=args.fill_min / 2)

    questions, seed = None, args.seed
    try:
        if args.key:
            key = [parse_answer(k) for k in args.key.split(",")]
        elif args.quiz:
            questions, quiz_seed = load_quiz(args.quiz)
            seed = seed or quiz_seed
            key = [parse_answer(q.key) for q in questions]
        else:
            sys.exit("give the key: --quiz FOLDER (or FILE), or --key C,n,all,D,B")
    except (ValueError, OSError) as e:
        sys.exit(str(e))
    if len(key) != N_Q:
        sys.exit(f"the answer key has {len(key)} values, the sheet has {N_Q} questions")

    images = collect_images(args.inputs, args.recursive)
    if not images:
        sys.exit("no image found (accepted: " + ", ".join(sorted(IMAGE_SUFFIXES)) + ")")

    table = []
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            print(f"{path}: cannot read image")
            continue
        try:
            sid, rows, flags, page, copy = read_sheet(img, tuning)
        except ValueError as e:
            print(f"{path}: {e}")
            continue
        if args.copy is not None:
            copy = args.copy
            flags = [f for f in flags if not f.startswith("copy code")]
        total, cells, scored = 0, [], copy is not None
        if scored and copy != 0 and (questions is None or seed is None):
            flags.append(f"copy {copy}: needs --quiz and its seed (seed.txt or --seed)")
            scored = False
        if scored:
            qorder, oorders = quizcopy.layout(questions, seed, copy)
        elif copy is None:
            flags.append("not scored: use --copy N")
        for q, line in enumerate(rows):
            ans, dc, notes = final_choice(line)
            points = ""
            if scored:
                if ans is not None:
                    o, code = quizcopy.original_answer(ans, q, qorder, oorders)
                    points = score(code, dc, key[o])
                else:
                    points = 0
                total += points
            flags += [f"Q{q + 1}: {n}" for n in notes]
            if ans is None:
                flags.append(f"Q{q + 1}: no answer")
            elif dc is None:
                note = f"no confidence degree (scored as DC {DEFAULT_DC})"
                flags.append(f"Q{q + 1}: {note}")
            cells += [LABELS.get(ans, ""), dc, points]
        total = total if scored else ""
        table.append([str(path), sid, "" if copy is None else copy] + cells + [total, "; ".join(flags)])
        grade = f"{max(0, total) / (N_Q * 20) * 20:.1f}/20" if scored else "-"
        shown = "?" if copy is None else copy
        line = f"{path}  ID={sid}  copy={shown}  total={total if scored else '-'}/{20 * N_Q}  grade={grade}"
        print(line + (f"  [{'; '.join(flags)}]" if flags else ""))
        if args.debug:
            debug_image(page, path.with_name(f"{path.stem}.debug.png"), tuning)

    print(f"{len(table)} sheet(s) read, {len(images) - len(table)} skipped")
    if args.csv and table:
        header = ["file", "student_id", "copy"]
        for q in range(1, N_Q + 1):
            header += [f"q{q}_answer", f"q{q}_dc", f"q{q}_points"]
        out_path = Path(args.csv)
        if not args.no_timestamp:
            out_path = timestamped(out_path)
        with out_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header + ["total", "flags"])
            writer.writerows(table)
        print(f"results written to {out_path}")


if __name__ == "__main__":
    main()
