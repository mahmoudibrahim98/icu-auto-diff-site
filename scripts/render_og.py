"""Render the OG preview image (1200x630) at assets/img/og-image.png."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def render_og(out_path: Path) -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    # Teal left band
    d.rectangle([0, 0, 40, H], fill="#2b7a78")
    # Try Inter if installed; fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 54)
        body_font  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        mono_font  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 24)
    except OSError:
        title_font = body_font = mono_font = ImageFont.load_default()

    d.text((96, 100),
           "Enabling Granular Subgroup Level Model Evaluations",
           fill="#14202e", font=title_font)
    d.text((96, 176),
           "by Generating Synthetic Medical Time Series",
           fill="#14202e", font=title_font)
    d.text((96, 280),
           "Enhanced TimeAutoDiff reduces real-on-synthetic evaluation gap",
           fill="#4a5a6e", font=body_font)
    d.text((96, 320),
           "by >70%; outperforms small real test sets in 72–84% of subgroups.",
           fill="#4a5a6e", font=body_font)
    d.text((96, 500),
           "SynDAiTE Workshop · ECML PKDD 2025 · arXiv:2510.19728",
           fill="#2b7a78", font=mono_font)
    img.save(out_path, "PNG", optimize=True)


if __name__ == "__main__":
    render_og(Path("assets/img/og-image.png"))
    print("wrote assets/img/og-image.png")
