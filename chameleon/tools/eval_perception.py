"""Measure S1: how good is the VLM's view of the source, and does the vote help?

    .venv/bin/python tools/eval_perception.py samples                 # three samples, ids stripped
    .venv/bin/python tools/eval_perception.py dac --n 60              # DesignAsCode-labelled Crello designs
    .venv/bin/python tools/eval_perception.py precompute --limit 300  # fill the perception cache for run_eval
    .venv/bin/python tools/eval_perception.py report                  # markdown tables from saved results

Every VLM answer is cached under eval/data/perception/cache (the same
`CHAMELEON_VLM_CACHE_DIR` the eval arms use), so reruns are free. Results go
to eval/data/perception/*.json; `report` prints the tables for
docs/S1_PERCEPTION.md.

Agreement is measured on the engine's coarse classes (engine.perceive.COARSE:
picture / headline / cta / logo / badge / secondary / minor) per analyzer unit,
for five "voters": rules (engine.analyze), classifier (engine.role_model,
argmax inside the type family), VLM (engine.perceive), rules+classifier (S4's
merge via apply_votes without a perception) and rules+classifier+VLM (the
three-voter merge). Hidden-task style: ids are stripped before anything runs.

Dev tool, never shipped.
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "eval" / "data" / "perception"
CACHE_DIR = OUT_DIR / "cache"
os.environ.setdefault("CHAMELEON_VLM_CACHE_DIR", str(CACHE_DIR))
os.environ.setdefault("CHAMELEON_VLM", "1")
if not os.environ.get("CHAMELEON_VLM_MODEL"):
    os.environ["CHAMELEON_VLM_MODEL"] = str(ROOT / "models" / "Qwen3VL-4B-Instruct-Q4_K_M.gguf")
    os.environ["CHAMELEON_VLM_MMPROJ"] = str(ROOT / "models" / "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf")

from engine import analyze as A  # noqa: E402
from engine import perceive as P  # noqa: E402
from engine import render as R  # noqa: E402
from engine import role_merge as RMG  # noqa: E402
from engine import role_model as RM  # noqa: E402
from engine import vlm  # noqa: E402

# the sample ids say what each element is (hidden tasks will not)
KNOWN_BY_ID = [("bg", "background"), ("logo", "logo"), ("headline", "headline"), ("subhead", "subhead"),
               ("cta", "cta"), ("badge", "badge"), ("ribbon", "badge"), ("product", "hero"),
               ("deco", "decorative"), ("legal", "fine_print"), ("watermark", "image")]
VOTERS = ("rules", "classifier", "vlm", "rules+classifier", "all three")
PRIMARY = ("headline", "cta", "logo", "hero")
DAC_DEFAULT = ("/private/tmp/claude-501/-Users-gauravshrivastava-Projects-AdobeHack/"
               "778794fe-3d58-4b6d-91fd-8d0b86308520/scratchpad/dac/dataset.jsonl")


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


def known_roles(source: dict) -> dict[str, str]:
    roles = {}
    for el in source["elements"]:
        for key, role in KNOWN_BY_ID:
            if key in el["id"].lower():
                roles[el["id"]] = role
                break
    return roles


# ---------------------------------------------------------------------------
# the five voters on one design


def voters_for(src: dict, timeout_note: dict | None = None) -> tuple[A.Analysis, dict[str, dict[str, str]], P.Perception]:
    """Per voter: {unit key: fine role} on the stripped design, plus the perception."""
    a = A.analyze(src)
    by_id = {el["id"]: el for el in src["elements"]}
    rules = {u.key: u.role for u in a.units}
    probs = RM.predict_proba(src)
    clf: dict[str, str] = {}
    for u in a.units:
        fam = P.unit_family(u, by_id)
        acc = RMG._unit_probs(u, by_id, probs, fam)
        allowed = RM.allowed_roles(fam)
        best = max(((r, v) for r, v in acc.items() if r in allowed), key=lambda t: t[1], default=None)
        clf[u.key] = best[0] if best else u.role
    R.begin_task()
    t0 = time.perf_counter()
    perception = P.perceive(src, a)
    if timeout_note is not None:
        timeout_note["vlm_s"] = time.perf_counter() - t0
        timeout_note["vlm_status"] = perception.status
    vlm_roles = {u.key: perception.fine.get(u.key, u.role) for u in a.units}
    a2 = A.analyze(src)
    RMG.apply_votes(a2, src, None, probs=probs, model_on=True)
    two = {u.key: u.role for u in a2.units}
    a3 = A.analyze(src)
    RMG.apply_votes(a3, src, perception, probs=probs, model_on=True)
    three = {u.key: u.role for u in a3.units}
    return a, {"rules": rules, "classifier": clf, "vlm": vlm_roles, "rules+classifier": two, "all three": three}, perception


def unit_truth(a: A.Analysis, truth: dict[str, str], by_id: dict[str, dict]) -> dict[str, str]:
    """Ground-truth role per unit: the label of the members that name the unit
    (text members of a text unit, images of an image unit), majority."""
    out = {}
    for u in a.units:
        fam = P.unit_family(u, by_id)
        members = [i for i in u.ids if by_id[i]["type"] == fam] or list(u.ids)
        labels = [truth[i] for i in members if truth.get(i)]
        if labels:
            out[u.key] = collections.Counter(labels).most_common(1)[0][0]
    return out


def score_design(a: A.Analysis, votes: dict[str, dict[str, str]], truth_u: dict[str, str],
                 by_id: dict[str, dict]) -> dict[str, Any]:
    """Per voter: coarse hits per class and the primary-role top-1 flags."""
    rec: dict[str, Any] = {"n_units": len(truth_u), "voters": {}}
    for name, roles in votes.items():
        hits = collections.Counter()
        total = collections.Counter()
        exact = 0
        for key, t in truth_u.items():
            tc = P.coarse_of(t)
            got = P.coarse_of(roles.get(key))
            total[tc] += 1
            hits[tc] += got == tc
            exact += roles.get(key) == t
        prim = {}
        for role in PRIMARY:
            truth_keys = [k for k, t in truth_u.items() if t == role]
            if not truth_keys:
                continue
            mine = [k for k, r in roles.items() if r == role and k in truth_u]
            prim[role] = bool(mine) and mine[0] in truth_keys
        rec["voters"][name] = {"hits": dict(hits), "total": dict(total), "exact": exact, "primary": prim}
    return rec


# ---------------------------------------------------------------------------
# samples


def run_samples(out: Path) -> dict[str, Any]:
    results = {"designs": []}
    for f in sorted((ROOT / "input").glob("*.json")):
        task = json.loads(f.read_text())
        src = task["source"]
        stripped, back = strip_ids(src)
        truth = {new: known_roles(src).get(old) for new, old in back.items()}
        note: dict[str, Any] = {}
        a, votes, perception = voters_for(stripped, note)
        by_id = {el["id"]: el for el in stripped["elements"]}
        truth_u = unit_truth(a, truth, by_id)
        rec = score_design(a, votes, truth_u, by_id)
        rec.update({"id": f.stem, "archetype": perception.archetype, "importance": perception.importance, **note,
                    "units": [{"key": u.key, "orig": [back[i] for i in u.ids], "truth": truth_u.get(u.key),
                               **{v: votes[v].get(u.key) for v in VOTERS},
                               "vlm_conf": round(perception.roles.get(u.key, ("", 0.0))[1], 2)} for u in a.units]})
        results["designs"].append(rec)
        print(f"{f.stem}: vlm {perception.status} {note.get('vlm_s', 0):.1f}s archetype={perception.archetype}")
        for u in rec["units"]:
            print("   %-18s truth=%-11s rules=%-11s clf=%-11s vlm=%-11s two=%-11s three=%s" % (
                "/".join(u["orig"])[:18], u["truth"], u["rules"], u["classifier"], u["vlm"], u["rules+classifier"], u["all three"]))
    out.mkdir(parents=True, exist_ok=True)
    (out / "samples.json").write_text(json.dumps(results, indent=1))
    return results


# ---------------------------------------------------------------------------
# DesignAsCode-labelled Crello designs


def dac_designs(dac_path: Path, n: int, seed: int, shards: str) -> list[dict[str, Any]]:
    from eval.crello_convert import SkipTemplate, convert_template, detect_angle_unit, load_raw
    from tools.build_role_dataset import load_dac, retype_logo_shapes
    from tools.role_labels import label_design

    dac = load_dac(dac_path)
    paths = sorted((ROOT / "eval" / "data" / "raw").glob(shards))
    rows = load_raw(paths)
    unit = detect_angle_unit(rows)
    rng = random.Random(seed)
    rng.shuffle(rows)
    out = []
    for r in rows:
        cid = str(r.get("id"))
        if cid not in dac:
            continue
        try:
            d = convert_template(r, angle_unit=unit, max_elements=14)
        except SkipTemplate:
            continue
        src = d["source"]
        n_content = sum(1 for e in src["elements"] if e["type"] != "image"
                        or e["width"] * e["height"] < 0.9 * src["canvas"]["width"] * src["canvas"]["height"])
        if n_content < 3:
            continue
        retype_logo_shapes(src, dac[cid])
        roles, ranks, raw = label_design(src, dac[cid])
        labelled = sum(1 for v in roles.values() if v)
        if labelled < max(3, 0.6 * len(src["elements"])):
            continue
        out.append({"id": cid, "title": d.get("meta", {}).get("title", ""), "source": src, "truth": roles})
        if len(out) >= n:
            break
    return out


def run_dac(out: Path, n: int, seed: int, dac_path: Path, shards: str) -> dict[str, Any]:
    designs = dac_designs(dac_path, n, seed, shards)
    print(f"{len(designs)} labelled designs")
    results: dict[str, Any] = {"designs": [], "n": len(designs)}
    for k, d in enumerate(designs):
        stripped, back = strip_ids(d["source"])
        truth = {new: d["truth"].get(old, "") for new, old in back.items()}
        note: dict[str, Any] = {}
        a, votes, perception = voters_for(stripped, note)
        by_id = {el["id"]: el for el in stripped["elements"]}
        truth_u = unit_truth(a, truth, by_id)
        rec = score_design(a, votes, truth_u, by_id)
        rec.update({"id": d["id"], "title": d["title"], "archetype": perception.archetype, **note,
                    "units": [{"key": u.key, "truth": truth_u.get(u.key),
                               **{v: votes[v].get(u.key) for v in VOTERS}} for u in a.units]})
        results["designs"].append(rec)
        print(f"[{k + 1}/{len(designs)}] {d['id']} {d['title'][:30]!r}: {len(a.units)} units, vlm {perception.status} "
              f"{note.get('vlm_s', 0):.1f}s, archetype={perception.archetype}, exact rules {rec['voters']['rules']['exact']} "
              f"vlm {rec['voters']['vlm']['exact']} three {rec['voters']['all three']['exact']} / {rec['n_units']}", flush=True)
        out.mkdir(parents=True, exist_ok=True)
        (out / "dac.json").write_text(json.dumps(results, indent=1))
    return results


# ---------------------------------------------------------------------------
# precompute for the eval harness


def run_precompute(out: Path, limit: int) -> dict[str, Any]:
    index = json.loads((ROOT / "eval" / "data" / "index.json").read_text())[:limit]
    files = [ROOT / "eval" / "data" / "designs" / f"{d['id']}.json" for d in index]
    files += sorted((ROOT / "input").glob("*.json"))
    rows = []
    for k, f in enumerate(files):
        doc = json.loads(f.read_text())
        src = doc["source"] if "source" in doc else doc
        a = A.analyze(src)
        R.begin_task()
        t0 = time.perf_counter()
        p = P.perceive(src, a)
        dt = time.perf_counter() - t0
        last = vlm.stats()["last"]
        rows.append({"id": f.stem, "status": p.status, "s": round(dt, 2), "archetype": p.archetype,
                     "n_units": len(a.units), "prefill_s": last.get("prefill_s"), "gen_s": last.get("gen_s"),
                     "gen_tokens": last.get("gen_tokens"), "changed_coarse": sum(
                         1 for u in a.units if u.key in p.roles and p.roles[u.key][0] != P.coarse_of(u.role))})
        print(f"[{k + 1}/{len(files)}] {f.stem} {p.status} {dt:.1f}s archetype={p.archetype} "
              f"units={len(a.units)} disagree={rows[-1]['changed_coarse']}", flush=True)
        out.mkdir(parents=True, exist_ok=True)
        (out / "precompute.json").write_text(json.dumps({"rows": rows, "vlm": vlm.status(), "stats": vlm.stats()}, indent=1))
    return {"rows": rows}


# ---------------------------------------------------------------------------
# report


def _table(rows: list[list[Any]], header: list[str]) -> str:
    L = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        L.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(L)


def agreement_tables(results: dict[str, Any], title: str) -> str:
    designs = results["designs"]
    L = [f"### {title} ({len(designs)} designs, {sum(d['n_units'] for d in designs)} labelled units)\n"]
    classes = sorted({c for d in designs for v in d["voters"].values() for c in v["total"]},
                     key=lambda c: -sum(d["voters"]["rules"]["total"].get(c, 0) for d in designs))
    rows = []
    for name in VOTERS:
        hits = collections.Counter()
        total = collections.Counter()
        exact = 0
        n_units = 0
        for d in designs:
            v = d["voters"].get(name)
            if not v:
                continue
            hits.update(v["hits"])
            total.update(v["total"])
            exact += v["exact"]
            n_units += d["n_units"]
        row = [name, f"{sum(hits.values()) / max(1, sum(total.values())):.3f}", f"{exact / max(1, n_units):.3f}"]
        for c in classes:
            row.append(f"{hits[c]}/{total[c]}" if total[c] else "-")
        rows.append(row)
    L.append(_table(rows, ["voter", "coarse agreement", "exact", *classes]))
    L.append("")
    rows = []
    for name in VOTERS:
        row = [name]
        for role in PRIMARY:
            have = [d["voters"][name]["primary"][role] for d in designs if role in d["voters"][name].get("primary", {})]
            row.append(f"{sum(have)}/{len(have)}" if have else "-")
        rows.append(row)
    L.append("Primary roles: the unit the voter names X is the labelled X (designs with a labelled X):\n")
    L.append(_table(rows, ["voter", *PRIMARY]))
    arche = collections.Counter(d.get("archetype") for d in designs)
    status = collections.Counter(d.get("vlm_status") for d in designs)
    times = [d["vlm_s"] for d in designs if d.get("vlm_s") is not None and d.get("vlm_status") == "ok"]
    L.append("")
    L.append(f"VLM status: {dict(status)}; archetypes: {dict(arche)}"
             + (f"; uncached call time p50 {statistics.median(times):.1f}s, max {max(times):.1f}s" if times else ""))
    return "\n".join(L)


def precompute_table(pre: dict[str, Any]) -> str:
    rows = pre["rows"]
    ok = [r for r in rows if r["status"] == "ok"]
    times = sorted(r["s"] for r in ok)
    L = [f"### Perception over {len(rows)} designs (eval subset + samples)\n"]
    status = collections.Counter(r["status"] for r in rows)
    L.append(f"status: {dict(status)}; archetypes: {dict(collections.Counter(r['archetype'] for r in rows))}")
    if times:
        p = lambda q: times[max(0, min(len(times) - 1, int(round(q * (len(times) - 1)))))]
        L.append(f"call time (native, uncached): p50 {p(0.5):.1f}s, p95 {p(0.95):.1f}s, max {times[-1]:.1f}s; "
                 f"units per design p50 {statistics.median(r['n_units'] for r in ok):.0f}; "
                 f"coarse disagreements with the rules per design: mean {statistics.fmean(r['changed_coarse'] for r in ok):.2f}, "
                 f"designs with any {sum(1 for r in ok if r['changed_coarse']) / len(ok):.0%}")
    return "\n".join(L)


def report(out: Path) -> str:
    parts = []
    if (out / "samples.json").exists():
        parts.append(agreement_tables(json.loads((out / "samples.json").read_text()), "Three samples, ids stripped"))
    if (out / "dac.json").exists():
        parts.append(agreement_tables(json.loads((out / "dac.json").read_text()), "DesignAsCode-labelled Crello designs, ids stripped"))
    if (out / "precompute.json").exists():
        parts.append(precompute_table(json.loads((out / "precompute.json").read_text())))
    text = "\n\n".join(parts)
    (out / "report.md").write_text(text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["samples", "dac", "precompute", "report"])
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--dac", default=DAC_DEFAULT)
    ap.add_argument("--shards", default="train-0000[0-2].parquet")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args(argv)
    out = Path(args.out)
    if args.cmd == "samples":
        run_samples(out)
    elif args.cmd == "dac":
        run_dac(out, args.n, args.seed, Path(args.dac), args.shards)
    elif args.cmd == "precompute":
        run_precompute(out, args.limit)
    print()
    print(report(out))
    print("vlm:", vlm.status(), json.dumps({k: v for k, v in vlm.stats().items() if k != "last"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
