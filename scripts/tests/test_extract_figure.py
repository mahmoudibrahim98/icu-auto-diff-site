from pathlib import Path
from scripts.extract_figure import extract_first_image_on_page

FIXTURE = Path(__file__).parent / "fixtures" / "camera-ready.pdf"


def test_extract_workflow_figure(tmp_path):
    out = tmp_path / "architecture.png"
    extract_first_image_on_page(FIXTURE, page_index=4, out_path=out)  # Fig 1 is on page 5 (0-indexed 4)
    assert out.exists()
    assert out.stat().st_size > 5_000  # plausible PNG size
