"""Designer references: the engine with the optimiser off vs on (v7).

For every reference (docs/designer*/out/<name>__<W>x<H>.json) this runs the
current engine twice on the same source and target, CHAMELEON_OPTIMIZE=0
and =1, and records per case: the engine's winner, its judge score and hard
fails, the designer-agreement metric (eval/metrics.designer_agreement), the
reference's own score under the current scorer, whether the designer wins
by that score, the design energy of both, and the runtime. Hold-out designs
(docs/designer2/holdout_ids.json) are reported in their own table and never
looked at while tuning.

    .venv/bin/python -m eval.compare_optimize [--names a,b] [--batch designer|designer2] [--out DIR] [--flag CHAMELEON_CRITIC]

`--flag` names another on/off switch to compare instead of the optimiser
(v9: CHAMELEON_CRITIC); the two modes are the flag at 0 and at 1.

Writes <out>/results.jsonl and <out>/SUMMARY.md (default
docs/designer/compare/v7_optimizer/).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHAMELEON_NO_RENDER", "1")

from engine.analyze import analyze  # noqa: E402
from engine.energy import energy_of  # noqa: E402
from engine.geometry import Box  # noqa: E402
from engine.score import score_design  # noqa: E402
from eval.metrics import designer_agreement  # noqa: E402
from eval.perturb_designer import BATCHES, Ref, references  # noqa: E402

OUT_DIR = ROOT.parent / "docs" / "designer" / "compare" / "v7_optimizer"
FLAG = "CHAMELEON_OPTIMIZE"       # the switch the two modes toggle (--flag)


def run_case(ref: Ref) -> dict[str, Any]:
    from engine.resize import resize_with_candidates

    an = analyze(ref.source)
    target = Box(0.0, 0.0, float(ref.W), float(ref.H))
    tdict = {"width": ref.W, "height": ref.H}
    s_ref = score_design(an, ref.source, ref.design, target, render=False)
    e_ref = energy_of(an, ref.source, ref.design, target)
    row: dict[str, Any] = {"name": ref.name, "batch": ref.batch, "format": f"{ref.W}x{ref.H}", "holdout": ref.holdout,
                           "ref_score": round(s_ref.total, 2), "ref_hard": list(s_ref.hard),
                           "ref_energy": round(e_ref.total, 3), "ref_energy_hard": list(e_ref.hard)}
    for mode in ("off", "on"):
        os.environ[FLAG] = "0" if mode == "off" else "1"
        t0 = time.time()
        design, judged = resize_with_candidates(ref.source, tdict)
        dt = time.time() - t0
        sc = judged[0].score if judged else score_design(an, ref.source, design, target, render=False)
        da = designer_agreement(design, ref.design, an)
        best_cand = max((float(designer_agreement(j.design, ref.design, an).get("da_agreement", 0.0))
                         for j in judged if not j.fallback), default=float("nan"))
        e = energy_of(an, ref.source, design, target)
        row[mode] = {"winner": judged[0].name if judged else "", "score": round(sc.total, 2), "hard": list(sc.hard),
                     "agreement": round(float(da.get("da_agreement", 0.0)), 4),
                     "pos_err": round(float(da.get("da_pos_err", 0.0)), 4),
                     "order_tau": da.get("da_order_tau"), "energy": round(e.total, 3), "energy_hard": list(e.hard),
                     "best_cand": round(best_cand, 4), "seconds": round(dt, 3), "designer_wins": bool(s_ref.total > sc.total),
                     "opt_won": bool(judged and judged[0].name.endswith("+opt"))}
    os.environ.pop(FLAG, None)
    return row


def _init_worker(flag: str) -> None:
    global FLAG
    FLAG = flag


def _safe_case(ref: Ref) -> dict[str, Any] | None:
    try:
        return run_case(ref)
    except Exception as exc:
        print(f"{ref.name} {ref.W}x{ref.H}: failed {exc!r}", flush=True)
        return None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def _p(xs, q):
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))] if s else float("nan")


def summary(rows: list[dict[str, Any]]) -> str:
    L = ["# Designer references: optimiser off vs on (v7)", "",
         f"{len(rows)} (design, format) cases; {sum(r['holdout'] for r in rows)} belong to the sealed hold-out designs "
         "and are reported separately below. Scores are the engine's own judge (no pixels); agreement is "
         "eval/metrics.designer_agreement (1 = the reference itself).", ""]

    def block(title: str, rs: list[dict[str, Any]]) -> None:
        if not rs:
            L.append(f"## {title}\n\n(no cases)\n")
            return
        L.append(f"## {title} ({len(rs)} cases)\n")
        L.append("| metric | optimiser off | optimiser on |")
        L.append("|---|---:|---:|")
        for label, fn, fmt in (
            ("designer agreement, mean", lambda m: _mean([r[m]["agreement"] for r in rs]), "{:.3f}"),
            ("best candidate agreement, mean", lambda m: _mean([r[m].get("best_cand") for r in rs]), "{:.3f}"),
            ("designer agreement >= 0.7", lambda m: sum(r[m]["agreement"] >= 0.7 for r in rs), "{}"),
            ("centre error, mean", lambda m: _mean([r[m]["pos_err"] for r in rs]), "{:.3f}"),
            ("reading-order tau, mean", lambda m: _mean([r[m]["order_tau"] for r in rs]), "{:.3f}"),
            ("engine cases with a hard fail (judge)", lambda m: sum(bool(r[m]["hard"]) for r in rs), "{}"),
            ("engine cases with a hard fail (energy)", lambda m: sum(bool(r[m]["energy_hard"]) for r in rs), "{}"),
            ("designer wins by judge score", lambda m: sum(r[m]["designer_wins"] for r in rs), "{}"),
            ("judge score, mean", lambda m: _mean([r[m]["score"] for r in rs]), "{:.2f}"),
            ("energy, mean (lower is better)", lambda m: _mean([r[m]["energy"] for r in rs]), "{:.2f}"),
            ("refined candidate wins", lambda m: sum(r[m]["opt_won"] for r in rs), "{}"),
            ("runtime p50 (s)", lambda m: _p([r[m]["seconds"] for r in rs], 0.5), "{:.2f}"),
            ("runtime p95 (s)", lambda m: _p([r[m]["seconds"] for r in rs], 0.95), "{:.2f}"),
        ):
            L.append(f"| {label} | {fmt.format(fn('off'))} | {fmt.format(fn('on'))} |")
        L.append(f"\nreferences with a hard fail under the current judge: {sum(bool(r['ref_hard']) for r in rs)}; "
                 f"under the energy: {sum(bool(r['ref_energy_hard']) for r in rs)}; reference energy mean "
                 f"{_mean([r['ref_energy'] for r in rs]):.2f}\n")
        better = sum(r["on"]["agreement"] > r["off"]["agreement"] + 1e-6 for r in rs)
        worse = sum(r["on"]["agreement"] < r["off"]["agreement"] - 1e-6 for r in rs)
        L.append(f"agreement up in {better}, down in {worse}, unchanged in {len(rs) - better - worse} cases\n")
        by_fmt: dict[str, list] = {}
        for r in rs:
            by_fmt.setdefault(r["format"], []).append(r)
        L.append("| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for f, fr in sorted(by_fmt.items(), key=lambda kv: -int(kv[0].split("x")[0]) * int(kv[0].split("x")[1])):
            L.append(f"| {f} | {len(fr)} | {_mean([r['off']['agreement'] for r in fr]):.3f} | {_mean([r['on']['agreement'] for r in fr]):.3f} | "
                     f"{sum(bool(r['off']['hard']) for r in fr)} | {sum(bool(r['on']['hard']) for r in fr)} | "
                     f"{sum(r['off']['designer_wins'] for r in fr)} | {sum(r['on']['designer_wins'] for r in fr)} |")
        L.append("")

    block("Tuning set (batch one + batch two without the hold-out)", [r for r in rows if not r["holdout"]])
    block("HOLD-OUT (10 sealed designs, never tuned on)", [r for r in rows if r["holdout"]])
    moved = sorted(rows, key=lambda r: r["on"]["agreement"] - r["off"]["agreement"])
    L.append("## Largest agreement changes (on - off)\n")
    for r in moved[:8] + moved[-8:]:
        L.append(f"- {r['name']} {r['format']}: {r['off']['agreement']:.3f} -> {r['on']['agreement']:.3f} "
                 f"({r['off']['winner'][:30]} -> {r['on']['winner'][:30]})")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    global FLAG
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--names", default="")
    ap.add_argument("--batch", default="", help="designer | designer2 (default both)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--flag", default=FLAG, help="environment switch compared at 0 vs 1 (default CHAMELEON_OPTIMIZE)")
    ap.add_argument("--workers", type=int, default=1, help="spawned worker processes")
    args = ap.parse_args(argv)
    FLAG = args.flag
    names = {n for n in args.names.split(",") if n} or None
    batches = [b for b in BATCHES if not args.batch or b.name == args.batch]
    refs = references(batches, names)
    if args.limit:
        refs = refs[: args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    t0 = time.time()
    if args.workers > 1:
        import multiprocessing as mp
        pool = mp.get_context("spawn").Pool(args.workers, initializer=_init_worker, initargs=(FLAG,))
        results = pool.imap(_safe_case, refs, chunksize=2)
    else:
        results = map(_safe_case, refs)
    with (args.out / "results.jsonl").open("w") as f:
        for i, row in enumerate(results):
            if row is None:
                continue
            rows.append(row)
            f.write(json.dumps(row) + "\n")
            if (i + 1) % 24 == 0:
                print(f"{i + 1}/{len(refs)} in {time.time() - t0:.0f} s", flush=True)
    (args.out / "SUMMARY.md").write_text(summary(rows))
    print("wrote", args.out / "SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
