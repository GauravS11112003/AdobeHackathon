"""Calibrate the scorer's component weights on pairwise labels.

    .venv/bin/python -m eval.calibrate                      # fit, report, write engine/score_weights.json
    .venv/bin/python -m eval.calibrate --dry-run            # fit and report only
    .venv/bin/python -m eval.calibrate --weak-weight 0.3 --floor 0.05 --l2 0.5

Model. The scorer's total is  T = sum_k W_k * bd_k - 1000 * |hard| - penalty
(engine/score.py), so for a labelled pair (A, B) the scorer's preference is
T_A - T_B = W . (bd_A - bd_B) - 1000 * d_hard - d_penalty. We fit

    P(A better) = sigmoid( s * ( W . d_bd - 1000 * d_hard - d_penalty ) )

by weighted logistic regression: W >= 0 with every weight floored at
`--floor` (5 %) of the sum, the sum fixed at 100 like the hand weights, the
hard-fail and adaptation-penalty terms pinned (not fitted), and one free
temperature s. Decisions: "a" -> y = 1, "b" -> y = 0, "tie" -> y = 0.5 (a
soft target), "both_bad" -> skipped (says nothing about the pair's order).
Weak labels (eval/data/labels_weak.jsonl, perturbation bootstrap) enter with
`--weak-weight` (0.3) per pair, human labels with 1.0. A small L2 pull
toward the hand weights (`--l2`) keeps the fit stable with few labels, and a
component that differs in fewer than `--min-pairs` decisive pairs is frozen
at its hand weight (no evidence, no change: the fit redistributes only among
components the labels actually speak about).

Reported: agreement of the hand weights and of the fitted weights with the
decisive labels (in sample), leave-one-design-out agreement of the fitted
weights (every design's pairs held out in turn), and per component how often
the component's own difference alone agrees with the label.

Output: engine/score_weights.json {"weights": {...}, "temperature": s,
"meta": {...}}; engine/score.py loads it at import when present.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.labeling import LABELS_FILE, WEAK_LABELS_FILE, read_labels  # noqa: E402

HARD_PENALTY = 1000.0
TOTAL = 100.0
DEFAULT_FLOOR = 0.05
DEFAULT_WEAK_WEIGHT = 0.3
DEFAULT_L2 = 0.5
DEFAULT_MIN_PAIRS = 5        # a component needs this many decisive pairs where it differs to be fitted
WEIGHTS_OUT = ROOT / "engine" / "score_weights.json"


def hand_weights() -> dict[str, float]:
    from engine.score import HAND_WEIGHTS

    return dict(HAND_WEIGHTS)


# ---------------------------------------------------------------------------
# pairs


@dataclass
class Pairs:
    """Labelled pairs as arrays: X[i] = bd_A - bd_B over `components`."""

    components: list[str]
    X: np.ndarray                   # (n, k) breakdown differences
    pinned: np.ndarray              # (n,) -1000 * d_hard - d_penalty
    y: np.ndarray                   # (n,) 1 / 0 / 0.5
    w: np.ndarray                   # (n,) example weights
    design: list[str]               # (n,) design id per pair
    kind: list[str]                 # (n,) "human" / "weak"
    skipped: dict[str, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.y)

    def subset(self, mask: np.ndarray) -> "Pairs":
        idx = np.flatnonzero(mask)
        return Pairs(self.components, self.X[idx], self.pinned[idx], self.y[idx], self.w[idx],
                     [self.design[i] for i in idx], [self.kind[i] for i in idx])

    @property
    def decisive(self) -> np.ndarray:
        return self.y != 0.5


def build_pairs(records: Iterable[dict[str, Any]], components: list[str], *,
                weak_weight: float = DEFAULT_WEAK_WEIGHT) -> Pairs:
    X, pinned, y, w, design, kind = [], [], [], [], [], []
    skipped: dict[str, int] = {}
    for r in records:
        d = r.get("decision")
        if d not in ("a", "b", "tie"):
            skipped[str(d)] = skipped.get(str(d), 0) + 1
            continue
        a, b = r.get("a") or {}, r.get("b") or {}
        ba, bb = a.get("breakdown") or {}, b.get("breakdown") or {}
        if any((k in ba) != (k in bb) for k in components):
            skipped["one-sided breakdown"] = skipped.get("one-sided breakdown", 0) + 1
            continue
        if any(k not in ba for k in components):
            # a label from an older scorer (a harness run before a component
            # existed): the missing component counts as "no difference"
            skipped["older breakdown (missing components = 0)"] = skipped.get("older breakdown (missing components = 0)", 0) + 1
        X.append([float(ba.get(k, 0.0)) - float(bb.get(k, 0.0)) for k in components])
        d_hard = len(a.get("hard") or []) - len(b.get("hard") or [])
        d_pen = float(a.get("penalty") or 0.0) - float(b.get("penalty") or 0.0)
        pinned.append(-HARD_PENALTY * d_hard - d_pen)
        y.append({"a": 1.0, "b": 0.0, "tie": 0.5}[d])
        k = r.get("kind", "human")
        w.append(weak_weight if k == "weak" else 1.0)
        design.append(str(r.get("design_id", "")))
        kind.append(str(k))
    n = len(y)
    return Pairs(components, np.array(X, dtype=float).reshape(n, len(components)),
                 np.array(pinned, dtype=float), np.array(y, dtype=float), np.array(w, dtype=float),
                 design, kind, skipped)


# ---------------------------------------------------------------------------
# fitting


@dataclass
class Fit:
    weights: dict[str, float]
    temperature: float
    loss: float
    n: int
    floor: float
    frozen: list[str] = field(default_factory=list)   # components kept at their hand weight (no evidence)


def _unpack(theta: np.ndarray, k: int, floor_abs: float, budget: float
            ) -> tuple[np.ndarray, float, np.ndarray]:
    """theta -> (free weights, temperature, softmax). The free weights share
    `budget` (the sum left after the frozen ones), each >= floor_abs."""
    z, log_s = theta[:k], theta[k]
    z = z - z.max()
    sm = np.exp(z)
    sm /= sm.sum()
    return floor_abs + (budget - k * floor_abs) * sm, math.exp(log_s), sm


def _loss_grad(theta: np.ndarray, P: Pairs, floor_abs: float, l2: float, prior: np.ndarray,
               free: np.ndarray | None = None, frozen_w: np.ndarray | None = None
               ) -> tuple[float, np.ndarray]:
    """Weighted logistic loss + L2 and its gradient in theta. `free` marks
    the fitted components (default all); `frozen_w` holds the others' fixed
    weights (zeros for the free ones)."""
    K = len(P.components)
    free = np.ones(K, dtype=bool) if free is None else free
    frozen_w = np.zeros(K) if frozen_w is None else frozen_w
    k = int(free.sum())
    budget = TOTAL - float(frozen_w.sum())
    wf, s, sm = _unpack(theta, k, floor_abs, budget)
    w = frozen_w.copy()
    w[free] = wf
    margin = P.X @ w + P.pinned                         # T_A - T_B
    logit = s * margin
    log_p = -np.logaddexp(0.0, -logit)                  # stable log-sigmoid
    log_q = -np.logaddexp(0.0, logit)
    wsum = P.w.sum() if len(P) else 1.0
    nll = -(P.w * (P.y * log_p + (1.0 - P.y) * log_q)).sum() / wsum
    reg = l2 * float((((w - prior) / TOTAL) ** 2).sum())
    loss = nll + reg
    p = np.exp(log_p)
    dl_dlogit = P.w * (p - P.y) / wsum                  # (n,)
    dl_dw = s * (P.X * dl_dlogit[:, None]).sum(axis=0) + 2.0 * l2 * (w - prior) / TOTAL ** 2
    dl_ds = float((dl_dlogit * margin).sum())
    g = dl_dw[free]
    span = budget - k * floor_abs
    # w_free = floor + span * softmax(z): dw_i/dz_j = span * sm_i (delta_ij - sm_j)
    dl_dz = span * (sm * g - sm * float((sm * g).sum()))
    return float(loss), np.concatenate([dl_dz, [dl_ds * s]])


def fit_weights(P: Pairs, *, floor: float = DEFAULT_FLOOR, l2: float = DEFAULT_L2,
                prior: dict[str, float] | None = None, min_pairs: int = DEFAULT_MIN_PAIRS,
                iters: int = 400, freeze: Iterable[str] = ()) -> Fit:
    """Non-negative weights (sum 100, each >= floor * 100) and a temperature
    by L-BFGS on the weighted logistic loss, starting at the hand weights.
    Components that differ in fewer than `min_pairs` decisive pairs, and the
    ones named in `freeze` (v8: terms the labels cannot speak about), are
    frozen at their (normalised) hand weight."""
    from scipy.optimize import minimize

    K = len(P.components)
    floor_abs = floor * TOTAL
    if K * floor_abs >= TOTAL:
        raise ValueError("floor too high: k * floor >= 1")
    prior_w = np.array([(prior or hand_weights())[c] for c in P.components], dtype=float)
    prior_w = prior_w * TOTAL / prior_w.sum()
    evidence = ((np.abs(P.X) > 1e-9) & P.decisive[:, None]).sum(axis=0) if len(P) else np.zeros(K, dtype=int)
    free = evidence >= max(1, min_pairs)
    freeze = set(freeze)
    free = np.array([f and c not in freeze for c, f in zip(P.components, free)], dtype=bool)
    frozen = [c for c, f in zip(P.components, free) if not f]
    if not free.any():
        return Fit({c: round(float(v), 4) for c, v in zip(P.components, prior_w)}, 0.3, float("nan"), len(P),
                   floor, frozen)
    frozen_w = np.where(free, 0.0, np.maximum(prior_w, floor_abs))
    k = int(free.sum())
    budget = TOTAL - float(frozen_w.sum())
    span = budget - k * floor_abs
    if span <= 0:
        raise ValueError("floor too high for the frozen weights")
    # start where w_free == the prior (projected onto the floor / budget)
    start = np.clip(prior_w[free], floor_abs, None)
    z0 = np.log(np.clip((start - floor_abs) / span, 1e-6, None))
    theta0 = np.concatenate([z0 - z0.mean(), [math.log(0.3)]])
    res = minimize(_loss_grad, theta0, args=(P, floor_abs, l2, prior_w, free, frozen_w), jac=True,
                   method="L-BFGS-B", bounds=[(-12, 12)] * k + [(math.log(1e-3), math.log(50.0))],
                   options={"maxiter": iters})
    wf, s, _ = _unpack(res.x, k, floor_abs, budget)
    w = frozen_w.copy()
    w[free] = wf
    return Fit({c: round(float(v), 4) for c, v in zip(P.components, w)}, float(s), float(res.fun), len(P),
               floor, frozen)


# ---------------------------------------------------------------------------
# agreement


def margins(P: Pairs, weights: dict[str, float]) -> np.ndarray:
    w = np.array([weights[c] for c in P.components], dtype=float)
    return P.X @ w + P.pinned


def agreement(P: Pairs, weights: dict[str, float], tol: float = 1e-9) -> dict[str, Any]:
    """Share of decisive labels (a / b) that the weights order the same way;
    a predicted tie counts half. Weighted by the example weights too."""
    m = margins(P, weights)
    dec = P.decisive
    if not dec.any():
        return {"n": 0, "agree": None, "agree_weighted": None}
    pred = np.where(m > tol, 1.0, np.where(m < -tol, 0.0, 0.5))
    hit = np.where(pred[dec] == 0.5, 0.5, (pred[dec] == P.y[dec]).astype(float))
    return {"n": int(dec.sum()), "agree": round(float(hit.mean()), 4),
            "agree_weighted": round(float((hit * P.w[dec]).sum() / P.w[dec].sum()), 4)}


def component_agreement(P: Pairs) -> dict[str, dict[str, Any]]:
    """Per component: among decisive pairs where the component differs, how
    often the side with the higher component value is the labelled winner."""
    out = {}
    dec = P.decisive
    sign_y = np.where(P.y > 0.5, 1.0, -1.0)
    for i, c in enumerate(P.components):
        d = P.X[:, i]
        m = dec & (np.abs(d) > 1e-9)
        n = int(m.sum())
        out[c] = {"n": n, "agree": round(float((np.sign(d[m]) == sign_y[m]).mean()), 4) if n else None,
                  "differs_share": round(float(np.mean(np.abs(d[dec]) > 1e-9)), 4) if dec.any() else None}
    return out


def leave_one_design_out(P: Pairs, *, floor: float = DEFAULT_FLOOR, l2: float = DEFAULT_L2,
                         prior: dict[str, float] | None = None, max_folds: int | None = None,
                         min_pairs: int = DEFAULT_MIN_PAIRS) -> dict[str, Any]:
    """Fit on every design but one, score the held-out design's decisive
    pairs; returns the pooled agreement. `max_folds` groups designs into at
    most that many folds (random, seeded) when there are very many."""
    designs = sorted(set(P.design))
    if len(designs) < 2:
        return {"n": 0, "agree": None, "folds": 0}
    folds: list[set[str]]
    if max_folds and len(designs) > max_folds:
        rng = np.random.default_rng(0)
        order = list(rng.permutation(designs))
        folds = [set(order[i::max_folds]) for i in range(max_folds)]
    else:
        folds = [{d} for d in designs]
    hits, weights_sum, n = 0.0, 0.0, 0
    design_arr = np.array(P.design)
    prior = prior or hand_weights()
    for held in folds:
        test = np.isin(design_arr, list(held)) & P.decisive
        if not test.any():
            continue
        train = ~np.isin(design_arr, list(held))
        f = fit_weights(P.subset(train), floor=floor, l2=l2, prior=prior, min_pairs=min_pairs)
        m = margins(P.subset(test), f.weights)
        yt = P.y[test]
        pred = np.where(m > 1e-9, 1.0, np.where(m < -1e-9, 0.0, 0.5))
        hit = np.where(pred == 0.5, 0.5, (pred == yt).astype(float))
        hits += float((hit * P.w[test]).sum())
        weights_sum += float(P.w[test].sum())
        n += int(test.sum())
    return {"n": n, "agree": round(hits / weights_sum, 4) if weights_sum else None, "folds": len(folds)}


# ---------------------------------------------------------------------------
# report


def report(P: Pairs, hand: dict[str, float], fit: Fit, lodo: dict[str, Any], comp: dict[str, dict[str, Any]],
           *, human_only: Pairs | None = None) -> str:
    lines = []
    n_h = sum(1 for k in P.kind if k == "human")
    n_w = len(P) - n_h
    lines.append(f"pairs used: {len(P)} ({n_h} human, {n_w} weak); skipped: {P.skipped or 'none'}")
    a_hand, a_fit = agreement(P, hand), agreement(P, fit.weights)
    lines.append(f"agreement with decisive labels (n={a_hand['n']}): hand weights {a_hand['agree']}, "
                 f"fitted {a_fit['agree']} (in sample), fitted leave-one-design-out {lodo['agree']} "
                 f"over {lodo['folds']} folds")
    if human_only is not None and len(human_only):
        ah, af = agreement(human_only, hand), agreement(human_only, fit.weights)
        lines.append(f"human labels only (n={ah['n']} decisive): hand {ah['agree']}, fitted {af['agree']}")
    lines.append(f"temperature {fit.temperature:.4f}, loss {fit.loss:.4f}, floor {fit.floor:.0%} of the sum; "
                 f"frozen at the hand weight (no evidence): {', '.join(fit.frozen) or 'none'}")
    lines.append("")
    lines.append("| component | hand | fitted | change | pairs where it differs | agrees with label |")
    lines.append("|---|---|---|---|---|---|")
    for c in P.components:
        ca = comp[c]
        agree = "-" if ca["agree"] is None else f"{ca['agree']:.2f}"
        lines.append(f"| {c} | {hand[c]:.1f} | {fit.weights[c]:.1f} | {fit.weights[c] - hand[c]:+.1f} | "
                     f"{ca['n']} | {agree} |")
    return "\n".join(lines)


def calibrate(labels: Path = LABELS_FILE, weak: Path | None = WEAK_LABELS_FILE, *,
              weak_weight: float = DEFAULT_WEAK_WEIGHT, floor: float = DEFAULT_FLOOR, l2: float = DEFAULT_L2,
              out: Path | None = WEIGHTS_OUT, max_folds: int | None = 60,
              min_pairs: int = DEFAULT_MIN_PAIRS) -> dict[str, Any]:
    hand = hand_weights()
    components = list(hand)
    records = [dict(r, kind=r.get("kind", "human")) for r in read_labels(labels)]
    if weak is not None:
        records += [dict(r, kind="weak") for r in read_labels(weak)]
    P = build_pairs(records, components, weak_weight=weak_weight)
    human = P.subset(np.array([k == "human" for k in P.kind], dtype=bool)) if len(P) else None
    fit = fit_weights(P, floor=floor, l2=l2, prior=hand, min_pairs=min_pairs)
    lodo = leave_one_design_out(P, floor=floor, l2=l2, prior=hand, max_folds=max_folds, min_pairs=min_pairs)
    comp = component_agreement(P)
    text = report(P, hand, fit, lodo, comp, human_only=human)
    result = {
        "weights": fit.weights, "temperature": round(fit.temperature, 6),
        "meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "labels_file": str(labels),
            "weak_file": str(weak) if weak else None, "n_pairs": len(P),
            "n_human": sum(1 for k in P.kind if k == "human"), "n_weak": sum(1 for k in P.kind if k == "weak"),
            "weak_weight": weak_weight, "floor": floor, "l2": l2, "min_pairs": min_pairs, "loss": fit.loss,
            "frozen": fit.frozen,
            "agreement_hand": agreement(P, hand), "agreement_fitted": agreement(P, fit.weights),
            "agreement_lodo": lodo, "components": comp, "hand_weights": hand,
            "agreement_human_hand": agreement(human, hand) if human is not None and len(human) else None,
            "agreement_human_fitted": agreement(human, fit.weights) if human is not None and len(human) else None,
        },
        "report": text,
    }
    if out is not None and len(P):
        Path(out).write_text(json.dumps({k: v for k, v in result.items() if k != "report"}, indent=1) + "\n")
        result["written"] = str(out)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels", type=Path, default=LABELS_FILE)
    ap.add_argument("--weak", type=Path, default=WEAK_LABELS_FILE)
    ap.add_argument("--no-weak", action="store_true", help="ignore the weak labels")
    ap.add_argument("--weak-weight", type=float, default=DEFAULT_WEAK_WEIGHT)
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR, help="min weight as a share of the sum")
    ap.add_argument("--l2", type=float, default=DEFAULT_L2, help="pull toward the hand weights")
    ap.add_argument("--out", type=Path, default=WEIGHTS_OUT)
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--max-folds", type=int, default=60, help="cap on leave-one-design-out folds (0 = none)")
    ap.add_argument("--min-pairs", type=int, default=DEFAULT_MIN_PAIRS,
                    help="decisive pairs a component must differ in to be fitted (else frozen at the hand weight)")
    args = ap.parse_args(argv)
    res = calibrate(args.labels, None if args.no_weak else args.weak, weak_weight=args.weak_weight,
                    floor=args.floor, l2=args.l2, out=None if args.dry_run else args.out,
                    max_folds=args.max_folds or None, min_pairs=args.min_pairs)
    print(res["report"])
    if res.get("written"):
        print(f"\nwrote {res['written']}")
    elif not res["meta"]["n_pairs"]:
        print("\nno labelled pairs: nothing written")
    return 0



# ---------------------------------------------------------------------------
# v7: the design energy (engine/energy.py)
#
#   .venv/bin/python -m eval.calibrate --energy                 # fit, report, write eval/data/energy_weights.json
#   .venv/bin/python -m eval.calibrate --energy --install       # ... and engine/energy_weights.json (the engine loads it)
#
# The energy is a cost (lower is better): E = sum_k V_k * t_k + 1000 * |hard|.
# For a labelled pair (A, B) the energy prefers A when E_A < E_B, so the same
# logistic model fits with X = -(t_A - t_B) and pinned = -1000 * d_hard. The
# term vectors are recomputed from the designs stored in the label records
# (every record keeps both designs; the source comes from `design_file` for
# harness cases or `source_file` for the designer references), so a label
# set never goes stale when a term changes. Pairs whose design is a sealed
# hold-out (docs/designer2/holdout_ids.json, or `holdout: true` on the
# record) are never fitted: they are reported separately.

ENERGY_WEIGHTS_OUT = ROOT / "engine" / "energy_weights.json"
ENERGY_FIT_OUT = ROOT / "eval" / "data" / "energy_weights.json"
DESIGNER_LABELS_FILE = ROOT / "eval" / "data" / "labels.designer.jsonl"            # tools/designer_compare.py --labels
DESIGNER_ENGINE_FILE = ROOT / "eval" / "data" / "labels_designer_engine.jsonl"     # eval/perturb_designer.py (same pairs)
DESIGNER_PERTURB_FILE = ROOT / "eval" / "data" / "labels_designer_perturb.jsonl"
HOLDOUT_IDS_FILE = ROOT.parent / "docs" / "designer2" / "holdout_ids.json"
DEFAULT_DESIGNER_WEIGHT = 1.0
ENERGY_FLOOR = 0.01          # 21 terms: each keeps at least 1 % of the sum (the scorer's 5 % would exceed 100 %)


def energy_hand_weights() -> dict[str, float]:
    from engine.energy import HAND_WEIGHTS

    return dict(HAND_WEIGHTS)


def holdout_ids(path: Path = HOLDOUT_IDS_FILE) -> set[str]:
    try:
        return set(json.loads(Path(path).read_text()))
    except (OSError, ValueError):
        return set()


def _source_for(record: dict[str, Any]) -> dict[str, Any] | None:
    sf = record.get("source_file")
    if sf:
        p = Path(sf)
        p = p if p.is_absolute() else ROOT.parent / p
    elif record.get("design_file"):
        p = ROOT / "eval" / "data" / str(record["design_file"])
    else:
        return None
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return doc.get("source", doc) if isinstance(doc, dict) else None


def energy_records(records: Iterable[dict[str, Any]], *, log=None) -> list[dict[str, Any]]:
    """Add `energy` ({total, hard, terms}) to both sides of every record whose
    source and designs can be loaded; the others are dropped. Analyses are
    cached per source."""
    from engine.analyze import analyze
    from engine.energy import energy_of
    from engine.geometry import Box

    analyses: dict[str, Any] = {}
    sources: dict[str, dict[str, Any]] = {}
    out = []
    dropped = 0
    for r in records:
        key = str(r.get("source_file") or r.get("design_file") or "")
        if key not in sources:
            src = _source_for(r)
            if src is None:
                dropped += 1
                continue
            sources[key] = src
            analyses[key] = analyze(src)
        src, an = sources[key], analyses[key]
        t = r.get("target") or {}
        try:
            target = Box(0.0, 0.0, float(t["width"]), float(t["height"]))
            sides = {}
            for s in ("a", "b"):
                design = (r.get(s) or {}).get("design")
                if not design:
                    raise KeyError(s)
                e = energy_of(an, src, design, target)
                sides[s] = dict(r[s], energy={"total": round(e.total, 4), "hard": list(e.hard),
                                              "terms": {k: round(v, 5) for k, v in e.terms.items()}})
        except Exception as exc:  # a record from an older schema, a missing design
            dropped += 1
            if log:
                log(f"skip {r.get('case_key')}: {exc!r}")
            continue
        out.append(dict(r, **sides))
    if log and dropped:
        log(f"{dropped} records dropped (no source / design)")
    return out


def build_energy_pairs(records: Iterable[dict[str, Any]], components: list[str], *,
                       weak_weight: float = DEFAULT_WEAK_WEIGHT,
                       designer_weight: float = DEFAULT_DESIGNER_WEIGHT) -> Pairs:
    X, pinned, y, w, design, kind = [], [], [], [], [], []
    skipped: dict[str, int] = {}
    for r in records:
        d = r.get("decision")
        if d not in ("a", "b", "tie"):
            skipped[str(d)] = skipped.get(str(d), 0) + 1
            continue
        ea, eb = (r.get("a") or {}).get("energy"), (r.get("b") or {}).get("energy")
        if not ea or not eb:
            skipped["no energy"] = skipped.get("no energy", 0) + 1
            continue
        if len(ea["hard"]) != len(eb["hard"]):
            # The hard terms are pinned at 1000 each, so such a pair says
            # nothing about the soft weights; a label that contradicts the
            # hard rules (a designer reference that collides on purpose) only
            # drives the temperature to zero and flattens the whole fit.
            # They are counted and reported, not fitted.
            skipped["hard fails differ (reported, not fitted)"] = skipped.get("hard fails differ (reported, not fitted)", 0) + 1
            continue
        ta, tb = ea["terms"], eb["terms"]
        X.append([-(float(ta.get(k, 0.0)) - float(tb.get(k, 0.0))) for k in components])
        pinned.append(-HARD_PENALTY * (len(ea["hard"]) - len(eb["hard"])))
        y.append({"a": 1.0, "b": 0.0, "tie": 0.5}[d])
        k = str(r.get("kind", "human"))
        w.append(weak_weight if k == "weak" else designer_weight if k == "designer" else 1.0)
        design.append(str(r.get("design_id", "")))
        kind.append(k)
    n = len(y)
    return Pairs(components, np.array(X, dtype=float).reshape(n, len(components)),
                 np.array(pinned, dtype=float), np.array(y, dtype=float), np.array(w, dtype=float),
                 design, kind, skipped)


def _by_kind(P: Pairs, weights: dict[str, float]) -> dict[str, Any]:
    out = {}
    for k in sorted(set(P.kind)):
        sub = P.subset(np.array([x == k for x in P.kind], dtype=bool))
        out[k] = agreement(sub, weights)
    return out


def hard_fail_picture(records: list[dict[str, Any]]) -> dict[str, Any]:
    """For the designer pairs: how often the reference itself trips the
    energy's hard rules (those pairs cannot be won by any soft weights)."""
    out = {"designer_pairs": 0, "reference_hard": 0, "engine_hard": 0, "kinds": {}}
    for r in records:
        if r.get("kind") != "designer":
            continue
        a, b = r.get("a") or {}, r.get("b") or {}
        ref, eng = (a, b) if a.get("id") == "designer" else (b, a)
        if not ref.get("energy") or not eng.get("energy"):
            continue
        out["designer_pairs"] += 1
        out["reference_hard"] += bool(ref["energy"]["hard"])
        out["engine_hard"] += bool(eng["energy"]["hard"])
        for h in ref["energy"]["hard"]:
            k = h.split(":")[0]
            out["kinds"][k] = out["kinds"].get(k, 0) + 1
    return out


def energy_report(P: Pairs, H: Pairs | None, hand: dict[str, float], fit: Fit, lodo: dict[str, Any],
                  comp: dict[str, dict[str, Any]], perturb_agree: dict[str, Any] | None = None,
                  picture: dict[str, Any] | None = None) -> str:
    lines = []
    if picture and picture.get("designer_pairs"):
        lines.append(f"designer pairs: {picture['designer_pairs']}; the reference trips a hard rule in "
                     f"{picture['reference_hard']} (kinds {picture['kinds']}), the engine in {picture['engine_hard']}: "
                     "those pairs are unwinnable for any soft weights and are left out of the fit")
    kinds = {k: sum(1 for x in P.kind if x == k) for k in sorted(set(P.kind))}
    lines.append(f"pairs fitted: {len(P)} ({', '.join(f'{v} {k}' for k, v in kinds.items())}); skipped: {P.skipped or 'none'}")
    a_hand, a_fit = agreement(P, hand), agreement(P, fit.weights)
    lines.append(f"agreement with decisive labels (n={a_hand['n']}): hand weights {a_hand['agree']}, fitted {a_fit['agree']} "
                 f"(in sample), fitted leave-one-design-out {lodo['agree']} over {lodo['folds']} folds")
    bh, bf = _by_kind(P, hand), _by_kind(P, fit.weights)
    for k in bh:
        lines.append(f"  {k}: n={bh[k]['n']} hand {bh[k]['agree']} fitted {bf[k]['agree']}")
    if perturb_agree:
        lines.append("  per perturbation (hand -> fitted): " + ", ".join(
            f"{k} {v['hand']}->{v['fitted']} (n={v['n']})" for k, v in sorted(perturb_agree.items())))
    if H is not None and len(H):
        hh, hf = agreement(H, hand), agreement(H, fit.weights)
        lines.append(f"HELD OUT (never fitted; n={hh['n']} decisive): hand {hh['agree']}, fitted {hf['agree']}")
    else:
        lines.append("HELD OUT: no held-out pairs (batch two references not present)")
    lines.append(f"temperature {fit.temperature:.4f}, loss {fit.loss:.4f}, floor {fit.floor:.0%} of the sum; "
                 f"frozen at the hand weight (no evidence): {', '.join(fit.frozen) or 'none'}")
    lines.append("")
    lines.append("| term | hand | fitted | change | pairs where it differs | agrees with label |")
    lines.append("|---|---|---|---|---|---|")
    for c in P.components:
        ca = comp[c]
        agree = "-" if ca["agree"] is None else f"{ca['agree']:.2f}"
        lines.append(f"| {c} | {hand[c]:.1f} | {fit.weights[c]:.1f} | {fit.weights[c] - hand[c]:+.1f} | {ca['n']} | {agree} |")
    return "\n".join(lines)


def calibrate_energy(labels: Path = LABELS_FILE, weak: Path | None = WEAK_LABELS_FILE,
                     designer: Path | None = DESIGNER_LABELS_FILE, perturb: Path | None = DESIGNER_PERTURB_FILE, *,
                     weak_weight: float = DEFAULT_WEAK_WEIGHT, designer_weight: float = DEFAULT_DESIGNER_WEIGHT,
                     floor: float = ENERGY_FLOOR, l2: float = DEFAULT_L2, out: Path | None = ENERGY_FIT_OUT,
                     install: Path | None = None, max_folds: int | None = 60, min_pairs: int = DEFAULT_MIN_PAIRS,
                     log=None) -> dict[str, Any]:
    hand = energy_hand_weights()
    components = list(hand)
    records = [dict(r, kind=r.get("kind", "human")) for r in read_labels(labels)]
    if weak is not None:
        records += [dict(r, kind="weak") for r in read_labels(weak)]
    if designer is not None:
        if not Path(designer).exists() and designer == DESIGNER_LABELS_FILE and DESIGNER_ENGINE_FILE.exists():
            designer = DESIGNER_ENGINE_FILE
        # reference > engine pairs, whichever tool wrote them (designer_compare
        # records them as kind "weak"; here they are their own kind)
        records += [dict(r, kind="designer") for r in read_labels(designer)]
    if perturb is not None:
        records += [dict(r, kind="weak") for r in read_labels(perturb)]
    hold = holdout_ids()
    records = energy_records(records, log=log)
    held = [r for r in records if r.get("holdout") or str(r.get("design_id")) in hold]
    train = [r for r in records if not (r.get("holdout") or str(r.get("design_id")) in hold)]
    P = build_energy_pairs(train, components, weak_weight=weak_weight, designer_weight=designer_weight)
    H = build_energy_pairs(held, components, weak_weight=weak_weight, designer_weight=designer_weight) if held else None
    fit = fit_weights(P, floor=floor, l2=l2, prior=hand, min_pairs=min_pairs)
    lodo = leave_one_design_out(P, floor=floor, l2=l2, prior=hand, max_folds=max_folds, min_pairs=min_pairs)
    comp = component_agreement(P)
    # per perturbation kind (the PRISM-style pairs name theirs)
    per: dict[str, Any] = {}
    names = [str(r.get("perturbation") or "") for r in train if r.get("decision") in ("a", "b", "tie")
             and (r.get("a") or {}).get("energy") and (r.get("b") or {}).get("energy")]
    if len(names) == len(P):
        arr = np.array(names)
        for pn in sorted(set(names) - {""}):
            sub = P.subset(arr == pn)
            per[pn] = {"n": int(sub.decisive.sum()), "hand": agreement(sub, hand)["agree"], "fitted": agreement(sub, fit.weights)["agree"]}
    picture = hard_fail_picture(train)
    text = energy_report(P, H, hand, fit, lodo, comp, per, picture)
    result = {
        "weights": fit.weights, "temperature": round(fit.temperature, 6),
        "meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "energy",
            "files": {"labels": str(labels), "weak": str(weak) if weak else None, "designer": str(designer) if designer else None,
                      "perturb": str(perturb) if perturb else None},
            "n_pairs": len(P), "n_by_kind": {k: sum(1 for x in P.kind if x == k) for k in sorted(set(P.kind))},
            "n_held_out": len(H) if H is not None else 0, "weak_weight": weak_weight, "designer_weight": designer_weight,
            "floor": floor, "l2": l2, "min_pairs": min_pairs, "loss": fit.loss, "frozen": fit.frozen,
            "agreement_hand": agreement(P, hand), "agreement_fitted": agreement(P, fit.weights), "agreement_lodo": lodo,
            "agreement_by_kind_hand": _by_kind(P, hand), "agreement_by_kind_fitted": _by_kind(P, fit.weights),
            "agreement_holdout_hand": agreement(H, hand) if H is not None and len(H) else None,
            "agreement_holdout_fitted": agreement(H, fit.weights) if H is not None and len(H) else None,
            "per_perturbation": per, "components": comp, "hand_weights": hand, "hard_fail_picture": picture,
        },
        "report": text,
    }
    payload = json.dumps({k: v for k, v in result.items() if k != "report"}, indent=1) + "\n"
    if out is not None and len(P):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(payload)
        result["written"] = str(out)
    if install is not None and len(P):
        Path(install).write_text(payload)
        result["installed"] = str(install)
    return result


def _main_energy(args: argparse.Namespace) -> int:
    res = calibrate_energy(args.labels, None if args.no_weak else args.weak,
                           None if args.no_designer else args.designer, None if args.no_perturb else args.perturb,
                           weak_weight=args.weak_weight, designer_weight=args.designer_weight,
                           floor=ENERGY_FLOOR if args.floor is None else args.floor,
                           l2=args.l2, out=None if args.dry_run else args.energy_out,
                           install=ENERGY_WEIGHTS_OUT if args.install and not args.dry_run else None,
                           max_folds=args.max_folds or None, min_pairs=args.min_pairs,
                           log=lambda s: print(s, flush=True))
    print(res["report"])
    if res.get("written"):
        print(f"\nwrote {res['written']}")
    if res.get("installed"):
        print(f"installed {res['installed']} (engine/energy.py loads it at import)")
    return 0


def _patched_main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="calibrate the scorer (default) or the design energy (--energy)")
    ap.add_argument("--energy", action="store_true", help="fit engine/energy.py's term weights instead of the scorer's")
    ap.add_argument("--labels", type=Path, default=LABELS_FILE)
    ap.add_argument("--weak", type=Path, default=WEAK_LABELS_FILE)
    ap.add_argument("--no-weak", action="store_true", help="ignore the weak labels")
    ap.add_argument("--designer", type=Path, default=DESIGNER_LABELS_FILE, help="(energy) designer > engine pairs")
    ap.add_argument("--no-designer", action="store_true")
    ap.add_argument("--perturb", type=Path, default=DESIGNER_PERTURB_FILE, help="(energy) designer perturbation pairs")
    ap.add_argument("--no-perturb", action="store_true")
    ap.add_argument("--weak-weight", type=float, default=DEFAULT_WEAK_WEIGHT)
    ap.add_argument("--designer-weight", type=float, default=DEFAULT_DESIGNER_WEIGHT)
    ap.add_argument("--floor", type=float, default=None,
                    help=f"min weight as a share of the sum (default {DEFAULT_FLOOR} scorer, {ENERGY_FLOOR} energy)")
    ap.add_argument("--l2", type=float, default=DEFAULT_L2, help="pull toward the hand weights")
    ap.add_argument("--out", type=Path, default=WEIGHTS_OUT)
    ap.add_argument("--energy-out", type=Path, default=ENERGY_FIT_OUT)
    ap.add_argument("--install", action="store_true", help="(energy) also write engine/energy_weights.json")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--max-folds", type=int, default=60, help="cap on leave-one-design-out folds (0 = none)")
    ap.add_argument("--min-pairs", type=int, default=DEFAULT_MIN_PAIRS,
                    help="decisive pairs a component must differ in to be fitted (else frozen at the hand weight)")
    args = ap.parse_args(argv)
    if args.energy:
        return _main_energy(args)
    res = calibrate(args.labels, None if args.no_weak else args.weak, weak_weight=args.weak_weight,
                    floor=DEFAULT_FLOOR if args.floor is None else args.floor, l2=args.l2,
                    out=None if args.dry_run else args.out, max_folds=args.max_folds or None, min_pairs=args.min_pairs)
    print(res["report"])
    if res.get("written"):
        print(f"\nwrote {res['written']}")
    elif not res["meta"]["n_pairs"]:
        print("\nno labelled pairs: nothing written")
    return 0


main = _patched_main


if __name__ == "__main__":
    raise SystemExit(main())
