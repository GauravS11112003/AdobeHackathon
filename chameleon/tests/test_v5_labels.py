"""v5: the generation weaknesses found in human labelling (docs/LABELS_V1.md,
docs/EVAL_V5.md), each with the mechanism on a hand-built design and, when
the eval corpus is present (eval/data/designs, gitignored), the named case.

1. banner cohesion: gaps in a banner row are capped and the row is centred;
   the scorer's `layout.cohesion` term punishes a spread-out hull,
2. importance tiers: when even the floors do not fit, minor and secondary
   floors go first (water-filling); the headline keeps its floor,
3. vertical texts beside the hero stay beside it (rails) and are sized
   against the hero's height, on one line when they can,
4. tall strips: font floors relative to the width, hero takes leftover height,
5. straddles: a text half over a photo fails readability (worst slice) and
   the rectifier slides it onto one side,
6. a thin text-on-text overlap in the source is a graze, not a lockup: the
   output does not keep it,
7. layered panels (an offset double card) are one unit that keeps its layering.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from engine import contrast as C
from engine import floorplan as F
from engine.analyze import BODY, HEADLINE, HERO, PANEL, analyze
from engine.geometry import Box
from engine.rectify import ink_box, rectify, rotated_extent, source_overlap_fractions, text_graze, unwanted_overlaps
from engine.resize import resize_with_candidates
from engine.score import WEIGHTS, _cohesion, is_straddle, straddling_texts
from engine.textfit import default_measurer

DESIGNS = Path(__file__).resolve().parent.parent / "eval" / "data" / "designs"


def _named(design_id: str) -> dict:
    p = DESIGNS / f"{design_id}.json"
    if not p.exists():
        pytest.skip(f"eval corpus not present ({p})")
    doc = json.loads(p.read_text())
    return doc["source"] if "source" in doc else doc


def _text(eid, x, y, w, h, content, font, **kw):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "content": content,
          "font_family": "Solstice Sans", "font_size": font, "color": "rgba(20,20,20,1)", "z_index": kw.pop("z", 5),
          "text_align": "left", "line_height": 1.2}
    el.update(kw)
    return el


def _shape(eid, x, y, w, h, fill="rgba(255,255,255,1)", z=0, **kw):
    el = {"id": eid, "type": "shape", "shape_type": "rectangle", "x": x, "y": y, "width": w, "height": h,
          "fill_color": fill, "z_index": z, "opacity": 1.0}
    el.update(kw)
    return el


def _image(eid, x, y, w, h, z=1, asset="solstice_bg_gradient.png", fit="cover"):
    return {"id": eid, "type": "image", "x": x, "y": y, "width": w, "height": h, "asset_id": asset, "fit": fit,
            "z_index": z, "opacity": 1.0}


def _by_role(src, out, role):
    roles = analyze(src).roles
    return [e for e in out["elements"] if roles.get(e["id"]) == role]


# ---------------------------------------------------------------------------
# 6. graze vs lockup


def test_thin_text_on_text_overlap_in_the_source_is_a_graze():
    m = default_measurer()
    src = {"canvas": {"width": 300, "height": 250}, "elements": [
        _shape("bg", 0, 0, 300, 250),
        _text("a", 190, 100, 90, 70, "When\nLife Is Great", 16, text_align="center", line_height=1.5),
        _text("b", 190, 150, 90, 22, "PRAY", 16, text_align="center", line_height=1.0),
    ]}
    an = analyze(src)
    ua, ub = an.unit(an.element_unit["a"]), an.unit(an.element_unit["b"])
    ia, ib = ink_box(src["elements"][1], ua.members["a"], 16, m), ink_box(src["elements"][2], ub.members["b"], 16, m)
    assert ia.overlaps(ib, tol=0.0), "the fixture must overlap by a sliver"
    assert text_graze(ua, ub, an.source_elements, m)
    assert source_overlap_fractions(an, m) == {}
    # a lockup: a short word laid across the middle of a big word keeps its overlap
    lock = {"canvas": {"width": 400, "height": 200}, "elements": [
        _shape("bg", 0, 0, 400, 200),
        _text("big", 20, 40, 360, 110, "SHOES", 90, text_align="center"),
        _text("small", 120, 70, 160, 60, "mega", 40, text_align="center", z=6),
    ]}
    an2 = analyze(lock)
    ub, us = an2.unit(an2.element_unit["big"]), an2.unit(an2.element_unit["small"])
    assert not text_graze(ub, us, an2.source_elements, m)
    assert source_overlap_fractions(an2, m)


def test_citation_a4_keeps_pray_clear_of_the_line_above():
    src = _named("595290bb95a7a863ddcdfcf0")
    best, judged = resize_with_candidates(src, {"width": 1240, "height": 1754})
    assert not judged[0].score.hard
    an = analyze(src)
    assert unwanted_overlaps(an, best["elements"], tol=0.0) == []
    m = default_measurer()
    texts = [e for e in best["elements"] if e["type"] == "text"]
    inks = [ink_box(e, Box.of(e), float(e["font_size"]), m) for e in texts]
    for i, a in enumerate(inks):
        for b in inks[i + 1:]:
            assert not a.overlaps(b, tol=1.0), (texts[i]["id"], a, b)


# ---------------------------------------------------------------------------
# 1. banner cohesion


def test_cohesion_term_punishes_a_row_spread_to_the_edges():
    t = Box(0, 0, 728, 90)
    spread = [Box(5, 5, 100, 80), Box(575, 20, 148, 56)]
    tight = [Box(210, 5, 100, 80), Box(330, 20, 148, 56)]
    assert _cohesion(spread, t) < 0.2 < 0.95 < _cohesion(tight, t)
    assert "layout.cohesion" in WEIGHTS and WEIGHTS["layout.cohesion"] > 0


def test_banner_row_is_clustered_and_centred():
    src = _named("5dc130c8abc8ea6d1cc3675d")
    best, judged = resize_with_candidates(src, {"width": 728, "height": 90})
    assert not judged[0].score.hard
    an = analyze(src)
    m = default_measurer()
    boxes = []
    for u in an.content_units():
        boxes.append(Box.union(ink_box(e, Box.of(e), float(e["font_size"]), m) if e["type"] == "text" else Box.of(e)
                               for e in best["elements"] if e["id"] in u.ids))
    boxes.sort(key=lambda b: b.x)
    gaps = [boxes[i + 1].x - boxes[i].right for i in range(len(boxes) - 1)]
    allowed = max(F.MAX_GAP_MULT * 4.0, F.MAX_GAP_FRAC * 728)
    assert max(gaps) <= allowed + 2.0, gaps
    hull = Box.union(boxes)
    assert abs(hull.cx - 364) < 0.1 * 728


# ---------------------------------------------------------------------------
# 2. importance tiers (water-filling)


class _Fake(F._Item):
    """An item of fixed size whose floor is lowered by relax()."""

    def __init__(self, h, floor, tier):
        self.ideal, self.floor, self.tier = h, floor, tier
        self.relaxed = 0

    def size(self, k, aw, ah):
        self.w, self.h = 10.0, max(self.floor, self.ideal * k)
        return self.w, self.h

    def relax(self, factor, tier=F.TIER_SECONDARY):
        if self.tier >= tier:
            self.floor *= factor
            self.relaxed += 1


def test_rescue_lowers_minor_floors_before_the_headline_moves():
    head = _Fake(h=40, floor=20, tier=F.TIER_PRIMARY)
    body = _Fake(h=40, floor=20, tier=F.TIER_SECONDARY)
    legal = _Fake(h=40, floor=20, tier=F.TIER_MINOR)
    items = [head, body, legal]
    ah = 48.0        # floors sum to 60: nothing fits until minor and secondary give way

    def fits(k):
        return sum(it.size(k, 100.0, ah)[1] for it in items) <= ah + 0.5

    k, ok = F._largest_k(fits, items)
    assert ok
    assert head.relaxed == 0 and head.floor == 20 and head.h >= 20
    assert legal.relaxed >= 1 and legal.floor < 20
    assert legal.floor <= body.floor


def test_eco_talks_strip_keeps_its_headline_readable():
    src = _named("592d1fbc95a7a863ddcd9d6f")
    best, judged = resize_with_candidates(src, {"width": 728, "height": 90})
    assert not judged[0].score.hard
    head = _by_role(src, best, HEADLINE)[0]
    met = F.Metrics.for_canvas(Box(0, 0, 1190, 1683), Box(0, 0, 728, 90), F.BANNER)
    assert float(head["font_size"]) >= 2 * met.min_font(HEADLINE)          # v4 left it at the 10 px floor
    smallest = min(float(e["font_size"]) for e in best["elements"] if e["type"] == "text")
    assert float(head["font_size"]) >= 2.5 * smallest


# ---------------------------------------------------------------------------
# 3 + 4. rails and tall strips


def _rails_design():
    return {"canvas": {"width": 600, "height": 1200}, "elements": [
        _shape("bg", 0, 0, 600, 1200, fill="rgba(230,231,232,1)"),
        _text("rail_r", 205.9, 603.1, 648.1, 30, "EXHIBITION OPENING 3 PM   SEMINAR 6 PM   AFTERPARTY 11 PM", 20.4,
              rotation=89.95, z=1),
        _text("rail_l", -251.1, 580.2, 634.3, 30, " INFO@NYFURNITUREFAIR.US     +11 7609 3343   +11 7608 3831", 20.6,
              rotation=-90.14, z=2),
        _text("date", 135.1, 1084, 334, 34, "1 JUNE 2018", 23.3, text_align="center", letter_spacing=9, z=3),
        _text("head", 62.9, 87.5, 481.6, 66, "NEW YORK FURNITURE\nFAIR", 23.8, text_align="center", letter_spacing=9, z=4),
        _image("hero", 126.2, 209.4, 345.7, 809.7, z=5),
    ]}


def test_strip_floors_follow_the_width():
    met = F.Metrics.for_canvas(Box(0, 0, 600, 1200), Box(0, 0, 300, 1050), F.TALL)
    assert met.min_font(HEADLINE) == round(F.STRIP_FONT_FRAC[HEADLINE] * 300) > 12
    narrow = F.Metrics.for_canvas(Box(0, 0, 600, 1200), Box(0, 0, 160, 600), F.TALL)
    assert narrow.min_font(HEADLINE) == 12     # the absolute floor still wins on a 160 px strip
    wide = F.Metrics.for_canvas(Box(0, 0, 600, 1200), Box(0, 0, 1080, 1350), F.TALL)
    assert wide.min_font(HEADLINE) == 12       # not a strip: the old floor


@pytest.mark.parametrize("src_fn", [_rails_design, lambda: _named("58dbb7af95a7a863ddccf7ae")])
def test_vertical_texts_stay_beside_the_hero_on_a_skyscraper(src_fn):
    src = src_fn()
    best, judged = resize_with_candidates(src, {"width": 160, "height": 600})
    assert not judged[0].score.hard
    an = analyze(src)
    hero = next(e for e in best["elements"] if an.roles[e["id"]] == HERO)
    hb = Box.of(hero)
    rails = [e for e in best["elements"] if e["type"] == "text" and F.is_vertical(float(e.get("rotation", 0) or 0))]
    assert len(rails) == 2
    met = F.Metrics.for_canvas(an.canvas, Box(0, 0, 160, 600), F.TALL)
    for r in rails:
        assert float(r["font_size"]) >= met.min_font(BODY)          # v4 left them at 5 px
        ext = rotated_extent(Box.of(r), float(r["rotation"]))
        yo = min(ext.bottom, hb.bottom) - max(ext.y, hb.y)
        assert yo > 0.5 * hb.h, (r["id"], ext, hb)
        assert ext.right <= hb.x + 1.0 or ext.x >= hb.right - 1.0, (r["id"], ext, hb)
    head = next(e for e in best["elements"] if an.roles[e["id"]] == HEADLINE)
    assert float(head["font_size"]) >= met.min_font(HEADLINE)
    assert Box.of(head).cy < hb.cy          # the headline was above the photo in the source


def test_furniture_expo_banner_rotated_texts_are_legible():
    src = _named("5952645b95a7a863ddcde7c9")
    best, judged = resize_with_candidates(src, {"width": 1584, "height": 396})
    assert not judged[0].score.hard
    rotated = [e for e in best["elements"] if e["type"] == "text" and F.is_vertical(float(e.get("rotation", 0) or 0))]
    assert rotated and min(float(e["font_size"]) for e in rotated) >= 24      # v4: 14 and 17 px
    head = _by_role(src, best, HEADLINE)[0]
    assert float(head["font_size"]) >= 150                                     # v4: 107 px


# ---------------------------------------------------------------------------
# 5. straddles


def _straddle_design():
    # dark panel on the left half; dark text runs from the panel onto the white canvas
    return {"canvas": {"width": 1000, "height": 600}, "elements": [
        _shape("bg", 0, 0, 1000, 600),
        _shape("dark", 0, 0, 500, 600, fill="rgba(30,20,40,1)", z=1),
        _text("t", 300, 250, 420, 60, "ELEGANT CRYSTAL", 36, z=3),
        _text("h", 520, 60, 420, 60, "BIG OFFER", 48, z=4, font_weight="bold"),
    ]}


def test_worst_slice_catches_text_half_over_a_dark_panel():
    src = _straddle_design()
    m = default_measurer()
    inks = {e["id"]: ink_box(e, Box.of(e), float(e["font_size"]), m) for e in src["elements"] if e["type"] == "text"}
    est = C.estimate(src, inks)
    assert is_straddle(est["t"]) and min(est["t"].slices) < 3.0 <= 4.5 <= max(est["t"].slices)
    assert not is_straddle(est["h"])
    assert est["t"].ratio <= min(est["t"].slices)


def test_rectifier_slides_a_straddling_text_onto_one_side():
    src = _straddle_design()
    an = analyze(src)
    # start from a layout where "t" straddles the panel's edge but did not in the source
    src_fixed = copy.deepcopy(src)
    src_fixed["elements"][2]["x"] = 520.0            # fully on the white side in the source
    an = analyze(src_fixed)
    elements = copy.deepcopy(src_fixed["elements"])
    elements[2]["x"] = 300.0                         # a candidate put it across the edge
    out = rectify(an, elements, Box(0, 0, 1000, 600))
    t = next(e for e in out if e["id"] == "t")
    m = default_measurer()
    ink = ink_box(t, Box.of(t), float(t["font_size"]), m)
    assert ink.x >= 500.0 or ink.right <= 500.0, ink
    assert straddling_texts(an, src_fixed, out, {"canvas": src["canvas"], "elements": out}, m) == []


def test_chandelier_square_has_no_straddling_text():
    src = _named("5952591895a7a863ddcde4f1")
    best, judged = resize_with_candidates(src, {"width": 1080, "height": 1080})
    assert not judged[0].score.hard
    assert judged[0].score.notes.get("straddles") == []
    anchors = [j for j in judged if j.strategy == "anchor"]
    assert anchors and all(any("straddles" in h for h in j.score.hard) for j in anchors)


# ---------------------------------------------------------------------------
# 7. layered panels


def test_offset_double_card_is_one_panel_stack():
    src = {"canvas": {"width": 1600, "height": 400}, "elements": [
        _shape("bg", 0, 0, 1600, 400, fill="rgba(10,2,3,1)"),
        _shape("back", 105, -41, 483, 483, fill="rgba(241,88,92,1)", z=3),
        _shape("front", 125, -21, 443, 443, fill="rgba(241,88,92,1)", z=4),
        _text("head", 178, 197, 334, 100, "SPARKLING NIGHT", 41, z=13, text_align="right", font_weight="bold",
              color="rgba(255,255,255,1)"),
    ]}
    an = analyze(src)
    stack = [u for u in an.units if u.role == PANEL and u.kind == "stack"]
    assert len(stack) == 1 and set(stack[0].ids) == {"back", "front"} and stack[0].ids[0] == "front"
    assert an.element_unit["back"] == an.element_unit["front"]
    best, judged = resize_with_candidates(src, {"width": 1280, "height": 720})
    by = {e["id"]: e for e in best["elements"]}
    back, front = Box.of(by["back"]), Box.of(by["front"])
    assert back.contains_fraction(front) >= 0.95
    assert front.x - back.x > 5 and front.y - back.y > 5          # the offset survives
    assert front.area < back.area


def test_sparkling_night_keeps_its_double_card():
    src = _named("59b26b3c1350e8329300d498")
    best, judged = resize_with_candidates(src, {"width": 1280, "height": 720})
    assert not judged[0].score.hard
    by = {e["id"]: e for e in best["elements"]}
    back, front = Box.of(by["el_03"]), Box.of(by["el_04"])
    assert back.contains_fraction(front) >= 0.95 and front.area < back.area
    assert front.x - back.x > 5
