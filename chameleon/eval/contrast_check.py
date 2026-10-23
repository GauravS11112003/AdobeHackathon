"""Validate the no-render contrast estimate against the render-based check.

    .venv/bin/python -m eval.contrast_check --run v2 --cases 300 [--seed 1]

Takes `--cases` random cases of an eval run (their winner JSON in
<run>/outputs/ plus the source design of every sampled case), computes for
every text element

  * the JSON estimate (engine/contrast.py: layers composited under the painted
    box at a 32x8 grid, 25th percentile WCAG ratio), and
  * the render-based ratio the v2 scorer used (text colour against the mean
    colour of a text-less render under the painted box),

and reports Pearson / Spearman correlation of log ratios, the share of
elements whose readable / unreadable verdict differs under a common
threshold, and the agreement of the hard-fail "drop" rule (ratio < 3 and
< 0.5 x the source's own ratio) between the two measurements. Writes a JSON
summary next to the run (contrast_check.json) and prints it.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR  # noqa: E402
from eval.run_eval import RUNS_DIR, _design_path, _load_source, read_results  # noqa: E402


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="v2")
    ap.add_argument("--cases", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    a = ap.parse_args(argv)
    from engine import contrast as C
    from engine.analyze import CTA, HEADLINE, analyze
    from engine.render import begin_task, render_design
    from engine.score import _contrast_pixels, _ink_boxes
    from engine.textfit import default_measurer
    from eval.metrics import spearman

    run_dir = Path(a.run) if Path(a.run).exists() else RUNS_DIR / a.run
    rows = [r for r in read_results(run_dir) if not r.get("error")]
    index = {d["id"]: d for d in json.loads((Path(a.data_dir) / "index.json").read_text())}
    rnd = random.Random(a.seed)
    rnd.shuffle(rows)
    m = default_measurer()
    est_all: list[float] = []
    px_all: list[float] = []
    roles_all: list[str] = []
    drop_est: list[bool] = []
    drop_px: list[bool] = []
    t_est = t_px = 0.0
    n_cases = n_el = 0
    for r in rows:
        if n_cases >= a.cases:
            break
        meta = index.get(r["design_id"])
        src_path = _design_path(meta, Path(a.data_dir)) if meta else ROOT / "input" / f"{r['design_id']}.json"
        out_path = run_dir / "outputs" / (r["key"].replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-") + ".json")
        if not src_path.exists() or not out_path.exists():
            continue
        source = _load_source(src_path)
        output = json.loads(out_path.read_text())
        analysis = analyze(source)
        pairs = []
        for design in (source, output):
            ink = _ink_boxes(design["elements"], m)
            t0 = time.perf_counter()
            est = C.estimate(design, ink)
            t_est += time.perf_counter() - t0
            t0 = time.perf_counter()
            begin_task()
            img = render_design(design, with_text=False)
            if img is None:
                continue
            px, _ = _contrast_pixels(design["elements"], design, img, m)
            t_px += time.perf_counter() - t0
            pairs.append(({k: v.ratio for k, v in est.items()}, px))
        if len(pairs) != 2:
            continue
        (s_est, s_px), (o_est, o_px) = pairs
        for eid in o_est:
            if eid not in o_px:
                continue
            est_all.append(o_est[eid])
            px_all.append(o_px[eid])
            roles_all.append(analysis.roles.get(eid, ""))
            n_el += 1
            if analysis.roles.get(eid) in (HEADLINE, CTA):
                drop_est.append(o_est[eid] < 3.0 and o_est[eid] < 0.5 * s_est.get(eid, 1e9))
                drop_px.append(o_px[eid] < 3.0 and o_px[eid] < 0.5 * s_px.get(eid, 1e9))
        n_cases += 1
    if not est_all:
        raise SystemExit("no comparable elements (renderer unavailable?)")
    le, lp = [math.log(max(x, 1.0)) for x in est_all], [math.log(max(x, 1.0)) for x in px_all]
    res = {
        "run": run_dir.name, "cases": n_cases, "text_elements": n_el,
        "pearson_log": round(_pearson(le, lp), 4),
        "spearman": round(spearman(est_all, px_all) or 0.0, 4),
        "median_abs_log_diff": round(sorted(abs(x - y) for x, y in zip(le, lp))[len(le) // 2], 4),
        "estimate_lower_share": round(sum(1 for x, y in zip(est_all, px_all) if x < y) / n_el, 4),
        "disagree_at_1.3": round(sum(1 for x, y in zip(est_all, px_all) if (x < 1.3) != (y < 1.3)) / n_el, 4),
        "disagree_at_3.0": round(sum(1 for x, y in zip(est_all, px_all) if (x < 3.0) != (y < 3.0)) / n_el, 4),
        "disagree_at_4.5": round(sum(1 for x, y in zip(est_all, px_all) if (x < 4.5) != (y < 4.5)) / n_el, 4),
        "headline_cta_elements": len(drop_est),
        "drop_rule_estimate_fails": sum(drop_est),
        "drop_rule_render_fails": sum(drop_px),
        "drop_rule_disagree": round(sum(1 for x, y in zip(drop_est, drop_px) if x != y) / max(1, len(drop_est)), 4),
        "ms_per_design_estimate": round(1000.0 * t_est / max(1, 2 * n_cases), 2),
        "ms_per_design_render": round(1000.0 * t_px / max(1, 2 * n_cases), 2),
    }
    (run_dir / "contrast_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
