"""Candidate layouts for the judge loop (generate -> rectify -> render -> score).

One floor plan per ratio family (v1) becomes a handful of variants here:
hero left / right / stacked, badges in a row / in the corners / beside the
CTA, tight / normal / loose spacing, a slightly bolder or shyer global
scale, and (banners) the headline stacked above or inline with the subhead.
Small ratio changes get two or three anchor variants whose content scale
sits a little above min(sx, sy) when the canvas has room, plus a couple of
floor plans as alternatives. Every candidate is a complete `Placement`
(boxes for every element, font sizes via the measurer); `engine.resize`
materializes, rectifies, renders and scores them and keeps the best.

Nothing here looks at element ids; roles come from the analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.analyze import Analysis
from engine.floorplan import (
    BANNER,
    SQUARE,
    TALL,
    WIDE,
    PlanOptions,
    floorplan_relayout,
    ratio_family,
)
from engine.geometry import Box
from engine.relayout import Placement, anchor_relayout, ratio_change, resolve_vertical_collisions
from engine.textfit import TextMeasurer, default_measurer

SMALL_CHANGE_MAX = 1.75     # ratio_change() up to this: anchor variants compete unpenalised (score.ADAPT_RATIO)
MAX_CANDIDATES = 18
ANCHOR_SCALE_BOOSTS = (1.0, 1.12, 1.25, 1.4)   # content scale = min(sx, sy) * boost, capped at max(sx, sy)
TIGHT, LOOSE = 0.75, 1.3
BOLD, BOLDER = 1.3, 1.5     # v4 scale_bias variants: ideal sizes past the proportional size when there is room
FILL = 1.5                  # the "fill" variant: one global scale, searched from 1.5 x proportional down


@dataclass
class Candidate:
    name: str
    strategy: str                       # "anchor" | "floorplan"
    placement: Placement
    options: PlanOptions | None = None  # floor plan variant
    scale: float | None = None          # anchor content scale
    fallback: bool = False              # safety net: pays the scorer's adaptation penalty, so it only
                                        # wins when every real candidate has a hard defect


def generate_candidates(analysis: Analysis, source: dict[str, Any], target: Box,
                        measurer: TextMeasurer | None = None,
                        limit: int = MAX_CANDIDATES) -> list[Candidate]:
    m = measurer or default_measurer()
    by_id = {el["id"]: el for el in source["elements"]}
    change = ratio_change(analysis.canvas, target)
    family = ratio_family(target)
    out: list[Candidate] = []

    small = change <= SMALL_CHANGE_MAX
    if small:
        for s, label in anchor_scales(analysis.canvas, target):
            out.append(Candidate(f"anchor {label} scale={s:.3f}", "anchor",
                                 _anchor(analysis, target, s), scale=s))
        plans = plan_variants(family)[:3] + [p for p in plan_variants(family) if p.scale_bias == BOLD][:1]
    else:
        plans = plan_variants(family)

    for opts in plans:
        pl = floorplan_relayout(analysis, target, by_id, m, opts)
        resolve_vertical_collisions(analysis, pl, target)
        out.append(Candidate(f"{family} {opts.name}", "floorplan", pl, options=opts))

    if not small:
        # Safety candidate: proportions kept, everything slid toward its anchor.
        s = min(target.w / analysis.canvas.w, target.h / analysis.canvas.h)
        out.append(Candidate(f"anchor fallback scale={s:.3f}", "anchor",
                             _anchor(analysis, target, s), scale=s, fallback=True))

    return dedupe(out)[:limit]


def anchor_scales(src: Box, target: Box) -> list[tuple[float, str]]:
    sx, sy = target.w / src.w, target.h / src.h
    lo, hi = min(sx, sy), max(sx, sy)
    scales: list[tuple[float, str]] = []
    for boost in ANCHOR_SCALE_BOOSTS:
        s = min(hi, lo * boost)
        if all(abs(s - t) > 0.015 * lo for t, _ in scales):
            scales.append((s, "fit" if boost == 1.0 else f"x{boost:g}"))
    return scales


def plan_variants(family: str) -> list[PlanOptions]:
    """Variants in rough order of prior usefulness (the list is truncated
    for small ratio changes). Duplicates that a design cannot realize
    (no chips, no hero) collapse in `dedupe`."""
    P = PlanOptions
    # v4: every family also tries bolder ideals (scale_bias 1.3 / 1.5) and a
    # "fill" variant (one global scale from 1.5 x proportional down); banners
    # also try the hero-beside-column plan (text_flow="column") and keep the
    # v3 stacked chip column as a variant (chips="stack").
    if family == TALL:
        return [P(), P(chips="corner"), P(chips="beside_cta"), P(spacing=TIGHT), P(spacing=LOOSE),
                P(scale_bias=1.15), P(scale_bias=BOLD), P(scale_bias=BOLDER), P(scale_bias=FILL, fill=True),
                P(scale_bias=0.85), P(chips="corner", spacing=TIGHT), P(chips="corner", scale_bias=BOLD)]
    if family == SQUARE:
        return [P(), P(chips="corner"), P(hero_side="left"), P(hero_side="right"),
                P(chips="beside_cta"), P(spacing=TIGHT), P(spacing=LOOSE), P(scale_bias=1.15),
                P(scale_bias=BOLD), P(scale_bias=BOLDER), P(scale_bias=FILL, fill=True),
                P(hero_side="left", chips="corner"), P(hero_side="right", chips="corner"),
                P(hero_side="left", scale_bias=BOLD)]
    if family == WIDE:
        return [P(), P(hero_side="left"), P(hero_side="right"), P(chips="corner"),
                P(chips="beside_cta"), P(hero_side="stack"), P(spacing=TIGHT), P(spacing=LOOSE),
                P(scale_bias=1.15), P(scale_bias=BOLD), P(scale_bias=BOLDER), P(scale_bias=FILL, fill=True),
                P(hero_side="left", chips="corner"), P(hero_side="right", chips="corner"),
                P(hero_side="left", scale_bias=BOLD), P(hero_side="right", scale_bias=BOLD),
                P(hero_side="stack", scale_bias=BOLD)]
    return [P(), P(text_flow="column"), P(text_flow="column", hero_side="right"), P(hero_side="right"),
            P(text_flow="inline"), P(hero_side="right", text_flow="inline"),
            P(spacing=TIGHT), P(spacing=LOOSE), P(scale_bias=1.15), P(scale_bias=BOLD),
            P(scale_bias=BOLDER), P(scale_bias=FILL, fill=True),
            P(text_flow="column", scale_bias=BOLD), P(text_flow="column", scale_bias=FILL, fill=True),
            P(chips="stack"), P(text_flow="inline", spacing=TIGHT)]


def _anchor(analysis: Analysis, target: Box, scale: float) -> Placement:
    pl = anchor_relayout(analysis, target, content_scale=scale)
    resolve_vertical_collisions(analysis, pl, target)
    return pl


def dedupe(cands: list[Candidate]) -> list[Candidate]:
    seen: set[tuple] = set()
    out = []
    for c in cands:
        key = placement_key(c.placement)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def placement_key(pl: Placement) -> tuple:
    items = []
    for eid in sorted(pl.boxes):
        b = pl.boxes[eid]
        f = pl.font_size.get(eid, pl.font_scale.get(eid, 1.0))
        items.append((eid, round(b.x), round(b.y), round(b.w), round(b.h), round(f, 1)))
    return tuple(items)
