"""Floor-plan path (big ratio changes): Level 2 (square -> 1600x400 banner)
and Level 3 (poster -> 728x90 leaderboard) through resize()."""

import json
from pathlib import Path

import pytest

from engine import analyze as A
from engine.floorplan import BANNER, SQUARE, TALL, WIDE, ratio_family
from engine.geometry import Box
from engine.resize import resize
from engine.textfit import default_measurer

INPUT = Path(__file__).resolve().parent.parent / "input"
BIG = [INPUT / "chameleon_sample_level2_core.json", INPUT / "chameleon_sample_level3_advanced.json"]


def load(path):
    t = json.loads(Path(path).read_text())
    return t["source"], t["target_canvas"]


@pytest.fixture(scope="module", params=BIG, ids=[p.stem for p in BIG])
def case(request):
    source, target = load(request.param)
    return source, target, resize(source, target)


def _unit_boxes(analysis, elements):
    by_id = {el["id"]: el for el in elements}
    return {u.key: Box.union(Box.of(by_id[i]) for i in u.ids) for u in analysis.content_units()}


def test_ratio_families():
    assert ratio_family(Box(0, 0, 1080, 1920)) == TALL
    assert ratio_family(Box(0, 0, 1080, 1080)) == SQUARE
    assert ratio_family(Box(0, 0, 1200, 628)) == WIDE
    assert ratio_family(Box(0, 0, 1600, 400)) == BANNER
    assert ratio_family(Box(0, 0, 728, 90)) == BANNER


def test_all_ids_present_once(case):
    source, _, out = case
    assert [el["id"] for el in out["elements"]] == [el["id"] for el in source["elements"]]


def test_no_new_overlaps_between_content_units(case):
    source, target, out = case
    analysis = A.analyze(source)
    before = _unit_boxes(analysis, source["elements"])
    after = _unit_boxes(analysis, out["elements"])
    units = analysis.content_units()
    for i, a in enumerate(units):
        for b in units[i + 1:]:
            if before[a.key].overlaps(before[b.key], tol=1.0):
                continue   # intentional in the source
            assert not after[a.key].overlaps(after[b.key], tol=1.0), f"{a.key} overlaps {b.key}"


def test_text_fits_its_box(case):
    _, _, out = case
    m = default_measurer()
    for el in out["elements"]:
        if el["type"] == "text":
            lay = m.layout(el)
            assert lay.max_width <= el["width"] + 0.5, el["id"]
            assert lay.height <= el["height"] + 0.5, el["id"]
            assert el["font_size"] >= 1


def test_image_aspect_kept(case):
    source, _, out = case
    src = {el["id"]: el for el in source["elements"]}
    for el in out["elements"]:
        s = src[el["id"]]
        if el["type"] == "image" and s.get("fit", "contain") != "cover":
            assert el["width"] / el["height"] == pytest.approx(s["width"] / s["height"], rel=0.05), el["id"]


def test_content_units_on_canvas(case):
    source, target, out = case
    analysis = A.analyze(source)
    W, H = target["width"], target["height"]
    for el in out["elements"]:
        if analysis.roles[el["id"]] in (A.BACKGROUND, A.DECORATIVE):
            continue
        assert el["x"] >= -0.5 and el["y"] >= -0.5, el["id"]
        assert el["x"] + el["width"] <= W + 0.5 and el["y"] + el["height"] <= H + 0.5, el["id"]


def test_level2_reads_as_a_banner():
    source, target = load(INPUT / "chameleon_sample_level2_core.json")
    out = {el["id"]: el for el in resize(source, target)["elements"]}
    # one row: logo on the left, bottle next, headline readable, CTA button intact on the right
    assert out["logo"]["x"] < out["product"]["x"] < out["headline"]["x"] < out["cta_bg"]["x"]
    assert out["product"]["height"] >= 0.6 * 400
    assert out["headline"]["font_size"] >= 30
    assert out["cta_label"]["x"] >= out["cta_bg"]["x"] - 0.5
    assert out["cta_label"]["x"] + out["cta_label"]["width"] <= out["cta_bg"]["x"] + out["cta_bg"]["width"] + 0.5
    assert out["cta_label"]["y"] >= out["cta_bg"]["y"] and out["cta_label"]["y"] + out["cta_label"]["height"] <= out["cta_bg"]["y"] + out["cta_bg"]["height"] + 0.5
    assert out["bg"] | {"x": 0, "y": 0, "width": 1600, "height": 400} == out["bg"]


def test_level3_legible_at_728x90():
    source, target = load(INPUT / "chameleon_sample_level3_advanced.json")
    out = {el["id"]: el for el in resize(source, target)["elements"]}
    m = default_measurer()
    assert out["headline"]["font_size"] >= 10
    assert m.layout(out["headline"]).n_lines <= 3
    assert out["cta_label"]["font_size"] >= 8
    assert out["logo"]["height"] >= 14
    for i in ("badge1_bg", "badge2_bg", "badge3_bg", "ribbon_bg", "legal_text", "holiday_watermark"):
        assert out[i]["width"] > 0 and out[i]["height"] > 0
