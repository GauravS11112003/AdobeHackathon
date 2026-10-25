"""Designer layout DSL: a declarative spec -> schema-valid design JSON (+ PNG).

Used to hand-compose "what a designer would do" references for the engine
to be compared against. A spec places every element of a source design on a
target canvas using a column grid and fractions of the canvas, and lets text
be sized by font or fitted into a box. Hard rules are enforced: same ids,
content/fonts untouched, images keep aspect, everything important on canvas.

Spec (JSON):
{
  "source": "docs/designer/src_03_level3_advanced.json",   # or a design dict
  "target": [1600, 400],
  "grid": {"cols": 12, "margin": 0.05, "gutter": 0.02},     # margin/gutter: fraction of the short side
  "concept": "one line on the composition idea",
  "place": [
    {"id": "bg", "cover": true},                              # full-bleed background (any element)
    {"id": "deco_circle_1", "corner": "top-left", "scale": 1.0},   # keep its corner offset, scale by canvas ratio
    {"id": "logo", "col": [1, 3], "y": 0.08},                 # image: width from the column span, height by aspect
    {"id": "product", "col": [4, 6], "y": 0.1, "h": 0.8, "fit_box": true},   # image contained in the box
    {"id": "headline", "col": [7, 11], "y": 0.2, "font": 64, "align": "left"},   # text: height auto-measured
    {"id": "subhead", "col": [7, 11], "below": "headline", "gap": 0.02, "font": 24},   # stack under another id
    {"id": "cta_bg", "col": [7, 9], "below": "subhead", "gap": 0.04, "h": 0.14},
    {"id": "cta_label", "in": "cta_bg", "font": 22},         # text centred inside a shape (insets kept)
    {"id": "legal_text", "col": [1, 12], "anchor_y": "bottom", "margin_y": 0.03, "font": 10, "align": "center"},
    {"id": "badge1_bg", "row": "badges"}, ...                # see "rows"
  ],
  "rows": {"badges": {"col": [7, 11], "below": "cta_bg", "gap": 0.03, "item_gap": 0.015, "h": 0.1,
                      "items": [["badge1_bg", "badge1_label"], ["badge2_bg", "badge2_label"]]}}   # groups side by side
}
Positions: x/y/w/h as fractions of canvas width/height when <= 1, else px.
"x"/"w" override the column span. "y" is the top; "cy" centres; "anchor_y": "bottom" uses margin_y from the
bottom. "font" fixes the font size; "fit": true picks the largest font that fits the given box.
Every element of the source must be placed exactly once (groups via "in"/"rows" count).

CLI:
  python tools/designer_dsl.py build spec.json [-o out_dir]        -> out_dir/<spec>.json + .png + report
  python tools/designer_dsl.py sheet out_dir --name <design>      -> contact sheet of every format for a design
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.geometry import Box  # noqa: E402
from engine.textfit import default_measurer  # noqa: E402

PRESETS = [("Instagram post", 1080, 1080), ("Instagram portrait", 1080, 1350), ("Story / Reel", 1080, 1920),
           ("YouTube thumbnail", 1280, 720), ("Twitter / X post", 1600, 900), ("Facebook cover", 820, 312),
           ("LinkedIn banner", 1584, 396), ("Wide web banner", 1600, 400), ("Leaderboard ad", 728, 90),
           ("Skyscraper ad", 160, 600), ("Pinterest pin", 1000, 1500), ("A4 poster", 1240, 1754)]


class SpecError(ValueError):
    pass


def _frac(v: float | None, total: float) -> float | None:
    if v is None:
        return None
    return float(v) * total if 0 <= float(v) <= 1 else float(v)


class Composer:
    def __init__(self, spec: dict[str, Any]):
        src = spec["source"]
        if isinstance(src, str):
            cand = [Path(src)] if Path(src).is_absolute() else [ROOT / src, ROOT.parent / src, Path.cwd() / src]
            path = next((c for c in cand if c.exists()), None)
            if path is None:
                raise SpecError(f"source not found: {src}")
            doc = json.loads(path.read_text())
            src = doc["source"] if "source" in doc else doc
        self.source = src
        self.by_id = {el["id"]: el for el in src["elements"]}
        self.W, self.H = float(spec["target"][0]), float(spec["target"][1])
        self.short = min(self.W, self.H)
        g = spec.get("grid", {})
        self.cols = int(g.get("cols", 12))
        self.margin = _frac(g.get("margin", 0.05), self.short) or 0.0
        self.gutter = _frac(g.get("gutter", 0.02), self.short) or 0.0
        self.colw = (self.W - 2 * self.margin - (self.cols - 1) * self.gutter) / self.cols
        self.spec = spec
        self.m = default_measurer()
        self.out: dict[str, dict[str, Any]] = {}
        self.boxes: dict[str, Box] = {}
        self.report: list[str] = []

    # -- geometry helpers -------------------------------------------------
    def span(self, col: list[int]) -> tuple[float, float]:
        a, b = int(col[0]), int(col[1])
        if not (1 <= a <= b <= self.cols):
            raise SpecError(f"bad col span {col}")
        x = self.margin + (a - 1) * (self.colw + self.gutter)
        w = (b - a + 1) * self.colw + (b - a) * self.gutter
        return x, w

    def src_aspect(self, el: dict[str, Any]) -> float:
        return float(el["width"]) / max(float(el["height"]), 1e-6)

    # -- placement ----------------------------------------------------------
    def place_all(self) -> None:
        rows = self.spec.get("rows", {})
        pending = list(self.spec.get("place", []))
        done_ids: set[str] = set()
        # iterate until everything resolvable is placed (handles "below"/"in" order)
        progress = True
        while pending and progress:
            progress = False
            for p in list(pending):
                if p.get("row"):
                    continue
                deps = [p.get("below"), p.get("in"), p.get("right_of")]
                if any(d and d not in self.boxes for d in deps):
                    continue
                self.place_one(p)
                done_ids.add(p["id"]); pending.remove(p); progress = True
        for name, row in rows.items():
            if any(d and d not in self.boxes for d in (row.get("below"),)):
                raise SpecError(f"row {name}: 'below' target not placed")
            self.place_row(name, row)
            for item in row["items"]:
                done_ids.update(item if isinstance(item, list) else [item])
        left = [p["id"] for p in pending if not p.get("row")]
        if left:
            raise SpecError(f"unresolvable placements (circular 'below'/'in'?): {left}")
        missing = set(self.by_id) - set(self.out)
        extra = set(self.out) - set(self.by_id)
        if missing or extra:
            raise SpecError(f"not every element placed exactly once; missing={sorted(missing)} extra={sorted(extra)}")

    def _emit(self, eid: str, box: Box, font: float | None = None) -> None:
        el = copy.deepcopy(self.by_id[eid])
        el["x"], el["y"], el["width"], el["height"] = round(box.x, 2), round(box.y, 2), round(box.w, 2), round(box.h, 2)
        if font is not None and el["type"] == "text":
            el["font_size"] = float(int(font))
        self.out[eid] = el
        self.boxes[eid] = box

    def place_one(self, p: dict[str, Any]) -> None:
        eid = p["id"]
        if eid not in self.by_id:
            raise SpecError(f"unknown id {eid}")
        el = self.by_id[eid]
        if p.get("cover"):
            self._emit(eid, Box(0, 0, self.W, self.H)); return
        if p.get("corner"):
            self._place_corner(p, el); return
        if p.get("in"):
            self._place_in(p, el); return
        # x / width
        if "col" in p:
            x, w = self.span(p["col"])
        else:
            x = _frac(p.get("x", 0.0), self.W) or 0.0
            w = _frac(p.get("w"), self.W) or float(el["width"])
        if "w" in p and "col" in p:
            w = _frac(p["w"], self.W) or w
        if "x" in p and "col" in p:
            x = _frac(p["x"], self.W) or x
        # height / font
        h = _frac(p.get("h"), self.H)
        font = None
        if el["type"] == "image":
            asp = self.src_aspect(el)
            if h is None:
                h = w / asp
            elif p.get("fit_box"):
                # contain the image's aspect inside w x h
                bw, bh = w, h
                if bw / bh > asp:
                    w = bh * asp
                    x = x + (bw - w) / 2 if p.get("center", True) else x
                else:
                    h = bw / asp
            else:
                w = h * asp
        elif el["type"] == "text":
            lh = float(el.get("line_height", 1.2) or 1.2)
            if p.get("fit") and h:
                font = self.m.fit_font_size(el, w, h, max_size=p.get("max_font", 400), min_size=6)
            else:
                font = float(p.get("font", el["font_size"]))
            if "font" in p and "w" not in p and "col" not in p:
                pass
            lay = self.m.layout(el, font, w)
            if lay.max_width > w + 0.5:   # a single word wider than the span: widen
                w = lay.max_width + 2
            if h is None:
                h = lay.height + 2
        else:  # shape
            if h is None:
                h = float(el["height"]) * (w / float(el["width"]))
        # y
        if p.get("below"):
            ref = self.boxes[p["below"]]
            y = ref.bottom + (_frac(p.get("gap", 0.02), self.H) or 0.0)
        elif p.get("anchor_y") == "bottom":
            y = self.H - (_frac(p.get("margin_y", 0.04), self.H) or 0.0) - h
        elif "cy" in p:
            y = (_frac(p["cy"], self.H) or 0.0) - h / 2
        else:
            y = _frac(p.get("y", 0.0), self.H) or 0.0
        if p.get("right_of"):
            ref = self.boxes[p["right_of"]]
            x = ref.right + (_frac(p.get("gap", 0.02), self.W) or 0.0)
        if p.get("align_x") == "center":
            x = (self.W - w) / 2
        elif p.get("align_x") == "right":
            x = self.W - self.margin - w
        self._emit(eid, Box(x, y, w, h), font)
        if el["type"] == "text" and p.get("align"):
            self.out[eid]["text_align"] = p["align"]

    def _place_corner(self, p: dict[str, Any], el: dict[str, Any]) -> None:
        sb = Box.of(el); sw, sh = float(self.source["canvas"]["width"]), float(self.source["canvas"]["height"])
        s = float(p.get("scale", 1.0)) * self.short / min(sw, sh)
        w, h = sb.w * s, sb.h * s
        cx = "left" if "left" in p["corner"] else "right"; cy = "top" if "top" in p["corner"] else "bottom"
        x = sb.x * s if cx == "left" else self.W - (sw - sb.right) * s - w
        y = sb.y * s if cy == "top" else self.H - (sh - sb.bottom) * s - h
        self._emit(p["id"], Box(x, y, w, h))

    def _place_in(self, p: dict[str, Any], el: dict[str, Any]) -> None:
        host = self.boxes[p["in"]]
        font = float(p.get("font", el["font_size"])) if el["type"] == "text" else None
        inset = _frac(p.get("inset", 0.0), self.short) or 0.0
        w = host.w - 2 * inset
        if el["type"] == "text":
            if p.get("fit", True):
                font = self.m.fit_font_size(el, w, host.h - 2 * inset, max_size=font or 400, min_size=6)
            lay = self.m.layout(el, font, w)
            h = lay.height + 1
            y = host.y + (host.h - h) / 2
            self._emit(p["id"], Box(host.x + inset, y, w, h), font)
            self.out[p["id"]]["text_align"] = p.get("align", "center")
        else:
            h = host.h - 2 * inset
            self._emit(p["id"], Box(host.x + inset, host.y + inset, w, h))

    def place_row(self, name: str, row: dict[str, Any]) -> None:
        x0, wspan = self.span(row["col"]) if "col" in row else (self.margin, self.W - 2 * self.margin)
        h = _frac(row.get("h", 0.08), self.H) or 0.0
        gap = _frac(row.get("item_gap", 0.015), self.W) or 0.0
        if row.get("below"):
            y = self.boxes[row["below"]].bottom + (_frac(row.get("gap", 0.03), self.H) or 0.0)
        elif row.get("anchor_y") == "bottom":
            y = self.H - (_frac(row.get("margin_y", 0.04), self.H) or 0.0) - h
        else:
            y = _frac(row.get("y", 0.0), self.H) or 0.0
        items = row["items"]
        # natural widths: scale each item's host (first id) to height h keeping aspect
        widths = []
        for item in items:
            ids = item if isinstance(item, list) else [item]
            host = self.by_id[ids[0]]
            widths.append(h * float(host["width"]) / max(float(host["height"]), 1e-6))
        total = sum(widths) + gap * (len(items) - 1)
        scale = min(1.0, wspan / total) if total > 0 else 1.0
        if scale < 1.0:
            widths = [w * scale for w in widths]; h *= scale; total = sum(widths) + gap * (len(items) - 1)
        align = row.get("align", "left")
        x = x0 if align == "left" else (x0 + (wspan - total) / 2 if align == "center" else x0 + wspan - total)
        for item, w in zip(items, widths):
            ids = item if isinstance(item, list) else [item]
            host_box = Box(x, y, w, h)
            self._emit(ids[0], host_box)
            for lab in ids[1:]:
                lab_el = self.by_id[lab]
                f0 = float(lab_el["font_size"]) if lab_el["type"] == "text" else None
                f = self.m.fit_font_size(lab_el, w * 0.9, h * 0.8, max_size=row.get("font", f0 or 400), min_size=6) if lab_el["type"] == "text" else None
                if lab_el["type"] == "text":
                    lay = self.m.layout(lab_el, f, w * 0.9)
                    self._emit(lab, Box(x + w * 0.05, y + (h - lay.height - 1) / 2, w * 0.9, lay.height + 1), f)
                    self.out[lab]["text_align"] = "center"
                else:
                    self._emit(lab, Box(x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8))
            x += w + gap

    # -- output ---------------------------------------------------------------
    def design(self) -> dict[str, Any]:
        ordered = [self.out[el["id"]] for el in self.source["elements"]]
        return {"canvas": {"width": int(self.W), "height": int(self.H)}, "elements": ordered}

    def validate(self) -> list[str]:
        probs: list[str] = []
        for el in self.design()["elements"]:
            src = self.by_id[el["id"]]
            b = Box.of(el)
            important = not (src["type"] == "shape" and float(src.get("opacity", 1)) < 0.35)
            if important and (b.x < -0.5 or b.y < -0.5 or b.right > self.W + 0.5 or b.bottom > self.H + 0.5):
                probs.append(f"{el['id']} off canvas")
            if src["type"] == "image" and src.get("fit", "contain") != "cover":
                a0, a1 = self.src_aspect(src), b.w / max(b.h, 1e-6)
                if abs(a1 / a0 - 1) > 0.05:
                    probs.append(f"{el['id']} aspect drift {a1/a0:.2f}")
            if src["type"] == "text":
                lay = self.m.layout(el, float(el["font_size"]), float(el["width"]))
                if lay.max_width > el["width"] + 0.5 or lay.height > el["height"] + 0.5:
                    probs.append(f"{el['id']} text overflow ({lay.n_lines} lines)")
        # overlaps between texts and other content (ignore bg/decorative)
        els = [e for e in self.design()["elements"] if not (self.by_id[e["id"]]["type"] == "shape" and float(self.by_id[e["id"]].get("opacity", 1)) < 0.35) and not Box.of(e).contains_fraction(Box(0, 0, self.W, self.H)) > 0.9]
        for i in range(len(els)):
            for j in range(i + 1, len(els)):
                a, b = els[i], els[j]
                if a.get("group_id") and a.get("group_id") == b.get("group_id"):
                    continue
                if self.by_id[a["id"]]["type"] != "text" and self.by_id[b["id"]]["type"] != "text":
                    continue
                ba, bb = Box.of(a), Box.of(b)
                inter = ba.intersection_area(bb)
                if inter > 0.02 * min(ba.area, bb.area) and min(ba.area, bb.area) > 0:
                    # allow text inside a shape that hosts it in the source (same group handled); flag otherwise
                    probs.append(f"{a['id']} overlaps {b['id']}")
        return probs


def build(spec_path: Path, out_dir: Path, render: bool = True) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text())
    c = Composer(spec)
    c.place_all()
    design = c.design()
    probs = c.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = spec_path.stem
    (out_dir / f"{stem}.json").write_text(json.dumps(design, indent=1))
    if render:
        import os
        os.environ.setdefault("CHAMELEON_RENDER", "1")
        from engine.render import render_design
        img = render_design(design, max_size=1200)
        if img is None:
            from renderer.converter.convert import render_design_to_png
            render_design_to_png(design, ROOT / "brand_kit" / "assets", str(out_dir / f"{stem}.png"))
        else:
            img.convert("RGB").save(out_dir / f"{stem}.png")
    rep = {"spec": str(spec_path), "problems": probs, "concept": spec.get("concept", "")}
    (out_dir / f"{stem}.report.json").write_text(json.dumps(rep, indent=1))
    return rep


def sheet(out_dir: Path, name: str, title: str = "") -> Path:
    from PIL import Image, ImageDraw, ImageFont
    files = sorted(out_dir.glob(f"{name}__*.png"))
    font = ImageFont.truetype(str(ROOT / "brand_kit/fonts/SolsticeSans-Bold.ttf"), 20)
    small = ImageFont.truetype(str(ROOT / "brand_kit/fonts/SolsticeSans-Regular.ttf"), 14)
    CW, CH, PAD = 420, 420, 18; cols = 4; rows = math.ceil(len(files) / cols)
    im = Image.new("RGB", (cols * (CW + PAD) + PAD, 50 + rows * (CH + 50 + PAD)), "#f3efe8"); d = ImageDraw.Draw(im)
    d.text((PAD, 12), f"DESIGNER reference · {title or name}", fill="#222", font=font)
    for i, f in enumerate(files):
        r, c = divmod(i, cols); x0 = PAD + c * (CW + PAD); y0 = 50 + r * (CH + 50 + PAD)
        img = Image.open(f).convert("RGB"); s = min(CW / img.width, CH / img.height)
        t = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
        ox, oy = x0 + (CW - t.width) // 2, y0 + (CH - t.height) // 2
        im.paste(t, (ox, oy)); d.rectangle([ox - 1, oy - 1, ox + t.width, oy + t.height], outline="#888")
        rep = json.loads(f.with_suffix(".report.json").read_text()) if f.with_suffix(".report.json").exists() else {}
        label = f.stem.split("__", 1)[1] if "__" in f.stem else f.stem
        d.text((x0, y0 + CH + 6), label, fill="#222", font=small)
        if rep.get("problems"):
            d.text((x0, y0 + CH + 24), ("! " + "; ".join(rep["problems"]))[:60], fill="#a33", font=small)
    out = out_dir / f"{name}__SHEET.png"; im.save(out); return out


def main() -> None:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("specs", nargs="+"); b.add_argument("-o", "--out", default="docs/designer/out"); b.add_argument("--no-render", action="store_true")
    s = sub.add_parser("sheet"); s.add_argument("out"); s.add_argument("--name", required=True); s.add_argument("--title", default="")
    a = ap.parse_args()
    if a.cmd == "build":
        bad = 0
        for sp in a.specs:
            try:
                rep = build(Path(sp), Path(a.out), render=not a.no_render)
                flag = "OK " if not rep["problems"] else "!! "
                print(f"{flag}{sp}: {'; '.join(rep['problems']) or 'clean'}")
                bad += bool(rep["problems"])
            except SpecError as e:
                print(f"ERR {sp}: {e}"); bad += 1
        sys.exit(1 if bad else 0)
    else:
        print(sheet(Path(a.out), a.name, a.title))


if __name__ == "__main__":
    main()
