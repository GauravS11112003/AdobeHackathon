"""v12: content the source showed is never hidden under a panel (engine/visibility.py)."""

from __future__ import annotations

import copy

from engine import resize as RZ
from engine.analyze import analyze
from engine.geometry import Box
from engine.visibility import hidden_content, reveal


def _source() -> dict:
    """A wide poster: a photo on the right, a white card drawn *above* it on
    the left two thirds (the photo peeks out on the right), copy on the card."""
    return {
        "canvas": {"width": 1500, "height": 600},
        "elements": [
            {"id": "a", "type": "image", "asset_id": "background_gradient", "fit": "cover",
             "x": 600, "y": 0, "width": 900, "height": 600, "z_index": 0},
            {"id": "b", "type": "shape", "shape_type": "rectangle", "fill_color": "rgba(255,255,255,1)",
             "x": 0, "y": 0, "width": 1000, "height": 600, "z_index": 1},
            {"id": "c", "type": "text", "content": "Nature Expo 2019", "font_family": "Solstice Sans",
             "font_weight": "bold", "font_size": 72, "color": "rgba(20,20,20,1)", "text_align": "left",
             "x": 60, "y": 80, "width": 800, "height": 100, "z_index": 2},
            {"id": "d", "type": "text", "content": "Get ready for the most remarkable eco-event of the year.",
             "font_family": "Solstice Sans", "font_size": 28, "color": "rgba(20,20,20,1)", "text_align": "left",
             "x": 60, "y": 240, "width": 800, "height": 80, "z_index": 3},
        ],
    }


def test_a_photo_under_a_grown_card_is_found_and_revealed():
    src = _source()
    an = analyze(src)
    out = copy.deepcopy(src["elements"])
    by = {e["id"]: e for e in out}
    # the card grew over the whole canvas and the photo moved under it
    by["b"].update(x=0, y=0, width=1500, height=600)
    by["a"].update(x=900, y=150, width=450, height=300)
    hidden = hidden_content(an, out)
    assert [h[0] for h in hidden] == ["a"]
    notes = reveal(an, out, Box(0, 0, 1500, 600))
    assert notes and not hidden_content(an, out)
    assert all(isinstance(e["z_index"], int) for e in out)


def test_the_designers_own_layering_is_not_a_defect():
    src = _source()
    assert hidden_content(analyze(src), copy.deepcopy(src["elements"])) == []


def _poster() -> dict:
    """The eval case that showed the defect, rebuilt: a white card over the
    left two thirds of a 3000 x 1055 poster drawn above the photo it half
    covers. v11 blew the card up to a story's full height above the photo."""
    def t(i, c, fs, x, y, w, h, z):
        return {"id": i, "type": "text", "content": c, "font_family": "Solstice Sans", "font_weight": "bold",
                "font_size": fs, "color": "rgba(20,20,20,1)", "text_align": "left",
                "x": x, "y": y, "width": w, "height": h, "z_index": z}
    return {"canvas": {"width": 3000, "height": 1055}, "elements": [
        {"id": "a", "type": "image", "asset_id": "background_gradient", "fit": "cover",
         "x": 730, "y": 0, "width": 2270, "height": 1055, "z_index": 0},
        {"id": "b", "type": "shape", "shape_type": "rectangle", "fill_color": "rgba(255,255,255,1)",
         "x": 0, "y": 0, "width": 2060, "height": 1055, "z_index": 1},
        t("c", "NATURE EXPO 2019", 130, 80, 120, 1600, 160, 2),
        t("d", "Get ready for the most remarkable eco-event!", 48, 80, 420, 900, 120, 3),
        t("e", "LEARN DETAILED INFORMATION BY 63-992-992-1821", 34, 80, 640, 900, 100, 4),
        t("f", "Don't miss out, book your place today on naturexpo.us", 48, 80, 830, 1500, 140, 5),
        {"id": "g", "type": "shape", "shape_type": "rectangle", "fill_color": "rgba(253,235,101,1)",
         "x": 1900, "y": 80, "width": 360, "height": 360, "z_index": 6},
        t("h", "1-6", 90, 1990, 200, 200, 110, 7),
    ]}


def test_resize_never_hides_the_photo(monkeypatch):
    """Without the v12 repair this design hides the photo at all three sizes."""
    monkeypatch.setattr(RZ, "JUDGE_RENDER", False)
    src = _poster()
    an = analyze(src)
    for w, h in ((1080, 1920), (1080, 1350), (160, 600)):
        out = RZ.resize(src, {"width": w, "height": h})
        assert hidden_content(an, out["elements"]) == [], (w, h)
