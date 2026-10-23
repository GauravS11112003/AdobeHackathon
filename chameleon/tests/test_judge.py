"""Judge loop (Idea 2): candidates -> rectify -> render -> score -> best.

Checks that the chosen candidate on every shipped sample is defect-free,
that the scorer prefers the engine's output to a deliberately perturbed
copy, that the rectifier removes an injected collision while keeping group
insets, and that the loop stays fast."""

import copy
import json
import time
from pathlib import Path

import pytest

from engine import analyze as A
from engine.geometry import Box, clamp
from engine.rectify import rectify, unwanted_overlaps
from engine.resize import resize, resize_with_candidates
from engine.score import WEIGHTS, score_design

INPUT = Path(__file__).resolve().parent.parent / "input"
SAMPLES = sorted(INPUT.glob("*.json"))


def load(path):
    t = json.loads(Path(path).read_text())
    return t["source"], t["target_canvas"]


@pytest.fixture(scope="module", params=SAMPLES, ids=[p.stem for p in SAMPLES])
def judged(request):
    source, target = load(request.param)
    t0 = time.time()
    best, cands = resize_with_candidates(source, target)
    return source, target, best, cands, time.time() - t0


def test_winner_is_best_of_several_with_no_hard_fails(judged):
    source, target, best, cands, _ = judged
    assert len(cands) >= 3
    assert cands[0].design is best
    assert cands[0].score.hard == [], cands[0].score.hard
    totals = [c.score.total for c in cands]
    assert totals == sorted(totals, reverse=True)
    assert len({c.name for c in cands}) == len(cands)
    for c in cands:
        assert set(c.score.breakdown) == set(WEIGHTS)
        assert all(0.0 <= v <= 1.0 for v in c.score.breakdown.values())


def test_loop_is_fast(judged):
    *_, elapsed = judged
    assert elapsed < 10.0


def test_resize_returns_the_winner(judged):
    source, target, best, cands, _ = judged
    out = resize(source, target)
    assert [el["id"] for el in out["elements"]] == [el["id"] for el in source["elements"]]
    assert out == best


def test_perturbed_layout_scores_worse(judged):
    """Shift half of the content units by 30 % of the canvas (clamped so
    nothing leaves the canvas): collisions and a scrambled order must lose."""
    source, target, best, cands, _ = judged
    analysis = A.analyze(source)
    W, H = target["width"], target["height"]
    bad = copy.deepcopy(best)
    by_id = {el["id"]: el for el in bad["elements"]}
    for i, unit in enumerate(analysis.content_units()):
        if i % 2:
            continue
        ub = Box.union(Box.of(by_id[e]) for e in unit.ids)
        dx = clamp(ub.x + 0.3 * W, 0.0, max(0.0, W - ub.w)) - ub.x
        dy = clamp(ub.y + 0.3 * H, 0.0, max(0.0, H - ub.h)) - ub.y
        for e in unit.ids:
            by_id[e]["x"] += dx
            by_id[e]["y"] += dy
    worse = score_design(analysis, source, bad, Box(0, 0, W, H))
    assert worse.total < cands[0].score.total - 5.0


def test_score_without_pixels_still_works():
    source, target = load(INPUT / "chameleon_sample_level2_core.json")
    analysis = A.analyze(source)
    out = resize(source, target)
    sc = score_design(analysis, source, out, render=False)
    assert sc.hard == []
    # no pixels: contrast comes from the JSON estimate (engine/contrast.py)
    assert 0.0 <= sc.breakdown["read.contrast"] <= 1.0
    assert sc.notes["contrast_source"] == "estimate" and sc.notes["contrast"]
    assert "pixels" in sc.notes


def _level2_output():
    source, target = load(INPUT / "chameleon_sample_level2_core.json")
    analysis = A.analyze(source)
    out = resize(source, target)
    return source, target, analysis, out


def test_rectifier_removes_injected_overlap():
    source, target, analysis, out = _level2_output()
    els = copy.deepcopy(out["elements"])
    by_id = {el["id"]: el for el in els}
    assert unwanted_overlaps(analysis, els) == []
    # drop the NEW FLAVOR badge onto the headline
    dx = by_id["headline"]["x"] + 10 - by_id["badge_bg"]["x"]
    dy = by_id["headline"]["y"] - by_id["badge_bg"]["y"]
    for e in ("badge_bg", "badge_label"):
        by_id[e]["x"] += dx
        by_id[e]["y"] += dy
    assert unwanted_overlaps(analysis, els), "the injected collision should be detected"
    inset_before = (by_id["badge_label"]["x"] - by_id["badge_bg"]["x"], by_id["badge_label"]["y"] - by_id["badge_bg"]["y"])
    scale_before = by_id["badge_label"]["width"] / by_id["badge_bg"]["width"]

    fixed = rectify(analysis, els, Box(0, 0, target["width"], target["height"]))
    assert [el["id"] for el in fixed] == [el["id"] for el in els]
    assert unwanted_overlaps(analysis, fixed) == []
    fb = {el["id"]: el for el in fixed}
    # group insets are preserved exactly (uniform scale), fonts never grow
    s = fb["badge_bg"]["width"] / by_id["badge_bg"]["width"]
    assert fb["badge_label"]["x"] - fb["badge_bg"]["x"] == pytest.approx(inset_before[0] * s, abs=0.6)
    assert fb["badge_label"]["y"] - fb["badge_bg"]["y"] == pytest.approx(inset_before[1] * s, abs=0.6)
    assert fb["badge_label"]["width"] / fb["badge_bg"]["width"] == pytest.approx(scale_before, rel=0.01)
    for el in fixed:
        if el["type"] == "text":
            assert el["font_size"] <= by_id[el["id"]]["font_size"] + 1e-6
    # untouched elements stay where they were
    for e in ("bg", "logo", "product"):
        assert fb[e]["x"] == pytest.approx(by_id[e]["x"]) and fb[e]["y"] == pytest.approx(by_id[e]["y"])


def test_rectifier_pulls_units_back_on_canvas():
    source, target, analysis, out = _level2_output()
    els = copy.deepcopy(out["elements"])
    by_id = {el["id"]: el for el in els}
    for e in ("cta_bg", "cta_label"):
        by_id[e]["x"] += 300   # half of the button leaves the right edge
    fixed = rectify(analysis, els, Box(0, 0, target["width"], target["height"]))
    fb = {el["id"]: el for el in fixed}
    for e in ("cta_bg", "cta_label"):
        assert fb[e]["x"] + fb[e]["width"] <= target["width"] + 0.5
    assert unwanted_overlaps(analysis, fixed) == []


def test_rectifier_terminates_and_keeps_clean_output_clean():
    source, target, analysis, out = _level2_output()
    fixed = rectify(analysis, out["elements"], Box(0, 0, target["width"], target["height"]), passes=50)
    assert unwanted_overlaps(analysis, fixed) == []
    for a, b in zip(out["elements"], fixed):
        for k in ("x", "y", "width", "height"):
            assert abs(a[k] - b[k]) <= 2.0, (a["id"], k)


# -- the renderer is a bonus, never a dependency ------------------------------

@pytest.fixture
def fresh_render(monkeypatch):
    from engine import render as R
    R._reset_for_tests()
    monkeypatch.delenv("CHAMELEON_RENDER", raising=False)
    monkeypatch.delenv("CHAMELEON_NO_RENDER", raising=False)
    yield R
    R._reset_for_tests()


def test_judge_survives_a_raising_renderer(monkeypatch, fresh_render):
    import engine.score as S
    from engine import resize as RZ

    def boom(*a, **k):
        raise RuntimeError("skia exploded")

    monkeypatch.setattr(S, "render_design", boom)
    source, target = load(INPUT / "chameleon_sample_level2_core.json")
    out = RZ.resize(source, target)
    assert [el["id"] for el in out["elements"]] == [el["id"] for el in source["elements"]]
    best = RZ.LAST_JUDGED[0]
    assert best.design == out and best.score.hard == [] and not best.fallback
    assert "render_error" in best.score.notes and best.score.notes["contrast_source"] == "estimate"


def test_judge_without_pixels_still_picks_a_clean_floor_plan(monkeypatch, fresh_render):
    from engine import resize as RZ
    monkeypatch.setenv("CHAMELEON_RENDER", "0")
    assert not fresh_render.enabled() and fresh_render.status().startswith("off")
    source, target = load(INPUT / "chameleon_sample_level3_advanced.json")
    out = RZ.resize(source, target)
    best = RZ.LAST_JUDGED[0]
    assert best.design == out and best.score.hard == [] and best.strategy == "floorplan"
    assert best.score.notes.get("pixels")


def test_slow_render_switches_pixels_off(monkeypatch, fresh_render):
    R = fresh_render
    if not R.available():
        pytest.skip("renderer not importable here")
    monkeypatch.setattr(R, "PER_RENDER_BUDGET_S", 0.0)
    source, _ = load(INPUT / "chameleon_sample_level1_warmup.json")
    R.begin_task()
    assert R.render_design(source, max_size=200) is not None    # first render completes ...
    assert not R.enabled() and "took" in R.status()               # ... and switches rendering off
    assert R.render_design(source, max_size=200) is None


def test_task_render_budget(monkeypatch, fresh_render):
    R = fresh_render
    if not R.available():
        pytest.skip("renderer not importable here")
    monkeypatch.setattr(R, "TASK_RENDER_BUDGET_S", 0.0)
    source, _ = load(INPUT / "chameleon_sample_level1_warmup.json")
    R.begin_task()
    assert R.render_design(source, max_size=200) is None          # budget already spent for this task
    assert R.enabled()                                             # but not switched off for good


def test_emulation_turns_pixels_off(monkeypatch, fresh_render):
    R = fresh_render
    monkeypatch.setattr(R, "_reported_family", lambda: "x86")
    monkeypatch.setattr(R, "_host_family", lambda: "arm")
    assert R.emulated()
    allowed, reason = R.policy()
    assert not allowed and "emulated" in reason
    R._reset_for_tests()
    monkeypatch.setenv("CHAMELEON_RENDER", "1")
    assert R.policy()[0]
