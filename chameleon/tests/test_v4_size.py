"""v4: the engine uses the canvas when it has room (docs/EVAL_V4.md).

1. candidates: bolder scale_bias variants (1.3 / 1.5), a "fill" variant
   (one global scale), the hero-beside-column plan on banners, chips in a
   row first (columns only when the rows do not fit the height),
2. floor plans: ideals of scaled units at least the proportional scale x
   the bias; the wide plan keeps the hero at full size and picks its share
   of the width so the headline wraps on at most HEAD_MAX_LINES lines,
3. scorer: `layout.size` credits primary units up to AMBITION x the
   proportional size, `layout.fill` also counts ink density; hard fails
   and the source-relative rules are untouched.

The Level 3 numbers below are the v3 engine's own output for the LinkedIn
banner (docs/sanity_v3/level3_1584x396.json): headline 16 px, CTA label
13 px, product 165 px, the four badges stacked in a column.
"""

import json
from pathlib import Path

import pytest

from engine import floorplan as F
from engine.analyze import BADGE, CTA, HEADLINE, HERO, analyze
from engine.candidates import BOLD, BOLDER, FILL, generate_candidates, plan_variants
from engine.geometry import Box
from engine.resize import resize, resize_with_candidates
from engine.score import AMBITION, WEIGHTS, score_design
from engine.textfit import default_measurer

INPUT = Path(__file__).resolve().parent.parent / "input"
LEVEL3 = INPUT / "chameleon_sample_level3_advanced.json"

V3_HEADLINE = 16.0      # docs/sanity_v3/level3_1584x396.json
V3_CTA = 13.0
V3_HERO = 165.0
MIN_GAIN = 1.5          # the v4 headline on the LinkedIn banner is at least this much larger


def _level3():
    return json.loads(LEVEL3.read_text())["source"]


def _roles(src):
    return analyze(src).roles


# ---------------------------------------------------------------------------
# 1. Level 3 on the LinkedIn banner: bigger type, badges in one row, no defect


@pytest.fixture(scope="module")
def linkedin():
    src = _level3()
    best, judged = resize_with_candidates(src, {"width": 1584, "height": 396})
    return src, best, judged


def test_level3_linkedin_headline_and_cta_are_much_larger_than_v3(linkedin):
    src, best, judged = linkedin
    roles = _roles(src)
    by = {e["id"]: e for e in best["elements"]}
    head = next(e for e in best["elements"] if e["type"] == "text" and roles[e["id"]] == HEADLINE)
    cta = next(e for e in best["elements"] if e["type"] == "text" and roles[e["id"]] == CTA)
    hero = next(e for e in best["elements"] if e["type"] == "image" and roles[e["id"]] == HERO)
    assert float(head["font_size"]) >= MIN_GAIN * V3_HEADLINE, head["font_size"]
    assert float(cta["font_size"]) >= V3_CTA
    assert float(hero["height"]) >= 1.5 * V3_HERO
    assert not judged[0].score.hard
    assert set(by) == {e["id"] for e in src["elements"]}


def test_level3_linkedin_badges_sit_in_one_row(linkedin):
    src, best, _ = linkedin
    roles = _roles(src)
    pills = [e for e in best["elements"] if e["type"] == "shape" and roles[e["id"]] == BADGE
             and not float(e.get("rotation", 0) or 0)]
    assert len(pills) >= 3
    cys = [float(e["y"]) + float(e["height"]) / 2.0 for e in pills]
    assert max(cys) - min(cys) <= 2.0, cys
    xs = sorted(float(e["x"]) for e in pills)
    # side by side, not stacked: distinct x positions spanning more than one pill width
    assert xs[-1] - xs[0] > 1.5 * max(float(e["width"]) for e in pills)


def test_level3_wide_formats_keep_headline_at_least_proportional():
    """Every wide / banner preset at least 200 px tall gets a headline no
    smaller than 0.9 x the source font scaled by sqrt(area ratio)."""
    src = _level3()
    roles = _roles(src)
    head_id = next(i for i, r in roles.items() if r == HEADLINE)
    src_font = float(next(e for e in src["elements"] if e["id"] == head_id)["font_size"])
    src_area = src["canvas"]["width"] * src["canvas"]["height"]
    for w, h in ((1584, 396), (1600, 400), (1280, 720), (1600, 900)):
        out = resize(src, {"width": w, "height": h})
        font = float(next(e for e in out["elements"] if e["id"] == head_id)["font_size"])
        prop = src_font * (w * h / src_area) ** 0.5
        assert font >= 0.9 * prop, (w, h, font, prop)


# ---------------------------------------------------------------------------
# 2. candidates


def test_plan_variants_include_bold_fill_and_banner_column():
    for fam in (F.TALL, F.SQUARE, F.WIDE, F.BANNER):
        biases = {p.scale_bias for p in plan_variants(fam)}
        assert BOLD in biases and BOLDER in biases and FILL in biases
        assert any(p.fill for p in plan_variants(fam))
    assert any(p.text_flow == "column" for p in plan_variants(F.BANNER))
    assert any(p.chips == "stack" for p in plan_variants(F.BANNER))


def test_banner_column_variant_is_generated_and_named():
    src = _level3()
    a = analyze(src)
    names = [c.name for c in generate_candidates(a, src, Box(0, 0, 1584, 396))]
    assert any("text=column" in n for n in names)
    assert any(n.endswith("fill") for n in names)
    # a 90 px strip is too short for a column beside the hero: the variant
    # collapses into the row plan and dedupes away
    short = [c.name for c in generate_candidates(a, src, Box(0, 0, 728, 90))]
    assert "banner text=column" not in short, short


def test_fill_variant_uses_one_shrink_speed():
    src = _level3()
    a = analyze(src)
    by = {e["id"]: e for e in src["elements"]}
    met = F.Metrics.for_canvas(a.canvas, Box(0, 0, 1080, 1920), F.TALL, 1.0, FILL)
    b = F._Builder(a, by, met, default_measurer(), F.TALL, uniform=True)
    items, _, _ = F._column_items(b, met, 1920.0, with_hero=True, tight=False)
    assert all(it.prio == F.PRIO_PRIMARY for it in items)


def test_scaled_ideal_is_at_least_proportional_times_bias():
    src = _level3()
    a = analyze(src)
    by = {e["id"]: e for e in src["elements"]}
    cta = next(u for u in a.content_units() if u.role == CTA)
    for bias in (1.0, 1.3):
        met = F.Metrics.for_canvas(a.canvas, Box(0, 0, 1584, 396), F.BANNER, 1.0, bias)
        b = F._Builder(a, by, met, default_measurer(), F.BANNER)
        it = b.scaled(cta, ideal_h=0.065 * 396, floor_h=0.0, prio=F.PRIO_PRIMARY, w_frac=1.0, role_for_floor=CTA)
        assert it.ideal_s >= min(met.prop * bias, met.cap_scale * 1.0) - 1e-9


# ---------------------------------------------------------------------------
# 3. chips: rows first, columns only when the rows would not fit the height


class _Chip:
    def __init__(self, w, h):
        self.w, self.h, self.prio = w, h, F.PRIO_MINOR

    def size(self, k, aw, ah):
        return self.w, self.h

    def relax(self, f):
        pass


def test_chips_auto_prefers_rows_and_falls_back_to_columns():
    chips = [_Chip(100, 30) for _ in range(4)]
    c = F._Chips(chips, "auto", gap=10.0)
    w, h = c.size(1.0, 1000.0, 200.0)
    assert h == 30 and w == 430               # one row
    w, h = c.size(1.0, 250.0, 200.0)
    assert h == 70 and w == 210               # two rows of two
    w, h = c.size(1.0, 250.0, 50.0)
    assert h <= 50 and w > 210                # too short for two rows: columns


# ---------------------------------------------------------------------------
# 4. scorer


def test_layout_size_rewards_bigger_primaries_but_never_a_hard_fail():
    src = _level3()
    a = analyze(src)
    target = Box(0, 0, 1584, 396)
    best, judged = resize_with_candidates(src, {"width": 1584, "height": 396})
    assert "layout.size" in WEIGHTS and "layout.size" in judged[0].score.breakdown
    roles = a.roles
    head_id = next(i for i, r in roles.items() if r == HEADLINE)
    shrunk = json.loads(json.dumps(best))
    for e in shrunk["elements"]:
        if e["id"] == head_id:
            e["font_size"] = max(13.0, float(e["font_size"]) * 0.6)
    s_best = score_design(a, src, best, target, render=False, strategy="floorplan")
    s_small = score_design(a, src, shrunk, target, render=False, strategy="floorplan")
    assert s_small.breakdown["layout.size"] < s_best.breakdown["layout.size"]
    # a candidate with a hard defect can never beat a clean one, however big
    assert all(j.score.total < judged[0].score.total for j in judged[1:] if j.score.hard)
    assert all(not j.score.hard for j in judged[:1])


def test_layout_size_saturates_at_ambition():
    src = _level3()
    a = analyze(src)
    target = Box(0, 0, 1080, 1350)
    out = resize(src, {"width": 1080, "height": 1350})
    roles = a.roles
    head_id = next(i for i, r in roles.items() if r == HEADLINE)
    big = json.loads(json.dumps(out))
    for e in big["elements"]:
        if e["id"] == head_id:
            e["font_size"] = float(e["font_size"]) * 3.0
            e["height"] = float(e["height"]) * 3.0
    s = score_design(a, src, big, target, render=False)
    assert s.breakdown["layout.size"] <= 1.0
    assert AMBITION >= 1.0


def test_fill_counts_density_not_only_the_hull():
    from engine.score import _fill
    t = Box(0, 0, 1000, 200)
    thin = [Box(20, 90, 960, 20)]                  # a hairline across the banner: hull wide, ink tiny
    chunky = [Box(20, 20, 960, 160)]
    assert _fill(chunky, t) > _fill(thin, t)
