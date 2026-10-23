"""Print the markdown tables docs/ROLE_MODEL.md quotes, from
eval/data/roles/cv_report.json and meta.json (tools/train_role_model.py,
tools/build_role_dataset.py). Paste the output into the docs after retraining.

    .venv/bin/python tools/role_model_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval" / "data" / "roles"


def table(rows: list[list], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> int:
    rep = json.loads((DATA / "cv_report.json").read_text())
    meta = json.loads((DATA / "meta.json").read_text())
    roles = meta["roles"]
    print(f"Dataset: {meta['n_designs']} designs, {meta['n_elements']} elements, {meta['n_labelled']} labelled "
          f"({meta['n_unlabelled']} layers without a DesignAsCode theme). Skipped templates: {meta['skipped']}.\n")
    print("Label counts:\n")
    print(table([[r, meta["role_counts"].get(r, 0)] for r in roles], ["role", "n"]))
    print(f"\nModel: {rep['params']}; fit {rep['fit_seconds']} s; file {rep['model_bytes'] / 1e6:.2f} MB; "
          f"numpy vs sklearn max |dp| {rep['export_max_abs_diff']:.1e}; predict {rep['predict_ms_level3']} ms "
          f"(level 3 sample).\n")
    for key, title in (("cv", "5-fold grouped cross-validation (groups = template title)"),
                       ("holdout20", "Held-out 20 % of designs (fold 1 of the grouped split)")):
        if key not in rep:
            continue
        r = rep[key]
        print(f"### {title}\n")
        acc = r["accuracy"]
        extra = ""
        if key == "cv":
            extra = (f"; text {r['text_accuracy']:.3f}, image {r['image_accuracy']:.3f}, "
                     f"shape {r['shape_accuracy']:.3f}")
        print(f"Element accuracy {acc:.3f}{extra}"
              + (f" ({r['n_designs']} designs, {r['n_elements']} elements)" if "n_designs" in r else "") + ".\n")
        pr = r["per_role"]
        print(table([[ro, pr[ro]["precision"], pr[ro]["recall"], pr[ro]["f1"], pr[ro]["support"]] for ro in roles],
                    ["role", "precision", "recall", "F1", "support"]))
        d = r["design_level"]
        print("\nPer design (is the top-scoring element the labelled one?):\n")
        print(table([[k, d[f"{k}_design_acc"], d[f"{k}_design_n"]] for k in ("headline", "cta", "logo", "hero")],
                    ["role", "accuracy", "designs"]))
        print(f"\nText hierarchy: mean Spearman between the model's rank (expected tier, then font size) and the "
              f"label rank = {d['hierarchy_spearman']} over {d['hierarchy_n']} designs with >= 3 texts.\n")
    if "confusion" in rep.get("cv", {}):
        c = rep["cv"]["confusion"]
        print("Confusion (rows = label, columns = prediction):\n")
        print(table([[roles[i]] + c[i] for i in range(len(roles))], ["label \\ pred"] + [r[:5] for r in roles]))
        print()
    print("Top features (permutation importance, accuracy drop on 5k elements):\n")
    print(table([[n, v] for n, v in rep["top_features"][:20]], ["feature", "drop"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
