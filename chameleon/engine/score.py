"""Judge a materialized candidate the way the official scorer will.

Ordered like the rubric:

  1. hard fails   (each costs HARD_PENALTY, so any candidate without one beats
                   any candidate with one): a content unit off canvas, text
                   that overflows its box (measured), an image whose aspect
                   drifted > 5 %, a headline / CTA below the readable minimum
                   for this canvas, an unwanted collision between content
                   units, unreadable contrast under a headline / CTA
  2. readability  font sizes relative to what the canvas affords, few lines
                   for headline / CTA, contrast of the text colour against the
                   pixels under the text (sampled on a render without text)
                   and how busy those pixels are
  3. layout       Ngo-style balance, alignment, even spacing, white-space /
                   fill, breathing room at the edges
  4. faithfulness reading order, which edges things hug, size hierarchy, and
                   how uniformly everything scaled

The result is one comparable number (`Score.total`, higher is better) plus
a breakdown dict for debugging / the playground. Rendering is optional:
without an image the contrast terms are neutral and the breakdown says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from engine.analyze import (
    Analysis,
    BADGE,
    BODY,
    CTA,
    FINE_PRINT,
    HEADLINE,
    HERO,
    LOGO,
    SUBHEAD,
    TEXT,
    Unit,
    _anchors,
    _rgb,
)
from engine.floorplan import Metrics, ratio_family
from engine.geometry import Box, clamp
from engine.rectify import Live, _lives, unit_visible_box, unwanted_overlaps, visible_box
from engine.render import image_scale, render_design
from engine.textfit import TextMeasurer, default_measurer

HARD_PENALTY = 1000.0

WEIGHTS = {
    # readability (30)
    "read.size": 14.0,
    "read.lines": 8.0,
    "read.contrast": 8.0,
    "read.presence": 6.0,     # hero / logo keep their visual weight
    # layout quality (34)
    "layout.balance": 8.0,
    "layout.alignment": 7.0,
    "layout.spacing": 6.0,
    "layout.fill": 9.0,
    "layout.margins": 4.0,
    # faithfulness to the source (30)
    "faith.order": 12.0,
    "faith.anchors": 6.0,
    "faith.hierarchy": 8.0,
    "faith.scale": 4.0,
}

ASPECT_TOL = 0.05
CONTRAST_GOOD = 4.5          # WCAG AA for normal text
CONTRAST_FLOOR = 1.5         # below: no score; headline / CTA below 1.3 is a hard fail
CONTRAST_FAIL = 1.3
GOOD_FILL = 0.55             # content hull covering this much of the canvas is "filled"
TEXT_ROLES = (HEADLINE, SUBHEAD, BODY, CTA, BADGE, FINE_PRINT, TEXT)


@dataclass
class Score:
    total: float
    hard: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def soft(self) -> float:
        return self.total + HARD_PENALTY * len(self.hard)

    def as_dict(self) -> dict[str, Any]:
        return {"total": round(self.total, 2), "soft": round(self.soft, 2), "hard": list(self.hard),
                "breakdown": {k: round(v, 3) for k, v in self.breakdown.items()}, "notes": self.notes}


def score_design(analysis: Analysis, source: dict[str, Any], design: dict[str, Any],
                 target: Box | None = None, image=None, render: bool = True,
                 measurer: TextMeasurer | None = None) -> Score:
    """Score `design` (a resize of `source`, analysed as `analysis`). Pass a
    PIL image rendered without text to reuse a render; with `render=True`
    and no image one is rendered here (skipped silently if unavailable)."""
    m = measurer or default_measurer()
    target = target or Box(0.0, 0.0, float(design["canvas"]["width"]), float(design["canvas"]["height"]))
    elements = design["elements"]
    by_id = {el["id"]: el for el in elements}
    src_by_id = {el["id"]: el for el in source["elements"]}
    lives = _lives(analysis, by_id)
    vis = {l.unit.key: unit_visible_box(l, by_id, m) for l in lives}
    hard: list[str] = []
    bd: dict[str, float] = {}
    notes: dict[str, Any] = {}

    # ---- 1. hard fails -------------------------------------------------------
    src_ids = [el["id"] for el in source["elements"]]
    if [el["id"] for el in elements] != src_ids:
        hard.append("element ids differ from the source")
    for l in lives:
        fb = l.frame(by_id)    # drawn extent: a rotated box counts rotated
        if fb.x < -0.5 or fb.y < -0.5 or fb.right > target.w + 0.5 or fb.bottom > target.h + 0.5:
            hard.append(f"{l.unit.key} off canvas")
    met = Metrics.for_canvas(analysis.canvas, target, ratio_family(target))
    for el in elements:
        if el["type"] == "text":
            font = float(el["font_size"])
            if not m.fits(el, font, float(el["width"]), float(el["height"])):
                hard.append(f"{el['id']} text overflows its box")
            role = analysis.roles.get(el["id"])
            if role in (HEADLINE, CTA) and font < met.min_font(role) - 0.5:
                hard.append(f"{el['id']} {role} font {font:g} below readable {met.min_font(role):g}")
        elif el["type"] == "image" and el.get("fit", "contain") != "cover":
            s = src_by_id.get(el["id"])
            if s and float(s["width"]) > 0 and float(s["height"]) > 0 and float(el["height"]) > 0:
                drift = abs((float(el["width"]) / float(el["height"])) / (float(s["width"]) / float(s["height"])) - 1.0)
                if drift > ASPECT_TOL:
                    hard.append(f"{el['id']} image aspect drifted {drift:.0%}")
    overlaps = unwanted_overlaps(analysis, elements, m)
    for a, b, area in overlaps:
        hard.append(f"{a} collides with {b} ({area:.0f}px²)")

    # ---- 2. readability ------------------------------------------------------
    area_scale = math.sqrt(target.area / analysis.canvas.area)
    size_num = size_den = 0.0
    lines_num = lines_den = 0.0
    for el in elements:
        if el["type"] != "text":
            continue
        role = analysis.roles.get(el["id"], TEXT)
        imp = analysis.unit(analysis.element_unit[el["id"]]).importance if el["id"] in analysis.element_unit else 0.3
        imp = max(imp, 0.05)
        src_font = float(src_by_id[el["id"]]["font_size"]) if el["id"] in src_by_id else float(el["font_size"])
        ideal = max(src_font * area_scale, met.min_font(role))
        size_num += imp * clamp(float(el["font_size"]) / ideal, 0.0, 1.0)
        size_den += imp
        if role in (HEADLINE, CTA, SUBHEAD):
            # A headline on more than three lines, a button label on more than
            # one, reads as a defect however the source wrapped them.
            n = m.layout(el).n_lines
            allowed, slope = {HEADLINE: (3, 4.0), CTA: (1, 2.0)}.get(role, (3, 5.0))
            extra = max(0, n - allowed)
            lines_num += imp * clamp(1.0 - extra / slope, 0.0, 1.0)
            lines_den += imp
    bd["read.size"] = size_num / size_den if size_den else 1.0
    bd["read.lines"] = lines_num / lines_den if lines_den else 1.0
    bd["read.presence"] = _presence(lives, analysis.canvas, target)

    if image is None and render:
        try:
            image = render_design(design, with_text=False)
        except Exception as exc:  # the renderer is a bonus, never a dependency
            image = None
            notes["render_error"] = str(exc)
    try:
        contrast, worst = _contrast(analysis, elements, design, image, m)
    except Exception as exc:  # pragma: no cover - odd image / crop
        contrast, worst = 1.0, {}
        notes["contrast_error"] = str(exc)
        image = None
    bd["read.contrast"] = contrast
    notes["contrast"] = worst
    if image is None:
        notes["pixels"] = "no render; contrast neutral"
    for eid, ratio in worst.items():
        role = analysis.roles.get(eid)
        if role in (HEADLINE, CTA) and ratio < CONTRAST_FAIL:
            hard.append(f"{eid} unreadable contrast {ratio:.2f}")

    # ---- 3. layout quality ---------------------------------------------------
    boxes = [l.box for l in lives]
    bd["layout.balance"] = _balance(lives, target)
    bd["layout.alignment"] = _alignment(boxes, target)
    bd["layout.spacing"] = _spacing(list(vis.values()))
    bd["layout.fill"] = _fill(boxes, target)
    bd["layout.margins"] = _margins(boxes, target)

    # ---- 4. faithfulness -----------------------------------------------------
    bd["faith.order"] = _order(lives, vis)
    bd["faith.anchors"] = _anchor_keep(lives, target)
    bd["faith.hierarchy"] = _hierarchy(elements, src_by_id)
    bd["faith.scale"] = _scale_consistency(lives)

    soft = sum(WEIGHTS[k] * clamp(v, 0.0, 1.0) for k, v in bd.items())
    total = soft - HARD_PENALTY * len(hard)
    return Score(total=total, hard=hard, breakdown=bd, notes=notes)


def _presence(lives: list[Live], src_canvas: Box, target: Box) -> float:
    """Hero and logo keep their visual weight: linear size relative to the
    canvas (sqrt of the area fraction) compared with the source, hero
    counting double. 1.0 when neither lost prominence."""
    num = den = 0.0
    for l in lives:
        if l.unit.role not in (HERO, LOGO):
            continue
        w = 2.0 if l.unit.role == HERO else 1.0
        src_lin = math.sqrt(max(l.unit.box.area, 0.0) / src_canvas.area)
        if src_lin <= 0:
            continue
        now_lin = math.sqrt(max(l.box.area, 0.0) / target.area)
        num += w * clamp(now_lin / src_lin, 0.0, 1.0)
        den += w
    return num / den if den else 1.0


# ---------------------------------------------------------------------------
# readability: contrast under text


def _luminance(rgb: tuple[float, float, float]) -> float:
    def ch(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _rgba(color: Any) -> tuple[tuple[int, int, int], float]:
    rgb = _rgb(color) or (0, 0, 0)
    alpha = 1.0
    if isinstance(color, str) and "(" in color:
        parts = [p.strip() for p in color[color.find("(") + 1: color.rfind(")")].split(",")]
        if len(parts) >= 4:
            try:
                alpha = clamp(float(parts[3]), 0.0, 1.0)
            except ValueError:
                alpha = 1.0
    return rgb, alpha


def _contrast(analysis: Analysis, elements: list[dict[str, Any]], design: dict[str, Any],
              image, m: TextMeasurer) -> tuple[float, dict[str, float]]:
    """Importance-weighted contrast score in [0, 1] and the per-text ratio."""
    if image is None:
        return 1.0, {}
    try:
        from PIL import ImageStat
    except Exception:  # pragma: no cover
        return 1.0, {}
    k = image_scale(design, image)
    num = den = 0.0
    ratios: dict[str, float] = {}
    for el in elements:
        if el["type"] != "text" or not str(el.get("content", "")).strip():
            continue
        box = visible_box(el, Box.of(el), float(el["font_size"]), m)
        x0, y0 = int(max(0, math.floor(box.x * k))), int(max(0, math.floor(box.y * k)))
        x1, y1 = int(min(image.width, math.ceil(box.right * k))), int(min(image.height, math.ceil(box.bottom * k)))
        if x1 <= x0 or y1 <= y0:
            continue
        crop = image.crop((x0, y0, x1, y1))
        stat = ImageStat.Stat(crop)
        mean = tuple(float(v) for v in stat.mean[:3])
        rgb, alpha = _rgba(el.get("color"))
        blended = tuple(alpha * c + (1.0 - alpha) * b for c, b in zip(rgb, mean))
        ratio = contrast_ratio(blended, mean)
        ratios[el["id"]] = ratio
        lum_std = sum(float(v) for v in stat.stddev[:3]) / 3.0
        busy = clamp((lum_std - 20.0) / 60.0, 0.0, 1.0)
        score = clamp((ratio - CONTRAST_FLOOR) / (CONTRAST_GOOD - CONTRAST_FLOOR), 0.0, 1.0) * (1.0 - 0.5 * busy)
        imp = analysis.unit(analysis.element_unit[el["id"]]).importance if el["id"] in analysis.element_unit else 0.3
        imp = max(imp, 0.05)
        num += imp * score
        den += imp
    return (num / den if den else 1.0), ratios


# ---------------------------------------------------------------------------
# layout quality (Ngo et al. style measures, each in [0, 1])


def _balance(lives: list[Live], target: Box) -> float:
    tw = tot = 0.0
    bx = by = 0.0
    for l in lives:
        b = l.box
        w = b.area * (l.importance + 0.1)
        bx += w * (b.cx - target.w / 2.0)
        by += w * (b.cy - target.h / 2.0)
        tot += w
    if tot <= 0:
        return 1.0
    bx = abs(bx / tot) / (target.w / 2.0)
    by = abs(by / tot) / (target.h / 2.0)
    return clamp(1.0 - (bx + by) / 2.0, 0.0, 1.0)


def _clusters(values: list[float], tol: float) -> int:
    values = sorted(values)
    n = 0
    last = None
    for v in values:
        if last is None or v - last > tol:
            n += 1
            last = v
    return n


def _alignment(boxes: list[Box], target: Box) -> float:
    n = len(boxes)
    if n < 2:
        return 1.0
    tol = max(2.0, 0.01 * min(target.w, target.h))
    xs = [v for b in boxes for v in (b.x, b.cx, b.right)]
    ys = [v for b in boxes for v in (b.y, b.cy, b.bottom)]
    cx, cy = _clusters(xs, tol), _clusters(ys, tol)
    # fewest possible distinct lines is 3 per axis (everything sharing left/centre/right)
    lines = clamp(1.0 - ((cx - 3) + (cy - 3)) / max(1.0, 6.0 * n - 6.0), 0.0, 1.0)
    aligned = 0
    for i, a in enumerate(boxes):
        ok = False
        for j, b in enumerate(boxes):
            if i == j:
                continue
            if (abs(a.x - b.x) <= tol or abs(a.cx - b.cx) <= tol or abs(a.right - b.right) <= tol
                    or abs(a.y - b.y) <= tol or abs(a.cy - b.cy) <= tol or abs(a.bottom - b.bottom) <= tol):
                ok = True
                break
        aligned += ok
    return 0.5 * lines + 0.5 * aligned / n


def _spacing(vis: list[Box]) -> float:
    scores = []
    for axis in ("y", "x"):
        for chain in _chains(vis, axis):
            if len(chain) < 3:
                continue
            if axis == "y":
                gaps = [chain[i + 1].y - chain[i].bottom for i in range(len(chain) - 1)]
            else:
                gaps = [chain[i + 1].x - chain[i].right for i in range(len(chain) - 1)]
            mean = sum(gaps) / len(gaps)
            if mean <= 0:
                continue
            sd = math.sqrt(sum((g - mean) ** 2 for g in gaps) / len(gaps))
            scores.append(clamp(1.0 - sd / mean, 0.0, 1.0))
    return sum(scores) / len(scores) if scores else 1.0


def _chains(boxes: list[Box], axis: str) -> list[list[Box]]:
    order = sorted(boxes, key=lambda b: b.y if axis == "y" else b.x)
    nxt: dict[int, int] = {}
    taken: set[int] = set()
    for i, a in enumerate(order):
        best = None
        for j in range(i + 1, len(order)):
            b = order[j]
            if axis == "y":
                gap = b.y - a.bottom
                ov = min(a.right, b.right) - max(a.x, b.x)
                span = min(a.w, b.w)
            else:
                gap = b.x - a.right
                ov = min(a.bottom, b.bottom) - max(a.y, b.y)
                span = min(a.h, b.h)
            # Same row/column if they overlap at all on the other axis (a badge
            # centred on a banner row overlaps neither neighbour by half).
            if gap < -0.5 or ov < min(1.0, 0.5 * span):
                continue
            if best is None or gap < best[0]:
                best = (gap, j)
        if best is not None and best[1] not in taken:
            nxt[i] = best[1]
            taken.add(best[1])
    chains = []
    for i in range(len(order)):
        if i in taken:
            continue
        chain = [i]
        while chain[-1] in nxt:
            chain.append(nxt[chain[-1]])
        if len(chain) >= 2:
            chains.append([order[j] for j in chain])
    return chains


def _fill(boxes: list[Box], target: Box) -> float:
    if not boxes:
        return 0.0
    hull = Box.union(boxes)
    hull = Box(max(0.0, hull.x), max(0.0, hull.y), min(target.w, hull.right) - max(0.0, hull.x),
               min(target.h, hull.bottom) - max(0.0, hull.y))
    fill = clamp(hull.area / target.area / GOOD_FILL, 0.0, 1.0)
    density = sum(b.area for b in boxes) / target.area
    crowded = clamp((density - 0.7) / 0.3, 0.0, 1.0)
    return fill * (1.0 - 0.5 * crowded)


def _margins(boxes: list[Box], target: Box) -> float:
    if not boxes:
        return 1.0
    mn = min(target.w, target.h)
    d = min(min(b.x, b.y, target.w - b.right, target.h - b.bottom) for b in boxes)
    return clamp(d / (0.03 * mn), 0.0, 1.0)


# ---------------------------------------------------------------------------
# faithfulness to the source


def reading_order(keys_boxes: list[tuple[str, Box]]) -> dict[str, int]:
    """Reading sequence of a laid-out design: rows are groups of boxes that
    overlap vertically (transitively, so a tall hero ties a banner row
    together), ordered top to bottom; inside a row, boxes that overlap
    horizontally form a stack (a headline over its subhead) ordered top to
    bottom, and stacks run left to right."""
    n = len(keys_boxes)
    boxes = [b for _, b in keys_boxes]

    def groups(idx: list[int], same) -> list[list[int]]:
        parent = {i: i for i in idx}

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                if same(boxes[i], boxes[j]):
                    parent[find(i)] = find(j)
        out: dict[int, list[int]] = {}
        for i in idx:
            out.setdefault(find(i), []).append(i)
        return list(out.values())

    def y_overlap(a: Box, b: Box) -> bool:
        return min(a.bottom, b.bottom) - max(a.y, b.y) >= 1.0

    def x_overlap(a: Box, b: Box) -> bool:
        return min(a.right, b.right) - max(a.x, b.x) >= 0.5 * max(1.0, min(a.w, b.w))

    order: dict[str, int] = {}
    pos = 0
    rows = groups(list(range(n)), y_overlap)
    rows.sort(key=lambda g: sum(boxes[i].cy for i in g) / len(g))
    for row in rows:
        stacks = groups(row, x_overlap)
        stacks.sort(key=lambda g: sum(boxes[i].cx for i in g) / len(g))
        for stack in stacks:
            for i in sorted(stack, key=lambda i: (boxes[i].cy, boxes[i].cx)):
                order[keys_boxes[i][0]] = pos
                pos += 1
    return order


def _order(lives: list[Live], vis: dict[str, Box]) -> float:
    if len(lives) < 2:
        return 1.0
    now = reading_order([(l.unit.key, vis[l.unit.key]) for l in lives])
    conc = disc = 0
    for i, a in enumerate(lives):
        for b in lives[i + 1:]:
            s = (a.unit.reading_index - b.unit.reading_index)
            t = (now[a.unit.key] - now[b.unit.key])
            if s * t > 0:
                conc += 1
            elif s * t < 0:
                disc += 1
    pairs = conc + disc
    if pairs == 0:
        return 1.0
    tau = (conc - disc) / pairs
    return (tau + 1.0) / 2.0


def _anchor_keep(lives: list[Live], target: Box) -> float:
    num = den = 0.0
    for l in lives:
        ax, ay = _anchors(l.box, target)
        u = l.unit
        w = max(u.importance, 0.05)
        if u.anchor_x != "fluid":
            den += w
            num += w * (ax == u.anchor_x)
        if u.anchor_y != "fluid":
            den += w
            num += w * (ay == u.anchor_y)
    return num / den if den else 1.0


def _hierarchy(elements: list[dict[str, Any]], src_by_id: dict[str, dict[str, Any]]) -> float:
    texts = [el for el in elements if el["type"] == "text" and el["id"] in src_by_id]
    images = [el for el in elements if el["type"] == "image" and el["id"] in src_by_id]
    ok = tot = 0
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            sa, sb = float(src_by_id[a["id"]]["font_size"]), float(src_by_id[b["id"]]["font_size"])
            if sa >= 1.1 * sb:
                tot += 1
                ok += float(a["font_size"]) >= float(b["font_size"]) - 0.5
            elif sb >= 1.1 * sa:
                tot += 1
                ok += float(b["font_size"]) >= float(a["font_size"]) - 0.5
    for i, a in enumerate(images):
        for b in images[i + 1:]:
            sa, sb = Box.of(src_by_id[a["id"]]).area, Box.of(src_by_id[b["id"]]).area
            if sa >= 1.5 * sb:
                tot += 1
                ok += Box.of(a).area >= Box.of(b).area
            elif sb >= 1.5 * sa:
                tot += 1
                ok += Box.of(b).area >= Box.of(a).area
    return ok / tot if tot else 1.0


def _scale_consistency(lives: list[Live]) -> float:
    scales = []
    for l in lives:
        sb = l.unit.box
        if sb.area <= 0:
            continue
        scales.append(math.sqrt(l.box.area / sb.area))
    if len(scales) < 2:
        return 1.0
    mean = sum(scales) / len(scales)
    if mean <= 0:
        return 0.0
    sd = math.sqrt(sum((s - mean) ** 2 for s in scales) / len(scales))
    return 1.0 / (1.0 + 2.0 * sd / mean)
