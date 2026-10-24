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
                iters: int = 400) -> Fit:
    """Non-negative weights (sum 100, each >= floor * 100) and a temperature
    by L-BFGS on the weighted logistic loss, starting at the hand weights.
    Components that differ in fewer than `min_pairs` decisive pairs are
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


if __name__ == "__main__":
    raise SystemExit(main())
