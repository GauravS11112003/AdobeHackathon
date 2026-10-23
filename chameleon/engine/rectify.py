"""Deterministic defect fixer, run on every candidate before it is judged.

Works on a materialized design (elements with final boxes and font sizes)
at the level of the analyzer's units, so a group always moves and scales as
one piece and its member insets stay exactly proportional. Each pass:

  1. images keep their aspect ratio (contain)
  2. groups only ever move or scale as one piece, so member insets stay
     exactly as the strategy laid them out (uniform, or a button squeezed
     around its label by the floor plan)
  3. unwanted overlaps between content units are pushed apart (or the less
     important unit shrinks when nothing can move): overlaps that already
     existed in the source, members of one group, and anything touching the
     background / decoration are left alone
  4. every content unit is fully on canvas with a small margin
  5. near-aligned edges and centres snap to a shared line
  6. nearly even gaps in a stack or a row become exactly even

Overlaps are judged on *visible* boxes: a text element counts as its ink
(the measured wrapped lines, aligned like the renderer aligns them), a
rotated element as the axis-aligned extent of its rotated box. Passes
repeat until nothing changes or `MAX_PASSES` is reached, so it always
terminates. Fonts shrink with their unit and are re-fitted so they still
fit their boxes; `content` / `font_family` are never touched.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from engine.analyze import Analysis, Unit
from engine.geometry import Box, clamp
from engine.textfit import TextMeasurer, apply_font_size, default_measurer

MAX_PASSES = 6
EPS = 0.01
OVERLAP_TOL = 0.015         # a pair may overlap this much more (fraction of the smaller box) than in the source
MIN_SHRINK = 0.4            # never shrink a unit below this fraction to solve an overlap
MARGIN_FRAC = 0.015         # on-canvas margin for content, as a fraction of min(W, H)
SNAP_FRAC = 0.008           # snap tolerance, fraction of min(W, H)
GAP_FRAC = 0.01             # minimum visible gap between pushed-apart units
EVEN_GAP_RATIO = 1.6        # gaps closer than this ratio (max/min) are made equal


@dataclass
class Live:
    """A unit's current geometry while the rectifier works."""

    unit: Unit
    boxes: dict[str, Box]                 # element id -> current box
    fonts: dict[str, float] = field(default_factory=dict)
    changed: bool = False
    shrunk: float = 1.0                   # cumulative scale applied to solve overlaps

    @property
    def box(self) -> Box:
        return Box.union(self.boxes.values())

    def frame(self, elements: dict[str, dict[str, Any]]) -> Box:
        """Axis-aligned extent of the unit as drawn: rotated members count
        with their rotated box (the renderer rotates about the box centre)."""
        return Box.union(rotated_extent(b, float(elements[eid].get("rotation", 0.0) or 0.0))
                         for eid, b in self.boxes.items())

    @property
    def importance(self) -> float:
        return self.unit.importance


# ---------------------------------------------------------------------------
# visible boxes


def rotated_extent(box: Box, rotation: float) -> Box:
    """Axis-aligned extent of `box` rotated about its centre (what the
    renderer draws for a rotated element)."""
    if not rotation:
        return box
    a = math.radians(rotation)
    w = box.w * abs(math.cos(a)) + box.h * abs(math.sin(a))
    h = box.w * abs(math.sin(a)) + box.h * abs(math.cos(a))
    return Box(box.cx - w / 2.0, box.cy - h / 2.0, w, h)


def ink_box(el: dict[str, Any], box: Box, font_size: float, m: TextMeasurer) -> Box:
    """Where the glyphs of a text element land: the painted extent of the
    wrapped lines (caps to the last baseline / descender), aligned inside
    the box like cr-renderer does. See `TextMeasurer.painted`."""
    p = m.painted(el, font_size, max(box.w, 1.0))
    ink = Box(box.x + p.x, box.y + p.top, max(p.w, 1.0), max(p.h, 1.0))
    return rotated_extent(ink, float(el.get("rotation", 0.0) or 0.0))


def visible_box(el: dict[str, Any], box: Box, font_size: float | None, m: TextMeasurer) -> Box:
    if el["type"] == "text":
        return ink_box(el, box, font_size if font_size is not None else float(el["font_size"]), m)
    return rotated_extent(box, float(el.get("rotation", 0.0) or 0.0))


def unit_visible_box(live: Live, elements: dict[str, dict[str, Any]], m: TextMeasurer) -> Box:
    return Box.union(visible_box(elements[eid], b, live.fonts.get(eid), m) for eid, b in live.boxes.items())


def unit_visible_parts(live: Live, elements: dict[str, dict[str, Any]], m: TextMeasurer) -> list[Box]:
    """Visible boxes used for collision tests: one per sibling of a row unit
    (the badges of a row pinned to two corners do not "overlap" what lies
    between them), one per element of a host unit (a heading and the bar
    above it do not cover the gap between them), otherwise the unit's one
    visible box (a pill with its label is solid)."""
    if live.unit.is_row:
        out = []
        for part in live.unit.parts:
            ids = [i for i in part.ids if i in live.boxes]
            if ids:
                out.append(Box.union(visible_box(elements[i], live.boxes[i], live.fonts.get(i), m) for i in ids))
        if out:
            return out
    if live.unit.kind == "host":
        return [visible_box(elements[i], b, live.fonts.get(i), m) for i, b in live.boxes.items()]
    return [unit_visible_box(live, elements, m)]


def parts_overlap(a: list[Box], b: list[Box], tol: float = 1.0) -> bool:
    return any(x.overlaps(y, tol=tol) for x in a for y in b)


def parts_overlap_fraction(a: list[Box], b: list[Box]) -> float:
    """Largest overlap fraction over the part pairs (fraction of the smaller part)."""
    return max((overlap_fraction(x, y) for x in a for y in b), default=0.0)


def parts_intersection(a: list[Box], b: list[Box]) -> float:
    return sum(x.intersection_area(y) for x in a for y in b)


# ---------------------------------------------------------------------------
# entry point


def rectify(analysis: Analysis, elements: list[dict[str, Any]], target: Box,
            measurer: TextMeasurer | None = None, passes: int = MAX_PASSES) -> list[dict[str, Any]]:
    """Return a corrected copy of `elements` (same ids, same order)."""
    m = measurer or default_measurer()
    elements = copy.deepcopy(elements)
    by_id = {el["id"]: el for el in elements}
    src_by_id = {eid: el for el in elements for eid in [el["id"]]}  # same dicts; fonts come from here
    lives = _lives(analysis, by_id)
    r = _Rectifier(analysis, by_id, lives, target, m)
    for _ in range(max(1, passes)):
        changed = r.run_pass()
        if not changed:
            break
    r.write_back()
    return elements


def _lives(analysis: Analysis, by_id: dict[str, dict[str, Any]]) -> list[Live]:
    out = []
    for u in analysis.units:
        if not u.is_content:
            continue
        boxes = {eid: Box.of(by_id[eid]) for eid in u.ids if eid in by_id}
        if not boxes:
            continue
        fonts = {eid: float(by_id[eid]["font_size"]) for eid in boxes if by_id[eid]["type"] == "text"}
        out.append(Live(u, boxes, fonts))
    return out


class _Rectifier:
    def __init__(self, analysis: Analysis, by_id: dict[str, dict[str, Any]], lives: list[Live],
                 target: Box, m: TextMeasurer):
        self.analysis = analysis
        self.by_id = by_id
        self.lives = sorted(lives, key=lambda l: l.unit.reading_index)
        self.target = target
        self.m = m
        mn = min(target.w, target.h)
        self.margin = clamp(MARGIN_FRAC * mn, 1.0, 16.0)
        self.snap_tol = clamp(SNAP_FRAC * mn, 1.0, 6.0)
        self.gap = clamp(GAP_FRAC * mn, 2.0, 12.0)
        # How much each pair overlapped in the source (visible boxes): a
        # pair may keep that much overlap (plus OVERLAP_TOL); more is a defect.
        self.src_frac = source_overlap_fractions(analysis, m)
        self._vis: dict[str, Box] = {}
        self._parts: dict[str, list[Box]] = {}
        self.src_fonts = {eid: float(el["font_size"]) for eid, el in by_id.items() if el["type"] == "text"}

    # -- geometry helpers -----------------------------------------------------

    def frame(self, l: Live) -> Box:
        return l.frame(self.by_id)

    def vis(self, l: Live) -> Box:
        b = self._vis.get(l.unit.key)
        if b is None:
            b = unit_visible_box(l, self.by_id, self.m)
            self._vis[l.unit.key] = b
        return b

    def parts(self, l: Live) -> list[Box]:
        p = self._parts.get(l.unit.key)
        if p is None:
            p = unit_visible_parts(l, self.by_id, self.m)
            self._parts[l.unit.key] = p
        return p

    def invalidate(self, l: Live) -> None:
        self._vis.pop(l.unit.key, None)
        self._parts.pop(l.unit.key, None)
        l.changed = True

    def move(self, l: Live, dx: float, dy: float) -> None:
        if abs(dx) < EPS and abs(dy) < EPS:
            return
        for eid, b in l.boxes.items():
            l.boxes[eid] = Box(b.x + dx, b.y + dy, b.w, b.h)
        self.invalidate(l)

    def scale(self, l: Live, f: float, ax: float, ay: float) -> None:
        """Scale the whole unit by `f` about the point (ax, ay); fonts follow."""
        if abs(f - 1.0) < 1e-6:
            return
        for eid, b in l.boxes.items():
            l.boxes[eid] = Box(ax + (b.x - ax) * f, ay + (b.y - ay) * f, b.w * f, b.h * f)
            if eid in l.fonts:
                l.fonts[eid] = max(1.0, l.fonts[eid] * f)
        self.refit_fonts(l)
        self.invalidate(l)

    def refit_fonts(self, l: Live) -> None:
        for eid, font in list(l.fonts.items()):
            el = self.by_id[eid]
            b = l.boxes[eid]
            size = float(int(font)) if font >= 1.0 else font
            if not self.m.fits(el, size, b.w, b.h):
                size = self.m.fit_font_size(el, b.w, b.h, size, 1.0)
            l.fonts[eid] = size

    def allowed_pair(self, a: Live, b: Live) -> bool:
        """Did the pair overlap in the source? Such pairs are only separated
        when their overlap grew by more than OVERLAP_TOL (see `collides`)."""
        return self.src_frac.get(_pair_key(a.unit.key, b.unit.key), 0.0) > 0.0

    def excess(self, a: Live, b: Live, pa: list[Box] | None = None, pb: list[Box] | None = None) -> float:
        """Overlap fraction now minus what the source had (negative: fine)."""
        pa = pa if pa is not None else self.parts(a)
        pb = pb if pb is not None else self.parts(b)
        return parts_overlap_fraction(pa, pb) - self.src_frac.get(_pair_key(a.unit.key, b.unit.key), 0.0)

    def collides(self, l: Live, box: Box | None = None, ignore: Iterable[str] = ()) -> bool:
        """Would `l` (at `box`, default its current visible box) overlap any
        unit it must not overlap?"""
        if box is not None:
            # a hypothetical position: shift this unit's parts by the same offset
            cur = self.vis(l)
            dx, dy = box.x - cur.x, box.y - cur.y
            mine = [Box(p.x + dx, p.y + dy, p.w, p.h) for p in self.parts(l)]
        else:
            mine = self.parts(l)
        skip = set(ignore)
        for o in self.lives:
            if o is l or o.unit.key in skip:
                continue
            if self.allowed_pair(l, o):
                if self.excess(l, o, mine, self.parts(o)) > OVERLAP_TOL:
                    return True
                continue
            if parts_overlap(mine, self.parts(o), tol=1.0):
                return True
        return False

    def on_canvas(self, box: Box) -> bool:
        t, mg = self.target, self.margin
        return box.x >= mg - EPS and box.y >= mg - EPS and box.right <= t.w - mg + EPS and box.bottom <= t.h - mg + EPS

    def inside_canvas_tol(self, box: Box) -> bool:
        t = self.target
        return box.x >= -0.5 and box.y >= -0.5 and box.right <= t.w + 0.5 and box.bottom <= t.h + 0.5

    # -- passes -----------------------------------------------------------------

    def run_pass(self) -> bool:
        for l in self.lives:
            l.changed = False
        self.fix_aspect()
        self.fix_overlaps()
        self.fix_on_canvas()
        self.snap()
        self.even_gaps()
        return any(l.changed for l in self.lives)

    def fix_aspect(self) -> None:
        for l in self.lives:
            if l.unit.is_group:
                continue   # uniform scaling of the group keeps member aspects
            for eid, b in list(l.boxes.items()):
                el = self.by_id[eid]
                if el["type"] != "image" or el.get("fit", "contain") == "cover":
                    continue
                sb = l.unit.members.get(eid)
                if sb is None or sb.w <= 0 or sb.h <= 0 or b.w <= 0:
                    continue
                aspect = sb.w / sb.h
                want_h = b.w / aspect
                if abs(want_h - b.h) > 0.5:
                    l.boxes[eid] = Box(b.x, b.cy - want_h / 2.0, b.w, want_h)
                    self.invalidate(l)

    def fix_overlaps(self) -> None:
        n = len(self.lives)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = self.lives[i], self.lives[j]
                pa, pb = self.parts(a), self.parts(b)
                if self.allowed_pair(a, b):
                    # overlapped by design: only a clearly bigger overlap is a defect
                    if self.excess(a, b, pa, pb) > OVERLAP_TOL:
                        self._separate(a, b)
                    continue
                if not parts_overlap(pa, pb, tol=-self.gap):    # closer than the minimum gap
                    continue
                self._separate(a, b)

    def _separate(self, a: Live, b: Live) -> None:
        va, vb = self.vis(a), self.vis(b)
        g = self.gap
        # Candidate moves: (unit, dx, dy). b is later in reading order.
        moves = [
            (b, 0.0, va.bottom + g - vb.y),        # b down
            (b, va.right + g - vb.x, 0.0),         # b right
            (b, 0.0, -(vb.bottom + g - va.y)),     # b up
            (b, -(vb.right + g - va.x), 0.0),      # b left
            (a, 0.0, -(va.bottom + g - vb.y)),     # a up
            (a, -(va.right + g - vb.x), 0.0),      # a left
            (a, 0.0, vb.bottom + g - va.y),        # a down
            (a, vb.right + g - va.x, 0.0),         # a right
        ]
        sa, sb = a.unit.box, b.unit.box
        vertical_src = sa.bottom <= sb.y + 1.0 or sb.bottom <= sa.y + 1.0
        horizontal_src = sa.right <= sb.x + 1.0 or sb.right <= sa.x + 1.0
        best = None
        for l, dx, dy in moves:
            dist = abs(dx) + abs(dy)
            if dist < EPS:
                continue
            cost = dist
            if dy and vertical_src and not horizontal_src:
                cost *= 0.6          # keep the source's above/below relation
            if dx and horizontal_src and not vertical_src:
                cost *= 0.6
            if l is a:
                cost *= 1.25         # prefer moving the later / less important piece
            if l.importance > (b if l is a else a).importance + 1e-9:
                cost *= 1.5
            nb = self.vis(l)
            nb = Box(nb.x + dx, nb.y + dy, nb.w, nb.h)
            full = self.frame(l)
            full = Box(full.x + dx, full.y + dy, full.w, full.h)
            if not self.on_canvas(full):
                continue
            if self.collides(l, nb, ignore=[(b if l is a else a).unit.key]):
                continue
            if best is None or cost < best[0]:
                best = (cost, l, dx, dy)
        if best is not None:
            _, l, dx, dy = best
            self.move(l, dx, dy)
            return
        # Nothing can move: shrink the less important (or later) unit away from
        # the other, but never below MIN_SHRINK of its materialized size in
        # total (one pass per round could otherwise shrink it to nothing).
        victim, other = (b, a)
        if a.importance < b.importance - 1e-9:
            victim, other = (a, b)
        vv, vo = self.vis(victim), self.vis(other)
        options = []
        # vertical shrink: anchor at the far edge from `other`
        if vv.cy >= vo.cy:
            need = vo.bottom + g - vv.y
            options.append((1.0 - need / max(vv.h, 1.0), victim.box.x, victim.box.bottom, "v"))
        else:
            need = vv.bottom + g - vo.y
            options.append((1.0 - need / max(vv.h, 1.0), victim.box.x, victim.box.y, "v"))
        if vv.cx >= vo.cx:
            need = vo.right + g - vv.x
            options.append((1.0 - need / max(vv.w, 1.0), victim.box.right, victim.box.y, "h"))
        else:
            need = vv.right + g - vo.x
            options.append((1.0 - need / max(vv.w, 1.0), victim.box.x, victim.box.y, "h"))
        options = [o for o in options if o[0] * victim.shrunk >= MIN_SHRINK]
        if not options:
            return
        f, ax, ay, _ = max(options, key=lambda o: o[0])
        # Anchor so the far edge stays put: scaling about (ax, ay) keeps that corner fixed.
        fb = victim.box
        ax = fb.right if ax >= fb.right - EPS else fb.x
        ay = fb.bottom if ay >= fb.bottom - EPS else fb.y
        f = min(f, 0.98)
        victim.shrunk *= f
        self.scale(victim, f, ax, ay)

    def fix_on_canvas(self) -> None:
        t, mg = self.target, self.margin
        aw, ah = t.w - 2 * mg, t.h - 2 * mg
        for l in self.lives:
            fb = self.frame(l)
            if fb.w > aw + EPS or fb.h > ah + EPS:
                f = min(aw / max(fb.w, 1e-6), ah / max(fb.h, 1e-6))
                self.scale(l, f, fb.cx, fb.cy)
                fb = self.frame(l)
            dx = dy = 0.0
            if fb.x < mg:
                dx = mg - fb.x
            elif fb.right > t.w - mg:
                dx = t.w - mg - fb.right
            if fb.y < mg:
                dy = mg - fb.y
            elif fb.bottom > t.h - mg:
                dy = t.h - mg - fb.bottom
            if abs(dx) > EPS or abs(dy) > EPS:
                self.move(l, dx, dy)

    def snap(self) -> None:
        tol = self.snap_tol
        order = sorted(self.lives, key=lambda l: (-l.importance, l.unit.reading_index))
        for idx, l in enumerate(order):
            refs = order[:idx]
            if not refs:
                continue
            fb = self.frame(l)
            for axis in ("x", "y"):
                best = None
                for r in refs:
                    rb = self.frame(r)
                    if axis == "x":
                        pairs = ((fb.cx, rb.cx), (fb.x, rb.x), (fb.right, rb.right))
                    else:
                        pairs = ((fb.cy, rb.cy), (fb.y, rb.y), (fb.bottom, rb.bottom))
                    for mine, theirs in pairs:
                        d = theirs - mine
                        if EPS < abs(d) <= tol and (best is None or abs(d) < abs(best)):
                            best = d
                if best is None:
                    continue
                dx, dy = (best, 0.0) if axis == "x" else (0.0, best)
                nb = self.vis(l)
                nb = Box(nb.x + dx, nb.y + dy, nb.w, nb.h)
                full = Box(fb.x + dx, fb.y + dy, fb.w, fb.h)
                if self.on_canvas(full) and not self.collides(l, nb):
                    self.move(l, dx, dy)
                    fb = self.frame(l)

    def even_gaps(self) -> None:
        for axis in ("y", "x"):
            for chain in self._chains(axis):
                if len(chain) < 3:
                    continue
                boxes = [self.vis(l) for l in chain]
                if axis == "y":
                    gaps = [boxes[i + 1].y - boxes[i].bottom for i in range(len(boxes) - 1)]
                else:
                    gaps = [boxes[i + 1].x - boxes[i].right for i in range(len(boxes) - 1)]
                lo, hi = min(gaps), max(gaps)
                if lo < 0.0 or hi - lo <= self.snap_tol or hi > EVEN_GAP_RATIO * max(lo, 1.0):
                    continue
                mean = sum(gaps) / len(gaps)
                # Shift the intermediates so every gap equals the mean (first and last stay).
                pos = boxes[0].bottom if axis == "y" else boxes[0].right
                planned = []
                ok = True
                for l, vb in zip(chain[1:-1], boxes[1:-1]):
                    want = pos + mean
                    d = want - (vb.y if axis == "y" else vb.x)
                    nb = Box(vb.x + (d if axis == "x" else 0.0), vb.y + (d if axis == "y" else 0.0), vb.w, vb.h)
                    full = self.frame(l)
                    full = Box(full.x + (d if axis == "x" else 0.0), full.y + (d if axis == "y" else 0.0), full.w, full.h)
                    if not self.on_canvas(full) or self.collides(l, nb, ignore=[c.unit.key for c in chain]):
                        ok = False
                        break
                    planned.append((l, d))
                    pos = nb.bottom if axis == "y" else nb.right
                if not ok:
                    continue
                for l, d in planned:
                    if axis == "y":
                        self.move(l, 0.0, d)
                    else:
                        self.move(l, d, 0.0)

    def _chains(self, axis: str) -> list[list[Live]]:
        """Runs of units that follow each other along `axis` with substantial
        overlap on the other axis (a stack for "y", a row for "x")."""
        lives = sorted(self.lives, key=lambda l: self.vis(l).y if axis == "y" else self.vis(l).x)
        nxt: dict[str, Live] = {}
        prev: set[str] = set()
        for i, a in enumerate(lives):
            va = self.vis(a)
            best = None
            for b in lives[i + 1:]:
                vb = self.vis(b)
                if axis == "y":
                    gap = vb.y - va.bottom
                    ov = min(va.right, vb.right) - max(va.x, vb.x)
                    span = min(va.w, vb.w)
                else:
                    gap = vb.x - va.right
                    ov = min(va.bottom, vb.bottom) - max(va.y, vb.y)
                    span = min(va.h, vb.h)
                if gap < -0.5 or ov < min(1.0, 0.5 * span):
                    continue
                if best is None or gap < best[0]:
                    best = (gap, b)
            if best is not None and best[1].unit.key not in prev:
                nxt[a.unit.key] = best[1]
                prev.add(best[1].unit.key)
        chains = []
        for a in lives:
            if a.unit.key in prev:
                continue
            chain = [a]
            while chain[-1].unit.key in nxt:
                chain.append(nxt[chain[-1].unit.key])
            if len(chain) >= 2:
                chains.append(chain)
        return chains

    # -- output -------------------------------------------------------------------

    def write_back(self) -> None:
        for l in self.lives:
            for eid, b in l.boxes.items():
                el = self.by_id[eid]
                el["x"], el["y"], el["width"], el["height"] = b.x, b.y, b.w, b.h
                if eid in l.fonts:
                    apply_font_size(el, l.fonts[eid])


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def overlap_fraction(a: Box, b: Box) -> float:
    """Shared area as a fraction of the smaller box (0 = disjoint)."""
    small = min(a.area, b.area)
    if small <= 0:
        return 0.0
    return a.intersection_area(b) / small


def source_overlap_fractions(analysis: Analysis, measurer: TextMeasurer | None = None) -> dict[tuple[str, str], float]:
    """Overlap fraction of every pair of content units in the *source*
    (visible boxes: painted text, rotated extents), cached on the analysis.
    What the designer overlapped on purpose is not a defect when kept."""
    m = measurer or default_measurer()
    if analysis.source_visible is None:
        by_id = analysis.source_elements
        vis: dict[str, list[Box]] = {}
        for u in analysis.units:
            if not u.is_content:
                continue
            boxes = {eid: u.members[eid] for eid in u.ids if eid in by_id}
            if not boxes:
                continue
            live = Live(u, boxes, {eid: float(by_id[eid]["font_size"]) for eid in boxes if by_id[eid]["type"] == "text"})
            try:
                vis[u.key] = unit_visible_parts(live, by_id, m)
            except Exception:  # pragma: no cover - odd source element
                vis[u.key] = [u.box]
        analysis.source_visible = vis   # type: ignore[assignment]
    vis = analysis.source_visible
    out: dict[tuple[str, str], float] = {}
    keys = list(vis)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            f = parts_overlap_fraction(vis[a], vis[b])
            if f > 0.0:
                out[_pair_key(a, b)] = f
    return out


def unwanted_overlaps(analysis: Analysis, elements: list[dict[str, Any]],
                      measurer: TextMeasurer | None = None, tol: float = OVERLAP_TOL) -> list[tuple[str, str, float]]:
    """Pairs of content units whose visible boxes overlap in `elements` by
    more than they did in the source (by more than `tol` of the smaller box,
    so a graze is not a collision and a sticker that sat on the photo may
    still sit on it), with the overlap area. Shared by the scorer, the
    rectifier, the eval metrics and the tests."""
    m = measurer or default_measurer()
    by_id = {el["id"]: el for el in elements}
    lives = _lives(analysis, by_id)
    vis = {l.unit.key: unit_visible_parts(l, by_id, m) for l in lives}
    src = source_overlap_fractions(analysis, m)
    out = []
    for i, a in enumerate(lives):
        for b in lives[i + 1:]:
            pa, pb = vis[a.unit.key], vis[b.unit.key]
            if not parts_overlap(pa, pb, tol=1.0):
                continue
            f = parts_overlap_fraction(pa, pb) - src.get(_pair_key(a.unit.key, b.unit.key), 0.0)
            if f > tol:
                out.append((a.unit.key, b.unit.key, parts_intersection(pa, pb)))
    return out
