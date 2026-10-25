"""v8: the picker (docs/EVAL_V8.md): the row-integrity term, the structure
prior, the fitted judge weights, and the fit / diagnosis tooling.

Offline: no rendering, no eval data; the Level 3 sample and small synthetic
designs are enough."""

import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from engine import analyze as A
from engine import resize as RZ
from engine import score as S
from engine.geometry import Box

INPUT = Path(__file__).resolve().parent.parent / "input"


def load_sample(name):
    t = json.loads((INPUT / name).read_text())
    return t["source"], t["target_canvas"]


def _text(eid, x, y, w, h, content, size, **kw):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "rotation": 0, "opacity": 1,
          "z_index": 5, "group_id": None, "content": content, "font_family": "Solstice Sans", "font_size": size,
          "color": "#111111", "text_align": "left", "line_height": 1.2}
    el.update(kw)
    return el


def _shape(eid, x, y, w, h, fill="#dddddd", z=1, **kw):
    el = {"id": eid, "type": "shape", "x": x, "y": y, "width": w, "height": h, "rotation": 0, "opacity": 1,
          "z_index": z, "group_id": None, "shape_type": "rectangle", "fill_color": fill}
    el.update(kw)
    return el


def _image(eid, x, y, w, h, z=2):
    return {"id": eid, "type": "image", "x": x, "y": y, "width": w, "height": h, "rotation": 0, "opacity": 1,
            "z_index": z, "group_id": None, "asset_id": "solstice_product_bottle.png", "fit": "contain"}


def badge_row_design():
    """A headline, a hero, a CTA pill and three badge pills side by side (a
    sibling row of three parts)."""
    els = [_shape("bg", 0, 0, 1000, 1000, "#ffffff", z=0),
           _text("head", 100, 60, 800, 160, "BIG SUMMER SALE", 96, text_align="center"),
           _image("hero", 250, 240, 500, 380),
           _shape("cta_bg", 350, 650, 300, 90, "#222222", z=3),
           _text("cta_l", 370, 670, 260, 50, "SHOP NOW", 36, text_align="center", color="#ffffff", z_index=4)]
    for i, x in enumerate((100, 400, 700)):
        els.append(_shape(f"b{i}_bg", x, 820, 200, 80, "#ff6600", z=3))
        els.append(_text(f"b{i}_l", x + 20, 835, 160, 50, f"{20 + 10 * i}% OFF", 32, text_align="center", z_index=4))
    return {"canvas": {"width": 1000, "height": 1000}, "elements": els}


def _row(an):
    rows = [u for u in an.units if u.is_row]
    assert len(rows) == 1, [u.key for u in an.units]
    return rows[0]


def _move(design, ids, dx, dy):
    out = copy.deepcopy(design)
    for el in out["elements"]:
        if el["id"] in ids:
            el["x"] += dx
            el["y"] += dy
    return out


# ---------------------------------------------------------------------------
# 1. row integrity


def test_source_badge_row_is_a_row_unit_and_scores_one():
    src = badge_row_design()
    an = A.analyze(src)
    row = _row(an)
    assert len(row.parts) == 3 and row.role == A.BADGE, (row.role, [p.ids for p in row.parts])
    sc = S.score_design(an, src, src, render=False)
    assert sc.breakdown["faith.rows"] == pytest.approx(1.0)
    assert "faith.rows" in S.WEIGHTS and S.WEIGHTS["faith.rows"] > 0


def test_corner_scatter_and_uneven_rows_lose_the_term():
    src = badge_row_design()
    an = A.analyze(src)
    kept = S.score_design(an, src, src, render=False).breakdown["faith.rows"]
    # the three badges spread over the whole bottom edge: gaps of 2.5 x their height
    spread = _move(src, ("b0_bg", "b0_l"), -100, 0)
    spread = _move(spread, ("b2_bg", "b2_l"), 100, 0)
    sc = S.score_design(an, src, spread, render=False).breakdown["faith.rows"]
    assert sc < 0.5 < kept
    # two badges pinned to the two bottom corners, one lifted to the top-right corner: scatter
    scattered = _move(spread, ("b1_bg", "b1_l"), 400, -800)
    assert S.score_design(an, src, scattered, render=False).breakdown["faith.rows"] < 0.05
    # one badge lifted out of the line: no longer one row
    lifted = _move(src, ("b1_bg", "b1_l"), 0, -300)
    assert S.score_design(an, src, lifted, render=False).breakdown["faith.rows"] < kept
    # uneven gaps: the middle badge slides toward the first
    uneven = _move(src, ("b1_bg", "b1_l"), -80, 0)
    assert S.score_design(an, src, uneven, render=False).breakdown["faith.rows"] < kept


def test_a_row_may_become_a_tight_column():
    """On a strip the row stacks; that is still one line of parts."""
    src = badge_row_design()
    an = A.analyze(src)
    col = copy.deepcopy(src)
    by = {e["id"]: e for e in col["elements"]}
    for i in range(3):
        for suffix, dx in (("_bg", 0), ("_l", 20)):
            el = by[f"b{i}{suffix}"]
            el["x"] = 400 + dx
            el["y"] = 700 + i * 95 + (15 if suffix == "_l" else 0)
    assert S.score_design(an, src, col, render=False).breakdown["faith.rows"] >= 0.9


def test_level3_square_keeps_the_badge_row():
    """docs/EVAL_V7.md §7: the corner plan beat the row plan on the square by
    layout.size; the row term settles it. Every judged corner plan scores 0
    on the term and the winner keeps the three badges in one line."""
    src, _ = load_sample("chameleon_sample_level3_advanced.json")
    an = A.analyze(src)
    row = next(u for u in an.units if u.is_row)
    best, judged = RZ.resize_with_candidates(src, {"width": 1080, "height": 1080})
    corner = [j for j in judged if "corner" in j.name]
    assert corner and all(j.score.breakdown["faith.rows"] < 0.05 for j in corner)
    assert judged[0].score.breakdown["faith.rows"] >= 0.9
    by = {e["id"]: e for e in best["elements"]}
    parts = [Box.union(Box.of(by[i]) for i in p.ids) for p in row.parts]
    ys = [p.cy for p in parts]
    assert max(ys) - min(ys) < 0.5 * min(p.h for p in parts)


# ---------------------------------------------------------------------------
# 2. structure prior


def test_structure_prior_rule():
    assert S.structure_prior("floorplan", 2.0, True) == S.STRUCTURE_PRIOR > 0
    assert S.structure_prior("floorplan", 2.0, False) == 0.0
    assert S.structure_prior("floorplan", 1.2, True) == 0.0          # a small shape change: no prior
    assert S.structure_prior("structure", 2.0, True, survives=True) == 0.0
    assert S.structure_prior("structure", 2.0, True, survives=False) == S.STRUCTURE_PRIOR
    assert S.structure_prior("anchor", 2.0, True) == 0.0            # anchors already pay the adaptation penalty
    clean = S.Score(90.0, [], {"read.size": 0.9, "read.lines": 1.0})
    assert S.structure_survives(clean)
    assert not S.structure_survives(S.Score(90.0, ["x off canvas"], {"read.size": 0.9, "read.lines": 1.0}))
    assert not S.structure_survives(S.Score(90.0, [], {"read.size": 0.5, "read.lines": 1.0}))   # copy halved
    assert not S.structure_survives(S.Score(90.0, [], {"read.size": 0.9, "read.lines": 0.6}))   # headline on 5 lines
    assert not S.structure_survives(S.Score(90.0, [], {"read.size": 0.9, "read.presence": 0.3}))  # product a sticker


def test_structure_prior_is_applied_to_templates_and_their_refinements():
    src, _ = load_sample("chameleon_sample_level2_core.json")
    _, judged = RZ.resize_with_candidates(src, {"width": 1600, "height": 400})   # 1080x1080 -> banner: a big shape change
    survivors = [j for j in judged if j.strategy == "structure" and S.structure_survives(j.score)]
    assert survivors, "Level 2 -> 1600x400 has a surviving structure candidate (the flipped band)"
    for j in judged:
        paid = j.score.notes.get("structure_prior", 0.0) or j.score.notes.get("prior", 0.0)
        if j.strategy == "floorplan" or (j.strategy == "structure" and j not in survivors):
            assert paid == pytest.approx(S.STRUCTURE_PRIOR), j.name
            assert j.score.penalty >= S.STRUCTURE_PRIOR - 1e-6
        else:
            assert "structure_prior" not in j.score.notes and not paid, j.name


def test_no_prior_without_a_clean_structure_candidate(monkeypatch):
    """When every structure candidate has a hard fail (or none exists) the
    templates pay nothing."""
    src, _ = load_sample("chameleon_sample_level1_warmup.json")
    from engine import candidates as CND

    orig = CND.detect_structure
    monkeypatch.setattr(CND, "detect_structure", lambda *a, **k: None)
    _, judged = RZ.resize_with_candidates(src, {"width": 160, "height": 600})
    assert not any(j.strategy == "structure" for j in judged)
    assert all("structure_prior" not in j.score.notes for j in judged)
    monkeypatch.setattr(CND, "detect_structure", orig)


# ---------------------------------------------------------------------------
# 3. the fitted weights file and the fit tooling


def test_shipped_weights_cover_every_component_and_load():
    w = S.load_weights(S.WEIGHTS_FILE) if S.WEIGHTS_FILE.exists() else None
    if w is None:
        pytest.skip("no engine/score_weights.json shipped")
    assert set(w) == set(S.HAND_WEIGHTS)
    assert all(v >= 0.99 for v in w.values())                 # the 1 % floor
    assert sum(w.values()) == pytest.approx(100.0, abs=0.05)
    assert S.WEIGHTS == w                                     # loaded at import


def test_fit_judge_pairs_and_rerank_on_a_toy_dump(tmp_path):
    from eval import fit_judge as F

    comps = list(S.HAND_WEIGHTS)
    rng = np.random.default_rng(0)

    def cand(rank, agreement, fam="floorplan", fallback=False, hard=()):
        bd = {k: float(rng.uniform(0.3, 1.0)) for k in comps}
        return {"rank": rank, "name": f"c{rank}", "strategy": fam, "fallback": fallback, "family": fam, "opt": False,
                "total": 50.0 - rank, "hard": list(hard), "penalty": 0.0, "breakdown": bd,
                "agreement": agreement, "da": {"da_order_tau": 0.5, "da_pos_err": 0.1}, "design": {}}

    rows = []
    for d in range(4):
        cands = [cand(0, 0.5), cand(1, 0.8), cand(2, 0.52), cand(3, 0.9, fallback=True), cand(4, 0.95, hard=["x"])]
        rows.append({"name": f"d{d}", "format": "100x100", "holdout": d == 3, "tgt_family": "square", "ratio_change": 2.0,
                     "reference": {"breakdown": {k: 1.0 for k in comps}, "hard": [], "penalty": 0.0, "total": 100.0},
                     "candidates": cands, "weights": dict(S.HAND_WEIGHTS)})
    recs = F.pairs_from_dump(rows, comps, margin=0.05)
    kinds = {r["kind"] for r in recs}
    assert kinds == {"designer", "candidate"}
    # the fallback and the hard-failing candidate never enter a pair
    assert all(r["a"]["hard"] == r["b"]["hard"] for r in recs)
    assert sum(r["weight"] for r in recs if r["kind"] == "designer" and r["design_id"] == "d0") == pytest.approx(1.0)
    assert sum(r["weight"] for r in recs if r["kind"] == "candidate" and r["design_id"] == "d0") == pytest.approx(1.0)
    # candidate pairs respect the margin (0.5 vs 0.52 is not a pair)
    cp = [r for r in recs if r["kind"] == "candidate" and r["design_id"] == "d0"]
    assert len(cp) == 2
    P = F.build(recs, comps)
    assert P.X.shape == (len(recs), len(comps))
    # re-ranking reproduces the judge's rule: the stored total order with the stored weights
    w = rows[0]["weights"]
    picked = F.rerank(rows[0], w)
    assert picked is max(rows[0]["candidates"], key=lambda c: F.total_under(c, w))
    st = F.rerank_stats(rows, lambda r: r["candidates"][0])
    assert st["n"] == 4 and 0.0 <= st["agreement"] <= 1.0 and st["gap_to_best"] >= 0.0


def test_env_switch_restores_hand_weights(monkeypatch):
    monkeypatch.setenv("CHAMELEON_SCORE_WEIGHTS", "0")
    assert S.load_weights() is None
