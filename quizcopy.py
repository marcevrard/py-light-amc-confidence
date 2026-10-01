# Copyright (c) 2026 Marc Evrard. Licensed under CC BY 4.0
# (https://creativecommons.org/licenses/by/4.0/). Attribution required: cite
# Evrard, M. (2026), py-light-amc-confidence,
# https://github.com/marcevrard/py-light-amc-confidence
"""Randomised copies: one shuffled version of the quiz per student.

Shared by build_copies.py (makes the copies) and scan_reader.py (undoes the
shuffle when marking). A copy is identified by its number (0 to 1023):

  * copy 0 is the quiz exactly as written in questions.md (no shuffle);
  * copy k > 0 shuffles the order of the questions and, inside each question,
    the order of the proposed answers A-D. `n` and `all` are never shuffled.

The shuffle is a pure function of (master seed, copy number), so nothing has to
be stored: the reader recomputes it from the seed kept in <quiz folder>/seed.txt.
The copy number is printed on the answer sheet as a small binary strip.
"""

import random
import re
from dataclasses import dataclass
from pathlib import Path

N_BITS = 10
MAX_COPY = 2**N_BITS - 1
LETTERS = "ABCD"


@dataclass(frozen=True)
class Question:
    stem: str  # text after the "**Question N.**" label (may span lines)
    options: tuple  # the 4 option texts, in the order A, B, C, D
    key: str  # 'A'-'D', 'n' or 'all'


def parse_questions(text, source="questions"):
    """Parse questions.md into a list of Question (4 options + one correct answer)."""
    blocks = re.split(r"(?m)^\*\*Question\s+\d+\.\*\*", text)[1:]
    option = re.compile(r"^\\(optc?)\{([A-Da-d])\}\{(.*)\}\s*$")
    correct = re.compile(r"^\\correct\{(n|all)\}\s*$")
    questions = []
    for number, block in enumerate(blocks, 1):
        stem, options, keys = [], [], []
        for line in block.strip().splitlines():
            if m := option.match(line):
                kind, letter, body = m.groups()
                if letter.upper() != LETTERS[len(options)]:
                    raise ValueError(f"{source}: question {number}: options must be A, B, C, D in order")
                options.append(body)
                if kind == "optc":
                    keys.append(letter.upper())
            elif m := correct.match(line):
                keys.append(m.group(1))
            elif not options:
                stem.append(line)
            elif line.strip():
                raise ValueError(f"{source}: question {number}: unexpected line {line!r} after the options")
        if len(options) != 4:
            raise ValueError(f"{source}: question {number} needs 4 options, found {len(options)}")
        if len(keys) != 1:
            raise ValueError(
                f"{source}: question {number} needs exactly one correct answer "
                f"(\\optc or \\correct), found {len(keys)}"
            )
        questions.append(Question("\n".join(stem).strip(), tuple(options), keys[0]))
    return questions


def read_seed(folder):
    """Master seed stored in <folder>/seed.txt (None if the file does not exist)."""
    path = Path(folder) / "seed.txt"
    return path.read_text().strip() if path.is_file() else None


def layout(questions, seed, copy):
    """Return (qorder, oorders) for a copy.

    qorder[i]      = original index of the question printed at position i;
    oorders[o][j]  = original option index (0-3) printed at position j of the
                     question whose original index is o.

    The correct letters are balanced: the questions whose answer is one of A-D
    get their correct option placed at positions drawn without repetition (so no
    letter is the answer of two questions), as long as there are at most 4 such
    questions; with more, every letter is used once before any is reused.
    """
    n = len(questions)
    if copy == 0:
        return list(range(n)), [[0, 1, 2, 3] for _ in range(n)]
    rng = random.Random(f"{seed}:{copy}")
    qorder = sorted(range(n), key=lambda _: rng.random())
    # target position (0-3) of the correct option, for the questions keyed A-D
    lettered = [o for o, q in enumerate(questions) if q.key in LETTERS]
    rng_pos = random.Random(f"{seed}:{copy}:positions")
    pool = []
    while len(pool) < len(lettered):
        pool += sorted(range(4), key=lambda _: rng_pos.random())
    target = dict(zip(lettered, pool))
    oorders = []
    for o, q in enumerate(questions):
        rng_o = random.Random(f"{seed}:{copy}:q{o}")
        order = sorted(range(4), key=lambda _: rng_o.random())
        if o in target:
            right = LETTERS.index(q.key)
            order.remove(right)
            order.insert(target[o], right)
        oorders.append(order)
    return qorder, oorders


def render_copy(questions, seed, copy):
    """Markdown of one copy: questions and options reordered and renumbered.

    The answer key markers are dropped: the copy only holds what students see.
    """
    qorder, oorders = layout(questions, seed, copy)
    out = []
    for i, o in enumerate(qorder, 1):
        q = questions[o]
        lines = [f"**Question {i}.** {q.stem}"]
        for j, idx in enumerate(oorders[o]):
            lines.append(f"\\opt{{{LETTERS[j]}}}{{{q.options[idx]}}}")
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def original_answer(code, printed_q, qorder, oorders):
    """Student's mark -> (original question index, original answer code).

    Codes: 1-4 = A-D, 6 = n, 7 = all (as in scan_reader.py). Only A-D move.
    """
    o = qorder[printed_q]
    if 1 <= code <= 4:
        return o, oorders[o][code - 1] + 1
    return o, code


# ---- copy code printed on the sheet: sentinel + 10 bits + parity ------------------
def code_bits(copy):
    """12 values (1 = dark square): a sentinel (always 1), 10 bits MSB first, parity.

    The parity bit makes the number of dark squares among bits + parity even.
    """
    if not 0 <= copy <= MAX_COPY:
        raise ValueError(f"copy number must be between 0 and {MAX_COPY}")
    bits = [(copy >> s) & 1 for s in range(N_BITS - 1, -1, -1)]
    return [1] + bits + [sum(bits) % 2]


def decode_bits(values):
    """Inverse of code_bits. Returns the copy number, or None if the code is invalid."""
    if len(values) != N_BITS + 2 or values[0] != 1 or sum(values[1:]) % 2:
        return None
    copy = 0
    for b in values[1 : N_BITS + 1]:
        copy = copy * 2 + b
    return copy
