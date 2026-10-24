"""Scorer calibration (eval/calibrate.py), the label store and pair sampling
(eval/labeling.py), and the fitted-weights loader in engine/score.py.

Offline: no rendering, no eval data needed (toy pairs are synthesised)."""

import json
import math
import random

import numpy as np
import pytest

from engine import score as S
from eval import calibrate as C
from eval import labeling as L

COMPONENTS = list(S.HAND_WEIGHTS)


def planted_pairs(rng, n=400, designs=40, noise_temp=0.8):
    """Synthetic labelled pairs whose decisions follow a planted weight vector."""
    planted = {c: 5.0 for c in COMPONENTS}
    planted.update({"faith.order": 30.0, "read.size": 25.0, "layout.fill": 15.0})
    w = np.array([planted[c] for c in COMPONENTS])
    w = w * 100.0 / w.sum()
    X = rng.normal(size=(n, len(COMPONENTS))) * 0.15
    p = 1.0 / (1.0 + np.exp(-noise_temp * (X @ w)))
    y = (p > rng.random(n)).astype(float)
    P = C.Pairs(COMPONENTS, X, np.zeros(n), y, np.ones(n), [f"d{i % designs}" for i in range(n)], ["human"] * n)
    return planted, P


def test_fit_recovers_planted_ordering():
    planted, P = planted_pairs(np.random.default_rng(0))
    fit = C.fit_weights(P, l2=0.0)
    w = fit.weights
    assert math.isclose(sum(w.values()), 100.0, abs_tol=1e-2)      # weights are rounded to 4 decimals
    assert all(v >= 5.0 - 1e-6 for v in w.values())          # the 5 % floor
    assert w["faith.order"] > w["read.size"] > w["layout.fill"]
    others = [v for k, v in w.items() if k not in ("faith.order", "read.size", "layout.fill")]
    assert w["layout.fill"] > max(others)
    assert C.agreement(P, w)["agree"] > C.agreement(P, S.HAND_WEIGHTS)["agree"]
    assert 0.0 < fit.temperature < 50.0


def test_gradient_matches_finite_differences():
    rng = np.random.default_rng(1)
    k = len(COMPONENTS)
    X = rng.normal(size=(30, k)) * 0.2
    pinned = np.where(rng.random(30) < 0.2, -1000.0, 0.0)
    y = (rng.random(30) < 0.5).astype(float)
    y[:4] = 0.5
    P = C.Pairs(COMPONENTS, X, pinned, y, rng.random(30) + 0.5, ["d"] * 30, ["human"] * 30)
    prior = np.array([S.HAND_WEIGHTS[c] for c in COMPONENTS])
    theta = rng.normal(size=k + 1) * 0.5
    loss, grad = C._loss_grad(theta, P, 5.0, 0.5, prior)
    num = np.zeros_like(theta)
    for i in range(len(theta)):
        e = np.zeros_like(theta)
        e[i] = 1e-6
        num[i] = (C._loss_grad(theta + e, P, 5.0, 0.5, prior)[0] - C._loss_grad(theta - e, P, 5.0, 0.5, prior)[0]) / 2e-6
    assert np.allclose(grad, num, atol=1e-5, rtol=1e-4)


def test_pinned_hard_fail_dominates_the_fit():
    """A pair where A has a hard fail is predicted for B whatever the soft terms."""
    rng = np.random.default_rng(2)
    _, P = planted_pairs(rng, n=120)
    fit = C.fit_weights(P)
    one = C.Pairs(COMPONENTS, np.full((1, len(COMPONENTS)), 0.9), np.array([-1000.0]), np.array([1.0]),
                  np.ones(1), ["x"], ["human"])
    assert C.margins(one, fit.weights)[0] < 0


def test_leave_one_design_out_runs_and_is_near_in_sample():
    _, P = planted_pairs(np.random.default_rng(3), n=300, designs=12)
    fit = C.fit_weights(P, l2=0.0)
    lodo = C.leave_one_design_out(P, l2=0.0)
    assert lodo["folds"] == 12 and lodo["n"] == 300
    assert abs(lodo["agree"] - C.agreement(P, fit.weights)["agree"]) < 0.1


def test_build_pairs_from_records_and_weak_weight():
    bd_a = {c: 0.5 for c in COMPONENTS}
    bd_b = dict(bd_a, **{"faith.order": 0.2})
    side = lambda bd, hard=(), pen=0.0: {"breakdown": bd, "hard": list(hard), "penalty": pen}  # noqa: E731
    recs = [
        {"decision": "a", "design_id": "d1", "a": side(bd_a), "b": side(bd_b)},
        {"decision": "b", "design_id": "d1", "a": side(bd_b), "b": side(bd_a), "kind": "weak"},
        {"decision": "tie", "design_id": "d2", "a": side(bd_a), "b": side(bd_a)},
        {"decision": "both_bad", "design_id": "d2", "a": side(bd_a), "b": side(bd_b)},
        {"decision": "a", "design_id": "d3", "a": side(bd_a, hard=["x off canvas"], pen=2.0), "b": side(bd_a)},
    ]
    P = C.build_pairs(recs, COMPONENTS, weak_weight=0.25)
    assert len(P) == 4 and P.skipped == {"both_bad": 1}
    assert list(P.w) == [1.0, 0.25, 1.0, 1.0]
    assert list(P.y) == [1.0, 0.0, 0.5, 1.0]
    i = COMPONENTS.index("faith.order")
    assert P.X[0, i] == pytest.approx(0.3) and P.X[1, i] == pytest.approx(-0.3)
    assert P.pinned[3] == pytest.approx(-1002.0)                   # the both_bad record was skipped
    comp = C.component_agreement(P)
    assert comp["faith.order"]["n"] == 2 and comp["faith.order"]["agree"] == 1.0
    assert comp["read.size"]["n"] == 0 and comp["read.size"]["agree"] is None


def test_calibrate_end_to_end_writes_weights(tmp_path):
    rng = random.Random(0)
    labels = tmp_path / "labels.jsonl"
    weak = tmp_path / "weak.jsonl"
    for i in range(40):
        bd_a = {c: rng.random() for c in COMPONENTS}
        bd_b = {c: rng.random() for c in COMPONENTS}
        better = "a" if bd_a["faith.order"] > bd_b["faith.order"] else "b"
        rec = {"case_key": f"d{i % 8}|p", "design_id": f"d{i % 8}", "mode": "candidates",
               "a": {"id": "x", "name": "x", "total": 1.0, "hard": [], "penalty": 0.0, "breakdown": bd_a, "design": {}},
               "b": {"id": "y", "name": "y", "total": 2.0, "hard": [], "penalty": 0.0, "breakdown": bd_b, "design": {}}}
        L.append_label(rec, better, labels if i % 2 else weak, kind="human" if i % 2 else "weak")
    out = tmp_path / "score_weights.json"
    res = C.calibrate(labels, weak, out=out, max_folds=4)
    assert res["written"] == str(out)
    data = json.loads(out.read_text())
    assert set(data["weights"]) == set(COMPONENTS)
    assert data["meta"]["n_human"] == 20 and data["meta"]["n_weak"] == 20
    assert data["weights"]["faith.order"] == max(data["weights"].values())
    assert "| faith.order |" in res["report"]
    # and score.py accepts the file
    assert S.load_weights(out) == {k: float(v) for k, v in data["weights"].items()}


# ---------------------------------------------------------------------------
# score.py loader


def test_score_falls_back_to_hand_weights_without_file(tmp_path, monkeypatch):
    assert S.load_weights(tmp_path / "missing.json") is None
    monkeypatch.setenv("CHAMELEON_SCORE_WEIGHTS", "0")
    assert S.load_weights() is None
    monkeypatch.setenv("CHAMELEON_SCORE_WEIGHTS", str(tmp_path / "missing.json"))
    assert S.load_weights() is None
    # the module's live weights are the hand weights unless a valid file was present at import
    # (the default file, or one named by CHAMELEON_SCORE_WEIGHTS in the environment)
    import os

    if not S.WEIGHTS_FILE.exists() and not os.environ.get("CHAMELEON_SCORE_WEIGHTS"):
        assert S.WEIGHTS == S.HAND_WEIGHTS
    assert set(S.WEIGHTS) == set(S.HAND_WEIGHTS)


def test_score_rejects_incomplete_or_invalid_weights(tmp_path):
    good = {k: v * 2 for k, v in S.HAND_WEIGHTS.items()}
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"weights": good}))
    assert S.load_weights(p) == good
    p.write_text(json.dumps(good))                       # bare dict form
    assert S.load_weights(p) == good
    p.write_text(json.dumps({"weights": {k: v for k, v in good.items() if k != "faith.scale"}}))
    assert S.load_weights(p) is None
    p.write_text(json.dumps({"weights": dict(good, **{"read.size": -1.0})}))
    assert S.load_weights(p) is None
    p.write_text(json.dumps({"weights": dict(good, **{"read.size": "nan"})}))
    assert S.load_weights(p) is None
    p.write_text("not json")
    assert S.load_weights(p) is None


# ---------------------------------------------------------------------------
# labelling: pair choice and the store


def _side(name, total, hard=(), design=None):
    return {"id": name, "name": name, "strategy": "x", "total": total, "hard": list(hard),
            "penalty": 0.0, "breakdown": {}, "design": design or {"n": name}}


def test_choose_pair_never_mixes_clean_with_hard_fail():
    rng = random.Random(0)
    sides = [_side("c1", 80), _side("c2", 79), _side("h1", 70, ["x off canvas"]), _side("h2", 69, ["y collides"]),
             dict(_side("fb", 60), fallback=True)]
    for _ in range(200):
        a, b = L.choose_pair(sides, rng)
        assert bool(a["hard"]) == bool(b["hard"])
        assert "fb" not in (a["id"], b["id"])
    assert L.choose_pair([_side("c1", 80), _side("h1", 70, ["bad"])], rng) is None
    assert L.choose_pair([_side("c1", 80), _side("c2", 80, design={"n": "c1"})], rng) is None


def test_choose_pair_prefers_close_scores():
    rng = random.Random(1)
    sides = [_side("a", 90), _side("b", 89), _side("c", 40)]
    close = sum(1 for _ in range(300) if {x["id"] for x in L.choose_pair(sides, rng)} == {"a", "b"})
    assert close > 250


def test_label_store_append_undo_stats(tmp_path):
    path = tmp_path / "labels.jsonl"
    assert L.read_labels(path) == [] and L.undo_label(path) is None
    rec = {"case_key": "d|p", "design_id": "d", "tgt_family": "tall", "src_family": "square", "preset": "p",
           "mode": "candidates", "a": _side("a", 80), "b": _side("b", 85)}
    L.append_label(rec, "a", path, seconds=3.2)
    L.append_label(rec, "b", path)
    with pytest.raises(ValueError):
        L.append_label(rec, "maybe", path)
    st = L.label_stats(path)
    assert st["n"] == 2 and st["by_decision"] == {"a": 1, "b": 1} and st["by_tgt_family"] == {"tall": 2}
    assert st["scorer_n"] == 2 and st["scorer_agree"] == 1          # the scorer preferred b
    assert st["last"]["decision"] == "b" and st["last"]["scorer"] == "b"
    undone = L.undo_label(path)
    assert undone["decision"] == "b"
    assert L.label_stats(path)["n"] == 1 and L.read_labels(path)[0]["seconds"] == 3.2


def test_sample_case_balances_families():
    rng = random.Random(0)
    index = [{"id": "s", "family": "square", "file": "x"}, {"id": "t", "family": "tall", "file": "y"}]
    presets = [("sq", 1000, 1000), ("tall", 1000, 1800), ("wide", 1800, 1000)]
    stats = {"by_tgt_family": {"square": 50, "wide": 50}, "by_src_family": {"square": 50}}
    picks = [L.sample_case(rng, index, presets, stats) for _ in range(300)]
    tall_targets = sum(1 for _, p in picks if p[0] == "tall")
    tall_sources = sum(1 for r, _ in picks if r["id"] == "t")
    assert tall_targets > 200 and tall_sources > 200


def test_perturb_moves_content_and_keeps_ids():
    from engine.analyze import analyze

    source = {"canvas": {"width": 1000, "height": 1000}, "elements": [
        {"id": "bg", "type": "shape", "shape_type": "rectangle", "x": 0, "y": 0, "width": 1000, "height": 1000,
         "fill": "#ffffff", "z_index": 0, "opacity": 1, "rotation": 0},
        {"id": "h", "type": "text", "content": "Hello", "x": 100, "y": 100, "width": 500, "height": 100,
         "font_size": 60, "font_family": "Solstice Sans", "color": "#000000", "z_index": 1, "opacity": 1, "rotation": 0},
        {"id": "s", "type": "text", "content": "Sub", "x": 100, "y": 300, "width": 500, "height": 60,
         "font_size": 30, "font_family": "Solstice Sans", "color": "#000000", "z_index": 2, "opacity": 1, "rotation": 0},
    ]}
    bad = L.perturb(source, analyze(source), random.Random(0), frac=1.0)
    assert [e["id"] for e in bad["elements"]] == ["bg", "h", "s"]
    moved = [e["id"] for e, s in zip(bad["elements"], source["elements"]) if (e["x"], e["y"]) != (s["x"], s["y"])]
    assert moved and "bg" not in moved
    for e in bad["elements"]:
        assert 0 <= e["x"] and e["x"] + e["width"] <= 1000 + 1e-6
        assert 0 <= e["y"] and e["y"] + e["height"] <= 1000 + 1e-6
