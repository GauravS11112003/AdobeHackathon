"""v9 critic loop (engine/critic.py, candidates.generate_repairs, resize.repair).

  * diagnosis on a hand-built judged set: shared hard fails only when no
    candidate is clean, soft weaknesses on the best clean ones, recipes
    keyed on roles / relations
  * directives on materialized elements: a text raised to its floor on a
    strip, a plate brought under the text it backed, a unit pinned back to
    its edge, a colliding unit shrunk
  * the loop end to end on a source whose every template fails the floor on
    a 160 px strip: a "+fix" candidate exists and the output keeps the contract
  * CHAMELEON_CRITIC=0 leaves the judge loop byte-identical to the loop
    without the repair step
"""

import copy
import json
from pathlib import Path

import pytest

from engine import candidates as C
from engine import critic as K
from engine import resize as RZ
from engine.analyze import CTA, HEADLINE, analyze
from engine.geometry import Box
from engine.score import Score, score_design
from engine.textfit import default_measurer

INPUT = Path(__file__).resolve().parent.parent / "input"


def load(name: str) -> dict:
    return json.loads((INPUT / f"chameleon_sample_{name}.json").read_text())["source"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(RZ, "JUDGE_RENDER", False)
    for k in ("CHAMELEON_CRITIC", "CHAMELEON_CRITIC_ROUNDS", "CHAMELEON_CRITIC_TARGET", "CHAMELEON_OPTIMIZE"):
        monkeypatch.delenv(k, raising=False)


class FakeJudged:
    def __init__(self, name, hard=(), breakdown=None, total=80.0, fallback=False, design=None, notes=None):
        self.name = name
        self.strategy = "floorplan"
        self.fallback = fallback
        self.design = design or {"canvas": {"width": 100, "height": 100}, "elements": []}
        self.score = Score(total=total - 1000.0 * len(hard), hard=list(hard),
                           breakdown=dict(breakdown or {}), notes=dict(notes or {}))


def text(eid, content, x, y, w, h, size, color="rgba(255,255,255,1)", **kw):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "content": content,
          "font_size": size, "font_family": "Solstice Sans", "color": color, "text_align": "center",
          "z_index": kw.pop("z", 5)}
    el.update(kw)
    return el


def shape(eid, x, y, w, h, fill="rgba(20,20,60,1)", z=1):
    return {"id": eid, "type": "shape", "shape_type": "rectangle", "x": x, "y": y, "width": w, "height": h,
            "fill_color": fill, "z_index": z}


def plate_source():
    """A white headline on a dark plate over a white canvas, a CTA label and body copy."""
    return {"canvas": {"width": 1000, "height": 1000}, "elements": [
        shape("bg", 0, 0, 1000, 1000, fill="rgba(255,255,255,1)", z=0),
        shape("plate", 100, 120, 800, 220, z=1),
        text("head", "SUMMER SALE", 150, 160, 700, 140, 110, font_weight="bold"),
        text("sub", "Everything in the shop at half price for one week only", 150, 400, 700, 120, 36,
             color="rgba(30,30,30,1)"),
        shape("pill", 350, 820, 300, 90, fill="rgba(200,30,30,1)", z=2),
        text("cta", "SHOP NOW", 380, 845, 240, 40, 32, z=3),
    ]}


def strip_source():
    """One long one-word headline plus lots of copy: every template is below the floor on 160x600."""
    return {"canvas": {"width": 1200, "height": 1600}, "elements": [
        shape("bg", 0, 0, 1200, 1600, fill="rgba(245,240,230,1)", z=0),
        text("head", "ORIGAMICLASSES", 60, 120, 1080, 160, 120, color="rgba(20,20,20,1)", font_weight="bold"),
        text("sub", "LEARN GREAT TIPS ON MAKING FLOWERS AND ANIMALS FROM A SINGLE SHEET OF PAPER", 100, 360, 1000, 220, 44,
             color="rgba(20,20,20,1)"),
        text("body", "MORE INFORMATION AVAILABLE ON OUR OFFICIAL WEBSITE AND IN THE STUDIO", 100, 640, 1000, 160, 34,
             color="rgba(20,20,20,1)"),
        text("date", "JAN 9, 5 PM - 6.30 PM", 100, 860, 1000, 80, 36, color="rgba(20,20,20,1)"),
        shape("pill", 350, 1380, 500, 110, fill="rgba(200,30,30,1)", z=2),
        text("cta", "MYORIGAMI.NET", 380, 1410, 440, 50, 40, z=3),
    ]}


# ---------------------------------------------------------------------------
# diagnosis


def test_shared_hard_fail_is_diagnosed_only_when_nobody_is_clean():
    src = plate_source()
    an = analyze(src)
    t = Box(0, 0, 160, 600)
    pool = [FakeJudged("a", ["head headline font 6 below readable 12"]),
            FakeJudged("b", ["head headline font 7 below readable 12", "cta cta font 5 below readable 12"]),
            FakeJudged("c", ["head headline font 5 below readable 12"]),
            FakeJudged("fb", ["head headline font 3 below readable 12"], fallback=True)]
    diags = K.diagnose(pool, an, src, t)
    rules = [(d.rule, d.units) for d in diags]
    assert ("below_floor", ("head",)) in rules
    assert ("below_floor", ("cta",)) not in rules          # one of three: not shared
    head = next(d for d in diags if d.units == ("head",))
    assert head.hard and head.shared == 3 and head.of == 3
    assert any("floor" in r.directives for r in head.recipes)
    assert any(r.plan.get("rescue") for r in head.recipes)
    # one clean candidate: the hard fails are the others' problem, not the generator's
    clean = FakeJudged("d", [], breakdown={k: 1.0 for k in K.TYPICAL}, total=95.0)
    assert K.diagnose(pool + [clean], an, src, t) == []


def test_contrast_drop_recipes_name_the_source_plate_and_hero():
    src = plate_source()
    an = analyze(src)
    assert an.roles["head"] == HEADLINE
    plate = K.find_backing("head", an, src, default_measurer())
    assert plate is not None and "plate" in plate
    assert K.find_backing("sub", an, src, default_measurer()) is None     # sat on the white canvas
    pool = [FakeJudged("a", ["head unreadable contrast 1.20 (source 12.5)"]),
            FakeJudged("b", ["head unreadable contrast 1.40 (source 12.5)"])]
    diags = K.diagnose(pool, an, src, Box(0, 0, 1080, 1080))
    assert diags and diags[0].rule == "contrast_drop"
    assert diags[0].recipes[0].directives == {"backing": {"head": plate}}


def test_weak_soft_term_on_the_best_clean_candidates():
    src = plate_source()
    an = analyze(src)
    t = Box(0, 0, 1080, 1920)
    good = {k: 1.0 for k in K.TYPICAL}
    weak = dict(good, **{"faith.anchors": 0.2})
    design = RZ.resize(src, {"width": 1080, "height": 1920})
    design = copy.deepcopy(design)
    for el in design["elements"]:
        if el["id"] in ("pill", "cta"):
            el["y"] = 300.0 + (el["id"] == "cta") * 25.0     # the CTA left the bottom edge it hugged
    pool = [FakeJudged("a", [], weak, 86.0, design=design), FakeJudged("b", [], weak, 85.0, design=design),
            FakeJudged("c", [], dict(good, **{"faith.anchors": 0.3}), 84.0, design=design),
            FakeJudged("d", [], good, 70.0, design=design)]      # 4th best: not consulted
    diags = K.diagnose(pool, an, src, t)
    assert [d.rule for d in diags] == ["weak:faith.anchors"]
    assert not diags[0].hard
    pool[0].score.breakdown["faith.anchors"] = 0.9       # the best one is fine: not shared
    assert K.diagnose(pool, an, src, t) == []


# ---------------------------------------------------------------------------
# directives


def test_floor_directive_raises_a_strip_headline_and_reshapes_the_cta_pill():
    src = strip_source()
    an = analyze(src)
    t = Box(0, 0, 160, 600)
    m = default_measurer()
    els = copy.deepcopy(src["elements"])
    by = {e["id"]: e for e in els}
    s = 160 / 1200
    for e in els:   # a crude proportional copy: everything far below the floors
        e["x"], e["y"], e["width"], e["height"] = e["x"] * s, e["y"] * s, e["width"] * s, e["height"] * s
        if e["type"] == "text":
            e["font_size"] = e["font_size"] * s
    by["head"]["font_size"] = 8.0          # the fitter's verdict on a 1.6 em tracked word: under the 12 px floor
    done = K.apply_directives(els, an, t, {"floor": ["head", "cta"], "cap_floor": True}, m)
    assert set(done["floor"]) == {"head", "cta"}
    floors = K.cap_floors(an, t)
    assert by["head"]["font_size"] >= floors[HEADLINE] - 0.5
    assert by["cta"]["font_size"] >= floors[CTA] - 0.5
    for eid in ("head", "cta"):
        el = by[eid]
        assert m.fits(el, el["font_size"], el["width"], el["height"])
        assert 0 <= el["x"] and el["x"] + el["width"] <= t.w + 0.01
    # the pill was re-shaped around its label
    pill, cta = Box.of(by["pill"]), Box.of(by["cta"])
    assert pill.contains_fraction(cta) > 0.95


def test_backing_pin_and_shrink_directives():
    src = plate_source()
    an = analyze(src)
    t = Box(0, 0, 1080, 1080)
    m = default_measurer()
    els = copy.deepcopy(src["elements"])
    by = {e["id"]: e for e in els}
    # the plate stayed where it was, the headline moved far away from it
    by["head"].update(x=100, y=700, width=880, height=160)
    done = K.apply_directives(els, an, t, {"backing": {"head": an.element_unit["plate"]}}, m)
    assert "backing" in done
    assert Box.of(by["plate"]).contains_fraction(Box.of(by["head"])) > 0.9
    # pin: the CTA hugged the bottom in the source; moved to the top, it comes back down
    cta_unit = an.element_unit["cta"]
    assert an.unit(cta_unit).anchor_y == "bottom"
    for eid in an.unit(cta_unit).ids:
        by[eid]["y"] -= 600
    assert K.apply_directives(els, an, t, {"pin": [cta_unit]}, m)["pin"] == [cta_unit]
    frame = Box.union(Box.of(by[i]) for i in an.unit(cta_unit).ids)
    assert t.h - frame.bottom <= 0.05 * t.h
    # shrink: scales the unit about its centre, label font follows
    before = Box.union(Box.of(by[i]) for i in an.unit(cta_unit).ids)
    f0 = by["cta"]["font_size"]
    K.apply_directives(els, an, t, {"shrink": {cta_unit: 0.8}}, m)
    after = Box.union(Box.of(by[i]) for i in an.unit(cta_unit).ids)
    assert abs(after.cx - before.cx) < 0.01 and abs(after.w - 0.8 * before.w) < 0.01
    assert abs(by["cta"]["font_size"] - 0.8 * f0) < 1e-6


# ---------------------------------------------------------------------------
# the loop


def test_loop_adds_fix_candidates_on_a_strip_and_keeps_the_contract(monkeypatch):
    monkeypatch.setenv("CHAMELEON_CRITIC", "1")
    monkeypatch.setenv("CHAMELEON_OPTIMIZE", "0")
    src = strip_source()
    best, judged = RZ.resize_with_candidates(src, {"width": 160, "height": 600})
    fixes = [j for j in judged if "+fix:" in j.name]
    assert fixes, "no repair candidate was generated"
    assert RZ.LAST_CRITIC and RZ.LAST_CRITIC[0]["diagnoses"]
    for j in fixes:
        assert j.score.notes["critic"]["round"] >= 1
        assert j.strategy in ("anchor", "floorplan", "structure")
    assert [el["id"] for el in best["elements"]] == [el["id"] for el in src["elements"]]
    for el, s in zip(best["elements"], src["elements"]):
        if el["type"] == "text":
            assert el["content"] == s["content"] and el["font_family"] == s["font_family"]
    # the repaired headline is readable where every template left it below the floor
    head = next(el for el in best["elements"] if el["id"] == "head")
    assert head["font_size"] >= K.cap_floors(analyze(src), Box(0, 0, 160, 600))[HEADLINE] - 0.5
    assert not judged[0].score.hard


def test_flag_off_is_byte_identical_to_the_loop_without_repairs(monkeypatch):
    src = load("level3_advanced")
    target = {"width": 160, "height": 600}
    monkeypatch.setenv("CHAMELEON_CRITIC", "0")
    off = RZ.resize(src, target)
    assert not any("+fix" in j.name for j in RZ.LAST_JUDGED)
    monkeypatch.setenv("CHAMELEON_CRITIC", "1")
    monkeypatch.setattr(RZ, "repair", lambda judged, *a, **k: judged)
    plain = RZ.resize(src, target)
    assert json.dumps(off, sort_keys=True) == json.dumps(plain, sort_keys=True)


def test_repairs_are_deduped_and_capped():
    src = strip_source()
    an = analyze(src)
    t = Box(0, 0, 160, 600)
    cands = C.generate_candidates(an, src, t)
    seeds = [c for c in cands if not c.fallback][:4]
    diag = K.Diagnosis("below_floor", ("head",), "x", 3, 3, True,
                       [K.Recipe("headline to floor", directives={"floor": ["head"], "cap_floor": True}),
                        K.Recipe("secondary copy yields", plan={"rescue": True}, directives={"floor": ["head"]}),
                        K.Recipe("tight, shy plan", plan={"spacing": 0.75, "scale_bias": 0.85})])
    already = {(C.placement_key(c.placement), K._freeze(c.directives or {})) for c in cands}
    reps = C.generate_repairs(an, src, t, [diag] * 3, seeds, already, limit=4)
    assert 1 <= len(reps) <= 4
    assert len({(C.placement_key(r.placement), K._freeze(r.directives or {})) for r in reps}) == len(reps)
    assert all("+fix:" in r.name and r.fix for r in reps)
    assert all(r.strategy == next(s.strategy for s in seeds if r.name.startswith(s.name)) for r in reps)
