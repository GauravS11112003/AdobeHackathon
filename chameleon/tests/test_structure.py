"""v6: the preserve-structure candidate family (engine/structure.py).

Synthetic sources built from the schema (opaque ids, no role hints):
an editorial poster with a header, a panel-beside-photo band and a legal
footer; a banner with a colour panel carrying the copy beside a photo; a
quote laid on a photo; and a plain gradient ad with no zone at all.
"""

from __future__ import annotations

import os

import pytest

from engine.analyze import analyze
from engine.candidates import generate_candidates
from engine.geometry import Box
from engine.rectify import unwanted_overlaps
from engine.resize import realize, resize_with_candidates
from engine.structure import (
    StructureOptions,
    detect_structure,
    structure_relayout,
    structure_variants,
)
from engine.textfit import default_measurer


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


def editorial_poster():
    """Header (date block + headline + subhead) / red panel with the venue
    beside the photo / legal footer, like the Charity Night reference."""
    return {"canvas": {"width": 735, "height": 1102}, "elements": [
        _image("a1", 244, 290, 490, 645),                                   # photo, right of the band
        _shape("a2", 0, 290, 246, 644),                                     # red panel, left of the band
        _shape("a3", 37, 62, 208, 159, fill="rgba(10,2,3,1)"),              # black date block
        _text("a4", 19, 985, 691, 55, "FOR TICKETS OR MORE DETAILS CONTACT ALEXIS YATES AT A.YATES@CHARITYHELP.COM", 14),
        _text("a5", 35, 562, 200, 54, "211 HAINES ST", 20, color="rgba(255,255,255,1)"),
        _text("a6", 108, 169, 130, 28, "08 09 2017", 19, color="rgba(255,255,255,1)"),
        _text("a7", 281, 174, 381, 63, "Come and help raise money for Orphans Shelter Foundation", 18),
        _text("a8", 283, 49, 432, 129, "CHARITY NIGHT", 49, color="rgba(241,88,92,1)"),
        _text("a9", 34, 611, 160, 54, "HAGAN RESTAURANT", 20, color="rgba(255,255,255,1)"),
    ]}


def panel_banner():
    """A blue panel carrying the copy on the left, a photo on the right (the
    panel is drawn over the photo's left part), like the SEO reference."""
    return {"canvas": {"width": 1590, "height": 400}, "elements": [
        _image("b0", 518, 0, 1154, 400),                                    # photo
        _shape("b1", 0, 0, 779, 400, fill="rgba(0,171,255,1)"),             # panel over the photo's left part
        _text("b2", 60, 60, 600, 180, "SEO", 150, color="rgba(255,255,255,1)"),
        _text("b3", 60, 250, 600, 60, "LIFE HACKS FOR SMALL BUSINESS", 36, color="rgba(255,255,255,1)"),
        _text("b4", 60, 330, 400, 30, "www.onedito-courses.ru", 18, color="rgba(255,255,255,1)"),
    ]}


def quote_on_photo():
    return {"canvas": {"width": 735, "height": 1102}, "elements": [
        _shape("q0", 0, 0, 735, 1102, fill="rgba(60,40,120,1)"),
        _image("q1", 150, 250, 435, 600, fit="contain"),
        _text("q2", 180, 300, 380, 400, "HANDCRAFTED THINGS NEVER GO OUT OF STYLE", 48,
              color="rgba(255,255,255,1)"),
    ]}


def gradient_ad():
    return {"canvas": {"width": 1080, "height": 1080}, "elements": [
        _image("g0", 0, 0, 1080, 1080),
        _image("g1", 380, 60, 320, 100, asset="solstice_logo_lockup.png", fit="contain"),
        _text("g2", 140, 420, 800, 160, "Chase the Light", 60, color="rgba(255,255,255,1)", text_align="center"),
        _text("g3", 140, 620, 800, 60, "Shop the Summer Line", 30, color="rgba(232,106,58,1)", text_align="center"),
    ]}


def _by_id(src):
    return {e["id"]: e for e in src["elements"]}


# ---------------------------------------------------------------------------
# detection


def test_editorial_poster_is_header_band_footer():
    src = editorial_poster()
    an = analyze(src)
    st = detect_structure(an, _by_id(src))
    assert st is not None and st.kind == "bands" and st.axis == "y"
    assert len(st.bands) == 3
    header, band, footer = st.bands
    assert not header.has_zone and {u.key for u in header.leaves[0].units} >= {"a8", "a7"}
    assert band.is_split and [l.zone.key for l in band.leaves] == ["a2", "a1"]
    panel_leaf = band.leaves[0]
    assert {u.key for u in panel_leaf.units} == {"a5", "a9"}, "the venue lines travel inside the red panel"
    assert footer.leaves[0].units[0].key == "a4"


def test_panel_over_photo_splits_on_visible_extents():
    src = panel_banner()
    an = analyze(src)
    st = detect_structure(an, _by_id(src))
    assert st is not None and st.axis == "x" and st.kind == "bands"
    assert [l.zone.key for b in st.bands for l in b.leaves] == ["b1", "b0"]
    panel = st.bands[0].leaves[0]
    assert {u.key for u in panel.units} == {"b2", "b3", "b4"}


def test_quote_on_photo_is_a_lockup():
    src = quote_on_photo()
    an = analyze(src)
    st = detect_structure(an, _by_id(src))
    assert st is not None and st.kind == "lockup"
    assert st.bands[0].leaves[0].zone.key == "q1" and [u.key for u in st.bands[0].leaves[0].units] == ["q2"]


def test_no_zone_no_structure():
    src = gradient_ad()
    assert detect_structure(analyze(src), _by_id(src)) is None


def test_rotated_blocks_are_never_zones():
    src = quote_on_photo()
    src["elements"][1]["rotation"] = 90.0
    src["elements"][1]["width"], src["elements"][1]["height"] = 600, 435
    an = analyze(src)
    assert detect_structure(an, _by_id(src)) is None


def test_variants_flip_only_across_orientations():
    src = editorial_poster()
    an = analyze(src)
    st = detect_structure(an, _by_id(src))
    tall = structure_variants(st, Box(0, 0, 1080, 1920), an.canvas)
    wide = structure_variants(st, Box(0, 0, 1600, 400), an.canvas)
    assert not any(v.flip for v in tall) and any(v.swap for v in tall)
    assert any(v.flip for v in wide)
    assert 2 <= len(tall) <= 3 and 2 <= len(wide) <= 3


# ---------------------------------------------------------------------------
# layout


@pytest.mark.parametrize("size", [(1080, 1920), (1080, 1080), (1600, 900), (1584, 396), (160, 600)])
def test_relayout_places_every_element_and_keeps_bands(size):
    src = editorial_poster()
    an = analyze(src)
    by = _by_id(src)
    st = detect_structure(an, by)
    target = Box(0, 0, *size)
    pl = structure_relayout(an, target, by, default_measurer(), StructureOptions(), st)
    assert pl is not None and set(pl.boxes) == set(by)
    design = realize(src, an, pl, target)
    els = {e["id"]: e for e in design["elements"]}
    for e in design["elements"]:
        assert e["width"] >= 1 and e["height"] >= 1
        if e["type"] == "text":
            assert e["font_size"] >= 1
    panel, photo, head, legal = els["a2"], els["a1"], els["a8"], els["a4"]
    # the panel carries its venue lines and stays full-bleed on its canvas edge
    for tid in ("a5", "a9"):
        assert Box.of(panel).contains_fraction(Box.of(els[tid])) > 0.9
    assert panel["x"] <= 0.5 or panel["x"] + panel["width"] >= target.w - 0.5 or size == (160, 600)
    # reading order of the bands: header above the band, legal copy at the bottom
    assert head["y"] + head["height"] <= max(panel["y"], photo["y"]) + 1.0
    assert legal["y"] >= max(panel["y"] + panel["height"], photo["y"] + photo["height"]) - 1.0 or size[1] < 400
    assert unwanted_overlaps(an, design["elements"]) == []


def test_strip_stacks_the_split():
    """On a 160 x 600 skyscraper the panel-beside-photo band becomes the
    panel above the photo."""
    src = editorial_poster()
    an = analyze(src)
    by = _by_id(src)
    pl = structure_relayout(an, Box(0, 0, 160, 600), by, default_measurer(), StructureOptions())
    panel, photo = pl.boxes["a2"], pl.boxes["a1"]
    assert panel.bottom <= photo.y + 1.0, "panel above the photo on a strip"
    assert panel.w >= 0.9 * 160 and photo.w >= 0.9 * 160


def test_flip_turns_a_banner_split_into_bands():
    src = panel_banner()
    an = analyze(src)
    by = _by_id(src)
    pl = structure_relayout(an, Box(0, 0, 1080, 1350), by, default_measurer(), StructureOptions(flip=True))
    panel, photo = pl.boxes["b1"], pl.boxes["b0"]
    assert panel.bottom <= photo.y + 1.0 and panel.w >= 1079 and photo.w >= 1079
    assert all(Box(panel.x, panel.y, panel.w, panel.h).contains_fraction(pl.boxes[t]) > 0.9 for t in ("b2", "b3", "b4"))
    assert pl.font_size["b2"] > pl.font_size["b3"] > pl.font_size["b4"]


def test_swap_mirrors_the_split():
    src = editorial_poster()
    an = analyze(src)
    by = _by_id(src)
    keep = structure_relayout(an, Box(0, 0, 1080, 1920), by, default_measurer(), StructureOptions())
    swap = structure_relayout(an, Box(0, 0, 1080, 1920), by, default_measurer(), StructureOptions(swap=True))
    assert keep.boxes["a2"].cx < keep.boxes["a1"].cx
    assert swap.boxes["a2"].cx > swap.boxes["a1"].cx


def test_lockup_stays_on_the_photo():
    src = quote_on_photo()
    an = analyze(src)
    by = _by_id(src)
    for size in ((1080, 1080), (1080, 1920)):
        pl = structure_relayout(an, Box(0, 0, *size), by, default_measurer(), StructureOptions())
        photo, text = pl.boxes["q1"], pl.boxes["q2"]
        assert photo.contains_fraction(text) > 0.9
        assert abs(photo.w / photo.h - 435 / 600) < 0.02, "a contain picture keeps its aspect"


# ---------------------------------------------------------------------------
# the hook


def test_candidates_include_structure_variants_only_with_a_structure():
    src = editorial_poster()
    an = analyze(src)
    cands = generate_candidates(an, src, Box(0, 0, 1600, 400))
    names = [c.name for c in cands if c.strategy == "structure"]
    assert names and all("structure" in n for n in names)
    assert len(names) <= 3
    plain = gradient_ad()
    assert not [c for c in generate_candidates(analyze(plain), plain, Box(0, 0, 1600, 400)) if c.strategy == "structure"]


def test_structure_candidates_are_judged_and_can_win(monkeypatch):
    monkeypatch.setenv("CHAMELEON_OPTIMIZE", "0")
    src = editorial_poster()
    best, judged = resize_with_candidates(src, {"width": 1080, "height": 1350})
    assert any(j.strategy == "structure" for j in judged)
    st = [j for j in judged if j.strategy == "structure"]
    assert all(not j.score.hard for j in st), [j.score.hard for j in st]
    assert [e["id"] for e in best["elements"]] == [e["id"] for e in src["elements"]]
