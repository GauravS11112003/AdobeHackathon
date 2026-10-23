"""
CHAMELEON engine entry point: resize(source, target_canvas) -> design.

Pipeline (see docs/CONTEXT.md §10 in the parent folder for the full plan):

  1. analyze(source)      -> roles, groups, anchors, hierarchy          (engine/analyze.py)
  2. generate candidates  -> several complete layouts: anchor variants  (engine/candidates.py)
                             for small shape changes (relayout.py), floor
                             plan variants for big ones (floorplan.py)
  3. materialize each     -> boxes + font sizes fitted with the real brand
                             fonts (shrink only when the wrapped text would
                             overflow its box)
  4. rectify each         -> push apart collisions, keep things on canvas,
                             snap, even out gaps, keep group insets     (engine/rectify.py)
  5. render + score each  -> hard defects, readability (incl. contrast on
                             the rendered pixels), layout quality,
                             faithfulness to the source                 (engine/render.py, score.py)
  6. return the best      -> same ids, same order, rounded geometry

Hard rules honoured here: every id returned exactly once, no content /
font_family changes, images scaled uniformly (aspect kept), no asset pixels
touched. A uniform-scale fallback guarantees an answer even if everything
above raises.

Debugging: `resize_with_candidates()` returns every judged candidate with
its score breakdown (the playground shows them); setting the environment
variable CHAMELEON_DUMP_DIR writes each candidate's JSON + PNG + scores
there; CHAMELEON_NO_RENDER=1 (or CHAMELEON_RENDER=0) judges on geometry
alone. Rendering is a bonus signal only: engine/render.py switches it off
under CPU emulation, on slow renders and on repeated failures, so resize()
never depends on the renderer (engine/main.py writes the JSON only after
resize() returns).
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.analyze import BACKGROUND, DECORATIVE, HEADLINE, Analysis, analyze
from engine.candidates import SMALL_CHANGE_MAX, Candidate, generate_candidates
from engine.geometry import Box
from engine import render as judge_render
from engine.rectify import rectify, rotated_extent
from engine.relayout import Placement, grow_panels
from engine.score import Score, score_design
from engine.textfit import MIN_FONT_SIZE, apply_font_size, default_measurer

logger = logging.getLogger(__name__)

JUDGE_RENDER = os.environ.get("CHAMELEON_NO_RENDER", "") not in ("1", "true", "yes")
TOP_RENDER = 3                     # candidates re-judged with pixels after the no-render pass
DUMP_DIR = os.environ.get("CHAMELEON_DUMP_DIR") or None
LAST_JUDGED: list["Judged"] = []     # every candidate of the most recent resize(), best first
_run_counter = 0


@dataclass
class Judged:
    name: str
    strategy: str
    design: dict[str, Any]
    score: Score
    elapsed: float = 0.0
    fallback: bool = False

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "strategy": self.strategy, "elapsed": round(self.elapsed, 3),
                "fallback": self.fallback, "pixels": judge_render.status(), **self.score.as_dict()}


def resize(source: dict[str, Any], target_canvas: dict[str, Any]) -> dict[str, Any]:
    target = Box(0.0, 0.0, float(target_canvas["width"]), float(target_canvas["height"]))
    try:
        best, judged = judge(source, target)
        _dump(judged)
        return best
    except Exception:  # pragma: no cover - last-resort safety net
        logger.exception("resize failed; falling back to uniform scale")
        return _uniform_fallback(source, target)


def resize_with_candidates(source: dict[str, Any], target_canvas: dict[str, Any]) -> tuple[dict[str, Any], list[Judged]]:
    """Like resize(), but also returns every judged candidate, best first."""
    target = Box(0.0, 0.0, float(target_canvas["width"]), float(target_canvas["height"]))
    try:
        return judge(source, target)
    except Exception:  # pragma: no cover
        logger.exception("resize failed; falling back to uniform scale")
        return _uniform_fallback(source, target), []


def judge(source: dict[str, Any], target: Box, render: bool | None = None) -> tuple[dict[str, Any], list[Judged]]:
    """Generate -> materialize -> rectify -> render -> score; best first."""
    global LAST_JUDGED
    analysis = analyze(source)
    render = JUDGE_RENDER if render is None else render
    judge_render.begin_task()          # per-task pixel budget; see engine/render.py
    judged: list[Judged] = []
    # Stage 1: every candidate is judged on geometry and the JSON contrast
    # estimate (no pixels). Stage 2: the top few are re-judged with a render
    # without text, which refines contrast / busyness under each text.
    for cand in generate_candidates(analysis, source, target):
        t0 = time.time()
        try:
            design = realize(source, analysis, cand.placement, target)
            sc = score_design(analysis, source, design, target, render=False, strategy=cand.strategy)
        except Exception:
            logger.exception("candidate %s failed; skipped", cand.name)
            continue
        judged.append(Judged(cand.name, cand.strategy, design, sc, time.time() - t0, cand.fallback))
    if not judged:
        raise RuntimeError("no candidate could be realized")
    # Best first; sort is stable, so earlier (default) candidates win exact
    # ties. The anchor safety net on a big shape change carries the scorer's
    # adaptation penalty, so it only wins when every real layout has a defect.
    judged.sort(key=lambda j: -j.score.total)
    if render:
        for j in judged[:TOP_RENDER]:
            t0 = time.time()
            try:
                j.score = score_design(analysis, source, j.design, target, render=True, strategy=j.strategy)
            except Exception:
                logger.exception("re-judging %s with pixels failed; keeping the estimate", j.name)
            j.elapsed += time.time() - t0
        judged.sort(key=lambda j: -j.score.total)
    LAST_JUDGED = judged
    return judged[0].design, judged


def realize(source: dict[str, Any], analysis: Analysis, placement: Placement, target: Box) -> dict[str, Any]:
    """Turn a Placement into a finished design: fit the text, fix defects,
    round and clamp."""
    elements = materialize(source, analysis, placement, target)
    elements = rectify(analysis, elements, target)
    grow_panels(analysis, elements, target)   # zones follow the content the rectifier moved
    _keep_headline_largest(elements, source, analysis)
    _finalize(elements, analysis, target)
    return {"canvas": {"width": int(target.w), "height": int(target.h)}, "elements": elements}


def materialize(source: dict[str, Any], analysis: Analysis, placement: Placement, target: Box) -> list[dict[str, Any]]:
    elements = []
    for el in source["elements"]:
        new = copy.deepcopy(el)
        box = placement.boxes[el["id"]]
        new["x"], new["y"], new["width"], new["height"] = box.x, box.y, box.w, box.h
        if el["type"] == "text":
            apply_font_size(new, _fit_text(new, el, placement.font_scale.get(el["id"], 1.0),
                                           placement.font_size.get(el["id"])))
        elements.append(new)
    return elements


def _fit_text(new: dict[str, Any], src: dict[str, Any], scale: float,
              explicit: float | None = None) -> float:
    """Scale the font with its box, then shrink only if the wrapped text would
    overflow. Grows the box height instead when the text needs a little more
    room than the box has (the renderer does not clip, so the box height is
    only a layout hint, but the judge sees overflow as a collision).

    `explicit` is a size a strategy already fitted with the measurer (floor
    plans); it is trusted below MIN_FONT_SIZE too, since tiny badge labels
    on a tiny banner are better than labels spilling out of their badge."""
    measurer = default_measurer()
    w, h = float(new["width"]), float(new["height"])
    if explicit is not None:
        wanted = max(1.0, float(explicit))
        if measurer.fits(new, wanted, w, h):
            return float(int(wanted)) if wanted >= 1.0 else wanted
        return measurer.fit_font_size(new, w, h, wanted, min(wanted, 1.0))
    wanted = max(MIN_FONT_SIZE, float(src["font_size"]) * scale)
    if measurer.fits(new, wanted, w, h):
        return float(int(wanted))
    size = measurer.fit_font_size(new, w, h, wanted, MIN_FONT_SIZE)
    if size < 0.8 * wanted:
        # Prefer a slightly taller box over a much smaller font: text boxes
        # are usually drawn with generous height in the source anyway.
        needed = measurer.natural_height(new, wanted, w)
        if needed <= h * 1.35:
            new["height"] = needed
            return float(int(wanted))
    return size


def _keep_headline_largest(elements: list[dict[str, Any]], source: dict[str, Any], analysis: Analysis) -> None:
    """The headline stays the largest text in the output, as it was in the
    source: any text that was smaller than the headline there and comes out
    bigger here (a short label the fitter could grow, a badge number) is
    capped at the headline's size. Text the designer made bigger than the
    headline (a date in a sticker) keeps that right."""
    src = {el["id"]: el for el in source["elements"]}
    heads = [el for el in elements if analysis.roles.get(el["id"]) == HEADLINE and el["type"] == "text"]
    if not heads:
        return
    head = heads[0]
    h_src = float(src[head["id"]]["font_size"])
    h_out = float(head["font_size"])
    for el in elements:
        if el["type"] != "text" or el is head or el["id"] not in src:
            continue
        if float(src[el["id"]]["font_size"]) < h_src and float(el["font_size"]) > h_out:
            apply_font_size(el, h_out)


def _finalize(elements: list[dict[str, Any]], analysis: Analysis, target: Box) -> None:
    for el in elements:
        role = analysis.roles.get(el["id"])
        rot = float(el.get("rotation", 0.0) or 0.0)
        # Keep important things fully on canvas; background/decoration may bleed.
        if role not in (BACKGROUND, DECORATIVE) and not rot:
            el["width"] = min(el["width"], target.w)
            el["height"] = min(el["height"], target.h)
            el["x"] = min(max(el["x"], 0.0), target.w - el["width"])
            el["y"] = min(max(el["y"], 0.0), target.h - el["height"])
        elif role not in (BACKGROUND, DECORATIVE):
            # Rotated: the box is in the element's own frame; what must stay
            # on canvas is its rotated extent (the renderer rotates about the
            # box centre), so slide it rather than clipping the frame box.
            ext = rotated_extent(Box.of(el), rot)
            nx = min(max(ext.x, 0.0), max(0.0, target.w - ext.w))
            ny = min(max(ext.y, 0.0), max(0.0, target.h - ext.h))
            el["x"] = float(el["x"]) + (nx - ext.x)
            el["y"] = float(el["y"]) + (ny - ext.y)
        for k in ("x", "y"):
            el[k] = round(float(el[k]), 2)
        for k in ("width", "height"):
            # Text boxes round *up*: a width 0.005 px smaller re-wraps a line
            # that was fitted exactly, and then the text overflows.
            v = float(el[k])
            el[k] = math.ceil(v * 100.0 - 1e-6) / 100.0 if el["type"] == "text" else round(v, 2)
        if el["type"] == "text":
            el["font_size"] = max(1.0, round(float(el["font_size"]), 2))
            if el.get("letter_spacing"):
                el["letter_spacing"] = round(float(el["letter_spacing"]), 3)
            # cr-renderer validates TextElement width/height > 0 and rejects
            # the whole design otherwise (no PNG at all). A slot squeezed to
            # nothing on a 728x90 banner must still be a 1px box.
            el["width"] = max(el["width"], 1.0)
            el["height"] = max(el["height"], 1.0)
            if not rot:
                el["x"] = min(el["x"], max(0.0, target.w - el["width"]))
                el["y"] = min(el["y"], max(0.0, target.h - el["height"]))


def _uniform_fallback(source: dict[str, Any], target: Box) -> dict[str, Any]:
    sx = target.w / source["canvas"]["width"]
    sy = target.h / source["canvas"]["height"]
    s = min(sx, sy)
    out = []
    for el in source["elements"]:
        el = copy.deepcopy(el)
        el["x"], el["y"] = el["x"] * sx, el["y"] * sy
        el["width"], el["height"] = el["width"] * s, el["height"] * s
        if el["type"] == "text":
            apply_font_size(el, max(1.0, el["font_size"] * s))
        out.append(el)
    return {"canvas": {"width": int(target.w), "height": int(target.h)}, "elements": out}


def _dump(judged: list[Judged]) -> None:
    """CHAMELEON_DUMP_DIR: write every candidate (JSON, PNG, scores) of each
    resize() call into its own numbered folder. Dev aid, off by default."""
    global _run_counter
    if not DUMP_DIR:
        return
    _run_counter += 1
    folder = Path(DUMP_DIR) / f"run{_run_counter:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        from engine.render import render_design
    except Exception:  # pragma: no cover
        render_design = None  # type: ignore
    rows = []
    for i, j in enumerate(judged):
        stem = folder / f"cand{i:02d}"
        stem.with_suffix(".json").write_text(json.dumps(j.design, indent=2))
        if render_design is not None:
            img = render_design(j.design, max_size=1200)
            if img is not None:
                img.save(stem.with_suffix(".png"))
        rows.append({"file": stem.name, **j.summary()})
    (folder / "scores.json").write_text(json.dumps(rows, indent=2))
