"""End-to-end checks on resize(): structural rules plus the Level 1 anchor path."""

import json
from pathlib import Path

import pytest

from engine.resize import resize
from engine.textfit import default_measurer

INPUT = Path(__file__).resolve().parent.parent / "input"
SAMPLES = sorted(INPUT.glob("*.json"))


def load(path):
    t = json.loads(Path(path).read_text())
    return t["source"], t["target_canvas"]


@pytest.mark.parametrize("path", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_structural_rules(path):
    source, target = load(path)
    out = resize(source, target)
    assert out["canvas"] == {"width": target["width"], "height": target["height"]}
    src_ids = [el["id"] for el in source["elements"]]
    assert [el["id"] for el in out["elements"]] == src_ids       # same ids, same order
    by_id = {el["id"]: el for el in source["elements"]}
    for el in out["elements"]:
        s = by_id[el["id"]]
        assert el["type"] == s["type"]
        for k in ("content", "font_family", "asset_id", "shape_type", "fill_color",
                  "style_runs", "group_id", "rotation", "opacity", "z_index"):
            if k in s:
                assert el[k] == s[k], f"{el['id']}.{k} changed"
        assert el["width"] >= 0 and el["height"] >= 0
        if el["type"] == "image" and s.get("fit", "contain") != "cover" and s["width"] > 0 and s["height"] > 0:
            assert el["width"] / el["height"] == pytest.approx(s["width"] / s["height"], rel=0.05)
        if el["type"] == "text":
            assert el["font_size"] >= 1


@pytest.mark.parametrize("path", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_important_elements_stay_on_canvas(path):
    source, target = load(path)
    out = resize(source, target)
    W, H = target["width"], target["height"]
    for el in out["elements"]:
        if el["type"] == "shape" and el.get("opacity", 1) < 0.35:
            continue  # decorative bleed is allowed
        assert el["x"] >= -0.5 and el["y"] >= -0.5
        assert el["x"] + el["width"] <= W + 0.5
        assert el["y"] + el["height"] <= H + 0.5


def test_level1_anchor_path():
    source, target = load(INPUT / "chameleon_sample_level1_warmup.json")
    src = {el["id"]: el for el in source["elements"]}
    out = {el["id"]: el for el in resize(source, target)["elements"]}
    # background covers the new canvas
    assert (out["bg"]["x"], out["bg"]["y"], out["bg"]["width"], out["bg"]["height"]) == (0, 0, 1080, 1350)
    # nothing had to shrink (the judge may pick a content scale a little
    # above min(sx, sy) = 1 since the taller canvas has room, and the v7
    # optimiser may grow a primary unit up to the judge's size ambition
    # (AMBITION 1.2 x the proportional size, in 10 % steps); never below)
    for i in ("logo", "headline", "cta"):
        assert src[i]["width"] <= out[i]["width"] <= 1.4 * src[i]["width"]
        assert out[i]["width"] / out[i]["height"] == pytest.approx(src[i]["width"] / src[i]["height"], rel=0.02)
    # the logo keeps hugging the top (margin grows with the canvas, 60 -> 75;
    # the v7 optimiser may settle it a little lower for balance, never above
    # the proportional margin nor out of the top band) and stays centred
    assert 75 - 0.5 <= out["logo"]["y"] <= 0.10 * 1350
    assert out["logo"]["x"] + out["logo"]["width"] / 2 == pytest.approx(540)
    # reading order and spacing preserved: logo above headline above cta
    assert out["logo"]["y"] + out["logo"]["height"] < out["headline"]["y"]
    assert out["headline"]["y"] + out["headline"]["height"] < out["cta"]["y"]
    # font sizes never shrink when nothing is cramped, and scale with the boxes
    assert out["headline"]["font_size"] >= 60 and out["cta"]["font_size"] >= 30
    assert out["headline"]["font_size"] / 60 == pytest.approx(out["headline"]["width"] / 800, abs=0.03)


def test_text_fits_its_box_level1():
    source, target = load(INPUT / "chameleon_sample_level1_warmup.json")
    m = default_measurer()
    for el in resize(source, target)["elements"]:
        if el["type"] == "text":
            lay = m.layout(el)
            assert lay.max_width <= el["width"] + 0.5
            assert lay.height <= el["height"] + 0.5


def test_textfit_shrinks_when_cramped():
    m = default_measurer()
    el = {"content": "Chase the Light", "font_family": "Solstice Serif", "font_weight": "bold",
          "font_size": 60, "width": 200, "height": 40}
    assert not m.fits(el, 60, 200, 40)
    size = m.fit_font_size(el, 200, 40, 60)
    assert 8 <= size < 60
    assert m.fits(el, size, 200, 40)
