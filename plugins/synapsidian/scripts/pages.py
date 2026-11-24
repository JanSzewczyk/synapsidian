#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2", "pypdfium2>=5.14", "pillow>=11"]
# ///
"""PDF pages as images, for Claude to read charts, scans and layouts the text layer garbles.

  pages.py FILE.pdf [--pages 1-3,6] [--scale 1.5] [--max 20]

Renders with PDFium (the pypdfium2 wheel; no poppler needed) into
<vault>/.git/synapsidian/pages/<file hash>/page-NNN.jpg. Folders older than two days are removed on
every run; git never sees them. Prints {"ok", "pages": total, "images": [{"page", "path"}], "dir"}.
Exit 2 = bad input, 4 = the file can't be opened as a PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

from synapsidianlib import config

KEEP_SECONDS = 2 * 24 * 3600


def fail(code: int, message: str) -> None:
    print(json.dumps({"ok": False, "error": message}))
    sys.exit(code)


def page_numbers(spec: str | None, total: int, limit: int) -> list[int]:
    """1-based page numbers from '1-3,6' (all pages when empty), capped at `limit`."""
    if not spec:
        return list(range(1, min(total, limit) + 1))
    wanted: list[int] = []
    for part in spec.split(","):
        first, _, last = part.strip().partition("-")
        try:
            start, end = int(first), int(last or first)
        except ValueError:
            fail(2, f"--pages expects ranges like 1-3,6, got {spec!r}")
        wanted += [n for n in range(start, end + 1) if 1 <= n <= total and n not in wanted]
    return wanted[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    parser.add_argument("file")
    parser.add_argument("--pages", help="e.g. 1-3,6 (default: all, up to --max)")
    parser.add_argument("--scale", type=float, default=1.5, help="1.0 = 72 dpi")
    parser.add_argument("--max", type=int, default=20)
    args = parser.parse_args()

    source = Path(args.file).expanduser()
    if not source.is_file():
        fail(2, f"{args.file} is not a file")
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(source)
    except pdfium.PdfiumError as exc:
        fail(4, f"cannot open {source.name} as a PDF: {exc}")

    vault_root = config.vault_path(args.vault)
    base = config.state_dir(vault_root) if vault_root and vault_root.is_dir() else config.data_dir()
    root = base / "pages"
    root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - KEEP_SECONDS
    for folder in root.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
    workdir = root / hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    workdir.mkdir(exist_ok=True)

    images = []
    for number in page_numbers(args.pages, len(pdf), args.max):
        target = workdir / f"page-{number:03d}.jpg"
        if not target.exists():
            pdf[number - 1].render(scale=args.scale).to_pil().convert("RGB").save(target, quality=80)
        images.append({"page": number, "path": str(target)})
    print(json.dumps({"ok": True, "pages": len(pdf), "images": images, "dir": str(workdir)}))


if __name__ == "__main__":
    main()
