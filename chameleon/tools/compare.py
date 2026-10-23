"""Dev renders for the docs: side-by-side source vs engine output, and a
contact sheet of every judged candidate with its score.

    .venv/bin/python tools/compare.py compare <out_dir> [--label "JUDGE v1"] [--target WxH] [task.json ...]
    .venv/bin/python tools/compare.py sheet <out_dir> [--target WxH] [task.json ...]

Dev tool only - not part of the submission (the Dockerfile does not copy tools/).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.render import render_design  # noqa: E402
from engine.resize import resize_with_candidates  # noqa: E402

BG = (245, 241, 234)
INK = (34, 34, 34)
GREEN = (20, 150, 80)
FONT_PATH = ROOT / "brand_kit" / "fonts" / "SolsticeSans-Bold.ttf"


def font(size: int):
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()


def _fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    s = min(max_w / img.width, max_h / img.height, 1.0)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def compare(source: dict, output: dict, label: str, path: Path) -> None:
    src_img = render_design(source, max_size=1000)
    out_img = render_design(output, max_size=1000)
    pad, top, cell = 40, 60, 900
    sheet = Image.new("RGB", (cell * 2 + pad * 3, cell + top + pad), BG)
    d = ImageDraw.Draw(sheet)
    f = font(28)
    for i, (img, text, color) in enumerate(((src_img, f"SOURCE {source['canvas']['width']}x{source['canvas']['height']}", INK),
                                            (out_img, f"{label} -> {output['canvas']['width']}x{output['canvas']['height']}", GREEN))):
        x = pad + i * (cell + pad)
        d.text((x, 20), text, fill=color, font=f)
        thumb = _fit(img, cell, cell)
        sheet.paste(thumb, (x, top))
    sheet.save(path)


def sheet(source: dict, judged, path: Path, cols: int = 3, cell: int = 520) -> None:
    rows = (len(judged) + cols - 1) // cols
    pad, head = 24, 86
    W = cols * (cell + pad) + pad
    H = rows * (cell + head + pad) + pad
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_name, f_small = font(17), font(14)
    for i, j in enumerate(judged):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + head + pad)
        color = GREEN if i == 0 else INK
        d.text((x, y), f"#{i + 1}  {j.score.total:.1f}  {j.name}"[:58], fill=color, font=f_name)
        bd = j.score.breakdown
        line1 = "  ".join(f"{k.split('.')[1][:5]}={v:.2f}" for k, v in bd.items() if k.startswith("read") or k.startswith("layout"))
        line2 = "  ".join(f"{k.split('.')[1][:5]}={v:.2f}" for k, v in bd.items() if k.startswith("faith"))
        d.text((x, y + 24), line1, fill=INK, font=f_small)
        d.text((x, y + 42), line2, fill=INK, font=f_small)
        if j.score.hard:
            d.text((x, y + 60), "HARD: " + "; ".join(j.score.hard)[:90], fill=(180, 30, 30), font=f_small)
        render = render_design(j.design, max_size=1000)
        if render is not None:
            thumb = _fit(render, cell, cell)
            img.paste(thumb, (x, y + head))
            d.rectangle([x - 1, y + head - 1, x + thumb.width, y + head + thumb.height], outline=(200, 200, 200))
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["compare", "sheet"])
    ap.add_argument("out_dir")
    ap.add_argument("--label", default="JUDGE v1")
    ap.add_argument("--target", default=None, help="WxH override")
    ap.add_argument("tasks", nargs="*")
    a = ap.parse_intermixed_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [Path(t) for t in a.tasks] or sorted((ROOT / "input").glob("*.json"))
    for tp in tasks:
        task = json.loads(tp.read_text())
        source = task["source"]
        target = task["target_canvas"]
        suffix = ""
        if a.target:
            w, h = a.target.lower().split("x")
            target = {"width": int(w), "height": int(h)}
            suffix = f"_{w}x{h}"
        best, judged = resize_with_candidates(source, target)
        if a.mode == "compare":
            p = out / f"{tp.stem}{suffix}_compare.png"
            compare(source, best, a.label, p)
        else:
            p = out / f"{tp.stem}{suffix}_candidates.png"
            sheet(source, judged, p)
        print(f"{tp.stem}{suffix}: best = {judged[0].name} ({judged[0].score.total:.1f}) -> {p}")


if __name__ == "__main__":
    main()
