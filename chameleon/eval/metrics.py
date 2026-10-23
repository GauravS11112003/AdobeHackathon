"""Per-case metrics for the eval harness (shared by run_eval.py and the tests).

`evaluate_case(source, output, target, judged, elapsed)` turns one engine run
into a flat dict of numbers and short strings that fits a CSV row:

  structural   ids preserved (set + order), required fields per type, canvas
               matches the target, immutable fields untouched (content,
               font_family, asset_id, shape_type, style_runs), important
               (non background / decorative) units fully on canvas, image
               aspect drift for `contain` images within 5 %
  text         measured overflow per engine.textfit, smallest font, smallest
               headline / CTA font vs. the floor-plan minimum for the canvas
  overlap      unwanted overlap (engine.rectify.unwanted_overlaps: content
               units that did not overlap in the source), count and area
  judge        which candidate won, its strategy, the score breakdown
  ground truth `gt_agreement(output, designer_version)` when Crello has the
               same template at the target size: position error, reading
               order agreement, size-hierarchy agreement on matched text

Nothing here changes the engine; it only reads its public pieces.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from engine.analyze import BACKGROUND, DECORATIVE, CTA, HEADLINE, Analysis, analyze
from engine.floorplan import Metrics, ratio_family
from engine.geometry import Box
from engine.rectify import rotated_extent, unwanted_overlaps
from engine.textfit import TextMeasurer, default_measurer

ASPECT_TOL = 0.05
ON_CANVAS_TOL = 0.5
REQUIRED = {
    "text": ("content", "font_family", "font_size", "color"),
    "image": ("asset_id",),
    "shape": ("shape_type", "fill_color"),
}
IMMUTABLE = ("type", "content", "font_family", "asset_id", "shape_type", "style_runs", "group_id")
DEFECT_FLAGS = ("ids_ok", "fields_ok", "immutable_ok", "canvas_ok")
DEFECT_COUNTS = ("offcanvas_n", "aspect_fail_n", "overflow_n", "below_floor_n", "overlap_n")


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# structural


def structural(source: dict[str, Any], output: dict[str, Any], target: dict[str, Any],
               analysis: Analysis | None = None) -> dict[str, Any]:
    analysis = analysis or analyze(source)
    src = source["elements"]
    out = output.get("elements") or []
    src_ids = [e["id"] for e in src]
    out_ids = [e.get("id") for e in out]
    m: dict[str, Any] = {}
    m["ids_ok"] = sorted(map(str, src_ids)) == sorted(map(str, out_ids)) and len(set(out_ids)) == len(out_ids)
    m["ids_order_ok"] = src_ids == out_ids
    m["canvas_ok"] = (output.get("canvas", {}).get("width") == target["width"]
                      and output.get("canvas", {}).get("height") == target["height"])

    fields_ok = True
    immutable_ok = True
    src_by_id = {e["id"]: e for e in src}
    for e in out:
        for k in ("id", "type", "x", "y", "width", "height"):
            if k not in e:
                fields_ok = False
        for k in REQUIRED.get(e.get("type", ""), ()):
            if k not in e:
                fields_ok = False
        if _f(e.get("width")) < 0 or _f(e.get("height")) < 0:
            fields_ok = False
        if e.get("type") == "text" and _f(e.get("font_size")) < 1:
            fields_ok = False
        s = src_by_id.get(e.get("id"))
        if s is not None:
            for k in IMMUTABLE:
                if k in s and s[k] != e.get(k):
                    immutable_ok = False
    m["fields_ok"] = fields_ok
    m["immutable_ok"] = immutable_ok

    # important units on canvas (unit = group bbox, so a badge label inside
    # its pill is judged with the pill)
    W, H = float(target["width"]), float(target["height"])
    out_by_id = {e.get("id"): e for e in out}
    off: list[str] = []
    worst = 0.0
    for u in analysis.units:
        if u.role in (BACKGROUND, DECORATIVE):
            continue
        # Drawn extent: a rotated element's box is in its own frame, the
        # renderer rotates it about its centre.
        boxes = [rotated_extent(Box.of(out_by_id[i]), _f(out_by_id[i].get("rotation", 0.0)))
                 for i in u.ids if i in out_by_id]
        if not boxes:
            continue
        b = Box.union(boxes)
        over = max(-b.x, -b.y, b.right - W, b.bottom - H, 0.0)
        if over > ON_CANVAS_TOL:
            off.append(u.key)
            inside = Box(0, 0, W, H).contains_fraction(b)
            worst = max(worst, 1.0 - inside)
    m["offcanvas_n"] = len(off)
    m["offcanvas_ids"] = ";".join(off)
    m["offcanvas_worst_frac"] = round(worst, 4)

    # image aspect
    fails = 0
    max_drift = 0.0
    for e in out:
        if e.get("type") != "image" or e.get("fit", "contain") == "cover":
            continue
        s = src_by_id.get(e.get("id"))
        if not s or _f(s["width"]) <= 0 or _f(s["height"]) <= 0 or _f(e.get("height")) <= 0:
            continue
        drift = abs((_f(e["width"]) / _f(e["height"])) / (_f(s["width"]) / _f(s["height"])) - 1.0)
        max_drift = max(max_drift, drift)
        if drift > ASPECT_TOL:
            fails += 1
    m["aspect_fail_n"] = fails
    m["aspect_max_drift"] = round(max_drift, 4)
    return m


# ---------------------------------------------------------------------------
# text


def text_metrics(source: dict[str, Any], output: dict[str, Any], target: dict[str, Any],
                 analysis: Analysis | None = None, measurer: TextMeasurer | None = None) -> dict[str, Any]:
    analysis = analysis or analyze(source)
    mm = measurer or default_measurer()
    tgt = Box(0.0, 0.0, float(target["width"]), float(target["height"]))
    met = Metrics.for_canvas(analysis.canvas, tgt, ratio_family(tgt))
    overflow: list[str] = []
    below: list[str] = []
    min_font = math.inf
    min_primary = math.inf
    n_text = 0
    src_by_id = {e["id"]: e for e in source["elements"]}
    ratios: list[float] = []
    for e in output.get("elements") or []:
        if e.get("type") != "text":
            continue
        n_text += 1
        font = _f(e.get("font_size"))
        min_font = min(min_font, font)
        try:
            if not mm.fits(e, font, _f(e.get("width")), _f(e.get("height"))):
                overflow.append(e["id"])
        except Exception:
            overflow.append(e["id"])
        role = analysis.roles.get(e["id"])
        if role in (HEADLINE, CTA):
            min_primary = min(min_primary, font)
            if font < met.min_font(role) - 0.5:
                below.append(e["id"])
        s = src_by_id.get(e["id"])
        if s and _f(s.get("font_size")) > 0:
            ratios.append(font / _f(s["font_size"]))
    area_scale = math.sqrt(tgt.area / analysis.canvas.area)
    return {
        "n_text": n_text,
        "overflow_n": len(overflow),
        "overflow_ids": ";".join(overflow),
        "min_font": round(min_font, 2) if n_text else None,
        "min_font_primary": round(min_primary, 2) if min_primary < math.inf else None,
        "below_floor_n": len(below),
        "below_floor_ids": ";".join(below),
        # how the text scaled vs. the canvas (1.0 = kept pace with sqrt(area ratio))
        "font_scale_vs_canvas": round((sum(ratios) / len(ratios)) / area_scale, 3) if ratios else None,
    }


# ---------------------------------------------------------------------------
# overlap


def overlap_metrics(source: dict[str, Any], output: dict[str, Any], target: dict[str, Any],
                    analysis: Analysis | None = None, measurer: TextMeasurer | None = None) -> dict[str, Any]:
    analysis = analysis or analyze(source)
    try:
        pairs = unwanted_overlaps(analysis, output["elements"], measurer or default_measurer())
    except Exception:
        pairs = []
    area = sum(a for _, _, a in pairs)
    canvas_area = max(1.0, float(target["width"]) * float(target["height"]))
    return {
        "overlap_n": len(pairs),
        "overlap_area": round(area, 1),
        "overlap_frac": round(area / canvas_area, 5),
        "overlap_pairs": ";".join(f"{a}+{b}" for a, b, _ in pairs[:6]),
    }


# ---------------------------------------------------------------------------
# ground truth (designer's own version at the target size)


def _norm_text(s: str) -> str:
    return " ".join(str(s).split()).strip().lower()


def match_text_elements(ours: dict[str, Any], theirs: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair text elements by (normalised) content; duplicates are matched in
    reading order of the source."""
    def texts(d: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in sorted(d["elements"], key=lambda e: (_f(e.get("y")), _f(e.get("x")))):
            if e.get("type") == "text" and _norm_text(e.get("content", "")):
                out.setdefault(_norm_text(e["content"]), []).append(e)
        return out

    a, b = texts(ours), texts(theirs)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key, ea in a.items():
        eb = b.get(key)
        if not eb:
            continue
        for x, y in zip(ea, eb):
            pairs.append((x, y))
    return pairs


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(a) != len(b):
        return None
    ra, rb = _rank(a), _rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return 1.0 if da == db else 0.0
    return num / (da * db)


def kendall_tau(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 2 or n != len(b):
        return None
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    tot = conc + disc
    return (conc - disc) / tot if tot else 1.0


def gt_agreement(ours: dict[str, Any], theirs: dict[str, Any]) -> dict[str, Any]:
    """How close our layout is to the designer's version of the same template
    at (about) the same canvas. Everything is computed on text elements
    matched by content, in canvas-normalised coordinates:

      gt_n          matched text elements
      gt_pos_err    mean distance between matched centres (fraction of the
                    canvas diagonal; 0 = identical placement)
      gt_order_tau  Kendall tau between reading orders (y then x); 1 = same
      gt_size_rho   Spearman correlation of font sizes (size hierarchy)
      gt_font_ratio median of our font / their font (1 = same type scale)
      gt_width_ratio median of our box width / their box width
    """
    pairs = match_text_elements(ours, theirs)
    W1, H1 = float(ours["canvas"]["width"]), float(ours["canvas"]["height"])
    W2, H2 = float(theirs["canvas"]["width"]), float(theirs["canvas"]["height"])
    res: dict[str, Any] = {"gt_n": len(pairs)}
    if not pairs:
        return res
    cx1 = [(_f(a["x"]) + _f(a["width"]) / 2) / W1 for a, _ in pairs]
    cy1 = [(_f(a["y"]) + _f(a["height"]) / 2) / H1 for a, _ in pairs]
    cx2 = [(_f(b["x"]) + _f(b["width"]) / 2) / W2 for _, b in pairs]
    cy2 = [(_f(b["y"]) + _f(b["height"]) / 2) / H2 for _, b in pairs]
    dist = [math.hypot(x1 - x2, y1 - y2) / math.sqrt(2) for x1, y1, x2, y2 in zip(cx1, cy1, cx2, cy2)]
    res["gt_pos_err"] = round(sum(dist) / len(dist), 4)
    # reading order: rank by rows (y) then x, with a row tolerance
    def order_keys(cx: list[float], cy: list[float]) -> list[float]:
        return [round(y, 2) * 10 + x for x, y in zip(cx, cy)]
    res["gt_order_tau"] = (round(kendall_tau(order_keys(cx1, cy1), order_keys(cx2, cy2)), 3)
                           if len(pairs) >= 2 else None)
    f1 = [_f(a.get("font_size")) for a, _ in pairs]
    f2 = [_f(b.get("font_size")) for _, b in pairs]
    res["gt_size_rho"] = round(spearman(f1, f2), 3) if len(pairs) >= 2 else None
    # type scale relative to the canvas (their canvas may differ slightly from ours)
    scale = math.sqrt((W1 * H1) / (W2 * H2))
    ratios = sorted(a / (b * scale) for a, b in zip(f1, f2) if b > 0)
    res["gt_font_ratio"] = round(ratios[len(ratios) // 2], 3) if ratios else None
    wr = sorted((_f(a["width"]) / W1) / max(_f(b["width"]) / W2, 1e-6) for a, b in pairs)
    res["gt_width_ratio"] = round(wr[len(wr) // 2], 3) if wr else None
    return res


# ---------------------------------------------------------------------------
# everything for one case


def evaluate_case(source: dict[str, Any], output: dict[str, Any], target: dict[str, Any],
                  judged: Iterable[Any] = (), elapsed: float | None = None,
                  gt: dict[str, Any] | None = None, measurer: TextMeasurer | None = None) -> dict[str, Any]:
    analysis = analyze(source)
    row: dict[str, Any] = {}
    row.update(structural(source, output, target, analysis))
    row.update(text_metrics(source, output, target, analysis, measurer))
    row.update(overlap_metrics(source, output, target, analysis, measurer))
    judged = list(judged)
    if judged:
        best = judged[0]
        row["winner"] = best.name
        row["strategy"] = best.strategy
        row["fallback"] = bool(best.fallback)
        row["n_candidates"] = len(judged)
        row["n_clean_candidates"] = sum(1 for j in judged if not j.score.hard)
        row["judge_hard_n"] = len(best.score.hard)
        row["judge_hard"] = " | ".join(best.score.hard)[:400]
        row["judge_contrast_fail_n"] = sum("contrast" in h for h in best.score.hard)
        row["score_total"] = round(best.score.total, 2)
        row["score_soft"] = round(best.score.soft, 2)
        for k, v in best.score.breakdown.items():
            row[k] = round(v, 3)
        row["pixels"] = best.summary().get("pixels")
        if len(judged) > 1:
            row["runner_up_gap"] = round(best.score.total - judged[1].score.total, 2)
    else:
        row["winner"] = ""
        row["strategy"] = ""
        row["fallback"] = True
        row["n_candidates"] = 0
    if elapsed is not None:
        row["elapsed"] = round(elapsed, 3)
    if gt is not None:
        row.update(gt_agreement(output, gt))
    row["defect_n"] = defect_count(row)
    return row


def defect_count(row: dict[str, Any]) -> int:
    """Number of distinct hard problems in a row (used for ranking the worst
    cases and for the failure-rate tables). Contrast fails from the judge are
    not counted here: with brand-kit stand-in assets they mostly reflect the
    asset substitution, not the layout."""
    n = 0
    for k in DEFECT_FLAGS:
        if k in row and not row[k]:
            n += 1
    for k in DEFECT_COUNTS:
        n += 1 if row.get(k) else 0
    if row.get("error"):
        n += 1
    return n
