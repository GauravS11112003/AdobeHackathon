"""Floor plans: archetype layouts for big canvas shape changes.

When the target canvas has a very different shape from the source (ratio
change above `resize.SMALL_CHANGE_MAX`), sliding things toward their
anchors leaves a tiny shrunken poster floating in the new canvas. Instead
we pick a *floor plan* by the target's ratio family and pour the content
units from `analyze()` into its slots:

  tall   (w/h <= 0.8)   column stack: logo, hero, headline, subhead, body,
                        badges row, CTA, fine print at the bottom
  square (0.8 - 1.25)   the same centred stack, slightly tighter
  wide   (1.25 - 3)     hero on one side, a column with logo, headline,
                        subhead, badges, CTA and fine print on the other
  banner (> 3)          a single row: logo | hero | text column | badges | CTA

Every slot's size is a function of one global shrink factor `k` in [0, 1]
(1 = the comfortable size for this canvas, 0 = the readable minimum). Items
shrink at different speeds (`prio`): the headline, logo, CTA and hero are
the last to give up room, subheads sooner, badges and legal copy first.
A binary search finds the largest `k` at which everything fits; whatever
room is left goes to spacing. Text is measured with the real brand fonts
(`TextMeasurer`) so the font sizes we emit really fit their boxes, images
scale uniformly, and groups move as one piece with their members' offsets
scaled (`relayout._place_members`).

Nothing here looks at element ids: roles come from the analyzer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from engine.analyze import (
    Analysis,
    BACKGROUND,
    BADGE,
    BODY,
    CTA,
    DECORATIVE,
    FINE_PRINT,
    HEADLINE,
    HERO,
    LOGO,
    SUBHEAD,
    TEXT,
    Unit,
)
from engine.geometry import Box, clamp
from engine.relayout import Placement, _cover_box, _map_decorative, _place_members, place_panels
from engine.textfit import TextMeasurer, default_measurer

TALL = "tall"
SQUARE = "square"
WIDE = "wide"
BANNER = "banner"

TALL_MAX_RATIO = 0.8
SQUARE_MAX_RATIO = 1.25
WIDE_MAX_RATIO = 3.0

SHORT_CANVAS = 300.0       # px tall; below this minimum font sizes scale with the height
K_SEARCH_STEPS = 14
VERTICAL_MIN_DEG = 60.0    # a text rotated at least this far is fitted in its own (vertical) frame

# Shrink speeds: size(k) = ideal * k ** prio (never below the item's floor).
PRIO_PRIMARY = 1.0         # headline, logo, CTA
PRIO_HERO = 1.3
PRIO_SECONDARY = 1.6       # subhead, body
PRIO_MINOR = 2.5           # badges, secondary images, fine print

# Banner headline wrapping: (max lines, smallest shrink factor k at which that
# many lines is still preferred over wrapping once more).
BANNER_LINE_POLICY = ((1, 0.75), (2, 0.45), (3, 0.0), (4, 0.0), (6, 0.0))

# Floors relative to the target canvas (gk7494's figures): fonts as a share
# of the long side, brand pieces as a share of the short side (their larger
# dimension), so a logo or a hero never vanishes on a big canvas.
FONT_FLOOR_LONG = 0.0085
FONT_FLOOR_MULT = {FINE_PRINT: 0.7, BADGE: 0.8}
LOGO_FLOOR_FRAC = 0.14
HERO_FLOOR_FRAC = 0.30
STAMP_FLOOR_FRAC = 0.08
CHIP_MAX_SHARE = 0.18       # a chip's ideal height is at most this share of the canvas height


@dataclass(frozen=True)
class PlanOptions:
    """Knobs that turn one floor plan into several candidates (see
    engine/candidates.py). All default to the v1 behaviour.

    hero_side   auto | left | right | stack
                where the hero goes: on the side it had in the source, forced
                to one side (a square canvas then uses the wide plan), or inside
                the column (a wide canvas then uses the column plan). Banners:
                left = right after the logo, right = at the far end of the row.
    spacing     multiplier on the canvas margin and the gap (0.75 tight, 1.3 loose)
    scale_bias  multiplier on the ideal (k = 1) sizes of everything
    chips       row | corner | beside_cta
                badges & stickers: a row in the column (v1), pinned to the
                canvas corners they came from, or in one row with the CTA
    text_flow   stacked | inline
                banner text: headline above the rest (v1) or beside it
    """

    hero_side: str = "auto"
    spacing: float = 1.0
    scale_bias: float = 1.0
    chips: str = "row"
    text_flow: str = "stacked"

    @property
    def name(self) -> str:
        """Only the knobs that differ from the defaults."""
        parts = []
        for f in ("hero_side", "chips", "text_flow", "spacing", "scale_bias"):
            v, d = getattr(self, f), getattr(DEFAULT_OPTIONS, f)
            if v != d:
                parts.append(f"{f.replace('_side', '').replace('_flow', '').replace('_bias', '')}={v:g}" if isinstance(v, float) else f"{f.replace('_side', '').replace('_flow', '')}={v}")
        return ", ".join(parts) or "default"


DEFAULT_OPTIONS = PlanOptions()


def ratio_family(target: Box) -> str:
    r = target.w / target.h
    if r <= TALL_MAX_RATIO:
        return TALL
    if r <= SQUARE_MAX_RATIO:
        return SQUARE
    if r <= WIDE_MAX_RATIO:
        return WIDE
    return BANNER


# ---------------------------------------------------------------------------
# canvas metrics


@dataclass
class Metrics:
    target: Box
    margin: float
    gap: float
    cap_scale: float      # font multiplier at k = 1 (relative to the source font_size)
    short: bool           # short canvas: minimum font sizes scale with the height

    @classmethod
    def for_canvas(cls, src: Box, target: Box, family: str, spacing: float = 1.0,
                   scale_bias: float = 1.0) -> "Metrics":
        mn = min(target.w, target.h)
        margin = clamp(0.05 * mn * spacing, 4.0, 60.0)
        gap = clamp(0.035 * mn * spacing, 4.0, 48.0)
        cap = clamp(math.sqrt(target.area / src.area), 0.2, 2.5)
        if family in (WIDE, BANNER):
            cap *= 1.15   # horizontal layouts give each line more room
        cap *= scale_bias
        return cls(target=target, margin=margin, gap=gap, cap_scale=cap, short=target.h < SHORT_CANVAS)

    def min_font(self, role: str) -> float:
        """Smallest font size we are willing to emit for a role: an absolute
        floor for normal canvases (scaled with the height below SHORT_CANVAS)
        and, on big canvases, a floor relative to the long side so that a
        12 px line on a 1920 px story does not count as readable."""
        h = self.target.h
        if role == HEADLINE:
            base = 12.0 if not self.short else _round(clamp(0.11 * h, 8.0, 12.0))
        elif role == CTA:
            base = 12.0 if not self.short else _round(clamp(0.09 * h, 7.0, 12.0))
        elif role == FINE_PRINT:
            base = 9.0 if not self.short else _round(clamp(0.065 * h, 5.0, 9.0))
        elif role == BADGE:
            # On a 90px banner a badge is a coloured pill; its label is a hint.
            base = 8.0 if not self.short else _round(clamp(0.035 * h, 3.0, 8.0))
        else:
            base = 10.0 if not self.short else _round(clamp(0.08 * h, 6.0, 10.0))
        rel = max(5.0, FONT_FLOOR_LONG * max(self.target.w, self.target.h)) * FONT_FLOOR_MULT.get(role, 1.0)
        return max(base, _round(rel))

    @property
    def short_side(self) -> float:
        return min(self.target.w, self.target.h)


def _round(v: float) -> float:
    return float(int(v + 0.5))


# ---------------------------------------------------------------------------
# layout items: each knows its size at a shrink factor k and how to place itself


class _Item:
    prio: float = PRIO_PRIMARY
    w_frac: float = 1.0        # share of the available width this item may use
    applies_w_frac: bool = False   # True: size() applies w_frac itself; else the caller does
    w: float = 0.0
    h: float = 0.0

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        raise NotImplementedError

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        raise NotImplementedError

    def relax(self, factor: float) -> None:
        """Rescue mode: lower this item's floors by `factor` (secondary and
        minor items only; the headline, logo and CTA keep theirs)."""
        return None


BUTTON_LABEL_INSIDE = 0.8   # a label is "in" its pill when this much of its box is (analyze.INSIDE_FRAC)
MIN_TEXT_BOX_H = 1.8        # a text box never drops below this height (a 1 px font needs ~1.4 px)
RESCUE_FACTOR = 0.55        # floors of secondary / minor items in rescue mode (when the floors do not fit)


class _Scaled(_Item):
    """An image, a group, or any unit that moves as one piece: uniform scale.

    A button-like group (shapes + one label, no images) whose uniform scale
    would push the label below `label_floor` is *squeezed* instead: the
    label is set at the readable size and the pill is re-shaped around it,
    insets scaled with the font and trimmed to the slot. That is what a
    designer does with a wide button on a narrow canvas."""

    applies_w_frac = True

    def __init__(self, unit: Unit, elements: dict[str, dict[str, Any]], ideal_s: float,
                 floor_s: float, prio: float = PRIO_PRIMARY, w_frac: float = 1.0,
                 m: TextMeasurer | None = None, label_floor: float = 0.0):
        self.unit = unit
        self.elements = elements
        self.ext_w, self.ext_h = _extents(unit, elements)
        # every member box stays >= 1 px (the official renderer rejects a 0 px
        # text box) and every text member tall enough for a 1 px font to fit
        thin = min((min(b.w, b.h) for b in unit.members.values() if min(b.w, b.h) > 0), default=1.0)
        text_h = min((unit.members[e].h for e in unit.ids if elements[e]["type"] == "text" and unit.members[e].h > 0),
                     default=0.0)
        self.min_s = max(1e-3, 1.0 / thin, (MIN_TEXT_BOX_H / text_h) if text_h else 0.0)
        self.ideal_s = max(ideal_s, floor_s)
        self.floor_s = floor_s
        self.prio = prio
        self.w_frac = w_frac
        self.s = 1.0
        self.m = m
        self.anchor_unit: Unit | None = None    # row parts: the row decides the corner
        self.label_floor = label_floor
        self.label = _button_label(unit, elements) if (m is not None and label_floor > 0) else None
        self.squeezed = False
        self.sq: tuple = ()

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        s = max(self.floor_s, self.ideal_s * k ** self.prio)
        s = min(s, aw * self.w_frac / self.ext_w, ah / self.ext_h)   # never larger than the slot
        self.s = max(s, self.min_s)
        self.squeezed = False
        if self.label is not None:
            src_font = float(self.elements[self.label]["font_size"])
            if src_font * self.s < self.label_floor - 1e-6 and self._squeeze(k, aw, ah):
                return self.w, self.h
        self.w, self.h = self.ext_w * self.s, self.ext_h * self.s
        return self.w, self.h

    def relax(self, factor: float) -> None:
        if self.prio >= PRIO_SECONDARY:
            self.floor_s *= factor
            self.label_floor = max(1.0, self.label_floor * factor)

    def _squeeze(self, k: float, slot_w: float, slot_h: float) -> bool:
        el = self.elements[self.label]
        src_font = float(el["font_size"])
        ub, lb = self.unit.box, self.unit.members[self.label]
        ink_src = self.m.layout(el, src_font, max(lb.w, 1.0)).max_width
        align = str(el.get("text_align", "left") or "left")
        if align == "center":
            ink_x = lb.x + (lb.w - ink_src) / 2.0
        elif align == "right":
            ink_x = lb.right - ink_src
        else:
            ink_x = lb.x
        pad_l, pad_r = max(0.0, ink_x - ub.x), max(0.0, ub.right - (ink_x + ink_src))
        pad_t, pad_b = max(0.0, lb.y - ub.y), max(0.0, ub.bottom - lb.bottom)
        wanted = max(self.label_floor, src_font * max(self.floor_s, self.ideal_s * k ** self.prio))
        font = max(1.0, float(int(wanted)))

        def attempt(font: float, max_lines: int, strict: bool) -> bool:
            s = font / src_font
            min_pad = 0.5 * font
            avail = slot_w - 2.0 * min_pad
            lay = self.m.layout(el, font, max(1.0, avail))
            if lay.max_width > avail + 0.5 or lay.n_lines > max_lines:
                return False
            ink_w = lay.max_width
            room = max(0.0, (slot_w - ink_w) / 2.0)
            pl = max(min_pad, min(pad_l * s, room))
            pr = max(min_pad, min(pad_r * s, room))
            text_h = math.ceil(lay.height) + 1.0
            w, h = ink_w + pl + pr, text_h + (pad_t + pad_b) * s
            if strict and (w > slot_w + 0.5 or h > slot_h + 0.5):
                return False
            self.squeezed = True
            self.sq = (font, pl, pr, pad_t * s, ink_w, text_h)
            self.w, self.h = w, h
            return True

        while True:
            if attempt(font, 2, True):
                return True
            if font <= self.label_floor:
                break
            font -= 1.0
        # At the floor: a long label may take three lines; as a last resort
        # the pill is reshaped at the floor font whatever its height (the
        # plan's shrink search and rescue mode make room, a 2 px label never reads).
        return attempt(self.label_floor, 3, True) or attempt(self.label_floor, 4, False)

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        box = self.unit.box
        if self.squeezed:
            font, pl, pr, pt, ink_w, text_h = self.sq
            pill = Box(x + (w - self.w) / 2.0, y + (h - self.h) / 2.0, self.w, self.h)
            sx, sy = pill.w / max(box.w, 1e-6), pill.h / max(box.h, 1e-6)
            src_font = float(self.elements[self.label]["font_size"])
            for eid, mb in self.unit.members.items():
                if eid == self.label:
                    out.boxes[eid] = Box(pill.x + pl - 0.5, pill.y + pt, ink_w + 1.0, text_h)
                    out.font_size[eid] = font
                    out.font_scale[eid] = font / src_font
                else:
                    out.boxes[eid] = Box(pill.x + (mb.x - box.x) * sx, pill.y + (mb.y - box.y) * sy,
                                         mb.w * sx, mb.h * sy)
                    out.font_scale[eid] = sy
            return
        bw, bh = box.w * self.s, box.h * self.s
        new = Box(x + (w - bw) / 2.0, y + (h - bh) / 2.0, bw, bh)
        _place_members(self.unit, new, self.s, out)
        for eid in self.unit.ids:
            out.font_scale[eid] = self.s
            el = self.elements[eid]
            if el["type"] == "text":
                out.font_size[eid] = max(1.0, float(el["font_size"]) * self.s)


def _button_label(unit: Unit, elements: dict[str, dict[str, Any]]) -> str | None:
    """The label id of a button-like group: shapes plus exactly one text that
    sits inside them, and no images. Anything else is not squeezable."""
    if not unit.is_group:
        return None
    texts = [e for e in unit.ids if elements[e]["type"] == "text"]
    shapes = [e for e in unit.ids if elements[e]["type"] == "shape"]
    if len(texts) != 1 or not shapes or len(texts) + len(shapes) != len(unit.ids):
        return None
    lb = unit.members[texts[0]]
    hull = Box.union(unit.members[s] for s in shapes)
    if hull.contains_fraction(lb) < BUTTON_LABEL_INSIDE:
        return None
    return texts[0]


class _TextItem(_Item):
    """A single text element whose font size is fitted to its slot.

    The footprint the plan reserves (`w` / `h`) is the *painted* extent of
    the text (its glyphs, not its box: the box starts `ascent - cap height`
    above the first caps and may be wider than the longest line), together
    with the shapes attached to the text (an underline bar, a divider): each
    keeps its position relative to the painted extent in units of the font
    size, so a bar under a heading stays under it at every size and line
    count. `place` puts the text box where that footprint lands.

    A text rotated to (near) vertical is wrapped and fitted in its *own*
    frame: the slot's height is its line width budget and the slot's width
    its height budget; its footprint is the rotated extent of its box and
    attachments scale with it uniformly."""

    def __init__(self, unit: Unit, el: dict[str, Any], m: TextMeasurer, cap: float,
                 floor: float, prio: float, natural_width: bool = False):
        self.unit = unit
        self.el = el
        self.m = m
        self.floor = float(floor)
        self.cap = max(float(int(cap)), self.floor)
        self.prio = prio
        self.natural_width = natural_width
        self.font = self.cap
        self.ink_w = 0.0            # widest wrapped line at the last size() (footprint width)
        self.rotation = float(el.get("rotation", 0.0) or 0.0)
        self.vertical = is_vertical(self.rotation)
        self.own_w = self.own_h = 0.0   # the box in the element's own frame
        self.box_off = (0.0, 0.0)       # text box top-left relative to the footprint top-left
        self.att: list[tuple[str, float, float, float, float, str, str]] = []   # attachments (see _attach)
        self.att_boxes: dict[str, Box] = {}   # attachment boxes relative to the footprint at the last size()
        self._attach()

    def _attach(self) -> None:
        """Record each attached shape relative to the source text's painted
        extent: x from the aligned edge, y from the painted top or bottom
        (whichever it is closer to), size, all in font-size units."""
        src_font = max(1.0, float(self.el["font_size"]))
        sb = self.unit.members[self.unit.primary or self.unit.ids[0]]
        painted = self.m.painted(self.el, src_font, max(sb.w, 1.0)).box(sb)
        align = str(self.el.get("text_align", "left") or "left")
        for eid in self.unit.attachments:
            ab = self.unit.members[eid]
            if align == "center":
                dx = ab.cx - painted.cx
            elif align == "right":
                dx = ab.right - painted.right
            else:
                dx = ab.x - painted.x
            if ab.cy <= painted.cy:
                dy, vref = ab.y - painted.y, "top"
            else:
                dy, vref = ab.y - painted.bottom, "bottom"
            self.att.append((eid, dx / src_font, dy / src_font, ab.w / src_font, ab.h / src_font, align, vref))

    def font_at(self, k: float) -> float:
        return max(self.floor, float(int(self.cap * k ** self.prio)))

    def relax(self, factor: float) -> None:
        if self.prio >= PRIO_SECONDARY:
            self.floor = max(1.0, float(int(self.floor * factor)))

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        # Budgets in the element's own frame.
        bw, bh = (ah, aw) if self.vertical else (aw, ah)
        font = self.font_at(k)
        # An over-wide single word overflows the box in the renderer: shrink first.
        while font > self.floor and self.m.layout(self.el, font, bw).max_width > bw + 0.5:
            font = max(self.floor, font - 1.0)
        natural = self.natural_width or self.vertical
        while True:
            w = min(bw, _single_line_width(self.m, self.el, font) + 2.0) if natural else bw
            lay = self.m.layout(self.el, font, w)
            h = math.ceil(lay.height) + 1.0
            if not self.vertical or h <= bh + 0.5 or font <= self.floor:
                break
            font = max(self.floor, font - 1.0)    # a vertical label too thick for its slot
        if lay.max_width > w + 0.5:
            # Still wider than the budget at the floor (letter-spaced line: the
            # renderer wraps on glyph widths and the spacing spills over): the
            # box takes the real width so the font the plan chose really fits
            # and the plan sees the true footprint.
            w = lay.max_width + 1.0
        self.font = font
        self.own_w, self.own_h = w, h
        self.att_boxes = {}
        if self.rotation:
            ext = _rotated_extent(w, h, self.rotation)
            self.w, self.h = ext
            self.ink_w = self.w if self.vertical else min(self.w, lay.max_width)
            self.box_off = ((self.w - w) / 2.0, (self.h - h) / 2.0)
            return self.w, self.h
        painted = self.m.painted(self.el, font, w)
        pb = Box(painted.x, painted.top, painted.w, painted.h)      # relative to the box
        boxes = [pb]
        rel: dict[str, Box] = {}
        for eid, dx, dy, aw_f, ah_f, align, vref in self.att:
            a_w, a_h = min(aw_f * font, max(w, 1.0)), ah_f * font
            if align == "center":
                ax = pb.cx + dx * font - a_w / 2.0
            elif align == "right":
                ax = pb.right + dx * font - a_w
            else:
                ax = pb.x + dx * font
            ay = (pb.y if vref == "top" else pb.bottom) + dy * font
            rel[eid] = Box(ax, ay, a_w, a_h)
            boxes.append(rel[eid])
        foot = Box.union(boxes)
        self.w, self.h = foot.w, foot.h
        self.ink_w = painted.w
        self.box_off = (-foot.x, -foot.y)
        self.att_boxes = {eid: Box(b.x - foot.x, b.y - foot.y, b.w, b.h) for eid, b in rel.items()}
        return self.w, self.h

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        eid = self.unit.primary or self.unit.ids[0]
        src_font = max(1.0, float(self.el["font_size"]))
        align = str(self.el.get("text_align", "left") or "left")
        if align == "right":
            fx = x + w - self.w
        elif align == "center" or self.rotation:
            fx = x + (w - self.w) / 2.0
        else:
            fx = x
        fy = y + (h - self.h) / 2.0     # footprint top-left
        if self.rotation:
            cx, cy = x + w / 2.0, y + h / 2.0
            box = Box(cx - self.own_w / 2.0, cy - self.own_h / 2.0, self.own_w, self.own_h)
            out.boxes[eid] = box
            s = self.font / src_font
            sb = self.unit.members[eid]
            for aid in self.unit.attachments:
                ab = self.unit.members[aid]
                out.boxes[aid] = Box(box.x + (ab.x - sb.x) * s, box.y + (ab.y - sb.y) * s, ab.w * s, ab.h * s)
                out.font_scale[aid] = s
        else:
            out.boxes[eid] = Box(fx + self.box_off[0], fy + self.box_off[1], self.own_w, self.own_h)
            for aid, b in self.att_boxes.items():
                out.boxes[aid] = Box(fx + b.x, fy + b.y, b.w, b.h)
                out.font_scale[aid] = self.font / src_font
        out.font_size[eid] = self.font
        out.font_scale[eid] = self.font / src_font


def is_vertical(rotation: float) -> bool:
    """Rotated closer to vertical than to horizontal (|rotation| near 90)."""
    r = abs(float(rotation or 0.0)) % 180.0
    return VERTICAL_MIN_DEG <= r <= 180.0 - VERTICAL_MIN_DEG


def _rotated_extent(w: float, h: float, rotation: float) -> tuple[float, float]:
    a = math.radians(rotation)
    return (w * abs(math.cos(a)) + h * abs(math.sin(a)), w * abs(math.sin(a)) + h * abs(math.cos(a)))


class _TextColumn(_Item):
    """Headline + subhead (+ body, fine print) stacked in a column whose width
    is chosen so the headline wraps on at most `max_lines` lines and the
    whole stack fits the available height. Used by the banner plan."""

    applies_w_frac = True

    def __init__(self, texts: list[_TextItem], head: _TextItem, gap: Callable[[float], float],
                 w_frac: float, max_lines: int = 2):
        self.texts = texts
        self.head = head
        self.gap = gap
        self.w_frac = w_frac
        self.max_lines = max_lines
        self.over = False

    def _height(self, k: float, w: float, ah: float) -> float:
        total = 0.0
        for t in self.texts:
            total += t.size(k, w, ah)[1]
        return total + self.gap(self.head.font) * (len(self.texts) - 1)

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        max_w = max(1.0, aw * self.w_frac)
        head_font = self.head.font_at(k)
        lo = _min_width_for_lines(self.head.m, self.head.el, head_font, self.max_lines, max_w)
        for t in self.texts:
            if t.vertical:
                continue   # its footprint width is its line height; size() handles it
            lo = max(lo, min(max_w, _longest_word_width(t.m, t.el, t.font_at(k)) + 1.0))
        lo = min(lo, max_w)
        if self._height(k, lo, ah) <= ah + 0.5:
            w = lo
            self.over = False
        else:
            a, b = lo, max_w
            if self._height(k, b, ah) > ah + 0.5:
                w = max_w
                self.over = True
            else:
                for _ in range(12):
                    mid = (a + b) / 2.0
                    if self._height(k, mid, ah) <= ah + 0.5:
                        b = mid
                    else:
                        a = mid
                w = b
                self.over = False
        self.h = self._height(k, w, ah)
        self.w = self._ink(w)
        return self.w, self.h

    def _ink(self, wrap_w: float) -> float:
        """Box width that keeps the wrap found at `wrap_w` but hugs the glyphs,
        so the gaps a viewer sees are the gaps the plan intended."""
        ink = max((t.ink_w for t in self.texts), default=wrap_w)
        return max(min(wrap_w, ink + 1.0), max((t.w for t in self.texts), default=0.0))

    def relax(self, factor: float) -> None:
        for t in self.texts:
            t.relax(factor)

    def comfortable_width(self, k: float, max_w: float) -> float:
        """Width at which the headline sits on one line and the rest on two."""
        best = 0.0
        for t in self.texts:
            lines = 1 if t is self.head else 2
            best = max(best, _min_width_for_lines(t.m, t.el, t.font_at(k), lines, max_w))
        return min(best, max_w)

    def widen(self, k: float, w: float, ah: float) -> None:
        if w > self.w:
            self.h = self._height(k, w, ah)
            self.w = self._ink(w)

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        cy = y + (h - self.h) / 2.0
        for t in self.texts:
            t.place(x + (w - self.w) / 2.0, cy, self.w, t.h, out)
            cy += t.h + self.gap(self.head.font)


class _Chips(_Item):
    """Badges, secondary images and other small stuff packed into a cluster:
    rows that wrap on the available width, or columns that wrap on the
    available height (banners)."""

    applies_w_frac = True

    def __init__(self, chips: list[_Scaled], direction: str, gap: float, w_frac: float = 1.0):
        self.chips = chips
        self.direction = direction
        self.gap = gap
        self.w_frac = w_frac
        self.prio = PRIO_MINOR
        self.offsets: list[tuple[float, float]] = []

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        aw = aw * self.w_frac
        for c in self.chips:
            c.size(k, aw, ah)
        g = self.gap
        lines: list[list[_Scaled]] = [[]]
        run = 0.0
        for c in self.chips:
            extent = c.w if self.direction == "row" else c.h
            limit = aw if self.direction == "row" else ah
            add = extent + (g if lines[-1] else 0.0)
            if lines[-1] and run + add > limit + 0.5:
                lines.append([c])
                run = extent
            else:
                lines[-1].append(c)
                run += add
        self.offsets = []
        if self.direction == "row":
            widths = [sum(c.w for c in ln) + g * (len(ln) - 1) for ln in lines]
            heights = [max(c.h for c in ln) for ln in lines]
            self.w = max(widths)
            self.h = sum(heights) + g * (len(lines) - 1)
            y = 0.0
            for ln, lw, lh in zip(lines, widths, heights):
                x = (self.w - lw) / 2.0
                for c in ln:
                    self.offsets.append((x, y + (lh - c.h) / 2.0))
                    x += c.w + g
                y += lh + g
        else:
            heights = [sum(c.h for c in ln) + g * (len(ln) - 1) for ln in lines]
            widths = [max(c.w for c in ln) for ln in lines]
            self.h = max(heights)
            self.w = sum(widths) + g * (len(lines) - 1)
            x = 0.0
            for ln, lw, lh in zip(lines, widths, heights):
                y = (self.h - lh) / 2.0
                for c in ln:
                    self.offsets.append((x + (lw - c.w) / 2.0, y))
                    y += c.h + g
                x += lw + g
        return self.w, self.h

    def relax(self, factor: float) -> None:
        for c in self.chips:
            c.relax(factor)

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        x0 = x + (w - self.w) / 2.0
        y0 = y + (h - self.h) / 2.0
        for c, (dx, dy) in zip(self.chips, self.offsets):
            c.place(x0 + dx, y0 + dy, c.w, c.h, out)


class _Row(_Item):
    """Items side by side (the CTA with the badges, a headline beside its
    subhead), vertically centred. Each child sizes itself on its own share
    of the row's width, so the row never grows wider than its slot."""

    def __init__(self, items: list[_Item], gap: float, shares: list[float] | None = None):
        self.items = items
        self.gap = gap
        self.shares = shares or [1.0 / len(items)] * len(items)
        self.prio = min(it.prio for it in items)

    def size(self, k: float, aw: float, ah: float) -> tuple[float, float]:
        inner = max(1.0, aw - self.gap * (len(self.items) - 1))
        self.w = self.gap * (len(self.items) - 1)
        self.h = 0.0
        for it, share in zip(self.items, self.shares):
            w, h = it.size(k, inner * share, ah)
            self.w += w
            self.h = max(self.h, h)
        return self.w, self.h

    def relax(self, factor: float) -> None:
        for it in self.items:
            it.relax(factor)

    def place(self, x: float, y: float, w: float, h: float, out: Placement) -> None:
        cx = x + (w - self.w) / 2.0
        for it in self.items:
            it.place(cx, y + (h - it.h) / 2.0, it.w, it.h, out)
            cx += it.w + self.gap


# ---------------------------------------------------------------------------
# measuring helpers


def _text_h(m: TextMeasurer, el: dict[str, Any], font: float, width: float) -> float:
    return math.ceil(m.layout(el, font, width).height) + 1.0


def _single_line_width(m: TextMeasurer, el: dict[str, Any], font: float) -> float:
    return m.layout(el, font, 1e7).max_width


def _longest_word_width(m: TextMeasurer, el: dict[str, Any], font: float) -> float:
    lay = m.layout(el, font, 1.0)   # wraps at every space: each line is one word
    return lay.max_width


def _min_width_for_lines(m: TextMeasurer, el: dict[str, Any], font: float,
                         max_lines: int, max_w: float) -> float:
    """Smallest box width at which the text wraps on at most `max_lines`."""
    if el.get("max_lines"):
        max_lines = min(max_lines, int(el["max_lines"]))

    def ok(w: float) -> bool:
        lay = m.layout(el, font, w)
        return lay.n_lines <= max_lines and lay.max_width <= w + 0.5

    if not ok(max_w):
        return max_w
    lo, hi = max(1.0, _longest_word_width(m, el, font)), max_w
    if ok(lo):
        return lo
    for _ in range(12):
        mid = (lo + hi) / 2.0
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


def _extents(unit: Unit, elements: dict[str, dict[str, Any]]) -> tuple[float, float]:
    """Axis-aligned extents of the unit, allowing for rotated members."""
    rot = 0.0
    for eid in unit.ids:
        rot = max(rot, abs(float(elements[eid].get("rotation", 0.0) or 0.0)))
    w, h = max(unit.box.w, 1.0), max(unit.box.h, 1.0)
    if rot == 0.0:
        return w, h
    a = math.radians(rot)
    return w * abs(math.cos(a)) + h * abs(math.sin(a)), w * abs(math.sin(a)) + h * abs(math.cos(a))


def _largest_k(fits: Callable[[float], bool], items: list[_Item] | None = None) -> tuple[float, bool]:
    """Largest k in [0, 1] for which fits(k) holds (fits is monotone in k).
    Leaves every item sized at the returned k. The flag is False when even
    the floors (k = 0) do not fit; with `items` given, that case first
    tries rescue mode (secondary / minor floors lowered by RESCUE_FACTOR):
    a readable headline and CTA with small legal copy beat a layout whose
    pieces run into each other."""
    if fits(1.0):
        return 1.0, True
    if not fits(0.0):
        if not items:
            return 0.0, False
        for it in items:
            it.relax(RESCUE_FACTOR)
        if not fits(0.0):
            return 0.0, False
    lo, hi = 0.0, 1.0
    for _ in range(K_SEARCH_STEPS):
        mid = (lo + hi) / 2.0
        if fits(mid):
            lo = mid
        else:
            hi = mid
    fits(lo)
    return lo, True


# ---------------------------------------------------------------------------
# slots: content units sorted into the roles a floor plan knows about


@dataclass
class _Slots:
    logo: Unit | None
    hero: Unit | None
    cta: Unit | None
    texts: list[Unit]          # headline / subhead / body, reading order
    fine: list[Unit]
    chips: list[Unit]          # badges, extra images, shapes, grouped text blocks
    text_align: str            # headline's alignment drives column alignment
    hero_side: str             # left | right (wide plan)


def _collect(analysis: Analysis, elements: dict[str, dict[str, Any]]) -> _Slots:
    logo = hero = cta = None
    texts: list[Unit] = []
    fine: list[Unit] = []
    chips: list[Unit] = []
    for u in sorted(analysis.content_units(), key=lambda u: u.reading_index):
        text_unit = u.primary_type(elements) == "text"   # a text, possibly with attached bars
        if u.role == LOGO and logo is None:
            logo = u
        elif u.role == HERO and hero is None:
            hero = u
        elif u.role == CTA and cta is None:
            cta = u
        elif u.role in (HEADLINE, SUBHEAD, BODY, TEXT) and text_unit:
            texts.append(u)
        elif u.role == FINE_PRINT and text_unit:
            fine.append(u)
        else:
            chips.append(u)
    head = next((u for u in texts if u.role == HEADLINE), texts[0] if texts else None)
    align = "center"
    if head is not None:
        align = str(elements[head.primary or head.ids[0]].get("text_align", "left") or "left")
        if align not in ("left", "center", "right"):
            align = "center"
    side = "left"
    if hero is not None and head is not None and hero.box.cx > head.box.cx + 0.1 * analysis.canvas.w:
        side = "right"
    return _Slots(logo, hero, cta, texts, fine, chips, align, side)


# ---------------------------------------------------------------------------
# item factories


class _Builder:
    def __init__(self, analysis: Analysis, elements: dict[str, dict[str, Any]],
                 met: Metrics, m: TextMeasurer, family: str):
        self.analysis = analysis
        self.elements = elements
        self.met = met
        self.m = m
        self.family = family
        self.slots = _collect(analysis, elements)
        self.target = met.target

    # -- text ------------------------------------------------------------

    def text(self, unit: Unit, prio: float, natural_width: bool = False) -> _TextItem:
        el = self.elements[unit.primary or unit.ids[0]]
        cap = float(el["font_size"]) * self.met.cap_scale
        return _TextItem(unit, el, self.m, cap, self.met.min_font(unit.role), prio, natural_width)

    def text_items(self) -> list[_TextItem]:
        items = []
        for u in self.slots.texts:
            prio = PRIO_PRIMARY if u.role == HEADLINE else PRIO_SECONDARY
            items.append(self.text(u, prio))
        return items

    def fine_items(self) -> list[_TextItem]:
        return [self.text(u, PRIO_MINOR) for u in self.slots.fine]

    def text_gap(self) -> Callable[[float], float]:
        g = self.met.gap
        return lambda head_font: clamp(0.35 * head_font, 3.0, g)

    # -- scaled pieces -----------------------------------------------------

    def _text_floor(self, unit: Unit, role: str) -> float:
        """Scale below which a group's text members go under the role's minimum."""
        fonts = [float(self.elements[e]["font_size"]) for e in unit.ids if self.elements[e]["type"] == "text"]
        if not fonts:
            return 0.0
        return self.met.min_font(role) / max(fonts)

    def scaled(self, unit: Unit, ideal_h: float, floor_h: float, prio: float, w_frac: float,
               role_for_floor: str | None = None, cap_mult: float = 1.0,
               floor_frac: float = 0.0) -> _Scaled:
        """`floor_frac`: the unit's larger dimension never drops below this
        share of the canvas's short side (capped by the slot in size())."""
        ext_w, ext_h = _extents(unit, self.elements)
        ideal_s = min(ideal_h / ext_h, self.met.cap_scale * cap_mult)
        floor_s = floor_h / ext_h
        if floor_frac > 0.0:
            floor_s = max(floor_s, floor_frac * self.met.short_side / max(ext_w, ext_h))
        label_floor = 0.0
        if role_for_floor is not None:
            floor_s = max(floor_s, self._text_floor(unit, role_for_floor))
            label_floor = self.met.min_font(role_for_floor)
        return _Scaled(unit, self.elements, ideal_s, floor_s, prio, w_frac, self.m, label_floor)

    def logo(self, ideal_h: float, floor_h: float, w_frac: float) -> _Scaled | None:
        if self.slots.logo is None:
            return None
        return self.scaled(self.slots.logo, ideal_h, floor_h, PRIO_PRIMARY, w_frac, cap_mult=1.2,
                           floor_frac=LOGO_FLOOR_FRAC)

    def hero(self, ideal_h: float, floor_h: float, w_frac: float) -> _Scaled | None:
        if self.slots.hero is None:
            return None
        src, t = self.analysis.canvas, self.target
        cap = max(t.w / src.w, t.h / src.h) / self.met.cap_scale   # never beyond the larger axis scale
        return self.scaled(self.slots.hero, ideal_h, floor_h, PRIO_HERO, w_frac, cap_mult=cap,
                           floor_frac=HERO_FLOOR_FRAC)

    def cta(self, ideal_h: float, w_frac: float, natural_width: bool = False) -> _Item | None:
        u = self.slots.cta
        if u is None:
            return None
        if u.primary_type(self.elements) == "text":
            return self.text(u, PRIO_PRIMARY, natural_width)
        return self.scaled(u, ideal_h, 0.0, PRIO_PRIMARY, w_frac, role_for_floor=CTA, cap_mult=1.15)

    def chips(self, badge_h: float, image_h: float, direction: str, w_frac: float = 1.0) -> _Chips | None:
        if not self.slots.chips:
            return None
        items = []
        for u in self.slots.chips:
            # A sibling row re-flows: its parts are separate chips that the
            # cluster packs into rows / columns of the available size.
            for part in (u.parts if u.is_row else [u]):
                has_text = any(self.elements[e]["type"] == "text" for e in part.ids)
                ideal = badge_h if has_text else image_h
                # A sticker that was big in the source (a date block at 17 % of
                # the poster) keeps some of that share instead of shrinking to a pill.
                share = part.box.h / self.analysis.canvas.h
                ideal = max(ideal, min(CHIP_MAX_SHARE * self.target.h, share * self.target.h))
                floor_h = 6.0 if has_text else min(10.0, image_h)
                it = self.scaled(part, ideal, floor_h, PRIO_MINOR, 1.0,
                                 role_for_floor=BADGE if has_text else None,
                                 floor_frac=STAMP_FLOOR_FRAC)
                it.anchor_unit = u      # corner pinning follows the row, not the part
                items.append(it)
        return _Chips(items, direction, max(3.0, self.met.gap * 0.5), w_frac)


# ---------------------------------------------------------------------------
# column plans (tall, square, and the text side of wide)


def _column_fits(items: list[_Item], gaps: list[float], aw: float, ah: float) -> Callable[[float], bool]:
    def fits(k: float) -> bool:
        total = sum(it.size(k, aw if it.applies_w_frac else aw * it.w_frac, ah)[1] for it in items) + sum(gaps)
        return total <= ah + 0.5
    return fits


def _anchored_bottom(item: _Item) -> bool:
    """Did this item's unit hug the bottom edge in the source (a CTA usually does)?"""
    units = [it.unit for it in getattr(item, "items", [item]) if hasattr(it, "unit")]
    return any(u.anchor_y == "bottom" for u in units)


def _place_column(items: list[_Item], gaps: list[float], x0: float, y0: float, aw: float, ah: float,
                  align: str, met: Metrics, out: Placement, top_anchor: bool, bottom_anchor: bool) -> None:
    n = len(items)
    total = sum(it.h for it in items) + sum(gaps)
    leftover = max(0.0, ah - total)
    extra = min(leftover / (len(gaps) + 2), met.gap) if gaps else 0.0
    leftover -= extra * len(gaps)
    before = [0.0] * n
    if n == 1:
        before[0] = 0.0 if top_anchor else (leftover if bottom_anchor else leftover / 2.0)
    elif top_anchor and bottom_anchor:
        if n == 2:
            before[1] = leftover
        else:
            before[1] += leftover / 2.0
            before[-1] += leftover / 2.0
    elif top_anchor:
        before[1] = leftover / 2.0
    elif bottom_anchor:
        before[0] = leftover / 2.0
        before[-1] += leftover / 2.0
    else:
        before[0] = leftover / 2.0
    y = y0
    for i, it in enumerate(items):
        y += before[i]
        if i > 0:
            y += gaps[i - 1] + extra
        if align == "left":
            x = x0
        elif align == "right":
            x = x0 + aw - it.w
        else:
            x = x0 + (aw - it.w) / 2.0
        it.place(x, y, it.w, it.h, out)
        y += it.h


def _column_items(b: _Builder, met: Metrics, H: float, with_hero: bool, tight: bool,
                  chips_mode: str = "row") -> tuple[list[_Item], list[float], _Chips | None]:
    """Items of the centred column and the gaps between them. The third value
    is the chips cluster when `chips_mode` is "corner": it is not part of the
    column and the caller pins it to the canvas corners after the k search."""
    items: list[_Item] = []
    text_gap = b.text_gap()
    # The logo keeps the share of the height the designer gave it (within
    # reason); a logo that was 10 % of the poster stays 10 % of the story.
    logo_frac = 0.07
    if b.slots.logo is not None:
        logo_frac = clamp(b.slots.logo.box.h / b.analysis.canvas.h, 0.07, 0.14)
    logo = b.logo(ideal_h=logo_frac * H, floor_h=max(12.0, 0.035 * H), w_frac=0.5)
    if logo:
        items.append(logo)
    if with_hero:
        hero = b.hero(ideal_h=(0.36 if tight else 0.40) * H, floor_h=0.15 * H, w_frac=0.85)
        if hero:
            items.append(hero)
    texts = b.text_items()
    for t in texts:
        t.w_frac = 0.86 if tight else 0.9
    items.extend(texts)
    chips = b.chips(badge_h=0.045 * H, image_h=0.07 * H, direction="row", w_frac=0.95)
    cta = b.cta(ideal_h=0.065 * H, w_frac=0.7)
    if cta:
        cta.w_frac = 0.7 if isinstance(cta, _Scaled) else 0.9
    corner_chips: _Chips | None = None
    if chips and chips_mode == "beside_cta" and cta:
        chips.w_frac = 1.0
        cta.w_frac = 1.0
        if isinstance(cta, _TextItem):
            cta.natural_width = True
        chips_first = _mean_reading_index(b.slots.chips) < b.slots.cta.reading_index
        pair = [chips, cta] if chips_first else [cta, chips]
        shares = [0.45, 0.55] if chips_first else [0.55, 0.45]
        row = _Row(pair, met.gap, shares)
        row.w_frac = 0.95
        items.append(row)
    else:
        if chips and chips_mode == "corner":
            corner_chips = chips
        elif chips:
            items.append(chips)
        if cta:
            items.append(cta)
    fine = b.fine_items()
    for f in fine:
        f.w_frac = 0.92
    items.extend(fine)

    gaps = []
    for a, c in zip(items, items[1:]):
        if isinstance(a, _TextItem) and isinstance(c, _TextItem) and a in texts and c in texts:
            gaps.append(text_gap(texts[0].cap))
        else:
            gaps.append(met.gap)
    return items, gaps, corner_chips


def _mean_reading_index(units: list[Unit]) -> float:
    idx = [u.reading_index for u in units if u.reading_index >= 0]
    return sum(idx) / len(idx) if idx else 1e9


def _place_corner_chips(chips: _Chips, k: float, met: Metrics, area: Box, out: Placement) -> None:
    """Pin each chip to the corner of `area` it came from in the source
    (its anchors), stacking chips that share a corner. Sizes come from the
    column's shrink factor so the stickers match the rest of the layout."""
    g = chips.gap
    cursors: dict[tuple[str, str], float] = {}
    row_seen: dict[str, int] = {}
    for c in chips.chips:
        c.size(k, area.w * 0.45, area.h * 0.3)
        u = getattr(c, "anchor_unit", None) or c.unit
        src = u.box
        if u.anchor_x in ("left", "right"):
            hx = u.anchor_x
        else:
            hx = "left" if src.cx <= met.target.w / 2.0 else "right"
        if u is not c.unit:
            # a sibling row spreads over both corners of its edge, left to right
            n = row_seen.get(u.key, 0)
            row_seen[u.key] = n + 1
            hx = ("left", "right")[n % 2] if u.anchor_x == "center" or u.anchor_x == "fluid" else (hx if n % 2 == 0 else ("right" if hx == "left" else "left"))
        if u.anchor_y in ("top", "bottom"):
            vy = u.anchor_y
        else:
            vy = "top" if src.cy <= met.target.h / 2.0 else "bottom"
        used = cursors.get((hx, vy), 0.0)
        x = area.x if hx == "left" else area.right - c.w
        y = area.y + used if vy == "top" else area.bottom - used - c.h
        c.place(x, y, c.w, c.h, out)
        cursors[(hx, vy)] = used + c.h + g


def _plan_column(b: _Builder, met: Metrics, out: Placement, family: str,
                 opts: PlanOptions = DEFAULT_OPTIONS) -> None:
    t = met.target
    m = met.margin
    aw, ah = t.w - 2 * m, t.h - 2 * m
    items, gaps, corner_chips = _column_items(b, met, t.h, with_hero=True,
                                              tight=(family == SQUARE), chips_mode=opts.chips)
    k = 1.0
    if items:
        k, _ = _largest_k(_column_fits(items, gaps, aw, ah), items + ([corner_chips] if corner_chips else []))
        top = bool(b.slots.logo) and isinstance(items[0], _Scaled) and items[0].unit is b.slots.logo
        bottom = bool(b.slots.fine) or _anchored_bottom(items[-1])
        _place_column(items, gaps, m, m, aw, ah, "center", met, out, top, bottom)
    if corner_chips is not None:
        _place_corner_chips(corner_chips, k, met, Box(m, m, aw, ah), out)


def _plan_wide(b: _Builder, met: Metrics, out: Placement, opts: PlanOptions = DEFAULT_OPTIONS) -> None:
    t = met.target
    m = met.margin
    aw, ah = t.w - 2 * m, t.h - 2 * m
    hero = b.hero(ideal_h=ah, floor_h=0.4 * ah, w_frac=1.0)
    items, gaps, corner_chips = _column_items(b, met, t.h, with_hero=False, tight=False,
                                              chips_mode=opts.chips)
    side = opts.hero_side if opts.hero_side in ("left", "right") else b.slots.hero_side
    align = b.slots.text_align if hero else "center"
    col_frac = 1.0 if hero else 0.8

    def col_w(k: float) -> float:
        if hero is None:
            return aw * col_frac
        hero.size(k, aw * 0.45, ah)
        return aw - hero.w - met.gap

    def fits(k: float) -> bool:
        cw = col_w(k)
        if not items:
            return True
        return _column_fits(items, gaps, cw, ah)(k)

    k, _ = _largest_k(fits, items + ([hero] if hero else []) + ([corner_chips] if corner_chips else []))
    cw = aw - hero.w - met.gap if hero is not None else aw * col_frac
    if hero is not None:
        hx = m if side == "left" else t.w - m - hero.w
        hero.place(hx, m + (ah - hero.h) / 2.0, hero.w, hero.h, out)
        x0 = m + hero.w + met.gap if side == "left" else m
    else:
        x0 = m + (aw - cw) / 2.0
    if items:
        top = bool(b.slots.logo) and isinstance(items[0], _Scaled) and items[0].unit is b.slots.logo
        bottom = bool(b.slots.fine) or _anchored_bottom(items[-1])
        _place_column(items, gaps, x0, m, cw, ah, align, met, out, top, bottom)
    if corner_chips is not None:
        _place_corner_chips(corner_chips, k, met, Box(x0, m, cw, ah), out)


# ---------------------------------------------------------------------------
# banner plan (single row)


def _plan_banner(b: _Builder, met: Metrics, out: Placement, opts: PlanOptions = DEFAULT_OPTIONS) -> None:
    t = met.target
    m = met.margin
    aw, ah = t.w - 2 * m, t.h - 2 * m
    gap = met.gap

    logo = b.logo(ideal_h=0.4 * ah, floor_h=max(10.0, 0.2 * ah), w_frac=0.3)
    hero = b.hero(ideal_h=ah, floor_h=0.35 * ah, w_frac=0.3)
    texts = b.text_items() + b.fine_items()
    column: _TextColumn | None = None     # the column the line policy steers (holds the headline)
    rest_column: _TextColumn | None = None
    if texts:
        head = next((x for x in texts if x.unit.role == HEADLINE), texts[0])
        others = [x for x in texts if x is not head]
        if opts.text_flow == "inline" and others:
            column = _TextColumn([head], head, b.text_gap(), w_frac=0.36)
            rest_column = _TextColumn(others, others[0], b.text_gap(), w_frac=0.3, max_lines=3)
        else:
            column = _TextColumn(texts, head, b.text_gap(), w_frac=0.6)
    chips = b.chips(badge_h=0.26 * ah, image_h=0.3 * ah, direction="col", w_frac=0.3)
    cta = b.cta(ideal_h=0.38 * ah, w_frac=0.3, natural_width=True)

    if opts.hero_side == "right":
        order = (logo, column, rest_column, chips, cta, hero)
    else:
        order = (logo, hero, column, rest_column, chips, cta)
    items: list[_Item] = [it for it in order if it is not None]
    if not items:
        return

    def fits(k: float) -> bool:
        # Size *every* item before judging: a plan that cannot fit (twelve
        # lines of copy in a 90 px row) must still leave each item with a
        # real size, or the unsized ones come out as 0x0 boxes, which the
        # official renderer rejects outright.
        total = 0.0
        ok = True
        for it in items:
            w, h = it.size(k, aw, ah)
            if h > ah + 0.5:
                ok = False
            total += w
        return ok and total + gap * (len(items) - 1) <= aw + 0.5

    # Fewest headline lines first, but only while the row is still roomy
    # (k above the threshold); a 1-line headline at half size loses to a
    # 2-line one at full size.
    k, ok = _largest_k(fits)
    if column is not None:
        chosen = None
        for max_lines, min_k in BANNER_LINE_POLICY:
            column.max_lines = max_lines
            k, ok = _largest_k(fits)
            if ok:
                chosen = max_lines
                if k >= min_k:
                    break
        column.max_lines = chosen if chosen is not None else BANNER_LINE_POLICY[-1][0]
        k, ok = _largest_k(fits)
    if not ok:
        k, ok = _largest_k(fits, items)      # rescue mode: lower the minor floors

    leftover = aw - sum(it.w for it in items) - gap * (len(items) - 1)
    if column is not None and leftover > 0:
        comfy = column.comfortable_width(k, aw * column.w_frac)
        column.widen(k, min(comfy, column.w + leftover), ah)
        leftover = aw - sum(it.w for it in items) - gap * (len(items) - 1)
    leftover = max(0.0, leftover)

    n = len(items)
    extra = leftover / (n - 1) if n > 1 else 0.0
    x = m + (leftover / 2.0 if n == 1 else 0.0)
    for it in items:
        it.place(x, m + (ah - it.h) / 2.0, it.w, it.h, out)
        x += it.w + gap + extra


# ---------------------------------------------------------------------------
# entry point


def floorplan_relayout(analysis: Analysis, target: Box, elements: dict[str, dict[str, Any]],
                       measurer: TextMeasurer | None = None,
                       options: PlanOptions | None = None) -> Placement:
    """Lay the analysed design out on `target` with the floor plan of its
    ratio family. `elements` maps element id -> source element (needed for
    text measurement and rotations). `options` picks one of the plan's
    variants (defaults reproduce the single v1 layout)."""
    m = measurer or default_measurer()
    opts = options or DEFAULT_OPTIONS
    family = ratio_family(target)
    met = Metrics.for_canvas(analysis.canvas, target, family, opts.spacing, opts.scale_bias)
    src = analysis.canvas
    s = min(target.w / src.w, target.h / src.h)
    out = Placement()

    for unit in analysis.units:
        if unit.role == BACKGROUND:
            for eid, mb in unit.members.items():
                out.boxes[eid] = _cover_box(mb, src, target)
                out.font_scale[eid] = s
        elif unit.role == DECORATIVE:
            _place_members(unit, _map_decorative(unit.box, src, target, s), s, out)
            for eid in unit.ids:
                out.font_scale[eid] = s

    b = _Builder(analysis, elements, met, m, family)
    plan = family
    if family == SQUARE and opts.hero_side in ("left", "right") and b.slots.hero is not None:
        plan = WIDE          # hero on one side, column on the other, on a square
    elif family == WIDE and opts.hero_side == "stack":
        plan = TALL          # one centred column on a wide canvas
    if plan in (TALL, SQUARE):
        _plan_column(b, met, out, family, opts)
    elif plan == WIDE:
        _plan_wide(b, met, out, opts)
    else:
        _plan_banner(b, met, out, opts)

    # Panels (colour zones) are rebuilt around the content they carried.
    place_panels(analysis, out, target, mode="wrap", measurer=m)

    # Safety net: anything a plan did not place keeps its proportions and
    # its relative position (should not happen; keeps every id present).
    for unit in analysis.units:
        if all(eid in out.boxes for eid in unit.ids):
            continue
        cx, cy = unit.box.cx / src.w * target.w, unit.box.cy / src.h * target.h
        new = Box(cx - unit.box.w * s / 2, cy - unit.box.h * s / 2, unit.box.w * s, unit.box.h * s)
        _place_members(unit, new, s, out)
        for eid in unit.ids:
            out.font_scale[eid] = s
    return out
