"""v10 backdrop awareness (engine/backdrop.py, engine/patterns.py and the
hooks in floorplan / structure / score / critic).

  * the feature map from the JSON composite: luminance band, glow, busyness
    of a box, agreement in direction with a map from a real render
  * source signatures record what a text lies over
  * the slide: a headline that sat in a bright glow moves toward the glow
    inside its slot, never out of it; nothing moves when the backdrop is flat
  * the quiet-area move: a text on a half-dark picture goes to the half
    where its colour reads
  * decoration patterns: corners / edge / diagonal / mirrored / scatter are
    told apart from geometry and placed as one arrangement
  * the judge term `read.backdrop`: present only with the flag on, paid for
    by the layout block (the weights still sum to the same total), lower when
    the headline left its backdrop
  * the critic prefers the quiet area to the source position on a `cover` picture
  * CHAMELEON_BACKGROUND=0 is byte-identical to the v5 goldens (tests/test_perceive.py);
    the default output matches the v10 goldens where it deliberately changed
"""

from __future__ import annotations

import json
import math
import platform
from pathlib import Path

import pytest

from engine import backdrop as B
from engine import contrast as ce
from engine import critic as K
from engine import patterns as P
from engine import resize as RZ
from engine import score as S
from engine.analyze import DECORATIVE, HEADLINE, Unit, analyze
from engine.floorplan import PlanOptions, floorplan_relayout
from engine.geometry import Box
from engine.textfit import default_measurer

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
GOLDEN_V5 = Path(__file__).resolve().parent / "fixtures" / "golden_v5"
GOLDEN_V10 = Path(__file__).resolve().parent / "fixtures" / "golden_v10"

pytestmark = pytest.mark.skipif(ce.np is None, reason="numpy (skia) is needed for the backdrop map")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(RZ, "JUDGE_RENDER", False)
    for k in ("CHAMELEON_BACKGROUND", "CHAMELEON_BACKDROP_SLIDE", "CHAMELEON_BACKDROP_QUIET",
              "CHAMELEON_BACKDROP_JUDGE", "CHAMELEON_BACKDROP_PATTERNS", "CHAMELEON_BACKDROP_PIXELS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CHAMELEON_BACKGROUND", "1")
    monkeypatch.setenv("CHAMELEON_BACKDROP_JUDGE", "1")     # off by default (docs/EVAL_V10.md); the judge tests need it
    monkeypatch.setenv("CHAMELEON_V11", "0")                # the v10 contract and goldens predate v11 (engine/flags.py)


def load(name: str) -> dict:
    return json.loads((INPUT / f"chameleon_sample_{name}.json").read_text())["source"]


def text(eid, content, x, y, w, h, size, color="rgba(255,255,255,1)", align="center", z=5, **kw):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "content": content,
          "font_size": size, "font_family": "Solstice Sans", "font_weight": "bold", "color": color,
          "text_align": align, "z_index": z}
    el.update(kw)
    return el


def shape(eid, x, y, w, h, fill, z=1, **kw):
    el = {"id": eid, "type": "shape", "shape_type": "rectangle", "x": x, "y": y, "width": w, "height": h,
          "fill_color": fill, "z_index": z, "opacity": 1.0}
    el.update(kw)
    return el


# ---------------------------------------------------------------------------
# the map and the signatures


def _split_design():
    """Dark left half, white right half, a white headline on the dark side."""
    return {"canvas": {"width": 1000, "height": 600}, "elements": [
        shape("dark", 0, 0, 500, 600, "rgba(20,20,40,1)", z=0),
        shape("light", 500, 0, 500, 600, "rgba(250,250,250,1)", z=0),
        text("head", "NIGHT", 60, 240, 380, 120, 80),
    ]}


def test_map_reads_band_glow_and_busyness_from_the_json():
    m = B.from_json(_split_design())
    assert m is not None and m.how == "estimate"
    dark = m.signature(Box(50, 50, 300, 200))
    light = m.signature(Box(650, 50, 300, 200))
    edge = m.signature(Box(350, 50, 300, 200))
    assert dark.lum < 0.3 < light.lum
    assert dark.glow < 0 < light.glow or abs(dark.glow - light.glow) > 0.3
    assert dark.busy < 5 and light.busy < 5 and edge.busy > 40
    assert B.distance(dark, light) > B.D_FULL          # not the same backdrop at all
    assert B.similarity(dark, dark) == 1.0


def test_signature_handles_boxes_smaller_than_a_sample_and_off_canvas():
    m = B.from_json(_split_design())
    tiny = m.signature(Box(100, 100, 2, 2))
    assert 0.0 <= tiny.lum <= 0.3
    off = m.signature(Box(-500, -500, 50, 50))
    assert isinstance(off.lum, float)


def test_source_signatures_say_what_the_text_lies_over():
    an = analyze(_split_design())
    sigs = B.source_signatures(an, default_measurer())
    assert sigs["head"].over == "dark"
    assert sigs["head"].lum < 0.3


def test_pixel_map_agrees_with_the_estimate_in_direction():
    from engine import render as R
    design = load("level3_advanced")
    R._reset_for_tests()
    import os
    os.environ["CHAMELEON_RENDER"] = "1"
    try:
        img = R.render_design(design, max_size=B.RENDER_SIZE, with_text=False)
    finally:
        os.environ.pop("CHAMELEON_RENDER", None)
        R._reset_for_tests()
    if img is None:
        pytest.skip("renderer unavailable")
    px, js = B.from_image(img, design), B.from_json(design)
    a, b = px.lum.ravel(), js.lum.ravel()
    corr = float(ce.np.corrcoef(a, b)[0, 1])
    assert corr > 0.9
    boxes = [Box(0, 0, 1080, 300), Box(0, 1000, 1080, 350), Box(340, 180, 400, 400)]
    for box in boxes:
        sp, sj = px.signature(box), js.signature(box)
        assert abs(sp.lum - sj.lum) < 0.12


# ---------------------------------------------------------------------------
# the slide


def _glow_source(with_glow: bool):
    """A dark poster; a faint bright ellipse (decoration) on the right where
    the headline sits. With `with_glow` False the headline sits on plain dark."""
    els = [shape("bg", 0, 0, 1000, 1000, "rgba(18,18,30,1)", z=0)]
    if with_glow:
        els.append({"id": "glow", "type": "shape", "shape_type": "ellipse", "x": 450, "y": 150, "width": 700,
                    "height": 700, "fill_color": "rgba(255,240,200,1)", "opacity": 0.3, "z_index": 1})
    els += [
        text("head", "GLOW", 520, 420, 420, 150, 110, align="center", z=5),
        text("sub", "A small line of copy under the title that wraps.", 100, 820, 800, 60, 28, align="center", z=5),
    ]
    return {"canvas": {"width": 1000, "height": 1000}, "elements": els}


def test_headline_slides_toward_its_glow_inside_the_slot(monkeypatch):
    src = _glow_source(True)
    an = analyze(src)
    assert an.roles["head"] == HEADLINE and an.roles["glow"] == DECORATIVE
    by_id = {e["id"]: e for e in src["elements"]}
    target = Box(0, 0, 500, 1400)
    monkeypatch.setenv("CHAMELEON_BACKDROP_SLIDE", "0")
    off = floorplan_relayout(an, target, by_id, default_measurer(), PlanOptions())
    monkeypatch.setenv("CHAMELEON_BACKDROP_SLIDE", "1")
    on = floorplan_relayout(an, target, by_id, default_measurer(), PlanOptions())
    assert "head" in on.slots or any(k.endswith("head") for k in on.slots)
    moves = on.notes.get("slide", [])
    assert moves, "the headline should have slid toward the glow"
    slot = on.slots[an.element_unit["head"]]
    hb = on.boxes["head"]
    assert slot.x - 0.5 <= hb.x and hb.right <= slot.right + 0.5
    assert slot.y - 0.5 <= hb.y and hb.bottom <= slot.bottom + 0.5
    # closer to the glow (the decoration keeps its right-hand corner) than before
    gx = on.boxes["glow"].cx
    assert abs(hb.cx - gx) < abs(off.boxes["head"].cx - gx)
    # the backdrop under it looks more like the source's
    assert moves[0]["d"] < moves[0]["d0"] - B.MIN_GAIN + 1e-9


def test_nothing_slides_on_a_flat_backdrop():
    src = _glow_source(False)
    an = analyze(src)
    by_id = {e["id"]: e for e in src["elements"]}
    on = floorplan_relayout(an, Box(0, 0, 500, 1400), by_id, default_measurer(), PlanOptions())
    assert not on.notes.get("slide")


def test_flag_off_records_no_slots_moves(monkeypatch):
    monkeypatch.delenv("CHAMELEON_BACKDROP_JUDGE", raising=False)
    assert B.enabled("slide") and B.enabled("quiet") and B.enabled("patterns") and not B.enabled("judge")
    monkeypatch.setenv("CHAMELEON_BACKGROUND", "0")
    assert not B.enabled() and not B.enabled("slide") and not B.enabled("patterns")
    src = _glow_source(True)
    an = analyze(src)
    by_id = {e["id"]: e for e in src["elements"]}
    pl = floorplan_relayout(an, Box(0, 0, 500, 1400), by_id, default_measurer(), PlanOptions())
    assert not pl.notes


# ---------------------------------------------------------------------------
# the quiet area


def test_quiet_position_moves_white_text_to_the_dark_half(tmp_path, monkeypatch):
    from PIL import Image

    img = Image.new("RGB", (400, 200), (250, 250, 250))
    for x in range(200):
        for y in range(200):
            img.putpixel((x, y), (10, 10, 20))
    (tmp_path / "half.png").save if False else img.save(tmp_path / "half.png")
    monkeypatch.setattr(ce, "ASSETS_DIR", tmp_path)
    src = {"canvas": {"width": 1000, "height": 800}, "elements": [
        {"id": "pic", "type": "image", "asset_id": "half.png", "fit": "cover", "x": 0, "y": 0, "width": 1000,
         "height": 500, "z_index": 1, "opacity": 1.0},
        text("head", "QUIET", 60, 150, 380, 120, 80, z=5),       # on the dark half in the source
        text("body", "Some body copy below the picture.", 100, 600, 800, 60, 28, color="rgba(0,0,0,1)", z=5),
    ]}
    an = analyze(src)
    # the layout put the headline on the bright half
    by_id = {e["id"]: dict(e) for e in src["elements"]}
    by_id["head"].update({"x": 560, "y": 150})
    got = B.quiet_position("head", an.element_unit["pic"], by_id, an, Box(0, 0, 1000, 800), default_measurer())
    assert got is not None
    dx, dy, before, after = got
    assert after > before * B.QUIET_MIN_GAIN
    assert 560 + dx + 380 / 2.0 < 500        # back over the dark half
    assert abs(dy) < 200                     # inside the picture


def test_critic_prefers_the_quiet_area_on_a_cover_picture(monkeypatch):
    src = {"canvas": {"width": 1000, "height": 800}, "elements": [
        {"id": "pic", "type": "image", "asset_id": "solstice_bg_gradient.png", "fit": "cover", "x": 0, "y": 0,
         "width": 1000, "height": 500, "z_index": 1, "opacity": 1.0},
        text("head", "QUIET", 60, 150, 380, 120, 80, z=5),
        text("body", "Some body copy below the picture.", 100, 600, 800, 60, 28, color="rgba(0,0,0,1)", z=5),
    ]}
    an = analyze(src)
    best = type("J", (), {"design": src})()
    labels = [r.label for r in K._contrast_recipes("head", an, src, best, default_measurer())]
    assert "headline onto the quiet area" in labels and "headline on the picture" not in labels
    monkeypatch.setenv("CHAMELEON_BACKGROUND", "0")
    labels = [r.label for r in K._contrast_recipes("head", an, src, best, default_measurer())]
    assert "headline on the picture" in labels and "headline onto the quiet area" not in labels


# ---------------------------------------------------------------------------
# patterns


def _deco_units(boxes: dict[str, Box]):
    units = [Unit(key=k, ids=[k], role=DECORATIVE, box=b, members={k: b}, primary=k) for k, b in boxes.items()]
    els = {k: {"id": k, "type": "shape", "shape_type": "ellipse", "x": b.x, "y": b.y, "width": b.w, "height": b.h,
               "opacity": 0.2} for k, b in boxes.items()}
    return units, els


def test_corners_are_kept_with_their_inset_ratios():
    canvas = Box(0, 0, 1000, 1000)
    units, els = _deco_units({"a": Box(-100, -100, 300, 300), "b": Box(800, 800, 300, 300)})
    pats = P.detect_patterns(units, canvas, els)
    assert len(pats) == 1 and pats[0].kind == P.CORNERS
    out = P.place_pattern(pats[0], canvas, Box(0, 0, 400, 1200), 0.4)
    a, b = out["a"], out["b"]
    assert a.w == pytest.approx(120) and b.w == pytest.approx(120)
    assert a.x == pytest.approx(-0.1 * 400) and a.y == pytest.approx(-0.1 * 1200)
    assert b.right == pytest.approx(400 + 0.1 * 400) and b.bottom == pytest.approx(1200 + 0.1 * 1200)


def test_edge_run_keeps_the_edge_and_the_spread():
    canvas = Box(0, 0, 1000, 500)
    units, els = _deco_units({f"d{i}": Box(100 + i * 200, 440, 40, 40) for i in range(4)})
    pats = P.detect_patterns(units, canvas, els)
    assert pats[0].kind == P.EDGE and pats[0].params["edge"] == "bottom"
    out = P.place_pattern(pats[0], canvas, Box(0, 0, 500, 1000), 0.5)
    for i in range(4):
        b = out[f"d{i}"]
        assert b.cx == pytest.approx((120 + i * 200) / 1000 * 500)
        assert b.bottom == pytest.approx(1000 - (500 - 480) / 500 * 1000)


def test_diagonal_keeps_direction_and_spacing_ratio():
    canvas = Box(0, 0, 1000, 1000)
    units, els = _deco_units({f"d{i}": Box(150 + i * 250 - 30, 200 + i * 200 - 30, 60, 60) for i in range(3)})
    pats = P.detect_patterns(units, canvas, els)
    assert pats[0].kind == P.DIAGONAL
    out = P.place_pattern(pats[0], canvas, Box(0, 0, 1200, 800), 0.8)
    c = [(out[f"d{i}"].cx, out[f"d{i}"].cy) for i in range(3)]
    ang = math.degrees(math.atan2(c[2][1] - c[0][1], c[2][0] - c[0][0]))
    assert ang == pytest.approx(math.degrees(math.atan2(400, 500)), abs=1.0)
    d01 = math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1])
    d12 = math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1])
    assert d01 == pytest.approx(d12, rel=0.01)
    for b in out.values():                       # fits the canvas (the source had no bleed)
        assert Box(0, 0, 1200, 800).contains_fraction(b) > 0.9


def test_mirrored_pair_stays_symmetric_about_the_axis():
    canvas = Box(0, 0, 1000, 1000)
    units, els = _deco_units({"l": Box(100, 400, 120, 120), "r": Box(780, 400, 120, 120)})
    pats = P.detect_patterns(units, canvas, els)
    assert pats[0].kind == P.MIRRORED and pats[0].params["axis"] == "v"
    out = P.place_pattern(pats[0], canvas, Box(0, 0, 600, 1500), 0.6)
    assert out["l"].cx + out["r"].cx == pytest.approx(600, abs=0.5)
    assert out["l"].cy == pytest.approx(out["r"].cy, abs=0.5)


def test_scatter_keeps_fractional_positions_and_a_lone_decoration_is_no_pattern():
    canvas = Box(0, 0, 1000, 1000)
    units, els = _deco_units({"a": Box(100, 100, 50, 50), "b": Box(600, 300, 50, 50), "c": Box(300, 700, 50, 50),
                              "d": Box(700, 800, 50, 50), "e": Box(500, 500, 50, 50)})
    pats = P.detect_patterns(units, canvas, els)
    assert pats[0].kind == P.SCATTER
    out = P.place_pattern(pats[0], canvas, Box(0, 0, 2000, 500), 0.5)
    assert out["e"].cx == pytest.approx(1050) and out["e"].cy == pytest.approx(262.5)
    one, els1 = _deco_units({"a": Box(100, 100, 50, 50)})
    assert P.detect_patterns(one, canvas, els1) == []


def test_level2_circles_are_a_corner_pattern_and_land_in_their_corners():
    src = load("level2_core")
    an = analyze(src)
    assert [p.kind for p in an.patterns] == [P.CORNERS]
    out, judged = RZ.resize_with_candidates(src, {"width": 1080, "height": 1920})
    by = {e["id"]: e for e in out["elements"]}
    for key, (cx, cy) in an.patterns[0].params["corners"].items():
        b = Box.of(by[key])
        assert (b.cx < 540) == (cx == 0.0) and (b.cy < 960) == (cy == 0.0)


# ---------------------------------------------------------------------------
# the judge


def test_backdrop_term_is_paid_by_the_layout_block(monkeypatch):
    w = S.active_weights()
    assert "read.backdrop" in w and w["read.backdrop"] == S.BACKDROP_WEIGHT
    assert sum(w.values()) == pytest.approx(sum(S.WEIGHTS.values()))
    for k in S.WEIGHTS:
        if not k.startswith("layout."):
            assert w[k] == S.WEIGHTS[k]
    monkeypatch.setenv("CHAMELEON_BACKGROUND", "0")
    assert S.active_weights() is S.WEIGHTS


def test_backdrop_term_drops_when_the_headline_leaves_its_backdrop(monkeypatch):
    src = _split_design()
    an = analyze(src)
    target = Box(0, 0, 1000, 600)
    stay = {"canvas": src["canvas"], "elements": [dict(e) for e in src["elements"]]}
    left = {"canvas": src["canvas"], "elements": [dict(e) for e in src["elements"]]}
    left["elements"][2].update({"x": 560, "color": "rgba(255,255,255,1)"})
    s_stay = S.score_design(an, src, stay, target, render=False)
    s_left = S.score_design(an, src, left, target, render=False)
    assert "read.backdrop" in s_stay.breakdown
    assert s_stay.breakdown["read.backdrop"] > 0.9
    assert s_left.breakdown["read.backdrop"] < s_stay.breakdown["read.backdrop"] - 0.3
    monkeypatch.setenv("CHAMELEON_BACKGROUND", "0")
    assert "read.backdrop" not in S.score_design(an, src, stay, target, render=False).breakdown


# ---------------------------------------------------------------------------
# contract and goldens


@pytest.mark.parametrize("name", ["level1_warmup", "level2_core", "level3_advanced"])
def test_default_output_keeps_the_contract(name):
    src = load(name)
    out = RZ.resize(src, {"width": 1584, "height": 396})
    assert [e["id"] for e in out["elements"]] == [e["id"] for e in src["elements"]]
    for e, s in zip(out["elements"], src["elements"]):
        if e["type"] == "text":
            assert e["content"] == s["content"] and e["font_family"] == s["font_family"]


@pytest.mark.skipif(platform.system() != "Darwin", reason="goldens were measured with macOS font hinting")
@pytest.mark.parametrize("golden", sorted(GOLDEN_V5.glob("*.json")), ids=lambda p: p.stem)
def test_default_output_matches_the_v10_goldens(golden, monkeypatch):
    """With the v10 default (backdrop on) the output equals the v5 golden,
    or the v10 golden where the default output deliberately changed
    (docs/EVAL_V10.md lists each with its reason)."""
    monkeypatch.delenv("CHAMELEON_VLM", raising=False)
    monkeypatch.delenv("CHAMELEON_ROLE_MODEL", raising=False)
    monkeypatch.delenv("CHAMELEON_BACKGROUND", raising=False)
    monkeypatch.delenv("CHAMELEON_BACKDROP_JUDGE", raising=False)
    monkeypatch.setenv("CHAMELEON_OPTIMIZE", "0")
    monkeypatch.setenv("CHAMELEON_CRITIC", "0")
    stem, size = golden.stem.rsplit("_", 1)
    w, h = (int(v) for v in size.split("x"))
    out = RZ.resize(load(stem.replace("chameleon_sample_", "")), {"width": w, "height": h})
    expected = GOLDEN_V10 / golden.name
    want = (expected if expected.exists() else golden).read_text()
    assert json.dumps(out, sort_keys=True, separators=(",", ":")) == want
