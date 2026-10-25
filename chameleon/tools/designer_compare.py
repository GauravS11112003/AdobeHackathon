"""Compare the engine's output with the hand-composed designer references.

For every designer spec in docs/designer/specs (<name>__<W>x<H>.json) this runs the
current engine on the same source and target, renders both, scores both with the
engine's own scorer, and computes a few layout statistics that explain *why* they
differ. Writes:

  docs/designer/compare/<name>__COMPARE.png      source | designer | engine, per format
  docs/designer/compare/results.jsonl            one row per (design, format)
  docs/designer/compare/SUMMARY.md               aggregate gaps

Run:  cd chameleon && CHAMELEON_RENDER=1 .venv/bin/python tools/designer_compare.py [--names a,b] [--no-sheets]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHAMELEON_RENDER", "1")

from engine.analyze import analyze  # noqa: E402
from engine.geometry import Box  # noqa: E402
from engine.render import render_design  # noqa: E402
from engine.resize import resize_with_candidates  # noqa: E402
from engine.score import score_design  # noqa: E402

DOCS = ROOT.parent / "docs" / "designer"
SPECS, OUT, CMP = DOCS / "specs", DOCS / "out", DOCS / "compare"


def rend(design, max_size=720):
    img = render_design(design, max_size=max_size)
    if img is None:
        from PIL import Image
        from renderer.converter.convert import render_design_to_png
        import tempfile
        p = tempfile.mktemp(suffix=".png")
        render_design_to_png(design, ROOT / "brand_kit" / "assets", p, max_size=max_size)
        img = Image.open(p)
    return img.convert("RGB")


def stats(source, design, roles):
    """Layout statistics that explain differences: headline size, content hull,
    min font, number of distinct left edges among text, hero share."""
    W, H = float(design["canvas"]["width"]), float(design["canvas"]["height"])
    by = {e["id"]: e for e in design["elements"]}
    texts = [e for e in design["elements"] if e["type"] == "text"]
    content = [e for e in design["elements"] if roles.get(e["id"]) not in ("background", "decorative")]
    hull = Box.union([Box.of(e) for e in content]) if content else Box(0, 0, 0, 0)
    head = [e for e in texts if roles.get(e["id"]) == "headline"]
    hero = [e for e in design["elements"] if roles.get(e["id"]) == "hero"]
    cta = [e for e in design["elements"] if roles.get(e["id"]) == "cta" and e["type"] == "text"]
    lefts = sorted({round(e["x"] / W, 2) for e in texts})
    return {
        "headline_px": head[0]["font_size"] if head else None,
        "headline_rel": (head[0]["font_size"] / max(W, H)) if head else None,
        "cta_px": cta[0]["font_size"] if cta else None,
        "min_font": min((e["font_size"] for e in texts), default=None),
        "hull_cover": (hull.w * hull.h) / (W * H) if content else 0.0,
        "hull_cx": hull.cx / W if content else 0.5,
        "hull_cy": hull.cy / H if content else 0.5,
        "hero_share": (hero[0]["width"] * hero[0]["height"]) / (W * H) if hero else None,
        "text_left_edges": len(lefts),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="")
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args()
    CMP.mkdir(parents=True, exist_ok=True)
    names = sorted({p.stem.split("__")[0] for p in SPECS.glob("*__*.json")})
    if a.names:
        names = [n for n in names if n in a.names.split(",")]
    rows = []
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(ROOT / "brand_kit/fonts/SolsticeSans-Bold.ttf"), 20)
    small = ImageFont.truetype(str(ROOT / "brand_kit/fonts/SolsticeSans-Regular.ttf"), 13)
    for name in names:
        specs = sorted(SPECS.glob(f"{name}__*.json"))
        cells = []
        for sp in specs:
            spec = json.loads(sp.read_text())
            src_path = spec["source"]
            src_doc = json.loads((ROOT.parent / src_path).read_text()) if not Path(src_path).is_absolute() else json.loads(Path(src_path).read_text())
            source = src_doc["source"] if "source" in src_doc else src_doc
            ref_path = OUT / f"{sp.stem}.json"
            if not ref_path.exists():
                continue
            ref = json.loads(ref_path.read_text())
            W, H = spec["target"]
            t0 = time.time()
            eng, judged = resize_with_candidates(source, {"width": W, "height": H})
            dt = time.time() - t0
            an = analyze(source)
            roles = {eid: u.role for u in an.units for eid in u.ids}
            s_ref = score_design(an, source, ref, render=False)
            s_eng = score_design(an, source, eng, render=False)
            st_ref, st_eng = stats(source, ref, roles), stats(source, eng, roles)
            row = {"name": name, "format": f"{W}x{H}", "engine_winner": judged[0].name if judged else "",
                   "engine_s": round(dt, 2),
                   "ref_score": round(s_ref.total, 1), "ref_hard": list(s_ref.hard), "ref_breakdown": s_ref.breakdown,
                   "eng_score": round(s_eng.total, 1), "eng_hard": list(s_eng.hard), "eng_breakdown": s_eng.breakdown,
                   "ref": st_ref, "eng": st_eng}
            rows.append(row)
            if not a.no_sheets:
                cells.append((f"{W}x{H}", rend(source, 480), rend(ref), rend(eng), row))
            print(f"{name} {W}x{H}: ref {row['ref_score']} ({len(row['ref_hard'])}) vs eng {row['eng_score']} ({len(row['eng_hard'])})  headline {st_ref['headline_px']} vs {st_eng['headline_px']}  hull {st_ref['hull_cover']:.2f} vs {st_eng['hull_cover']:.2f}")
        if cells and not a.no_sheets:
            CW, CH, PAD, LBL = 400, 300, 14, 44
            sheet = Image.new("RGB", (3 * CW + 4 * PAD + 120, 50 + len(cells) * (CH + LBL + PAD)), "#f3efe8")
            d = ImageDraw.Draw(sheet)
            d.text((PAD, 12), f"{name}: SOURCE | DESIGNER reference | ENGINE (current)", fill="#222", font=font)
            for i, (lab, s, r, e, row) in enumerate(cells):
                y0 = 50 + i * (CH + LBL + PAD)
                d.text((PAD, y0 + CH // 2 - 8), lab, fill="#222", font=small)
                for k, (img, cap) in enumerate(((s, "source"), (r, f"designer · score {row['ref_score']} · hl {row['ref']['headline_px']}px · hull {row['ref']['hull_cover']:.2f}"),
                                                (e, f"engine · score {row['eng_score']} · hl {row['eng']['headline_px']}px · hull {row['eng']['hull_cover']:.2f} · {row['engine_winner'][:26]}"))):
                    x0 = 120 + PAD + k * (CW + PAD)
                    sc = min(CW / img.width, CH / img.height)
                    im = img.resize((max(1, round(img.width * sc)), max(1, round(img.height * sc))), Image.LANCZOS)
                    ox, oy = x0 + (CW - im.width) // 2, y0 + (CH - im.height) // 2
                    sheet.paste(im, (ox, oy)); d.rectangle([ox - 1, oy - 1, ox + im.width, oy + im.height], outline="#888")
                    d.text((x0, y0 + CH + 4), cap[:70], fill="#555", font=small)
                    hard = row["ref_hard"] if k == 1 else (row["eng_hard"] if k == 2 else [])
                    if hard:
                        d.text((x0, y0 + CH + 22), ("! " + "; ".join(hard))[:70], fill="#a33", font=small)
            sheet.save(CMP / f"{name}__COMPARE.png")
    (CMP / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    # summary
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else float("nan")
    by_fmt: dict[str, list] = {}
    for r in rows:
        by_fmt.setdefault(r["format"], []).append(r)
    lines = ["# Designer references vs engine", "", f"{len(rows)} (design, format) pairs. Scores are the engine's own scorer (no pixels).", "",
             "| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | engine hard fails |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f, rs in sorted(by_fmt.items(), key=lambda kv: -int(kv[0].split("x")[0]) * int(kv[0].split("x")[1])):
        lines.append(f"| {f} | {len(rs)} | {mean([r['ref_score'] for r in rs]):.1f} | {mean([r['eng_score'] for r in rs]):.1f} | "
                     f"{sum(r['ref_score'] > r['eng_score'] for r in rs)}/{len(rs)} | {mean([r['ref']['headline_px'] for r in rs]):.0f} | {mean([r['eng']['headline_px'] for r in rs]):.0f} | "
                     f"{mean([r['ref']['hull_cover'] for r in rs]):.2f} | {mean([r['eng']['hull_cover'] for r in rs]):.2f} | {mean([r['ref']['min_font'] for r in rs]):.0f} | {mean([r['eng']['min_font'] for r in rs]):.0f} | {sum(bool(r['eng_hard']) for r in rs)} |")
    comps = sorted({k for r in rows for k in r["ref_breakdown"]})
    lines += ["", "## Score components, mean (designer vs engine)", "", "| component | designer | engine | gap |", "|---|---:|---:|---:|"]
    for c in comps:
        a_, b_ = mean([r["ref_breakdown"].get(c) for r in rows]), mean([r["eng_breakdown"].get(c) for r in rows])
        lines.append(f"| {c} | {a_:.3f} | {b_:.3f} | {a_ - b_:+.3f} |")
    lines += ["", "## Engine hard fails on cases where the designer reference is clean", ""]
    for r in rows:
        if r["eng_hard"] and not r["ref_hard"]:
            lines.append(f"- {r['name']} {r['format']}: {'; '.join(r['eng_hard'])}")
    (CMP / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\nwrote", CMP / "SUMMARY.md")


if __name__ == "__main__":
    main()
