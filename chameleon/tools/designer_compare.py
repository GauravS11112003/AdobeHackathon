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
from eval.metrics import designer_agreement  # noqa: E402

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


def label_record(name, src_path, source, W, H, an, s_ref, ref, winner):
    """One weak calibration pair in eval/data/labels.jsonl's record format
    (eval/labeling.py): side a = the designer reference, side b = the
    engine's winner for the same case, decision "a", kind "weak". The
    reference's score comes from the engine's own scorer, like a candidate's."""
    from eval.labeling import _record, side_from_judged

    a_side = {"id": "designer", "name": "designer reference", "strategy": "designer",
              "total": round(float(s_ref.total), 3), "hard": list(s_ref.hard),
              "penalty": round(float(s_ref.penalty), 3),
              "breakdown": {k: round(float(v), 4) for k, v in s_ref.breakdown.items()}, "design": ref}
    b_side = side_from_judged(winner)
    row = {"id": name, "file": str(src_path), "title": source.get("title", name)}
    rec = _record("designer", row, f"{W}x{H}", {"width": W, "height": H}, source, a_side, b_side)
    rec.update({"decision": "a", "kind": "weak", "ts": time.time(),
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S"), "engine_winner": winner.name,
                # the source is a designer source, not a harness design: path from the repo root
                "source_file": str(src_path)})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="")
    ap.add_argument("--no-sheets", action="store_true")
    ap.add_argument("--out", default="", help="write results under docs/designer/compare/<out>/ instead")
    ap.add_argument("--labels", default="", help="also write weak calibration pairs (reference > engine winner) to this jsonl")
    a = ap.parse_args()
    labels: list[dict] = []
    global CMP
    if a.out:
        CMP = CMP / a.out
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
            # Designer agreement (v6, eval/metrics.designer_agreement): the
            # winner's, and the best any judged candidate reaches (what the
            # generator can produce vs what the judge picks).
            da = designer_agreement(eng, ref, an)
            best_da, best_name, best_rank = da.get("da_agreement", 0.0), judged[0].name if judged else "", 0
            for rank, j in enumerate(judged):
                v = designer_agreement(j.design, ref, an).get("da_agreement", 0.0)
                if v > best_da + 1e-9:
                    best_da, best_name, best_rank = v, j.name, rank
            row = {"name": name, "format": f"{W}x{H}", "engine_winner": judged[0].name if judged else "",
                   "engine_s": round(dt, 2),
                   "ref_score": round(s_ref.total, 1), "ref_hard": list(s_ref.hard), "ref_breakdown": s_ref.breakdown,
                   "eng_score": round(s_eng.total, 1), "eng_hard": list(s_eng.hard), "eng_breakdown": s_eng.breakdown,
                   "ref": st_ref, "eng": st_eng, **da,
                   "da_best": round(best_da, 4), "da_best_name": best_name, "da_best_rank": best_rank,
                   "candidates": [{"name": j.name, "strategy": j.strategy, "total": round(j.score.total, 2),
                                   "hard": len(j.score.hard)} for j in judged]}
            rows.append(row)
            if a.labels and judged:
                labels.append(label_record(name, src_path, source, W, H, an, s_ref, ref, judged[0]))
            if not a.no_sheets:
                cells.append((f"{W}x{H}", rend(source, 480), rend(ref), rend(eng), row))
            print(f"{name} {W}x{H}: ref {row['ref_score']} ({len(row['ref_hard'])}) vs eng {row['eng_score']} ({len(row['eng_hard'])})  headline {st_ref['headline_px']} vs {st_eng['headline_px']}  hull {st_ref['hull_cover']:.2f} vs {st_eng['hull_cover']:.2f}  agreement {da.get('da_agreement', 0):.2f} (best {best_da:.2f} {best_name[:24]})", flush=True)
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
    if a.labels:
        Path(a.labels).parent.mkdir(parents=True, exist_ok=True)
        Path(a.labels).write_text("\n".join(json.dumps(r) for r in labels) + "\n")
        print("wrote", len(labels), "designer pairs to", a.labels)
    # summary
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else float("nan")
    by_fmt: dict[str, list] = {}
    for r in rows:
        by_fmt.setdefault(r["format"], []).append(r)
    def fmt_key(kv):
        return -int(kv[0].split("x")[0]) * int(kv[0].split("x")[1])

    n_ref_hard = sum(bool(r["ref_hard"]) for r in rows)
    agree = mean([r.get("da_agreement") for r in rows])
    best = mean([r.get("da_best") for r in rows])
    wins = sum(r["ref_score"] > r["eng_score"] for r in rows)
    lines = ["# Designer references vs engine", "",
             f"{len(rows)} (design, format) pairs. Scores are the engine's own scorer (no pixels).", "",
             f"**Headline numbers:** designer agreement of the engine's winner **{agree:.3f}** (best judged candidate "
             f"{best:.3f}); references tripping a hard fail **{n_ref_hard}/{len(rows)}**; designer scores higher in "
             f"{wins}/{len(rows)}; engine hard fails {sum(bool(r['eng_hard']) for r in rows)}/{len(rows)}.", "",
             "| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | designer hard fails | engine hard fails |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f, rs in sorted(by_fmt.items(), key=fmt_key):
        lines.append(f"| {f} | {len(rs)} | {mean([r['ref_score'] for r in rs]):.1f} | {mean([r['eng_score'] for r in rs]):.1f} | "
                     f"{sum(r['ref_score'] > r['eng_score'] for r in rs)}/{len(rs)} | {mean([r['ref']['headline_px'] for r in rs]):.0f} | {mean([r['eng']['headline_px'] for r in rs]):.0f} | "
                     f"{mean([r['ref']['hull_cover'] for r in rs]):.2f} | {mean([r['eng']['hull_cover'] for r in rs]):.2f} | {mean([r['ref']['min_font'] for r in rs]):.0f} | {mean([r['eng']['min_font'] for r in rs]):.0f} | "
                     f"{sum(bool(r['ref_hard']) for r in rs)} | {sum(bool(r['eng_hard']) for r in rs)} |")
    lines += ["", "## Designer agreement (eval/metrics.designer_agreement; 1 = the reference itself)", "",
              "| format | n | agreement (winner) | agreement (best candidate) | winner is best | centre error | within 10 % | reading-order tau | size rho | winner >= 0.7 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f, rs in sorted(by_fmt.items(), key=fmt_key):
        lines.append(f"| {f} | {len(rs)} | {mean([r.get('da_agreement') for r in rs]):.3f} | {mean([r.get('da_best') for r in rs]):.3f} | "
                     f"{sum(r.get('da_best_rank') == 0 for r in rs)}/{len(rs)} | {mean([r.get('da_pos_err') for r in rs]):.3f} | "
                     f"{mean([r.get('da_within10') for r in rs]):.2f} | {mean([r.get('da_order_tau') for r in rs]):.2f} | "
                     f"{mean([r.get('da_size_rho') for r in rs]):.2f} | {sum((r.get('da_agreement') or 0) >= 0.7 for r in rs)}/{len(rs)} |")
    lines.append(f"| **all** | {len(rows)} | {agree:.3f} | {best:.3f} | {sum(r.get('da_best_rank') == 0 for r in rows)}/{len(rows)} | "
                 f"{mean([r.get('da_pos_err') for r in rows]):.3f} | {mean([r.get('da_within10') for r in rows]):.2f} | "
                 f"{mean([r.get('da_order_tau') for r in rows]):.2f} | {mean([r.get('da_size_rho') for r in rows]):.2f} | "
                 f"{sum((r.get('da_agreement') or 0) >= 0.7 for r in rows)}/{len(rows)} |")
    by_name: dict[str, list] = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r)
    lines += ["", "### By design", "", "| design | n | agreement (winner) | agreement (best) | winner >= 0.7 | structure wins | designer hard fails |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for nm, rs in sorted(by_name.items(), key=lambda kv: mean([r.get("da_agreement") for r in kv[1]])):
        lines.append(f"| {nm} | {len(rs)} | {mean([r.get('da_agreement') for r in rs]):.3f} | {mean([r.get('da_best') for r in rs]):.3f} | "
                     f"{sum((r.get('da_agreement') or 0) >= 0.7 for r in rs)}/{len(rs)} | "
                     f"{sum('structure' in (r.get('engine_winner') or '') for r in rs)}/{len(rs)} | {sum(bool(r['ref_hard']) for r in rs)} |")
    lines += ["", "## Designer references that still trip a hard fail", ""]
    for r in rows:
        if r["ref_hard"]:
            lines.append(f"- {r['name']} {r['format']}: {'; '.join(r['ref_hard'])}")
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
