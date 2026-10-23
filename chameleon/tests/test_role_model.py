"""Learned role classifier: features, numpy inference, merge helper.

Runs offline: `tests/fixtures/roles_tiny.npz` is a 3-iteration export of the
same training run with scikit-learn's probabilities for the three samples
recorded in `roles_tiny_expected.json`, so the numpy traversal is checked
against the library that trained the trees without importing it.
"""

from __future__ import annotations

import copy
import json
import math
import os
import time
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from engine import analyze as A  # noqa: E402
from engine import role_features as RF  # noqa: E402
from engine import role_merge as RMG  # noqa: E402
from engine import role_model as RM  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
FIX = ROOT / "tests" / "fixtures"
SAMPLES = ("chameleon_sample_level1_warmup", "chameleon_sample_level2_core", "chameleon_sample_level3_advanced")


def load(name: str) -> dict:
    return json.loads((INPUT / f"{name}.json").read_text())["source"]


def strip_ids(source: dict) -> tuple[dict, dict[str, str]]:
    """Opaque ids like the hidden tasks; returns (design, opaque -> original)."""
    src = copy.deepcopy(source)
    back = {}
    gids = {}
    for i, el in enumerate(src["elements"]):
        new = f"e{i:02d}"
        back[new] = el["id"]
        el["id"] = new
        if el.get("group_id"):
            el["group_id"] = gids.setdefault(el["group_id"], f"g{len(gids)}")
    return src, back


@pytest.fixture(scope="module")
def tiny() -> RM.RoleModel:
    return RM.RoleModel(FIX / "roles_tiny.npz")


@pytest.fixture(scope="module")
def expected() -> dict:
    return json.loads((FIX / "roles_tiny_expected.json").read_text())


# -- features ---------------------------------------------------------------


def test_feature_names_unique_and_sized():
    assert len(RF.FEATURE_NAMES) == RF.N_FEATURES
    assert len(set(RF.FEATURE_NAMES)) == RF.N_FEATURES


@pytest.mark.parametrize("name", SAMPLES)
def test_features_are_finite_and_ordered(name):
    src = load(name)
    ids, rows = RF.features(src)
    assert ids == [el["id"] for el in src["elements"]]
    assert all(len(r) == RF.N_FEATURES for r in rows)
    assert all(math.isfinite(v) for r in rows for v in r)


def test_features_read_the_level2_signals():
    f = RF.feature_dict(load("chameleon_sample_level2_core"))
    assert f["bg"]["area_share"] == pytest.approx(1.0)
    assert f["bg"]["is_image"] == 1.0 and f["bg"]["fit_cover"] == 1.0
    assert f["headline"]["font_rank"] == 0 and f["headline"]["is_biggest_text"] == 1.0
    assert f["headline"]["bold"] == 1.0 and f["headline"]["has_runs"] == 1.0
    assert f["cta_label"]["verb_start"] == 1.0 and f["cta_label"]["grouped"] == 1.0
    assert f["cta_label"]["behind_shape"] == 1.0 and f["cta_bg"]["backs_text"] == 1.0
    assert f["badge_label"]["upper_ratio"] == 1.0
    assert f["deco_circle_1"]["inside_frac"] < 1.0 and f["deco_circle_1"]["opacity"] == pytest.approx(0.15)
    assert f["product"]["largest_image"] == 0.0 and f["bg"]["largest_image"] == 1.0
    assert f["product"]["image_area_rank"] == 1


def test_features_do_not_depend_on_ids():
    src = load("chameleon_sample_level3_advanced")
    stripped, back = strip_ids(src)
    a = RF.feature_dict(src)
    b = RF.feature_dict(stripped)
    for new, old in back.items():
        assert a[old] == b[new]


def test_features_handle_degenerate_input():
    src = {"canvas": {"width": 100, "height": 50}, "elements": [
        {"id": "t", "type": "text", "x": 0, "y": 0, "width": 0, "height": 0, "content": "", "font_size": 0},
        {"id": "s", "type": "shape", "x": -10, "y": -10, "width": 5, "height": 5, "shape_type": "line"},
    ]}
    ids, rows = RF.features(src)
    assert ids == ["t", "s"]
    assert all(math.isfinite(v) for r in rows for v in r)
    assert RF.features({"canvas": {"width": 10, "height": 10}, "elements": []}) == ([], [])


# -- numpy inference ----------------------------------------------------------


def test_tiny_model_matches_sklearn(tiny, expected):
    assert tiny.roles == expected["roles"]
    for name in SAMPLES:
        src = load(name)
        probs = tiny.predict_design(src)
        for eid, want in expected["proba"][name].items():
            got = [probs[eid][r] for r in tiny.roles]
            assert np.allclose(got, want, atol=1e-5), (name, eid)


def test_predict_is_deterministic_and_typed(tiny):
    src = load("chameleon_sample_level3_advanced")
    a = RM.predict(src, path=tiny.path)
    b = RM.predict(src, path=tiny.path)
    assert a == b
    assert set(a) == {el["id"] for el in src["elements"]}
    for el in src["elements"]:
        role, conf = a[el["id"]]
        assert role in RM.allowed_roles(el["type"])
        assert 0.0 < conf <= 1.0


def test_predict_is_fast(tiny):
    src = load("chameleon_sample_level3_advanced")
    model = RM.load(RM.MODEL_PATH) or tiny
    model.predict_design(src)
    t0 = time.perf_counter()
    for _ in range(10):
        model.predict_design(src)
    assert (time.perf_counter() - t0) / 10 < 0.020


def test_missing_model_is_harmless(tmp_path):
    assert RM.predict(load("chameleon_sample_level1_warmup"), path=tmp_path / "nope.npz") == {}
    assert RM.load(tmp_path / "nope.npz") is None


def test_feature_mismatch_is_refused(tmp_path, tiny):
    with np.load(tiny.path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    arrays["feature_names"] = np.asarray(list(arrays["feature_names"])[:-1] + ["bogus"])
    np.savez(tmp_path / "bad.npz", **arrays)
    with pytest.raises(ValueError):
        RM.RoleModel(tmp_path / "bad.npz")
    assert RM.load(tmp_path / "bad.npz") is None


def test_text_hierarchy_ranks_every_text(tiny):
    src = load("chameleon_sample_level3_advanced")
    probs = tiny.predict_design(src)
    ranks = RM.text_hierarchy(src, probs)
    texts = [el["id"] for el in src["elements"] if el["type"] == "text"]
    assert sorted(ranks) == sorted(texts)
    assert sorted(ranks.values()) == list(range(len(texts)))


# -- the shipped model ----------------------------------------------------------


@pytest.mark.skipif(not RM.MODEL_PATH.exists(), reason="no shipped model")
def test_shipped_model_is_small_and_loads():
    assert RM.MODEL_PATH.stat().st_size < 5 * 1024 * 1024
    model = RM.load()
    assert model is not None and model.feature_names == RF.FEATURE_NAMES


@pytest.mark.skipif(not RM.MODEL_PATH.exists(), reason="no shipped model")
@pytest.mark.parametrize("name", SAMPLES)
def test_shipped_model_reads_the_samples_without_ids(name):
    """Ids stripped: the model must still find the headline, the CTA, the logo
    and the product from geometry and text alone."""
    src, back = strip_ids(load(name))
    pred = {back[k]: v for k, v in RM.predict(src).items()}
    probs = {back[k]: v for k, v in RM.predict_proba(src).items()}
    texts = [el["id"] for el in load(name)["elements"] if el["type"] == "text"]
    images = [el["id"] for el in load(name)["elements"] if el["type"] == "image"]
    assert max(texts, key=lambda i: probs[i]["headline"]) == "headline"
    cta = "cta" if "cta" in texts else "cta_label"
    assert max(texts, key=lambda i: probs[i]["cta"]) == cta
    assert max(images, key=lambda i: probs[i]["logo"]) == "logo"
    if "product" in images:
        assert max(images, key=lambda i: probs[i]["hero"]) == "product"
    assert pred["bg"][0] == "background"


# -- merge -------------------------------------------------------------------


def _synthetic_probs(src: dict, **overrides: dict[str, float]) -> dict[str, dict[str, float]]:
    roles = ["headline", "subhead", "body", "cta", "badge", "fine_print",
             "logo", "hero", "image", "background", "decorative", "shape"]
    out = {}
    for el in src["elements"]:
        p = {r: 1.0 / len(roles) for r in roles}
        p.update(overrides.get(el["id"], {}))
        s = sum(p.values())
        out[el["id"]] = {r: v / s for r, v in p.items()}
    return out


def test_flag_off_returns_rule_roles(monkeypatch):
    monkeypatch.setenv("CHAMELEON_ROLE_MODEL", "0")
    src = load("chameleon_sample_level2_core")
    rules = A.analyze(src).roles
    assert RMG.merged_roles(src, rules) == rules
    assert not RMG.enabled()
    monkeypatch.setenv("CHAMELEON_ROLE_MODEL", "1")
    assert RMG.enabled()


def test_merge_overrides_only_confident_disagreements():
    src = load("chameleon_sample_level3_advanced")
    rules = A.analyze(src).roles
    # the model is sure legal_text is body copy and only mildly thinks subhead is fine print
    probs = _synthetic_probs(src, legal_text={"body": 20.0}, subhead={"fine_print": 1.2, "subhead": 1.0})
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    assert merged["legal_text"] == "body"
    assert merged["subhead"] == rules["subhead"]
    # untouched elsewhere
    for eid in ("headline", "logo", "product", "bg"):
        assert merged[eid] == rules[eid]


def test_merge_never_touches_frozen_roles():
    src = load("chameleon_sample_level2_core")
    rules = A.analyze(src).roles
    probs = _synthetic_probs(src, bg={"hero": 50.0}, deco_circle_1={"shape": 50.0})
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    assert merged["bg"] == rules["bg"] == A.BACKGROUND
    assert merged["deco_circle_1"] == rules["deco_circle_1"] == A.DECORATIVE


def test_merge_keeps_groups_together_and_one_cta():
    src = load("chameleon_sample_level3_advanced")
    rules = A.analyze(src).roles
    # the model thinks the SUNSET SALE ribbon is the call to action
    probs = _synthetic_probs(src, ribbon_label={"cta": 30.0}, cta_label={"cta": 25.0})
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    assert merged["ribbon_bg"] == merged["ribbon_label"]
    assert merged["cta_bg"] == merged["cta_label"]
    ctas = {merged[i] for i in ("ribbon_label", "cta_label")}
    assert "cta" in ctas and len([i for i in ("ribbon_label", "cta_label") if merged[i] == "cta"]) == 1


def test_merge_keeps_exactly_one_headline():
    src = load("chameleon_sample_level3_advanced")
    rules = A.analyze(src).roles
    probs = _synthetic_probs(src, subhead={"headline": 30.0}, headline={"headline": 10.0})
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    heads = [i for i, r in merged.items() if r == "headline"]
    assert heads == ["subhead"]
    assert merged["headline"] == "subhead"


def test_merge_respects_type_families():
    src = load("chameleon_sample_level2_core")
    rules = A.analyze(src).roles
    probs = _synthetic_probs(src, headline={"logo": 50.0}, product={"headline": 50.0})
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    assert merged["headline"] == "headline"
    assert merged["product"] == rules["product"]


@pytest.mark.skipif(not RM.MODEL_PATH.exists(), reason="no shipped model")
@pytest.mark.parametrize("name", SAMPLES)
def test_apply_to_analysis_keeps_the_samples_sane(name):
    src = load(name)
    analysis = A.analyze(src)
    before = dict(analysis.roles)
    changed = RMG.apply_to_analysis(analysis, src, force=True)
    assert set(analysis.roles) == set(before)
    heads = [u for u in analysis.units if u.role == "headline"]
    assert len(heads) == 1 and heads[0].ids == ["headline"]
    ctas = [u for u in analysis.units if u.role == "cta"]
    assert len(ctas) == 1 and "cta" in ctas[0].key
    for u in analysis.units:
        for i in u.ids:
            assert analysis.roles[i] == u.role
    assert all(before[i] != analysis.roles[i] for i in changed)
    # the rules' specific calls survive a merely-probable model opinion
    for eid, role in (("logo", "logo"), ("legal_text", "fine_print"), ("badge_label", "badge")):
        if eid in analysis.roles:
            assert analysis.roles[eid] == role


def test_apply_is_noop_when_flag_off(monkeypatch):
    monkeypatch.delenv("CHAMELEON_ROLE_MODEL", raising=False)
    src = load("chameleon_sample_level2_core")
    analysis = A.analyze(src)
    before = {u.key: u.role for u in analysis.units}
    assert RMG.apply_to_analysis(analysis, src) == {}
    assert {u.key: u.role for u in analysis.units} == before
