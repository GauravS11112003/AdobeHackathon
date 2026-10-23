"""Run the engine over every converted design x every preset and tabulate.

    .venv/bin/python -m eval.run_eval --limit 20                 # smoke run (~2 min)
    nohup .venv/bin/python -m eval.run_eval --workers 4 > eval/data/runs/full/stdout.log 2>&1 &
    .venv/bin/python -m eval.run_eval --summarize-only           # rebuild CSV + summary

Cases: for each design in eval/data/index.json (first --limit of them), one
case per preset in the catalogue (the same PRESETS list as tools/playground.py,
read from that file) plus, when Crello has the same template at another size,
one "ground truth" case per sibling (target = the sibling's canvas) so
`gt_*` columns can compare our layout with the designer's.

Each case calls engine.resize.resize_with_candidates, computes the metrics
in eval/metrics.py and appends one JSON line to <run>/results.jsonl; the
winner's JSON goes to <run>/outputs/. The run is resumable: cases already in
results.jsonl are skipped. Progress (done / total, rate, ETA, running defect
rate) is logged every few seconds to stdout and <run>/progress.log. At the
end (or with --summarize-only) results.csv, summary.json and summary.md are
written next to it.

Engine crashes are caught per case and recorded in the `error` column; the
run goes on. Workers are separate processes (spawn), each importing the
engine once; --no-render judges on geometry alone (CHAMELEON_NO_RENDER=1).
"""

from __future__ import annotations

import argparse
import ast
import collections
import csv
import json
import logging
import os
import statistics
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR, ratio_family  # noqa: E402
from eval.metrics import DEFECT_COUNTS, DEFECT_FLAGS, defect_count  # noqa: E402

PLAYGROUND = ROOT / "tools" / "playground.py"
RUNS_DIR = DATA_DIR / "runs"
SAMPLES_DIR = ROOT / "input"

logger = logging.getLogger("eval.run_eval")

CSV_COLUMNS = [
    "design_id", "title", "src_w", "src_h", "src_family", "preset", "tgt_w", "tgt_h", "tgt_family",
    "ratio_change", "n_elements", "n_text", "elapsed", "error", "winner", "strategy", "fallback",
    "n_candidates", "n_clean_candidates", "defect_n", "ids_ok", "ids_order_ok", "fields_ok",
    "immutable_ok", "canvas_ok", "offcanvas_n", "offcanvas_ids", "offcanvas_worst_frac",
    "aspect_fail_n", "aspect_max_drift", "overflow_n", "overflow_ids", "min_font", "min_font_primary",
    "below_floor_n", "below_floor_ids", "font_scale_vs_canvas", "overlap_n", "overlap_area",
    "overlap_frac", "overlap_pairs", "judge_hard_n", "judge_contrast_fail_n", "judge_hard",
    "score_total", "score_soft", "runner_up_gap", "read.size", "read.lines", "read.contrast",
    "read.presence", "layout.balance", "layout.alignment", "layout.spacing", "layout.fill",
    "layout.margins", "faith.order", "faith.anchors", "faith.hierarchy", "faith.scale", "pixels",
    "gt_id", "gt_n", "gt_pos_err", "gt_order_tau", "gt_size_rho", "gt_font_ratio", "gt_width_ratio",
]


# ---------------------------------------------------------------------------
# presets


def load_presets(path: Path = PLAYGROUND) -> list[tuple[str, int, int]]:
    """The playground's PRESETS literal, parsed from the file (no import, so
    the HTTP server module is never executed)."""
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PRESETS" for t in node.targets):
            value = ast.literal_eval(node.value)
            return [(str(n), int(w), int(h)) for n, w, h in value]
    raise RuntimeError(f"PRESETS not found in {path}")


# ---------------------------------------------------------------------------
# cases


def load_index(data_dir: Path) -> list[dict[str, Any]]:
    p = data_dir / "index.json"
    if not p.exists():
        raise SystemExit(f"{p} missing: run `python -m eval.crello_convert` first")
    return json.loads(p.read_text())


def sample_designs() -> list[dict[str, Any]]:
    """The three shipped samples as index rows (always evaluated too)."""
    rows = []
    for p in sorted(SAMPLES_DIR.glob("*.json")):
        t = json.loads(p.read_text())
        c = t["source"]["canvas"]
        rows.append({"id": p.stem, "file": str(p), "title": t.get("task_id", p.stem), "canvas": c,
                     "family": ratio_family(c["width"], c["height"]),
                     "n_elements": len(t["source"]["elements"]),
                     "n_text": sum(1 for e in t["source"]["elements"] if e["type"] == "text"),
                     "siblings": [], "sample": True})
    return rows


def build_cases(index: list[dict[str, Any]], presets: list[tuple[str, int, int]], data_dir: Path,
                with_gt: bool = True) -> list[dict[str, Any]]:
    by_id = {d["id"]: d for d in index}
    cases = []
    for d in index:
        # a design may carry its own target list (eval/synth.py nasty cases:
        # 1x1, 4000x4000, identical, +3 % ...) instead of the preset catalogue
        own = [(f"own:{t['name']}", int(t["width"]), int(t["height"])) for t in d.get("targets") or []]
        for name, w, h in own or presets:
            cases.append({"key": f"{d['id']}|{name}", "design": d, "preset": name,
                          "target": {"width": w, "height": h}, "gt_id": None})
        if with_gt:
            for sib in d.get("siblings", []):
                s = by_id.get(sib)
                if s is None:
                    continue
                cases.append({"key": f"{d['id']}|gt:{sib}", "design": d, "preset": f"gt:{sib}",
                              "target": dict(s["canvas"]), "gt_id": sib})
    return cases


def _design_path(d: dict[str, Any], data_dir: Path) -> Path:
    p = Path(d["file"])
    return p if p.is_absolute() else data_dir / p


def _load_source(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text())
    return doc["source"] if "source" in doc else doc


# ---------------------------------------------------------------------------
# one case (runs in a worker)


def run_case(case: dict[str, Any], data_dir: str, outputs_dir: str | None) -> dict[str, Any]:
    from engine.resize import resize_with_candidates
    from eval.metrics import evaluate_case

    d = case["design"]
    target = case["target"]
    row: dict[str, Any] = {
        "design_id": d["id"], "title": d.get("title", "")[:60],
        "src_w": d["canvas"]["width"], "src_h": d["canvas"]["height"], "src_family": d["family"],
        "preset": case["preset"], "tgt_w": target["width"], "tgt_h": target["height"],
        "tgt_family": ratio_family(target["width"], target["height"]),
        "n_elements": d.get("n_elements"), "n_text": d.get("n_text"), "gt_id": case.get("gt_id"),
        "error": "",
    }
    if d.get("props"):
        row["props"] = d["props"]
        for k, v in d["props"].items():
            row[f"prop.{k}"] = v
    if d.get("synthetic"):
        row["synthetic"] = True
    sx = target["width"] / d["canvas"]["width"]
    sy = target["height"] / d["canvas"]["height"]
    row["ratio_change"] = round(max(sx, sy) / min(sx, sy), 3)
    try:
        source = _load_source(_design_path(d, Path(data_dir)))
        gt = None
        if case.get("gt_id"):
            gt_path = Path(data_dir) / "designs" / f"{case['gt_id']}.json"
            if gt_path.exists():
                gt = _load_source(gt_path)
        t0 = time.perf_counter()
        best, judged = resize_with_candidates(source, target)
        elapsed = time.perf_counter() - t0
        row.update(evaluate_case(source, best, target, judged, elapsed, gt=gt))
        if outputs_dir:
            safe = case["key"].replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")
            Path(outputs_dir, f"{safe}.json").write_text(json.dumps(best))
    except Exception as exc:  # the harness must survive any engine crash
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
        row["traceback"] = traceback.format_exc()[-2000:]
        row["defect_n"] = defect_count(row)
    row["key"] = case["key"]
    return row


# ---------------------------------------------------------------------------
# summary


def _pct(n: float, d: float) -> str:
    return f"{100.0 * n / d:.1f}%" if d else "-"


def _p(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]


def _fail_flags(r: dict[str, Any]) -> dict[str, bool]:
    return {
        "any_defect": bool(r.get("defect_n")),
        "error": bool(r.get("error")),
        "ids": not r.get("ids_ok", True),
        "fields": not r.get("fields_ok", True) or not r.get("immutable_ok", True) or not r.get("canvas_ok", True),
        "offcanvas": bool(r.get("offcanvas_n")),
        "aspect": bool(r.get("aspect_fail_n")),
        "overflow": bool(r.get("overflow_n")),
        "below_floor": bool(r.get("below_floor_n")),
        "overlap": bool(r.get("overlap_n")),
        "judge_hard": bool(r.get("judge_hard_n")),
        "judge_contrast": bool(r.get("judge_contrast_fail_n")),
        "fallback": bool(r.get("fallback")),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in rows]
    preset_rows = [r for r in rows if not str(r.get("preset", "")).startswith("gt:")]
    gt_rows = [r for r in rows if str(r.get("preset", "")).startswith("gt:") and r.get("gt_n")]
    flags = [_fail_flags(r) for r in rows]
    n = len(rows)
    summary: dict[str, Any] = {
        "n_cases": n,
        "n_designs": len({r["design_id"] for r in rows}),
        "n_preset_cases": len(preset_rows),
        "n_gt_cases": len(gt_rows),
    }
    summary["failure_rate"] = {k: sum(f[k] for f in flags) / n if n else 0.0 for k in flags[0]} if flags else {}
    summary["failure_count"] = {k: sum(f[k] for f in flags) for k in flags[0]} if flags else {}

    def by(keyfn, name):
        groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for r in rows:
            groups[str(keyfn(r))].append(r)
        out = {}
        for g, rs in sorted(groups.items()):
            fl = [_fail_flags(r) for r in rs]
            scores = [r["score_total"] for r in rs if isinstance(r.get("score_total"), (int, float))]
            out[g] = {
                "n": len(rs),
                "any_defect": sum(f["any_defect"] for f in fl) / len(rs),
                "offcanvas": sum(f["offcanvas"] for f in fl) / len(rs),
                "overflow": sum(f["overflow"] for f in fl) / len(rs),
                "overlap": sum(f["overlap"] for f in fl) / len(rs),
                "below_floor": sum(f["below_floor"] for f in fl) / len(rs),
                "aspect": sum(f["aspect"] for f in fl) / len(rs),
                "error": sum(f["error"] for f in fl) / len(rs),
                "judge_contrast": sum(f["judge_contrast"] for f in fl) / len(rs),
                "score_mean": statistics.fmean(scores) if scores else None,
                "elapsed_p50": _p([r["elapsed"] for r in rs if r.get("elapsed") is not None], 0.5),
            }
        summary[name] = out

    by(lambda r: r.get("src_family"), "by_src_family")
    by(lambda r: r.get("tgt_family"), "by_tgt_family")
    by(lambda r: "gt (designer siblings)" if str(r.get("preset", "")).startswith("gt:") else r.get("preset"),
       "by_preset")
    by(lambda r: f"{r.get('src_family')}->{r.get('tgt_family')}", "by_family_pair")

    el = [r["elapsed"] for r in rows if r.get("elapsed") is not None]
    summary["runtime"] = {"p50": _p(el, 0.5), "p95": _p(el, 0.95), "max": max(el) if el else None,
                          "mean": statistics.fmean(el) if el else None}
    strat = collections.Counter(r.get("strategy") or "error" for r in rows)
    summary["strategy_share"] = {k: v / n for k, v in strat.items()} if n else {}
    win = collections.Counter(r.get("winner") or "error" for r in rows)
    summary["winner_top"] = win.most_common(15)
    hard = collections.Counter()
    for r in rows:
        for h in str(r.get("judge_hard") or "").split(" | "):
            h = h.strip()
            if h:
                hard[_normalize_hard(h)] += 1
    summary["judge_hard_top"] = hard.most_common(12)
    scores = [r["score_total"] for r in rows if isinstance(r.get("score_total"), (int, float))]
    summary["score"] = {"mean": statistics.fmean(scores) if scores else None, "p10": _p(scores, 0.1),
                        "p50": _p(scores, 0.5), "p90": _p(scores, 0.9)}
    comps = collections.defaultdict(list)
    for r in rows:
        for k, v in r.items():
            if (k.startswith("read.") or k.startswith("layout.") or k.startswith("faith.")) and isinstance(v, (int, float)):
                comps[k].append(v)
    summary["score_components_mean"] = {k: statistics.fmean(v) for k, v in sorted(comps.items())}
    summary["min_font"] = {"p05": _p([r["min_font"] for r in rows if r.get("min_font") is not None], 0.05),
                           "p50": _p([r["min_font"] for r in rows if r.get("min_font") is not None], 0.5)}
    if gt_rows:
        def mean_of(k):
            v = [r[k] for r in gt_rows if isinstance(r.get(k), (int, float))]
            return statistics.fmean(v) if v else None
        summary["ground_truth"] = {
            "n_cases": len(gt_rows),
            "matched_text_mean": mean_of("gt_n"),
            "pos_err_mean": mean_of("gt_pos_err"),
            "pos_err_p50": _p([r["gt_pos_err"] for r in gt_rows if r.get("gt_pos_err") is not None], 0.5),
            "order_tau_mean": mean_of("gt_order_tau"),
            "order_tau_share_ge_0.5": (sum(1 for r in gt_rows if (r.get("gt_order_tau") or 0) >= 0.5)
                                       / len(gt_rows)),
            "size_rho_mean": mean_of("gt_size_rho"),
            "font_ratio_p50": _p([r["gt_font_ratio"] for r in gt_rows if r.get("gt_font_ratio") is not None], 0.5),
            "width_ratio_p50": _p([r["gt_width_ratio"] for r in gt_rows if r.get("gt_width_ratio") is not None], 0.5),
        }
    return summary


def _normalize_hard(h: str) -> str:
    import re
    h = re.sub(r"\bel_\d+\b|group:\S+|\b[a-z_]+_\d+\b", "<el>", h)
    h = re.sub(r"\d+(\.\d+)?", "N", h)
    return h[:70]


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def summary_markdown(s: dict[str, Any]) -> str:
    L: list[str] = []
    L.append(f"Cases: **{s['n_cases']}** ({s['n_designs']} designs; {s['n_preset_cases']} preset cases, "
             f"{s['n_gt_cases']} ground-truth cases)\n")
    L.append("### Failure rate by metric\n")
    L.append("| metric | cases | rate |\n|---|---:|---:|")
    for k, v in s.get("failure_rate", {}).items():
        L.append(f"| {k} | {s['failure_count'][k]} | {_pct(v, 1)} |")
    for name, title in (("by_src_family", "By source ratio family"), ("by_tgt_family", "By target family"),
                        ("by_family_pair", "By source -> target family"), ("by_preset", "By preset")):
        L.append(f"\n### {title}\n")
        L.append("| group | n | any defect | off-canvas | overflow | overlap | below floor | aspect | error | "
                 "contrast (judge) | score mean | p50 s |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for g, r in s.get(name, {}).items():
            L.append(f"| {g} | {r['n']} | {_pct(r['any_defect'], 1)} | {_pct(r['offcanvas'], 1)} | "
                     f"{_pct(r['overflow'], 1)} | {_pct(r['overlap'], 1)} | {_pct(r['below_floor'], 1)} | "
                     f"{_pct(r['aspect'], 1)} | {_pct(r['error'], 1)} | {_pct(r['judge_contrast'], 1)} | "
                     f"{_fmt(r['score_mean'])} | {_fmt(r['elapsed_p50'])} |")
    rt = s.get("runtime", {})
    L.append("\n### Runtime per case (s)\n")
    L.append("| p50 | p95 | max | mean |\n|---:|---:|---:|---:|")
    L.append(f"| {_fmt(rt.get('p50'))} | {_fmt(rt.get('p95'))} | {_fmt(rt.get('max'))} | {_fmt(rt.get('mean'))} |")
    L.append("\n### Strategy share / winners\n")
    L.append("| strategy | share |\n|---|---:|")
    for k, v in sorted(s.get("strategy_share", {}).items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {_pct(v, 1)} |")
    L.append("\n| winner | cases |\n|---|---:|")
    for k, v in s.get("winner_top", []):
        L.append(f"| {k} | {v} |")
    L.append("\n### Judge score\n")
    sc = s.get("score", {})
    L.append("| mean | p10 | p50 | p90 |\n|---:|---:|---:|---:|")
    L.append(f"| {_fmt(sc.get('mean'))} | {_fmt(sc.get('p10'))} | {_fmt(sc.get('p50'))} | {_fmt(sc.get('p90'))} |")
    L.append("\n| component | mean (0-1) |\n|---|---:|")
    for k, v in s.get("score_components_mean", {}).items():
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("\n### Judge hard fails (winner), most common\n")
    L.append("| message (normalised) | cases |\n|---|---:|")
    for k, v in s.get("judge_hard_top", []):
        L.append(f"| {k} | {v} |")
    mf = s.get("min_font", {})
    L.append(f"\nSmallest font in the output: p05 = {_fmt(mf.get('p05'))}px, p50 = {_fmt(mf.get('p50'))}px\n")
    gt = s.get("ground_truth")
    if gt:
        L.append("### Ground truth (designer's own version at the target size)\n")
        L.append("| metric | value |\n|---|---:|")
        for k, v in gt.items():
            L.append(f"| {k} | {_fmt(v)} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# io


def read_results(run_dir: Path) -> list[dict[str, Any]]:
    p = run_dir / "results.jsonl"
    rows: list[dict[str, Any]] = []
    if not p.exists():
        return rows
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # keep the last row per key (a resumed run may re-append)
    last: dict[str, dict[str, Any]] = {}
    for r in rows:
        last[r.get("key") or f"{r.get('design_id')}|{r.get('preset')}"] = r
    return list(last.values())


def write_outputs(run_dir: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    with (run_dir / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    s = summarize(rows)
    (run_dir / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    (run_dir / "summary.md").write_text(summary_markdown(s))
    return s


# ---------------------------------------------------------------------------
# main loop


def run(args: argparse.Namespace) -> Path:
    data_dir = Path(args.data_dir)
    if args.synthetic and args.name == "full":
        args.name = "synth"
    run_dir = Path(args.out) if args.out else RUNS_DIR / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    log_path = run_dir / "progress.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logging.getLogger().addHandler(handler)

    if args.summarize_only:
        rows = read_results(run_dir)
        s = write_outputs(run_dir, rows)
        logger.info("summarised %d cases -> %s", len(rows), run_dir)
        print(summary_markdown(s))
        return run_dir

    if args.synthetic:
        # generate the corpus into its own data dir (designs/ + index.json)
        # unless the user pointed --data-dir somewhere explicitly
        from eval.synth import SYNTH_DIR, write_corpus

        if data_dir == DATA_DIR:
            data_dir = SYNTH_DIR
        index_rows = write_corpus(data_dir, args.synthetic, args.seed, with_nasty=not args.no_nasty)
        logger.info("synthetic corpus: %d designs (seed %d) -> %s", len(index_rows), args.seed, data_dir)
        args.no_samples = True
        args.no_gt = True

    presets = load_presets()
    if args.presets:
        wanted = {p.strip().lower() for p in args.presets.split(",")}
        presets = [p for p in presets if p[0].lower() in wanted]
        if not presets:
            raise SystemExit(f"no preset matches {args.presets}")
    index = load_index(data_dir) if not args.samples_only else []
    if args.limit:
        index = index[: args.limit]
    if not args.no_samples:
        index = sample_designs() + index
    cases = build_cases(index, presets, data_dir, with_gt=not args.no_gt)
    done = {r["key"] for r in read_results(run_dir) if r.get("key")}
    todo = [c for c in cases if c["key"] not in done]
    logger.info("run %s: %d designs x %d presets (+gt) = %d cases, %d done, %d to do, workers=%d, render=%s",
                run_dir.name, len(index), len(presets), len(cases), len(cases) - len(todo), len(todo),
                args.workers, "off" if args.no_render else "on")
    if args.no_render:
        os.environ["CHAMELEON_NO_RENDER"] = "1"

    t0 = time.time()
    n_done = 0
    n_defect = 0
    n_err = 0
    last_log = 0.0
    results_path = run_dir / "results.jsonl"

    def record(row: dict[str, Any]) -> None:
        nonlocal n_done, n_defect, n_err, last_log
        with results_path.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        n_done += 1
        n_defect += 1 if row.get("defect_n") else 0
        n_err += 1 if row.get("error") else 0
        if row.get("error"):
            logger.warning("ERROR %s: %s", row["key"], row["error"])
        now = time.time()
        if now - last_log >= args.log_every or n_done == len(todo):
            last_log = now
            rate = n_done / max(now - t0, 1e-6)
            eta = (len(todo) - n_done) / rate if rate else float("inf")
            logger.info("%d/%d done (%.1f/s, ETA %.0fs) defects %s errors %d", n_done, len(todo), rate,
                        eta, _pct(n_defect, n_done), n_err)

    if args.workers <= 1:
        for c in todo:
            record(run_case(c, str(data_dir), str(outputs_dir)))
    else:
        import multiprocessing as mp

        with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn")) as ex:
            futs = [ex.submit(run_case, c, str(data_dir), str(outputs_dir)) for c in todo]
            for fut in as_completed(futs):
                try:
                    record(fut.result())
                except Exception as exc:  # a worker died (segfault etc.)
                    logger.error("worker failure: %s", exc)
    rows = read_results(run_dir)
    s = write_outputs(run_dir, rows)
    logger.info("finished: %d cases in %.0fs -> %s", len(rows), time.time() - t0, run_dir)
    print(summary_markdown(s))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--name", default="full", help="run name under eval/data/runs/")
    ap.add_argument("--out", default=None, help="explicit run directory (overrides --name)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N designs of the index")
    ap.add_argument("--presets", default="", help="comma-separated preset names (default: all)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--no-render", action="store_true", help="judge on geometry only (faster)")
    ap.add_argument("--no-gt", action="store_true", help="skip the ground-truth sibling cases")
    ap.add_argument("--no-samples", action="store_true", help="do not add the three shipped samples")
    ap.add_argument("--samples-only", action="store_true", help="only the three shipped samples")
    ap.add_argument("--summarize-only", action="store_true")
    ap.add_argument("--synthetic", type=int, default=0, metavar="N",
                    help="generate N designs with eval/synth.py (plus the nasty cases) into "
                         "eval/data/synth/ and evaluate those instead of the Crello index")
    ap.add_argument("--seed", type=int, default=1, help="seed for --synthetic")
    ap.add_argument("--no-nasty", action="store_true", help="--synthetic without the nasty cases")
    ap.add_argument("--log-every", type=float, default=15.0, help="seconds between progress lines")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("engine").setLevel(logging.ERROR)
    run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
