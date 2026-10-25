"""A small learned ranker for the judge, compared honestly with the linear fit (v8).

Reads the candidate dump of eval/picker_gap.py and learns to rank the
candidates of a case by designer agreement from features the judge already
has at decision time: the breakdown terms, the design-energy terms
(engine/energy.py), the seed family (anchor / template / structure, refined
or not), the pinned penalties and the shape change. Hard fails stay pinned:
a candidate with a hard fail never outranks a clean one.

Models (all fitted on the tuning designs only; the sealed hold-out designs
are scored once at the end):

  linear-ext   logistic regression on pairwise feature differences
               (candidate pairs with agreement margin >= 0.05, both orders),
               i.e. a linear score over the extended feature set
  gbt-point    HistGradientBoostingRegressor on the candidate's agreement
               relative to the best of its case (pointwise), one case = one
               unit of sample weight, shallow trees so it exports like
               engine/models/roles.npz (complete trees, numpy traversal)

Reported for every model and for the hand / fitted weights: re-ranking
agreement on the tuning set (leave-one-design-out over 25 folds) and on the
hold-out, best-vs-chosen gap, hard fails, family shares.

    .venv/bin/python -m eval.rank_judge [--dump ...] [--weights eval/data/score_weights.v8.json] [--export PATH.npz]
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

from eval.fit_judge import DUMP, FIT_OUT, hand_weights, rerank, rerank_stats  # noqa: E402
from eval.picker_gap import load_rows  # noqa: E402

FAMILIES = ("anchor", "floorplan", "structure")
TGT = ("tall", "square", "wide", "banner")
MARGIN = 0.05
FOLDS = 25


def feature_names(rows: list[dict[str, Any]]) -> list[str]:
    bd = list(hand_weights())
    en = sorted({k for r in rows for c in r["candidates"] for k in (c.get("energy") or {}).get("terms", {})})
    return ([f"bd.{k}" for k in bd] + [f"en.{k}" for k in en] + [f"fam.{f}" for f in FAMILIES]
            + ["opt", "fallback", "penalty", "n_hard", "log_ratio_change"] + [f"tgt.{t}" for t in TGT])


def features(row: dict[str, Any], c: dict[str, Any], names: list[str]) -> list[float]:
    bd, en = c["breakdown"], (c.get("energy") or {}).get("terms", {})
    out = []
    for n in names:
        if n.startswith("bd."):
            out.append(float(bd.get(n[3:], 0.0)))
        elif n.startswith("en."):
            out.append(float(en.get(n[3:], 0.0)))
        elif n.startswith("fam."):
            out.append(1.0 if c["strategy"] == n[4:] else 0.0)
        elif n.startswith("tgt."):
            out.append(1.0 if row["tgt_family"] == n[4:] else 0.0)
        elif n == "opt":
            out.append(1.0 if c["opt"] else 0.0)
        elif n == "fallback":
            out.append(1.0 if c["fallback"] else 0.0)
        elif n == "penalty":
            out.append(float(c["penalty"]) / 20.0)
        elif n == "n_hard":
            out.append(float(len(c["hard"])))
        elif n == "log_ratio_change":
            out.append(float(np.log(max(1.0, row["ratio_change"]))))
    return out


def dataset(rows: list[dict[str, Any]], names: list[str]):
    """Pointwise arrays: X, y (agreement - best of the case), case index, weight."""
    X, y, case, w = [], [], [], []
    for ci, r in enumerate(rows):
        cands = [c for c in r["candidates"] if not c["fallback"]]
        best = max(c["agreement"] for c in cands) if cands else 0.0
        for c in cands:
            X.append(features(r, c, names))
            y.append(c["agreement"] - best)
            case.append(ci)
            w.append(1.0 / len(cands))
    return np.array(X), np.array(y), np.array(case), np.array(w)


def pair_dataset(rows: list[dict[str, Any]], names: list[str], margin: float = MARGIN):
    X, y, w = [], [], []
    for r in rows:
        cands = [c for c in r["candidates"] if not c["fallback"]]
        pairs = []
        for i, a in enumerate(cands):
            for b in cands[i + 1:]:
                if len(a["hard"]) != len(b["hard"]) or abs(a["agreement"] - b["agreement"]) < margin:
                    continue
                pairs.append((a, b))
        for a, b in pairs:
            fa, fb = np.array(features(r, a, names)), np.array(features(r, b, names))
            d = fa - fb
            yy = 1.0 if a["agreement"] > b["agreement"] else 0.0
            X += [d, -d]
            y += [yy, 1.0 - yy]
            w += [0.5 / len(pairs)] * 2
    return np.array(X), np.array(y), np.array(w)


# ---------------------------------------------------------------------------
# models


class LinearExt:
    def __init__(self, C: float = 1.0):
        self.C = C
        self.w = None

    def fit(self, rows, names):
        from sklearn.linear_model import LogisticRegression

        X, y, w = pair_dataset(rows, names)
        clf = LogisticRegression(C=self.C, fit_intercept=False, max_iter=2000)
        clf.fit(X, y, sample_weight=w)
        self.w = clf.coef_.reshape(-1)
        return self

    def score(self, row, c, names) -> float:
        return float(np.dot(self.w, features(row, c, names)))


class GBTPoint:
    def __init__(self, depth: int = 4, iters: int = 200, lr: float = 0.05, l2: float = 1.0):
        self.depth, self.iters, self.lr, self.l2 = depth, iters, lr, l2
        self.model = None

    def fit(self, rows, names):
        from sklearn.ensemble import HistGradientBoostingRegressor

        X, y, _, w = dataset(rows, names)
        self.model = HistGradientBoostingRegressor(max_depth=self.depth, max_iter=self.iters, learning_rate=self.lr,
                                                   l2_regularization=self.l2, min_samples_leaf=20, random_state=0)
        self.model.fit(X, y, sample_weight=w)
        return self

    def score(self, row, c, names) -> float:
        return float(self.model.predict(np.array([features(row, c, names)]))[0])


def pick_with(model, row, names) -> dict[str, Any]:
    """Hard fails pinned, then the model's score; the fallback is never
    picked unless every real candidate has a hard fail (the judge's policy)."""
    cands = row["candidates"]
    real = [c for c in cands if not c["fallback"]]
    pool = real if any(not c["hard"] for c in real) or not any(not c["hard"] for c in cands) else cands
    return max(pool, key=lambda c: (-len(c["hard"]), model.score(row, c, names), -c["rank"]))


def lodo(model_factory, rows: list[dict[str, Any]], names: list[str], folds: int = FOLDS) -> dict[str, Any]:
    designs = sorted({r["name"] for r in rows})
    rng = np.random.default_rng(0)
    order = list(rng.permutation(designs))
    parts = [set(order[i::folds]) for i in range(min(folds, len(order)))]
    picked: dict[str, dict[str, Any]] = {}
    for held in parts:
        m = model_factory().fit([r for r in rows if r["name"] not in held], names)
        for r in rows:
            if r["name"] in held:
                picked[f"{r['name']}|{r['format']}"] = pick_with(m, r, names)
    return rerank_stats(rows, lambda r: picked[f"{r['name']}|{r['format']}"])


def export_gbt(model: GBTPoint, names: list[str], path: Path) -> None:
    """Complete-tree export in the layout of engine/models/roles.npz (one
    'class': the relative-agreement regression)."""
    from tools.train_role_model import export_hgb  # noqa: WPS433 (dev tool)

    arrays = export_hgb(model.model, ["agreement"], model.depth)
    arrays["feature_names"] = np.asarray(names)
    np.savez_compressed(path, **arrays)


def _fmt(label, s):
    return (f"| {label} | {s['n']} | {s['agreement']:.3f} | {s['gap_to_best']:.3f} | {s['gap_to_best_clean']:.3f} | "
            f"{s['hard']} | {s['fallback']} | {s['order_tau']:.3f} | " + ", ".join(f"{k} {v}" for k, v in s["families"].items()) + " |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", type=Path, default=DUMP)
    ap.add_argument("--weights", type=Path, default=FIT_OUT, help="the linear fit to compare with")
    ap.add_argument("--export", type=Path, default=None, help="write the gbt-point model as an npz")
    ap.add_argument("--no-lodo", action="store_true")
    args = ap.parse_args(argv)
    rows = load_rows(args.dump)
    tune = [r for r in rows if not r["holdout"]]
    hold = [r for r in rows if r["holdout"]]
    names = feature_names(rows)
    hand = hand_weights()
    fitted = None
    if args.weights.exists():
        fitted = json.loads(args.weights.read_text())["weights"]

    L = [f"# Learned ranker vs linear fit (v8)\n\n{len(rows)} cases, {len(hold)} hold-out; {len(names)} features; "
         f"leave-one-design-out over {FOLDS} folds on the tuning set.\n",
         "| model | n | agreement | gap to best | gap to best clean | hard | fallback wins | order tau | winner families |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    L.append(_fmt("tuning: judge as run (hand)", rerank_stats(tune, lambda r: r["candidates"][0])))
    if fitted:
        L.append(_fmt("tuning: linear fit (in sample)", rerank_stats(tune, lambda r: rerank(r, fitted))))
    models = {"linear-ext C=0.3": lambda: LinearExt(0.3), "linear-ext C=3": lambda: LinearExt(3.0),
              "gbt-point d3": lambda: GBTPoint(3, 150, 0.05, 1.0), "gbt-point d4": lambda: GBTPoint(4, 200, 0.05, 1.0)}
    fitted_models = {}
    for name, factory in models.items():
        t0 = time.time()
        if not args.no_lodo:
            L.append(_fmt(f"tuning: {name} (leave-one-design-out)", lodo(factory, tune, names)))
        m = factory().fit(tune, names)
        fitted_models[name] = m
        L.append(_fmt(f"tuning: {name} (in sample)", rerank_stats(tune, lambda r, m=m: pick_with(m, r, names))))
        print(f"{name}: {time.time() - t0:.0f} s", flush=True)
    L.append(_fmt("HOLD-OUT: judge as run (hand)", rerank_stats(hold, lambda r: r["candidates"][0])))
    if fitted:
        L.append(_fmt("HOLD-OUT: linear fit", rerank_stats(hold, lambda r: rerank(r, fitted))))
    for name, m in fitted_models.items():
        L.append(_fmt(f"HOLD-OUT: {name}", rerank_stats(hold, lambda r, m=m: pick_with(m, r, names))))
    # linear-ext coefficients, for the record
    m = fitted_models["linear-ext C=0.3"]
    top = sorted(zip(names, m.w), key=lambda kv: -abs(kv[1]))[:20]
    L += ["", "linear-ext C=0.3 largest coefficients: " + ", ".join(f"{n} {v:+.2f}" for n, v in top)]
    text = "\n".join(L) + "\n"
    print(text)
    (args.dump.parent / "RANKER.md").write_text(text)
    if args.export:
        export_gbt(fitted_models["gbt-point d4"], names, args.export)
        print("exported", args.export, args.export.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
