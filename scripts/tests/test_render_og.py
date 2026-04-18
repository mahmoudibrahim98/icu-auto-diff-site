from pathlib import Path
from scripts.render_og import render_og


def test_og_shape(tmp_path):
    out = tmp_path / "og.png"
    render_og(out)
    from PIL import Image
    im = Image.open(out)
    assert im.size == (1200, 630)
