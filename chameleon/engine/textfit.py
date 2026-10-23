"""Measure text the way cr-renderer draws it, so font sizes we emit really fit.

Mirrors renderer/converter: greedy word wrap on skia glyph advances at the
float font size (letter spacing is NOT part of the wrap decision), lines
stacked at `font_size * line_height` from the top of the box, and nothing
clipped to the box. Falls back to Pillow measurement if skia or the brand
fonts are unavailable, so the engine never crashes on a missing renderer.

Letter spacing is a px value in the schema, but the engine treats it as
*proportional to the font*: measuring an element at a font size other than
its own scales `letter_spacing` by the same factor (`scaled_letter_spacing`),
and whoever writes a new `font_size` into an element writes the scaled
spacing next to it (`apply_font_size`). Otherwise a 28 px tracking that was
designed for a 60 px headline stays 28 px when the headline drops to 12 px,
no width ever fits, and the fitter runs the font down to 1 px.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO_ROOT / "brand_kit" / "fonts"

DEFAULT_LINE_HEIGHT = 1.2
MIN_FONT_SIZE = 8.0


@dataclass
class TextLayout:
    font_size: float
    lines: list[str]
    line_widths: list[float]
    height: float          # visual height from box top to last descender

    @property
    def n_lines(self) -> int:
        return len(self.lines)

    @property
    def max_width(self) -> float:
        return max(self.line_widths) if self.line_widths else 0.0


def _font_key(el: dict[str, Any]) -> tuple[str, str, str]:
    family = str(el.get("font_family", "Solstice Sans"))
    weight = "bold" if str(el.get("font_weight", "regular")).lower() == "bold" else "regular"
    italic = str(el.get("font_style", "normal")).lower() == "italic"
    if weight == "bold" and italic:
        style = "bolditalic"
    elif weight == "bold":
        style = "bold"
    elif italic:
        style = "italic"
    else:
        style = "regular"
    return family, weight, style


class _SkiaBackend:
    def __init__(self, fonts_dir: Path):
        import skia  # type: ignore
        from renderer.converter.brand_fonts import load_brand_font_manager

        self.skia = skia
        self.manager = load_brand_font_manager(str(fonts_dir))
        self._typefaces: dict[tuple[str, str, str], Any] = {}

    def _typeface(self, key: tuple[str, str, str]):
        tf = self._typefaces.get(key)
        if tf is None:
            data = self.manager.lookup(*key)
            tf = self.skia.Typeface.MakeFromData(data)
            self._typefaces[key] = tf
        return tf

    def widths(self, key: tuple[str, str, str], size: float, text: str) -> list[float]:
        if not text:
            return []
        font = self.skia.Font(self._typeface(key), size)
        return list(font.getWidths(font.textToGlyphs(text)))

    def metrics(self, key: tuple[str, str, str], size: float) -> tuple[float, float]:
        font = self.skia.Font(self._typeface(key), int(size))
        m = font.getMetrics()
        return float(m.fAscent), float(m.fDescent)


class _PillowBackend:
    """Approximate fallback. Only used when skia / the renderer are missing."""

    def __init__(self, fonts_dir: Path):
        from PIL import ImageFont

        self.ImageFont = ImageFont
        self.fonts_dir = fonts_dir
        self._cache: dict[tuple, Any] = {}

    def _font(self, key: tuple[str, str, str], size: float):
        family, weight, style = key
        suffix = {"regular": "Regular", "bold": "Bold", "italic": "Italic", "bolditalic": "BoldItalic"}[style]
        stem = family.replace(" ", "") + "-" + suffix
        ck = (stem, int(size))
        f = self._cache.get(ck)
        if f is None:
            path = self.fonts_dir / f"{stem}.ttf"
            try:
                f = self.ImageFont.truetype(str(path), max(1, int(size)))
            except OSError:
                f = self.ImageFont.load_default()
            self._cache[ck] = f
        return f

    def widths(self, key, size, text):
        f = self._font(key, size)
        return [f.getlength(c) for c in text]

    def metrics(self, key, size):
        f = self._font(key, size)
        asc, desc = f.getmetrics()
        return -float(asc), float(desc)


class TextMeasurer:
    def __init__(self, fonts_dir: Path | str | None = None):
        fonts_dir = Path(fonts_dir) if fonts_dir else FONTS_DIR
        self.backend: Any
        try:
            self.backend = _SkiaBackend(fonts_dir)
            self.exact = True
        except Exception as exc:  # pragma: no cover - only without renderer
            logger.warning("skia text measurement unavailable (%s); using Pillow", exc)
            self.backend = _PillowBackend(fonts_dir)
            self.exact = False

    # -- core -------------------------------------------------------------

    def layout(self, el: dict[str, Any], font_size: float | None = None,
               width: float | None = None) -> TextLayout:
        size = float(font_size if font_size is not None else el["font_size"])
        box_w = float(width if width is not None else el["width"])
        text = str(el.get("content", ""))
        key = _font_key(el)
        lh = float(el.get("line_height", DEFAULT_LINE_HEIGHT) or DEFAULT_LINE_HEIGHT)
        ls = scaled_letter_spacing(el, size)

        widths = self.backend.widths(key, size, text)
        wrapped = _wrap(text, widths, box_w)
        lines = wrapped.split("\n")
        line_widths: list[float] = []
        pos = 0
        for line in lines:
            w = sum(widths[pos:pos + len(line)]) + ls * max(0, len(line) - 1)
            line_widths.append(w)
            pos += len(line) + 1
        ascent, descent = self.backend.metrics(key, size)
        height = (len(lines) - 1) * size * lh + (descent - ascent)
        return TextLayout(font_size=size, lines=lines, line_widths=line_widths, height=height)

    def fits(self, el: dict[str, Any], font_size: float, width: float, height: float,
             slack: float = 0.5) -> bool:
        lay = self.layout(el, font_size, width)
        if el.get("max_lines") and lay.n_lines > int(el["max_lines"]):
            return False
        return lay.max_width <= width + slack and lay.height <= height + slack

    def fit_font_size(self, el: dict[str, Any], width: float, height: float,
                      max_size: float, min_size: float = MIN_FONT_SIZE) -> float:
        """Largest integer font size in [min_size, max_size] whose wrapped text
        fits the box. Returns min_size if nothing fits (caller decides what
        to do about the overflow)."""
        hi = int(max_size)
        lo = int(min_size)
        if hi < lo:
            return float(lo)
        if self.fits(el, hi, width, height):
            return float(hi)
        best = lo
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.fits(el, mid, width, height):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return float(best)

    def natural_height(self, el: dict[str, Any], font_size: float, width: float) -> float:
        """Height the box needs so the renderer's last line sits inside it."""
        return self.layout(el, font_size, width).height


def scaled_letter_spacing(el: dict[str, Any], font_size: float) -> float:
    """The element's letter spacing at `font_size`: proportional to its own
    font size (an element whose font we did not change keeps its spacing)."""
    ls = float(el.get("letter_spacing", 0.0) or 0.0)
    if ls == 0.0:
        return 0.0
    own = float(el.get("font_size", 0.0) or 0.0)
    if own <= 0.0 or font_size <= 0.0:
        return ls
    return ls * float(font_size) / own


def apply_font_size(el: dict[str, Any], font_size: float) -> None:
    """Set `font_size` on `el` and scale its letter spacing with it. Every
    place that changes a font goes through here so the measurer's model
    (spacing proportional to the font) matches what is written out."""
    if "letter_spacing" in el and el.get("letter_spacing"):
        el["letter_spacing"] = scaled_letter_spacing(el, font_size)
    el["font_size"] = float(font_size)


def _wrap(text: str, widths: list[float], max_width: float) -> str:
    """Identical to renderer/converter/wrap.py: turn spaces into newlines."""
    if not text or max_width <= 0:
        return text
    chars = list(text)
    line_width = 0.0
    last_space = None
    for i, c in enumerate(chars):
        if c == "\n":
            line_width = 0.0
            last_space = None
            continue
        w = widths[i] if i < len(widths) else 0.0
        if line_width + w > max_width and last_space is not None:
            chars[last_space] = "\n"
            line_width = sum(widths[j] for j in range(last_space + 1, i + 1) if chars[j] != "\n")
            last_space = None
        else:
            line_width += w
        if c == " ":
            last_space = i
    return "".join(chars)


@lru_cache(maxsize=1)
def default_measurer() -> TextMeasurer:
    return TextMeasurer()
