"""The four v3 rule upgrades (docs/EVAL_V3.md):

1. no-render contrast estimate (engine/contrast.py) and the drop rule,
2. units beyond group_id (holders, stickers, cards, frames, hosts, rows),
3. painted text boxes, canvas-relative floors, headline stays largest,
4. source-relative overlap / bleed / hierarchy, adaptation and disruption
   penalties, two-stage judging (estimate for all, pixels for the top 3).
"""

import copy
import json
from pathlib import Path

import pytest

from engine import analyze as A
from engine import contrast as C
from engine.candidates import generate_candidates
from engine.floorplan import HERO_FLOOR_FRAC, LOGO_FLOOR_FRAC, Metrics, ratio_family
from engine.geometry import Box
from engine.rectify import ink_box, unwanted_overlaps
from engine.resize import TOP_RENDER, resize, resize_with_candidates
from engine.score import ADAPT_PENALTY, score_design
from engine.textfit import default_measurer
from eval.run_eval import load_presets

INPUT = Path(__file__).resolve().parent.parent / "input"
DESIGNS = Path(__file__).resolve().parent.parent / "eval" / "data" / "designs"
BOYNTON = DESIGNS / "5928010895a7a863ddcd8e06.json"


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


def image(eid, x, y, w, h, asset="solstice_bottle.png", fit="contain", **kw):
    el = {"id": eid, "type": "image", "x": x, "y": y, "width": w, "height": h, "rotation": 0.0,
          "opacity": 1.0, "z_index": 2, "group_id": None, "asset_id": asset, "fit": fit}
    el.update(kw)
    return el


def design(w, h, *els, bg=True):
    base = [image("b0", 0, 0, w, h, asset="solstice_bg_gradient.png", fit="cover", z_index=0)] if bg else []
    return {"canvas": {"width": w, "height": h}, "elements": [*base, *els]}


def load_sample(name):
    t = json.loads((INPUT / name).read_text())
    return t["source"], t["target_canvas"]


# ---------------------------------------------------------------------------
# 1. contrast estimate


@pytest.mark.skipif(not C.available(), reason="numpy unavailable")
def test_contrast_estimate_reads_layers_under_the_text():
    d = design(600, 400,
               shape("dark", 0, 0, 300, 400, fill_color="rgba(20,20,30,1)"),
               text("on_dark", 20, 40, 260, 60, "WHITE ON DARK", 36, color="rgba(255,255,255,1)"),
               text("on_white", 320, 40, 260, 60, "WHITE ON WHITE", 36, color="rgba(255,255,255,1)"),
               text("half", 150, 200, 300, 60, "HALF AND HALF", 36, color="rgba(255,255,255,1)"),
               bg=False)
    est = C.estimate(d)
    assert est["on_dark"].ratio > 10
    assert est["on_white"].ratio < 1.1
    # the 25th percentile judges by the bad half, not the average
    assert est["half"].ratio < 1.5
    # the estimate sees shapes through their alpha and an ellipse only inside it
    d2 = design(600, 400,
                shape("wash", 0, 0, 600, 400, fill_color="rgba(0,0,0,0.5)"),
                text("t", 20, 40, 560, 60, "GREY WASH", 36, color="rgba(255,255,255,1)"), bg=False)
    r = C.estimate(d2)["t"].ratio
    assert 2.5 < r < 5.0


@pytest.mark.skipif(not C.available(), reason="numpy unavailable")
def test_contrast_estimate_samples_image_assets_through_fit():
    # The bottle asset is transparent around the bottle: contain-fitted into a
    # wide box, the sides show the canvas; a text over the sides sits on white.
    d = design(800, 400, image("img", 0, 0, 800, 400), text("t", 10, 150, 150, 60, "SIDE", 40,
                                                              color="rgba(255,255,255,1)"), bg=False)
    assert C.estimate(d)["t"].ratio < 1.2
    # a style run in another colour counts when it covers enough of the text
    d3 = design(600, 300, shape("dark", 0, 0, 600, 300, fill_color="rgba(10,10,10,1)"),
                text("t", 20, 40, 560, 60, "BLACK RUN", 36, color="rgba(255,255,255,1)",
                     style_runs=[{"start": 0, "end": 5, "color": "rgba(10,10,10,1)"}]), bg=False)
    est = C.estimate(d3)["t"]
    assert est.ratios["main"] > 10 and est.ratio < 1.2


def test_contrast_drop_rule_is_source_relative():
    # White headline on a dark panel in the source; the output drops it on the
    # white canvas: a hard fail. The same output for a source that already had
    # white-on-white is not (stand-in assets are not the layout's fault).
    src = design(600, 400, shape("p", 0, 0, 600, 400, fill_color="rgba(10,10,10,1)"),
                 text("h", 40, 40, 520, 80, "Big headline", 60, font_weight="bold", color="rgba(255,255,255,1)"),
                 text("b", 40, 200, 520, 60, "body copy", 24, color="rgba(255,255,255,1)"), bg=False)
    a = A.analyze(src)
    out = copy.deepcopy(src)
    for el in out["elements"]:
        if el["id"] == "p":
            el["x"], el["y"], el["width"], el["height"] = 0, 300, 600, 100     # panel slides away
    sc = score_design(a, src, out, Box(0, 0, 600, 400), render=False)
    assert any("unreadable contrast" in h and h.startswith("h ") for h in sc.hard), sc.hard
    assert sc.notes["contrast_source"] == "estimate"
    src2 = copy.deepcopy(out)      # the source itself has white on white
    sc2 = score_design(A.analyze(src2), src2, out, Box(0, 0, 600, 400), render=False)
    assert not any("contrast" in h for h in sc2.hard)


# ---------------------------------------------------------------------------
# 2. units beyond group_id


def test_label_in_a_pill_is_a_button_unit_and_the_cta():
    src = design(1000, 1000,
                 text("h", 100, 100, 800, 120, "Headline", 80, font_weight="bold"),
                 shape("pill", 300, 700, 400, 90, fill_color="rgba(200,40,40,1)", z_index=3),
                 text("lbl", 330, 720, 340, 50, "Shop now", 32, color="rgba(255,255,255,1)", z_index=6))
    a = A.analyze(src)
    u = a.unit(a.element_unit["lbl"])
    assert set(u.ids) == {"pill", "lbl"} and u.kind == "group" and u.role == A.CTA
    assert a.roles["pill"] == A.CTA and u.is_group


def test_sticker_keeps_several_short_lines_but_a_card_becomes_a_panel():
    src = design(1200, 1600,
                 text("h", 100, 900, 1000, 150, "THE OCEAN", 90, font_weight="bold"),
                 shape("sq", 800, 100, 280, 280, fill_color="rgba(240,60,60,1)", z_index=3),
                 text("d1", 820, 120, 240, 150, "17", 120, z_index=6, color="rgba(255,255,255,1)"),
                 text("d2", 820, 280, 240, 60, "JULY", 50, z_index=6, color="rgba(255,255,255,1)"),
                 shape("card", 100, 1100, 600, 400, fill_color="rgba(230,230,230,1)", z_index=3),
                 text("c1", 130, 1130, 540, 60, "Become a speaker", 40, z_index=6),
                 text("c2", 130, 1220, 540, 240, "A long paragraph about the conference that goes on", 28, z_index=6))
    a = A.analyze(src)
    sticker = a.unit(a.element_unit["d1"])
    assert set(sticker.ids) == {"sq", "d1", "d2"} and sticker.role == A.BADGE
    assert a.roles["h"] == A.HEADLINE          # the big "17" lives in the sticker, not the headline slot
    assert a.roles["card"] == A.PANEL
    assert a.element_unit["c1"] == "c1" and a.element_unit["c2"] == "c2"
    assert {u.key for u in a.carried("card")} == {"c1", "c2"}


def test_underline_bar_is_attached_to_its_heading_and_bars_do_not_chain():
    src = design(1000, 1400,
                 text("h", 100, 100, 800, 120, "Headline", 80, font_weight="bold"),
                 shape("bar", 100, 230, 300, 10, fill_color="rgba(200,40,40,1)"),
                 shape("far", 100, 330, 300, 10, fill_color="rgba(200,40,40,1)"),
                 shape("sq", 100, 260, 80, 80, fill_color="rgba(0,120,200,1)"),
                 text("b", 100, 500, 800, 200, "Body copy under the heading", 30))
    a = A.analyze(src)
    h = a.unit(a.element_unit["h"])
    assert h.kind == "host" and h.primary == "h" and h.attachments == ["bar"] and h.role == A.HEADLINE
    assert a.element_unit["far"] == "far"       # 90 px below the bar: not chained through it
    assert a.element_unit["sq"] == "sq"         # not thin, not inside: a chip of its own


def test_photo_in_frame_travels_with_the_photo():
    src = design(1000, 1000,
                 shape("frame", 240, 190, 520, 520, fill_color="rgba(255,255,255,1)", z_index=1),
                 image("photo", 250, 200, 500, 500, z_index=2),
                 text("h", 100, 800, 800, 100, "Caption", 48, font_weight="bold"))
    a = A.analyze(src)
    u = a.unit(a.element_unit["photo"])
    assert u.kind == "host" and u.primary == "photo" and u.attachments == ["frame"] and u.role == A.HERO


def test_three_badges_side_by_side_are_one_row():
    src, _ = load_sample("chameleon_sample_level3_advanced.json")
    a = A.analyze(src)
    row = a.unit(a.element_unit["badge2_bg"])
    assert row.is_row and len(row.parts) == 3 and row.role == A.BADGE
    assert a.element_unit["badge1_label"] == row.key == a.element_unit["badge3_bg"]


@pytest.mark.skipif(not BOYNTON.exists(), reason="eval designs not converted")
def test_boynton_bars_stay_under_their_headings_in_every_format():
    """docs/sanity_v2: the underline bars scattered; now they are attached to
    their headings (host units) and stay just below their painted text."""
    src = json.loads(BOYNTON.read_text())["source"]
    a = A.analyze(src)
    hosts = {u.primary: u.attachments for u in a.units if u.kind == "host" and u.primary_type(a.source_elements) == "text"}
    assert hosts, "expected host units"
    m = default_measurer()
    for name, w, h in load_presets():
        out = resize(src, {"width": w, "height": h})
        by = {e["id"]: e for e in out["elements"]}
        for head_id, bars in hosts.items():
            head = by[head_id]
            ink = ink_box(head, Box.of(head), float(head["font_size"]), m)
            for bar_id in bars:
                bar = Box.of(by[bar_id])
                gap = bar.y - ink.bottom
                assert -0.6 * ink.h <= gap <= 1.2 * float(head["font_size"]) + 2.0, (name, head_id, bar_id, gap, ink, bar)
                xo = min(bar.right, ink.right) - max(bar.x, ink.x)
                assert xo >= 0.5 * min(bar.w, ink.w) - 1.0, (name, head_id, bar_id)


# ---------------------------------------------------------------------------
# 3. painted boxes, floors, headline largest


def test_painted_box_is_tighter_than_the_text_box():
    m = default_measurer()
    el = text("t", 0, 0, 600, 200, "HEADLINE", 100, text_align="center")
    p = m.painted(el, 100, 600)
    assert 5 < p.top < 30                      # caps start below the box top (ascent - cap height)
    assert p.h < p.box_h                        # no descender in HEADLINE: ends at the baseline
    assert p.x > 0 and abs((p.x + p.w / 2) - 300) < 1.0   # centred lines
    q = m.painted(text("t", 0, 0, 600, 200, "giggly", 100), 100, 600)
    assert q.bottom > p.bottom                  # descenders add depth
    ink = ink_box(el, Box.of(el), 100, m)
    assert ink.y > 0 and ink.bottom < 200 and ink.w < 600


def test_font_floor_grows_with_the_long_side():
    big = Metrics.for_canvas(Box(0, 0, 1080, 1350), Box(0, 0, 1080, 1920), ratio_family(Box(0, 0, 1080, 1920)))
    small = Metrics.for_canvas(Box(0, 0, 1080, 1350), Box(0, 0, 160, 600), ratio_family(Box(0, 0, 160, 600)))
    assert big.min_font(A.HEADLINE) == 16 and big.min_font(A.FINE_PRINT) == 11 and big.min_font(A.BADGE) == 13
    assert small.min_font(A.HEADLINE) == 12 and small.min_font(A.FINE_PRINT) == 9


def test_logo_and_hero_keep_a_share_of_the_short_side():
    src, _ = load_sample("chameleon_sample_level2_core.json")
    for W, H in ((1080, 1920), (160, 600), (728, 90)):
        out = {e["id"]: e for e in resize(src, {"width": W, "height": H})["elements"]}
        mn = min(W, H)
        assert max(out["logo"]["width"], out["logo"]["height"]) >= LOGO_FLOOR_FRAC * mn - 0.5, (W, H)
        assert max(out["product"]["width"], out["product"]["height"]) >= HERO_FLOOR_FRAC * mn - 0.5, (W, H)


def test_headline_stays_the_largest_text():
    src = design(1080, 1350,
                 text("h", 90, 300, 900, 100, "A fairly long headline that wraps", 48, font_weight="bold"),
                 text("k", 90, 150, 900, 60, "KICKER", 40),
                 text("b", 90, 500, 900, 300, "Body copy that is clearly smaller", 24))
    for W, H in ((1080, 1920), (1600, 400), (160, 600)):
        out = {e["id"]: e for e in resize(src, {"width": W, "height": H})["elements"]}
        assert out["h"]["font_size"] >= out["k"]["font_size"] - 1e-6, (W, H)
        assert out["h"]["font_size"] >= out["b"]["font_size"] - 1e-6, (W, H)


# ---------------------------------------------------------------------------
# 4. source-relative penalties, adaptation, two-stage judge


def test_overlap_is_a_defect_only_when_worse_than_the_source():
    src = design(1000, 1000,
                 image("photo", 100, 100, 600, 600),
                 shape("sticker", 600, 600, 200, 200, fill_color="rgba(200,40,40,1)", z_index=4),
                 text("h", 100, 800, 800, 120, "Headline", 60, font_weight="bold"))
    a = A.analyze(src)
    assert unwanted_overlaps(a, src["elements"]) == []        # the sticker sat on the photo's corner
    out = copy.deepcopy(src)
    by = {e["id"]: e for e in out["elements"]}
    by["sticker"]["x"], by["sticker"]["y"] = 598, 598          # a hair more overlap (1 pp): still fine
    assert unwanted_overlaps(a, out["elements"]) == []
    by["sticker"]["x"], by["sticker"]["y"] = 300, 300          # fully on the photo: worse than designed
    pairs = unwanted_overlaps(a, out["elements"])
    assert pairs and {pairs[0][0], pairs[0][1]} == {"photo", "sticker"}
    # a graze between units that did not overlap is not a collision either
    by["sticker"]["x"], by["sticker"]["y"] = 600, 600
    by["h"]["y"] = 797                                          # touches the sticker's bottom by 3 px
    assert unwanted_overlaps(a, out["elements"]) == []


def test_bleed_the_source_had_is_excused():
    src = design(1000, 1000, image("photo", 700, 100, 330, 500), text("h", 50, 700, 600, 100, "Headline", 60))
    a = A.analyze(src)
    assert a.roles["photo"] in (A.HERO, A.IMAGE)
    out = copy.deepcopy(src)
    sc = score_design(a, src, out, Box(0, 0, 1000, 1000), render=False)
    assert not any("off canvas" in h for h in sc.hard)
    by = {e["id"]: e for e in out["elements"]}
    by["photo"]["x"] = 850                                       # bleeds more than it did
    sc = score_design(a, src, out, Box(0, 0, 1000, 1000), render=False)
    assert any("off canvas" in h for h in sc.hard)


def test_hierarchy_keeps_the_sources_ratio_floor():
    src = design(1000, 1000, text("h", 50, 100, 900, 150, "Headline", 80, font_weight="bold"),
                 text("s", 50, 300, 900, 100, "Subhead", 40), text("b", 50, 500, 900, 300, "Body", 24))
    a = A.analyze(src)
    good = score_design(a, src, copy.deepcopy(src), Box(0, 0, 1000, 1000), render=False)
    bad = copy.deepcopy(src)
    for e in bad["elements"]:
        if e["id"] == "s":
            e["font_size"] = 100     # subhead bigger than the headline: hierarchy lost
    worse = score_design(a, src, bad, Box(0, 0, 1000, 1000), render=False)
    assert worse.breakdown["faith.hierarchy"] < good.breakdown["faith.hierarchy"] == 1.0


def test_anchor_layout_pays_the_adaptation_penalty_on_a_big_shape_change():
    src, _ = load_sample("chameleon_sample_level2_core.json")
    a = A.analyze(src)
    target = Box(0, 0, 1600, 400)
    cands = generate_candidates(a, src, target)
    anchor = next(c for c in cands if c.strategy == "anchor")
    assert anchor.fallback
    from engine.resize import realize
    d = realize(src, a, anchor.placement, target)
    sc = score_design(a, src, d, target, render=False, strategy="anchor")
    assert sc.penalty == ADAPT_PENALTY and sc.notes["adaptation_penalty"] == ADAPT_PENALTY
    same = score_design(a, src, d, target, render=False, strategy="floorplan")
    assert same.total == pytest.approx(sc.total + ADAPT_PENALTY)
    # on the shipped Level 2 task a real floor plan wins; the penalised anchor
    # would still win if it were the only clean candidate (penalty << hard fail)
    best, judged = resize_with_candidates(src, {"width": 1600, "height": 400})
    assert judged[0].strategy == "floorplan" and not judged[0].score.hard
    assert ADAPT_PENALTY < 1000


def test_identity_resize_prefers_the_identity():
    src, _ = load_sample("chameleon_sample_level1_warmup.json")
    best, judged = resize_with_candidates(src, dict(src["canvas"]))
    assert judged[0].strategy == "anchor" and judged[0].score.penalty == 0.0
    fp = next(j for j in judged if j.strategy == "floorplan")
    assert fp.score.penalty > 0.0 and "disruption_penalty" in fp.score.notes


def test_two_stage_judge_renders_only_the_top_candidates():
    from engine import render as R
    if not R.enabled():
        pytest.skip("renderer unavailable or switched off")
    src, target = load_sample("chameleon_sample_level3_advanced.json")
    best, judged = resize_with_candidates(src, target)
    assert len(judged) > TOP_RENDER
    with_pixels = [j for j in judged if "pixels" in j.score.notes.get("contrast_source", "")]
    assert len(with_pixels) <= TOP_RENDER and judged[0] in with_pixels
    assert all(j.score.notes.get("contrast_source") == "estimate" for j in judged[TOP_RENDER + 1:] if not j.score.hard or True)
