"""Train the role classifier and export it for engine/role_model.py.

    .venv/bin/python tools/train_role_model.py            # CV report + export
    .venv/bin/python tools/train_role_model.py --no-cv    # export only

Reads eval/data/roles/dataset.npz (tools/build_role_dataset.py), runs a
5-fold grouped cross-validation (groups = template title, so the same design
at several sizes never straddles train and test), prints per-role
precision / recall / F1, per-design headline / CTA / logo / hero accuracy and
the text-hierarchy agreement, then fits on everything and writes

    engine/models/roles.npz              the shipped model (complete trees, depth D)
    tests/fixtures/roles_tiny.npz        a 3-iteration model for offline tests
    tests/fixtures/roles_tiny_expected.json
                                         sklearn probabilities on a fixed design
    eval/data/roles/cv_report.json       the numbers docs/ROLE_MODEL.md quotes

Dev tool; needs scikit-learn (not a runtime dependency).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import role_features as RF  # noqa: E402
from engine import role_model as RM  # noqa: E402

DATA = ROOT / "eval" / "data" / "roles"
MODEL_OUT = ROOT / "engine" / "models" / "roles.npz"
TINY_OUT = ROOT / "tests" / "fixtures" / "roles_tiny.npz"
TINY_EXPECTED = ROOT / "tests" / "fixtures" / "roles_tiny_expected.json"

# rare roles that matter most to the layouts get more weight; the probabilities
# stay usable as confidences (checked on the samples / eval designs)
CLASS_WEIGHT = {"logo": 4.0, "cta": 2.0, "hero": 1.5, "subhead": 1.3}

PARAMS = dict(max_iter=120, learning_rate=0.08, max_depth=6, max_leaf_nodes=48, min_samples_leaf=20,
              l2_regularization=1.0, early_stopping=False, random_state=0)


# ---------------------------------------------------------------------------
# export: sklearn HGB -> complete binary trees


def export_hgb(clf, roles: list[str], depth: int) -> dict[str, np.ndarray]:
    n_classes = len(roles)
    n_nodes = 2 ** depth - 1
    n_leaves = 2 ** depth
    predictors = clf._predictors            # [iter][class] -> TreePredictor
    n_iter = len(predictors)
    trees = [p for it in predictors for p in it]
    assert len(trees) == n_iter * n_classes
    F = np.zeros((len(trees), n_nodes), dtype=np.int16)
    T = np.full((len(trees), n_nodes), np.inf, dtype=np.float32)
    V = np.zeros((len(trees), n_leaves), dtype=np.float32)
    for ti, pred in enumerate(trees):
        nodes = pred.nodes
        # (sklearn node index, slot in the complete tree, depth)
        stack = [(0, 0, 0)]
        while stack:
            ni, slot, d = stack.pop()
            node = nodes[ni]
            if d == depth and not node["is_leaf"]:
                raise ValueError("tree deeper than export depth")
            if node["is_leaf"]:
                # pad: the pads below keep feature 0 / threshold +inf (always
                # left), and every depth-D leaf under this node gets its value
                first = slot
                for _ in range(depth - d):
                    first = 2 * first + 1
                span = 2 ** (depth - d)
                V[ti, first - n_nodes: first - n_nodes + span] = node["value"]
                continue
            if node["is_categorical"]:
                raise ValueError("categorical splits are not supported")
            F[ti, slot] = node["feature_idx"]
            T[ti, slot] = node["num_threshold"]
            stack.append((int(node["left"]), 2 * slot + 1, d + 1))
            stack.append((int(node["right"]), 2 * slot + 2, d + 1))
    baseline = np.asarray(clf._baseline_prediction, dtype=np.float32).reshape(-1)
    return {
        "feature": F, "threshold": T, "value": V, "baseline": baseline,
        "roles": np.asarray(roles), "feature_names": np.asarray(RF.FEATURE_NAMES),
        "depth": np.asarray(depth), "n_iter": np.asarray(n_iter),
    }


def save_model(arrays: dict[str, np.ndarray], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


# ---------------------------------------------------------------------------
# evaluation helpers


def per_role_report(y_true: np.ndarray, y_pred: np.ndarray, roles: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    for k, r in enumerate(roles):
        tp = int(((y_true == k) & (y_pred == k)).sum())
        fp = int(((y_true != k) & (y_pred == k)).sum())
        fn = int(((y_true == k) & (y_pred != k)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        out[r] = {"precision": round(p, 3), "recall": round(rc, 3), "f1": round(f1, 3), "support": tp + fn}
    return out


def design_level(P: np.ndarray, y: np.ndarray, design: np.ndarray, etype: np.ndarray, roles: list[str],
                 h_rank: np.ndarray) -> dict[str, float]:
    """Per-design accuracies: is the element with the highest P(role) the
    labelled one, for headline / cta / logo / hero; plus the Spearman agreement
    of the text hierarchy (designs with >= 3 texts)."""
    idx = {r: roles.index(r) for r in roles}
    hits = {r: [0, 0] for r in ("headline", "cta", "logo", "hero")}
    rhos = []
    for d in np.unique(design):
        m = design == d
        Pd, yd, td, hd = P[m], y[m], etype[m], h_rank[m]
        for r in hits:
            k = idx[r]
            if (yd == k).sum() == 0:
                continue
            hits[r][1] += 1
            if r == "cta":
                # a CTA may be a group: the top-scoring text wins
                cand = np.where(td == 0)[0] if (td == 0).any() else np.arange(len(yd))
            elif r == "headline":
                cand = np.where(td == 0)[0]
            else:
                cand = np.where(td == 1)[0]
            if len(cand) == 0:
                continue
            best = cand[np.argmax(Pd[cand, k])]
            if yd[best] == k:
                hits[r][0] += 1
        texts = np.where(td == 0)[0]
        if len(texts) >= 3:
            tiers = np.array([RM.TIER.get(r, 3.0) for r in roles])
            exp_tier = Pd[texts] @ tiers
            pred_rank = np.argsort(np.argsort(exp_tier, kind="stable"), kind="stable")
            rhos.append(_spearman(pred_rank, hd[texts]))
    out = {f"{r}_design_acc": round(h / n, 3) if n else None for r, (h, n) in hits.items()}
    out.update({f"{r}_design_n": n for r, (h, n) in hits.items()})
    out["hierarchy_spearman"] = round(float(np.mean(rhos)), 3) if rhos else None
    out["hierarchy_n"] = len(rhos)
    return out


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = np.argsort(np.argsort(a)).astype(float)
    b = np.argsort(np.argsort(b)).astype(float)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cv", action="store_true")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--max-iter", type=int, default=PARAMS["max_iter"])
    ap.add_argument("--depth", type=int, default=PARAMS["max_depth"])
    args = ap.parse_args(argv)

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    z = np.load(DATA / "dataset.npz")
    meta = json.loads((DATA / "meta.json").read_text())
    X, y, design, etype, h_rank = z["X"], z["y"].astype(int), z["design"], z["etype"], z["h_rank"]
    sample = z["sample"] if "sample" in z.files else design     # design-level metrics per augmented copy
    roles = meta["roles"]
    assert meta["feature_names"] == RF.FEATURE_NAMES, "rebuild the dataset: feature set changed"
    groups = np.asarray(meta["design_group"])[design]
    w = np.ones(X.shape[0])
    for r, v in CLASS_WEIGHT.items():
        w[y == roles.index(r)] = v
    print(f"{X.shape[0]} elements, {len(np.unique(design))} designs, {len(np.unique(groups))} title groups")

    params = dict(PARAMS, max_iter=args.max_iter, max_depth=args.depth)
    report: dict = {"params": params, "class_weight": CLASS_WEIGHT, "n_elements": int(X.shape[0]),
                    "n_designs": int(len(np.unique(design))), "role_counts": meta["role_counts"]}

    if not args.no_cv:
        P = np.zeros((X.shape[0], len(roles)))
        t0 = time.time()
        for fold, (tr, te) in enumerate(GroupKFold(n_splits=args.folds).split(X, y, groups)):
            clf = HistGradientBoostingClassifier(**params)
            clf.fit(X[tr], y[tr], sample_weight=w[tr])
            P[te] = clf.predict_proba(X[te])
            print(f"fold {fold}: {len(te)} test elements, acc {(P[te].argmax(1) == y[te]).mean():.3f}")
        y_pred = P.argmax(1)
        report["cv"] = {
            "accuracy": round(float((y_pred == y).mean()), 4),
            "text_accuracy": round(float((y_pred[etype == 0] == y[etype == 0]).mean()), 4),
            "image_accuracy": round(float((y_pred[etype == 1] == y[etype == 1]).mean()), 4),
            "shape_accuracy": round(float((y_pred[etype == 2] == y[etype == 2]).mean()), 4),
            "per_role": per_role_report(y, y_pred, roles),
            "design_level": design_level(P, y, sample, etype, roles, h_rank),
            "confusion": _confusion(y, y_pred, len(roles)).tolist(),
            "seconds": round(time.time() - t0, 1),
        }
        # a held-out 20 % split (the last fold of a 5-fold grouped split) for the docs
        tr, te = next(iter(GroupKFold(n_splits=5).split(X, y, groups)))
        clf = HistGradientBoostingClassifier(**params).fit(X[tr], y[tr], sample_weight=w[tr])
        Pt = clf.predict_proba(X[te])
        report["holdout20"] = {
            "n_elements": int(len(te)), "n_designs": int(len(np.unique(design[te]))),
            "accuracy": round(float((Pt.argmax(1) == y[te]).mean()), 4),
            "per_role": per_role_report(y[te], Pt.argmax(1), roles),
            "design_level": design_level(Pt, y[te], sample[te], etype[te], roles, h_rank[te]),
        }
        print(json.dumps(report["cv"]["per_role"], indent=1))
        print(json.dumps(report["cv"]["design_level"], indent=1))

    # final fit + export
    t0 = time.time()
    clf = HistGradientBoostingClassifier(**params).fit(X, y, sample_weight=w)
    report["fit_seconds"] = round(time.time() - t0, 1)
    arrays = export_hgb(clf, roles, args.depth)
    save_model(arrays, MODEL_OUT)
    model = RM.RoleModel(MODEL_OUT)
    # the numpy path must reproduce sklearn
    sample = np.random.RandomState(0).choice(X.shape[0], size=min(2000, X.shape[0]), replace=False)
    diff = np.abs(model.proba(X[sample]) - clf.predict_proba(X[sample])).max()
    report["export_max_abs_diff"] = float(diff)
    report["model_bytes"] = MODEL_OUT.stat().st_size
    print(f"exported {MODEL_OUT} ({MODEL_OUT.stat().st_size / 1e6:.2f} MB), max |diff| vs sklearn {diff:.2e}")
    assert diff < 1e-4, "export mismatch"
    imp = _importance(clf, X, y, roles)
    report["top_features"] = imp[:25]

    # tiny fixture for tests (3 iterations) + its expected probabilities on the samples
    tiny = HistGradientBoostingClassifier(**dict(params, max_iter=3)).fit(X, y, sample_weight=w)
    save_model(export_hgb(tiny, roles, args.depth), TINY_OUT)
    expected = {}
    for name in ("chameleon_sample_level1_warmup", "chameleon_sample_level2_core", "chameleon_sample_level3_advanced"):
        src = json.loads((ROOT / "input" / f"{name}.json").read_text())["source"]
        ids, rows = RF.features(src)
        expected[name] = {eid: [round(float(v), 6) for v in p] for eid, p in zip(ids, tiny.predict_proba(rows))}
    TINY_EXPECTED.write_text(json.dumps({"roles": roles, "proba": expected}, indent=0))

    # timing of the shipped model
    src = json.loads((ROOT / "input" / "chameleon_sample_level3_advanced.json").read_text())["source"]
    RM.predict(src)
    t0 = time.perf_counter()
    for _ in range(20):
        RM.predict(src)
    report["predict_ms_level3"] = round((time.perf_counter() - t0) / 20 * 1000, 2)
    print(f"predict: {report['predict_ms_level3']} ms per design (level 3 sample)")

    (DATA / "cv_report.json").write_text(json.dumps(report, indent=1))
    return 0


def _confusion(y: np.ndarray, p: np.ndarray, k: int) -> np.ndarray:
    m = np.zeros((k, k), dtype=int)
    for a, b in zip(y, p):
        m[a, b] += 1
    return m


def _importance(clf, X: np.ndarray, y: np.ndarray, roles: list[str]) -> list[tuple[str, float]]:
    """Permutation importance on a 5k subsample (cheap, model-agnostic)."""
    rs = np.random.RandomState(0)
    idx = rs.choice(X.shape[0], size=min(5000, X.shape[0]), replace=False)
    Xs, ys = X[idx].copy(), y[idx]
    base = (clf.predict(Xs) == ys).mean()
    out = []
    for j, name in enumerate(RF.FEATURE_NAMES):
        col = Xs[:, j].copy()
        Xs[:, j] = rs.permutation(col)
        out.append((name, round(float(base - (clf.predict(Xs) == ys).mean()), 4)))
        Xs[:, j] = col
    out.sort(key=lambda t: -t[1])
    return out


if __name__ == "__main__":
    raise SystemExit(main())
