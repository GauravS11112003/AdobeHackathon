"""S1: VLM perception (engine/perceive.py) and the three-voter role merge
(engine/role_merge.vote_roles / apply_votes), without weights: the VLM is a
stub backend. Also the contract that matters most: with CHAMELEON_VLM and
CHAMELEON_ROLE_MODEL unset the engine's output is byte-identical to the
engine before S1 (golden files from the v5 tree)."""

from __future__ import annotations

import copy
import json
import platform
import subprocess
import sys
from pathlib import Path

import pytest

from engine import analyze as A
from engine import candidates as C
from engine import perceive as P
from engine import resize as RZ
from engine import role_merge as RMG
from engine import vlm
from engine.floorplan import BANNER, SQUARE, TALL, WIDE, PlanOptions
from engine.geometry import Box

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden_v5"
SAMPLES = sorted(INPUT.glob("*.json"))


def load(name: str) -> dict:
    return json.loads((INPUT / f"{name}.json").read_text())["source"]


@pytest.fixture
def fresh(monkeypatch, tmp_path):
    """VLM on with a stub backend (no weights: an empty model dir), no classifier, clean caches."""
    vlm._reset_for_tests()
    P._reset_for_tests()
    for k in ("CHAMELEON_VLM_MODEL", "CHAMELEON_VLM_MMPROJ", "CHAMELEON_VLM_CACHE_DIR",
              "CHAMELEON_VLM_BUDGET_S", "CHAMELEON_ROLE_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CHAMELEON_VLM", "1")
    monkeypatch.setenv("CHAMELEON_VLM_DIR", str(tmp_path / "no-models"))
    from engine import render as R
    R._reset_for_tests()          # an earlier test may have switched the renderer off for the process
    if not R.enabled():
        pytest.skip("renderer unavailable: " + R.status())
    yield
    vlm._reset_for_tests()
    P._reset_for_tests()


class Stub:
    """Answers with the roles given per box number (defaults: the analyzer's)."""

    def __init__(self, roles=None, archetype="product_ad", importance=None, text=None, raise_exc=None):
        self.roles, self.archetype, self.importance = roles or {}, archetype, importance
        self.text, self.raise_exc = text, raise_exc
        self.calls = 0
        self.last = {}
        self.model_path = Path("stub.gguf")
        self.prompts: list[str] = []

    def complete(self, png, prompt, schema, max_tokens, deadline):
        self.calls += 1
        self.prompts.append(prompt)
        if self.raise_exc:
            raise self.raise_exc
        if self.text is not None:
            return self.text
        numbers = schema["properties"]["roles"]["required"]
        roles = {n: self.roles.get(n, self.roles.get(int(n), "body")) for n in numbers}
        imp = self.importance if self.importance is not None else numbers[:3]
        return json.dumps({"roles": roles, "archetype": self.archetype, "importance": imp})


def stub_with_rules(src, analysis, **changes):
    """A stub that repeats the analyzer's roles (background skipped) except `changes` (by unit key)."""
    mk = P.marks(analysis)
    roles = {}
    for m in mk:
        roles[str(m["n"])] = changes.get(m["key"], m["role"])
    return Stub(roles=roles), mk


# ---------------------------------------------------------------------------
# the switch and the byte-identity contract


def test_default_is_off(monkeypatch):
    monkeypatch.delenv("CHAMELEON_VLM", raising=False)
    assert not P.enabled()
    monkeypatch.setenv("CHAMELEON_VLM", "0")
    assert not P.enabled()
    monkeypatch.setenv("CHAMELEON_VLM", "1")
    assert P.enabled()


def test_off_returns_empty_without_touching_the_adapter(monkeypatch):
    monkeypatch.delenv("CHAMELEON_VLM", raising=False)
    src = load("chameleon_sample_level2_core")
    stub = Stub()
    vlm.set_backend(stub)
    try:
        p = P.perceive(src, A.analyze(src))
    finally:
        vlm.set_backend(None)
    assert not p and p.status == "off" and stub.calls == 0


def test_understand_is_a_noop_by_default(monkeypatch):
    monkeypatch.delenv("CHAMELEON_VLM", raising=False)
    monkeypatch.delenv("CHAMELEON_ROLE_MODEL", raising=False)
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    before = copy.deepcopy(a.roles), [(u.key, u.role, u.importance) for u in a.units]
    RZ.understand(src, a)
    assert a.perception is None
    assert (a.roles, [(u.key, u.role, u.importance) for u in a.units]) == before


@pytest.mark.skipif(platform.system() != "Darwin", reason="goldens were measured with macOS font hinting")
@pytest.mark.parametrize("golden", sorted(GOLDEN.glob("*.json")), ids=lambda p: p.stem)
def test_output_is_byte_identical_to_v5_with_the_flags_off(golden, monkeypatch):
    monkeypatch.delenv("CHAMELEON_VLM", raising=False)
    monkeypatch.delenv("CHAMELEON_ROLE_MODEL", raising=False)
    stem, size = golden.stem.rsplit("_", 1)
    w, h = (int(v) for v in size.split("x"))
    out = RZ.resize(load(stem), {"width": w, "height": h})
    assert json.dumps(out, sort_keys=True, separators=(",", ":")) == golden.read_text()


def test_engine_does_not_import_the_adapter_by_default():
    """engine.perceive is imported (role_merge needs its coarse classes) but
    it imports engine.vlm / llama_cpp only inside perceive() when switched on."""
    code = "import sys, engine.resize, engine.main; print('engine.vlm' in sys.modules, 'llama_cpp' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT),
                         env={k: v for k, v in __import__("os").environ.items() if k != "CHAMELEON_VLM"})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False False"


# ---------------------------------------------------------------------------
# set of marks, prompt, interpretation


def test_marks_cover_every_non_background_unit_in_reading_order():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    mk = P.marks(a)
    keys = [m["key"] for m in mk]
    assert set(keys) == {u.key for u in a.units if u.role != A.BACKGROUND}
    assert [m["n"] for m in mk] == list(range(1, len(mk) + 1))
    ys = [round(m["box"][1] / 40.0) for m in mk]
    assert ys == sorted(ys)


def test_prompt_hints_and_schema_are_grammar_friendly():
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    mk = P.marks(a)
    prompt, schema = P.prompt_and_schema(mk, P.hints(src, mk))
    assert "Refresh Your Summer" in prompt or "Summer" in prompt         # the headline text is hinted
    assert "archetype" in prompt and "importance" in prompt
    assert set(schema["required"]) == {"roles", "archetype", "importance"}
    assert schema["properties"]["roles"]["required"] == [str(m["n"]) for m in mk]
    assert schema["properties"]["archetype"]["enum"] == P.ARCHETYPES
    assert schema["properties"]["importance"]["maxItems"] <= P.MAX_IMPORTANCE
    assert vlm.validate(json.loads(Stub().complete(b"", prompt, schema, 10, 0)), schema) == []


def test_interpret_maps_fine_roles_to_coarse_with_confidence():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    mk = P.marks(a)
    by_key = {m["key"]: str(m["n"]) for m in mk}
    answer = {"roles": {str(m["n"]): m["role"] for m in mk}, "archetype": "event_poster",
              "importance": [by_key["headline"], by_key["product"], by_key["headline"]]}
    answer["roles"][by_key["product"]] = "image"          # the model's hero/image split, not ours
    p = P.interpret(answer, mk, src, a)
    assert p.archetype == "event_poster"
    assert p.importance == ["headline", "product"]        # duplicates dropped, keys not numbers
    assert p.roles["headline"] == (P.HEADLINE, P.BASE_CONF[P.HEADLINE])
    assert p.roles["product"][0] == P.PICTURE and p.fine["product"] == "image"
    assert p.roles["legal_text"][0] == P.SECONDARY
    assert p.roles["logo"][0] == P.LOGO


def test_interpret_drops_type_conflicts_and_dilutes_shared_unique_roles():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    mk = P.marks(a)
    by_key = {m["key"]: str(m["n"]) for m in mk}
    roles = {str(m["n"]): m["role"] for m in mk}
    roles[by_key["product"]] = "headline"      # an image cannot be a headline
    roles[by_key["subhead"]] = "headline"      # two text headlines
    answer = {"roles": roles, "archetype": "other", "importance": [by_key["subhead"]]}
    p = P.interpret(answer, mk, src, a)
    assert "product" not in p.roles
    assert p.roles["subhead"] == (P.HEADLINE, P.BASE_CONF[P.HEADLINE])          # ranked first: keeps the base
    assert p.roles["headline"] == (P.HEADLINE, P.BASE_CONF[P.HEADLINE] / 2)     # the other is diluted
    assert p.roles["headline"][1] < RMG.VLM_TIEBREAK <= p.roles["subhead"][1]


# ---------------------------------------------------------------------------
# the call: cache, budget, failures


def test_perceive_with_stub_answers_and_caches(fresh, tmp_path, monkeypatch):
    monkeypatch.setenv("CHAMELEON_VLM_CACHE_DIR", str(tmp_path))
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    stub, mk = stub_with_rules(src, a, subhead="body")
    vlm.set_backend(stub)
    p = P.perceive(src, a)
    assert p.status == "ok" and stub.calls == 1
    assert p.roles["headline"][0] == P.HEADLINE and p.roles["subhead"][0] == P.SECONDARY
    assert p.fine["subhead"] == "body"
    assert "Lemon" in stub.prompts[0] or "text" in stub.prompts[0]
    # same source again: no call (memory), and again from disk in a fresh process state
    p2 = P.perceive(src, a)
    assert p2.status == "cached" and stub.calls == 1 and p2.roles == p.roles
    P._reset_for_tests()
    p3 = P.perceive(src, a)
    assert p3.status == "cached" and stub.calls == 1 and p3.archetype == p.archetype
    assert list(tmp_path.glob("perceive_*.json"))
    # a different source is a different key
    other = copy.deepcopy(src)
    other["elements"][0]["x"] += 1
    P.perceive(other, A.analyze(other))
    assert stub.calls == 2


def test_perceive_skips_when_the_budget_is_gone(fresh):
    src = load("chameleon_sample_level1_warmup")
    a = A.analyze(src)
    stub, _ = stub_with_rules(src, a)
    vlm.set_backend(stub)
    p = P.perceive(src, a, budget=0.0)
    assert p.status == "budget" and stub.calls == 0 and not p


def test_perceive_never_raises(fresh):
    src = load("chameleon_sample_level1_warmup")
    a = A.analyze(src)
    vlm.set_backend(Stub(raise_exc=RuntimeError("boom")))
    assert P.perceive(src, a).status == "no_answer"
    vlm._reset_for_tests()
    vlm.set_backend(Stub(text="not json at all"))
    assert P.perceive(src, a, use_cache=False).status == "no_answer"
    vlm._reset_for_tests()
    assert P.perceive(src, a).status == "no_model"          # no backend, no weights configured
    assert P.perceive({"canvas": {"width": 10, "height": 10}, "elements": []},
                      A.analyze({"canvas": {"width": 10, "height": 10}, "elements": []})).status in ("no_model", "no_answer", "error")


# ---------------------------------------------------------------------------
# the vote


def unit_role(a, key):
    return a.unit(key).role


def test_vote_without_voters_is_empty():
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    roles, decisions = RMG.vote_roles(src, a, probs={}, perception=None, model_on=False)
    assert roles == a.roles and decisions == {}
    assert RMG.apply_votes(a, src, None, model_on=False) == {} and a.perception is None


def test_vlm_alone_needs_tiebreak_confidence():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    # confident: the free text the rules call subhead is a CTA-less body -> VLM says body: a fine split, ignored alone
    p = P.Perception(roles={"subhead": (P.SECONDARY, 0.85)}, fine={"subhead": "body"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs={}, perception=p, model_on=False)
    assert roles["subhead"] == "subhead" and dec["subhead"]["by"] == "rules+vlm"
    # confident coarse disagreement: the legal line is a badge
    p = P.Perception(roles={"legal_text": (P.BADGE, 0.7)}, fine={"legal_text": "badge"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs={}, perception=p, model_on=False)
    assert roles["legal_text"] == "badge" and dec["legal_text"]["by"] == "vlm"
    # the same below the tie-break threshold: rules
    p = P.Perception(roles={"legal_text": (P.BADGE, 0.5)}, fine={"legal_text": "badge"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs={}, perception=p, model_on=False)
    assert roles["legal_text"] == "fine_print" and dec["legal_text"]["by"] == "rules"


def test_hard_structure_stays_with_the_rules():
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    p = P.Perception(roles={"deco_circle_1": (P.BADGE, 0.9), "bg": (P.BADGE, 0.9)},
                     fine={"deco_circle_1": "badge", "bg": "badge"}, status="ok")
    probs = {"deco_circle_1": {"badge": 0.99}, "bg": {"badge": 0.99}}
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert roles["deco_circle_1"] == "decorative" and roles["bg"] == "background"
    assert dec["deco_circle_1"]["by"] == "rules"


def test_majority_of_models_beats_the_rules_and_groups_move_together():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    ribbon = a.unit("group:ribbon")
    assert ribbon.role == "badge"
    texts = [i for i in ribbon.ids if a.source_elements[i]["type"] == "text"]
    probs = {i: {"cta": 0.7, "badge": 0.3} for i in texts}
    p = P.Perception(roles={"group:ribbon": (P.CTA, 0.8)}, fine={"group:ribbon": "cta"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    # both models say CTA: the ribbon becomes the CTA ... but one CTA per design: the
    # consistency pass keeps the stronger one (the real button, rules + nothing against it)
    assert dec["group:ribbon"]["by"] in ("model+vlm", "consistency")
    ctas = {a.element_unit[i] for i, r in roles.items() if r == "cta"}
    assert len(ctas) == 1
    assert all(roles[i] == roles[ribbon.ids[0]] for i in ribbon.ids)


def test_three_way_split_goes_to_a_confident_vlm_else_rules():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    probs = {"legal_text": {"body": 0.9, "fine_print": 0.05}}        # model: secondary (same class as rules!)
    # make the model vote a different coarse class: badge
    probs = {"legal_text": {"badge": 0.6, "fine_print": 0.2, "body": 0.2}}
    p = P.Perception(roles={"legal_text": (P.CTA, 0.8)}, fine={"legal_text": "cta"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert roles["legal_text"] == "cta" or dec["legal_text"]["by"] in ("vlm", "consistency")
    p = P.Perception(roles={"legal_text": (P.CTA, 0.5)}, fine={"legal_text": "cta"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert roles["legal_text"] == "fine_print" and dec["legal_text"]["by"] == "rules"


def test_fine_split_changes_only_when_both_models_agree():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    assert a.roles["subhead"] == "subhead"
    probs = {"subhead": {"body": 0.9, "subhead": 0.05}}
    # model alone: fine split stays
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=None, model_on=True)
    assert roles["subhead"] == "subhead"
    # VLM agrees on body: both against the rules -> body
    p = P.Perception(roles={"subhead": (P.SECONDARY, 0.6)}, fine={"subhead": "body"}, status="ok")
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert roles["subhead"] == "body" and dec["subhead"]["by"] == "model+vlm"
    # VLM says a different fine role: rules keep their split
    p = P.Perception(roles={"subhead": (P.SECONDARY, 0.6)}, fine={"subhead": "fine_print"}, status="ok")
    roles, _ = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert roles["subhead"] == "subhead"


def test_one_headline_one_logo_after_the_vote():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    p = P.Perception(roles={"subhead": (P.HEADLINE, 0.85), "headline": (P.HEADLINE, 0.85),
                            "holiday_watermark": (P.LOGO, 0.85), "logo": (P.LOGO, 0.85)},
                     fine={"subhead": "headline", "headline": "headline", "holiday_watermark": "logo", "logo": "logo"},
                     importance=["headline", "logo"], status="ok")
    probs = {"subhead": {"headline": 0.9}, "headline": {"headline": 0.9}, "holiday_watermark": {"logo": 0.9},
             "logo": {"logo": 0.9}}
    roles, dec = RMG.vote_roles(src, a, probs=probs, perception=p, model_on=True)
    assert [k for k, r in roles.items() if r == "headline"] == ["headline"]
    assert roles["subhead"] == "subhead" and dec["subhead"]["by"] == "consistency"
    assert [k for k, r in roles.items() if r == "logo"] == ["logo"]
    assert roles["holiday_watermark"] == "image"


def test_apply_votes_rewrites_units_and_records_decisions():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    p = P.Perception(roles={"legal_text": (P.BADGE, 0.7)}, fine={"legal_text": "badge"}, archetype="editorial", status="ok")
    changed = RMG.apply_votes(a, src, p, model_on=False)
    assert changed == {"legal_text": "fine_print"}
    assert a.roles["legal_text"] == "badge" and a.unit("legal_text").role == "badge"
    assert a.unit("legal_text").importance == A.IMPORTANCE["badge"]
    assert a.perception["archetype"] == "editorial" and a.perception["changed"] == 1
    assert a.perception["by"]["vlm"] == 1 and a.perception["decisions"]["headline"]["by"] == "rules"
    assert RZ.roles_summary(a) == {"archetype": "editorial", "vlm": "ok", "by": a.perception["by"], "changed": 1}


def test_apply_votes_records_an_empty_perception_status():
    src = load("chameleon_sample_level1_warmup")
    a = A.analyze(src)
    assert RMG.apply_votes(a, src, P.Perception(status="no_answer"), model_on=False) == {}
    assert a.perception["vlm"] == "no_answer" and a.perception["changed"] == 0


# ---------------------------------------------------------------------------
# archetype -> candidates


@pytest.mark.parametrize("family", [TALL, SQUARE, WIDE, BANNER])
def test_plan_variants_are_the_same_set_whatever_the_archetype(family):
    base = C.plan_variants(family)
    for arch in P.ARCHETYPES:
        assert sorted(map(str, C.plan_variants(family, arch))) == sorted(map(str, base))
    assert C.plan_variants(family, None) == base


def test_editorial_prefers_text_columns_and_grid_keeps_rows():
    wide = C.plan_variants(WIDE, "editorial")
    assert not C.hero_first(WIDE, wide[0])                       # a stack (column) plan comes first
    assert C.archetype_prior(WIDE, PlanOptions(hero_side="left"), "quote") == C.ARCHETYPE_PENALTY
    assert C.archetype_prior(WIDE, PlanOptions(hero_side="stack"), "quote") == 0.0
    assert C.archetype_prior(BANNER, PlanOptions(text_flow="column"), "editorial") == C.ARCHETYPE_PENALTY
    assert C.archetype_prior(SQUARE, PlanOptions(hero_side="right"), "editorial") == C.ARCHETYPE_PENALTY
    assert C.archetype_prior(TALL, PlanOptions(chips="corner"), "grid") == C.ARCHETYPE_PENALTY
    assert C.archetype_prior(TALL, PlanOptions(), "grid") == 0.0
    assert C.archetype_prior(TALL, PlanOptions(chips="corner"), "product_ad") == 0.0
    assert all(C.archetype_prior(TALL, o, None) == 0.0 for o in C.plan_variants(TALL))
    grid = C.plan_variants(TALL, "grid")
    assert all(o.chips == "row" for o in grid[:3])


def test_candidates_carry_the_prior_and_the_judge_applies_it():
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    a.perception = {"archetype": "editorial", "vlm": "ok", "decisions": {}, "by": {}, "changed": 0}
    target = Box(0, 0, 1200, 628)
    cands = C.generate_candidates(a, src, target)
    priors = {c.name: c.prior for c in cands}
    assert any(v == C.ARCHETYPE_PENALTY for v in priors.values()) and any(v == 0.0 for v in priors.values())
    a2 = A.analyze(src)
    assert all(c.prior == 0.0 for c in C.generate_candidates(a2, src, target))
    # the judge subtracts the prior from the total
    from engine.score import Score
    sc = Score(total=50.0)
    RZ._apply_prior(sc, cands[[c.prior for c in cands].index(C.ARCHETYPE_PENALTY)])
    assert sc.total == 50.0 - C.ARCHETYPE_PENALTY and sc.penalty == C.ARCHETYPE_PENALTY


# ---------------------------------------------------------------------------
# end to end with the stub


def test_resize_with_stub_vlm_records_the_voters_and_keeps_the_contract(fresh):
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    stub, _ = stub_with_rules(src, a, legal_text="badge")
    stub.archetype = "editorial"
    vlm.set_backend(stub)
    best, judged = RZ.resize_with_candidates(src, {"width": 1200, "height": 628})
    assert stub.calls == 1
    assert [el["id"] for el in best["elements"]] == [el["id"] for el in src["elements"]]
    summ = judged[0].summary()
    assert summ["roles"]["archetype"] == "editorial" and summ["roles"]["vlm"] == "ok"
    assert summ["roles"]["by"].get("vlm") == 1 and summ["roles"]["changed"] == 1
    assert RZ.LAST_ANALYSIS is not None and RZ.LAST_ANALYSIS.roles["legal_text"] == "badge"
    assert RZ.LAST_ANALYSIS.perception["decisions"]["legal_text"]["by"] == "vlm"
    assert judged[0].score.hard == []
    # a second target of the same source hits the perception cache
    RZ.resize(src, {"width": 160, "height": 600})
    assert stub.calls == 1
