#!/usr/bin/env python3
"""Column-aware PDF text extraction for claim mining.

Why this exists (generation instruction v0.9): reading a two-column PDF straight across
interleaves the columns, so quotes mined from that text are spliced from two columns and
are NOT verbatim -- they look like OCR damage but the corruption is the extractor's.

Naive fix (clip each half at the page midline) trades one bug for another: it cuts
full-width elements -- title, abstract, wide tables -- in half. So work in layout blocks
instead: a block wider than most of the page is full-width and is kept whole; everything
else is assigned to a column by its center, and blocks are emitted top-to-bottom, left
column before right.

Usage: extract_columns.py <in.pdf> <out.txt>
"""
import re, sys, unicodedata
from pathlib import Path

FULL_WIDTH = 0.60   # a block spanning >60% of the text width is not in a column


def norm_block(t: str) -> str:
    t = unicodedata.normalize('NFKC', t)
    t = re.sub(r'-\n(\w)', r'\1', t)      # rejoin hyphenated line breaks
    t = re.sub(r'\n(?![A-Z0-9(\[])', ' ', t)  # unwrap soft line breaks
    return re.sub(r'[ \t]+', ' ', t).strip()


def page_lines(page):
    blocks = [b for b in page.get_text('blocks') if (b[6] if len(b) > 6 else 0) == 0]
    if not blocks:
        return []
    x0s = [b[0] for b in blocks]
    x1s = [b[2] for b in blocks]
    left_edge, right_edge = min(x0s), max(x1s)
    span = max(right_edge - left_edge, 1.0)
    mid = (left_edge + right_edge) / 2

    full, left, right = [], [], []
    for b in blocks:
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        if not text.strip():
            continue
        if (x1 - x0) / span > FULL_WIDTH:
            full.append((y0, text))
        elif (x0 + x1) / 2 < mid:
            left.append((y0, text))
        else:
            right.append((y0, text))

    out = []
    # Full-width blocks (title/abstract) sit above the columns in every layout we hold.
    for _, t in sorted(full):
        out.append(norm_block(t))
    for col in (left, right):
        for _, t in sorted(col):
            out.append(norm_block(t))
    return [l for l in out if l]


def extract(pdf_path, out_path):
    import fitz
    doc = fitz.open(pdf_path)
    lines = []
    for i, page in enumerate(doc):
        lines.append(f'=== PDF PAGE {i + 1} ===')
        lines += page_lines(page)
    doc.close()
    Path(out_path).write_text('\n'.join(f'L{n + 1}: {l}' for n, l in enumerate(lines)))
    print(f'{out_path}: {len(lines)} lines from {pdf_path}')


if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2])
