"""docs/EVAL_SYNTH.md + docs/eval_synth/ from a synthetic run.

    .venv/bin/python -m eval.run_eval --synthetic 200 --seed 1 --workers 4 --name synth
    .venv/bin/python -m eval.synth_report --run synth --worst 30 [--notes eval/notes_synth.md]

Reads eval/data/runs/<run>/results.jsonl (rows carry `prop.*` columns from
eval/synth.py), writes:
  - the harness summary tables (eval.run_eval.summary_markdown)
  - defect rates sliced by every generator property (element-count bucket,
    headline length, missing asset, rotation, background, CTA kind, badges,
    letter spacing, ...), one table per property, sorted by defect rate
  - the nasty cases: one line each with error / defects
  - crashes and hard-defect groups with example cases (the material for the
    prioritised failure list), plus the hand-written notes file
  - worst-N contact sheets (eval.report.contact_sheets)
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.report import DOCS_DIR, contact_sheets, defects_text, rank_worst  # noqa: E402
from eval.run_eval import RUNS_DIR, _fail_flags, _normalize_hard, _pct, read_results, summarize, summary_markdown  # noqa: E402
from eval.synth import SYNTH_DIR  # noqa: E402

# properties worth a table, in the order they appear in the report
PROPERTIES = [
    ("n_elements_bucket", "Element count"),
    ("headline_len", "Headline length class"),
    ("family", "Source ratio family"),
    ("has_missing_asset", "Hero asset missing"),
    ("rotated", "Any rotated element (ribbon / badge / headline)"),
    ("has_rotated_text", "Rotated text"),
    ("background", "Background kind"),
    ("panel", "Text on a panel shape"),
    ("theme", "Theme"),
    ("logo_pos", "Logo position"),
    ("hero", "Hero"),
    ("cta", "CTA kind"),
    ("n_badges", "Badge count"),
    ("n_subs", "Subhead / body count"),
    ("n_decor", "Decorative ellipses"),
    ("has_letter_spacing", "Letter spacing > 0"),
    ("line_height", "Line height"),
    ("has_style_runs", "style_runs"),
    ("has_max_lines", "max_lines"),
    ("text_align", "Text alignment"),
    ("z_tie", "z-index ties"),
    ("has_shadow_text", "Near-duplicate shadow headline"),
    ("has_tiny", "Tiny elements (dots / hairlines)"),
    ("density", "Density"),
    ("src_overfull", "Source overfull (content did not fit the source canvas)"),
    ("src_overflow", "Source text overflow (unbreakable word / letter spacing)"),
]
FLAG_COLS = [("any_defect", "any defect"), ("error", "error"), ("offcanvas", "off-canvas"),
             ("overflow", "overflow"), ("overlap", "overlap"), ("below_floor", "below floor"),
             ("aspect", "aspect"), ("fields", "fields"), ("judge_contrast", "contrast (judge)")]


def _prop(r: dict[str, Any], k: str) -> Any:
    v = r.get(f"prop.{k}")
    if v is None and isinstance(r.get("props"), dict):
        v = r["props"].get(k)
    return v


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nasty = [r for r in rows if _prop(r, "nasty")]
    normal = [r for r in rows if not _prop(r, "nasty")]
    return normal, nasty


def by_property(rows: list[dict[str, Any]], key: str) -> list[tuple[str, int, dict[str, float], float | None]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        v = _prop(r, key)
        groups[str(v)].append(r)
    out = []
    for g, rs in groups.items():
        fl = [_fail_flags(r) for r in rs]
        rates = {k: sum(f[k] for f in fl) / len(rs) for k, _ in FLAG_COLS}
        scores = [r["score_total"] for r in rs if isinstance(r.get("score_total"), (int, float))]
        out.append((g, len(rs), rates, sum(scores) / len(scores) if scores else None))
    out.sort(key=lambda t: (-t[2]["any_defect"], t[0]))
    return out


def property_tables(rows: list[dict[str, Any]]) -> list[str]:
    L: list[str] = []
    for key, title in PROPERTIES:
        groups = by_property(rows, key)
        if len(groups) < 2:
            continue
        L.append(f"\n#### {title} (`{key}`)\n")
        L.append("| value | cases | " + " | ".join(t for _, t in FLAG_COLS) + " | score mean |")
        L.append("|---|---:|" + "---:|" * len(FLAG_COLS) + "---:|")
        for g, n, rates, sc in groups:
            L.append(f"| {g} | {n} | " + " | ".join(_pct(rates[k], 1) for k, _ in FLAG_COLS) +
                     f" | {sc:.1f} |" if sc is not None else f"| {g} | {n} | " +
                     " | ".join(_pct(rates[k], 1) for k, _ in FLAG_COLS) + " | - |")
    return L


def nasty_table(rows: list[dict[str, Any]]) -> list[str]:
    L = ["| case | target | result | winner | score |", "|---|---|---|---|---:|"]
    for r in sorted(rows, key=lambda r: (str(_prop(r, "nasty")), str(r.get("preset")))):
        res = defects_text(r)
        if r.get("error"):
            res = "**" + res + "**"
        L.append(f"| {_prop(r, 'nasty')} | {r['preset']} {r['tgt_w']}x{r['tgt_h']} | {res} | "
                 f"{r.get('winner', '')} | {r.get('score_total', '-')} |")
    return L


def failure_groups(rows: list[dict[str, Any]]) -> list[str]:
    """Crashes first (grouped by exception), then hard defects grouped by
    type with the properties that over-index in them."""
    L: list[str] = []
    errs = [r for r in rows if r.get("error")]
    L.append(f"\n### Crashes and errors: {len(errs)} of {len(rows)} cases\n")
    if errs:
        groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for r in errs:
            groups[re.sub(r"\d+", "N", str(r["error"]))[:120]].append(r)
        for msg, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            ex = ", ".join(f"`{r['key']}`" for r in rs[:4])
            L.append(f"- **{len(rs)}x** `{msg}` — e.g. {ex}")
            tb = next((r.get("traceback") for r in rs if r.get("traceback")), None)
            if tb:
                last = [ln for ln in str(tb).splitlines() if ln.strip().startswith("File")][-2:]
                L.append("  " + " | ".join(ln.strip()[:110] for ln in last))
    else:
        L.append("- none")

    base = {k: sum(_fail_flags(r)[k] for r in rows) / max(1, len(rows)) for k, _ in FLAG_COLS}
    for flag, title in (("offcanvas", "Important unit off canvas"), ("overflow", "Measured text overflow"),
                        ("overlap", "Unwanted overlap"), ("below_floor", "Headline / CTA font below floor"),
                        ("aspect", "Image aspect drift > 5 %"), ("fields", "Structural (ids / fields / immutables / canvas)")):
        rs = [r for r in rows if _fail_flags(r)[flag]]
        L.append(f"\n### {title}: {len(rs)} cases ({_pct(len(rs), len(rows))})\n")
        if not rs:
            L.append("- none")
            continue
        # which properties over-index (lift >= 1.5 over the base rate, n >= 5)
        lifts = []
        for key, _ in PROPERTIES:
            for g, n, rates, _sc in by_property(rows, key):
                if n >= 5 and base[flag] > 0 and rates[flag] / base[flag] >= 1.5 and rates[flag] >= 0.05:
                    lifts.append((rates[flag] / base[flag], f"{key}={g} ({_pct(rates[flag], 1)}, n={n})"))
        lifts.sort(reverse=True)
        if lifts:
            L.append("- over-indexed properties: " + "; ".join(t for _, t in lifts[:8]))
        presets = collections.Counter(r["preset"] for r in rs)
        L.append("- by target: " + ", ".join(f"{p} {n}" for p, n in presets.most_common(6)))
        if flag == "overflow":
            ids = collections.Counter()
            for r in rs:
                for i in str(r.get("overflow_ids") or "").split(";"):
                    if i:
                        ids[i] += 1
            small = sum(1 for r in rs if (r.get("min_font") or 99) <= 8)
            L.append(f"- {small} of them end with a font <= 8 px (fitter at its floor)")
        if flag == "overlap":
            med = sorted(float(r.get("overlap_frac") or 0) for r in rs)[len(rs) // 2]
            L.append(f"- median overlap area {100 * med:.2f} % of the canvas; pairs e.g. " +
                     ", ".join(f"`{r.get('overlap_pairs', '')[:40]}`" for r in rs[:3]))
        worst = sorted(rs, key=lambda r: -(r.get("defect_n") or 0))[:5]
        L.append("- examples: " + ", ".join(f"`{r['key']}`" for r in worst))
    hard = collections.Counter()
    for r in rows:
        for h in str(r.get("judge_hard") or "").split(" | "):
            if h.strip():
                # synthetic ids are opaque hex ("e3f9a1c"); fold them too
                hard[_normalize_hard(re.sub(r"\be[0-9a-f]{6}\b|\b(t|dup|zz)\d+\b", "<el>", h.strip()))] += 1
    L.append("\n### Judge hard fails on the winner (normalised), most common\n")
    L.append("| message | cases |\n|---|---:|")
    for k, v in hard.most_common(12):
        L.append(f"| {k} | {v} |")
    return L


def write_markdown(run_dir: Path, rows: list[dict[str, Any]], notes: str | None, out_md: Path,
                   sheet_dir: Path, worst: list[dict[str, Any]], sheets: list[tuple[str, list[int]]],
                   meta_summary: str | None) -> None:
    normal, nasty = split_rows(rows)
    s = summarize(normal)
    rel = sheet_dir.relative_to(out_md.parent) if sheet_dir.is_relative_to(out_md.parent) else sheet_dir
    L: list[str] = []
    L.append("# EVAL SYNTH — the engine on adversarial synthetic designs\n")
    L.append(f"Generated {dt.date.today().isoformat()} by `eval/synth_report.py` from run `{run_dir.name}` "
             f"(`{run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}`).\n")
    L.append("Harness: `eval/synth.py` (seeded generator + nasty cases), `eval/run_eval.py --synthetic N --seed S` "
             "(same metrics as the Crello run, `eval/metrics.py`), `tests/test_metamorphic.py` "
             "(metamorphic relations over `resize()`), this report.\n")
    L.append("What the corpus contains: canvases in all four ratio families, 2-45 elements, image / shape / no "
             "background, text panels, logo in any corner or the centre, hero present / absent / with a missing "
             "asset, headlines from two words to 140+ characters including unbreakable words, 0-4 subheads, "
             "CTA as free text or shape+label group (badge-style insets), 0-6 badges in rows, rotated ribbons / "
             "badges / headlines (5-45 deg), decorative ellipses (opacity 0.1-0.5) bleeding off canvas, letter "
             "spacing, line height, style_runs, max_lines, text_align, z-index ties, tiny elements, "
             "near-duplicate shadow headlines; plus the nasty cases listed below with their own targets.\n")
    L.append("Caveat: the same measurement caveats as EVAL_V1 (contrast fails are reported, not counted). "
             "The sources are generated, not designed: a few are deliberately overfull or carry an unbreakable "
             "word wider than the canvas (`src_overfull`, `src_overflow` in the tables), which no engine can "
             "lay out cleanly; they are kept because the hidden set promises such input.\n")
    if meta_summary:
        L.append("## Metamorphic tests (`tests/test_metamorphic.py`)\n")
        L.append(meta_summary)
    L.append("## Summary (random corpus, nasty cases excluded)\n")
    L.append(summary_markdown(s))
    L.append("\n## Defect rate by generator property\n")
    L.append("Rates are per case (design x target). Sorted by any-defect rate within each table.\n")
    L += property_tables(normal)
    L.append(f"\n## Nasty cases ({len(nasty)} cases)\n")
    L += nasty_table(nasty)
    L.append("\n## Failure groups (all cases)\n")
    L += failure_groups(rows)
    L.append(f"\n## Worst {len(worst)} cases\n")
    L.append("Contact sheets (source left, our output right): " +
             ", ".join(f"[{name}]({rel}/{name})" for name, _ in sheets) + "\n")
    L.append("| # | design | source | target | defects | winner | score |\n|---:|---|---|---|---|---|---:|")
    for i, r in enumerate(worst, 1):
        L.append(f"| {i} | `{r['design_id']}` {str(r.get('title', ''))[:36]} | {r['src_w']}x{r['src_h']} | "
                 f"{r['preset']} {r['tgt_w']}x{r['tgt_h']} | {defects_text(r)} | {r.get('winner', '')} | "
                 f"{r.get('score_total', '-')} |")
    for name, ranks in sheets:
        L.append(f"\n![worst {ranks[0]}-{ranks[-1]}]({rel}/{name})")
    if notes:
        L.append("\n" + notes.strip() + "\n")
    out_md.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="synth", help="run name under eval/data/runs/ (or a path)")
    ap.add_argument("--data-dir", default=str(SYNTH_DIR))
    ap.add_argument("--worst", type=int, default=30)
    ap.add_argument("--out-dir", default=str(DOCS_DIR / "eval_synth"))
    ap.add_argument("--md", default=str(DOCS_DIR / "EVAL_SYNTH.md"))
    ap.add_argument("--notes", default=None, help="markdown with the hand-written failure list")
    ap.add_argument("--meta", default=None, help="markdown snippet summarising the metamorphic test run")
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args(argv)
    run_dir = Path(a.run) if Path(a.run).exists() else RUNS_DIR / a.run
    rows = read_results(run_dir)
    if not rows:
        raise SystemExit(f"no results in {run_dir}")
    worst = rank_worst(rows, a.worst)
    sheet_dir = Path(a.out_dir)
    sheets = [] if a.no_sheets else contact_sheets(worst, run_dir, Path(a.data_dir), sheet_dir)
    notes = Path(a.notes).read_text() if a.notes else None
    meta = Path(a.meta).read_text() if a.meta else None
    write_markdown(run_dir, rows, notes, Path(a.md), sheet_dir, worst, sheets, meta)
    print(f"{len(rows)} cases; {len(sheets)} sheets in {sheet_dir}; wrote {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
