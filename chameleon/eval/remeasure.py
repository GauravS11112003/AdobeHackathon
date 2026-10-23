"""Re-measure an old run's outputs with the current metrics and scorer.

    .venv/bin/python -m eval.remeasure --run v2 --name v2_remeasured [--workers 4]

Metric definitions move with the engine (painted text boxes, source-relative
overlaps, canvas-relative font floors, the JSON contrast estimate), so the
published numbers of an old run are not comparable with a new run. This
re-reads every case's source and winner JSON from <run>/outputs/, recomputes
`eval.metrics.evaluate_case` (structural, text, overlap, ground truth) and
re-judges the winner with the current `score_design` (render on, the
winner's own strategy), and writes a new run folder with results.jsonl /
results.csv / summary.json / summary.md so `eval.report` and the comparison
tables can use it. Runtime columns are copied from the old run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR  # noqa: E402
from eval.run_eval import RUNS_DIR, _design_path, _load_source, read_results, write_outputs  # noqa: E402

logger = logging.getLogger("eval.remeasure")


class _Judged:
    def __init__(self, name: str, strategy: str, score, fallback: bool):
        self.name, self.strategy, self.score, self.fallback = name, strategy, score, fallback

    def summary(self) -> dict[str, Any]:
        return {"pixels": "remeasured"}


def remeasure_row(row: dict[str, Any], run_dir: str, data_dir: str, index: dict[str, Any]) -> dict[str, Any]:
    from engine.analyze import analyze
    from engine.geometry import Box
    from engine.render import begin_task
    from engine.score import score_design
    from eval.metrics import defect_count, evaluate_case

    out = dict(row)
    try:
        meta = index.get(row["design_id"])
        src_path = _design_path(meta, Path(data_dir)) if meta else ROOT / "input" / f"{row['design_id']}.json"
        key = row["key"].replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")
        out_path = Path(run_dir) / "outputs" / f"{key}.json"
        source = _load_source(src_path)
        output = json.loads(out_path.read_text())
        target = {"width": row["tgt_w"], "height": row["tgt_h"]}
        gt = None
        if row.get("gt_id"):
            p = Path(data_dir) / "designs" / f"{row['gt_id']}.json"
            if p.exists():
                gt = _load_source(p)
        analysis = analyze(source)
        begin_task()          # per-task render budget, as resize() resets it
        sc = score_design(analysis, source, output, Box(0, 0, target["width"], target["height"]),
                          render=True, strategy=row.get("strategy") or None)
        judged = [_Judged(row.get("winner", ""), row.get("strategy", ""), sc, bool(row.get("fallback")))]
        keep = {k: row.get(k) for k in ("n_candidates", "n_clean_candidates", "runner_up_gap", "elapsed")}
        out.update(evaluate_case(source, output, target, judged, row.get("elapsed"), gt=gt))
        for k, v in keep.items():
            if v is not None:
                out[k] = v
        out["pixels"] = "remeasured"
        out["error"] = ""
    except Exception as exc:
        out["error"] = f"remeasure {type(exc).__name__}: {exc}"[:300]
        out["traceback"] = traceback.format_exc()[-1500:]
        out["defect_n"] = defect_count(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="v2")
    ap.add_argument("--name", default=None, help="new run name (default <run>_remeasured)")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("engine").setLevel(logging.ERROR)
    run_dir = Path(a.run) if Path(a.run).exists() else RUNS_DIR / a.run
    new_dir = RUNS_DIR / (a.name or f"{run_dir.name}_remeasured")
    new_dir.mkdir(parents=True, exist_ok=True)
    rows = read_results(run_dir)
    if a.limit:
        rows = rows[: a.limit]
    done = {r["key"] for r in read_results(new_dir)}
    todo = [r for r in rows if r["key"] not in done]
    index = {d["id"]: d for d in json.loads((Path(a.data_dir) / "index.json").read_text())}
    logger.info("remeasure %s -> %s: %d cases, %d to do", run_dir.name, new_dir.name, len(rows), len(todo))
    t0 = time.time()
    results = new_dir / "results.jsonl"
    n = 0

    def record(r: dict[str, Any]) -> None:
        nonlocal n
        with results.open("a") as f:
            f.write(json.dumps(r, default=str) + "\n")
        n += 1
        if n % 200 == 0:
            logger.info("%d/%d (%.0fs)", n, len(todo), time.time() - t0)

    if a.workers <= 1:
        for r in todo:
            record(remeasure_row(r, str(run_dir), a.data_dir, index))
    else:
        import multiprocessing as mp

        with ProcessPoolExecutor(max_workers=a.workers, mp_context=mp.get_context("spawn")) as ex:
            futs = [ex.submit(remeasure_row, r, str(run_dir), a.data_dir, index) for r in todo]
            for fut in as_completed(futs):
                record(fut.result())
    s = write_outputs(new_dir, read_results(new_dir))
    logger.info("done: %d cases in %.0fs -> %s", s["n_cases"], time.time() - t0, new_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
