"""v6: scorer / rectifier allowances learned from the designer references
(docs/designer/FINDINGS.md), the painted-ink overflow rule and the
designer-agreement metric."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from engine.analyze import analyze
from engine.geometry import Box
from engine.rectify import (
    OverlapRules,
    ink_lines,
    lines_inside,
    overlap_rules,
    rectify,
    source_overlap_fractions,
    text_graze,
    unwanted_overlaps,
)
from engine.score import bleed_allowance, margin_judged, score_design, source_spacing_cv, text_overflows
from engine.textfit import default_measurer
from eval.metrics import designer_agreement

ROOT = Path(__file__).resolve().parent.parent


def _text(eid, x, y, w, h, content, fs, **kw):
    d = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "content": content,
         "font_size": fs, "font_family": "Solstice Sans", "font_weight": "bold", "color": "rgba(20,20,20,1)",
         "opacity": 1.0}
    d.update(kw)
    return d


def _shape(eid, x, y, w, h, fill="rgba(241,88,92,1)", **kw):
    d = {"id": eid, "type": "shape", "shape_type": "rectangle", "x": x, "y": y, "width": w, "height": h,
         "fill_color": fill, "opacity": 1.0}
    d.update(kw)
    return d


def _image(eid, x, y, w, h, asset="solstice_bg_gradient.png", fit="cover", **kw):
    d = {"id": eid, "type": "image", "x": x, "y": y, "width": w, "height": h, "asset_id": asset, "fit": fit,
         "opacity": 1.0}
    d.update(kw)
    return d


def _move(design, eid, dx=0.0, dy=0.0):
    out = copy.deepcopy(design)
    for e in out["elements"]:
        if e["id"] == eid:
            e["x"] += dx
            e["y"] += dy
    return out


# ---------------------------------------------------------------------------
# 1. graze vs lockup: containment on the ink lines


def test_shadow_copy_of_the_same_word_is_a_lockup_not_a_graze():
    m = default_measurer()
    src = {"canvas": {"width": 1296, "height": 1728}, "elements": [
        _shape("bg", 0, 0, 1296, 1728, fill="rgba(255,255,255,1)"),
        _text("a", 392, 619, 620, 147, "NATURAL", 104.4),
        _text("b", 385, 613, 624, 147, "NATURAL", 104.4, color="rgba(241,88,92,1)"),
    ]}
    an = analyze(src)
    ua, ub = an.unit(an.element_unit["a"]), an.unit(an.element_unit["b"])
    assert not text_graze(ua, ub, an.source_elements, m)
    assert source_overlap_fractions(an, m), "the designed overlap is recorded, so keeping it is not a collision"
    # the same layering on a resized canvas is not flagged
    assert unwanted_overlaps(an, src["elements"]) == []


def test_small_label_on_a_big_figure_is_a_lockup():
    m = default_measurer()
    src = {"canvas": {"width": 600, "height": 400}, "elements": [
        _shape("bg", 0, 0, 600, 400, fill="rgba(255,255,255,1)"),
        _text("big", 100, 60, 400, 220, "30%", 180, text_align="center"),
        _text("small", 230, 150, 140, 60, "OFF", 40, text_align="center", z_index=5),
    ]}
    an = analyze(src)
    ub, us = an.unit(an.element_unit["big"]), an.unit(an.element_unit["small"])
    assert not text_graze(ub, us, an.source_elements, m)


def test_two_lines_of_the_same_size_running_into_each_other_stay_a_graze():
    """The v5 PRAY case: a word sitting on the last line of a heading of the
    same size is a collision, not a lockup (nothing distinguishes the two)."""
    m = default_measurer()
    src = {"canvas": {"width": 300, "height": 250}, "elements": [
        _shape("bg", 0, 0, 300, 250, fill="rgba(255,255,255,1)"),
        _text("a", 190, 100, 90, 70, "When\nLife Is Great", 16, text_align="center", line_height=1.5),
        _text("b", 190, 150, 90, 22, "PRAY", 16, text_align="center", line_height=1.0),
    ]}
    an = analyze(src)
    ua, ub = an.unit(an.element_unit["a"]), an.unit(an.element_unit["b"])
    assert text_graze(ua, ub, an.source_elements, m)


def test_ink_lines_follow_the_wrapped_lines():
    m = default_measurer()
    el = _text("t", 10, 10, 200, 100, "one two three four five six seven", 20)
    lines = ink_lines(el, Box.of(el), None, m)
    assert len(lines) == m.layout(el, 20, 200).n_lines >= 2
    assert all(lines[i + 1].y > lines[i].y for i in range(len(lines) - 1))
    assert lines_inside(lines, lines) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 2. layering allowances


def _poster_with_headline_on_hero():
    return {"canvas": {"width": 1080, "height": 1080}, "elements": [
        _shape("bg", 0, 0, 1080, 1080, fill="rgba(19,16,13,1)"),
        _image("hero", 396, 110, 638, 915, fit="contain"),
        _text("head", 127, 413, 442, 273, "Party Dresses", 118, color="rgba(255,255,255,1)"),   # 38 % on the photo
        _text("sub", 140, 352, 211, 49, "COLLECT", 34, color="rgba(255,255,255,1)"),
        _shape("block", 77, 754, 171, 270, fill="rgba(255,255,255,1)"),
    ]}


def test_layered_role_may_be_layered_again_on_a_bigger_share():
    src = _poster_with_headline_on_hero()
    an = analyze(src)
    rules = overlap_rules(an)
    assert an.roles["head"] in rules.layered_roles
    out = _move(src, "head", dx=200)        # the headline now mostly on the photo
    assert unwanted_overlaps(an, out["elements"]) == []
    # but a text whose role never sat on a picture is still a collision when it lands on one
    out2 = _move(src, "sub", dx=400, dy=200)
    assert any("sub" in p for pair in unwanted_overlaps(an, out2["elements"]) for p in pair[:2])


def test_text_hosted_by_a_shape_drawn_below_it_is_never_a_collision():
    src = {"canvas": {"width": 800, "height": 600}, "elements": [
        _shape("bg", 0, 0, 800, 600, fill="rgba(255,255,255,1)"),
        _shape("block", 500, 350, 240, 200, fill="rgba(240,240,240,1)"),
        _text("label", 40, 40, 300, 60, "A LABEL", 36),
    ]}
    an = analyze(src)
    assert "label" not in an.unit(an.element_unit["block"]).ids      # separate units
    out = _move(src, "label", dx=480, dy=330)                        # fully inside the block, drawn above it
    assert unwanted_overlaps(an, out["elements"]) == []
    # the same text under the block (block drawn above it) is hidden: a collision
    src2 = {"canvas": src["canvas"], "elements": [src["elements"][0], src["elements"][2], src["elements"][1]]}
    an2 = analyze(src2)
    out2 = _move(src2, "label", dx=480, dy=330)
    assert unwanted_overlaps(an2, out2["elements"])


def test_designed_non_text_overlap_may_double_not_more():
    src = {"canvas": {"width": 1080, "height": 1920}, "elements": [
        _shape("bg", 0, 0, 1080, 1920, fill="rgba(255,255,255,1)"),
        _shape("wall", 237, 1116, 506, 217, fill="rgba(153,131,231,1)"),
        _image("figure", 552, 858, 464, 573, asset="solstice_bottle.png", fit="contain"),
        _text("head", 144, 200, 793, 269, "even though we are apart", 100),
    ]}
    an = analyze(src)
    f0 = source_overlap_fractions(an)[("figure", "wall")]
    assert 0.3 < f0 < 0.5
    assert unwanted_overlaps(an, _move(src, "figure", dx=-60)["elements"]) == []      # a bit more overlap: fine
    assert unwanted_overlaps(an, _move(src, "figure", dx=-300)["elements"])          # far more: a collision


def test_rectifier_leaves_layered_text_on_the_hero():
    src = _poster_with_headline_on_hero()
    an = analyze(src)
    out = _move(src, "head", dx=200)
    fixed = rectify(an, out["elements"], Box(0, 0, 1080, 1080))
    head = next(e for e in fixed if e["id"] == "head")
    assert abs(head["x"] - 327) < 1.0 and abs(head["y"] - 413) < 1.0, "not pushed off the photo"


# ---------------------------------------------------------------------------
# 3. margins, bleed, overflow


def test_margins_judge_text_and_small_units_not_blocks():
    src = _poster_with_headline_on_hero()
    an = analyze(src)
    by = {e["id"]: e for e in src["elements"]}
    hero = an.unit(an.element_unit["hero"])
    head = an.unit(an.element_unit["head"])
    assert not margin_judged(hero, by, an.canvas)
    assert margin_judged(head, by, an.canvas)
    flush = copy.deepcopy(src)
    for e in flush["elements"]:
        if e["id"] == "hero":
            e["x"], e["y"] = 1080 - e["width"], 1080 - e["height"]      # photo flush with the corner
    s0 = score_design(an, src, src, render=False)
    s1 = score_design(an, src, flush, render=False)
    assert s1.breakdown["layout.margins"] == pytest.approx(s0.breakdown["layout.margins"])


def test_bleed_allowance_for_pictures_that_bled_in_the_source():
    src = _poster_with_headline_on_hero()
    an = analyze(src)
    by = {e["id"]: e for e in src["elements"]}
    hero, head = an.unit(an.element_unit["hero"]), an.unit(an.element_unit["head"])
    assert bleed_allowance(hero, 0.0, by) == pytest.approx(0.01)
    assert bleed_allowance(hero, 0.10, by) == pytest.approx(0.15)
    assert bleed_allowance(hero, 0.30, by) == pytest.approx(0.31)      # capped: the +1 % rule wins past the cap
    assert bleed_allowance(head, 0.10, by) == pytest.approx(0.11)      # text: the old rule


def test_overflow_is_measured_on_painted_ink():
    m = default_measurer()
    el = _text("t", 0, 0, 400, 40, "A line of text", 30)
    lay = m.layout(el, 30, 400)
    assert lay.height > 40 > m.painted(el, 30, 400).bottom     # box metric says overflow, the glyphs fit
    assert not m.fits(el, 30, 400, 40)
    assert not text_overflows(el, m)
    el2 = dict(el, width=60)
    assert text_overflows(el2, m)
    el3 = dict(el, max_lines=1, width=120)
    assert text_overflows(el3, m)


# ---------------------------------------------------------------------------
# 4. designer agreement


def test_designer_agreement_is_one_for_the_reference_and_falls_with_distance():
    src = _poster_with_headline_on_hero()
    an = analyze(src)
    ref = copy.deepcopy(src)
    assert designer_agreement(ref, ref, an)["da_agreement"] == pytest.approx(1.0)
    near = _move(src, "head", dx=30)
    far = _move(_move(src, "head", dy=500), "sub", dy=600)
    a_near, a_far = designer_agreement(near, ref, an), designer_agreement(far, ref, an)
    assert 1.0 > a_near["da_agreement"] > a_far["da_agreement"]
    assert a_near["da_within10"] == 1.0 and a_far["da_order_tau"] < 1.0
    assert a_near["da_n"] == 4      # background left out


def test_designer_agreement_on_a_reference_file():
    """The shipped Charity Night reference agrees with itself and the engine
    reaches a sensible value against it (no exception on real data)."""
    ref_p = ROOT.parent / "docs" / "designer" / "out" / "5888cec295a7a863ddcc24c9__1080x1920.json"
    src_p = ROOT.parent / "docs" / "designer" / "src_14_5888cec295a7a863ddcc24c9.json"
    if not ref_p.exists() or not src_p.exists():
        pytest.skip("designer references not present")
    src = json.loads(src_p.read_text())
    src = src.get("source", src)
    ref = json.loads(ref_p.read_text())
    da = designer_agreement(ref, ref, analyze(src))
    assert da["da_agreement"] == pytest.approx(1.0) and da["da_n"] == 11


# ---------------------------------------------------------------------------
# 5. spacing is source-relative


def test_spacing_keeps_the_sources_rhythm_free():
    """A header / band / footer source has uneven gaps; an output as uneven
    as the source scores full marks, a more uneven one less, an even one too."""
    src = {"canvas": {"width": 600, "height": 1000}, "elements": [
        _shape("bg", 0, 0, 600, 1000, fill="rgba(255,255,255,1)"),
        _text("head", 50, 40, 500, 80, "HEADLINE", 60),
        _image("photo", 50, 160, 500, 600, fit="contain"),
        _text("cap", 50, 770, 500, 40, "A caption under the photo", 24),
        _text("cta", 50, 920, 500, 50, "BOOK NOW", 30),
    ]}
    an = analyze(src)
    m = default_measurer()
    assert source_spacing_cv(an, m) > 0.3
    same = score_design(an, src, src, render=False).breakdown["layout.spacing"]
    assert same == pytest.approx(1.0)
    worse = _move(src, "cta", dy=0)
    for e in worse["elements"]:
        if e["id"] == "cap":
            e["y"] = 762        # caption glued to the photo: gaps 40 / 2 / 110 - more uneven than the source
    assert score_design(an, src, worse, render=False).breakdown["layout.spacing"] < 1.0
    even = copy.deepcopy(src)
    for e in even["elements"]:
        if e["id"] == "cta":
            e["y"] = 840        # gaps 40 / 10 / 30 -> still uneven but not more than the source
    assert score_design(an, src, even, render=False).breakdown["layout.spacing"] >= 0.99
