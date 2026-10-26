"""S6: the text-only LLM reading (engine/llm.py) without weights: a stub
backend stands in for llama.cpp. The contracts that matter: off by default
and never imported by the engine then; the prompt listing is id-free and
order-free; the answer maps onto units / groups / plans tolerantly; the
adapter never raises and caches by source."""

from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

from engine import analyze as A
from engine import llm
from engine import perceive as P

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"


def load(name: str) -> dict:
    return json.loads((INPUT / f"{name}.json").read_text())["source"]


@pytest.fixture
def fresh(monkeypatch, tmp_path):
    llm._reset_for_tests()
    for k in ("CHAMELEON_LLM_MODEL", "CHAMELEON_LLM_CACHE_DIR", "CHAMELEON_LLM_BUDGET_S"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CHAMELEON_LLM", "1")
    monkeypatch.setenv("CHAMELEON_LLM_DIR", str(tmp_path / "no-models"))
    yield
    llm._reset_for_tests()


class Stub:
    """Answers from the schema: every element gets `roles` (by 1-based index,
    default: the first allowed role), plus the given groups / plans."""

    def __init__(self, roles=None, groups=None, plans=None, archetype="product_ad", focal="hero",
                 importance=None, text=None, raise_exc=None, delay=0.0):
        self.roles = {int(k): v for k, v in (roles or {}).items()}
        self.groups, self.plans, self.archetype, self.focal = groups or [], plans, archetype, focal
        self.importance, self.text, self.raise_exc, self.delay = importance, text, raise_exc, delay
        self.calls = 0
        self.last = {}
        self.model_path = Path("stub.gguf")
        self.messages = []

    def complete(self, messages, schema, max_tokens, deadline):
        self.calls += 1
        self.messages.append(messages)
        if self.raise_exc:
            raise self.raise_exc
        if self.delay:
            time.sleep(self.delay)
            self.last = {"stopped_at_deadline": time.perf_counter() > deadline}
        if self.text is not None:
            return self.text
        props = schema["properties"]["roles"]["properties"]
        roles = {k: self.roles.get(int(k), props[k]["enum"][0]) for k in props}
        n = len(props)
        plans = self.plans if self.plans is not None else {
            "tall": {"chips": "row", "keep": True}, "square": {"hero": "left", "chips": "row", "keep": False},
            "wide": {"hero": "right", "chips": "corner", "keep": True},
            "banner": {"hero": "left", "text": "column", "chips": "stack", "keep": False}}
        imp = self.importance if self.importance is not None else [str(k) for k in range(1, min(3, n) + 1)]
        return json.dumps({"roles": roles, "groups": self.groups, "importance": imp, "archetype": self.archetype,
                           "focal": self.focal, "plans": plans})


# ---------------------------------------------------------------------------
# the switch


def test_default_is_off(monkeypatch):
    monkeypatch.delenv("CHAMELEON_LLM", raising=False)
    assert not llm.enabled()
    monkeypatch.setenv("CHAMELEON_LLM", "0")
    assert not llm.enabled()
    monkeypatch.setenv("CHAMELEON_LLM", "1")
    assert llm.enabled()


def test_off_returns_empty_without_touching_the_backend(monkeypatch):
    monkeypatch.delenv("CHAMELEON_LLM", raising=False)
    src = load("chameleon_sample_level2_core")
    stub = Stub()
    llm.set_backend(stub)
    try:
        r = llm.read(src, A.analyze(src))
    finally:
        llm._reset_for_tests()
    assert not r and r.status == "off" and stub.calls == 0


def test_engine_does_not_import_llm_or_llama_cpp_by_default():
    code = "import sys, engine.resize, engine.main; print('engine.llm' in sys.modules, 'llama_cpp' in sys.modules)"
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("CHAMELEON_LLM", "CHAMELEON_VLM")}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), env=env)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False False"


# ---------------------------------------------------------------------------
# the listing and the schema


def test_listing_is_id_free_and_order_free():
    src = load("chameleon_sample_level3_advanced")
    text, ids = llm.listing(src)
    assert len(ids) == len(src["elements"]) and set(ids) == {e["id"] for e in src["elements"]}
    words = set(text.replace('"', " ").replace("(", " ").replace(")", " ").split())
    for el in src["elements"]:
        assert el["id"] not in words, el["id"]                    # no element id leaks into the prompt
    assert "group_id" not in text and "badge1" not in text and "cta_bg" not in text
    assert "Shop the Summer Line" in text and "rank1/" in text and "in #" in text and "grp A" in text
    # renamed ids, renamed groups and a shuffled element list give the same text
    shuffled = copy.deepcopy(src)
    random.Random(3).shuffle(shuffled["elements"])
    names = {el["id"]: f"x{i}" for i, el in enumerate(shuffled["elements"])}
    gids = {}
    for el in shuffled["elements"]:
        el["id"] = names[el["id"]]
        if el.get("group_id"):
            el["group_id"] = gids.setdefault(el["group_id"], f"g{len(gids)}")
    text2, ids2 = llm.listing(shuffled)
    assert text2 == text
    assert [names[i] for i in ids] == ids2


def test_listing_caps_the_element_count_keeping_texts_first():
    src = load("chameleon_sample_level2_core")
    big = copy.deepcopy(src)
    for k in range(60):
        big["elements"].append({"id": f"s{k}", "type": "shape", "x": 10 + k, "y": 10, "width": 5, "height": 5,
                                "shape_type": "rectangle", "fill_color": "rgba(1,2,3,1)", "z_index": 1})
    text, ids = llm.listing(big)
    assert len(ids) == llm.MAX_ELEMENTS
    assert all(e["id"] in ids for e in src["elements"] if e["type"] in ("text", "image"))
    assert text.count("\n") == llm.MAX_ELEMENTS


def test_schema_restricts_roles_per_type_and_indices_to_listed_elements():
    src = load("chameleon_sample_level2_core")
    text, ids = llm.listing(src)
    s = llm.schema_for(src, ids)
    by = {e["id"]: e for e in src["elements"]}
    props = s["properties"]["roles"]["properties"]
    assert list(props) == [str(k) for k in range(1, len(ids) + 1)]
    for k, eid in enumerate(ids, 1):
        enum = props[str(k)]["enum"]
        expect = {"text": llm.TEXT_ROLES, "image": llm.IMAGE_ROLES, "shape": llm.SHAPE_ROLES}[by[eid]["type"]]
        assert enum == expect
    assert s["properties"]["groups"]["items"]["properties"]["m"]["items"]["enum"] == [str(k) for k in range(1, len(ids) + 1)]
    assert list(s["properties"]) == ["roles", "groups", "importance", "archetype", "focal", "plans"]
    assert set(s["properties"]["plans"]["properties"]) == set(llm.FAMILIES)
    from engine.vlm import validate
    assert validate(json.loads(Stub().complete(llm.messages_for(text), s, 10, 0)), s) == []
    # the grammar builder accepts it (llama_cpp is installed in the dev venv; skip elsewhere)
    try:
        from llama_cpp.llama_grammar import json_schema_to_gbnf
    except Exception:  # noqa: BLE001
        pytest.skip("llama_cpp not installed")
    root = next(line for line in json_schema_to_gbnf(json.dumps(s)).splitlines() if line.startswith("root "))
    assert root.index("roles-kv") < root.index("groups-kv") < root.index("plans-kv")     # answer order = property order


# ---------------------------------------------------------------------------
# interpretation


def test_interpret_maps_roles_groups_and_plans_onto_the_design():
    src = load("chameleon_sample_level3_advanced")
    a = A.analyze(src)
    text, ids = llm.listing(src)
    k = {eid: str(i) for i, eid in enumerate(ids, 1)}
    roles = {k[e["id"]]: {"text": "body", "image": "image", "shape": "shape"}[e["type"]] for e in src["elements"]}
    roles.update({k["headline"]: "headline", k["cta_label"]: "cta", k["logo"]: "logo", k["product"]: "hero",
                  k["badge1_label"]: "badge", k["badge2_label"]: "badge", k["badge3_label"]: "body",
                  k["legal_text"]: "fine_print", k["ribbon_label"]: "headline"})
    answer = {"roles": roles,
              "groups": [{"m": [k["headline"], k["subhead"]], "why": "lockup"},
                         {"m": [k["product"], k["product"]], "why": "frame"},            # one member: dropped
                         {"m": [k["subhead"], k["headline"]], "why": "caption"},         # duplicate set: dropped
                         {"m": ["99", k["logo"]], "why": "logo"}],                         # bad index: dropped
              "importance": [k["headline"], k["product"], k["headline"], "0"],
              "archetype": "product_ad", "focal": "hero",
              "plans": {"tall": {"chips": "corner", "keep": True}, "square": {"hero": "up", "chips": "row", "keep": "yes"},
                        "wide": {"hero": "right", "chips": "beside_cta", "keep": False},
                        "banner": {"hero": "stack", "text": "column", "chips": "stack", "keep": True}}}
    r = llm.interpret(answer, ids, src, a)
    assert r.status == "ok" and r
    assert r.fine["headline"] == "headline" and r.roles["headline"][0] == P.HEADLINE
    assert r.fine["group:cta"] == "cta" and r.roles["group:cta"] == (P.CTA, llm.BASE_CONF[P.CTA])
    assert r.fine["logo"] == "logo" and r.fine["product"] == "hero" and r.roles["product"][0] == P.PICTURE
    assert r.fine["row:group:badge1"] == "badge"          # a sibling row takes its parts' label votes (2 badge : 1 body)
    # two headlines: the one ranked most important keeps the full confidence, the other is diluted
    assert r.roles["headline"][1] == llm.BASE_CONF[P.HEADLINE]
    assert r.roles["group:ribbon"][0] == P.HEADLINE and r.roles["group:ribbon"][1] == pytest.approx(llm.BASE_CONF[P.HEADLINE] / 2)
    assert r.groups == [(["headline", "subhead"], "lockup")]
    assert r.importance == ["headline", "product"]
    assert r.plans == {"tall": {"chips": "corner", "keep": True}, "square": {"chips": "row"},
                       "wide": {"hero": "right", "chips": "beside_cta", "keep": False},
                       "banner": {"text": "column", "chips": "stack", "keep": True}}
    assert r.archetype == "product_ad" and r.focal == "hero"
    p = r.perception()
    assert isinstance(p, P.Perception) and p.roles == r.roles and p.archetype == "product_ad"
    assert llm.Reading.from_dict(json.loads(json.dumps(r.as_dict()))).as_dict() == r.as_dict()


def test_interpret_drops_roles_that_contradict_the_element_type():
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    text, ids = llm.listing(src)
    k = {eid: str(i) for i, eid in enumerate(ids, 1)}
    roles = {k[e["id"]]: {"text": "body", "image": "image", "shape": "shape"}[e["type"]] for e in src["elements"]}
    roles[k["product"]] = "headline"            # not in the image enum
    roles[k["logo"]] = "background"             # allowed for an image, but MINOR is no vote for an image unit
    r = llm.interpret({"roles": roles, "groups": [], "importance": [], "archetype": "x", "focal": "y", "plans": 7},
                      ids, src, a)
    assert "product" not in r.element_roles and "product" not in r.roles
    assert "logo" not in r.roles and r.element_roles["logo"] == "background"
    assert r.archetype is None and r.focal is None and r.plans == {} and r.importance == []


# ---------------------------------------------------------------------------
# the call: stub backend, cache, failures


def test_read_asks_once_per_source_and_caches(fresh, monkeypatch, tmp_path):
    monkeypatch.setenv("CHAMELEON_LLM_CACHE_DIR", str(tmp_path / "cache"))
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    text, ids = llm.listing(src)
    k = {eid: str(i) for i, eid in enumerate(ids, 1)}
    stub = Stub(roles={k["headline"]: "headline", k["cta_label"]: "cta", k["badge_label"]: "badge",
                       k["logo"]: "logo", k["product"]: "hero", k["subhead"]: "subhead"},
                groups=[{"m": [k["headline"], k["subhead"]], "why": "lockup"}])
    llm.set_backend(stub)
    r = llm.read(src, a)
    assert r.status == "ok" and stub.calls == 1
    assert r.fine == {"group:badge": "badge", "logo": "logo", "product": "hero", "headline": "headline",
                      "subhead": "subhead", "group:cta": "cta", "deco_circle_1": "background", "deco_circle_2": "background"}
    assert r.groups == [(["headline", "subhead"], "lockup")]
    assert r.plans["wide"] == {"hero": "right", "chips": "corner", "keep": True}
    assert stub.messages[0][0]["role"] == "system" and "Design:" in stub.messages[0][1]["content"]
    assert "headline" not in stub.messages[0][1]["content"].split("Design:")[1]      # no id, no role in the listing
    r2 = llm.read(src, a)
    assert r2.status == "cached" and stub.calls == 1 and r2.fine == r.fine
    llm._state["cache"].clear()                     # disk cache still answers
    r3 = llm.read(src, a)
    assert r3.status == "cached" and stub.calls == 1
    other = load("chameleon_sample_level1_warmup")
    llm.read(other, A.analyze(other))
    assert stub.calls == 2


def test_read_never_raises(fresh):
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    llm.set_backend(Stub(text="not json at all"))
    r = llm.read(src, a)
    assert not r and r.status == "no_answer"
    llm.set_backend(Stub(text=json.dumps({"roles": {}, "groups": [], "importance": [], "archetype": "x",
                                          "focal": "y", "plans": {}})))
    assert llm.read(src, a, use_cache=False).status == "no_answer"       # fails the schema
    boom = Stub(raise_exc=RuntimeError("boom"))
    llm.set_backend(boom)
    assert llm.read(src, a, use_cache=False).status == "error"
    assert llm.read(src, a, use_cache=False).status == "error"
    assert llm._state["disabled"] and boom.calls == 2
    assert llm.read(src, a, use_cache=False).status == "off"            # switched off for the process
    assert boom.calls == 2


def test_read_respects_the_budget(fresh, monkeypatch):
    src = load("chameleon_sample_level2_core")
    a = A.analyze(src)
    stub = Stub()
    llm.set_backend(stub)
    monkeypatch.setenv("CHAMELEON_LLM_BUDGET_S", "0.5")
    assert llm.read(src, a, use_cache=False).status == "budget" and stub.calls == 0     # less than MIN_REMAINING_S left
    monkeypatch.setenv("CHAMELEON_LLM_BUDGET_S", "1.2")
    slow = Stub(delay=1.4)
    llm.set_backend(slow)
    r = llm.read(src, a, use_cache=False)
    assert r.status == "ok" and llm._state["timeouts"] == 1              # the answer still parsed: kept, counted
    assert llm.read(src, a, use_cache=False).status == "ok"
    assert llm._state["disabled"]                                         # two timeouts switch it off
    assert llm.read(src, a, use_cache=False).status == "off" and slow.calls == 2


def test_no_model_file_means_no_opinion(fresh):
    src = load("chameleon_sample_level1_warmup")
    r = llm.read(src, A.analyze(src))
    assert r.status == "no_model" and not r
    assert llm.status().startswith("off: no model")
