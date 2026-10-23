"""Evaluate the shipped role model where the training data cannot: the three
samples with ids stripped, the 450 converted eval designs (agreement with
the rule analyzer, no labels there), and the Boynton poster.

    .venv/bin/python tools/eval_role_model.py [--design <crello id>] [--markdown]
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import analyze as A  # noqa: E402
from engine import role_merge as RMG  # noqa: E402
from engine import role_model as RM  # noqa: E402

SAMPLES = ("chameleon_sample_level1_warmup", "chameleon_sample_level2_core", "chameleon_sample_level3_advanced")
BOYNTON = "5928010895a7a863ddcd8e06"


def strip_ids(source: dict) -> tuple[dict, dict[str, str]]:
    src = copy.deepcopy(source)
    back, gids = {}, {}
    for i, el in enumerate(src["elements"]):
        new = f"e{i:02d}"
        back[new] = el["id"]
        el["id"] = new
        if el.get("group_id"):
            el["group_id"] = gids.setdefault(el["group_id"], f"g{len(gids)}")
    return src, back


def table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


def design_rows(src: dict, back: dict[str, str] | None = None) -> list[dict]:
    rules = A.analyze(src).roles
    probs = RM.predict_proba(src)
    merged = RMG.merged_roles(src, rules, probs=probs, force=True)
    rows = []
    for el in src["elements"]:
        eid = el["id"]
        p = probs.get(eid, {})
        fam = RM.allowed_roles(el["type"])
        best = max(((r, v) for r, v in p.items() if r in fam), key=lambda t: t[1], default=("", 0.0))
        label = back.get(eid, eid) if back else eid
        text = (str(el.get("content", ""))[:28].replace("\n", " ") + ("…" if len(str(el.get("content", ""))) > 28 else "")) if el["type"] == "text" else ""
        rows.append({"id": label, "type": el["type"], "font": el.get("font_size", ""), "text": text,
                     "rule": rules.get(eid), "model": best[0], "p": f"{best[1]:.2f}", "merged": merged.get(eid),
                     "flag": "" if merged.get(eid) == rules.get(eid) else "←"})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", action="append", default=[])
    ap.add_argument("--out", default=str(ROOT / "eval" / "data" / "roles" / "eval_report.md"))
    args = ap.parse_args(argv)
    model = RM.load()
    assert model is not None, "no model"
    parts = []

    parts.append(f"Model: `{RM.MODEL_PATH.relative_to(ROOT)}` ({RM.MODEL_PATH.stat().st_size / 1e6:.2f} MB, "
                 f"{model.n_iter} iterations x {model.n_classes} classes, depth {model.depth})\n")

    # samples, ids stripped
    for name in SAMPLES:
        src = json.loads((ROOT / "input" / f"{name}.json").read_text())["source"]
        stripped, back = strip_ids(src)
        rows = design_rows(stripped, back)
        parts.append(f"### {name} (ids stripped)\n\n" + table(rows, ["id", "type", "font", "text", "rule", "model", "p", "merged", "flag"]) + "\n")

    # Boynton + any requested designs
    for cid in [BOYNTON] + args.design:
        path = ROOT / "eval" / "data" / "designs" / f"{cid}.json"
        if not path.exists():
            parts.append(f"### {cid}: not in eval/data/designs\n")
            continue
        d = json.loads(path.read_text())
        rows = design_rows(d["source"])
        parts.append(f"### {cid} — {d['meta'].get('title')} ({d['meta']['canvas']['width']}x{d['meta']['canvas']['height']})\n\n"
                     + table(rows, ["id", "type", "font", "text", "rule", "model", "p", "merged", "flag"]) + "\n")

    # agreement with the rules over the 450 eval designs
    designs = sorted((ROOT / "eval" / "data" / "designs").glob("*.json"))
    agree = collections.Counter()
    total = collections.Counter()
    pair = collections.Counter()
    changed_designs = 0
    head_agree = head_n = 0
    t_sum = 0.0
    for p in designs:
        src = json.loads(p.read_text())["source"]
        rules = A.analyze(src).roles
        t0 = time.perf_counter()
        probs = RM.predict_proba(src)
        t_sum += time.perf_counter() - t0
        merged = RMG.merged_roles(src, rules, probs=probs, force=True)
        if any(merged[i] != rules[i] for i in rules):
            changed_designs += 1
        texts = [el["id"] for el in src["elements"] if el["type"] == "text"]
        if texts:
            head_n += 1
            rule_head = [i for i in texts if rules.get(i) == "headline"]
            model_head = max(texts, key=lambda i: probs[i]["headline"])
            if rule_head and rule_head[0] == model_head:
                head_agree += 1
        for el in src["elements"]:
            eid = el["id"]
            if el["type"] == "shape":
                continue        # the merge never lets the model touch shapes
            fam = RM.allowed_roles(el["type"])
            best = max(((r, v) for r, v in probs[eid].items() if r in fam), key=lambda t: t[1])[0]
            r = rules.get(eid)
            total[r] += 1
            if best == r:
                agree[r] += 1
            else:
                pair[(r, best)] += 1
    rows = [{"rule role": r, "n": total[r], "model agrees": f"{agree[r] / total[r]:.2f}"} for r in sorted(total, key=lambda r: -total[r])]
    parts.append(f"### Agreement with the rule analyzer on {len(designs)} eval designs, text and image elements "
                 f"(no labels; disagreement is not error)\n\n"
                 + table(rows, ["rule role", "n", "model agrees"]) + "\n")
    parts.append(f"Headline: model's top P(headline) text = rule headline in {head_agree}/{head_n} designs "
                 f"({head_agree / max(1, head_n):.2f}). Merge (force) changes at least one role in "
                 f"{changed_designs}/{len(designs)} designs. Mean predict time {t_sum / len(designs) * 1000:.1f} ms.\n")
    top = [{"rule → model": f"{a} → {b}", "n": n} for (a, b), n in pair.most_common(15)]
    parts.append("Most common disagreements:\n\n" + table(top, ["rule → model", "n"]) + "\n")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts))
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
