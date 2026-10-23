"""Download a slice of the Crello dataset and convert it to CHAMELEON schema v0.9.

    .venv/bin/python -m eval.crello_convert --target 400
    .venv/bin/python -m eval.crello_convert --shards validation:0 --target 40   # quick

Why: we only have three sample designs; Crello (HF `cyberagent/crello`,
CDLA-Permissive-2.0, ~19k real templates) gives us hundreds of real layouts
with per-element geometry, text, fonts, and families of the *same* template
at several canvas sizes (ground truth for "what did the designer do?").

How the download stays small: the parquet shards embed every layer's pixels
(~0.5 GB per shard). We open each shard through the Hugging Face filesystem
and read only the metadata columns with pyarrow (HTTP range requests), which
is ~3 MB per shard. Raw tables are cached in eval/data/raw/.

Mapping (the reverse of renderer/converter/convert.py, see also the FAQ):
  - coordinates: Crello v5 parquet stores pixels already; normalized [0,1]
    tables (older releases) are detected per row and scaled by the canvas.
  - angle: degrees if the slice contains any |angle| > 2*pi, else radians.
  - z order: Crello lists layers bottom to top -> z_index = position.
  - TextElement  -> text (content, font_size, color, align, line_height,
    letter_spacing, dominant bold/italic, style_runs for per-character
    deviations; `capitalize` is baked into the content).
  - ColoredBackground -> shape rectangle in the element's colour.
  - SvgElement with exactly one palette colour -> shape rectangle in that
    colour (buttons, pills, rules, blobs). Any other SVG / image / mask layer
    -> image mapped to one of the three brand-kit assets by *shape*: full
    bleed -> solstice_bg_gradient.png (fit cover), a photo covering >= 25 %
    of the canvas -> the same gradient as a panel (fit cover), wide and short
    -> solstice_logo_lockup.png, otherwise -> solstice_bottle.png (contain).
    We never use Crello's pixels.
  - fonts: serif / script families -> "Solstice Serif", everything else ->
    "Solstice Sans". The original font name is kept in the sidecar.
  - ids are opaque ("el_07"), like the hidden tasks. No group_id (Crello has
    no grouping information).
  - text boxes are normalised to the engine's fit model (--raw-boxes turns it
    off): Crello sizes a text box as lines x font_size x line_height, while
    engine.textfit needs ascent + descent, so 90 % of raw boxes count as
    "overflowing" and the engine would shrink their fonts. The height grows to
    the measured need (cr-renderer draws from the box top and never clips, so
    the source render is unchanged); the width grows only when a line is wider
    than the box (letter spacing is ignored by the wrap, single over-wide
    words). The sidecar records every grown box.

Output: eval/data/designs/<crello_id>.json with {"id", "source", "meta",
"sidecar"}, eval/data/index.json (one row per design incl. sibling ids) and
eval/data/pairs.json (families of the same template at different sizes:
same title, different canvas, at least one text string in common).
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import math
import random
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "eval" / "data"
RAW_DIR = DATA_DIR / "raw"
DESIGNS_DIR = DATA_DIR / "designs"
INDEX_PATH = DATA_DIR / "index.json"
PAIRS_PATH = DATA_DIR / "pairs.json"

HF_REPO = "datasets/cyberagent/crello"
SHARD_COUNTS = {"train": 31, "validation": 3, "test": 4}
DEFAULT_SHARDS = "validation:0,1,2 test:0,1"
PIXEL_COLUMNS = ("image", "preview")

MAX_ELEMENTS = 25
MIN_CANVAS_PX = 50

ASSET_BG = "solstice_bg_gradient.png"
ASSET_LOGO = "solstice_logo_lockup.png"
ASSET_HERO = "solstice_bottle.png"
FULL_BLEED_COVER = 0.85          # fraction of the canvas an image covers to count as a background
WIDE_SHORT_ASPECT = 1.8          # w/h above this -> logo-like
PHOTO_PANEL_COVER = 0.25         # a photo covering this much of the canvas becomes a gradient panel

SERIF_FONT = "Solstice Serif"
SANS_FONT = "Solstice Sans"

# Crello families that read as serif / slab / didone, or as script / hand
# lettering (closest brand-kit match is the serif). Everything else is sans.
SERIF_LIKE = {
    "Playfair Display", "Abril Fatface", "Libre Baskerville", "Podkova", "Cormorant Infant", "Arapey",
    "Kreon", "Alfa Slab One", "Frank Ruhl Libre", "Droid Serif", "Merriweather", "Crete Round",
    "Patua One", "Rokkitt", "Tinos", "Josefin Slab", "Arima Madurai", "Noticia Text", "Old Standard Tt",
    "Italiana", "Vast Shadow", "Radley", "Superclarendon", "Vollkorn", "Yeseva One", "Glass Antiqua",
    "Oranienbaum", "Scope One", "Copse", "Source Serif Pro", "Suez One", "Rakkas", "Mate", "Kurale", "Rye",
    "Quattrocento", "Bentham", "Junge", "Kelly Slab", "Alice", "Forum", "Elsie", "Elsie Swash Caps",
    "Marcellus Sc", "Bellefair", "Fauna One", "Gabriela", "Eb Garamond", "Gfs Didot", "Cutive Mono",
    "Im Fell Dw Pica Sc", "Gravitas One", "Limelight", "Port Lligat Slab", "Sansita One", "Ewert",
    "Stint Ultra Expanded", "Jacques Francois Shadow", "Fredericka The Great", "Londrina Shadow",
    "Bungee Shade", "Trocchi", "Lora", "Cinzel", "Prata", "Spectral", "Crimson Text", "Cardo", "Domine",
    "Arvo", "Bitter", "Zilla Slab", "Roboto Slab", "Lustria", "Caudex", "Cormorant", "Cormorant Garamond",
}
SCRIPT_LIKE = {
    "Playlist Script", "Pacifico", "Yellowtail", "Caveat", "Breathe", "Oleo Script", "Kalam", "Playball",
    "Bad Script", "Patrick Hand", "Selima Script", "Lemon Tuesday", "Sunday", "Cookie", "Brusher Free Font",
    "Mrs Sheppards", "Grand Hotel", "Great Vibes", "Damion", "Parisienne", "Permanent Marker", "Satisfy",
    "Sacramento", "Mr Dafoe", "Lauren", "Mr De Haviland", "Pirou", "Rise", "Sensei", "Yesteryear", "Delius",
    "Sue Ellen Francisco", "Pattaya", "Dancing Script", "Playlist", "Kaushan Script", "Reenie Beanie",
    "Mrs Saint Delafield", "Covered By Your Grace", "Allura", "Brusher", "Nothing You Could Do", "Rochester",
    "Dawning Of A New Day", "Neucha", "Shadows Into Two", "Merienda One", "Stalemate", "Berkshire Swash",
    "Pinyon Script", "Delius Swash Caps", "Clicker Script", "Finger Paint", "La Belle Aurore", "Handlee",
    "Homemade Apple", "Meddon", "Arizonia", "Just Me Again Down Here", "Cedarville Cursive", "Courgette",
    "Happy Monkey", "Rock Salt", "Euphoria Script", "Zeyada", "Loved By The King", "League Script",
    "Give You Glory", "Kristi", "Italianno", "Lovers Quarrel", "Waiting For The Sunrise", "Marck Script",
    "Monsieur La Doulaise", "Petit Formal Script", "Bilbo", "Amatic Sc", "Architects Daughter", "Pangolin",
    "Kavivanar", "Gaegu", "Text Me One",
}

TALL, SQUARE, WIDE, BANNER = "tall", "square", "wide", "banner"

logger = logging.getLogger("eval.crello_convert")


# ---------------------------------------------------------------------------
# small helpers


def ratio_family(width: float, height: float) -> str:
    """Same thresholds as engine.floorplan.ratio_family (kept local so the
    converter's geometry does not depend on the engine)."""
    r = width / max(height, 1e-9)
    if r <= 0.8:
        return TALL
    if r <= 1.25:
        return SQUARE
    if r <= 3.0:
        return WIDE
    return BANNER


def map_font(name: str | None) -> str:
    name = (name or "").strip()
    if name in SERIF_LIKE or name in SCRIPT_LIKE:
        return SERIF_FONT
    low = name.lower()
    if any(k in low for k in ("serif", "slab", "garamond", "baskerville", "script", "hand", "brush")) \
            and "sans" not in low:
        return SERIF_FONT
    return SANS_FONT


def asset_for_box(w: float, h: float, canvas_w: float, canvas_h: float, photo: bool = False) -> tuple[str, str]:
    """(asset_id, fit) for an image layer, chosen by shape only. A `photo`
    (Crello ImageElement / mask) that covers a big part of the canvas becomes
    a gradient panel (fit cover), so text that sat on the photo still sits on
    a coloured panel rather than on the bare white canvas."""
    canvas_area = max(canvas_w * canvas_h, 1.0)
    cover = (min(w, canvas_w) * min(h, canvas_h)) / canvas_area
    if cover >= FULL_BLEED_COVER or (w >= 0.9 * canvas_w and h >= 0.9 * canvas_h):
        return ASSET_BG, "cover"
    if photo and cover >= PHOTO_PANEL_COVER:
        return ASSET_BG, "cover"
    if h > 0 and w / h >= WIDE_SHORT_ASPECT:
        return ASSET_LOGO, "contain"
    return ASSET_HERO, "contain"


def _majority(values: Iterable[Any], default: Any) -> Any:
    counts = collections.Counter(values)
    return counts.most_common(1)[0][0] if counts else default


def _rgba(color: str | None, default: str = "rgba(0,0,0,1)") -> str:
    """Normalise a Crello colour ("rgba(255, 102, 51, 1)" / "#ff6633" / "rgb(...)")
    to the schema's compact rgba() form."""
    if not color:
        return default
    c = color.strip()
    m = re.match(r"rgba?\(([^)]*)\)", c)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            return default
        if len(nums) == 3:
            nums.append(1.0)
        if len(nums) != 4:
            return default
        r, g, b = (int(round(max(0.0, min(255.0, v)))) for v in nums[:3])
        a = max(0.0, min(1.0, nums[3]))
        return f"rgba({r},{g},{b},{a:g})"
    m = re.match(r"#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$", c)
    if m:
        r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        a = int(m.group(2), 16) / 255.0 if m.group(2) else 1.0
        return f"rgba({r},{g},{b},{a:g})"
    return default


def _style_runs(n: int, colors: list[str], bolds: list[bool], italics: list[bool],
                base_color: str, base_bold: bool, base_italic: bool) -> list[dict[str, Any]]:
    """Contiguous spans whose (colour, bold, italic) differ from the element's
    dominant values, as schema style_runs (0-based, end-exclusive)."""
    runs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for i in range(n):
        c = _rgba(colors[i]) if i < len(colors) else base_color
        b = bool(bolds[i]) if i < len(bolds) else base_bold
        it = bool(italics[i]) if i < len(italics) else base_italic
        delta: dict[str, Any] = {}
        if c != base_color:
            delta["color"] = c
        if b != base_bold:
            delta["font_weight"] = "bold" if b else "regular"
        if it != base_italic:
            delta["font_style"] = "italic" if it else "normal"
        if not delta:
            cur = None
            continue
        if cur is not None and cur["end"] == i and all(cur.get(k) == v for k, v in delta.items()) \
                and len(cur) == len(delta) + 2:
            cur["end"] = i + 1
        else:
            cur = {"start": i, "end": i + 1, **delta}
            runs.append(cur)
    return runs


# ---------------------------------------------------------------------------
# decoding the raw table


def classlabel_names(schema_metadata: dict[bytes, bytes] | None) -> dict[str, list[str]]:
    """ClassLabel name tables for the per-element columns, read from the
    `huggingface` metadata the datasets library writes into each parquet."""
    if not schema_metadata or b"huggingface" not in schema_metadata:
        return {}
    info = json.loads(schema_metadata[b"huggingface"])
    feats = info.get("info", {}).get("features", {})
    out: dict[str, list[str]] = {}
    for col, spec in feats.items():
        node = spec
        while isinstance(node, dict) and node.get("_type") in ("Sequence", "List"):
            node = node.get("feature")
        if isinstance(node, dict) and node.get("_type") == "ClassLabel":
            out[col] = list(node.get("names", []))
    return out


def decode_row(row: dict[str, Any], names: dict[str, list[str]]) -> dict[str, Any]:
    """Replace ClassLabel ints with their names (per-element lists and scalars)."""
    out = dict(row)
    for col, table in names.items():
        if col not in out or out[col] is None:
            continue
        v = out[col]

        def dec(x: Any) -> Any:
            if isinstance(x, int) and 0 <= x < len(table):
                return table[x]
            return x

        out[col] = [dec(x) for x in v] if isinstance(v, list) else dec(v)
    return out


def detect_angle_unit(rows: Iterable[dict[str, Any]]) -> str:
    """'degrees' when any rotation exceeds 2*pi in magnitude, else 'radians'."""
    for r in rows:
        for a in r.get("angle") or []:
            if a is not None and abs(float(a)) > 2 * math.pi + 1e-3:
                return "degrees"
    return "radians"


def normalize_text_box(el: dict[str, Any], measurer: Any) -> dict[str, float]:
    """Grow a text box so its content fits by engine.textfit at the source
    font: width first (keeping the alignment anchor), then height. Returns the
    growth factors ({} when nothing changed)."""
    changed: dict[str, float] = {}
    w0, h0 = float(el["width"]), float(el["height"])
    for _ in range(3):
        lay = measurer.layout(el)
        if lay.max_width <= el["width"] + 0.5:
            break
        new_w = math.ceil(lay.max_width + 1.0)
        dx = new_w - float(el["width"])
        if el.get("text_align") == "center":
            el["x"] = round(float(el["x"]) - dx / 2.0, 2)
        elif el.get("text_align") == "right":
            el["x"] = round(float(el["x"]) - dx, 2)
        el["width"] = float(new_w)
    need_h = measurer.natural_height(el, float(el["font_size"]), float(el["width"]))
    if need_h > el["height"] + 0.5:
        el["height"] = float(math.ceil(need_h + 1.0))
    if el["width"] != w0:
        changed["w"] = round(el["width"] / max(w0, 1e-6), 3)
    if el["height"] != h0:
        changed["h"] = round(el["height"] / max(h0, 1e-6), 3)
    return changed


# ---------------------------------------------------------------------------
# conversion of one template


class SkipTemplate(Exception):
    pass


def convert_template(row: dict[str, Any], angle_unit: str = "degrees",
                     max_elements: int = MAX_ELEMENTS, normalize_boxes: bool = True) -> dict[str, Any]:
    """Convert one decoded Crello row to {"id", "source", "meta", "sidecar"}.

    Raises SkipTemplate for templates we do not want in the eval set (too many
    elements, no usable text, degenerate canvas)."""
    W = int(row["canvas_width"])
    H = int(row["canvas_height"])
    if W < MIN_CANVAS_PX or H < MIN_CANVAS_PX:
        raise SkipTemplate("canvas too small")
    n = int(row.get("length") or len(row["type"]))
    if n > max_elements:
        raise SkipTemplate(f"{n} elements > {max_elements}")
    if n == 0:
        raise SkipTemplate("empty")

    def col(name: str, default: Any = None) -> list[Any]:
        v = row.get(name)
        if v is None:
            return [default] * n
        return list(v) + [default] * (n - len(v))

    lefts, tops, widths, heights = col("left", 0.0), col("top", 0.0), col("width", 0.0), col("height", 0.0)
    geom = [abs(float(v or 0.0)) for v in lefts + tops + widths + heights]
    normalized = max(geom, default=0.0) <= 2.0
    sx, sy = (float(W), float(H)) if normalized else (1.0, 1.0)

    types = col("type", "")
    angles = col("angle", 0.0)
    opacities = col("opacity", 1.0)
    palettes = col("color", [])
    texts = col("text", "")
    fonts = col("font", "")
    font_sizes = col("font_size", 0.0)
    bolds = col("font_bold", [])
    italics = col("font_italic", [])
    text_colors = col("text_color", [])
    aligns = col("text_align", "")
    caps = col("capitalize", False)
    line_heights = col("line_height", 1.2)
    letter_spacings = col("letter_spacing", 0.0)

    elements: list[dict[str, Any]] = []
    sidecar: dict[str, Any] = {"elements": {}, "normalized_coords": normalized, "angle_unit": angle_unit,
                               "boxes_normalized": normalize_boxes}
    n_text = 0
    for i in range(n):
        etype = str(types[i])
        x = float(lefts[i] or 0.0) * sx
        y = float(tops[i] or 0.0) * sy
        w = max(0.0, float(widths[i] or 0.0) * sx)
        h = max(0.0, float(heights[i] or 0.0) * sy)
        angle = float(angles[i] or 0.0)
        rotation = angle if angle_unit == "degrees" else math.degrees(angle)
        rotation = round(((rotation + 180.0) % 360.0) - 180.0, 2)
        opacity = max(0.0, min(1.0, float(opacities[i] if opacities[i] is not None else 1.0)))
        palette = [c for c in (palettes[i] or []) if c]
        eid = f"el_{i:02d}"
        el: dict[str, Any] = {"id": eid, "type": "", "x": round(x, 2), "y": round(y, 2),
                              "width": round(w, 2), "height": round(h, 2), "rotation": rotation,
                              "opacity": round(opacity, 3), "z_index": i, "group_id": None}
        side: dict[str, Any] = {"crello_type": etype, "palette": palette}

        if etype == "TextElement":
            content = str(texts[i] or "")
            content = re.sub("\n+", "\n", content)
            if caps[i] is True or str(caps[i]).lower() == "true":
                content = content.upper()
            fs = float(font_sizes[i] or 0.0)
            if not content.strip() or fs <= 0 or w <= 0:
                continue        # an invisible text layer: drop it from the eval design
            chars = len(content)
            b_list = [bool(v) for v in (bolds[i] or [])]
            i_list = [bool(v) for v in (italics[i] or [])]
            c_list = [str(v) for v in (text_colors[i] or [])]
            base_bold = _majority(b_list, False)
            base_italic = _majority(i_list, False)
            base_color = _rgba(_majority(c_list, palette[0] if palette else None))
            align = str(aligns[i] or "left")
            if align not in ("left", "center", "right"):
                align = "left"
            lh = float(line_heights[i] or 0.0)
            el.update({
                "type": "text",
                "content": content,
                "font_family": map_font(str(fonts[i] or "")),
                "font_size": round(fs, 2),
                "font_weight": "bold" if base_bold else "regular",
                "font_style": "italic" if base_italic else "normal",
                "color": base_color,
                "text_align": align,
                "line_height": round(lh, 3) if lh > 0 else 1.2,
                "letter_spacing": round(float(letter_spacings[i] or 0.0), 2),
            })
            runs = _style_runs(chars, c_list, b_list, i_list, base_color, base_bold, base_italic)
            if runs:
                el["style_runs"] = runs
            side.update({"font": str(fonts[i] or ""), "capitalize": bool(caps[i])})
            if normalize_boxes:
                from engine.textfit import default_measurer   # dev harness: the engine's own fit model

                grown = normalize_text_box(el, default_measurer())
                if grown:
                    side["box_grown"] = grown
            n_text += 1
        elif etype == "ColoredBackground":
            el.update({"type": "shape", "shape_type": "rectangle",
                       "fill_color": _rgba(palette[0] if palette else None, "rgba(255,255,255,1)"),
                       "stroke_color": None, "stroke_width": 0, "corner_radius": 0})
        elif etype == "SvgElement" and len(palette) == 1:
            el.update({"type": "shape", "shape_type": "rectangle", "fill_color": _rgba(palette[0]),
                       "stroke_color": None, "stroke_width": 0, "corner_radius": 0})
        else:
            asset, fit = asset_for_box(w, h, W, H, photo=etype in ("ImageElement", "SvgMaskElement"))
            el.update({"type": "image", "asset_id": asset, "fit": fit})
        elements.append(el)
        sidecar["elements"][eid] = side

    if n_text == 0:
        raise SkipTemplate("no text")
    if not elements:
        raise SkipTemplate("no elements")

    cid = str(row.get("id") or f"row{random.randrange(10**9)}")
    meta = {
        "crello_id": cid,
        "title": str(row.get("title") or ""),
        "format": str(row.get("format") or ""),
        "group": str(row.get("group") or ""),
        "category": str(row.get("category") or ""),
        "cluster_index": row.get("cluster_index"),
        "canvas": {"width": W, "height": H},
        "family": ratio_family(W, H),
        "n_elements": len(elements),
        "n_text": n_text,
    }
    return {"id": cid, "source": {"canvas": {"width": W, "height": H}, "elements": elements},
            "meta": meta, "sidecar": sidecar}


# ---------------------------------------------------------------------------
# siblings (same template at another size) and balanced selection


def _text_set(design: dict[str, Any]) -> set[str]:
    return {el["content"].strip().lower() for el in design["source"]["elements"]
            if el["type"] == "text" and len(el["content"].strip()) >= 3}


def find_pairs(designs: list[dict[str, Any]]) -> list[list[str]]:
    """Families of designs that share a title and at least one text string but
    differ in canvas size. Returns lists of ids (size >= 2)."""
    by_title: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for d in designs:
        t = d["meta"]["title"].strip().lower()
        if t and t != "none":
            by_title[t].append(d)
    groups: list[list[str]] = []
    for members in by_title.values():
        if len(members) < 2:
            continue
        sizes = {(m["meta"]["canvas"]["width"], m["meta"]["canvas"]["height"]) for m in members}
        if len(sizes) < 2:
            continue
        # keep members connected by shared text to the largest text set
        texts = {m["id"]: _text_set(m) for m in members}
        anchor = max(members, key=lambda m: len(texts[m["id"]]))
        fam = [m for m in members if m is anchor or texts[m["id"]] & texts[anchor["id"]]]
        fam_sizes = {(m["meta"]["canvas"]["width"], m["meta"]["canvas"]["height"]) for m in fam}
        if len(fam) >= 2 and len(fam_sizes) >= 2:
            groups.append([m["id"] for m in fam])
    return groups


def select_designs(designs: list[dict[str, Any]], target: int, seed: int = 0,
                   pairs: list[list[str]] | None = None) -> list[dict[str, Any]]:
    """Pick up to `target` designs: every member of a multi-size family first,
    then round-robin over ratio families so tall / square / wide / banner
    sources are all represented."""
    rng = random.Random(seed)
    by_id = {d["id"]: d for d in designs}
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for grp in pairs or []:
        for i in grp:
            if i in by_id and i not in seen and len(chosen) < target:
                chosen.append(by_id[i])
                seen.add(i)
    queues: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for d in designs:
        if d["id"] not in seen:
            queues[d["meta"]["family"]].append(d)
    for q in queues.values():
        rng.shuffle(q)
    order = [TALL, SQUARE, WIDE, BANNER]
    while len(chosen) < target and any(queues.values()):
        for fam in order:
            if queues[fam] and len(chosen) < target:
                d = queues[fam].pop()
                chosen.append(d)
                seen.add(d["id"])
    return chosen


# ---------------------------------------------------------------------------
# download


def _parse_shard_spec(spec: str) -> list[tuple[str, int]]:
    """'validation:0,1,2 test:0' -> [('validation',0),('validation',1),...]."""
    out: list[tuple[str, int]] = []
    for token in spec.split():
        if ":" not in token:
            out.extend((token, i) for i in range(SHARD_COUNTS[token]))
            continue
        split, idxs = token.split(":", 1)
        for i in idxs.split(","):
            if i.strip():
                out.append((split, int(i)))
    return out


def shard_path(split: str, idx: int) -> str:
    return f"{HF_REPO}/data/{split}-{idx:05d}-of-{SHARD_COUNTS[split]:05d}.parquet"


def fetch_shard(split: str, idx: int, raw_dir: Path = RAW_DIR, force: bool = False) -> Path:
    """Download the non-pixel columns of one shard into raw_dir (cached)."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / f"{split}-{idx:05d}.parquet"
    if out.exists() and not force:
        return out
    socket.setdefaulttimeout(180)
    fs = HfFileSystem()
    t0 = time.time()
    tmp = out.with_suffix(".part")
    with fs.open(shard_path(split, idx), "rb") as f:
        pf = pq.ParquetFile(f)
        cols = [c for c in pf.schema_arrow.names if c not in PIXEL_COLUMNS]
        table = pf.read(columns=cols)
    pq.write_table(table, tmp)
    tmp.replace(out)
    logger.info("fetched %s:%d (%d rows, %.1f MB) in %.0fs", split, idx, table.num_rows,
                out.stat().st_size / 1e6, time.time() - t0)
    return out


def load_raw(paths: Iterable[Path]) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for p in paths:
        pf = pq.ParquetFile(p)
        names = classlabel_names(pf.schema_arrow.metadata)
        for r in pf.read().to_pylist():
            rows.append(decode_row(r, names))
    return rows


# ---------------------------------------------------------------------------
# main


def build(shards: list[tuple[str, int]], target: int, max_elements: int, seed: int,
          data_dir: Path = DATA_DIR, force_download: bool = False, normalize_boxes: bool = True) -> dict[str, Any]:
    raw_dir = data_dir / "raw"
    designs_dir = data_dir / "designs"
    paths = [fetch_shard(s, i, raw_dir, force=force_download) for s, i in shards]
    rows = load_raw(paths)
    unit = detect_angle_unit(rows)
    logger.info("%d raw templates, rotation stored in %s", len(rows), unit)

    converted: list[dict[str, Any]] = []
    skipped: collections.Counter[str] = collections.Counter()
    for r in rows:
        try:
            converted.append(convert_template(r, angle_unit=unit, max_elements=max_elements,
                                              normalize_boxes=normalize_boxes))
        except SkipTemplate as exc:
            skipped[str(exc).split(" ")[0] if "elements" not in str(exc) else "too many elements"] += 1
        except Exception:
            logger.exception("conversion crashed on %s", r.get("id"))
            skipped["crash"] += 1
    logger.info("%d convertible, skipped %s", len(converted), dict(skipped))

    pairs = find_pairs(converted)
    logger.info("%d multi-size families (%d designs)", len(pairs), sum(len(p) for p in pairs))
    chosen = select_designs(converted, target, seed=seed, pairs=pairs)
    chosen_ids = {d["id"] for d in chosen}
    pairs = [[i for i in grp if i in chosen_ids] for grp in pairs]
    pairs = [grp for grp in pairs if len(grp) >= 2]
    siblings: dict[str, list[str]] = collections.defaultdict(list)
    for grp in pairs:
        for i in grp:
            siblings[i] = [j for j in grp if j != i]

    designs_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    for d in chosen:
        d["meta"]["siblings"] = siblings.get(d["id"], [])
        path = designs_dir / f"{d['id']}.json"
        path.write_text(json.dumps(d, indent=1))
        index.append({"id": d["id"], "file": str(path.relative_to(data_dir)), **d["meta"]})
    (data_dir / "index.json").write_text(json.dumps(index, indent=1))
    (data_dir / "pairs.json").write_text(json.dumps(pairs, indent=1))
    fam = collections.Counter(d["meta"]["family"] for d in chosen)
    n_text = sum(d["meta"]["n_text"] for d in chosen)
    grown = sum(1 for d in chosen for e in d["sidecar"]["elements"].values() if e.get("box_grown"))
    grown_w = sum(1 for d in chosen for e in d["sidecar"]["elements"].values() if "w" in (e.get("box_grown") or {}))
    logger.info("wrote %d designs to %s: %s; %d pairs; text boxes grown %d/%d (%d in width)",
                len(chosen), designs_dir, dict(fam), len(pairs), grown, n_text, grown_w)
    return {"n_raw": len(rows), "n_convertible": len(converted), "n_chosen": len(chosen),
            "families": dict(fam), "n_pairs": len(pairs), "skipped": dict(skipped), "angle_unit": unit,
            "n_text": n_text, "boxes_grown": grown, "boxes_grown_width": grown_w,
            "boxes_normalized": normalize_boxes}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shards", default=DEFAULT_SHARDS,
                    help="e.g. 'validation:0,1,2 test:0' or 'validation' for all shards of a split")
    ap.add_argument("--target", type=int, default=400, help="number of designs to keep")
    ap.add_argument("--max-elements", type=int, default=MAX_ELEMENTS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--force-download", action="store_true")
    ap.add_argument("--raw-boxes", action="store_true", help="keep Crello's text boxes as they are (see module doc)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = build(_parse_shard_spec(a.shards), a.target, a.max_elements, a.seed,
                  Path(a.data_dir), a.force_download, normalize_boxes=not a.raw_boxes)
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
