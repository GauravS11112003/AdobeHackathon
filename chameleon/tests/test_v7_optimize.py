"""v7: relational graph, design energy and the local-search optimiser.

One regression test per module plus the wiring contract:
  * relations on Level 2 (alignment group, proximity, symmetry, reading order,
    serialisable, zero loss against itself)
  * the energy is monotone on known one-principle perturbations
  * the optimiser never adds a hard fail, never raises the energy, keeps ids /
    order / immutables / image aspect, is deterministic and bounded
  * CHAMELEON_OPTIMIZE=0 leaves the judge loop byte-identical to the
    un-refined engine
"""

import copy
import json
import os
import sys
from pathlib import Path

import pytest

from engine import energy as E
from engine import optimize as O
from engine import relations as R
from engine import resize as RZ
from engine.analyze import CTA, HEADLINE, analyze
from engine.geometry import Box

INPUT = Path(__file__).resolve().parent.parent / "input"
NO_RENDER = {"CHAMELEON_NO_RENDER": "1"}


def load(name: str) -> dict:
    return json.loads((INPUT / f"chameleon_sample_{name}.json").read_text())["source"]


@pytest.fixture(autouse=True)
def _no_pixels(monkeypatch):
    monkeypatch.setattr(RZ, "JUDGE_RENDER", False)
    monkeypatch.delenv("CHAMELEON_OPTIMIZE", raising=False)
    monkeypatch.delenv("CHAMELEON_OPTIMIZE_K", raising=False)


# ---------------------------------------------------------------------------
# relations


def test_relations_on_level2_source():
    src = load("level2_core")
    an = analyze(src)
    rel = R.source_relations(an)
    assert rel.keys and set(rel.keys) == {u.key for u in an.content_units()}
    # the centred column: logo, product, headline, subhead and CTA share the vertical centre line
    cx_groups = rel.alignments["cx"]
    big = max(cx_groups, key=len)
    assert {"logo", "product", "headline", "subhead", "group:cta"} <= set(big)
    assert rel.shares_line("headline", "group:cta", "x")
    # symmetry about the vertical axis for the centred pieces, not for the corner badge
    assert rel.symmetry["headline"][0] and rel.symmetry["logo"][0]
    assert not rel.symmetry["group:badge"][0]
    # reading order: badge / logo on top, then product, headline, subhead, CTA
    assert rel.reading["product"] < rel.reading["headline"] < rel.reading["subhead"] < rel.reading["group:cta"]
    # proximity: the headline sits right under the product
    assert rel.proximity.get(("headline", "product")) == "y"
    # serialisable
    d = rel.to_dict()
    json.dumps(d)
    assert {"units", "alignments", "aligned_pairs", "proximity", "near_misses"} <= set(d)
    # the source compared with itself loses nothing
    same = R.relations(an, list(an.source_elements.values()), an.canvas)
    assert R.lost_alignments(rel, same) == []
    assert R.broken_proximity(rel, same) == []
    assert R.order_discordance(rel, same)[0] == 0.0
    assert R.lost_containment(rel, same) == [] and R.lost_symmetry(rel, same) == []


# ---------------------------------------------------------------------------
# energy


def _identity(src):
    return {"canvas": dict(src["canvas"]), "elements": copy.deepcopy(src["elements"])}


def test_energy_is_monotone_on_one_principle_perturbations():
    src = load("level2_core")
    an = analyze(src)
    canvas = an.canvas
    base = E.energy_of(an, src, _identity(src), canvas)
    assert base.hard == []
    assert set(base.terms) == set(E.WEIGHTS)
    assert all(0.0 <= v <= 1.0 for v in base.terms.values())

    # 1. misalign: slide the CTA group off the centre line
    d = _identity(src)
    for el in d["elements"]:
        if an.element_unit[el["id"]] == "group:cta":
            el["x"] = float(el["x"]) + 0.08 * canvas.w
    e = E.energy_of(an, src, d, canvas)
    assert e.terms["pres.align"] > base.terms["pres.align"]
    assert e.terms["pres.symmetry"] > base.terms["pres.symmetry"]
    assert e.total > base.total

    # 2. shrink the headline far below what the canvas affords
    d = _identity(src)
    for el in d["elements"]:
        if an.roles[el["id"]] == HEADLINE:
            el["font_size"] = float(el["font_size"]) * 0.35
    e = E.energy_of(an, src, d, canvas)
    assert e.terms["aes.read"] > base.terms["aes.read"]
    assert e.terms["aes.hier"] >= base.terms["aes.hier"]
    assert e.total > base.total

    # 3. a collision: drop the subhead onto the headline
    d = _identity(src)
    by = {el["id"]: el for el in d["elements"]}
    head = next(el for el in d["elements"] if an.roles[el["id"]] == HEADLINE)
    sub = next(el for el in d["elements"] if an.roles[el["id"]] == "subhead")
    sub["y"] = head["y"]
    e = E.energy_of(an, src, d, canvas)
    assert any(h.startswith("collide:") for h in e.hard)
    assert e.total > base.total + E.HARD / 2

    # 4. flip the reading order: CTA above the headline
    d = _identity(src)
    by = {el["id"]: el for el in d["elements"]}
    cta_ids = [el["id"] for el in d["elements"] if an.element_unit[el["id"]] == "group:cta"]
    head = next(el for el in d["elements"] if an.roles[el["id"]] == HEADLINE)
    dy = float(head["y"]) - 0.5 * canvas.h - min(float(by[i]["y"]) for i in cta_ids)
    for i in cta_ids:
        by[i]["y"] = float(by[i]["y"]) + dy
    e = E.energy_of(an, src, d, canvas)
    assert e.terms["pres.order"] > base.terms["pres.order"]


# ---------------------------------------------------------------------------
# optimiser


def _seeds(name, w, h, monkeypatch, k=3):
    monkeypatch.setenv("CHAMELEON_OPTIMIZE", "0")
    src = load(name)
    _, judged = RZ.resize_with_candidates(src, {"width": w, "height": h})
    return src, [j for j in judged if not j.fallback][:k]


@pytest.mark.parametrize("name,w,h", [("level1_warmup", 1080, 1920), ("level2_core", 160, 600),
                                      ("level2_core", 1600, 400), ("level3_advanced", 1200, 628),
                                      ("level3_advanced", 728, 90)])
def test_optimizer_never_adds_a_hard_fail_and_never_raises_the_energy(name, w, h, monkeypatch):
    src, seeds = _seeds(name, w, h, monkeypatch)
    an = analyze(src)
    target = Box(0, 0, w, h)
    src_by = {el["id"]: el for el in src["elements"]}
    for j in seeds:
        res = O.optimize(an, src, j.design["elements"], target, max_evals=120)
        assert set(res.after.hard) <= set(res.before.hard), (j.name, res.before.hard, res.after.hard)
        assert res.after.total <= res.before.total + 1e-9
        assert res.evals <= 120
        out = res.elements
        assert [e["id"] for e in out] == [e["id"] for e in src["elements"]]
        for el in out:
            s = src_by[el["id"]]
            if el["type"] == "text":
                assert el["content"] == s["content"] and el["font_family"] == s["font_family"]
                assert el["font_size"] >= 1.0
            if el["type"] == "image" and el.get("fit", "contain") != "cover" and s["height"] > 0 and el["height"] > 0:
                assert abs((el["width"] / el["height"]) / (s["width"] / s["height"]) - 1.0) <= 0.05
        # deterministic: the same seed gives the same layout and the same moves
        again = O.optimize(an, src, j.design["elements"], target, max_evals=120)
        assert again.accepted == res.accepted
        assert json.dumps(again.elements, sort_keys=True) == json.dumps(out, sort_keys=True)


def test_optimizer_removes_a_misalignment_it_is_handed():
    """A clean seed with the CTA knocked off the centre line: the optimiser
    brings it back onto a shared line (lower pres.align) without any new
    hard fail."""
    src = load("level2_core")
    an = analyze(src)
    monkeypatch_target = Box(0, 0, 1080, 1080)
    design = _identity(src)
    for el in design["elements"]:
        if an.element_unit[el["id"]] == "group:cta":
            el["x"] = float(el["x"]) + 40.0
    before = E.energy_of(an, src, design, monkeypatch_target)
    assert before.terms["pres.align"] > 0.0
    res = O.optimize(an, src, design["elements"], monkeypatch_target)
    assert res.changed
    assert res.after.terms["pres.align"] < before.terms["pres.align"]
    assert set(res.after.hard) <= set(before.hard)


# ---------------------------------------------------------------------------
# wiring


def test_flag_off_is_byte_identical_to_the_unrefined_judge(monkeypatch):
    src = load("level2_core")
    target = {"width": 1080, "height": 1920}
    monkeypatch.setenv("CHAMELEON_OPTIMIZE", "0")
    off = RZ.resize(src, target)
    assert not any("+opt" in j.name for j in RZ.LAST_JUDGED)
    monkeypatch.delenv("CHAMELEON_OPTIMIZE")
    monkeypatch.setattr(RZ, "refine", lambda judged, *a, **k: judged)
    plain = RZ.resize(src, target)
    assert json.dumps(off, sort_keys=True) == json.dumps(plain, sort_keys=True)


def test_flag_on_adds_refined_candidates_that_respect_the_seed(monkeypatch):
    src = load("level2_core")
    target = {"width": 1080, "height": 1920}
    monkeypatch.setenv("CHAMELEON_OPTIMIZE_K", "2")
    best, judged = RZ.resize_with_candidates(src, target)
    refined = [j for j in judged if j.name.endswith("+opt")]
    assert 1 <= len(refined) <= 2
    by_name = {j.name: j for j in judged}
    for j in refined:
        seed = by_name[j.name[: -len(" +opt")]]
        assert j.strategy == seed.strategy
        assert {RZ._hard_key(h) for h in j.score.hard} <= {RZ._hard_key(h) for h in seed.score.hard}
        assert j.score.notes["optimize"]["after"] <= j.score.notes["optimize"]["before"]
    assert [el["id"] for el in best["elements"]] == [el["id"] for el in src["elements"]]
    assert judged[0].score.total == max(j.score.total for j in judged)


def test_swap_moves_never_exchange_two_texts():
    """Text keeps the designer's sequence: the headline of Level 2 may not
    swap places with its subhead (a lockup), while a picture may change
    sides with a text."""
    src = load("level2_core")
    an = analyze(src)
    lay = E.Layout(an, src, copy.deepcopy(src["elements"]), an.canvas)
    for l in lay.lives:
        names = [name for name, _, _ in O.swap_moves(lay, l)]
        mine_text = any(lay.by_id[e]["type"] == "text" for e in l.boxes)
        for name in names:
            other = name[len("swap with "):].rsplit(" (", 1)[0]
            other_text = any(lay.by_id[e]["type"] == "text" for e in lay.live_of[other].boxes)
            assert not (mine_text and other_text), name
