"""Before / after table of two (or more) eval runs on their common cases.

    .venv/bin/python -m eval.compare_runs v2 v2_remeasured v3 [--presets "Skyscraper ad,Leaderboard ad"]

Prints markdown: failure counts and rates (any defect, overflow, below
floor, overlap, judge contrast, fallback), judge score mean, every score
component, runtime p50 / p95, the ground-truth agreement, and per-preset
defect rates for the presets named (default: all). Only cases present in
every run are compared, so a partial run can be compared with a full one.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.run_eval import RUNS_DIR, _fail_flags, read_results  # noqa: E402

COMPONENTS = ("read.size", "read.lines", "read.contrast", "read.presence", "layout.balance", "layout.alignment",
              "layout.spacing", "layout.fill", "layout.margins", "layout.size", "faith.order", "faith.anchors",
              "faith.hierarchy", "faith.scale")


def _p(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))] if s else float("nan")


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else float("nan")


def table(runs: dict[str, dict[str, dict[str, Any]]], presets: list[str] | None) -> str:
    names = list(runs)
    keys = sorted(set.intersection(*(set(r) for r in runs.values())))
    L: list[str] = []
    L.append(f"Common cases: **{len(keys)}** (" + ", ".join(f"{n}: {len(runs[n])}" for n in names) + ")\n")
    L.append("| metric | " + " | ".join(names) + " |")
    L.append("|---|" + "---:|" * len(names))

    def row(label: str, fn, fmt="{:.3f}"):
        L.append(f"| {label} | " + " | ".join(fmt.format(fn(runs[n])) for n in names) + " |")

    def rate(flag: str):
        return lambda rows: 100.0 * sum(_fail_flags(rows[k])[flag] for k in keys) / len(keys)

    def count(flag: str):
        return lambda rows: sum(_fail_flags(rows[k])[flag] for k in keys)

    for flag, label in (("any_defect", "any hard defect"), ("overflow", "text overflow"), ("below_floor", "headline/CTA below floor"),
                        ("overlap", "unwanted overlap"), ("offcanvas", "off canvas"), ("judge_contrast", "judge contrast fail"),
                        ("fallback", "anchor fallback wins"), ("error", "errors")):
        row(f"{label} (%)", rate(flag), "{:.2f}")
        row(f"{label} (n)", count(flag), "{:.0f}")
    row("judge score mean", lambda rows: _mean([rows[k]["score_total"] for k in keys if isinstance(rows[k].get("score_total"), (int, float))]), "{:.2f}")
    row("judge score p50", lambda rows: _p([rows[k]["score_total"] for k in keys if isinstance(rows[k].get("score_total"), (int, float))], 0.5), "{:.2f}")
    for c in COMPONENTS:
        row(c, lambda rows, c=c: _mean([rows[k][c] for k in keys if isinstance(rows[k].get(c), (int, float))]))
    row("runtime p50 (s)", lambda rows: _p([rows[k]["elapsed"] for k in keys if rows[k].get("elapsed") is not None], 0.5), "{:.2f}")
    row("runtime p95 (s)", lambda rows: _p([rows[k]["elapsed"] for k in keys if rows[k].get("elapsed") is not None], 0.95), "{:.2f}")
    row("smallest font p05 (px)", lambda rows: _p([rows[k]["min_font"] for k in keys if rows[k].get("min_font") is not None], 0.05), "{:.1f}")
    gt = [k for k in keys if str(runs[names[0]][k].get("preset", "")).startswith("gt:") and runs[names[0]][k].get("gt_n")]
    for col, label in (("gt_pos_err", "gt centre error"), ("gt_order_tau", "gt reading-order tau"),
                       ("gt_size_rho", "gt size rho"), ("gt_font_ratio", "gt font ratio (median)")):
        if col == "gt_font_ratio":
            row(label, lambda rows, col=col: _p([rows[k][col] for k in gt if isinstance(rows[k].get(col), (int, float))], 0.5))
        else:
            row(label, lambda rows, col=col: _mean([rows[k][col] for k in gt if isinstance(rows[k].get(col), (int, float))]))

    L.append("\n### Defect rate by preset (%)\n")
    L.append("| preset | n | " + " | ".join(f"{n} any" for n in names) + " | " + " | ".join(f"{n} below floor" for n in names)
             + " | " + " | ".join(f"{n} overlap" for n in names) + " | " + " | ".join(f"{n} contrast" for n in names) + " |")
    L.append("|---|---:|" + "---:|" * (4 * len(names)))
    all_presets = sorted({("gt (designer siblings)" if str(runs[names[0]][k].get("preset", "")).startswith("gt:")
                           else runs[names[0]][k].get("preset")) for k in keys}, key=str)
    for p in all_presets:
        if presets and p not in presets:
            continue
        ks = [k for k in keys if (("gt (designer siblings)" if str(runs[names[0]][k].get("preset", "")).startswith("gt:")
                                   else runs[names[0]][k].get("preset")) == p)]
        cells = []
        for flag in ("any_defect", "below_floor", "overlap", "judge_contrast"):
            for n in names:
                cells.append(f"{100.0 * sum(_fail_flags(runs[n][k])[flag] for k in ks) / len(ks):.1f}")
        L.append(f"| {p} | {len(ks)} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--presets", default="")
    a = ap.parse_args(argv)
    runs = {}
    for name in a.runs:
        d = Path(name) if Path(name).exists() else RUNS_DIR / name
        runs[d.name] = {r["key"]: r for r in read_results(d) if r.get("key")}
    presets = [p.strip() for p in a.presets.split(",") if p.strip()] or None
    print(table(runs, presets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
