"""Contact sheet of one design across every playground preset (dev tool).

    .venv/bin/python -m eval.sanity_sheet <design> <out_dir> [--prefix name] [--label "engine v3"]

`<design>` is a sample task file (input/*.json, the `source` key is used), an
eval design id (eval/data/designs/<id>.json) or any design JSON. Writes
<prefix>_source.png, one <prefix>_<WxH>.json + .png per preset and
<prefix>_sheet.png (the grid with preset names and run times), like the
docs/sanity_v2 sheets. Renders use the organizers' renderer directly.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR  # noqa: E402
from eval.run_eval import load_presets  # noqa: E402

ASSETS_DIR = ROOT / "brand_kit" / "assets"
FONTS_DIR = ROOT / "brand_kit" / "fonts"
BG = (245, 241, 234)
INK = (34, 34, 34)
GREY = (120, 120, 120)

_renderer = None


def render(design: dict, max_size: int = 520) -> Image.Image | None:
    global _renderer
    try:
        from renderer.converter.convert import _get_renderer, convert_chameleon_to_crello

        if _renderer is None:
            _renderer = _get_renderer(str(FONTS_DIR))
        example, _ = convert_chameleon_to_crello(design, _renderer.font_manager, str(ASSETS_DIR))
        png = _renderer.render(example, max_size=max_size, format="png")
        img = Image.open(io.BytesIO(png))
        img.load()
        return img.convert("RGB")
    except Exception:
        return None


def _font(size: int, bold: bool = False):
    name = "SolsticeSans-Bold.ttf" if bold else "SolsticeSans-Regular.ttf"
    try:
        return ImageFont.truetype(str(FONTS_DIR / name), size)
    except OSError:
        return ImageFont.load_default()


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    s = min(w / img.width, h / img.height, 1.0)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def load_design(spec: str) -> tuple[dict, str]:
    p = Path(spec)
    if not p.exists():
        p = DATA_DIR / "designs" / f"{spec}.json"
    doc = json.loads(p.read_text())
    title = doc.get("meta", {}).get("title") or doc.get("task_id") or p.stem
    return (doc["source"] if "source" in doc else doc), str(title)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design")
    ap.add_argument("out_dir")
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--label", default="engine v3")
    ap.add_argument("--cell", type=int, default=440)
    a = ap.parse_args(argv)
    from engine.resize import resize_with_candidates

    source, title = load_design(a.design)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = a.prefix or Path(a.design).stem
    src_img = render(source)
    if src_img is not None:
        src_img.save(out / f"{prefix}_source.png")
    presets = load_presets()
    cell, pad, head = a.cell, 24, 30
    cols = 4
    rows = (len(presets) + cols - 1) // cols
    sheet = Image.new("RGB", (pad + cols * (cell + pad), 60 + rows * (cell + head + pad)), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 18), f"{title} ({len(source['elements'])} elements)  ·  source {source['canvas']['width']}x"
                      f"{source['canvas']['height']}  ·  {a.label}", fill=INK, font=_font(24, True))
    f_name, f_small = _font(18, True), _font(16)
    for i, (name, w, h) in enumerate(presets):
        t0 = time.perf_counter()
        best, judged = resize_with_candidates(source, {"width": w, "height": h})
        ms = (time.perf_counter() - t0) * 1000.0
        (out / f"{prefix}_{w}x{h}.json").write_text(json.dumps(best))
        img = render(best)
        r, c = divmod(i, cols)
        x, y = pad + c * (cell + pad), 60 + r * (cell + head + pad)
        d.rectangle([x, y, x + cell, y + cell], outline=(205, 205, 205))
        if img is not None:
            img.save(out / f"{prefix}_{w}x{h}.png")
            th = _fit(img, cell, cell)
            sheet.paste(th, (x + (cell - th.width) // 2, y + (cell - th.height) // 2))
        win = judged[0].name if judged else "?"
        hard = "; ".join(judged[0].score.hard)[:40] if judged and judged[0].score.hard else ""
        d.text((x, y + cell + 6), f"{name}  {w}x{h}", fill=INK, font=f_name)
        d.text((x + cell - 90, y + cell + 8), f"{ms:.0f} ms", fill=GREY, font=f_small)
        d.text((x, y + cell + 28 - 4), (win + ("  HARD: " + hard if hard else ""))[:60], fill=GREY if not hard else (180, 30, 30), font=_font(13))
        print(f"{name:20s} {w}x{h}: {win} ({judged[0].score.total:.1f}) {ms:.0f} ms {hard}")
    sheet.save(out / f"{prefix}_sheet.png")
    print(f"wrote {out / (prefix + '_sheet.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
