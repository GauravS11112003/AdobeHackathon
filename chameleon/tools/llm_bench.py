"""Bench the text-only LLM reading (engine/llm.py, workstream S6).

    .venv/bin/python tools/llm_bench.py roles   [--models qwen3-1.7b,qwen3-4b,gemma3-4b] [--n 60]
    .venv/bin/python tools/llm_bench.py groups  [--models ...]        # designer-reference designs (+ latency)
    .venv/bin/python tools/llm_bench.py report                         # markdown tables from the saved results

roles   the 60 DesignAsCode-labelled Crello designs S1 used (seeded, ids
        stripped): coarse / exact agreement per analyzer unit for the voters
        rules, classifier, llm, rules+classifier, rules+llm, all three (the
        LLM takes the VLM's seat in role_merge.vote_roles), primary-role
        top-1, JSON validity, self-consistency (one headline, <= 1 hero /
        logo / cta), latency.
groups  the designer-reference designs (docs/designer*/out, 60 designs x 12
        formats): for every LLM group (and, as baselines, every schema group,
        every multi-element analyzer unit and random content pairs) the share
        of reference formats in which the designer kept the members together
        (`kept`: the members stay a connected cluster at a gap threshold of
        max(1.5 x the source's own connecting gap, 2 % of the canvas
        diagonal)); latency p50 / p95 on the same designs (eval designs, 4-25
        elements) and the plan prior's distribution.

Every answer is cached under eval/data/llm_bench/cache (CHAMELEON_LLM_CACHE_DIR,
keyed by source hash + prompt version + model), so reruns are free and the
wiring eval reuses them. Results: eval/data/llm_bench/<model>/{roles,groups}.json.
Dev tool, never shipped.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "eval" / "data" / "llm_bench"
CACHE_DIR = OUT_DIR / "cache"
os.environ.setdefault("CHAMELEON_LLM_CACHE_DIR", str(CACHE_DIR))
os.environ["CHAMELEON_LLM"] = "1"

from tools import eval_perception as EP  # noqa: E402  (strip_ids, unit_truth, score_design, dac_designs)

os.environ["CHAMELEON_VLM"] = "0"          # eval_perception defaults the VLM on; never here

from engine import analyze as A  # noqa: E402
from engine import llm  # noqa: E402
from engine import perceive as P  # noqa: E402
from engine import role_merge as RMG  # noqa: E402
from engine import role_model as RM  # noqa: E402
from engine.geometry import Box  # noqa: E402

MODELS = {
    "qwen3-1.7b": ("Qwen3-1.7B-Q4_K_M.gguf", "unsloth/Qwen3-1.7B-GGUF"),
    "qwen3-4b": ("Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "unsloth/Qwen3-4B-Instruct-2507-GGUF"),
    "gemma3-4b": ("gemma-3-4b-it-Q4_K_M.gguf", "ggml-org/gemma-3-4b-it-GGUF"),
}
VOTERS = ("rules", "classifier", "llm", "rules+classifier", "rules+llm", "all three")
PRIMARY = ("headline", "cta", "logo", "hero")
BENCH_BUDGET_S = 180.0
KEPT_GROW = 1.5          # a group is kept when its members connect at 1.5 x the source's connecting gap ...
KEPT_MIN_FRAC = 0.02     # ... or 2 % of the canvas diagonal, whichever is larger
ADJACENT_FRAC = 0.03     # stricter, absolute: the members connect within 3 % of the reference diagonal
RANDOM_PAIRS = 8


def use_model(tag: str) -> None:
    name = MODELS[tag][0]
    os.environ["CHAMELEON_LLM_MODEL"] = str(ROOT / "models" / name)
    llm._reset_for_tests()


def _p(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))] if s else float("nan")


def call(src: dict, a: A.Analysis) -> tuple[llm.Reading, dict[str, Any]]:
    t0 = time.perf_counter()
    r = llm.read(src, a, budget=BENCH_BUDGET_S)
    dt = time.perf_counter() - t0
    last = dict(llm._state["last"])
    note = {"status": r.status, "s": round(dt, 3), "cached": bool(last.get("cached")),
            "prefill_s": last.get("prefill_s"), "gen_s": last.get("gen_s"), "gen_tokens": last.get("gen_tokens"),
            "prompt_tokens": last.get("prompt_tokens"), "n_elements": len(src["elements"])}
    return r, note


def self_consistent(src: dict, r: llm.Reading) -> dict[str, bool]:
    by_type = collections.defaultdict(list)
    for el in src["elements"]:
        role = r.element_roles.get(el["id"])
        if role:
            by_type[el["type"]].append(role)
    texts = by_type.get("text", [])
    images = by_type.get("image", [])
    return {"one_headline": texts.count("headline") == 1 if texts else True,
            "le1_cta": texts.count("cta") <= 1, "le1_hero": images.count("hero") <= 1,
            "le1_logo": images.count("logo") <= 1}


# ---------------------------------------------------------------------------
# roles on the DesignAsCode-labelled designs


def voters_for(src: dict, r: llm.Reading) -> tuple[A.Analysis, dict[str, dict[str, str]]]:
    a = A.analyze(src)
    by_id = {el["id"]: el for el in src["elements"]}
    rules = {u.key: u.role for u in a.units}
    probs = RM.predict_proba(src)
    clf: dict[str, str] = {}
    for u in a.units:
        fam = P.unit_family(u, by_id)
        acc = RMG._unit_probs(u, by_id, probs, fam)
        allowed = RM.allowed_roles(fam)
        best = max(((ro, v) for ro, v in acc.items() if ro in allowed), key=lambda t: t[1], default=None)
        clf[u.key] = best[0] if best else u.role
    mine = {u.key: r.fine.get(u.key, u.role) for u in a.units}
    perception = r.perception() if r else None
    a2 = A.analyze(src)
    RMG.apply_votes(a2, src, None, probs=probs, model_on=True)
    a3 = A.analyze(src)
    RMG.apply_votes(a3, src, perception, probs=None, model_on=False)
    a4 = A.analyze(src)
    RMG.apply_votes(a4, src, perception, probs=probs, model_on=True)
    return a, {"rules": rules, "classifier": clf, "llm": mine,
               "rules+classifier": {u.key: u.role for u in a2.units},
               "rules+llm": {u.key: u.role for u in a3.units},
               "all three": {u.key: u.role for u in a4.units}}


def run_roles(tag: str, n: int, seed: int, dac: Path, shards: str) -> dict[str, Any]:
    use_model(tag)
    designs = EP.dac_designs(dac, n, seed, shards)
    print(f"[{tag}] {len(designs)} labelled designs", flush=True)
    results: dict[str, Any] = {"model": tag, "designs": [], "n": len(designs)}
    for k, d in enumerate(designs):
        stripped, back = EP.strip_ids(d["source"])
        truth = {new: d["truth"].get(old, "") for new, old in back.items()}
        a0 = A.analyze(stripped)
        r, note = call(stripped, a0)
        a, votes = voters_for(stripped, r)
        by_id = {el["id"]: el for el in stripped["elements"]}
        truth_u = EP.unit_truth(a, truth, by_id)
        rec = EP.score_design(a, votes, truth_u, by_id)
        rec.update({"id": d["id"], "title": d["title"], "archetype": r.archetype, "focal": r.focal,
                    "consistent": self_consistent(stripped, r), "groups": [[ids, why] for ids, why in r.groups],
                    "plans": r.plans, **note,
                    "units": [{"key": u.key, "truth": truth_u.get(u.key), **{v: votes[v].get(u.key) for v in VOTERS}}
                              for u in a.units]})
        results["designs"].append(rec)
        print(f"[{tag} {k + 1}/{len(designs)}] {d['id']} {d['title'][:28]!r}: {len(a.units)} units, {r.status} "
              f"{note['s']:.1f}s, exact rules {rec['voters']['rules']['exact']} llm {rec['voters']['llm']['exact']} "
              f"three {rec['voters']['all three']['exact']} / {rec['n_units']}", flush=True)
        out = OUT_DIR / tag
        out.mkdir(parents=True, exist_ok=True)
        (out / "roles.json").write_text(json.dumps(results, indent=1))
    return results


# ---------------------------------------------------------------------------
# groups and latency on the designer-reference designs


def _gap(a: Box, b: Box) -> float:
    dx = max(b.x - a.right, a.x - b.right, 0.0)
    dy = max(b.y - a.bottom, a.y - b.bottom, 0.0)
    return max(dx, dy)


def connecting_gap(boxes: list[Box]) -> float:
    """The smallest threshold at which the boxes form one cluster (max edge
    of the minimum spanning tree on pairwise gaps)."""
    if len(boxes) < 2:
        return 0.0
    n = len(boxes)
    in_tree = [False] * n
    best = [math.inf] * n
    best[0] = 0.0
    worst = 0.0
    for _ in range(n):
        i = min((k for k in range(n) if not in_tree[k]), key=lambda k: best[k])
        in_tree[i] = True
        worst = max(worst, best[i])
        for j in range(n):
            if not in_tree[j]:
                best[j] = min(best[j], _gap(boxes[i], boxes[j]))
    return worst


def kept_in(ids: list[str], source: dict, ref: dict) -> tuple[bool, bool] | None:
    """Did the designer keep these elements together in `ref`? (kept: the
    members connect within 1.5 x their source gap or 2 % of the diagonal;
    adjacent: within 3 % of the diagonal, whatever the source). None when
    fewer than two members are drawn in the reference."""
    sb = {el["id"]: Box.of(el) for el in source["elements"]}
    rb = {el["id"]: Box.of(el) for el in ref["elements"]}
    ids = [i for i in ids if i in sb and i in rb]
    if len(ids) < 2:
        return None
    sw, sh = float(source["canvas"]["width"]), float(source["canvas"]["height"])
    rw, rh = float(ref["canvas"]["width"]), float(ref["canvas"]["height"])
    sd, rd = math.hypot(sw, sh), math.hypot(rw, rh)
    g_src = connecting_gap([sb[i] for i in ids])
    tau = max(KEPT_GROW * g_src * rd / sd, KEPT_MIN_FRAC * rd)
    g_ref = connecting_gap([rb[i] for i in ids])
    return g_ref <= tau + 1e-6, g_ref <= ADJACENT_FRAC * rd + 1e-6


def designer_designs() -> list[dict[str, Any]]:
    from eval.perturb_designer import references

    by_name: dict[str, dict[str, Any]] = {}
    for ref in references():
        d = by_name.setdefault(ref.name, {"id": ref.name, "batch": ref.batch, "holdout": ref.holdout,
                                          "source": ref.source, "refs": []})
        d["refs"].append({"size": f"{ref.W}x{ref.H}", "design": ref.design})
    return sorted(by_name.values(), key=lambda d: d["id"])


def group_sets(src: dict, a: A.Analysis, r: llm.Reading, rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    content = [el["id"] for el in src["elements"] if a.roles.get(el["id"]) not in ("background", "decorative")]
    schema: dict[str, list[str]] = {}
    for el in src["elements"]:
        if el.get("group_id"):
            schema.setdefault(str(el["group_id"]), []).append(el["id"])
    units = {u.key: list(u.ids) for u in a.units if len(u.ids) > 1 and u.role != "background"}
    unit_of = dict(a.element_unit)
    out: dict[str, list[dict[str, Any]]] = {
        "llm": [{"ids": ids, "why": why, "novel": len({unit_of.get(i) for i in ids}) > 1,
                 "crosses_zone": any(a.roles.get(i) in ("background", "panel") for i in ids)}
                for ids, why in r.groups],
        "schema": [{"ids": ids} for ids in schema.values()],
        "analyzer": [{"ids": ids, "kind": a.unit(k).kind} for k, ids in units.items()
                     if not any(set(ids) == set(g) for g in schema.values())],
        "random": [],
    }
    pool = [i for i in content]
    seen: set[tuple[str, str]] = set()
    tries = 0
    while len(out["random"]) < RANDOM_PAIRS and len(pool) >= 2 and tries < 200:
        tries += 1
        x, y = rng.sample(pool, 2)
        key = tuple(sorted((x, y)))
        if key in seen or unit_of.get(x) == unit_of.get(y):
            continue
        seen.add(key)
        out["random"].append({"ids": [x, y]})
    return out


def run_groups(tag: str, limit: int) -> dict[str, Any]:
    use_model(tag)
    designs = designer_designs()
    if limit:
        designs = designs[:limit]
    print(f"[{tag}] {len(designs)} designer designs", flush=True)
    rng = random.Random(0)
    results: dict[str, Any] = {"model": tag, "designs": []}
    for k, d in enumerate(designs):
        src = d["source"]
        a = A.analyze(src)
        r, note = call(src, a)
        sets = group_sets(src, a, r, rng) if r.status in ("ok", "cached") else group_sets(src, a, llm.Reading(), rng)
        for kind, groups in sets.items():
            for g in groups:
                res = [kept_in(g["ids"], src, ref["design"]) for ref in d["refs"]]
                res = [x for x in res if x is not None]
                g["kept"] = round(sum(k for k, _ in res) / len(res), 3) if res else None
                g["adjacent"] = round(sum(a for _, a in res) / len(res), 3) if res else None
                g["n_formats"] = len(res)
                sg = connecting_gap([Box.of(el) for el in src["elements"] if el["id"] in g["ids"]])
                g["src_gap_frac"] = round(sg / math.hypot(float(src["canvas"]["width"]), float(src["canvas"]["height"])), 4)
        rec = {"id": d["id"], "batch": d["batch"], "holdout": d["holdout"], "n_refs": len(d["refs"]),
               "archetype": r.archetype, "focal": r.focal, "plans": r.plans, "importance": r.importance,
               "consistent": self_consistent(src, r), "sets": sets, **note,
               "roles_changed": sum(1 for u in a.units if u.key in r.fine and P.coarse_of(r.fine[u.key]) != P.coarse_of(u.role))}
        results["designs"].append(rec)
        print(f"[{tag} {k + 1}/{len(designs)}] {d['id'][:12]} {note['n_elements']} el, {r.status} {note['s']:.1f}s "
              f"(prefill {note.get('prefill_s') or 0:.1f} gen {note.get('gen_s') or 0:.1f}), llm groups "
              f"{len(sets['llm'])} kept {[g['kept'] for g in sets['llm']]}", flush=True)
        out = OUT_DIR / tag
        out.mkdir(parents=True, exist_ok=True)
        (out / "groups.json").write_text(json.dumps(results, indent=1))
    return results


# ---------------------------------------------------------------------------
# report


def _table(rows: list[list[Any]], header: list[str]) -> str:
    L = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        L.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(L)


def latency_rows(tag: str, rows: list[dict[str, Any]]) -> list[Any]:
    fresh = [r for r in rows if not r.get("cached") and r.get("status") == "ok"]
    times = [r["s"] for r in fresh]
    if not times:
        return [tag, len(rows), "-", "-", "-", "-", "-", "-", "-"]
    first = fresh[0]["s"]
    rest = times[1:] or times
    return [tag, len(rows), f"{_p(rest, 0.5):.1f}", f"{_p(rest, 0.95):.1f}", f"{max(rest):.1f}", f"{first:.1f}",
            f"{statistics.median(r['prefill_s'] or 0 for r in fresh):.1f} / {statistics.median(r['gen_s'] or 0 for r in fresh):.1f}",
            f"{statistics.median(r['gen_tokens'] or 0 for r in fresh):.0f}",
            f"{statistics.median(r['n_elements'] for r in fresh):.0f}"]


def roles_report(tag: str, res: dict[str, Any]) -> tuple[str, dict[str, float]]:
    designs = res["designs"]
    L = [f"### {tag}: roles on {len(designs)} DesignAsCode designs, ids stripped ({sum(d['n_units'] for d in designs)} labelled units)\n"]
    classes = sorted({c for d in designs for v in d["voters"].values() for c in v["total"]},
                     key=lambda c: -sum(d["voters"]["rules"]["total"].get(c, 0) for d in designs))
    rows = []
    per_class: dict[str, float] = {}
    for name in VOTERS:
        hits = collections.Counter()
        total = collections.Counter()
        exact = n_units = 0
        for d in designs:
            v = d["voters"][name]
            hits.update(v["hits"])
            total.update(v["total"])
            exact += v["exact"]
            n_units += d["n_units"]
        row = [name, f"{sum(hits.values()) / max(1, sum(total.values())):.3f}", f"{exact / max(1, n_units):.3f}"]
        for c in classes:
            row.append(f"{hits[c]}/{total[c]}" if total[c] else "-")
            if name == "llm" and total[c]:
                per_class[c] = round(hits[c] / total[c], 3)
        rows.append(row)
    L.append(_table(rows, ["voter", "coarse", "exact", *classes]))
    L.append("")
    rows = []
    for name in VOTERS:
        row = [name]
        for role in PRIMARY:
            have = [d["voters"][name]["primary"][role] for d in designs if role in d["voters"][name].get("primary", {})]
            row.append(f"{sum(have)}/{len(have)}" if have else "-")
        rows.append(row)
    L.append("Primary roles, top-1 (the unit the voter names X is the labelled X):\n")
    L.append(_table(rows, ["voter", *PRIMARY]))
    ok = sum(1 for d in designs if d["status"] in ("ok", "cached"))
    cons = collections.Counter()
    for d in designs:
        for k, v in (d.get("consistent") or {}).items():
            cons[k] += bool(v)
    L.append("")
    L.append(f"valid JSON {ok}/{len(designs)}; self-consistent: " + ", ".join(f"{k} {v}/{len(designs)}" for k, v in sorted(cons.items()))
             + f"; archetypes {dict(collections.Counter(d.get('archetype') for d in designs))}"
             + f"; focal {dict(collections.Counter(d.get('focal') for d in designs))}")
    return "\n".join(L), per_class


def groups_report(tag: str, res: dict[str, Any]) -> str:
    designs = res["designs"]
    L = [f"### {tag}: groups on {len(designs)} designer-reference designs ({sum(d['n_refs'] for d in designs)} reference layouts)\n"]
    rows = []
    for kind, label in (("llm", "LLM groups"), ("llm-novel", "LLM groups beyond the analyzer's units"),
                        ("schema", "schema group_id groups"), ("analyzer", "analyzer units (holder / host / row)"),
                        ("random", "random content pairs (not one unit)")):
        gs = []
        for d in designs:
            src_kind = "llm" if kind == "llm-novel" else kind
            for g in d["sets"].get(src_kind, []):
                if kind == "llm-novel" and not g.get("novel"):
                    continue
                if g.get("kept") is not None:
                    gs.append(g)
        if not gs:
            rows.append([label, 0, "-", "-", "-"])
            continue
        kept = [g["kept"] for g in gs]
        adj = [g["adjacent"] for g in gs if g.get("adjacent") is not None]
        rows.append([label, len(gs), f"{statistics.fmean(kept):.3f}", f"{sum(k >= 0.8 for k in kept) / len(kept):.2f}",
                     f"{statistics.fmean(adj):.3f}" if adj else "-", f"{sum(a >= 0.8 for a in adj) / len(adj):.2f}" if adj else "-",
                     f"{statistics.fmean(g.get('src_gap_frac', 0.0) for g in gs):.3f}",
                     f"{statistics.fmean(len(g['ids']) for g in gs):.1f}"])
    L.append(_table(rows, ["set", "groups", "kept, mean share of formats", "kept in >= 80 %", "adjacent (<= 3 % diag), mean",
                           "adjacent in >= 80 %", "source gap (frac of diag)", "members"]))
    why = collections.Counter(g.get("why") for d in designs for g in d["sets"].get("llm", []))
    cross = sum(1 for d in designs for g in d["sets"].get("llm", []) if g.get("crosses_zone"))
    per_design = [len(d["sets"].get("llm", [])) for d in designs]
    L.append("")
    L.append(f"LLM groups per design: mean {statistics.fmean(per_design):.2f}, designs with none {sum(1 for n in per_design if n == 0)}; "
             f"reasons {dict(why.most_common())}; groups touching a background / panel (rejected by the wiring) {cross}")
    plans = collections.Counter()
    for d in designs:
        for f, p in (d.get("plans") or {}).items():
            for k, v in p.items():
                plans[f"{f}.{k}={v}"] += 1
    L.append(f"plan prior: {dict(sorted(plans.items()))}")
    L.append(f"archetypes {dict(collections.Counter(d.get('archetype') for d in designs))}; focal {dict(collections.Counter(d.get('focal') for d in designs))}; "
             f"coarse roles changed vs rules per design: mean {statistics.fmean(d['roles_changed'] for d in designs):.2f}")
    return "\n".join(L)


def report(tags: list[str]) -> str:
    parts = []
    lat_rows = []
    per_class_all = {}
    for tag in tags:
        d = OUT_DIR / tag
        if (d / "roles.json").exists():
            txt, pc = roles_report(tag, json.loads((d / "roles.json").read_text()))
            parts.append(txt)
            per_class_all[tag] = pc
        if (d / "groups.json").exists():
            res = json.loads((d / "groups.json").read_text())
            parts.append(groups_report(tag, res))
            lat_rows.append(latency_rows(tag, res["designs"]))
        if (d / "roles.json").exists():
            res = json.loads((d / "roles.json").read_text())
            row = latency_rows(tag + " (DaC designs)", res["designs"])
            lat_rows.append(row)
    if lat_rows:
        parts.insert(0, "### Latency (native, CPU, 8 threads, uncached calls; first call includes the system-prompt prefill)\n\n"
                     + _table(lat_rows, ["model / set", "designs", "p50 s", "p95 s", "max s", "first call s",
                                         "prefill / gen p50 s", "gen tokens p50", "elements p50"]))
    if per_class_all:
        parts.append("### LLM per-class coarse accuracy (BASE_CONF candidates)\n\n```\n" + json.dumps(per_class_all, indent=1) + "\n```")
    text = "\n\n".join(parts)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.md").write_text(text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["roles", "groups", "report"])
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dac", default=EP.DAC_DEFAULT)
    ap.add_argument("--shards", default="train-0000[0-2].parquet")
    args = ap.parse_args(argv)
    tags = [t for t in args.models.split(",") if t]
    for tag in tags:
        if tag not in MODELS:
            ap.error(f"unknown model {tag}; known: {', '.join(MODELS)}")
    if args.cmd == "roles":
        for tag in tags:
            run_roles(tag, args.n, args.seed, Path(args.dac), args.shards)
    elif args.cmd == "groups":
        for tag in tags:
            run_groups(tag, args.limit)
    print()
    print(report(tags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
