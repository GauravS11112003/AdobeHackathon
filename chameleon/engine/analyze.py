"""Read the invisible rules out of a source design.

Hidden tasks give us only id / type / geometry, so every role here is
inferred from signals (size, position, opacity, grouping, font size,
text length, colour), never from element ids.

Output is an `Analysis`: a list of layout `Unit`s (an ungrouped element, or
a whole `group_id` treated as one piece of furniture), each tagged with a
role, an importance weight, and the canvas edges it hugs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.geometry import Box

# Roles, roughly in importance order. Keep these strings stable: the layout
# code and the tests key off them.
BACKGROUND = "background"
DECORATIVE = "decorative"
LOGO = "logo"
HERO = "hero"
IMAGE = "image"
HEADLINE = "headline"
SUBHEAD = "subhead"
BODY = "body"
CTA = "cta"
BADGE = "badge"
FINE_PRINT = "fine_print"
PANEL = "panel"              # a large flat shape: a colour zone / card / bar, not a sticker
SHAPE = "shape"
TEXT = "text"

IMPORTANCE = {
    HEADLINE: 1.0,
    LOGO: 0.9,
    CTA: 0.9,
    HERO: 0.85,
    SUBHEAD: 0.6,
    BADGE: 0.5,
    BODY: 0.5,
    IMAGE: 0.4,
    SHAPE: 0.3,
    FINE_PRINT: 0.2,
    PANEL: 0.15,
    DECORATIVE: 0.1,
    BACKGROUND: 0.0,
    TEXT: 0.4,
}

# Thresholds (fractions of the canvas unless noted).
BACKGROUND_COVER = 0.85      # element covers >= this much of the canvas
DECO_OPACITY = 0.35          # below this an ungrouped shape is decoration
DECO_BLEED = 0.10            # >= this fraction of its own area off-canvas
LOGO_MAX_AREA = 0.15         # logo candidates are small
HERO_MIN_AREA = 0.03         # anything smaller is a sticker, not the hero
EDGE_HUG = 0.15              # margin < this fraction => anchored to that edge
CENTER_TOL_X = 0.06
CENTER_TOL_Y = 0.08
FINE_PRINT_RATIO = 0.45      # font_size <= this * headline size ...
FINE_PRINT_MAX_PX = 16       # ... and absolutely small, or very long (legal copy)
FINE_PRINT_MIN_CHARS = 80
CTA_MAX_CHARS = 32
PANEL_MIN_COVER = 0.15       # an ungrouped shape covering >= this much of the canvas is a panel ...
PANEL_EDGE = 0.02            # ... or one that runs from one canvas edge to the opposite one
PANEL_CARRY = 0.5            # a unit sits "on" a panel when this fraction of its box is inside it
PANEL_TEXT_CONTRAST = 1.5    # text with less contrast against the panel's fill is not carried by it


@dataclass
class Unit:
    """One piece of furniture: a single element or a whole group."""

    key: str                       # element id, or "group:<group_id>"
    ids: list[str]
    role: str
    box: Box                       # bbox in source canvas px
    importance: float = 0.0
    anchor_x: str = "fluid"        # left | center | right | fluid
    anchor_y: str = "fluid"        # top | center | bottom | fluid
    reading_index: int = -1        # order among content units (y then x)
    group_id: str | None = None
    members: dict[str, Box] = field(default_factory=dict)   # id -> source box
    panel: str | None = None       # key of the panel this unit sits on in the source

    @property
    def is_group(self) -> bool:
        return self.group_id is not None

    @property
    def is_content(self) -> bool:
        """Furniture the plans arrange. Backgrounds, decoration and panels are
        zones laid out around the content instead."""
        return self.role not in (BACKGROUND, DECORATIVE, PANEL)

    @property
    def is_panel(self) -> bool:
        return self.role == PANEL


@dataclass
class Analysis:
    canvas: Box
    units: list[Unit]
    roles: dict[str, str]          # element id -> role
    element_unit: dict[str, str]   # element id -> unit key
    headline_font_size: float | None = None
    shape_types: dict[str, str] = field(default_factory=dict)   # shape id -> shape_type

    def unit(self, key: str) -> Unit:
        for u in self.units:
            if u.key == key:
                return u
        raise KeyError(key)

    def by_role(self, role: str) -> list[Unit]:
        return [u for u in self.units if u.role == role]

    def content_units(self) -> list[Unit]:
        return [u for u in self.units if u.is_content]

    def panels(self) -> list[Unit]:
        return [u for u in self.units if u.is_panel]

    def carried(self, panel_key: str) -> list[Unit]:
        """Content units that sat on this panel in the source."""
        return [u for u in self.units if u.is_content and u.panel == panel_key]


# ---------------------------------------------------------------------------


def analyze(source: dict[str, Any]) -> Analysis:
    canvas = Box(0.0, 0.0, float(source["canvas"]["width"]), float(source["canvas"]["height"]))
    elements = source["elements"]
    by_id = {el["id"]: el for el in elements}

    # 1. Per-element roles for things that are decided individually.
    roles: dict[str, str] = {}
    for el in elements:
        if _is_background(el, canvas):
            roles[el["id"]] = BACKGROUND
        elif _is_panel(el, canvas):
            roles[el["id"]] = PANEL
        elif _is_decorative(el, canvas):
            roles[el["id"]] = DECORATIVE

    # 2. Groups become single units; their role is decided from their members.
    groups: dict[str, list[dict[str, Any]]] = {}
    for el in elements:
        gid = el.get("group_id")
        if gid and roles.get(el["id"]) is None:
            groups.setdefault(gid, []).append(el)

    # 3. Images: logo / hero / other.
    free_images = [
        el for el in elements
        if el["type"] == "image" and el["id"] not in roles and not el.get("group_id")
    ]
    _assign_image_roles(free_images, canvas, roles)

    # 4. Free text: headline / subhead / body / cta / fine print.
    free_text = [
        el for el in elements
        if el["type"] == "text" and el["id"] not in roles and not el.get("group_id")
    ]
    headline_size = _assign_text_roles(free_text, canvas, roles)

    # 5. Remaining ungrouped shapes.
    for el in elements:
        if el["id"] not in roles and not el.get("group_id"):
            roles[el["id"]] = SHAPE if el["type"] == "shape" else TEXT

    # 6. Group roles (needs the headline position to tell CTA from badge).
    headline_box = next((Box.of(el) for el in free_text if roles.get(el["id"]) == HEADLINE), None)
    group_roles = _assign_group_roles(groups, canvas, headline_box)
    for gid, members in groups.items():
        for el in members:
            roles[el["id"]] = group_roles[gid]

    # 7. Build units.
    units: list[Unit] = []
    element_unit: dict[str, str] = {}
    for el in elements:
        gid = el.get("group_id")
        if gid and gid in groups:
            continue  # handled below
        box = Box.of(el)
        u = Unit(key=el["id"], ids=[el["id"]], role=roles[el["id"]], box=box,
                 members={el["id"]: box})
        units.append(u)
        element_unit[el["id"]] = u.key
    for gid, members in groups.items():
        boxes = {el["id"]: Box.of(el) for el in members}
        u = Unit(key=f"group:{gid}", ids=[el["id"] for el in members],
                 role=group_roles[gid], box=Box.union(boxes.values()),
                 group_id=gid, members=boxes)
        units.append(u)
        for el in members:
            element_unit[el["id"]] = u.key

    for u in units:
        u.importance = IMPORTANCE.get(u.role, 0.3)
        u.anchor_x, u.anchor_y = _anchors(u.box, canvas)

    # Which panel does each piece of content sit on? The *topmost* panel
    # drawn below it that holds most of the unit's box: that is the colour
    # the viewer sees behind it (content under an opaque panel is hidden, not
    # carried). The layouts keep that relation.
    z = {el["id"]: float(el.get("z_index", i) if el.get("z_index") is not None else i)
         for i, el in enumerate(elements)}
    panels = sorted((u for u in units if u.is_panel), key=lambda u: (-z[u.ids[0]], u.box.area))
    for u in units:
        if not u.is_content:
            continue
        top = min(z[i] for i in u.ids)
        for p in panels:
            if z[p.ids[0]] < top and p.box.contains_fraction(u.box) >= PANEL_CARRY \
                    and _readable_on(u, by_id[p.ids[0]], by_id):
                u.panel = p.key
                break

    # Reading order over content units: top-to-bottom, then left-to-right,
    # with a row tolerance so side-by-side badges count as one row.
    content = sorted((u for u in units if u.is_content), key=lambda u: (u.box.cy, u.box.cx))
    rows: list[list[Unit]] = []
    for u in content:
        if rows and abs(rows[-1][0].box.cy - u.box.cy) < 0.5 * min(rows[-1][0].box.h, u.box.h) + 1:
            rows[-1].append(u)
        else:
            rows.append([u])
    idx = 0
    for row in rows:
        for u in sorted(row, key=lambda u: u.box.cx):
            u.reading_index = idx
            idx += 1

    # Stable, meaningful order: by reading index, non-content last.
    units.sort(key=lambda u: (u.reading_index if u.reading_index >= 0 else 10_000, u.key))
    shape_types = {el["id"]: str(el.get("shape_type", "rectangle") or "rectangle")
                   for el in elements if el["type"] == "shape"}
    return Analysis(canvas=canvas, units=units, roles=roles, element_unit=element_unit,
                    headline_font_size=headline_size, shape_types=shape_types)


# ---------------------------------------------------------------------------
# individual classifiers


def _is_background(el: dict[str, Any], canvas: Box) -> bool:
    if el["type"] == "text":
        return False
    box = Box.of(el)
    covered = canvas.intersection_area(box) / canvas.area
    if covered < BACKGROUND_COVER:
        return False
    # A huge, nearly transparent shape is a wash, which is still background-like.
    return True


def _is_panel(el: dict[str, Any], canvas: Box) -> bool:
    """A large flat shape: a colour block behind text, a side bar, a split
    background, a frame. It is a zone, not a sticker: layouts stretch it (flat
    colour has no aspect) and keep the content that sat on it on top."""
    if el["type"] != "shape" or el.get("group_id"):
        return False
    box = Box.of(el)
    if box.area <= 0:
        return False
    covered = canvas.intersection_area(box) / canvas.area
    rect = str(el.get("shape_type", "rectangle") or "rectangle") == "rectangle"
    if rect:
        spans_x = box.x <= PANEL_EDGE * canvas.w and box.right >= (1.0 - PANEL_EDGE) * canvas.w
        spans_y = box.y <= PANEL_EDGE * canvas.h and box.bottom >= (1.0 - PANEL_EDGE) * canvas.h
        return covered >= PANEL_MIN_COVER or spans_x or spans_y
    # A big ellipse is a panel only when it is solid and sits on the canvas;
    # a faint or bleeding one is decoration.
    opacity = float(el.get("opacity", 1.0))
    off = 1.0 - canvas.contains_fraction(box)
    return covered >= PANEL_MIN_COVER and opacity >= DECO_OPACITY and off < DECO_BLEED


def _is_decorative(el: dict[str, Any], canvas: Box) -> bool:
    if el["type"] == "text":
        return False
    if el.get("group_id"):
        return False
    box = Box.of(el)
    opacity = float(el.get("opacity", 1.0))
    if opacity < DECO_OPACITY:
        return True
    if box.area > 0:
        off = 1.0 - canvas.contains_fraction(box)
        if off >= DECO_BLEED:
            return True
    return False


def _assign_image_roles(images: list[dict[str, Any]], canvas: Box, roles: dict[str, str]) -> None:
    if not images:
        return
    scored: list[tuple[float, dict[str, Any]]] = []
    for el in images:
        box = Box.of(el)
        area = box.area / canvas.area
        if area > LOGO_MAX_AREA:
            continue
        cy = box.cy / canvas.h
        cx = box.cx / canvas.w
        score = 0.0
        if cy < 0.35:
            score += 2.0
        if abs(cx - 0.5) < 0.1:
            score += 0.5
        if cx < 0.25 or cx > 0.75:
            score += 0.5
        score -= area * 5.0
        if cy > 0.6:
            score -= 2.0   # bottom-dwelling small images are stickers/watermarks
        scored.append((score, el))
    logo = None
    if scored:
        scored.sort(key=lambda t: -t[0])
        if scored[0][0] > 0:
            logo = scored[0][1]
            roles[logo["id"]] = LOGO
    rest = [el for el in images if logo is None or el["id"] != logo["id"]]
    if rest:
        rest.sort(key=lambda el: -Box.of(el).area)
        biggest = rest[0]
        if Box.of(biggest).area / canvas.area >= HERO_MIN_AREA:
            roles[biggest["id"]] = HERO
            rest = rest[1:]
        for el in rest:
            roles[el["id"]] = IMAGE


def _assign_text_roles(texts: list[dict[str, Any]], canvas: Box, roles: dict[str, str]) -> float | None:
    if not texts:
        return None
    ordered = sorted(texts, key=lambda el: -float(el["font_size"]))
    headline = ordered[0]
    roles[headline["id"]] = HEADLINE
    h_size = float(headline["font_size"])
    h_box = Box.of(headline)
    h_color = _rgb(headline.get("color"))

    # A free-text CTA: bold, short, below the headline, in a colour of its
    # own. Several lines can look like that (section labels in an accent
    # colour); a design has one call to action, and it is the lowest one.
    cta_like = [
        el for el in ordered[1:]
        if el.get("font_weight") == "bold" and len(str(el.get("content", ""))) <= CTA_MAX_CHARS
        and Box.of(el).cy > h_box.cy and _rgb(el.get("color")) != h_color
        and not _fine_print_like(el, h_size)
    ]
    cta_id = max(cta_like, key=lambda el: Box.of(el).cy)["id"] if cta_like else None

    subhead_taken = False
    for el in ordered[1:]:
        box = Box.of(el)
        if _fine_print_like(el, h_size):
            roles[el["id"]] = FINE_PRINT
        elif el["id"] == cta_id:
            roles[el["id"]] = CTA
        elif not subhead_taken and box.cy > h_box.cy:
            roles[el["id"]] = SUBHEAD
            subhead_taken = True
        else:
            roles[el["id"]] = BODY
    return h_size


def _fine_print_like(el: dict[str, Any], headline_size: float) -> bool:
    size = float(el["font_size"])
    content = str(el.get("content", ""))
    return size <= FINE_PRINT_RATIO * headline_size and (
        size <= FINE_PRINT_MAX_PX or len(content) >= FINE_PRINT_MIN_CHARS
    )


def _assign_group_roles(groups: dict[str, list[dict[str, Any]]], canvas: Box,
                        headline_box: Box | None) -> dict[str, str]:
    out: dict[str, str] = {}
    button_like: list[tuple[str, Box]] = []
    for gid, members in groups.items():
        types = {el["type"] for el in members}
        box = Box.union(Box.of(el) for el in members)
        if "text" in types and ("shape" in types or "image" in types):
            button_like.append((gid, box))
            out[gid] = BADGE
        elif types == {"text"}:
            out[gid] = BODY
        elif "image" in types:
            out[gid] = IMAGE
        else:
            out[gid] = SHAPE
    # The CTA is the largest button-like group that sits below the headline
    # (or, with no headline, in the lower half of the canvas).
    candidates = []
    for gid, box in button_like:
        below = box.cy > headline_box.cy if headline_box else box.cy > canvas.h / 2
        if below:
            candidates.append((box.area, gid))
    if candidates:
        candidates.sort(reverse=True)
        out[candidates[0][1]] = CTA
    return out


def _readable_on(unit: Unit, panel: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    """Text in (nearly) the panel's own colour was not meant to be read on
    it (white copy half over a white card in a loosely built template): the
    panel must not be rebuilt around it."""
    fill = _rgb(panel.get("fill_color"))
    if fill is None:
        return True
    texts = [by_id[i] for i in unit.ids if by_id[i]["type"] == "text"]
    if not texts:
        return True
    for el in texts:
        rgb = _rgb(el.get("color"))
        if rgb is None or contrast_ratio(rgb, fill) >= PANEL_TEXT_CONTRAST:
            return True
    return False


def _luminance(rgb: tuple[int, int, int]) -> float:
    def ch(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _anchors(box: Box, canvas: Box) -> tuple[str, str]:
    l, r = box.x / canvas.w, (canvas.w - box.right) / canvas.w
    t, b = box.y / canvas.h, (canvas.h - box.bottom) / canvas.h
    cx, cy = box.cx / canvas.w, box.cy / canvas.h
    if abs(cx - 0.5) < CENTER_TOL_X:
        ax = "center"
    elif l < EDGE_HUG and l <= r:
        ax = "left"
    elif r < EDGE_HUG:
        ax = "right"
    else:
        ax = "fluid"
    if t < EDGE_HUG and t <= b:
        ay = "top"
    elif b < EDGE_HUG:
        ay = "bottom"
    elif abs(cy - 0.5) < CENTER_TOL_Y:
        ay = "center"
    else:
        ay = "fluid"
    return ax, ay


def _rgb(color: Any) -> tuple[int, int, int] | None:
    if not isinstance(color, str):
        return None
    inner = color[color.find("(") + 1: color.rfind(")")]
    parts = [p.strip() for p in inner.split(",")]
    try:
        return tuple(int(float(p)) for p in parts[:3])  # type: ignore[return-value]
    except ValueError:
        return None
