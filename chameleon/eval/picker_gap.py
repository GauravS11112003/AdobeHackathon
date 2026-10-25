"""The picker gap on the designer references (v8).

For every reference (docs/designer*/out/<name>__<W>x<H>.json) this runs the
current engine once (default settings: optimiser on, no pixels) and records
*every judged candidate*: name, strategy, whether it is a refined "+opt"
layout, the judge's full breakdown / hard fails / penalty / total, the design
energy terms, and the designer agreement with the reference
(eval/metrics.designer_agreement). The reference itself is scored by the
same judge (so it can serve as a pair side) and its energy recorded.

The report answers the v7 follow-up questions: how often the candidate with
the best agreement is in the judged set but not the winner, how large the
best-vs-chosen gap is, and which breakdown terms are responsible when the
winner is not the best (sum of weight x term difference, winner minus best),
split by target format family and by seed family (anchor / template /
structure, plain / +opt) of the winner and of the best candidate.

    .venv/bin/python -m eval.picker_gap [--workers 4] [--batch designer|designer2] [--out DIR] [--limit N]
    .venv/bin/python -m eval.picker_gap --report-only [--out DIR]       # re-read <out>/candidates.jsonl

Writes <out>/candidates.jsonl (one line per case, every candidate inside)
and <out>/REPORT.md (default docs/designer/compare/v8_picker/). Hold-out
designs (docs/designer2/holdout_ids.json) are flagged per case and reported
in their own block; nothing here fits anything.

The dump is also the data of eval/fit_judge.py (the v8 weight fit): with the
judge's total being  sum_k W_k * bd_k - 1000 * |hard| - penalty, any
re-weighting can be evaluated offline by re-ranking the stored candidates.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHAMELEON_NO_RENDER", "1")

OUT_DIR = ROOT.parent / "docs" / "designer" / "compare" / "v8_picker"
GAP_MIN = 0.02            # a case counts as "the judge missed" when the best candidate beats the winner by this much


def seed_family(name: str, strategy: str) -> str:
    base = {"anchor": "anchor", "floorplan": "template", "structure": "structure"}.get(strategy, strategy)
    return base + ("+opt" if name.endswith("+opt") else "")


def run_case(ref_index: int, batch_names: list[str], names: list[str] | None) -> dict[str, Any]:
    """One reference: engine once, every candidate recorded. Runs in a worker."""
    from engine.analyze import analyze
    from engine.energy import energy_of
    from engine.geometry import Box
    from engine.resize import resize_with_candidates
    from engine.score import WEIGHTS, score_design
    from eval.metrics import designer_agreement
    from eval.perturb_designer import BATCHES, references

    batches = [b for b in BATCHES if b.name in batch_names]
    ref = references(batches, set(names) if names else None)[ref_index]
    an = analyze(ref.source)
    target = Box(0.0, 0.0, float(ref.W), float(ref.H))
    tdict = {"width": ref.W, "height": ref.H}
    from engine.relayout import ratio_change
    from engine.floorplan import ratio_family
    row: dict[str, Any] = {
        "name": ref.name, "batch": ref.batch, "format": f"{ref.W}x{ref.H}", "holdout": ref.holdout,
        "source_file": ref.source_file, "target": tdict,
        "tgt_family": ratio_family(target), "ratio_change": round(ratio_change(an.canvas, target), 3),
        "weights": dict(WEIGHTS),
    }
    s_ref = score_design(an, ref.source, ref.design, target, render=False)
    e_ref = energy_of(an, ref.source, ref.design, target)
    row["reference"] = {"total": round(s_ref.total, 3), "hard": list(s_ref.hard), "penalty": round(s_ref.penalty, 3),
                        "breakdown": {k: round(v, 5) for k, v in s_ref.breakdown.items()},
                        "energy": {"total": round(e_ref.total, 3), "hard": list(e_ref.hard),
                                   "terms": {k: round(v, 5) for k, v in e_ref.terms.items()}}}
    t0 = time.perf_counter()
    design, judged = resize_with_candidates(ref.source, tdict)
    row["seconds"] = round(time.perf_counter() - t0, 3)
    cands = []
    for rank, j in enumerate(judged):
        da = designer_agreement(j.design, ref.design, an)
        try:
            e = energy_of(an, ref.source, j.design, target)
            energy = {"total": round(e.total, 3), "hard": list(e.hard),
                      "terms": {k: round(v, 5) for k, v in e.terms.items()}}
        except Exception as exc:  # pragma: no cover
            energy = {"total": None, "hard": [], "terms": {}, "error": repr(exc)}
        cands.append({"rank": rank, "name": j.name, "strategy": j.strategy, "fallback": bool(j.fallback),
                      "family": seed_family(j.name, j.strategy), "opt": j.name.endswith("+opt"),
                      "total": round(j.score.total, 3), "hard": list(j.score.hard),
                      "penalty": round(j.score.penalty, 3),
                      "breakdown": {k: round(v, 5) for k, v in j.score.breakdown.items()},
                      "notes": {k: v for k, v in j.score.notes.items()
                                if k in ("adaptation_penalty", "disruption_penalty", "archetype_penalty", "structure_prior")},
                      "agreement": round(float(da.get("da_agreement", 0.0)), 4),
                      "da": {k: v for k, v in da.items() if k != "da_agreement"},
                      "energy": energy, "design": j.design})
    row["candidates"] = cands
    return row


# ---------------------------------------------------------------------------
# report


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def _p(xs, q):
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))] if s else float("nan")


def winner_and_best(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """(winner, best-agreement candidate, best *clean* candidate or None)."""
    cands = row["candidates"]
    winner = cands[0]
    best = max(cands, key=lambda c: (c["agreement"], -c["rank"]))
    clean = [c for c in cands if not c["hard"] and not c["fallback"]]
    best_clean = max(clean, key=lambda c: (c["agreement"], -c["rank"])) if clean else None
    return winner, best, best_clean


def blame(row: dict[str, Any], winner: dict[str, Any], best: dict[str, Any]) -> dict[str, float]:
    """Weighted term differences winner - best (positive = the term voted for
    the winner), plus the pinned parts (hard fails, penalties)."""
    w = row["weights"]
    out = {k: w.get(k, 0.0) * (winner["breakdown"].get(k, 0.0) - best["breakdown"].get(k, 0.0))
           for k in set(winner["breakdown"]) | set(best["breakdown"])}
    out["hard"] = -1000.0 * (len(winner["hard"]) - len(best["hard"]))
    out["penalty"] = -(winner["penalty"] - best["penalty"])
    return out


def report(rows: list[dict[str, Any]]) -> str:
    L = ["# The picker gap on the designer references (v8 diagnosis)", "",
         f"{len(rows)} (design, format) cases, {sum(r['holdout'] for r in rows)} of them from the sealed hold-out "
         "designs (own block). One engine run per case (optimiser on, no pixels); every judged candidate is "
         "scored for designer agreement (eval/metrics.designer_agreement, 1 = the reference itself). "
         "'best' is the candidate with the highest agreement, 'winner' the one the judge returned.", ""]

    def block(title: str, rs: list[dict[str, Any]]) -> None:
        if not rs:
            return
        L.append(f"## {title} ({len(rs)} cases)\n")
        wb = [(r, *winner_and_best(r)) for r in rs]
        win_ag = [w["agreement"] for _, w, _, _ in wb]
        best_ag = [b["agreement"] for _, _, b, _ in wb]
        bc_ag = [bc["agreement"] if bc else w["agreement"] for _, w, _, bc in wb]
        gaps = [b["agreement"] - w["agreement"] for _, w, b, _ in wb]
        missed = [(r, w, b) for r, w, b, _ in wb if b["agreement"] - w["agreement"] >= GAP_MIN]
        L.append("| metric | value |")
        L.append("|---|---:|")
        L.append(f"| winner agreement, mean | {_mean(win_ag):.3f} |")
        L.append(f"| best candidate agreement, mean | {_mean(best_ag):.3f} |")
        L.append(f"| best *clean* candidate agreement, mean | {_mean(bc_ag):.3f} |")
        L.append(f"| best - winner gap, mean / p50 / p90 | {_mean(gaps):.3f} / {_p(gaps, 0.5):.3f} / {_p(gaps, 0.9):.3f} |")
        L.append(f"| winner is the best candidate | {sum(g < 1e-9 for g in gaps)} |")
        L.append(f"| judge missed by >= {GAP_MIN} | {len(missed)} |")
        L.append(f"| judge missed by >= 0.10 | {sum(g >= 0.10 for g in gaps)} |")
        L.append(f"| best candidate has a hard fail | {sum(bool(b['hard']) for _, _, b, _ in wb)} |")
        L.append(f"| winner has a hard fail | {sum(bool(w['hard']) for _, w, _, _ in wb)} |")
        L.append(f"| reference trips a judge hard fail | {sum(bool(r['reference']['hard']) for r in rs)} |")
        L.append(f"| reference judge total > winner total (clean refs) | "
                 f"{sum(r['reference']['total'] > w['total'] for r, w, _, _ in wb if not r['reference']['hard'])} |")
        L.append(f"| candidates per case, mean | {_mean([len(r['candidates']) for r in rs]):.1f} |")
        L.append(f"| runtime p50 / p95 (s) | {_p([r['seconds'] for r in rs], 0.5):.2f} / {_p([r['seconds'] for r in rs], 0.95):.2f} |")
        L.append("")

        # by format family
        L.append("### By target family\n")
        L.append("| family | n | winner | best | gap | missed | winner families (share) |")
        L.append("|---|---:|---:|---:|---:|---:|---|")
        fam: dict[str, list] = defaultdict(list)
        for r, w, b, bc in wb:
            fam[r["tgt_family"]].append((r, w, b))
        for f in ("tall", "square", "wide", "banner"):
            xs = fam.get(f, [])
            if not xs:
                continue
            cnt = defaultdict(int)
            for _, w, _ in xs:
                cnt[w["family"]] += 1
            share = ", ".join(f"{k} {v / len(xs):.0%}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]))
            L.append(f"| {f} | {len(xs)} | {_mean([w['agreement'] for _, w, _ in xs]):.3f} | "
                     f"{_mean([b['agreement'] for _, _, b in xs]):.3f} | "
                     f"{_mean([b['agreement'] - w['agreement'] for _, w, b in xs]):.3f} | "
                     f"{sum(b['agreement'] - w['agreement'] >= GAP_MIN for _, w, b in xs)} | {share} |")
        L.append("")

        # by format
        L.append("### By format\n")
        L.append("| format | n | winner | best | gap | missed |")
        L.append("|---|---:|---:|---:|---:|---:|")
        byf: dict[str, list] = defaultdict(list)
        for r, w, b, bc in wb:
            byf[r["format"]].append((w, b))
        for f, xs in sorted(byf.items(), key=lambda kv: -int(kv[0].split("x")[0]) * int(kv[0].split("x")[1])):
            L.append(f"| {f} | {len(xs)} | {_mean([w['agreement'] for w, _ in xs]):.3f} | {_mean([b['agreement'] for _, b in xs]):.3f} | "
                     f"{_mean([b['agreement'] - w['agreement'] for w, b in xs]):.3f} | "
                     f"{sum(b['agreement'] - w['agreement'] >= GAP_MIN for w, b in xs)} |")
        L.append("")

        # agreement by candidate family (every candidate, clean only)
        L.append("### Agreement by seed family (every clean candidate, not only winners)\n")
        L.append("| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |")
        L.append("|---|---:|---:|---:|---:|---:|")
        per: dict[str, list] = defaultdict(list)
        wins: dict[str, int] = defaultdict(int)
        bests: dict[str, int] = defaultdict(int)
        steals: dict[str, int] = defaultdict(int)
        for r, w, b, bc in wb:
            for c in r["candidates"]:
                if not c["hard"] and not c["fallback"]:
                    per[c["family"]].append(c["agreement"])
            wins[w["family"]] += 1
            bests[b["family"]] += 1
            if b["family"].split("+")[0] != w["family"].split("+")[0] and b["agreement"] - w["agreement"] >= GAP_MIN:
                steals[w["family"]] += 1
        for f in sorted(per, key=lambda k: -len(per[k])):
            L.append(f"| {f} | {len(per[f])} | {_mean(per[f]):.3f} | {wins[f]} | {bests[f]} | {steals[f]} |")
        L.append("")

        # transitions winner family -> best family
        L.append(f"### Missed cases (gap >= {GAP_MIN}): winner family -> best family\n")
        trans: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r, w, b in missed:
            trans[(w["family"], b["family"])].append(b["agreement"] - w["agreement"])
        L.append("| winner | best | n | mean gap |")
        L.append("|---|---|---:|---:|")
        for (a, b_), g in sorted(trans.items(), key=lambda kv: -len(kv[1])):
            L.append(f"| {a} | {b_} | {len(g)} | {_mean(g):.3f} |")
        L.append("")

        # blame: which terms carried the winner over the best
        L.append(f"### Blame: weight x (winner - best) per term, missed cases\n")
        L.append("Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the "
                 "target family and by the best candidate's family (the layout the judge should have taken).\n")
        terms = sorted({k for r, w, b in missed for k in blame(r, w, b)})

        def blame_table(groups: dict[str, list[tuple]], label: str) -> None:
            L.append(f"| term | all missed | " + " | ".join(f"{label} {g}" for g in groups) + " |")
            L.append("|---|---:|" + "---:|" * len(groups))
            allb = [blame(r, w, b) for r, w, b in missed]
            gb = {g: [blame(r, w, b) for r, w, b in xs] for g, xs in groups.items()}
            rows_ = []
            for t in terms:
                m_all = _mean([x.get(t, 0.0) for x in allb])
                rows_.append((t, m_all, [_mean([x.get(t, 0.0) for x in gb[g]]) for g in groups]))
            rows_.sort(key=lambda x: -abs(x[1]))
            for t, m_all, ms in rows_:
                L.append(f"| {t} | {m_all:+.2f} | " + " | ".join(f"{m:+.2f}" if m == m else "-" for m in ms) + " |")
            L.append("")

        if missed:
            byfam: dict[str, list] = defaultdict(list)
            for r, w, b in missed:
                byfam[r["tgt_family"]].append((r, w, b))
            blame_table({f: byfam[f] for f in ("tall", "square", "wide", "banner") if f in byfam}, "target")
            bybest: dict[str, list] = defaultdict(list)
            for r, w, b in missed:
                bybest[b["family"]].append((r, w, b))
            blame_table(dict(sorted(bybest.items(), key=lambda kv: -len(kv[1]))), "best =")
            # how often each term is the single largest vote for the winner
            L.append("| term | largest single vote for the winner (cases) |")
            L.append("|---|---:|")
            top = defaultdict(int)
            for r, w, b in missed:
                bl = blame(r, w, b)
                k = max(bl, key=lambda k: bl[k])
                top[k] += 1
            for k, v in sorted(top.items(), key=lambda kv: -kv[1]):
                L.append(f"| {k} | {v} |")
            L.append("")

        # agreement components: where the winner loses to the best
        L.append("### Where the winner loses agreement (components, missed cases)\n")
        L.append("| component | winner | best |")
        L.append("|---|---:|---:|")
        for comp in ("da_pos", "da_within10", "da_order_tau", "da_size_rho"):
            L.append(f"| {comp} | {_mean([w['da'].get(comp) for _, w, _ in missed]):.3f} | "
                     f"{_mean([b['da'].get(comp) for _, _, b in missed]):.3f} |")
        L.append("")

    block("Tuning set (designs not in the hold-out)", [r for r in rows if not r["holdout"]])
    block("HOLD-OUT (10 sealed designs)", [r for r in rows if r["holdout"]])
    L.append("## Largest misses (tuning set)\n")
    wb = [(r, *winner_and_best(r)) for r in rows if not r["holdout"]]
    wb.sort(key=lambda t: -(t[2]["agreement"] - t[1]["agreement"]))
    for r, w, b, _ in wb[:15]:
        bl = blame(r, w, b)
        top = sorted(bl.items(), key=lambda kv: -kv[1])[:3]
        L.append(f"- {r['name'][:12]} {r['format']}: winner `{w['name'][:34]}` {w['agreement']:.3f} -> best "
                 f"`{b['name'][:34]}` {b['agreement']:.3f} (rank {b['rank']}); for the winner: "
                 + ", ".join(f"{k} {v:+.1f}" for k, v in top))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--names", default="")
    ap.add_argument("--batch", default="", help="designer | designer2 (default both)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    dump = args.out / "candidates.jsonl"
    if args.report_only:
        rows = load_rows(dump)
    else:
        from eval.perturb_designer import BATCHES, references
        names = [n for n in args.names.split(",") if n] or None
        batch_names = [b.name for b in BATCHES if not args.batch or b.name == args.batch]
        refs = references([b for b in BATCHES if b.name in batch_names], set(names) if names else None)
        n = min(len(refs), args.limit) if args.limit else len(refs)
        rows = []
        t0 = time.time()
        with dump.open("w") as f, ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn")) as ex:
            futs = {ex.submit(run_case, i, batch_names, names): i for i in range(n)}
            for k, fut in enumerate(as_completed(futs)):
                try:
                    row = fut.result()
                except Exception as exc:
                    print(f"case {futs[fut]} failed: {exc!r}", flush=True)
                    continue
                rows.append(row)
                f.write(json.dumps(row) + "\n")
                if (k + 1) % 40 == 0:
                    print(f"{k + 1}/{n} in {time.time() - t0:.0f} s", flush=True)
        rows.sort(key=lambda r: (r["batch"], r["name"], r["format"]))
        with dump.open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    (args.out / "REPORT.md").write_text(report(rows))
    print("wrote", args.out / "REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
