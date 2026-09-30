#!/usr/bin/env python3
"""Read scanned answer sheets made from smart-scan-quiz.md and score them
with the SMART certainty-degree scale.

Usage:
  pdftoppm -r 200 -gray -png scans.pdf scan          # PDF scans -> PNG
  python3 smart_scan_reader.py scan-*.png --key 3,6,7,4,2 --csv results.csv
  python3 smart_scan_reader.py scans/ --key 3,6,7,4,2 --csv results.csv
  python3 smart_scan_reader.py scans/ --recursive --key 3,6,7,4,2 --debug

Inputs can be image files and/or folders; a folder is scanned for images
(add --recursive to include its sub-folders). With --debug, a
<name>.debug.png is written next to each scan and skipped on later runs.

Requires: python3, opencv (import cv2), numpy.
All geometry (millimetres from the top-left of the A4 page) mirrors the
constants documented in the header of smart-scan-quiz.md.
"""

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

# ---- geometry (must match smart-scan-quiz.md) ---------------------------
MARKS = [(10, 10), (200, 10), (10, 287), (200, 287)]  # TL, TR, BL, BR centres
PAGE_W, PAGE_H = 210, 297
PX_PER_MM = 8
R_READ = 1.5  # mm, inner disk that is read (the bubble radius is 2 mm)
ANS_CODES = [1, 2, 3, 4, 6, 7]
N_Q, N_DIGITS = 5, 8


def id_xy(i, d):
    return 50 + 10 * i, 68 + 6 * d


def ans_xy(q, line, k):
    return 42 + 9 * k, 146 + 22 * q + 9 * line


def dc_xy(q, line, j):
    return 112 + 9 * j, 146 + 22 * q + 9 * line


# ---- SMART certainty-degree scale: DC -> (points if correct, if wrong) --
SCALE = {0: (13, 4), 1: (16, 3), 2: (17, 2), 3: (18, 0), 4: (19, -6), 5: (20, -20)}
DEFAULT_DC = 3  # certainty used when the student gives none (or an unreadable one)
FILLED, DOUBT = 0.50, 0.30  # fill ratio: ticked / ambiguous zone
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


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


def fill_ratio(page, x_mm, y_mm):
    """Fraction of dark pixels inside the bubble centred at (x_mm, y_mm)."""
    cx, cy = int(x_mm * PX_PER_MM), int(y_mm * PX_PER_MM)
    mask = np.zeros(page.shape, np.uint8)
    cv2.circle(mask, (cx, cy), int(R_READ * PX_PER_MM), 255, -1)
    return float((page[mask > 0] < 140).mean())


def pick(ratios):
    """Turn the fill ratios of one group of bubbles into (index or None, flag)."""
    ticked = [i for i, r in enumerate(ratios) if r >= FILLED]
    doubt = [i for i, r in enumerate(ratios) if DOUBT <= r < FILLED]
    if len(ticked) == 1 and not doubt:
        return ticked[0], ""
    if not ticked and not doubt:
        return None, ""
    if len(ticked) == 1:
        return ticked[0], "faint extra mark"
    if not ticked and len(doubt) == 1:
        return None, "faint mark, not counted"
    return None, "multiple marks"


def read_sheet(img):
    """Return (student ID, rows, flags, rectified page) for one scanned sheet."""
    page = rectify(img)
    flags = []
    digits = []
    for i in range(N_DIGITS):
        ratios = [fill_ratio(page, *id_xy(i, d)) for d in range(10)]
        d, flag = pick(ratios)
        digits.append("?" if d is None else str(d))
        if d is None:
            flags.append(f"ID digit {i + 1}: {flag or 'blank'}")
        elif flag:
            flags.append(f"ID digit {i + 1}: {flag}")
    rows = []
    for q in range(N_Q):
        line = []
        for ln in (0, 1):
            a, flag_a = pick([fill_ratio(page, *ans_xy(q, ln, k)) for k in range(6)])
            c, flag_c = pick([fill_ratio(page, *dc_xy(q, ln, j)) for j in range(6)])
            line.append((None if a is None else ANS_CODES[a], c, flag_a, flag_c))
        rows.append(line)
    return "".join(digits), rows, flags, page


def final_choice(line):
    """The 2nd line replaces the 1st one, for the answer and/or the certainty."""
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


def debug_image(page, path):
    """Save the rectified page with every bubble circled (green = ticked)."""
    out = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)
    pts = [id_xy(i, d) for i in range(N_DIGITS) for d in range(10)]
    for q in range(N_Q):
        for ln in (0, 1):
            pts += [ans_xy(q, ln, k) for k in range(6)]
            pts += [dc_xy(q, ln, j) for j in range(6)]
    for x, y in pts:
        r = fill_ratio(page, x, y)
        if r >= FILLED:
            color = (0, 160, 0)
        elif r >= DOUBT:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="image files and/or folders")
    ap.add_argument("--recursive", action="store_true", help="also search sub-folders")
    ap.add_argument("--key", required=True, help="correct answers, e.g. 3,6,7,4,2")
    ap.add_argument("--csv", help="write results to this CSV file")
    ap.add_argument("--debug", action="store_true", help="save <image>.debug.png")
    args = ap.parse_args()

    key = [int(k) for k in args.key.split(",")]
    if len(key) != N_Q:
        sys.exit(f"--key needs {N_Q} values")

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
            sid, rows, flags, page = read_sheet(img)
        except ValueError as e:
            print(f"{path}: {e}")
            continue
        total, cells = 0, []
        for q, line in enumerate(rows):
            ans, dc, notes = final_choice(line)
            points = score(ans, dc, key[q])
            total += points
            flags += [f"Q{q + 1}: {n}" for n in notes]
            if ans is None:
                flags.append(f"Q{q + 1}: no answer")
            elif dc is None:
                flags.append(f"Q{q + 1}: no certainty (scored as DC {DEFAULT_DC})")
            cells += [ans, dc, points]
        table.append([str(path), sid] + cells + [total, "; ".join(flags)])
        grade = max(0, total) / (N_Q * 20) * 20
        line = f"{path}  ID={sid}  total={total}/{20 * N_Q}  grade={grade:.1f}/20"
        print(line + (f"  [{'; '.join(flags)}]" if flags else ""))
        if args.debug:
            debug_image(page, path.with_name(f"{path.stem}.debug.png"))

    print(f"{len(table)} sheet(s) read, {len(images) - len(table)} skipped")
    if args.csv and table:
        header = ["file", "student_id"]
        for q in range(1, N_Q + 1):
            header += [f"q{q}_answer", f"q{q}_dc", f"q{q}_points"]
        with Path(args.csv).open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header + ["total", "flags"])
            writer.writerows(table)


if __name__ == "__main__":
    main()
