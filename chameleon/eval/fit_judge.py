"""Fit the judge's soft weights to the designer references (v8).

Data: the candidate dump of eval/picker_gap.py (every judged candidate of
every reference case with its breakdown, hard fails, penalty and designer
agreement) plus the human A/B labels (eval/data/labels.jsonl, re-scored
under the current scorer from the stored designs). Pairs:

  designer pairs    the reference (scored by the same judge) beats every
                    non-fallback candidate of its case with the same number
                    of hard fails
  candidate pairs   two non-fallback candidates of one case with the same
                    number of hard fails whose designer agreement differs
                    by >= --margin (0.05): the closer one wins
  human pairs       a / b / tie decisions (both_bad skipped), weight 1 each

Every case's designer pairs sum to one unit of weight and its candidate
pairs to another, so a case with 20 candidates does not outvote one with 6.
Pairs from the sealed hold-out designs (docs/designer2/holdout_ids.json)
are never fitted.

Model: eval/calibrate.py's pairwise logistic regression (weights >= --floor
1 % of the sum, sum 100, hard fails and penalties pinned, free temperature,
L2 toward the hand weights). Reported: pair agreement (in sample, by kind,
leave-one-design-out, hold-out pairs) and, what matters, the *re-ranking*:
the judge's winner under hand vs fitted weights for every case (total =
sum W_k bd_k - 1000 |hard| - penalty, exactly the judge's rule), with
designer agreement, best-vs-chosen gap, hard fails and family shares, on
the tuning set (also leave-one-design-out) and on the hold-out.

    .venv/bin/python -m eval.fit_judge [--dump docs/designer/compare/v8_picker/candidates.jsonl]
                                       [--l2 0.5] [--floor 0.01] [--margin 0.05] [--install]

Writes eval/data/score_weights.v8.json (+ REPORT.md next to the dump) and,
with --install, engine/score_weights.json (engine/score.py loads it at import).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHAMELEON_NO_RENDER", "1")

from eval import calibrate as C  # noqa: E402
from eval.labeling import LABELS_FILE, read_labels  # noqa: E402
from eval.picker_gap import OUT_DIR, load_rows  # noqa: E402

DUMP = OUT_DIR / "candidates.jsonl"
FIT_OUT = ROOT / "eval" / "data" / "score_weights.v8.json"
INSTALL = ROOT / "engine" / "score_weights.json"
DEFAULT_MARGIN = 0.05
DEFAULT_FLOOR = 0.01
DEFAULT_L2 = 0.5
HARD = 1000.0


def hand_weights() -> dict[str, float]:
    from engine.score import HAND_WEIGHTS

    return dict(HAND_WEIGHTS)


# ---------------------------------------------------------------------------
# pairs


def _side(c: dict[str, Any]) -> dict[str, Any]:
    return {"breakdown": c["breakdown"], "hard": c["hard"], "penalty": c["penalty"]}


def pairs_from_dump(rows: list[dict[str, Any]], components: list[str], *, margin: float = DEFAULT_MARGIN,
                    designer_weight: float = 1.0, candidate_weight: float = 1.0) -> list[dict[str, Any]]:
    """Label-like records (a, b, decision, kind, design_id, holdout) from the
    candidate dump."""
    out: list[dict[str, Any]] = []
    for r in rows:
        cands = [c for c in r["candidates"] if not c["fallback"]]
        ref = r["reference"]
        dp = [c for c in cands if len(c["hard"]) == len(ref["hard"])]
        for c in dp:
            out.append({"a": _side(ref), "b": _side(c), "decision": "a", "kind": "designer", "design_id": r["name"],
                        "holdout": r["holdout"], "weight": designer_weight / len(dp), "case": f"{r['name']}|{r['format']}"})
        cp = []
        for i, a in enumerate(cands):
            for b in cands[i + 1:]:
                if len(a["hard"]) != len(b["hard"]):
                    continue
                d = a["agreement"] - b["agreement"]
                if abs(d) < margin:
                    continue
                cp.append((a, b, "a" if d > 0 else "b"))
        for a, b, dec in cp:
            out.append({"a": _side(a), "b": _side(b), "decision": dec, "kind": "candidate", "design_id": r["name"],
                        "holdout": r["holdout"], "weight": candidate_weight / len(cp), "case": f"{r['name']}|{r['format']}"})
    return out


def rescored_human_pairs(path: Path = LABELS_FILE, log=None) -> list[dict[str, Any]]:
    """The human labels with both sides re-scored by the current judge (the
    stored breakdowns predate the v8 terms)."""
    from engine.analyze import analyze
    from engine.geometry import Box
    from engine.score import score_design

    out = []
    sources: dict[str, Any] = {}
    dropped = 0
    for r in read_labels(path):
        if r.get("decision") not in ("a", "b", "tie"):
            continue
        key = str(r.get("design_file") or "")
        if key not in sources:
            src = C._source_for(r)
            sources[key] = (src, analyze(src)) if src is not None else None
        if sources[key] is None:
            dropped += 1
            continue
        src, an = sources[key]
        t = r["target"]
        target = Box(0.0, 0.0, float(t["width"]), float(t["height"]))
        sides = {}
        try:
            for s in ("a", "b"):
                sc = score_design(an, src, r[s]["design"], target, render=False, strategy=r[s].get("strategy"))
                sides[s] = {"breakdown": sc.breakdown, "hard": sc.hard, "penalty": sc.penalty}
        except Exception as exc:
            dropped += 1
            if log:
                log(f"skip {r.get('case_key')}: {exc!r}")
            continue
        out.append({"a": sides["a"], "b": sides["b"], "decision": r["decision"], "kind": "human",
                    "design_id": str(r.get("design_id")), "holdout": False, "weight": 1.0, "case": r.get("case_key")})
    if log and dropped:
        log(f"{dropped} human labels dropped (no source / design)")
    return out


def build(records: list[dict[str, Any]], components: list[str]) -> C.Pairs:
    X, pinned, y, w, design, kind = [], [], [], [], [], []
    for r in records:
        a, b = r["a"], r["b"]
        X.append([float(a["breakdown"].get(k, 0.0)) - float(b["breakdown"].get(k, 0.0)) for k in components])
        pinned.append(-HARD * (len(a["hard"]) - len(b["hard"])) - (float(a["penalty"]) - float(b["penalty"])))
        y.append({"a": 1.0, "b": 0.0, "tie": 0.5}[r["decision"]])
        w.append(float(r["weight"]))
        design.append(r["design_id"])
        kind.append(r["kind"])
    n = len(y)
    return C.Pairs(components, np.array(X, dtype=float).reshape(n, len(components)), np.array(pinned, dtype=float),
                   np.array(y, dtype=float), np.array(w, dtype=float), design, kind)


# ---------------------------------------------------------------------------
# re-ranking (what the judge would return under other weights)


def total_under(c: dict[str, Any], weights: dict[str, float]) -> float:
    return (sum(weights.get(k, 0.0) * min(1.0, max(0.0, float(v))) for k, v in c["breakdown"].items())
            - HARD * len(c["hard"]) - float(c["penalty"]))


def rerank(row: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    cands = row["candidates"]
    return max(cands, key=lambda c: (total_under(c, weights), -c["rank"]))


def rerank_stats(rows: list[dict[str, Any]], pick) -> dict[str, Any]:
    if not rows:
        return {}
    ws = [pick(r) for r in rows]
    best = [max(r["candidates"], key=lambda c: c["agreement"])["agreement"] for r in rows]
    best_real = [max([c for c in r["candidates"] if not c["fallback"] and not c["hard"]] or r["candidates"],
                     key=lambda c: c["agreement"])["agreement"] for r in rows]
    fam = defaultdict(int)
    for w in ws:
        fam[w["family"]] += 1
    return {"n": len(rows), "agreement": round(statistics.fmean(w["agreement"] for w in ws), 4),
            "gap_to_best": round(statistics.fmean(b - w["agreement"] for b, w in zip(best, ws)), 4),
            "gap_to_best_clean": round(statistics.fmean(b - w["agreement"] for b, w in zip(best_real, ws)), 4),
            "winner_is_best": sum(w["agreement"] >= b - 1e-9 for b, w in zip(best, ws)),
            "ge_0.7": sum(w["agreement"] >= 0.7 for w in ws),
            "hard": sum(bool(w["hard"]) for w in ws), "fallback": sum(bool(w["fallback"]) for w in ws),
            "order_tau": round(statistics.fmean(w["da"].get("da_order_tau") or 0.0 for w in ws), 4),
            "pos_err": round(statistics.fmean(w["da"].get("da_pos_err") or 0.0 for w in ws), 4),
            "judge_total": round(statistics.fmean(w["total"] for w in ws), 2),
            "families": dict(sorted(fam.items()))}


def leave_one_design_out(P: C.Pairs, *, floor: float, l2: float, prior: dict[str, float], max_folds: int,
                         min_pairs: int, freeze: list[str]) -> dict[str, Any]:
    """calibrate.leave_one_design_out with the v8 freeze list (pair agreement)."""
    designs = sorted(set(P.design))
    rng = np.random.default_rng(0)
    order = list(rng.permutation(designs))
    folds = [set(order[i::max_folds]) for i in range(min(max_folds, len(order)))]
    hits = wsum = 0.0
    n = 0
    arr = np.array(P.design)
    for held in folds:
        test = np.isin(arr, list(held)) & P.decisive
        if not test.any():
            continue
        f = C.fit_weights(P.subset(~np.isin(arr, list(held))), floor=floor, l2=l2, prior=prior, min_pairs=min_pairs,
                          freeze=freeze)
        m = C.margins(P.subset(test), f.weights)
        pred = np.where(m > 1e-9, 1.0, np.where(m < -1e-9, 0.0, 0.5))
        hit = np.where(pred == 0.5, 0.5, (pred == P.y[test]).astype(float))
        hits += float((hit * P.w[test]).sum())
        wsum += float(P.w[test].sum())
        n += int(test.sum())
    return {"n": n, "agree": round(hits / wsum, 4) if wsum else None, "folds": len(folds)}


def lodo_rerank(rows: list[dict[str, Any]], records: list[dict[str, Any]], components: list[str], *,
                floor: float, l2: float, prior: dict[str, float], min_pairs: int, max_folds: int = 25,
                freeze: list[str] = ()) -> dict[str, Any]:
    """Leave-one-design-out on the *re-ranking*: fit on the other designs'
    pairs, pick the held design's winners with those weights."""
    designs = sorted({r["name"] for r in rows})
    rng = np.random.default_rng(0)
    order = list(rng.permutation(designs))
    folds = [set(order[i::max_folds]) for i in range(min(max_folds, len(order)))]
    picked: dict[str, dict[str, Any]] = {}
    for held in folds:
        train = [r for r in records if r["design_id"] not in held]
        fit = C.fit_weights(build(train, components), floor=floor, l2=l2, prior=prior, min_pairs=min_pairs, freeze=freeze)
        for r in rows:
            if r["name"] in held:
                picked[f"{r['name']}|{r['format']}"] = rerank(r, fit.weights)
    return rerank_stats(rows, lambda r: picked[f"{r['name']}|{r['format']}"])


# ---------------------------------------------------------------------------


def _fmt_stats(label: str, s: dict[str, Any]) -> str:
    if not s:
        return f"| {label} | - |"
    return (f"| {label} | {s['n']} | {s['agreement']:.3f} | {s['gap_to_best']:.3f} | {s['gap_to_best_clean']:.3f} | "
            f"{s['winner_is_best']} | {s['ge_0.7']} | {s['hard']} | {s['fallback']} | {s['order_tau']:.3f} | {s['judge_total']:.1f} | "
            + ", ".join(f"{k} {v}" for k, v in s["families"].items()) + " |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", type=Path, default=DUMP)
    ap.add_argument("--labels", type=Path, default=LABELS_FILE)
    ap.add_argument("--no-human", action="store_true")
    ap.add_argument("--no-designer", action="store_true", help="drop the reference > candidate pairs")
    ap.add_argument("--no-candidates", action="store_true", help="drop the candidate vs candidate pairs")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR)
    ap.add_argument("--l2", type=float, default=DEFAULT_L2)
    ap.add_argument("--min-pairs", type=int, default=C.DEFAULT_MIN_PAIRS)
    ap.add_argument("--freeze", default="", help="comma-separated components kept at their hand weight "
                    "(e.g. read.size,read.lines,read.contrast,read.presence: legibility, which the references cannot teach)")
    ap.add_argument("--designer-weight", type=float, default=1.0)
    ap.add_argument("--candidate-weight", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=FIT_OUT)
    ap.add_argument("--install", action="store_true", help="also write engine/score_weights.json")
    ap.add_argument("--no-lodo", action="store_true")
    args = ap.parse_args(argv)

    hand = hand_weights()
    components = list(hand)
    rows = load_rows(args.dump)
    tune = [r for r in rows if not r["holdout"]]
    hold = [r for r in rows if r["holdout"]]
    records = pairs_from_dump(rows, components, margin=args.margin, designer_weight=args.designer_weight,
                              candidate_weight=args.candidate_weight)
    if args.no_designer:
        records = [r for r in records if r["kind"] != "designer"]
    if args.no_candidates:
        records = [r for r in records if r["kind"] != "candidate"]
    human = [] if args.no_human else rescored_human_pairs(args.labels, log=lambda s: print(s, flush=True))
    train_recs = [r for r in records if not r["holdout"]] + human
    held_recs = [r for r in records if r["holdout"]]
    P = build(train_recs, components)
    H = build(held_recs, components) if held_recs else None
    t0 = time.time()
    freeze = [c for c in args.freeze.split(",") if c]
    fit = C.fit_weights(P, floor=args.floor, l2=args.l2, prior=hand, min_pairs=args.min_pairs, freeze=freeze)
    lodo = {} if args.no_lodo else leave_one_design_out(P, floor=args.floor, l2=args.l2, prior=hand, max_folds=25,
                                                        min_pairs=args.min_pairs, freeze=freeze)
    comp = C.component_agreement(P)
    by_kind_hand, by_kind_fit = C._by_kind(P, hand), C._by_kind(P, fit.weights)

    # re-ranking
    rr = {
        "tuning hand": rerank_stats(tune, lambda r: r["candidates"][0]),
        "tuning hand (re-ranked)": rerank_stats(tune, lambda r: rerank(r, hand)),
        "tuning fitted": rerank_stats(tune, lambda r: rerank(r, fit.weights)),
        "HOLD-OUT hand": rerank_stats(hold, lambda r: r["candidates"][0]),
        "HOLD-OUT fitted": rerank_stats(hold, lambda r: rerank(r, fit.weights)),
    }
    if not args.no_lodo:
        rr["tuning fitted (leave-one-design-out)"] = lodo_rerank(tune, train_recs, components, floor=args.floor, l2=args.l2,
                                                                 prior=hand, min_pairs=args.min_pairs, freeze=freeze)
    # by target family (fitted vs hand), hold-out and tuning
    fam_rows = []
    for label, rs in (("tuning", tune), ("HOLD-OUT", hold)):
        byf: dict[str, list] = defaultdict(list)
        for r in rs:
            byf[r["tgt_family"]].append(r)
        for f in ("tall", "square", "wide", "banner"):
            if byf.get(f):
                h = rerank_stats(byf[f], lambda r: r["candidates"][0])
                g = rerank_stats(byf[f], lambda r: rerank(r, fit.weights))
                fam_rows.append(f"| {label} {f} | {h['n']} | {h['agreement']:.3f} | {g['agreement']:.3f} | {h['gap_to_best']:.3f} | "
                                f"{g['gap_to_best']:.3f} | {h['hard']} | {g['hard']} |")

    L = ["# Judge weight fit on the designer references (v8)", "",
         f"dump: {args.dump} ({len(rows)} cases, {len(hold)} hold-out); pairs fitted: {len(P)} "
         f"({', '.join(f'{v} {k}' for k, v in sorted({k: sum(1 for x in P.kind if x == k) for k in set(P.kind)}.items()))}); "
         f"hold-out pairs (never fitted): {len(H) if H is not None else 0}; margin {args.margin}, floor {args.floor:.0%}, "
         f"l2 {args.l2}, min pairs {args.min_pairs}; fit {time.time() - t0:.1f} s", ""]
    a_hand, a_fit = C.agreement(P, hand), C.agreement(P, fit.weights)
    L.append(f"pair agreement (decisive, weighted): hand {a_hand['agree_weighted']}, fitted {a_fit['agree_weighted']} in sample, "
             f"leave-one-design-out {lodo.get('agree')}")
    for k in by_kind_hand:
        L.append(f"  {k}: n={by_kind_hand[k]['n']} hand {by_kind_hand[k]['agree_weighted']} fitted {by_kind_fit[k]['agree_weighted']}")
    if H is not None and len(H):
        hh, hf = C.agreement(H, hand), C.agreement(H, fit.weights)
        L.append(f"  HOLD-OUT pairs: n={hh['n']} hand {hh['agree_weighted']} fitted {hf['agree_weighted']}")
    L.append(f"temperature {fit.temperature:.4f}, loss {fit.loss:.4f}; frozen: {', '.join(fit.frozen) or 'none'}")
    L += ["", "| component | hand | fitted | change | pairs where it differs | agrees with label |", "|---|---|---|---|---|---|"]
    for c in components:
        ca = comp[c]
        agree = "-" if ca["agree"] is None else f"{ca['agree']:.2f}"
        L.append(f"| {c} | {hand[c]:.1f} | {fit.weights[c]:.1f} | {fit.weights[c] - hand[c]:+.1f} | {ca['n']} | {agree} |")
    L += ["", "## Re-ranking: the judge's winner under each weight set", "",
          "| set | n | agreement | gap to best | gap to best clean non-fallback | winner is best | >= 0.7 | hard | fallback wins | order tau | judge total | winner families |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for k, v in rr.items():
        L.append(_fmt_stats(k, v))
    L += ["", "| set | n | agreement hand | agreement fitted | gap hand | gap fitted | hard hand | hard fitted |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    L += fam_rows
    text = "\n".join(L) + "\n"
    print(text)
    result = {"weights": fit.weights, "temperature": round(fit.temperature, 6),
              "meta": {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "judge-v8", "dump": str(args.dump),
                       "n_pairs": len(P), "n_holdout_pairs": len(H) if H is not None else 0, "margin": args.margin,
                       "floor": args.floor, "l2": args.l2, "min_pairs": args.min_pairs, "frozen": fit.frozen,
                       "freeze": freeze,
                       "pair_agreement_hand": a_hand, "pair_agreement_fitted": a_fit, "pair_agreement_lodo": lodo,
                       "rerank": rr, "components": comp, "hand_weights": hand}}
    payload = json.dumps(result, indent=1) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    (args.dump.parent / "FIT.md").write_text(text)
    print("wrote", args.out, "and", args.dump.parent / "FIT.md")
    if args.install:
        INSTALL.write_text(payload)
        print("installed", INSTALL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
