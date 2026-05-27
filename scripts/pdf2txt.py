#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pypdf>=4.3",
# ]
# ///
"""
Extract text from a PDF for feeding into tts.py.

Usage:
    uv run --script pdf2txt.py input.pdf [output.txt]

Writes to stdout when no output path is given. Pages are separated by a
blank line so tts.py's paragraph chunking has something to grab onto.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pypdf import PdfReader

# NBSP and its narrow/thin/figure cousins. Apple Mail's "Save as PDF" output
# (and other HTML-sourced PDFs) sprinkles these in place of regular spaces.
_NBSP_LIKE = re.compile(r"[       ]")


def _normalize(text: str) -> str:
    return _NBSP_LIKE.sub(" ", text)


def extract(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    prev_last: str | None = None
    for page in reader.pages:
        text = _normalize(page.extract_text() or "").rstrip()
        # Apple Mail's print-to-PDF repeats the last line of each page at the
        # top of the next as a continuation cue. Drop the leading duplicate.
        lines = text.split("\n")
        if prev_last is not None and lines and lines[0].strip() == prev_last:
            lines = lines[1:]
            text = "\n".join(lines)
        pages.append(text)
        # Track the last non-empty line for the next iteration.
        for line in reversed(lines):
            if line.strip():
                prev_last = line.strip()
                break
    return "\n\n".join(pages)


def main() -> int:
    ap = argparse.ArgumentParser(description="PDF → plain text")
    ap.add_argument("input", type=Path, help="Input PDF")
    ap.add_argument("output", type=Path, nargs="?", help="Output .txt (stdout if omitted)")
    args = ap.parse_args()

    text = extract(args.input)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output} ({len(text):,} chars)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
