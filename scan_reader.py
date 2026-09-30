#!/usr/bin/env python3
"""Read scanned answer sheets made from smart-scan-quiz.md and score them
with the SMART certainty-degree scale.

Usage:
  pdftoppm -r 200 -gray -png scans.pdf scan          # PDF scans -> PNG
  python3 smart_scan_reader.py scan-*.png --key 3,6,7,4,2 --csv results.csv
  python3 smart_scan_reader.py scan-01.png --key 3,6,7,4,2 --debug   # writes scan-01.debug.png

Requires: python3, opencv-python, numpy.
All geometry (millimetres from the top-left of the A4 page) mirrors the
constants documented in the header of smart-scan-quiz.md.
"""
import argparse
import csv
import sys

import cv2
import numpy as np

# ---- geometry (must match smart-scan-quiz.md) ---------------------------
MARKS = [(10, 10), (200, 10), (10, 287), (200, 287)]       # TL TR BL BR centres
PAGE_W, PAGE_H = 210, 297
PX_PER_MM = 8
R_READ = 1.5                                               # mm, inner disk read (bubble radius is 2)
ANS_CODES = [1, 2, 3, 4, 6, 7]
N_Q, N_DIGITS = 5, 8

def id_xy(i, d):     return 50 + 10 * i, 68 + 6 * d
def ans_xy(q, line, k): return 42 + 9 * k, 146 + 22 * q + 9 * line
def dc_xy(q, line, j):  return 112 + 9 * j, 146 + 22 * q + 9 * line

# ---- SMART certainty-degree scale: DC -> (points if correct, if wrong) --
SCALE = {0: (13, 4), 1: (16, 3), 2: (17, 2), 3: (18, 0), 4: (19, -6), 5: (20, -20)}
FILLED, DOUBT = 0.50, 0.30      # fill ratio: ticked / ambiguous zone


def find_marks(gray):
    """Locate the 4 black registration squares (one per image quadrant)."""
    h, w = gray.shape
    bw = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255,
                       cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
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
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    found = []
    for cx, cy in corners:
        if not cands:
            raise ValueError("registration squares not found")
        best = min(cands, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        found.append(best)
    if len(set(found)) < 4:
        raise ValueError("could not find 4 distinct registration squares")
    return np.float32(found)


def rectify(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    src = find_marks(gray)
    dst = np.float32([(x * PX_PER_MM, y * PX_PER_MM) for x, y in MARKS])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, M, (PAGE_W * PX_PER_MM, PAGE_H * PX_PER_MM),
                               flags=cv2.INTER_AREA, borderValue=255)


def fill_ratio(page, x_mm, y_mm):
    cx, cy, r = int(x_mm * PX_PER_MM), int(y_mm * PX_PER_MM), int(R_READ * PX_PER_MM)
    mask = np.zeros(page.shape, np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    vals = page[mask > 0]
    return float((vals < 140).mean())


def pick(ratios):
    """ratios: list of fill ratios -> (index or None, flag)."""
    ticked = [i for i, r in enumerate(ratios) if r >= FILLED]
    doubt = [i for i, r in enumerate(ratios) if DOUBT <= r < FILLED]
    if len(ticked) == 1 and not doubt:
        return ticked[0], ""
    if len(ticked) == 0 and not doubt:
        return None, ""
    if len(ticked) == 1:
        return ticked[0], "faint extra mark"
    if not ticked and len(doubt) == 1:
        return None, "faint mark, not counted"
    return None, "multiple marks"


def read_sheet(img):
    page = rectify(img)
    flags = []
    digits = []
    for i in range(N_DIGITS):
        d, f = pick([fill_ratio(page, *id_xy(i, d)) for d in range(10)])
        digits.append("?" if d is None else str(d))
        if d is None:
            flags.append(f"ID digit {i + 1}: {f or 'blank'}")
        elif f:
            flags.append(f"ID digit {i + 1}: {f}")
    rows = []
    for q in range(N_Q):
        line = []
        for ln in (0, 1):
            a, fa = pick([fill_ratio(page, *ans_xy(q, ln, k)) for k in range(6)])
            c, fc = pick([fill_ratio(page, *dc_xy(q, ln, j)) for j in range(6)])
            line.append((None if a is None else ANS_CODES[a], c, fa, fc))
        rows.append(line)
    return "".join(digits), rows, flags, page


def final_choice(line):
    """Second line replaces the first for the answer and/or the certainty."""
    (a1, c1, fa1, fc1), (a2, c2, fa2, fc2) = line
    ans = a2 if a2 is not None else a1
    dc = c2 if c2 is not None else c1
    fl = [f"1st answer {fa1}" if fa1 else "", f"1st DC {fc1}" if fc1 else "",
          f"2nd answer {fa2}" if fa2 else "", f"2nd DC {fc2}" if fc2 else ""]
    return ans, dc, [f for f in fl if f]


def score(ans, dc, key):
    """Blank answer = 0 point. Answer without DC is scored as DC 0 (assumption)."""
    if ans is None:
        return 0
    right, wrong = SCALE[0 if dc is None else dc]
    return right if ans == key else wrong


def debug_image(page, path):
    out = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)
    pts = [id_xy(i, d) for i in range(N_DIGITS) for d in range(10)]
    for q in range(N_Q):
        for ln in (0, 1):
            pts += [ans_xy(q, ln, k) for k in range(6)] + [dc_xy(q, ln, j) for j in range(6)]
    for x, y in pts:
        r = fill_ratio(page, x, y)
        col = (0, 160, 0) if r >= FILLED else (0, 165, 255) if r >= DOUBT else (200, 200, 200)
        cv2.circle(out, (int(x * PX_PER_MM), int(y * PX_PER_MM)), int(R_READ * PX_PER_MM), col, 2)
    cv2.imwrite(path, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--key", required=True, help="correct answers, e.g. 3,6,7,4,2")
    ap.add_argument("--csv", help="write results to this CSV file")
    ap.add_argument("--debug", action="store_true", help="save <image>.debug.png")
    args = ap.parse_args()
    key = [int(k) for k in args.key.split(",")]
    if len(key) != N_Q:
        sys.exit(f"--key needs {N_Q} values")
    table = []
    for path in args.images:
        img = cv2.imread(path)
        if img is None:
            print(f"{path}: cannot read image"); continue
        try:
            sid, rows, flags, page = read_sheet(img)
        except ValueError as e:
            print(f"{path}: {e}"); continue
        total, cells = 0, []
        for q, line in enumerate(rows):
            ans, dc, fl = final_choice(line)
            p = score(ans, dc, key[q]); total += p
            flags += [f"Q{q + 1}: {f}" for f in fl]
            if ans is None: flags.append(f"Q{q + 1}: no answer")
            elif dc is None: flags.append(f"Q{q + 1}: no certainty (scored as DC 0)")
            cells += [ans, dc, p]
        table.append([path, sid] + cells + [total, "; ".join(flags)])
        print(f"{path}  ID={sid}  total={total}/{20 * N_Q}  grade={max(0, total) / (N_Q * 20) * 20:.1f}/20"
              + (f"  [{'; '.join(flags)}]" if flags else ""))
        if args.debug:
            debug_image(page, path.rsplit(".", 1)[0] + ".debug.png")
    if args.csv and table:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "student_id"] + [f"q{q}_{c}" for q in range(1, N_Q + 1)
                        for c in ("answer", "dc", "points")] + ["total", "flags"])
            w.writerows(table)


if __name__ == "__main__":
    main()
