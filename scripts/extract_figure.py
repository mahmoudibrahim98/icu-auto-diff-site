"""Extract the first embedded image from a given PDF page and write as PNG."""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def extract_first_image_on_page(pdf: Path, page_index: int, out_path: Path) -> None:
    reader = PdfReader(str(pdf))
    page = reader.pages[page_index]
    images = page.images
    if not images:
        raise RuntimeError(f"No embedded images found on page {page_index}")
    img = images[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # pypdf gives us .data + .name; use the raw bytes directly.
    out_path.write_bytes(img.data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--page", type=int, required=True,
                    help="0-indexed page number")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    extract_first_image_on_page(args.pdf, args.page, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
