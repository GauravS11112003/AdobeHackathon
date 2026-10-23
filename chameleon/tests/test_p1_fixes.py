"""The four P1 weaknesses found by the eval run (docs/EVAL_V1.md):

1. letter spacing scales with the font (fonts no longer run to 1 px),
2. rotated text is fitted in its own frame (vertical labels keep their line),
3. large flat shapes are panels that carry their text, not chips,
4. the banner plan never emits a zero-size text box, and a design has at
   most one free-text CTA.
"""

import copy
import json
from pathlib import Path

import pytest

from engine import analyze as A
from engine.candidates import generate_candidates
from engine.geometry import Box
from engine.rectify import rotated_extent
from engine.relayout import anchor_relayout
from engine.resize import materialize, resize, resize_with_candidates
from engine.textfit import apply_font_size, default_measurer, scaled_letter_spacing

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUT = Path(__file__).resolve().parent.parent / "input"


def text(eid, x, y, w, h, content, size, **kw):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "rotation": 0.0,
          "opacity": 1.0, "z_index": 5, "group_id": None, "content": content,
          "font_family": "Solstice Sans", "font_size": size, "font_weight": "regular",
          "font_style": "normal", "color": "rgba(20,20,20,1)", "text_align": "left",
          "line_height": 1.2, "letter_spacing": 0.0}
    el.update(kw)
    return el


def shape(eid, x, y, w, h, **kw):
    el = {"id": eid, "type": "shape", "x": x, "y": y, "width": w, "height": h, "rotation": 0.0,
          "opacity": 1.0, "z_index": 1, "group_id": None, "shape_type": "rectangle",
          "fill_color": "rgba(240,200,60,1)", "stroke_color": None, "stroke_width": 0, "corner_radius": 0}
    el.update(kw)
    return el


def bg(w, h):
    return {"id": "b0", "type": "image", "x": 0, "y": 0, "width": w, "height": h, "rotation": 0.0,
            "opacity": 1.0, "z_index": 0, "group_id": None, "asset_id": "solstice_bg_gradient.png", "fit": "cover"}


def design(w, h, *els):
    return {"canvas": {"width": w, "height": h}, "elements": [bg(w, h), *els]}


def ids_match(src, out):
    assert [e["id"] for e in out["elements"]] == [e["id"] for e in src["elements"]]


# ---------------------------------------------------------------------------
# 1. letter spacing


def test_measurer_scales_letter_spacing_with_the_font():
    m = default_measurer()
    el = text("t", 0, 0, 2000, 100, "TRACKED HEADLINE", 60, letter_spacing=20.0)
    full = m.layout(el, 60).max_width
    half = m.layout(el, 30).max_width
    assert abs(half - full / 2.0) < 1.0          # glyphs *and* spacing halve
    assert scaled_letter_spacing(el, 30) == pytest.approx(10.0)
    assert scaled_letter_spacing(el, 60) == pytest.approx(20.0)
    apply_font_size(el, 15)
    assert el["font_size"] == 15 and el["letter_spacing"] == pytest.approx(5.0)
    assert m.layout(el).max_width == pytest.approx(full / 4.0, abs=1.0)


def test_letter_spaced_headline_keeps_a_readable_font_on_a_small_canvas():
    # 28 px tracking on a 72 px line: fixed spacing alone would be 308 px wide
    # on a 160 px canvas and the fitter would run down to 1 px.
    src = design(1080, 1350,
                 text("h", 90, 300, 900, 100, "IS IN DANGER", 72, letter_spacing=28.0, font_weight="bold"),
                 text("s", 90, 450, 900, 60, "Save the ocean conference", 36))
    out = resize(src, {"width": 160, "height": 600})
    ids_match(src, out)
    h = next(e for e in out["elements"] if e["id"] == "h")
    assert h["font_size"] >= 12
    assert 0 < h["letter_spacing"] < 28.0
    assert h["letter_spacing"] == pytest.approx(28.0 * h["font_size"] / 72.0, rel=1e-3)
    assert default_measurer().fits(h, h["font_size"], h["width"], h["height"])
    s = next(e for e in out["elements"] if e["id"] == "s")
    assert s["letter_spacing"] == 0.0           # untouched when the source had none


# ---------------------------------------------------------------------------
# 2. rotated text


def test_vertical_label_is_fitted_in_its_own_frame_on_a_skyscraper():
    src = design(1080, 1350,
                 text("h", 90, 120, 900, 240, "Charity Garage Sale", 96, font_weight="bold"),
                 text("v", -180, 700, 480, 40, "3421 CLIFTON AVE SUNDAY", 28, rotation=-90.0),
                 text("b", 90, 1100, 900, 80, "All proceeds go to the shelter", 30))
    best, judged = resize_with_candidates(src, {"width": 160, "height": 600})
    ids_match(src, best)
    v = next(e for e in best["elements"] if e["id"] == "v")
    m = default_measurer()
    lay = m.layout(v)
    assert lay.n_lines == 1, lay.lines           # the line was not folded into a 130 px column
    assert v["width"] > v["height"]              # own frame: a wide, flat box ...
    ext = rotated_extent(Box.of(v), v["rotation"])
    assert ext.w < ext.h                         # ... drawn as a tall strip
    assert ext.x >= -0.5 and ext.right <= 160.5 and ext.y >= -0.5 and ext.bottom <= 600.5
    assert v["font_size"] >= 8
    assert m.fits(v, v["font_size"], v["width"], v["height"])
    assert not judged[0].score.hard, judged[0].score.hard


def test_rotated_text_is_clamped_by_its_drawn_extent_not_its_frame():
    # Anchor path: a vertical label whose own-frame box is wider than the
    # target canvas must not be clipped to the canvas width.
    src = design(1080, 1080,
                 text("h", 90, 120, 900, 200, "Headline", 96, font_weight="bold"),
                 text("v", -300, 500, 700, 50, "TUESDAY | APRIL 6TH AT THE OLD TOWN HALL", 34, rotation=90.0))
    out = resize(src, {"width": 400, "height": 600})
    v = next(e for e in out["elements"] if e["id"] == "v")
    ext = rotated_extent(Box.of(v), v["rotation"])
    assert v["width"] > 400 * 0.6 or v["width"] > v["height"] * 3   # frame kept wide
    assert ext.x >= -0.5 and ext.right <= 400.5 and ext.y >= -0.5 and ext.bottom <= 600.5


# ---------------------------------------------------------------------------
# 3. panels


def panel_design():
    # Left half: solid colour block carrying the headline and the body; a
    # full-width bar along the bottom; a small sticker square (a chip).
    return design(1200, 800,
                  shape("panel", 0, 0, 600, 800, fill_color="rgba(200,40,40,1)"),
                  shape("bar", 0, 760, 1200, 40, fill_color="rgba(30,30,30,1)"),
                  shape("chip", 1050, 60, 90, 90, fill_color="rgba(40,120,220,1)"),
                  text("h", 60, 200, 480, 160, "Charity Night", 72, font_weight="bold", color="rgba(255,255,255,1)"),
                  text("b", 60, 400, 480, 120, "Come and help raise money for the shelter", 28, color="rgba(255,255,255,1)"),
                  text("c", 700, 600, 300, 60, "Join us today", 32, font_weight="bold", color="rgba(10,10,10,1)"))


def test_analyzer_finds_panels_and_what_they_carry():
    a = A.analyze(panel_design())
    assert a.roles["panel"] == A.PANEL
    assert a.roles["bar"] == A.PANEL          # edge to edge, although only 5 % of the canvas
    assert a.roles["chip"] == A.SHAPE         # small and free-standing: still a chip
    assert a.roles["h"] == A.HEADLINE
    assert {u.key for u in a.carried("panel")} == {"h", "b"}
    assert a.carried("bar") == []
    assert all(not u.is_content for u in a.panels())
    assert "panel" not in {u.key for u in a.content_units()}


def test_text_is_carried_by_the_topmost_panel_under_it():
    src = panel_design()
    # A second, larger card drawn over the first one and under the texts: it
    # is what the viewer sees behind them, so it is the carrier.
    src["elements"].insert(2, shape("card", 20, 20, 560, 700, z_index=2, fill_color="rgba(30,30,80,1)"))
    for el in src["elements"]:
        if el["id"] in ("h", "b"):
            el["z_index"] = 6
    a = A.analyze(src)
    assert {u.key for u in a.carried("card")} == {"h", "b"}
    assert a.carried("panel") == []


def test_text_in_the_panel_colour_is_not_carried_by_it():
    src = panel_design()
    for el in src["elements"]:
        if el["id"] == "h":
            el["color"] = "rgba(200,40,40,1)"      # same red as the panel: not meant to be read on it
    a = A.analyze(src)
    assert {u.key for u in a.carried("panel")} == {"b"}


def test_a_panel_drawn_above_a_text_does_not_carry_it():
    src = panel_design()
    for el in src["elements"]:
        if el["id"] == "h":
            el["z_index"] = 0          # the headline is under the panel (z 1): hidden, not carried
    a = A.analyze(src)
    assert {u.key for u in a.carried("panel")} == {"b"}
    out = resize(src, {"width": 1080, "height": 1920})
    by = {e["id"]: e for e in out["elements"]}
    panel, h = Box.of(by["panel"]), Box.of(by["h"])
    assert panel.intersection_area(h) < 0.05 * h.area     # the panel keeps clear, the headline shows


@pytest.mark.parametrize("target", [(160, 600), (728, 90), (1080, 1920), (1000, 1000)])
def test_panel_keeps_its_text_and_stays_clear_of_the_rest(target):
    src = panel_design()
    a = A.analyze(src)
    out = resize(src, {"width": target[0], "height": target[1]})
    ids_match(src, out)
    by = {e["id"]: e for e in out["elements"]}
    panel = Box.of(by["panel"])
    for eid in ("h", "b"):
        assert panel.contains_fraction(Box.of(by[eid])) > 0.95, (target, eid, panel, Box.of(by[eid]))
    for eid in ("c", "chip"):
        assert panel.intersection_area(Box.of(by[eid])) < 0.05 * Box.of(by[eid]).area, (target, eid)
    bar = Box.of(by["bar"])
    assert bar.x <= 0.5 and bar.right >= target[0] - 0.5    # a bar stays edge to edge
    assert panel.x <= 0.5                                   # the block keeps the edge it touched
    assert 0 <= panel.x and panel.right <= target[0] + 0.5 and 0 <= panel.y and panel.bottom <= target[1] + 0.5


def test_anchor_path_stretches_a_panel_and_keeps_its_text_on_it():
    src = panel_design()
    a = A.analyze(src)
    pl = anchor_relayout(a, Box(0, 0, 1000, 800))    # mild ratio change
    panel = pl.boxes["panel"]
    assert panel.x == pytest.approx(0.0) and panel.bottom == pytest.approx(800.0)
    assert panel.contains_fraction(Box.union([pl.boxes["h"], pl.boxes["b"]])) > 0.99


# ---------------------------------------------------------------------------
# 4. the banner plan and the CTA role


def test_one_free_text_cta_per_design():
    source = json.loads((FIXTURES / "zero_size_text_regression.json").read_text())["source"]
    a = A.analyze(source)
    ctas = [u for u in a.units if u.role == A.CTA]
    assert len(ctas) == 1
    assert ctas[0].key == "el_10"            # the lowest accent-coloured bold line ("EACH YEAR")
    assert a.roles["el_16"] in (A.SUBHEAD, A.BODY)   # "THE OCEAN" is copy, not a button


def test_every_banner_candidate_sizes_every_text_box():
    """Before: the row's fits() returned early when one item was taller than
    the banner, later items were never sized and came out as 0x0 boxes with
    a 1 px font (the official renderer rejects those). The _finalize clamp
    only hid it; here the materialized candidates themselves are checked."""
    source = json.loads((FIXTURES / "zero_size_text_regression.json").read_text())["source"]
    a = A.analyze(source)
    target = Box(0, 0, 728, 90)
    for cand in generate_candidates(a, source, target):
        for el in materialize(source, a, cand.placement, target):
            if el["type"] == "text":
                if cand.strategy == "floorplan":
                    assert el["width"] >= 1.0 and el["height"] >= 1.0, (cand.name, el["id"])
                else:   # the uniform safety net scales 13 px boxes by 0.075; _finalize lifts them to 1 px
                    assert el["width"] > 0.0 and el["height"] > 0.0, (cand.name, el["id"])
                assert el["font_size"] >= 1.0


def test_rectifier_never_shrinks_a_unit_below_the_floor_in_total():
    from engine.rectify import MIN_SHRINK, rectify
    # Two texts forced to overlap on a canvas too narrow to move apart.
    src = design(300, 100,
                 text("a", 10, 10, 280, 40, "Left text", 24, font_weight="bold"),
                 text("b", 10, 60, 280, 40, "Right text", 24))
    a = A.analyze(src)
    els = copy.deepcopy(src["elements"])
    for e in els:
        if e["id"] == "b":
            e["y"] = 12.0        # injected collision
    out = rectify(a, els, Box(0, 0, 300, 100))
    for e in out:
        if e["type"] == "text":
            s = next(x for x in src["elements"] if x["id"] == e["id"])
            assert e["width"] >= MIN_SHRINK * s["width"] - 1e-6
            assert e["font_size"] >= MIN_SHRINK * s["font_size"] - 1e-6
