"""Eval harness: the Crello converter on a synthetic Crello-shaped row, the
per-case metrics on the three shipped samples, the ground-truth agreement
metric, and a tiny end-to-end run_eval smoke run (resumable)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from engine.resize import resize_with_candidates
from eval import crello_convert as cc
from eval.metrics import evaluate_case, gt_agreement, structural
from eval.run_eval import build_cases, load_presets, main as run_eval_main, read_results, summarize

INPUT = Path(__file__).resolve().parent.parent / "input"
SAMPLES = sorted(INPUT.glob("*.json"))


# ---------------------------------------------------------------------------
# converter


def crello_row(normalized: bool = False, radians: bool = False) -> dict:
    """A decoded Crello v5-shaped template: background colour, full-bleed
    photo, a single-colour SVG pill, a multi-colour wide SVG, a serif headline
    with a two-colour run, a capitalised sans label rotated 30 degrees."""
    W, H = 1080, 1350
    lefts = [0, 0, 90, 40, 90, 400]
    tops = [0, 0, 1150, 40, 300, 700]
    widths = [1080, 1080, 400, 300, 900, 280]
    heights = [1350, 1350, 90, 100, 200, 60]
    angle = [0, 0, 0, 0, 0, 30.0]
    if normalized:
        lefts = [v / W for v in lefts]
        tops = [v / H for v in tops]
        widths = [v / W for v in widths]
        heights = [v / H for v in heights]
    if radians:
        angle = [math.radians(a) for a in angle]
    headline = "Chase the Light"
    label = "shop now"
    return {
        "id": "abc123", "length": 6, "group": "SM", "format": "Instagram", "canvas_width": W, "canvas_height": H,
        "category": "foodDrinks", "title": "Synthetic sale", "cluster_index": 3,
        "type": ["ColoredBackground", "ImageElement", "SvgElement", "SvgElement", "TextElement", "TextElement"],
        "left": lefts, "top": tops, "width": widths, "height": heights, "angle": angle,
        "opacity": [1.0, 1.0, 1.0, 0.5, 1.0, 1.0],
        "color": [["rgba(20, 30, 40, 1)"], [], ["rgba(232, 106, 58, 1)"], ["#ff0000", "#00ff00"], [], []],
        "text": ["", "", "", "", headline, label],
        "font": ["", "", "", "", "Playfair Display", "Montserrat"],
        "font_size": [0, 0, 0, 0, 72.0, 24.0],
        "font_bold": [[], [], [], [], [True] * len(headline), [False] * len(label)],
        "font_italic": [[], [], [], [], [False] * len(headline), [False] * len(label)],
        "text_color": [[], [], [], [], ["rgba(255, 255, 255, 1)"] * 6 + ["rgba(240, 178, 66, 1)"] * 9,
                       ["rgba(0, 0, 0, 1)"] * len(label)],
        "text_line": [[], [], [], [], [0] * len(headline), [0] * len(label)],
        "text_align": ["", "", "", "", "center", "left"],
        "capitalize": [False, False, False, False, False, True],
        "line_height": [1.0, 1.0, 1.0, 1.0, 1.1, 1.0],
        "letter_spacing": [0, 0, 0, 0, 0.0, 2.0],
    }


def test_convert_synthetic_template():
    d = cc.convert_template(crello_row(), angle_unit="degrees")
    src = d["source"]
    assert src["canvas"] == {"width": 1080, "height": 1350}
    els = src["elements"]
    assert [e["type"] for e in els] == ["shape", "image", "shape", "image", "text", "text"]
    assert [e["id"] for e in els] == [f"el_{i:02d}" for i in range(6)]
    assert [e["z_index"] for e in els] == list(range(6))
    # pixel geometry kept, background colour, full-bleed photo -> gradient cover
    assert els[0]["fill_color"] == "rgba(20,30,40,1)"
    assert (els[1]["asset_id"], els[1]["fit"]) == (cc.ASSET_BG, "cover")
    assert els[2]["fill_color"] == "rgba(232,106,58,1)" and els[2]["shape_type"] == "rectangle"
    assert els[3]["asset_id"] == cc.ASSET_LOGO and els[3]["opacity"] == 0.5
    assert (els[2]["x"], els[2]["y"], els[2]["width"], els[2]["height"]) == (90, 1150, 400, 90)
    # text
    h, lab = els[4], els[5]
    assert h["content"] == "Chase the Light" and h["font_family"] == "Solstice Serif"
    assert h["font_weight"] == "bold" and h["text_align"] == "center" and h["font_size"] == 72
    assert h["color"] == "rgba(240,178,66,1)"            # dominant colour
    assert h["style_runs"] == [{"start": 0, "end": 6, "color": "rgba(255,255,255,1)"}]
    assert lab["content"] == "SHOP NOW" and lab["font_family"] == "Solstice Sans"
    assert lab["rotation"] == 30 and lab["letter_spacing"] == 2 and "style_runs" not in lab
    # sidecar remembers the real fonts
    assert d["sidecar"]["elements"]["el_04"]["font"] == "Playfair Display"
    assert d["sidecar"]["elements"]["el_05"]["font"] == "Montserrat"
    assert d["meta"]["family"] == "tall" and d["meta"]["n_text"] == 2
    # the result is a valid source for the structural checks and the engine
    s = structural(src, src, src["canvas"])
    assert s["ids_ok"] and s["fields_ok"] and s["immutable_ok"]
    out, judged = resize_with_candidates(src, {"width": 1600, "height": 400})
    assert [e["id"] for e in out["elements"]] == [e["id"] for e in els]
    assert judged


def test_convert_normalized_coordinates_and_radians():
    a = cc.convert_template(crello_row(), angle_unit="degrees")["source"]["elements"]
    b = cc.convert_template(crello_row(normalized=True, radians=True), angle_unit="radians")["source"]["elements"]
    for x, y in zip(a, b):
        for k in ("x", "y", "width", "height", "rotation"):
            assert x[k] == pytest.approx(y[k], abs=0.05), k
    assert cc.detect_angle_unit([crello_row()]) == "degrees"
    assert cc.detect_angle_unit([crello_row(radians=True)]) == "radians"


def test_convert_skips_unusable_templates():
    row = crello_row()
    with pytest.raises(cc.SkipTemplate):
        cc.convert_template(row, max_elements=3)
    row["text"] = ["", "", "", "", "", ""]
    with pytest.raises(cc.SkipTemplate):
        cc.convert_template(row)


def test_decode_row_and_font_mapping():
    names = cc.classlabel_names({b"huggingface": json.dumps({"info": {"features": {
        "type": {"_type": "Sequence", "feature": {"_type": "ClassLabel", "names": ["SvgElement", "TextElement"]}},
        "format": {"_type": "ClassLabel", "names": ["Instagram", "Poster"]},
        "left": {"_type": "Sequence", "feature": {"dtype": "float32", "_type": "Value"}},
    }}}).encode()})
    assert set(names) == {"type", "format"}
    row = cc.decode_row({"type": [1, 0], "format": 1, "left": [0.1, 0.2]}, names)
    assert row["type"] == ["TextElement", "SvgElement"] and row["format"] == "Poster" and row["left"] == [0.1, 0.2]
    assert cc.map_font("Playfair Display") == "Solstice Serif"
    assert cc.map_font("Great Vibes") == "Solstice Serif"
    assert cc.map_font("Montserrat") == "Solstice Sans"
    assert cc.map_font("") == "Solstice Sans"
    assert cc.asset_for_box(1080, 1080, 1080, 1080) == (cc.ASSET_BG, "cover")
    assert cc.asset_for_box(600, 150, 1080, 1080) == (cc.ASSET_LOGO, "contain")
    assert cc.asset_for_box(400, 420, 1080, 1080) == (cc.ASSET_HERO, "contain")
    assert cc.asset_for_box(700, 700, 1080, 1080, photo=True) == (cc.ASSET_BG, "cover")


def _fake_design(i: str, title: str, w: int, h: int, texts: list[str]) -> dict:
    els = [{"id": f"el_{k:02d}", "type": "text", "x": 0, "y": 40 * k, "width": 300, "height": 30,
            "content": t, "font_family": "Solstice Sans", "font_size": 20, "color": "rgba(0,0,0,1)"}
           for k, t in enumerate(texts)]
    return {"id": i, "source": {"canvas": {"width": w, "height": h}, "elements": els},
            "meta": {"title": title, "canvas": {"width": w, "height": h}, "family": cc.ratio_family(w, h)}}


def test_find_pairs_and_balanced_selection():
    designs = [
        _fake_design("a1", "Summer Sale", 1080, 1080, ["Summer Sale", "50% off"]),
        _fake_design("a2", "Summer Sale", 1080, 1920, ["Summer sale", "shop"]),
        _fake_design("a3", "Summer Sale", 1080, 1080, ["Summer Sale"]),          # same size as a1: still family
        _fake_design("b1", "Other", 728, 90, ["Other text"]),
        _fake_design("b2", "Other", 300, 250, ["Nothing shared"]),              # no shared text -> dropped
        _fake_design("c1", "None", 600, 600, ["x y z"]),
        _fake_design("c2", "None", 600, 1200, ["x y z"]),                       # title None never pairs
    ] + [_fake_design(f"t{k}", f"tall {k}", 600, 1200, ["tall text"]) for k in range(6)]
    pairs = cc.find_pairs(designs)
    assert pairs == [["a1", "a2", "a3"]]
    chosen = cc.select_designs(designs, target=7, pairs=pairs)
    ids = [d["id"] for d in chosen]
    assert ids[:3] == ["a1", "a2", "a3"]
    fams = [d["meta"]["family"] for d in chosen[3:]]
    assert "banner" in fams and "square" in fams and "tall" in fams      # round robin over families
    assert len(chosen) == 7


# ---------------------------------------------------------------------------
# metrics


def test_presets_come_from_the_playground():
    presets = load_presets()
    assert ("Leaderboard ad", 728, 90) in presets and ("Story / Reel", 1080, 1920) in presets
    assert len(presets) >= 10


@pytest.mark.parametrize("path", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_metrics_on_shipped_samples(path):
    t = json.loads(path.read_text())
    source, target = t["source"], t["target_canvas"]
    best, judged = resize_with_candidates(source, target)
    row = evaluate_case(source, best, target, judged, elapsed=0.5)
    assert row["ids_ok"] and row["ids_order_ok"] and row["fields_ok"] and row["immutable_ok"] and row["canvas_ok"]
    assert row["offcanvas_n"] == 0 and row["aspect_fail_n"] == 0 and row["overflow_n"] == 0
    assert row["overlap_n"] == 0 and row["below_floor_n"] == 0
    assert row["defect_n"] == 0
    assert row["winner"] == judged[0].name and row["strategy"] in ("anchor", "floorplan")
    assert row["n_candidates"] == len(judged) and row["min_font"] >= 1   # L3 -> 728x90 keeps 3px badge labels on purpose
    assert set(k for k in row if k.startswith(("read.", "layout.", "faith."))) == set(judged[0].score.breakdown)
    # the metrics do flag damage: push the headline off canvas and squash an image
    broken = json.loads(json.dumps(best))
    for el in broken["elements"]:
        if el["type"] == "text":
            el["x"] = target["width"] - el["width"] / 2
        if el["type"] == "image" and el.get("fit", "contain") != "cover":
            el["width"] *= 1.5
    row2 = evaluate_case(source, broken, target, judged)
    assert row2["offcanvas_n"] >= 1 and row2["defect_n"] >= 1
    if any(e["type"] == "image" and e.get("fit", "contain") != "cover" for e in source["elements"]):
        assert row2["aspect_fail_n"] >= 1


def test_gt_agreement_identity_and_shuffle():
    t = json.loads(SAMPLES[1].read_text())
    source = t["source"]
    same = gt_agreement(source, source)
    assert same["gt_n"] >= 3
    assert same["gt_pos_err"] == 0 and same["gt_order_tau"] == 1 and same["gt_size_rho"] == 1
    assert same["gt_font_ratio"] == 1 and same["gt_width_ratio"] == 1
    # reverse the vertical order of the texts and halve their fonts
    other = json.loads(json.dumps(source))
    texts = [e for e in other["elements"] if e["type"] == "text"]
    ys = [e["y"] for e in texts]
    for e, y in zip(texts, reversed(ys)):
        e["y"] = y
        e["font_size"] /= 2
    diff = gt_agreement(source, other)
    assert diff["gt_pos_err"] > 0 and diff["gt_order_tau"] < 0.5
    assert diff["gt_font_ratio"] == pytest.approx(2.0, rel=0.01)
    # a design with no shared text has nothing to compare
    assert gt_agreement(source, {"canvas": source["canvas"], "elements": []}) == {"gt_n": 0}


# ---------------------------------------------------------------------------
# run_eval end to end


def test_run_eval_smoke_is_resumable(tmp_path):
    data = tmp_path / "data"
    (data / "designs").mkdir(parents=True)
    d1 = cc.convert_template(crello_row(), angle_unit="degrees")
    d2 = json.loads(json.dumps(d1))
    d2["id"] = "abc456"
    d2["source"]["canvas"] = {"width": 1200, "height": 628}
    d2["meta"]["canvas"] = {"width": 1200, "height": 628}
    d2["meta"]["family"] = "wide"
    index = []
    for d, sib in ((d1, ["abc456"]), (d2, ["abc123"])):
        d["meta"]["siblings"] = sib
        (data / "designs" / f"{d['id']}.json").write_text(json.dumps(d))
        index.append({"id": d["id"], "file": f"designs/{d['id']}.json", **d["meta"]})
    (data / "index.json").write_text(json.dumps(index))

    cases = build_cases(index, load_presets()[:2], data)
    assert len(cases) == 2 * 2 + 2 and sum(1 for c in cases if c["gt_id"]) == 2

    run = tmp_path / "run"
    args = ["--data-dir", str(data), "--out", str(run), "--presets", "Leaderboard ad,Instagram post",
            "--no-samples", "--no-render", "--log-every", "0"]
    assert run_eval_main(args) == 0
    rows = read_results(run)
    assert len(rows) == 6 and all(not r["error"] for r in rows)
    assert (run / "results.csv").exists() and (run / "summary.md").exists()
    gt = [r for r in rows if r["gt_id"]]
    assert gt and all(r["gt_n"] == 2 for r in gt)
    n_lines = len((run / "results.jsonl").read_text().splitlines())
    # second invocation: nothing to do, nothing appended
    assert run_eval_main(args) == 0
    assert len((run / "results.jsonl").read_text().splitlines()) == n_lines
    s = summarize(read_results(run))
    assert s["n_cases"] == 6 and s["n_gt_cases"] == 2 and "any_defect" in s["failure_rate"]
    assert set(s["by_preset"]) == {"Leaderboard ad", "Instagram post", "gt (designer siblings)"}


def test_text_boxes_are_normalized_to_the_fit_model():
    """Crello sizes a text box as font_size x line_height; the engine's fit
    model needs ascent + descent, and the wrap ignores letter spacing. The
    converter grows such boxes (height always, width only when a line spills)
    and keeps the alignment anchor."""
    from engine.textfit import default_measurer

    row = crello_row()
    row["height"][4] = 72.0                      # headline box exactly one font size tall
    row["letter_spacing"][4] = 30.0              # ... and heavily letter-spaced
    raw = cc.convert_template(row, angle_unit="degrees", normalize_boxes=False)["source"]["elements"][4]
    m = default_measurer()
    assert not m.fits(raw, raw["font_size"], raw["width"], raw["height"])
    d = cc.convert_template(row, angle_unit="degrees")
    h = d["source"]["elements"][4]
    assert m.fits(h, h["font_size"], h["width"], h["height"])
    grown = d["sidecar"]["elements"]["el_04"]["box_grown"]
    assert grown["h"] > 1.0 and grown["w"] > 1.0
    assert h["x"] + h["width"] / 2 == pytest.approx(raw["x"] + raw["width"] / 2, abs=1.0)   # centred text stays centred
    assert h["font_size"] == raw["font_size"] and h["content"] == raw["content"]
    assert d["sidecar"]["boxes_normalized"] is True


def test_no_zero_size_text_elements_reach_the_official_renderer():
    """Found by the eval run: 23 of 6058 cases (all 728x90) had a text element
    squeezed to 0x0, and cr-renderer's TextElement model (width/height > 0)
    then rejects the whole design, so no PNG would be produced."""
    from renderer.converter.convert import _get_renderer, convert_chameleon_to_crello

    fixture = Path(__file__).resolve().parent / "fixtures" / "zero_size_text_regression.json"
    source = json.loads(fixture.read_text())["source"]
    out, _ = resize_with_candidates(source, {"width": 728, "height": 90})
    for el in out["elements"]:
        if el["type"] == "text":
            assert el["width"] >= 1 and el["height"] >= 1, el["id"]
            assert 0 <= el["x"] <= 728 - el["width"] and 0 <= el["y"] <= 90 - el["height"], el["id"]
    renderer = _get_renderer(str(Path(__file__).resolve().parent.parent / "brand_kit" / "fonts"))
    example, _ = convert_chameleon_to_crello(out, renderer.font_manager,
                                             str(Path(__file__).resolve().parent.parent / "brand_kit" / "assets"))
    assert len(renderer.render(example, max_size=400, format="png")) > 0
