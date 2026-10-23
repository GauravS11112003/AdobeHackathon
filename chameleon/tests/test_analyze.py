"""Role / anchor inference checked against the three shipped samples.

The sample ids are descriptive (headline, logo, ...) which is exactly what
hidden tasks will NOT give us, so these tests assert that the analyzer
reaches the same conclusions from geometry alone.
"""

import json
from pathlib import Path

import pytest

from engine import analyze as A
from engine.geometry import Box
from engine.relayout import ratio_change

INPUT = Path(__file__).resolve().parent.parent / "input"


def load(name):
    return json.loads((INPUT / name).read_text())


@pytest.fixture(scope="module")
def l1():
    return A.analyze(load("chameleon_sample_level1_warmup.json")["source"])


@pytest.fixture(scope="module")
def l2():
    return A.analyze(load("chameleon_sample_level2_core.json")["source"])


@pytest.fixture(scope="module")
def l3():
    return A.analyze(load("chameleon_sample_level3_advanced.json")["source"])


# -- roles ------------------------------------------------------------------

def test_level1_roles(l1):
    assert l1.roles == {"bg": A.BACKGROUND, "logo": A.LOGO, "headline": A.HEADLINE, "cta": A.CTA}


def test_level2_roles(l2):
    r = l2.roles
    assert r["bg"] == A.BACKGROUND
    assert r["deco_circle_1"] == A.DECORATIVE and r["deco_circle_2"] == A.DECORATIVE
    assert r["logo"] == A.LOGO
    assert r["product"] == A.HERO
    assert r["headline"] == A.HEADLINE
    assert r["subhead"] == A.SUBHEAD
    assert r["badge_bg"] == r["badge_label"] == A.BADGE
    assert r["cta_bg"] == r["cta_label"] == A.CTA


def test_level3_roles(l3):
    r = l3.roles
    assert r["bg"] == A.BACKGROUND
    assert r["logo"] == A.LOGO
    assert r["product"] == A.HERO
    assert r["headline"] == A.HEADLINE
    assert r["subhead"] == A.SUBHEAD
    assert r["legal_text"] == A.FINE_PRINT
    assert r["holiday_watermark"] == A.IMAGE          # missing asset, bottom corner: not the logo
    for n in (1, 2, 3):
        assert r[f"badge{n}_bg"] == r[f"badge{n}_label"] == A.BADGE
    assert r["ribbon_bg"] == r["ribbon_label"] == A.BADGE
    assert r["cta_bg"] == r["cta_label"] == A.CTA


# -- groups & units ----------------------------------------------------------

def test_groups_become_single_units(l2):
    cta = l2.unit("group:cta")
    assert sorted(cta.ids) == ["cta_bg", "cta_label"]
    assert cta.box == Box(330, 950, 420, 90)           # union of the members
    assert l2.element_unit["cta_label"] == "group:cta"


def test_every_element_in_exactly_one_unit(l3):
    src = load("chameleon_sample_level3_advanced.json")["source"]
    ids = [el["id"] for el in src["elements"]]
    seen = [i for u in l3.units for i in u.ids]
    assert sorted(seen) == sorted(ids)


# -- anchors & order ---------------------------------------------------------

def test_level1_anchors(l1):
    assert (l1.unit("logo").anchor_x, l1.unit("logo").anchor_y) == ("center", "top")
    assert l1.unit("headline").anchor_x == "center"
    assert l1.unit("cta").anchor_x == "center"


def test_level2_anchors(l2):
    assert (l2.unit("group:badge").anchor_x, l2.unit("group:badge").anchor_y) == ("left", "top")
    assert l2.unit("deco_circle_2").anchor_x == "right"
    assert l2.unit("group:cta").anchor_y == "bottom"


def test_reading_order_is_top_to_bottom_left_to_right(l3):
    order = [u.key for u in l3.units if u.reading_index >= 0]
    assert order.index("logo") < order.index("product") < order.index("headline")
    assert order.index("headline") < order.index("subhead") < order.index("group:badge1")
    assert order.index("group:badge1") < order.index("group:badge2") < order.index("group:badge3")
    assert order.index("group:cta") < order.index("legal_text")
    # background and decoration are not part of the reading order
    assert l3.unit("bg").reading_index == -1


def test_importance_puts_headline_first(l2):
    content = sorted(l2.content_units(), key=lambda u: -u.importance)
    assert content[0].role == A.HEADLINE
    assert content[-1].role in (A.BADGE, A.SUBHEAD)


def test_ratio_change():
    assert ratio_change(Box(0, 0, 1080, 1080), Box(0, 0, 1080, 1350)) == pytest.approx(1.25)
    assert ratio_change(Box(0, 0, 1080, 1080), Box(0, 0, 1600, 400)) == pytest.approx(4.0)


# -- robustness: no names, odd input ----------------------------------------

def test_opaque_ids_do_not_change_roles():
    task = load("chameleon_sample_level2_core.json")["source"]
    mapping = {el["id"]: f"e{i}" for i, el in enumerate(task["elements"])}
    for el in task["elements"]:
        el["id"] = mapping[el["id"]]
    a = A.analyze(task)
    assert a.roles[mapping["headline"]] == A.HEADLINE
    assert a.roles[mapping["product"]] == A.HERO
    assert a.roles[mapping["cta_label"]] == A.CTA


def test_single_text_element_is_headline():
    a = A.analyze({"canvas": {"width": 100, "height": 100}, "elements": [
        {"id": "t", "type": "text", "x": 10, "y": 10, "width": 80, "height": 20,
         "content": "Hi", "font_family": "Solstice Sans", "font_size": 12, "color": "rgba(0,0,0,1)"}]})
    assert a.roles == {"t": A.HEADLINE}
