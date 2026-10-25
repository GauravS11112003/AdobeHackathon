"""Weak preference pairs from the designer references (v7).

Two kinds of pairs, both in the labels format of eval/labeling.py (a / b
sides with the scorer's breakdown and the full design, a decision, a kind):

  perturbation pairs   PRISM-style one-principle damage to a reference:
                       misalign one member of an alignment group, shrink a
                       headline / CTA below the floor, break one proximity
                       group, swap two neighbours in reading order, move a
                       text onto the hero. Reference > perturbed copy.
                       -> eval/data/labels_designer_perturb.jsonl (kind "weak",
                          field "perturbation")
  designer pairs       the reference against the engine's own output for the
                       same source and target. Reference > engine.
                       -> eval/data/labels_designer_engine.jsonl (kind "designer"),
                          written only when the file does not exist yet

Every record carries `source_file` (so eval/calibrate.py --energy can
recompute the energy terms), `holdout` (docs/designer2/holdout_ids.json:
those pairs are reported, never fitted) and the batch.

    .venv/bin/python -m eval.perturb_designer                 # both kinds
    .venv/bin/python -m eval.perturb_designer --no-engine     # perturbations only
    .venv/bin/python -m eval.perturb_designer --names a,b --seed 1
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHAMELEON_NO_RENDER", "1")

from engine.analyze import BODY, CTA, HEADLINE, HERO, IMAGE, SUBHEAD, Analysis, analyze  # noqa: E402
from engine.geometry import Box, clamp  # noqa: E402
from engine.relations import X_LINES, Relations, relations  # noqa: E402
from engine.score import score_design  # noqa: E402
from engine.textfit import apply_font_size  # noqa: E402
from eval.labeling import DATA_DIR, _record, append_label, side_from_judged  # noqa: E402

DOCS = ROOT.parent / "docs"
BATCHES = (DOCS / "designer", DOCS / "designer2")
HOLDOUT_FILE = DOCS / "designer2" / "holdout_ids.json"
PERTURB_FILE = DATA_DIR / "labels_designer_perturb.jsonl"
DESIGNER_FILE = DATA_DIR / "labels_designer_engine.jsonl"   # tools/designer_compare.py --labels owns labels.designer.jsonl

MISALIGN_FRAC = 0.04       # one member of an alignment group slides this x the canvas span off its line
SHRINK_FONT = 0.55         # a headline / CTA font x this
BREAK_FRAC = 0.12          # one neighbour of a proximity pair moves this x the span away
PERTURBATIONS = ("misalign", "shrink_text", "break_prox", "swap_order", "busy")


@dataclass
class Ref:
    name: str
    batch: str
    W: int
    H: int
    source_file: str          # relative to the repo root (AdobeHack/)
    source: dict[str, Any]
    design: dict[str, Any]
    holdout: bool


def holdout_ids() -> set[str]:
    try:
        return set(json.loads(HOLDOUT_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def references(batches=BATCHES, names: set[str] | None = None) -> list[Ref]:
    hold = holdout_ids()
    out: list[Ref] = []
    for batch in batches:
        specs = batch / "specs"
        if not specs.exists():
            continue
        for sp in sorted(specs.glob("*__*.json")):
            name, size = sp.stem.rsplit("__", 1)
            if names and name not in names:
                continue
            ref_path = batch / "out" / f"{sp.stem}.json"
            if not ref_path.exists():
                continue
            spec = json.loads(sp.read_text())
            src_path = Path(spec["source"])
            full = src_path if src_path.is_absolute() else ROOT.parent / src_path
            try:
                doc = json.loads(full.read_text())
                design = json.loads(ref_path.read_text())
            except (OSError, ValueError):
                continue
            W, H = (int(v) for v in spec.get("target") or size.split("x"))
            rel = str(full.relative_to(ROOT.parent)) if full.is_relative_to(ROOT.parent) else str(full)
            out.append(Ref(name, batch.name, W, H, rel, doc.get("source", doc), design, name in hold))
    return out


# ---------------------------------------------------------------------------
# perturbations (unit level: a group moves as one piece)


def _unit_elements(analysis: Analysis, by_id: dict[str, dict[str, Any]], key: str) -> list[dict[str, Any]]:
    u = analysis.unit(key)
    return [by_id[i] for i in u.ids if i in by_id]

def _unit_box(els: list[dict[str, Any]]) -> Box:
    return Box.union(Box.of(e) for e in els)


def _shift(els: list[dict[str, Any]], dx: float, dy: float, canvas: Box) -> bool:
    """Move the elements, clamped so their hull stays on canvas. False when
    nothing moved."""
    hull = _unit_box(els)
    dx = clamp(dx, -hull.x, canvas.w - hull.right)
    dy = clamp(dy, -hull.y, canvas.h - hull.bottom)
    if abs(dx) < 1.0 and abs(dy) < 1.0:
        return False
    for e in els:
        e["x"] = round(float(e["x"]) + dx, 2)
        e["y"] = round(float(e["y"]) + dy, 2)
    return True


def perturb_misalign(design, analysis, rel: Relations, rng, canvas) -> bool:
    groups = [(line, g) for line, gs in rel.alignments.items() for g in gs if len(g) >= 2]
    if not groups:
        return False
    line, g = rng.choice(groups)
    key = rng.choice(g)
    by_id = {e["id"]: e for e in design["elements"]}
    els = _unit_elements(analysis, by_id, key)
    hull = _unit_box(els)
    if line in X_LINES:
        d = MISALIGN_FRAC * canvas.w
        d = d if canvas.w - hull.right >= hull.x else -d
        return _shift(els, d, 0.0, canvas)
    d = MISALIGN_FRAC * canvas.h
    d = d if canvas.h - hull.bottom >= hull.y else -d
    return _shift(els, 0.0, d, canvas)


def perturb_shrink_text(design, analysis, rel, rng, canvas) -> bool:
    texts = [e for e in design["elements"] if e["type"] == "text" and analysis.roles.get(e["id"]) in (HEADLINE, CTA)]
    if not texts:
        return False
    el = rng.choice(texts)
    apply_font_size(el, max(1.0, float(el["font_size"]) * SHRINK_FONT))
    return True


def perturb_break_prox(design, analysis, rel: Relations, rng, canvas) -> bool:
    pairs = sorted(rel.proximity.items())
    if not pairs:
        return False
    (a, b), axis = rng.choice(pairs)
    later = max((a, b), key=lambda k: rel.reading.get(k, 0))
    other = a if later == b else b
    by_id = {e["id"]: e for e in design["elements"]}
    els = _unit_elements(analysis, by_id, later)
    ba, bo = rel.boxes[later], rel.boxes[other]
    if axis == "y":
        d = BREAK_FRAC * canvas.h * (1.0 if ba.cy >= bo.cy else -1.0)
        return _shift(els, 0.0, d, canvas)
    d = BREAK_FRAC * canvas.w * (1.0 if ba.cx >= bo.cx else -1.0)
    return _shift(els, d, 0.0, canvas)


def perturb_swap_order(design, analysis, rel: Relations, rng, canvas) -> bool:
    pairs = sorted(rel.proximity.items())
    if not pairs:
        return False
    (a, b), axis = rng.choice(pairs)
    first, second = sorted((a, b), key=lambda k: rel.reading.get(k, 0))
    by_id = {e["id"]: e for e in design["elements"]}
    ea, eb = _unit_elements(analysis, by_id, first), _unit_elements(analysis, by_id, second)
    va, vb = rel.boxes[first], rel.boxes[second]
    if axis == "y":
        g = vb.y - va.bottom
        ok1 = _shift(eb, 0.0, va.y - vb.y, canvas)
        ok2 = _shift(ea, 0.0, vb.h + g, canvas)
    else:
        g = vb.x - va.right
        ok1 = _shift(eb, va.x - vb.x, 0.0, canvas)
        ok2 = _shift(ea, vb.w + g, 0.0, canvas)
    return ok1 or ok2


def perturb_busy(design, analysis, rel: Relations, rng, canvas) -> bool:
    """Move a text onto the hero (a busy region)."""
    by_id = {e["id"]: e for e in design["elements"]}
    pictures = [u for u in analysis.content_units() if u.role in (HERO, IMAGE) and u.key in rel.boxes]
    texts = [u for u in analysis.content_units() if u.role in (HEADLINE, SUBHEAD, BODY, CTA) and u.key in rel.boxes
             and any(by_id.get(i, {}).get("type") == "text" for i in u.ids)]
    if not pictures or not texts:
        return False
    pic = max(pictures, key=lambda u: rel.boxes[u.key].area)
    pb = rel.boxes[pic.key]
    t = rng.choice(texts)
    tb = rel.boxes[t.key]
    if pb.contains_fraction(tb) >= 0.5:
        return False     # already on it: nothing to break
    els = _unit_elements(analysis, by_id, t.key)
    return _shift(els, pb.cx - tb.cx, pb.cy - tb.cy, canvas)


PERTURB_FN = {"misalign": perturb_misalign, "shrink_text": perturb_shrink_text, "break_prox": perturb_break_prox,
              "swap_order": perturb_swap_order, "busy": perturb_busy}


def perturbations(ref: Ref, analysis: Analysis, rng: random.Random) -> list[tuple[str, dict[str, Any]]]:
    canvas = Box(0.0, 0.0, float(ref.W), float(ref.H))
    rel = relations(analysis, ref.design["elements"], canvas)
    out = []
    for name in PERTURBATIONS:
        design = copy.deepcopy(ref.design)
        try:
            changed = PERTURB_FN[name](design, analysis, rel, rng, canvas)
        except Exception:
            changed = False
        if changed and design != ref.design:
            out.append((name, design))
    return out


# ---------------------------------------------------------------------------
# records


def side(name: str, design: dict[str, Any], analysis: Analysis, source: dict[str, Any], target: Box,
         strategy: str | None = None) -> dict[str, Any]:
    sc = score_design(analysis, source, design, target, render=False, strategy=strategy)
    return {"id": name, "name": name, "strategy": strategy or "", "total": round(float(sc.total), 3),
            "hard": list(sc.hard), "penalty": round(float(sc.penalty), 3),
            "breakdown": {k: round(float(v), 4) for k, v in sc.breakdown.items()}, "design": design}


def _row(ref: Ref) -> dict[str, Any]:
    return {"id": ref.name, "file": "", "title": ref.name}


def write_pairs(refs: list[Ref], *, seed: int = 0, perturb_path: Path = PERTURB_FILE,
                designer_path: Path | None = DESIGNER_FILE, engine: bool = True, log=print) -> dict[str, int]:
    rng = random.Random(seed)
    counts = {"perturb": 0, "designer": 0, "refs": len(refs)}
    if perturb_path.exists():
        perturb_path.unlink()
    write_designer = engine and designer_path is not None and not designer_path.exists()
    if engine and not write_designer:
        log(f"{designer_path} exists: designer pairs kept as they are")
    analyses: dict[str, Analysis] = {}
    for i, ref in enumerate(refs):
        an = analyses.get(ref.source_file)
        if an is None:
            an = analyses[ref.source_file] = analyze(ref.source)
        target = Box(0.0, 0.0, float(ref.W), float(ref.H))
        tdict = {"width": ref.W, "height": ref.H}
        extra = {"source_file": ref.source_file, "holdout": ref.holdout, "batch": ref.batch}
        good = side("designer", ref.design, an, ref.source, target)
        for pname, bad_design in perturbations(ref, an, rng):
            bad = side(f"perturbed:{pname}", bad_design, an, ref.source, target)
            if rng.random() < 0.5:
                a, b, decision = good, bad, "a"
            else:
                a, b, decision = bad, good, "b"
            rec = _record("designer_perturb", _row(ref), f"{ref.W}x{ref.H}", tdict, ref.source, a, b,
                          perturbation=pname, seed=seed, **extra)
            append_label(rec, decision, perturb_path, kind="weak")
            counts["perturb"] += 1
        if write_designer:
            from engine.resize import resize_with_candidates
            try:
                _, judged = resize_with_candidates(ref.source, tdict)
            except Exception as exc:
                log(f"engine failed on {ref.name} {ref.W}x{ref.H}: {exc!r}")
                judged = []
            if judged:
                eng = side_from_judged(judged[0])
                eng["id"] = "engine"
                if rng.random() < 0.5:
                    a, b, decision = good, eng, "a"
                else:
                    a, b, decision = eng, good, "b"
                rec = _record("designer", _row(ref), f"{ref.W}x{ref.H}", tdict, ref.source, a, b,
                              engine_winner=judged[0].name, seed=seed, **extra)
                append_label(rec, decision, designer_path, kind="designer")
                counts["designer"] += 1
        if (i + 1) % 20 == 0:
            log(f"{i + 1}/{len(refs)} references, {counts['perturb']} perturbation pairs, {counts['designer']} designer pairs")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--names", default="", help="comma-separated design names (default: all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-engine", action="store_true", help="perturbation pairs only")
    ap.add_argument("--perturb-out", type=Path, default=PERTURB_FILE)
    ap.add_argument("--designer-out", type=Path, default=DESIGNER_FILE)
    args = ap.parse_args(argv)
    names = {n.strip() for n in args.names.split(",") if n.strip()} or None
    refs = references(names=names)
    if not refs:
        print("no designer references found under", [str(b) for b in BATCHES])
        return 1
    t0 = time.time()
    counts = write_pairs(refs, seed=args.seed, perturb_path=args.perturb_out, designer_path=args.designer_out,
                         engine=not args.no_engine, log=lambda s: print(s, flush=True))
    print(f"{counts['refs']} references ({sum(r.holdout for r in refs)} held out): {counts['perturb']} perturbation pairs -> "
          f"{args.perturb_out}, {counts['designer']} designer pairs -> {args.designer_out} in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
