"""Seeded adversarial synthetic designs (schema v0.9) for the eval harness and
the metamorphic tests.

    .venv/bin/python -m eval.synth --n 200 --seed 1          # -> eval/data/synth/{designs,index.json}
    .venv/bin/python -m eval.run_eval --synthetic 200 --seed 1 --workers 4 --name synth

Why: Crello gives us real layouts but none of the traps the brief promises for
the hidden Level 3 set (run-on headlines, variable badge counts, rotated
elements, a missing asset) and none of the plainly hostile input a robust
engine must survive (empty text, zero-size boxes, negative coordinates,
1x1 targets). This module makes those on demand, reproducibly, with every
property recorded so the report can slice defect rates by it.

Two kinds of output:

  generate_corpus(n, seed)   n designs sampled from `random_spec`: canvases in
                             all four ratio families, 2-45 elements, image /
                             shape / no background, a text panel, logo in any
                             corner or centre, hero present / absent / with a
                             missing asset, headlines from two words to 140+
                             characters including unbreakable words, 0-4
                             subheads, CTA as free text or shape+label group
                             (badge-style insets), 0-6 badges in rows, rotated
                             ribbons / badges / headlines (5-45 deg), decorative
                             ellipses (opacity 0.1-0.5) bleeding off canvas,
                             letter spacing, line height, style_runs,
                             max_lines, text_align, z-index ties, tiny
                             elements, a near-duplicate shadow headline.
  nasty_cases()              deterministic hostile inputs with their own
                             targets: empty content, font_size 0.5 / 400,
                             zero-size elements, negative coordinates, every
                             asset missing, one element, everything in one
                             group, minimal fields only, rotation 90 / 360 /
                             725, unicode and newlines, huge letter spacing,
                             45 elements, identical stacked texts; targets
                             1x1, 4000x4000, identical, +3 % width.

Every design is self-consistent the way a designer's file is: text boxes are
sized with the engine's TextMeasurer so the source text fits (except where a
single word is wider than the canvas, which is recorded in the props), ids are
opaque hex strings (no role hints), z_index follows paint order. `validate()`
checks the schema rules the organizers' structural pass will check.

Nothing here touches engine/; the generator only *reads* engine.textfit to
size text boxes like the renderer wraps them.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.textfit import default_measurer  # noqa: E402
from eval.crello_convert import DATA_DIR, ratio_family  # noqa: E402

SYNTH_DIR = DATA_DIR / "synth"

ASSET_BG = "solstice_bg_gradient.png"
ASSET_LOGO = "solstice_logo_lockup.png"
ASSET_HERO = "solstice_bottle.png"
MISSING_ASSET = "solstice_holiday_badge_2025.png"     # the Level 3 trick, on purpose
SERIF = "Solstice Serif"
SANS = "Solstice Sans"

CANVASES: dict[str, list[tuple[int, int]]] = {
    "tall": [(1080, 1350), (1080, 1920), (600, 1200), (1000, 1500), (1240, 1754), (720, 1280)],
    "square": [(1080, 1080), (800, 800), (500, 500), (1200, 1200)],
    "wide": [(1200, 628), (1600, 900), (1280, 720), (1920, 1080), (1024, 512)],
    "banner": [(1600, 400), (728, 90), (970, 250), (1584, 396), (820, 312), (320, 50)],
}

# palette (the brand kit's colours plus a couple of accents)
PLUM = (43, 27, 46)
CREAM = (245, 241, 234)
WHITE = (255, 255, 255)
ORANGE = (232, 106, 58)
GOLD = (240, 178, 66)
RED = (220, 60, 50)
INK = (34, 34, 34)
TEAL = (30, 110, 120)
ACCENTS = [ORANGE, GOLD, RED, TEAL]

HEAD_WORDS = ["Chase", "the", "Light", "Golden", "Hour", "Botanical", "Sparkling", "Solstice", "Summer",
              "Limited", "Batch", "Collection", "Introducing", "All-New", "Crafted", "Gatherings", "Wild",
              "Honey", "Blood", "Orange", "Zest", "Smoked", "Rosemary", "Sunset", "Sale", "Fresh", "Taste",
              "Bright", "Days", "Evening", "Glow", "Exclusively", "Peak", "Lingers", "Whisper", "Infusions"]
UNBREAKABLE = ["SUPERLIMITEDBOTANICALSPARKLINGEDITION", "Chase-the-Light-Golden-Hour-Collection-2026",
               "www.solsticebotanicals.com/goldenhour/limited-batch", "#GOLDENHOURGATHERINGS2026",
               "Unbelievablylongbrandnamewithoutanyspaces"]
SENTENCES = [
    "Small-batch botanical infusions blended with wild honey, blood orange zest, and a whisper of smoked rosemary.",
    "Bottled at the peak of golden hour for a taste that lingers long after sunset.",
    "Now pouring at select cafes and rooftop bars across the city.",
    "Zero added sugar, naturally sparkling, endlessly refreshing.",
    "Available for a limited time while the season lasts.",
    "Made with real fruit and nothing artificial.",
    "Join the club and get free delivery on your first order.",
    "Pairs beautifully with long evenings and good company.",
]
CTA_LABELS = ["Shop Now", "Shop the Summer Line", "Learn More", "Get Yours", "Order Today",
              "Discover the Collection", "Try It", "Buy", "Reserve a Bottle", "Find a Store Near You"]
BADGE_LABELS = ["LIMITED EDITION", "AWARD WINNING 2026", "SMALL BATCH", "NEW", "NEW FLAVOR", "VEGAN",
                "0% SUGAR", "SINCE 1998", "GLUTEN FREE", "BEST SELLER", "ORGANIC", "LOW CAL"]
RIBBON_LABELS = ["SUNSET SALE", "NEW", "30% OFF", "LAST CHANCE", "FRESH DROP"]
LEGAL = ("Please drink responsibly. Botanical Sparkling Co., 2026. Void where prohibited. "
         "See solstice.com/terms for full details.")

HEADLINE_CLASSES = ["two_words", "short", "medium", "long", "unbreakable"]
LOGO_POSITIONS = ["tl", "tc", "tr", "bl", "bc", "br", "c"]


def rgba(c: tuple[int, int, int], a: float = 1.0) -> str:
    return f"rgba({c[0]},{c[1]},{c[2]},{a:g})"


# ---------------------------------------------------------------------------
# spec


@dataclass
class Spec:
    """Everything that varies between synthetic designs. `random_spec` draws
    one; `build` turns it into a design. All fields are recorded in the
    design's `props` so the report can slice by them."""

    seed: int = 0
    family: str = "tall"
    width: int = 1080
    height: int = 1350
    theme: str = "dark"              # dark: light text on a dark ground; light: the reverse
    background: str = "image"        # image (gradient, fit cover) | shape (opaque rect) | none
    panel: bool = False              # opaque-ish rectangle behind the text column
    logo_pos: str | None = "tc"      # tl tc tr bl bc br c, or None for no logo
    hero: str = "present"            # none | present | missing_asset
    headline_len: str = "short"      # two_words | short | medium | long | unbreakable
    headline_rotated: bool = False   # +-5..12 degrees
    n_subs: int = 1                  # subhead / body texts, 0-4
    cta: str = "group"               # none | text | group | group_inset
    n_badges: int = 0                # 0-6, pills in a row (wraps to two rows)
    badge_rotated: bool = False      # one badge rotated 10-30 degrees
    ribbon: bool = False             # rotated shape + label group in a top corner (5-45 degrees)
    n_decor: int = 0                 # decorative ellipses, opacity 0.1-0.5, bleeding off canvas
    n_tiny: int = 0                  # dots / hairlines (1-6 px)
    n_extra_shapes: int = 0          # accent squares / bars on the margins
    fine_print: bool = True
    shadow_text: bool = False        # near-duplicate headline offset by 3 px (drop shadow)
    style_runs: bool = False         # two-colour headline
    max_lines: bool = False          # max_lines on the first subhead
    letter_spacing: float = 0.0      # px, on headline (scaled by the generator per role)
    line_height: float = 1.2
    text_align: str = "center"
    z_tie: bool = False              # all content shares one z_index (like the shipped samples)
    density: str = "normal"          # minimal | light | normal | heavy | max  (informational)
    column_width: float = 0.9        # fraction of the available width the text column uses
    hero_side: str = "left"          # wide canvases: where the hero sits

    @property
    def canvas(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}


def random_spec(rng: random.Random, seed: int | None = None, family: str | None = None) -> Spec:
    fam = family or rng.choice(["tall", "square", "wide", "banner"])
    w, h = rng.choice(CANVASES[fam])
    density = rng.choices(["minimal", "light", "normal", "heavy", "max"], weights=[1, 2, 4, 2, 1])[0]
    d = {"minimal": 0, "light": 1, "normal": 2, "heavy": 3, "max": 4}[density]
    theme = rng.choice(["dark", "dark", "light"])
    background = rng.choice(["image", "shape", "none"]) if d else rng.choice(["none", "shape"])
    if theme == "dark" and background == "none":
        theme = "light"                       # a bare canvas renders white
    if background == "image":
        theme = "dark"                        # the gradient asset is dark
    spec = Spec(
        seed=seed if seed is not None else rng.randrange(1 << 30),
        family=fam, width=w, height=h, theme=theme, background=background,
        panel=d >= 2 and rng.random() < 0.3,
        logo_pos=rng.choice(LOGO_POSITIONS) if (d >= 1 and rng.random() < 0.85) else None,
        hero=(rng.choices(["none", "present", "missing_asset"], weights=[2, 6, 2])[0] if d >= 1 else "none"),
        headline_len=rng.choices(HEADLINE_CLASSES, weights=[2, 4, 3, 2, 1])[0],
        headline_rotated=d >= 2 and rng.random() < 0.12,
        n_subs=[0, rng.choice([0, 1]), rng.choice([1, 2]), rng.choice([2, 3]), rng.choice([3, 4])][d],
        cta=rng.choices(["none", "text", "group", "group_inset"], weights=[1, 2, 4, 3])[0] if d else "text",
        n_badges=[0, rng.choice([0, 1]), rng.choice([0, 1, 2, 3]), rng.choice([2, 3, 4]), rng.choice([4, 5, 6])][d],
        badge_rotated=d >= 2 and rng.random() < 0.2,
        ribbon=d >= 2 and rng.random() < 0.35,
        n_decor=[0, rng.choice([0, 1]), rng.choice([0, 1, 2]), rng.choice([1, 2, 3]), rng.choice([3, 4, 6])][d],
        n_tiny=[0, 0, rng.choice([0, 1]), rng.choice([1, 2]), rng.choice([2, 4])][d],
        n_extra_shapes=[0, 0, rng.choice([0, 1]), rng.choice([0, 2, 4]), rng.choice([4, 8])][d],
        fine_print=d >= 2 and rng.random() < 0.7,
        shadow_text=d >= 2 and rng.random() < 0.15,
        style_runs=rng.random() < 0.3,
        max_lines=rng.random() < 0.25,
        letter_spacing=rng.choice([0.0, 0.0, 0.0, 1.0, 2.0, 4.0, 6.0]),
        line_height=rng.choice([0.9, 1.0, 1.1, 1.2, 1.2, 1.35, 1.6]),
        text_align=rng.choices(["left", "center", "right"], weights=[3, 5, 1])[0],
        z_tie=rng.random() < 0.4,
        density=density,
        column_width=rng.uniform(0.7, 1.0),
        hero_side=rng.choice(["left", "right"]),
    )
    if d == 0:
        # two to four elements: headline + CTA, maybe a background
        spec.logo_pos = None
        spec.n_badges = 0
        spec.fine_print = False
    return spec


# ---------------------------------------------------------------------------
# building blocks


class _Block:
    """One slot in a column / row flow. `measure(scale)` -> (w, h) for a
    content scale (fonts and image sizes shrink with it); `emit(x, y, scale)`
    appends the elements."""

    def __init__(self, kind: str, measure: Callable[[float], tuple[float, float]],
                 emit: Callable[[float, float, float], None], align: str = "center",
                 shrinks: bool = True) -> None:
        self.kind = kind
        self.measure = measure
        self.emit = emit
        self.align = align
        self.shrinks = shrinks


class _Builder:
    def __init__(self, spec: Spec, rng: random.Random) -> None:
        self.spec = spec
        self.rng = rng
        self.W, self.H = float(spec.width), float(spec.height)
        self.m = default_measurer()
        self.elements: list[dict[str, Any]] = []
        self._ids: set[str] = set()
        self._z = 0
        self.notes: dict[str, Any] = {}
        unit = math.sqrt(self.W * self.H) / 30.0
        self.unit = max(9.0, unit)
        self.ink = WHITE if spec.theme == "dark" else INK
        self.ink_soft = rgba(WHITE, 0.85) if spec.theme == "dark" else rgba(INK, 0.8)
        self.accent = rng.choice(ACCENTS)
        self.margin = 0.06 * min(self.W, self.H) if spec.family != "banner" else 0.08 * self.H
        self.gap = 0.022 * self.H if spec.family != "banner" else 0.06 * self.W
        # text blocks remember their boxes so a panel can be drawn behind them
        self.text_boxes: list[tuple[float, float, float, float]] = []

    # -- helpers -----------------------------------------------------------

    def new_id(self) -> str:
        while True:
            i = f"e{self.rng.randrange(16 ** 6):06x}"
            if i not in self._ids:
                self._ids.add(i)
                return i

    def z(self, fixed: int | None = None) -> int:
        if fixed is not None:
            return fixed
        self._z += 1
        return 5 if self.spec.z_tie else self._z

    def add(self, el: dict[str, Any]) -> dict[str, Any]:
        el.setdefault("id", self.new_id())
        el.setdefault("rotation", 0)
        el.setdefault("opacity", 1)
        el.setdefault("z_index", self.z())
        el.setdefault("group_id", None)
        for k in ("x", "y", "width", "height"):
            el[k] = round(float(el[k]), 2)
        self.elements.append(el)
        return el

    def text(self, content: str, font: float, x: float, y: float, w: float, h: float, *,
             family: str = SANS, weight: str = "regular", color: str | None = None,
             align: str | None = None, group: str | None = None, rotation: float = 0,
             letter_spacing: float = 0.0, line_height: float | None = None, z: int | None = None,
             style_runs: list[dict[str, Any]] | None = None, max_lines: int | None = None,
             remember: bool = True) -> dict[str, Any]:
        el: dict[str, Any] = {
            "type": "text", "x": x, "y": y, "width": w, "height": h,
            "content": content, "font_family": family, "font_size": round(float(font), 2),
            "font_weight": weight, "color": color or rgba(self.ink),
            "text_align": align or self.spec.text_align,
            "line_height": line_height if line_height is not None else self.spec.line_height,
            "letter_spacing": round(letter_spacing, 2),
        }
        if style_runs:
            el["style_runs"] = style_runs
        if max_lines:
            el["max_lines"] = max_lines
        if group:
            el["group_id"] = group
        if rotation:
            el["rotation"] = rotation
        if z is not None:
            el["z_index"] = z
        if remember:
            self.text_boxes.append((x, y, w, h))
        return self.add(el)

    def shape(self, kind: str, x: float, y: float, w: float, h: float, fill: str, *, group: str | None = None,
              rotation: float = 0, opacity: float = 1, radius: float = 0, z: int | None = None,
              stroke: str | None = None, stroke_width: float = 0) -> dict[str, Any]:
        el: dict[str, Any] = {"type": "shape", "x": x, "y": y, "width": w, "height": h, "shape_type": kind,
                              "fill_color": fill, "stroke_color": stroke, "stroke_width": stroke_width,
                              "corner_radius": round(radius, 2)}
        if group:
            el["group_id"] = group
        if rotation:
            el["rotation"] = rotation
        if opacity != 1:
            el["opacity"] = opacity
        if z is not None:
            el["z_index"] = z
        return self.add(el)

    def image(self, asset: str, x: float, y: float, w: float, h: float, *, fit: str = "contain",
              z: int | None = None, group: str | None = None, opacity: float = 1) -> dict[str, Any]:
        el: dict[str, Any] = {"type": "image", "x": x, "y": y, "width": w, "height": h, "asset_id": asset, "fit": fit}
        if z is not None:
            el["z_index"] = z
        if group:
            el["group_id"] = group
        if opacity != 1:
            el["opacity"] = opacity
        return self.add(el)

    def text_proto(self, content: str, font: float, family: str = SANS, weight: str = "regular",
                   letter_spacing: float = 0.0, line_height: float | None = None,
                   max_lines: int | None = None) -> dict[str, Any]:
        p = {"content": content, "font_family": family, "font_size": font, "font_weight": weight,
             "letter_spacing": letter_spacing,
             "line_height": line_height if line_height is not None else self.spec.line_height}
        if max_lines:
            p["max_lines"] = max_lines
        return p

    def label_height(self, proto: dict[str, Any], font: float) -> float:
        """Height of a one-line label box (ascent + descent and a hair)."""
        return self.m.layout(proto, font, 1e9).height + 0.1 * font

    def measure_text(self, proto: dict[str, Any], font: float, width: float) -> tuple[float, float]:
        """(box width, box height) a text needs at `font` in a column `width`:
        the natural wrapped height plus a little slack; the width grows to a
        single over-wide word (capped at the canvas) like a designer would
        drag the box wider."""
        w = width
        lay = self.m.layout(proto, font, w)
        # Widening the box re-wraps the text (letter spacing is not part of
        # the wrap decision, so a wider box can hold wider lines): iterate
        # to a fixed point, capped at the canvas width.
        for _ in range(6):
            if lay.max_width <= w + 0.5 or w >= self.W:
                break
            w = min(self.W, lay.max_width + 2.0)
            lay = self.m.layout(proto, font, w)
        if lay.max_width > w + 0.5:
            self.notes["src_overflow"] = True
        return w, lay.height + 0.15 * font

    # -- content -------------------------------------------------------------

    def headline_text(self) -> str:
        r, cls = self.rng, self.spec.headline_len
        if cls == "two_words":
            return " ".join(r.sample(HEAD_WORDS, 2))
        if cls == "short":
            return " ".join(r.sample(HEAD_WORDS, r.randint(3, 6)))
        if cls == "medium":
            return " ".join(r.sample(HEAD_WORDS, r.randint(8, 15)))
        if cls == "long":
            words: list[str] = []
            while len(" ".join(words)) < r.randint(140, 190):
                words.append(r.choice(HEAD_WORDS))
            return " ".join(words)
        # unbreakable: one giant word, alone or inside a sentence
        word = r.choice(UNBREAKABLE)
        if r.random() < 0.5:
            return word
        return " ".join(r.sample(HEAD_WORDS, 2)) + " " + word + " " + r.choice(HEAD_WORDS)

    # -- blocks --------------------------------------------------------------

    def block_logo(self, width_frac: float) -> _Block:
        base_w = width_frac
        pos = self.spec.logo_pos or "tc"
        align = {"l": "left", "c": "center", "r": "right"}[pos[-1]]

        def measure(s: float) -> tuple[float, float]:
            w = base_w * (0.6 + 0.4 * s)
            return w, w / 3.0

        def emit(x: float, y: float, s: float) -> None:
            w, h = measure(s)
            self.image(ASSET_LOGO, x, y, w, h)

        return _Block("logo", measure, emit, align)

    def block_hero(self, side: float) -> _Block:
        def measure(s: float) -> tuple[float, float]:
            return side * s, side * s

        def emit(x: float, y: float, s: float) -> None:
            w, h = measure(s)
            asset = ASSET_HERO if self.spec.hero == "present" else MISSING_ASSET
            self.image(asset, x, y, w, h)

        return _Block("hero", measure, emit, "center")

    def block_text(self, kind: str, content: str, font: float, col_w: float, *, family: str = SANS,
                   weight: str = "regular", color: str | None = None, letter_spacing: float = 0.0,
                   max_lines: int | None = None, style_runs: list[dict[str, Any]] | None = None,
                   rotation: float = 0.0, shadow: bool = False, min_font: float = 6.0) -> _Block:
        proto = self.text_proto(content, font, family, weight, letter_spacing, max_lines=max_lines)
        align = self.spec.text_align

        def size_at(s: float) -> tuple[float, float, float]:
            f = max(min_font, font * s)
            if max_lines:
                # keep the source honest: shrink until the cap holds
                f = max(min_font, self.m.fit_font_size(proto, col_w, 1e9, f, min_font))
            w, h = self.measure_text(proto, f, col_w)
            return f, w, h

        def measure(s: float) -> tuple[float, float]:
            _, w, h = size_at(s)
            return w, h

        def emit(x: float, y: float, s: float) -> None:
            f, w, h = size_at(s)
            ls = letter_spacing * f / font if letter_spacing else 0.0
            if shadow:
                self.text(content, f, x + 3, y + 3, w, h, family=family, weight=weight,
                          color=rgba(INK if self.spec.theme == "dark" else GOLD, 0.6), align=align,
                          letter_spacing=ls, style_runs=None, max_lines=max_lines, remember=False)
            el = self.text(content, f, x, y, w, h, family=family, weight=weight, color=color, align=align,
                           letter_spacing=ls, style_runs=style_runs, max_lines=max_lines, rotation=rotation)
            self.notes.setdefault("roles", {})[el["id"]] = kind

        return _Block(kind, measure, emit, align)

    def block_cta(self, font: float) -> _Block:
        label = self.rng.choice(CTA_LABELS)
        kind = self.spec.cta
        proto = self.text_proto(label, font, SANS, "bold")
        gid = f"g{self.rng.randrange(16 ** 4):04x}"

        def measure(s: float) -> tuple[float, float]:
            f = max(6.0, font * s)
            tw = self.m.layout(proto, f, 1e9).max_width
            if kind == "text":
                return tw + 4, f * 1.5
            return tw + 3.2 * f, f * 2.6

        def emit(x: float, y: float, s: float) -> None:
            f = max(6.0, font * s)
            w, h = measure(s)
            if kind == "text":
                el = self.text(label, f, x, y, w, h, weight="bold", color=rgba(self.accent) if self.spec.theme == "light" else rgba(GOLD), align="center")
                self.notes.setdefault("roles", {})[el["id"]] = "cta"
                return
            self.shape("rectangle", x, y, w, h, rgba(self.accent), group=gid, radius=h / 2)
            th = self.label_height(proto, f)
            if kind == "group_inset":
                # badge-style inset: label box is a strip inside the pill
                self.text(label, f, x + 0.6 * f, y + (h - th) / 2, w - 1.2 * f, th, weight="bold",
                          color=rgba(WHITE), align="center", group=gid, remember=False)
            else:
                self.text(label, f, x, y + (h - th) / 2, w, th, weight="bold", color=rgba(WHITE),
                          align="center", group=gid, remember=False)

        return _Block("cta", measure, emit, "center")

    def block_badges(self, font: float, col_w: float) -> _Block:
        n = self.spec.n_badges
        labels = self.rng.sample(BADGE_LABELS, n)
        protos = [self.text_proto(t, font, SANS, "bold") for t in labels]
        rotate_idx = self.rng.randrange(n) if self.spec.badge_rotated else -1

        def pills(s: float) -> list[tuple[float, float]]:
            f = max(5.0, font * s)
            return [(self.m.layout(p, f, 1e9).max_width + 2.2 * f, f * 2.5) for p in protos]

        def rows(s: float) -> list[list[int]]:
            ps = pills(s)
            g = 0.5 * ps[0][1]
            out: list[list[int]] = [[]]
            x = 0.0
            for i, (w, _) in enumerate(ps):
                if out[-1] and x + w > col_w:
                    out.append([])
                    x = 0.0
                out[-1].append(i)
                x += w + g
            return out

        def measure(s: float) -> tuple[float, float]:
            ps = pills(s)
            rs = rows(s)
            g = 0.5 * ps[0][1]
            w = max(sum(ps[i][0] for i in r) + g * (len(r) - 1) for r in rs)
            h = len(rs) * ps[0][1] + (len(rs) - 1) * g
            return min(w, col_w), h

        def emit(x0: float, y0: float, s: float) -> None:
            f = max(5.0, font * s)
            ps = pills(s)
            g = 0.5 * ps[0][1]
            y = y0
            for r in rows(s):
                row_w = sum(ps[i][0] for i in r) + g * (len(r) - 1)
                x = x0 + {"left": 0.0, "center": (measure(s)[0] - row_w) / 2, "right": measure(s)[0] - row_w}[self.spec.text_align]
                for i in r:
                    w, h = ps[i]
                    gid = f"g{self.rng.randrange(16 ** 4):04x}"
                    rot = self.rng.choice([-1, 1]) * self.rng.uniform(10, 30) if i == rotate_idx else 0
                    fill = rgba(self.rng.choice([self.accent, PLUM if self.spec.theme == "dark" else TEAL]))
                    self.shape("rectangle", x, y, w, h, fill, group=gid, radius=h / 2, rotation=rot)
                    th = self.label_height(protos[i], f)
                    self.text(labels[i], f, x, y + (h - th) / 2, w, th, weight="bold", color=rgba(WHITE),
                              align="center", group=gid, rotation=rot, remember=False)
                    x += w + g
                y += ps[0][1] + g

        return _Block("badges", measure, emit, "center")

    # -- flows ---------------------------------------------------------------

    def flow_column(self, blocks: list[_Block], rx: float, ry: float, rw: float, rh: float) -> None:
        """Stack blocks top to bottom inside the region, shrinking content
        until it fits (up to a point: an overfull source is a legitimate
        adversarial input and is recorded in the notes)."""
        if not blocks:
            return
        scale = 1.0
        gap = self.gap
        for _ in range(6):
            sizes = [b.measure(scale) for b in blocks]
            total = sum(h for _, h in sizes) + gap * (len(blocks) - 1)
            if total <= rh:
                break
            scale *= max(0.5, rh / total) * 0.96
        sizes = [b.measure(scale) for b in blocks]
        total = sum(h for _, h in sizes) + gap * (len(blocks) - 1)
        if total > rh + 1:
            self.notes["src_overfull"] = True
        leftover = max(0.0, rh - total)
        mode = self.rng.choice(["top", "center", "spread"])
        y = ry + (leftover / 2 if mode == "center" else 0.0)
        extra = leftover / max(1, len(blocks) - 1) if mode == "spread" and len(blocks) > 1 else 0.0
        for b, (w, h) in zip(blocks, sizes):
            w = min(w, rw) if w > rw and b.kind != "headline" else w
            x = {"left": rx, "center": rx + (rw - w) / 2, "right": rx + rw - w}[b.align]
            x = max(0.0, min(x, self.W - w))
            b.emit(x, y, scale)
            y += h + gap + extra
        self.notes["content_scale"] = round(scale, 3)

    def flow_row(self, blocks: list[_Block], rx: float, ry: float, rw: float, rh: float) -> None:
        """Banner: blocks left to right, each vertically centred."""
        scale = 1.0
        gap = self.gap
        for _ in range(8):
            sizes = [b.measure(scale) for b in blocks]
            total_w = sum(w for w, _ in sizes) + gap * (len(blocks) - 1)
            max_h = max(h for _, h in sizes)
            if total_w <= rw and max_h <= rh:
                break
            scale *= max(0.5, min(rw / total_w, rh / max_h)) * 0.96
        sizes = [b.measure(scale) for b in blocks]
        total_w = sum(w for w, _ in sizes) + gap * (len(blocks) - 1)
        if total_w > rw + 1 or max(h for _, h in sizes) > rh + 1:
            self.notes["src_overfull"] = True
        extra = max(0.0, rw - total_w) / max(1, len(blocks) - 1) if len(blocks) > 1 else 0.0
        x = rx if len(blocks) > 1 else rx + max(0.0, rw - total_w) / 2
        for b, (w, h) in zip(blocks, sizes):
            y = ry + max(0.0, rh - h) / 2
            b.emit(x, y, scale)
            x += w + gap + extra
        self.notes["content_scale"] = round(scale, 3)


# ---------------------------------------------------------------------------
# the design


def build(spec: Spec) -> dict[str, Any]:
    """A schema-valid design from a spec. Deterministic for a given spec."""
    rng = random.Random(f"{spec.seed}|{spec.family}|{spec.width}x{spec.height}|{spec.headline_len}")
    b = _Builder(spec, rng)
    W, H, m, u = b.W, b.H, b.margin, b.unit

    # background
    if spec.background == "image":
        b.image(ASSET_BG, 0, 0, W, H, fit="cover", z=0)
    elif spec.background == "shape":
        b.shape("rectangle", 0, 0, W, H, rgba(PLUM if spec.theme == "dark" else CREAM), z=0)

    # decorative ellipses, partially off canvas
    for _ in range(spec.n_decor):
        side = rng.uniform(0.15, 0.5) * min(W, H)
        edge = rng.choice(["left", "right", "top", "bottom", "corner"])
        if edge == "left":
            x, y = -side * rng.uniform(0.3, 0.7), rng.uniform(-0.2, 0.9) * H
        elif edge == "right":
            x, y = W - side * rng.uniform(0.3, 0.7), rng.uniform(-0.2, 0.9) * H
        elif edge == "top":
            x, y = rng.uniform(-0.2, 0.9) * W, -side * rng.uniform(0.3, 0.7)
        elif edge == "bottom":
            x, y = rng.uniform(-0.2, 0.9) * W, H - side * rng.uniform(0.3, 0.7)
        else:
            x, y = rng.choice([-side * 0.5, W - side * 0.5]), rng.choice([-side * 0.5, H - side * 0.5])
        b.shape("ellipse", x, y, side, side * rng.uniform(0.7, 1.3), rgba(rng.choice(ACCENTS)),
                opacity=round(rng.uniform(0.1, 0.5), 2), z=1)

    # fonts per role
    head_font = u * rng.uniform(1.2, 2.0)
    if spec.headline_len in ("long", "unbreakable"):
        head_font *= 0.75
    sub_font = u * rng.uniform(0.5, 0.7)
    body_font = u * rng.uniform(0.4, 0.55)
    cta_font = u * rng.uniform(0.5, 0.65)
    badge_font = u * rng.uniform(0.33, 0.45)
    fine_font = max(7.0, u * 0.3)
    head_family = rng.choice([SERIF, SERIF, SANS])

    headline = b.headline_text()
    runs = None
    if spec.style_runs and len(headline) > 4:
        k = headline.find(" ", 3)
        k = k if k > 0 else len(headline) // 2
        runs = [{"start": 0, "end": k, "color": rgba(GOLD if spec.theme == "dark" else ORANGE)}]
        if rng.random() < 0.5:
            runs.append({"start": k, "end": len(headline), "font_weight": "bold"})

    def text_blocks(col_w: float) -> list[_Block]:
        blocks = [b.block_text("headline", headline, head_font, col_w, family=head_family, weight="bold",
                               letter_spacing=spec.letter_spacing, style_runs=runs,
                               rotation=(rng.choice([-1, 1]) * rng.uniform(5, 12) if spec.headline_rotated else 0.0),
                               shadow=spec.shadow_text)]
        for i in range(spec.n_subs):
            if i == 0:
                content = rng.choice(SENTENCES)
                blocks.append(b.block_text("subhead", content, sub_font, col_w, color=b.ink_soft,
                                           max_lines=rng.choice([1, 2, 3]) if spec.max_lines else None))
            else:
                content = " ".join(rng.sample(SENTENCES, rng.randint(1, 3)))
                blocks.append(b.block_text("body", content, body_font, col_w, color=b.ink_soft))
        return blocks

    logo_in_flow = spec.logo_pos in ("tl", "tc", "tr", "c")
    fine_block = b.block_text("fine_print", LEGAL, fine_font, W - 2 * m, color=rgba(WHITE, 0.6) if spec.theme == "dark" else rgba(INK, 0.6)) if spec.fine_print else None

    if spec.family in ("tall", "square"):
        col_w = (W - 2 * m) * spec.column_width
        rx = m + (W - 2 * m - col_w) / 2
        ry, rh = m, H - 2 * m
        if spec.fine_print:
            rh -= fine_font * 2.5
        if spec.logo_pos in ("bl", "bc", "br"):
            rh -= col_w * 0.3 / 3 + b.gap
        blocks: list[_Block] = []
        if logo_in_flow and spec.logo_pos != "c":
            blocks.append(b.block_logo(col_w * rng.uniform(0.25, 0.4)))
        if spec.hero != "none":
            blocks.append(b.block_hero(min(col_w, rh) * rng.uniform(0.3, 0.5)))
        if spec.logo_pos == "c":
            blocks.append(b.block_logo(col_w * rng.uniform(0.25, 0.4)))
        blocks += text_blocks(col_w)
        if spec.n_badges:
            blocks.append(b.block_badges(badge_font, col_w))
        if spec.cta != "none":
            blocks.append(b.block_cta(cta_font))
        b.flow_column(blocks, rx, ry, col_w, rh)
    elif spec.family == "wide":
        hero_w = W * 0.4 if spec.hero != "none" else 0.0
        col_w = (W - 2 * m - hero_w) * spec.column_width
        if spec.hero != "none":
            side = min(hero_w - m, H - 2 * m) * rng.uniform(0.7, 0.95)
            hx = m + (hero_w - m - side) / 2 if spec.hero_side == "left" else W - m - (hero_w - m - side) / 2 - side
            b.block_hero(side).emit(hx, (H - side) / 2, 1.0)
        rx = (m + hero_w if spec.hero_side == "left" else m) + (W - 2 * m - hero_w - col_w) / 2
        ry, rh = m, H - 2 * m
        if spec.fine_print:
            rh -= fine_font * 2.5
        blocks = []
        if logo_in_flow:
            blocks.append(b.block_logo(col_w * rng.uniform(0.25, 0.4)))
        blocks += text_blocks(col_w)
        if spec.n_badges:
            blocks.append(b.block_badges(badge_font, col_w))
        if spec.cta != "none":
            blocks.append(b.block_cta(cta_font))
        b.flow_column(blocks, rx, ry, col_w, rh)
    else:  # banner: one row
        rx, ry, rw, rh = m, m, W - 2 * m, H - 2 * m
        if spec.fine_print:
            rh -= fine_font * 1.8
        blocks = []
        if spec.logo_pos:
            blocks.append(b.block_logo(W * rng.uniform(0.08, 0.14)))
        if spec.hero != "none":
            blocks.append(b.block_hero(rh * rng.uniform(0.8, 1.0)))
        col_w = W * rng.uniform(0.28, 0.42) * spec.column_width
        col_blocks = text_blocks(col_w)

        def col_measure(s: float) -> tuple[float, float]:
            sizes = [bl.measure(s) for bl in col_blocks]
            return max(w for w, _ in sizes), sum(h for _, h in sizes) + 0.3 * b.gap * (len(sizes) - 1)

        def col_emit(x: float, y: float, s: float) -> None:
            for bl in col_blocks:
                w, h = bl.measure(s)
                bl.emit(x, y, s)
                y += h + 0.3 * b.gap

        blocks.append(_Block("text_column", col_measure, col_emit))
        if spec.n_badges:
            blocks.append(b.block_badges(badge_font, W * 0.22))
        if spec.cta != "none":
            blocks.append(b.block_cta(cta_font))
        b.flow_row(blocks, rx, ry, rw, rh)

    # logo in a bottom corner (absolute)
    if spec.logo_pos in ("bl", "bc", "br"):
        lw = W * rng.uniform(0.15, 0.28)
        lh = lw / 3
        ly = H - m - lh - (fine_font * 2.5 if spec.fine_print else 0)
        lx = {"bl": m, "bc": (W - lw) / 2, "br": W - m - lw}[spec.logo_pos]
        b.image(ASSET_LOGO, lx, ly, lw, lh)

    # fine print along the bottom edge
    if fine_block is not None:
        w, h = fine_block.measure(1.0)
        fine_block.emit((W - min(w, W - 2 * m)) / 2, H - 0.4 * m - h, 1.0)

    # ribbon: rotated shape + label in a top corner
    if spec.ribbon:
        label = rng.choice(RIBBON_LABELS)
        f = u * 0.5
        proto = b.text_proto(label, f, SANS, "bold")
        rw_ = b.m.layout(proto, f, 1e9).max_width + 2.5 * f
        rh_ = f * 2.4
        rot = rng.choice([-1, 1]) * rng.uniform(5, 45)
        rx_ = rng.choice([0.02 * W, W - rw_ - 0.02 * W])
        gid = f"g{rng.randrange(16 ** 4):04x}"
        b.shape("rectangle", rx_, 0.02 * H, rw_, rh_, rgba(RED), group=gid, rotation=round(rot, 1))
        th = b.label_height(proto, f)
        b.text(label, f, rx_, 0.02 * H + (rh_ - th) / 2, rw_, th, weight="bold", color=rgba(WHITE),
               align="center", group=gid, rotation=round(rot, 1), remember=False)

    # tiny elements: dots and hairlines
    for i in range(spec.n_tiny):
        kind = rng.choice(["dot", "line", "square"])
        if kind == "line":
            lw = W * rng.uniform(0.1, 0.4)
            b.shape("line", rng.uniform(m, W - m - lw), rng.uniform(m, H - m), lw, rng.choice([1, 1.5, 2]), rgba(b.accent))
        else:
            s = rng.choice([2, 3, 4, 6])
            b.shape("ellipse" if kind == "dot" else "rectangle", rng.uniform(m, W - m), rng.uniform(m, H - m), s, s, rgba(b.accent))

    # accent shapes on the margins
    for i in range(spec.n_extra_shapes):
        s = rng.uniform(0.01, 0.04) * min(W, H)
        edge = rng.choice(["left", "right"])
        x = rng.uniform(0, m * 0.6) if edge == "left" else W - rng.uniform(s, m * 0.6 + s)
        b.shape(rng.choice(["rectangle", "ellipse"]), x, rng.uniform(0, H - s), s, s * rng.uniform(0.5, 3),
                rgba(rng.choice(ACCENTS)), opacity=rng.choice([1, 1, 0.7]), radius=rng.choice([0, s / 4]))

    # panel behind the text column (inserted below the texts in z)
    if spec.panel and b.text_boxes:
        x0 = min(t[0] for t in b.text_boxes)
        y0 = min(t[1] for t in b.text_boxes)
        x1 = max(t[0] + t[2] for t in b.text_boxes)
        y1 = max(t[1] + t[3] for t in b.text_boxes)
        pad = 0.5 * u
        fill = rgba((20, 12, 24), rng.choice([0.85, 1.0])) if spec.theme == "dark" else rgba(WHITE, rng.choice([0.9, 1.0]))
        panel = b.shape("rectangle", max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad) - max(0, x0 - pad),
                        min(H, y1 + pad) - max(0, y0 - pad), fill, radius=rng.choice([0, 0.3 * u]), z=2)
        # the panel must paint below everything it carries: give the content
        # z above it (z_tie keeps content at 5, which is already above 2)
        if not spec.z_tie:
            for el in b.elements:
                if el is not panel and el["z_index"] >= 2 and el["z_index"] != 0:
                    el["z_index"] += 1

    elements = b.elements
    design = {"canvas": spec.canvas, "elements": elements}
    return design


# ---------------------------------------------------------------------------
# props (what the report slices by)


def _bucket_elements(n: int) -> str:
    if n <= 4:
        return "02-04"
    if n <= 10:
        return "05-10"
    if n <= 20:
        return "11-20"
    if n <= 30:
        return "21-30"
    return "31-45"


def props_of(spec: Spec, design: dict[str, Any], notes: dict[str, Any] | None = None) -> dict[str, Any]:
    els = design["elements"]
    texts = [e for e in els if e["type"] == "text"]
    longest = max((len(e["content"]) for e in texts), default=0)
    longest_word = max((len(w) for e in texts for w in str(e["content"]).split()), default=0)
    p = {k: v for k, v in asdict(spec).items() if k not in ("seed", "width", "height")}
    p.update({
        "n_elements": len(els),
        "n_elements_bucket": _bucket_elements(len(els)),
        "n_text": len(texts),
        "n_groups": len({e.get("group_id") for e in els if e.get("group_id")}),
        "headline_chars": longest,
        "headline_len": spec.headline_len,
        "longest_word": longest_word,
        "has_missing_asset": spec.hero == "missing_asset",
        "rotated": bool(spec.headline_rotated or spec.badge_rotated or spec.ribbon),
        "has_rotated_text": any(e["type"] == "text" and e.get("rotation") for e in els),
        "has_decor_bleed": spec.n_decor > 0,
        "has_letter_spacing": spec.letter_spacing > 0,
        "has_style_runs": any("style_runs" in e for e in els),
        "has_max_lines": any(e.get("max_lines") for e in els),
        "has_group_cta": spec.cta.startswith("group"),
        "has_shadow_text": spec.shadow_text,
        "has_tiny": spec.n_tiny > 0,
        "src_overfull": bool((notes or {}).get("src_overfull")),
        "src_overflow": bool((notes or {}).get("src_overflow")),
        "src_overlap_n": source_overlap_count(design),
    })
    return p


def source_overlap_count(design: dict[str, Any]) -> int:
    """Pairs of content elements (not background / decorative / panel-like,
    not in the same group) whose boxes intersect in the source. Informational:
    an overfull synthetic source has these on purpose."""
    W, H = float(design["canvas"]["width"]), float(design["canvas"]["height"])
    content = []
    for e in design["elements"]:
        area = float(e["width"]) * float(e["height"])
        if area >= 0.5 * W * H or float(e.get("opacity", 1)) < 0.5:
            continue
        if e["type"] == "shape" and area >= 0.15 * W * H:
            continue
        content.append(e)
    n = 0
    for i, a in enumerate(content):
        for b in content[i + 1:]:
            if a.get("group_id") and a.get("group_id") == b.get("group_id"):
                continue
            if (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                    and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]):
                n += 1
    return n


# ---------------------------------------------------------------------------
# validation (the structural rules of schema v0.9, without jsonschema)


def validate(design: dict[str, Any], strict: bool = True) -> list[str]:
    """Schema v0.9 problems as strings (empty = valid). `strict=False` lets
    the nasty cases through (font_size < 1, zero sizes are *meant* there)."""
    errs: list[str] = []
    c = design.get("canvas")
    if not isinstance(c, dict) or not all(isinstance(c.get(k), int) and c[k] >= 1 for k in ("width", "height")):
        errs.append("canvas must have integer width/height >= 1")
    els = design.get("elements")
    if not isinstance(els, list) or not els:
        return errs + ["elements must be a non-empty list"]
    seen: set[str] = set()
    for e in els:
        i = e.get("id")
        if not isinstance(i, str) or not i:
            errs.append("element without string id")
        elif i in seen:
            errs.append(f"duplicate id {i}")
        seen.add(str(i))
        if e.get("type") not in ("text", "image", "shape"):
            errs.append(f"{i}: bad type {e.get('type')}")
        for k in ("x", "y", "width", "height"):
            if not isinstance(e.get(k), (int, float)) or isinstance(e.get(k), bool):
                errs.append(f"{i}: {k} missing or not a number")
        if strict and (float(e.get("width", 0)) < 0 or float(e.get("height", 0)) < 0):
            errs.append(f"{i}: negative size")
        if "opacity" in e and not (0 <= float(e["opacity"]) <= 1):
            errs.append(f"{i}: opacity out of range")
        if "z_index" in e and not isinstance(e["z_index"], int):
            errs.append(f"{i}: z_index not an integer")
        if e.get("type") == "text":
            for k in ("content", "font_family", "font_size", "color"):
                if k not in e:
                    errs.append(f"{i}: text without {k}")
            if strict and float(e.get("font_size", 1)) < 1:
                errs.append(f"{i}: font_size < 1")
            if e.get("font_weight", "regular") not in ("regular", "bold"):
                errs.append(f"{i}: bad font_weight")
            if e.get("text_align", "left") not in ("left", "center", "right"):
                errs.append(f"{i}: bad text_align")
            for r in e.get("style_runs") or []:
                if not (isinstance(r.get("start"), int) and isinstance(r.get("end"), int)):
                    errs.append(f"{i}: style_run without int start/end")
                elif strict and not (0 <= r["start"] <= r["end"] <= len(e.get("content", ""))):
                    errs.append(f"{i}: style_run outside content")
        elif e.get("type") == "image":
            if "asset_id" not in e:
                errs.append(f"{i}: image without asset_id")
            if e.get("fit", "contain") not in ("contain", "cover", "fill"):
                errs.append(f"{i}: bad fit")
        elif e.get("type") == "shape":
            for k in ("shape_type", "fill_color"):
                if k not in e:
                    errs.append(f"{i}: shape without {k}")
            if e.get("shape_type") not in ("rectangle", "ellipse", "line"):
                errs.append(f"{i}: bad shape_type")
    return errs


# ---------------------------------------------------------------------------
# corpus


def generate(seed: int, family: str | None = None) -> tuple[Spec, dict[str, Any], dict[str, Any]]:
    """One design: (spec, design, props) for a seed."""
    rng = random.Random(seed)
    spec = random_spec(rng, seed=seed, family=family)
    design = build(spec)
    notes = _last_notes(spec, design)
    return spec, design, props_of(spec, design, notes)


def _last_notes(spec: Spec, design: dict[str, Any]) -> dict[str, Any]:
    # notes are derived cheaply from the design itself so build() stays pure
    W, H = float(spec.width), float(spec.height)
    m = default_measurer()
    over = False
    for e in design["elements"]:
        if e["type"] != "text":
            continue
        try:
            if not m.fits(e, e["font_size"], e["width"], e["height"]):
                over = True
        except Exception:
            over = True
    overfull = any(e["type"] == "text" and (e["y"] + e["height"] > H + 1 or e["x"] + e["width"] > W + 1)
                   for e in design["elements"] if not e.get("rotation"))
    return {"src_overflow": over, "src_overfull": overfull}


def generate_corpus(n: int, seed: int = 1, balanced: bool = True) -> list[dict[str, Any]]:
    """n designs as harness documents {id, source, meta, props}. `balanced`
    cycles through the four ratio families so banners are not rare."""
    docs = []
    fams = ["tall", "square", "wide", "banner"]
    for k in range(n):
        s = seed * 100_000 + k
        fam = fams[k % 4] if balanced else None
        spec, design, props = generate(s, fam)
        did = f"syn_{seed}_{k:04d}"
        docs.append({
            "id": did,
            "source": design,
            "meta": {"title": f"{spec.density} {spec.family} {spec.headline_len} ({spec.width}x{spec.height})",
                     "canvas": spec.canvas, "family": spec.family, "n_elements": len(design["elements"]),
                     "n_text": props["n_text"], "siblings": [], "synthetic": True, "seed": s},
            "props": props,
        })
    return docs


# ---------------------------------------------------------------------------
# nasty cases


def _base_design(seed: int = 4242) -> dict[str, Any]:
    spec = Spec(seed=seed, family="tall", width=1080, height=1350, theme="dark", background="image",
                logo_pos="tc", hero="present", headline_len="short", n_subs=1, cta="group", n_badges=2,
                fine_print=True, density="normal")
    return build(spec)


def _texts(design: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in design["elements"] if e["type"] == "text"]


def _headline(design: dict[str, Any]) -> dict[str, Any]:
    return max(_texts(design), key=lambda e: float(e["font_size"]))


def nasty_cases() -> list[dict[str, Any]]:
    """Hostile inputs. Each: {name, source, targets: [{name, width, height}],
    why}. Deterministic. The engine must return a structurally valid design
    for all of them; nothing else is promised."""
    std = [{"name": "1080x1080", "width": 1080, "height": 1080},
           {"name": "728x90", "width": 728, "height": 90},
           {"name": "1080x1920", "width": 1080, "height": 1920}]
    cases: list[dict[str, Any]] = []

    def case(name: str, src: dict[str, Any], why: str, targets: list[dict[str, Any]] | None = None) -> None:
        cases.append({"name": name, "source": src, "targets": targets or std, "why": why})

    base = _base_design()

    d = copy.deepcopy(base)
    _headline(d)["content"] = ""
    _texts(d)[1]["content"] = "   "
    case("empty_content", d, "headline content '' and a whitespace-only text")

    d = copy.deepcopy(base)
    _texts(d)[1]["font_size"] = 0.5
    case("font_size_half", d, "a subhead with font_size 0.5 (below the schema minimum of 1)")

    d = copy.deepcopy(base)
    h = _headline(d)
    h["font_size"] = 400
    case("font_size_400", d, "headline font 400 px in a box that fits ~60 px")

    d = copy.deepcopy(base)
    d["elements"].append({"id": "zz0", "type": "shape", "x": 100, "y": 100, "width": 0, "height": 0,
                          "shape_type": "rectangle", "fill_color": rgba(RED), "z_index": 9})
    d["elements"].append({"id": "zz1", "type": "text", "x": 200, "y": 200, "width": 0, "height": 0,
                          "content": "Zero box", "font_family": SANS, "font_size": 20, "color": rgba(WHITE), "z_index": 9})
    d["elements"].append({"id": "zz2", "type": "image", "x": 300, "y": 300, "width": 0, "height": 120,
                          "asset_id": ASSET_HERO, "fit": "contain", "z_index": 9})
    case("zero_size_elements", d, "a 0x0 shape, a 0x0 text and a 0-wide image")

    d = copy.deepcopy(base)
    logo = next(e for e in d["elements"] if e.get("asset_id") == ASSET_LOGO)
    logo["x"], logo["y"] = -40, -20
    h = _headline(d)
    h["x"] = d["canvas"]["width"] - h["width"] * 0.6
    d["elements"].append({"id": "far", "type": "shape", "x": 3000, "y": 3000, "width": 50, "height": 50,
                          "shape_type": "ellipse", "fill_color": rgba(GOLD), "z_index": 9})
    case("negative_and_offcanvas", d, "logo at negative coordinates, headline 60 % off the right edge, a shape far outside")

    d = copy.deepcopy(base)
    for e in d["elements"]:
        if e["type"] == "image":
            e["asset_id"] = "nope_" + e["asset_id"]
    case("all_assets_missing", d, "every image asset_id is unknown (background included)")

    d = {"canvas": {"width": 800, "height": 600},
         "elements": [{"id": "only", "type": "text", "x": 100, "y": 250, "width": 600, "height": 100,
                       "content": "Chase the Light", "font_family": SERIF, "font_size": 64, "color": rgba(INK)}]}
    case("single_element", d, "one text element, no background")

    d = {"canvas": {"width": 1080, "height": 1080},
         "elements": [{"id": "a", "type": "text", "x": 90, "y": 400, "width": 900, "height": 120,
                       "content": "Golden Hour", "font_family": SERIF, "font_size": 80, "color": rgba(INK),
                       "text_align": "center"},
                      {"id": "b", "type": "text", "x": 390, "y": 600, "width": 300, "height": 50,
                       "content": "Shop Now", "font_family": SANS, "font_size": 28, "color": rgba(ORANGE),
                       "text_align": "center"}]}
    case("two_texts_only", d, "the minimum design: headline + CTA text, nothing else")

    d = copy.deepcopy(base)
    for e in d["elements"]:
        e["group_id"] = "everything"
    case("all_one_group", d, "every element (background included) shares one group_id")

    d = copy.deepcopy(base)
    for e in d["elements"]:
        e["group_id"] = f"solo_{e['id']}"
    case("singleton_groups", d, "every element is in a group of its own")

    d = copy.deepcopy(base)
    keep = {"text": ("id", "type", "x", "y", "width", "height", "content", "font_family", "font_size", "color"),
            "image": ("id", "type", "x", "y", "width", "height", "asset_id"),
            "shape": ("id", "type", "x", "y", "width", "height", "shape_type", "fill_color")}
    d["elements"] = [{k: e[k] for k in keep[e["type"]]} for e in d["elements"]]
    case("required_fields_only", d, "no z_index / opacity / rotation / fit / group_id / weight / align anywhere")

    d = copy.deepcopy(base)
    rots = [90, 180, -270, 360, 725, -45.5]
    for e, r in zip([e for e in d["elements"] if e.get("z_index", 1) != 0][:6], rots):
        e["rotation"] = r
    case("rotation_extremes", d, "rotations 90, 180, -270, 360, 725 and -45.5 on content elements")

    d = copy.deepcopy(base)
    h = _headline(d)
    h["content"] = "Introducing the All-New Limited-Batch Solstice Chase the Light Botanical Sparkling Collection"
    h["max_lines"] = 1
    _texts(d)[1]["max_lines"] = 0
    case("max_lines_1_on_long_headline", d, "max_lines 1 on a 95-char headline, max_lines 0 on the subhead")

    d = copy.deepcopy(base)
    h = _headline(d)
    n = len(h["content"])
    h["style_runs"] = [{"start": 0, "end": n, "color": rgba(GOLD)}, {"start": 2, "end": n + 40, "font_weight": "bold"},
                       {"start": 5, "end": 3}]
    case("style_runs_malformed", d, "runs covering all content, overlapping, past the end, and end < start")

    d = copy.deepcopy(base)
    h = _headline(d)
    h["content"] = "Golden Hour ☀️ 黄金時間 — ساعة ذهبية 🍾"
    _texts(d)[1]["content"] = "Line one\nLine two\n\nLine four after a blank line\tand a tab"
    case("unicode_and_newlines", d, "emoji, CJK and RTL text in the headline; newlines and a tab in the subhead")

    d = copy.deepcopy(base)
    h = _headline(d)
    h["letter_spacing"] = 40
    h["line_height"] = 0
    _texts(d)[1]["line_height"] = 3.0
    _texts(d)[1]["letter_spacing"] = -2
    case("spacing_extremes", d, "letter_spacing 40 and line_height 0 on the headline, line_height 3 and negative tracking on the subhead")

    d = copy.deepcopy(base)
    for e in d["elements"]:
        if e["type"] == "text":
            e["opacity"] = 0
    d["elements"].append({"id": "wash", "type": "shape", "x": 20, "y": 20, "width": 1040, "height": 1310,
                          "shape_type": "ellipse", "fill_color": rgba(GOLD), "opacity": 1, "z_index": 1})
    case("opacity_zero_and_giant_ellipse", d, "all text at opacity 0, an opaque ellipse covering 95 % of the canvas")

    d = copy.deepcopy(base)
    hero = next(e for e in d["elements"] if e.get("asset_id") == ASSET_HERO)
    hero["fit"] = "fill"
    logo = next(e for e in d["elements"] if e.get("asset_id") == ASSET_LOGO)
    logo["fit"] = "cover"
    case("image_fit_fill_and_cover", d, "hero with fit fill, logo with fit cover")

    d = {"canvas": {"width": 1080, "height": 1350}, "elements": [
        {"id": "bg", "type": "shape", "x": 0, "y": 0, "width": 1080, "height": 1350, "shape_type": "rectangle",
         "fill_color": rgba(CREAM), "z_index": 0}]}
    for k in range(44):
        d["elements"].append({"id": f"t{k:02d}", "type": "text", "x": 60 + (k % 4) * 250, "y": 60 + (k // 4) * 110,
                              "width": 220, "height": 40, "content": f"Item {k + 1} {SENTENCES[k % len(SENTENCES)].split('.')[0][:18]}",
                              "font_family": SANS, "font_size": 14 + (k % 5) * 3, "color": rgba(INK), "z_index": 1})
    case("forty_five_elements", d, "45 elements: a background and a 4x11 grid of small texts")

    d = copy.deepcopy(base)
    h = _headline(d)
    for k in range(6):
        c = copy.deepcopy(h)
        c["id"] = f"dup{k}"
        c["color"] = rgba(ACCENTS[k % 4], 0.8)
        d["elements"].append(c)
    case("identical_stacked_texts", d, "the headline duplicated six times at the exact same box and z")

    d = copy.deepcopy(base)
    d["elements"].append({"id": "big", "type": "text", "x": 0, "y": 0, "width": 1080, "height": 1350,
                          "content": "BIG", "font_family": SERIF, "font_size": 900, "color": rgba(GOLD, 0.3), "z_index": 1})
    case("canvas_sized_text", d, "a text box the size of the canvas with a 900 px font (watermark)")

    d = copy.deepcopy(base)
    case("target_1x1", d, "target canvas 1x1", [{"name": "1x1", "width": 1, "height": 1}])
    case("target_4000x4000", d, "target canvas 4000x4000", [{"name": "4000x4000", "width": 4000, "height": 4000}])
    case("target_4000x100", d, "target canvas 4000x100 (40:1)", [{"name": "4000x100", "width": 4000, "height": 100}])
    case("target_100x4000", d, "target canvas 100x4000 (1:40)", [{"name": "100x4000", "width": 100, "height": 4000}])
    case("target_identical", d, "target identical to the source canvas",
         [{"name": "identical", "width": d["canvas"]["width"], "height": d["canvas"]["height"]}])
    case("target_plus_3pct_width", d, "target 3 % wider than the source",
         [{"name": "+3%w", "width": round(d["canvas"]["width"] * 1.03), "height": d["canvas"]["height"]}])
    case("target_minus_3pct_height", d, "target 3 % shorter than the source",
         [{"name": "-3%h", "width": d["canvas"]["width"], "height": round(d["canvas"]["height"] * 0.97)}])

    d = {"canvas": {"width": 50, "height": 50}, "elements": [
        {"id": "s", "type": "shape", "x": 0, "y": 0, "width": 50, "height": 50, "shape_type": "rectangle",
         "fill_color": rgba(PLUM), "z_index": 0},
        {"id": "t", "type": "text", "x": 2, "y": 15, "width": 46, "height": 20, "content": "Tiny source",
         "font_family": SANS, "font_size": 8, "color": rgba(WHITE), "text_align": "center", "z_index": 1},
        {"id": "i", "type": "image", "x": 20, "y": 2, "width": 10, "height": 10, "asset_id": ASSET_HERO, "z_index": 1}]}
    case("tiny_source_50x50", d, "a 50x50 source scaled up to the standard targets", std + [{"name": "1080x1350", "width": 1080, "height": 1350}])

    return cases


# ---------------------------------------------------------------------------
# write a harness data dir


def write_corpus(out_dir: Path, n: int, seed: int = 1, with_nasty: bool = True) -> list[dict[str, Any]]:
    """eval/data/synth-style data dir: designs/<id>.json + index.json in the
    shape run_eval.load_index expects (plus `props`, `synthetic` and, for the
    nasty cases, an explicit `targets` list that replaces the presets)."""
    out_dir = Path(out_dir)
    (out_dir / "designs").mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    for doc in generate_corpus(n, seed):
        (out_dir / "designs" / f"{doc['id']}.json").write_text(json.dumps(doc, indent=1))
        index.append({"id": doc["id"], "file": f"designs/{doc['id']}.json", **doc["meta"], "props": doc["props"]})
    if with_nasty:
        for c in nasty_cases():
            did = f"nasty_{c['name']}"
            src = c["source"]
            doc = {"id": did, "source": src,
                   "meta": {"title": f"nasty: {c['why']}", "canvas": src["canvas"],
                            "family": ratio_family(src["canvas"]["width"], src["canvas"]["height"]),
                            "n_elements": len(src["elements"]),
                            "n_text": sum(1 for e in src["elements"] if e["type"] == "text"),
                            "siblings": [], "synthetic": True, "nasty": True},
                   "props": {"nasty": c["name"], "n_elements": len(src["elements"]),
                             "n_elements_bucket": _bucket_elements(len(src["elements"]))}}
            (out_dir / "designs" / f"{did}.json").write_text(json.dumps(doc, indent=1))
            index.append({"id": did, "file": f"designs/{did}.json", **doc["meta"], "props": doc["props"],
                          "targets": c["targets"]})
    (out_dir / "index.json").write_text(json.dumps(index, indent=1))
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(SYNTH_DIR))
    ap.add_argument("--no-nasty", action="store_true")
    ap.add_argument("--validate", action="store_true", help="also run validate() on every design")
    a = ap.parse_args(argv)
    index = write_corpus(Path(a.out), a.n, a.seed, with_nasty=not a.no_nasty)
    if a.validate:
        bad = 0
        for row in index:
            doc = json.loads((Path(a.out) / row["file"]).read_text())
            errs = validate(doc["source"], strict=not row.get("nasty"))
            if errs:
                bad += 1
                print(row["id"], errs[:3])
        print(f"{bad} invalid of {len(index)}")
    print(f"{len(index)} designs -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
