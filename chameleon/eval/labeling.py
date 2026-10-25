"""Human-labelling loop for the scorer: pair sampling, label store, weak labels.

The playground's /label page (tools/playground.py) shows two rendered
candidates for the same source and target side by side and asks which one
looks better. Everything that is not HTTP lives here so tests and
eval/calibrate.py can use it:

  * `next_pair()`        picks an informative pair: a random eval design and
                         a preset (formats and shape families under-labelled
                         so far are preferred), runs the engine, and chooses
                         two non-fallback candidates whose geometric totals
                         are close; pairs where only one side has a hard
                         fail are never offered (the scorer already knows).
                         Mode "runs" compares two harness runs' outputs for
                         the same case instead.
  * `append_label()` / `undo_label()` / `label_stats()`
                         the label store, one JSON object per line in
                         eval/data/labels.jsonl: case key, both sides (id,
                         name, strategy, total, hard fails, breakdown and the
                         design itself so the pair can be re-scored under
                         future metrics), decision, timestamp.
  * `write_weak_labels()` the bootstrap: the engine's winner vs the same
                         layout with 40 % of the content units shifted by
                         30 % of the canvas (the perturbation probe from
                         tools/vlm_bench.py). Written to a separate file,
                         eval/data/labels_weak.jsonl, used by the calibration
                         with a lower weight.

Decisions: "a" (A better), "b" (B better), "tie", "both_bad".
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import sys
import threading
import time
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR, ratio_family  # noqa: E402

LABELS_FILE = DATA_DIR / "labels.jsonl"
WEAK_LABELS_FILE = DATA_DIR / "labels_weak.jsonl"
INPUT_DIR = ROOT / "input"
DECISIONS = ("a", "b", "tie", "both_bad")
CLOSENESS_TAU = 5.0          # pair weight exp(-|total_a - total_b| / tau)
CLEAN_PAIR_PROB = 0.85       # prefer clean-clean pairs over hard-hard pairs this often
PERTURB_FRAC = 0.4           # weak labels: share of content units moved ...
PERTURB_SHIFT = 0.3          # ... by this fraction of the canvas
PERTURB_TRIES = 5            # seeds tried to find a perturbation without a new hard fail

_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# designs and presets


def load_presets() -> list[tuple[str, int, int]]:
    from eval.run_eval import load_presets as _lp

    return _lp()


def designs_index(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
    """Index rows of every eval design plus the three shipped samples."""
    from eval.run_eval import sample_designs

    rows = sample_designs()
    p = data_dir / "index.json"
    if p.exists():
        rows += json.loads(p.read_text())
    return rows


def design_path(row: dict[str, Any], data_dir: Path = DATA_DIR) -> Path:
    p = Path(row["file"])
    return p if p.is_absolute() else data_dir / p


def load_source(row: dict[str, Any], data_dir: Path = DATA_DIR) -> dict[str, Any]:
    doc = json.loads(design_path(row, data_dir).read_text())
    return doc["source"] if "source" in doc else doc


def source_hash(source: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(source, sort_keys=True).encode()).hexdigest()[:12]


def case_key(design_id: str, preset: str) -> str:
    return f"{design_id}|{preset}"


def safe_key(key: str) -> str:
    """The harness's file name for a case (eval/run_eval.py)."""
    return key.replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")


# ---------------------------------------------------------------------------
# sides and records


def side_from_judged(j: Any) -> dict[str, Any]:
    sc = j.score
    return {"id": j.name, "name": j.name, "strategy": j.strategy, "total": round(float(sc.total), 3),
            "hard": list(sc.hard), "penalty": round(float(getattr(sc, "penalty", 0.0)), 3),
            "breakdown": {k: round(float(v), 4) for k, v in sc.breakdown.items()}, "design": j.design}


def side_from_row(run: str, row: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    bd = {k: float(v) for k, v in row.items() if k.startswith(("read.", "layout.", "faith."))}
    hard = [h for h in str(row.get("judge_hard") or "").split(";") if h.strip()]
    total = float(row.get("score_total", 0.0))
    soft = float(row.get("score_soft", total))
    return {"id": run, "name": f"{run}: {row.get('winner', '')}", "strategy": row.get("strategy", ""),
            "total": round(total, 3), "hard": hard, "penalty": round(soft - total - 1000.0 * len(hard), 3),
            "breakdown": bd, "design": design}


def one_sided_hard(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return bool(a["hard"]) != bool(b["hard"])


def pair_weight(a: dict[str, Any], b: dict[str, Any], tau: float = CLOSENESS_TAU) -> float:
    return math.exp(-abs(float(a["total"]) - float(b["total"])) / tau)


def choose_pair(sides: list[dict[str, Any]], rng: random.Random, tau: float = CLOSENESS_TAU
                ) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Two distinct sides, both clean or both with hard fails, close totals
    preferred. None when no such pair exists."""
    sides = [s for s in sides if not s.get("fallback")]
    clean = [s for s in sides if not s["hard"]]
    dirty = [s for s in sides if s["hard"]]
    pools = [p for p in (clean, dirty) if len(p) >= 2]
    if not pools:
        return None
    if len(pools) == 2:
        pool = clean if rng.random() < CLEAN_PAIR_PROB else dirty
    else:
        pool = pools[0]
    pairs = [(x, y) for x, y in combinations(pool, 2) if x["design"] != y["design"]]
    if not pairs:
        return None
    weights = [pair_weight(x, y, tau) for x, y in pairs]
    a, b = rng.choices(pairs, weights=weights, k=1)[0]
    return (a, b) if rng.random() < 0.5 else (b, a)


def _balanced_choice(rng: random.Random, options: list[Any], keyfn, counts: dict[str, int]) -> Any:
    """Pick an option, favouring keys with few labels so far (weight 1/(1+n))."""
    weights = [1.0 / (1.0 + counts.get(keyfn(o), 0)) for o in options]
    return rng.choices(options, weights=weights, k=1)[0]


def sample_case(rng: random.Random, index: list[dict[str, Any]], presets: list[tuple[str, int, int]],
                stats: dict[str, Any] | None = None) -> tuple[dict[str, Any], tuple[str, int, int]]:
    """A design and a preset; target families and source families that have
    fewer labels so far are more likely."""
    stats = stats or {}
    fam_counts = stats.get("by_tgt_family", {})
    families = sorted({ratio_family(w, h) for _, w, h in presets})
    fam = _balanced_choice(rng, families, lambda f: f, fam_counts)
    preset = rng.choice([p for p in presets if ratio_family(p[1], p[2]) == fam])
    row = _balanced_choice(rng, index, lambda r: r.get("family", ""), stats.get("by_src_family", {}))
    return row, preset


def _record(mode: str, row: dict[str, Any], preset: str, target: dict[str, int], source: dict[str, Any],
            a: dict[str, Any], b: dict[str, Any], **extra: Any) -> dict[str, Any]:
    from engine.relayout import ratio_change
    from engine.geometry import Box

    c = source["canvas"]
    rc = ratio_change(Box(0, 0, float(c["width"]), float(c["height"])),
                      Box(0, 0, float(target["width"]), float(target["height"])))
    return {"mode": mode, "case_key": case_key(row["id"], preset), "design_id": row["id"],
            "design_file": str(row.get("file", "")), "title": row.get("title", ""),
            "source_hash": source_hash(source), "preset": preset, "target": dict(target),
            "src_family": ratio_family(c["width"], c["height"]),
            "tgt_family": ratio_family(target["width"], target["height"]), "ratio_change": round(rc, 3),
            "a": a, "b": b, **extra}



# ---------------------------------------------------------------------------
# source quality: skip designs the harness itself broke (stand-in assets,
# truncated text) so human labels judge the engine, not the eval data


def source_quality(source: dict[str, Any], *, max_panel_share: float = 0.55) -> list[str]:
    """Reasons this *source* is not a fair test. Empty list = fine.

    - a text whose content does not fit its own box at its own font (truncated
      or wrapped off the box: 'IENCE / LIGION' in the labels round-1 sheets);
    - an image whose asset file is missing (renders as the grey placeholder);
    - an opaque non-background shape covering a large share of the canvas
      (a photo that the Crello conversion replaced by a blank panel);
    """
    from engine.textfit import default_measurer
    from engine.geometry import Box
    from engine.contrast import ASSETS_DIR

    issues: list[str] = []
    c = source["canvas"]; cw, ch = float(c["width"]), float(c["height"]); area = cw * ch
    m = default_measurer()
    texts = []
    for el in source["elements"]:
        t = el.get("type")
        if t == "text":
            try:
                if not m.fits(el, float(el["font_size"]), float(el["width"]), float(el["height"]), slack=2.0):
                    issues.append(f"source text overflows its box: {el['id']}")
            except Exception:
                pass
            texts.append(el)
        elif t == "image":
            aid = el.get("asset_id")
            if aid and not (Path(ASSETS_DIR) / str(aid)).is_file():
                issues.append(f"missing asset: {el['id']}")
        elif t == "shape":
            b = Box.of(el)
            share = min(b.area, area) / area
            alpha = float(el.get("opacity", 1.0))
            if max_panel_share <= share < 0.85 and alpha >= 0.9 and str(el.get("shape_type")) == "rectangle":
                # a card with text on it is design; a big empty rectangle is a photo the
                # conversion replaced (nothing is drawn on it)
                covered = any(e.get("type") in ("text", "image") and b.contains_fraction(Box.of(e)) >= 0.5
                              for e in source["elements"] if e is not el)
                if not covered:
                    issues.append(f"large blank panel ({share:.0%}): {el['id']}")
    # Text-box overlap is deliberately NOT a reason: designers stack and lock up
    # text boxes all the time ("17" over "JULY", a date under a weekday); the
    # truncated-text case is already caught by the overflow check above.
    return issues

# ---------------------------------------------------------------------------
# pair sampling


def judge_pair(source: dict[str, Any], target: dict[str, int], rng: random.Random,
               tau: float = CLOSENESS_TAU) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Run the engine and pick a pair among its candidates."""
    from engine.resize import resize_with_candidates

    _, judged = resize_with_candidates(source, target)
    sides = []
    for j in judged:
        s = side_from_judged(j)
        s["fallback"] = bool(getattr(j, "fallback", False))
        sides.append(s)
    pair = choose_pair(sides, rng, tau)
    if pair is None:
        return None
    for s in pair:
        s.pop("fallback", None)
    return pair


def next_pair(mode: str = "candidates", rng: random.Random | None = None, *, data_dir: Path = DATA_DIR,
              presets: list[tuple[str, int, int]] | None = None, stats: dict[str, Any] | None = None,
              runs: tuple[str, str] | None = None, tries: int = 12) -> dict[str, Any]:
    """An unlabelled pair as a record without decision (the UI adds the
    decision and posts it back). Raises RuntimeError when nothing suitable
    was found in `tries` attempts."""
    rng = rng or random.Random()
    if mode == "runs":
        if not runs or len(runs) != 2:
            raise ValueError("mode 'runs' needs two run names")
        return _next_runs_pair(runs, rng, data_dir, stats, tries)
    presets = presets or load_presets()
    index = designs_index(data_dir)
    last_err = "no designs"
    for _ in range(tries):
        row, (pname, w, h) = sample_case(rng, index, presets, stats)
        target = {"width": w, "height": h}
        try:
            source = load_source(row, data_dir)
            issues = source_quality(source)
            if issues:
                last_err = f"{row['id']}: unfair source ({issues[0]})"
                continue
            pair = judge_pair(source, target, rng)
        except Exception as exc:  # a broken design is skipped, not fatal
            last_err = f"{row['id']}: {exc!r}"
            continue
        if pair is None:
            last_err = f"{row['id']} x {pname}: fewer than two comparable candidates"
            continue
        a, b = pair
        return _record("candidates", row, pname, target, source, a, b)
    raise RuntimeError(f"no informative pair found in {tries} tries (last: {last_err})")


def _run_rows(run: str, data_dir: Path) -> dict[str, dict[str, Any]]:
    f = data_dir / "runs" / run / "results.jsonl"
    rows = {}
    if f.is_file():
        for line in f.open():
            if line.strip():
                r = json.loads(line)
                rows[r["key"]] = r
    return rows


def _next_runs_pair(runs: tuple[str, str], rng: random.Random, data_dir: Path, stats: dict[str, Any] | None,
                    tries: int) -> dict[str, Any]:
    ra, rb = runs
    rows_a, rows_b = _run_rows(ra, data_dir), _run_rows(rb, data_dir)
    index = {r["id"]: r for r in designs_index(data_dir)}
    common = [k for k in rows_a if k in rows_b and not rows_a[k].get("error") and not rows_b[k].get("error")
              and rows_a[k]["design_id"] in index and not str(rows_a[k].get("preset", "")).startswith("gt:")]
    if not common:
        raise RuntimeError(f"runs {ra!r} and {rb!r} share no cases")
    stats = stats or {}
    fam_counts = stats.get("by_tgt_family", {})
    for _ in range(tries):
        key = _balanced_choice(rng, common, lambda k: rows_a[k].get("tgt_family", ""), fam_counts)
        row_a, row_b = rows_a[key], rows_b[key]
        if bool(row_a.get("judge_hard_n")) != bool(row_b.get("judge_hard_n")):
            continue
        # closeness: keep with probability of the pair weight (always keep ties)
        if rng.random() > math.exp(-abs(float(row_a["score_total"]) - float(row_b["score_total"])) / CLOSENESS_TAU):
            continue
        pa = data_dir / "runs" / ra / "outputs" / f"{safe_key(key)}.json"
        pb = data_dir / "runs" / rb / "outputs" / f"{safe_key(key)}.json"
        if not (pa.exists() and pb.exists()):
            continue
        da, db = json.loads(pa.read_text()), json.loads(pb.read_text())
        if da == db:
            continue
        drow = index[row_a["design_id"]]
        source = load_source(drow, data_dir)
        a, b = side_from_row(ra, row_a, da), side_from_row(rb, row_b, db)
        if rng.random() < 0.5:
            a, b = b, a
        target = {"width": int(row_a["tgt_w"]), "height": int(row_a["tgt_h"])}
        return _record("runs", drow, row_a["preset"], target, source, a, b, runs=[ra, rb])
    raise RuntimeError(f"no informative pair between runs {ra!r} and {rb!r} in {tries} tries")


# ---------------------------------------------------------------------------
# label store


def read_labels(path: Path = LABELS_FILE) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).open():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def append_label(record: dict[str, Any], decision: str, path: Path = LABELS_FILE, *,
                 kind: str = "human", seconds: float | None = None) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")
    rec = dict(record)
    rec.update({"decision": decision, "kind": kind, "ts": time.time(),
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())})
    if seconds is not None:
        rec["seconds"] = round(float(seconds), 2)
    path = Path(path)
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def undo_label(path: Path = LABELS_FILE) -> dict[str, Any] | None:
    """Remove the last label; returns it (or None when the file is empty)."""
    path = Path(path)
    with _write_lock:
        labels = read_labels(path)
        if not labels:
            return None
        last = labels.pop()
        tmp = path.with_suffix(".tmp")
        with tmp.open("w") as f:
            for rec in labels:
                f.write(json.dumps(rec) + "\n")
        os.replace(tmp, path)
    return last


def scorer_prediction(rec: dict[str, Any]) -> str:
    da = float(rec["a"]["total"]) - float(rec["b"]["total"])
    return "a" if da > 1e-9 else "b" if da < -1e-9 else "tie"


def label_stats(path: Path = LABELS_FILE) -> dict[str, Any]:
    labels = read_labels(path)
    by = lambda key: _count(labels, key)  # noqa: E731
    decisive = [r for r in labels if r.get("decision") in ("a", "b")]
    agree = sum(1 for r in decisive if scorer_prediction(r) == r["decision"])
    return {"n": len(labels), "by_decision": by("decision"), "by_tgt_family": by("tgt_family"),
            "by_src_family": by("src_family"), "by_preset": by("preset"), "by_mode": by("mode"),
            "scorer_agree": agree, "scorer_n": len(decisive),
            "designs": len({r.get("design_id") for r in labels}),
            "last": _brief(labels[-1]) if labels else None}


def _count(labels: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in labels:
        k = str(r.get(key, ""))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _brief(rec: dict[str, Any]) -> dict[str, Any]:
    return {"case_key": rec.get("case_key"), "decision": rec.get("decision"), "ts_iso": rec.get("ts_iso"),
            "a": {k: rec["a"].get(k) for k in ("id", "name", "total", "hard")},
            "b": {k: rec["b"].get(k) for k in ("id", "name", "total", "hard")},
            "scorer": scorer_prediction(rec)}


# ---------------------------------------------------------------------------
# weak labels (perturbation bootstrap)


def perturb(source: dict[str, Any], analysis: Any, rng: random.Random, frac: float = PERTURB_FRAC,
            shift: float = PERTURB_SHIFT) -> dict[str, Any]:
    """Move `frac` of the content units by `shift` of the canvas along one
    axis, as far as the canvas allows (same probe as tools/vlm_bench.py)."""
    bad = copy.deepcopy(source)
    cw, ch = source["canvas"]["width"], source["canvas"]["height"]
    content = list(analysis.content_units())
    if not content:
        return bad
    k = max(1, round(frac * len(content)))
    chosen = rng.sample(content, k) if len(content) >= k else content
    by_id = {e["id"]: e for e in bad["elements"]}
    for u in chosen:
        ids = [i for i in u.ids if i in by_id]
        if not ids:
            continue
        xs = [float(by_id[i]["x"]) for i in ids]
        ys = [float(by_id[i]["y"]) for i in ids]
        rs = [float(by_id[i]["x"]) + float(by_id[i]["width"]) for i in ids]
        bs = [float(by_id[i]["y"]) + float(by_id[i]["height"]) for i in ids]
        ux, uy, uw, uh = min(xs), min(ys), max(rs) - min(xs), max(bs) - min(ys)
        axis = rng.choice(["x", "y"])
        sign = rng.choice([-1, 1])
        dx = dy = 0.0
        for ax in (axis, "y" if axis == "x" else "x"):
            if ax == "x":
                room_neg, room_pos, d = ux, cw - (ux + uw), shift * cw
            else:
                room_neg, room_pos, d = uy, ch - (uy + uh), shift * ch
            if sign < 0 and room_neg >= d:
                move = -d
            elif sign > 0 and room_pos >= d:
                move = d
            elif room_neg >= d:
                move = -d
            elif room_pos >= d:
                move = d
            else:
                move = -room_neg if room_neg >= room_pos else room_pos
            if abs(move) >= 0.5 * d:
                if ax == "x":
                    dx = move
                else:
                    dy = move
                break
        for eid in ids:
            e = by_id[eid]
            e["x"] = round(float(e["x"]) + dx, 2)
            e["y"] = round(float(e["y"]) + dy, 2)
    return bad


def weak_pair(source: dict[str, Any], target: dict[str, int], rng: random.Random, *,
              tries: int = PERTURB_TRIES) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(good, bad) sides: the engine's winner and a perturbed copy of it,
    both scored without pixels. Perturbations that add a hard fail are
    retried a few times (the soft terms are what the calibration learns
    from); the last try is kept whatever it did. None when the winner
    itself has hard fails or the perturbation moved nothing."""
    from engine.analyze import analyze
    from engine.geometry import Box
    from engine.resize import resize_with_candidates
    from engine.score import score_design

    best, judged = resize_with_candidates(source, target)
    if not judged or judged[0].score.hard or judged[0].fallback:
        return None
    winner = judged[0]
    analysis = analyze(source)
    tbox = Box(0.0, 0.0, float(target["width"]), float(target["height"]))
    # perturb() takes the units from the source analysis and their boxes from
    # the output's elements, so no re-analysis of the output is needed
    good = side_from_judged(winner)
    good["hard"] = []
    bad_design = None
    bad_score = None
    for _ in range(tries):
        cand = perturb(best, analysis, rng)
        if cand == best:
            continue
        sc = score_design(analysis, source, cand, tbox, render=False, strategy=winner.strategy)
        bad_design, bad_score = cand, sc
        if not sc.hard:
            break
    if bad_design is None or bad_score is None:
        return None
    bad = {"id": "perturbed", "name": f"perturbed {winner.name}", "strategy": winner.strategy,
           "total": round(float(bad_score.total), 3), "hard": list(bad_score.hard),
           "penalty": round(float(bad_score.penalty), 3),
           "breakdown": {k: round(float(v), 4) for k, v in bad_score.breakdown.items()}, "design": bad_design}
    good["id"] = "winner"
    return good, bad


def write_weak_labels(n: int = 300, seed: int = 0, path: Path = WEAK_LABELS_FILE, *,
                      data_dir: Path = DATA_DIR, presets: list[tuple[str, int, int]] | None = None,
                      log=None) -> int:
    """Append `n` weak-label records to `path` (balanced over target families,
    A/B order randomised, decision = the unperturbed side). Returns the number
    written."""
    rng = random.Random(seed)
    presets = presets or load_presets()
    index = designs_index(data_dir)
    stats: dict[str, Any] = {"by_tgt_family": {}, "by_src_family": {}}
    written = 0
    attempts = 0
    while written < n and attempts < 4 * n + 20:
        attempts += 1
        row, (pname, w, h) = sample_case(rng, index, presets, stats)
        target = {"width": w, "height": h}
        try:
            source = load_source(row, data_dir)
            pair = weak_pair(source, target, rng)
        except Exception as exc:
            if log:
                log(f"skip {row['id']} x {pname}: {exc!r}")
            continue
        if pair is None:
            continue
        good, bad = pair
        if rng.random() < 0.5:
            a, b, decision = good, bad, "a"
        else:
            a, b, decision = bad, good, "b"
        rec = _record("perturb", row, pname, target, source, a, b, seed=seed)
        append_label(rec, decision, path, kind="weak")
        for key, fam in (("by_tgt_family", rec["tgt_family"]), ("by_src_family", rec["src_family"])):
            stats[key][fam] = stats[key].get(fam, 0) + 1
        written += 1
        if log and written % 25 == 0:
            log(f"{written}/{n} weak pairs")
    return written


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="write perturbation weak labels")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=WEAK_LABELS_FILE)
    ap.add_argument("--fresh", action="store_true", help="delete the file first")
    args = ap.parse_args(argv)
    os.environ.setdefault("CHAMELEON_NO_RENDER", "1")
    if args.fresh and args.out.exists():
        args.out.unlink()
    t0 = time.time()
    n = write_weak_labels(args.n, args.seed, args.out, log=lambda s: print(s, flush=True))
    print(f"wrote {n} weak labels to {args.out} in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
