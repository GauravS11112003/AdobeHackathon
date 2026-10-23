"""Contact sheets of the worst cases + docs/EVAL_V1.md from a run.

    .venv/bin/python -m eval.report --run full --worst 30 [--notes eval/notes_v1.md]

Reads eval/data/runs/<run>/results.jsonl (+ outputs/*.json), ranks the cases
by (defects, unwanted overlap area, overflow, off-canvas, low score), renders
source and output side by side (organizers' renderer, no engine budgets) into
docs/eval_v1/worst_XX.png (5 cases per sheet) and writes docs/EVAL_V1.md:
run facts, the summary tables, the worst-case table with thumbnails, the
automatically detected failure patterns, and - when --notes points to a
markdown file - the hand-written observations and engine suggestions.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import io
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.crello_convert import DATA_DIR  # noqa: E402
from eval.run_eval import RUNS_DIR, _design_path, _load_source, read_results, summarize, summary_markdown  # noqa: E402

DOCS_DIR = ROOT.parent / "docs"
ASSETS_DIR = ROOT / "brand_kit" / "assets"
FONTS_DIR = ROOT / "brand_kit" / "fonts"
FONT_PATH = FONTS_DIR / "SolsticeSans-Regular.ttf"
BG = (245, 241, 234)
INK = (34, 34, 34)
RED = (180, 30, 30)
GREEN = (20, 150, 80)


def _font(size: int):
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()


_renderer = None


def render(design: dict[str, Any], max_size: int = 520) -> Image.Image | None:
    """Render with the organizers' renderer directly (no engine budgets)."""
    global _renderer
    try:
        from renderer.converter.convert import _get_renderer, convert_chameleon_to_crello

        if _renderer is None:
            _renderer = _get_renderer(str(FONTS_DIR))
        example, _ = convert_chameleon_to_crello(design, _renderer.font_manager, str(ASSETS_DIR))
        png = _renderer.render(example, max_size=max_size, format="png")
        img = Image.open(io.BytesIO(png))
        img.load()
        return img.convert("RGB")
    except Exception:
        return None


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    s = min(w / img.width, h / img.height, 1.0)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def defects_text(r: dict[str, Any]) -> str:
    bits = []
    if r.get("error"):
        bits.append("ERROR " + str(r["error"])[:60])
    if not r.get("ids_ok", True):
        bits.append("ids")
    if not r.get("fields_ok", True) or not r.get("immutable_ok", True) or not r.get("canvas_ok", True):
        bits.append("fields")
    if r.get("offcanvas_n"):
        bits.append(f"off-canvas x{r['offcanvas_n']}")
    if r.get("overflow_n"):
        bits.append(f"overflow x{r['overflow_n']}")
    if r.get("overlap_n"):
        bits.append(f"overlap x{r['overlap_n']} ({100 * float(r.get('overlap_frac') or 0):.1f}% canvas)")
    if r.get("below_floor_n"):
        bits.append(f"font below floor x{r['below_floor_n']}")
    if r.get("aspect_fail_n"):
        bits.append(f"aspect x{r['aspect_fail_n']}")
    if r.get("judge_contrast_fail_n"):
        bits.append(f"contrast x{r['judge_contrast_fail_n']}")
    return "; ".join(bits) or "no hard defect (low score)"


def rank_worst(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    def key(r: dict[str, Any]):
        return (
            -int(r.get("defect_n") or 0),
            -float(r.get("overlap_frac") or 0.0),
            -int(r.get("overflow_n") or 0),
            -int(r.get("offcanvas_n") or 0),
            float(r.get("score_total") if r.get("score_total") is not None else -1e9),
        )
    worst = sorted(rows, key=key)
    # at most two cases per design so one bad template does not fill the sheet
    out: list[dict[str, Any]] = []
    per: collections.Counter[str] = collections.Counter()
    for r in worst:
        if per[r["design_id"]] >= 2:
            continue
        per[r["design_id"]] += 1
        out.append(r)
        if len(out) >= n:
            break
    return out


def _output_path(run_dir: Path, r: dict[str, Any]) -> Path:
    safe = r["key"].replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")
    return run_dir / "outputs" / f"{safe}.json"


def contact_sheets(worst: list[dict[str, Any]], run_dir: Path, data_dir: Path, out_dir: Path,
                   per_sheet: int = 5, cell: int = 420) -> list[tuple[str, list[int]]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {d["id"]: d for d in json.loads((data_dir / "index.json").read_text())} if (data_dir / "index.json").exists() else {}
    sheets: list[tuple[str, list[int]]] = []
    f_big, f_small = _font(18), _font(14)
    pad, head = 16, 64
    for start in range(0, len(worst), per_sheet):
        chunk = worst[start:start + per_sheet]
        W = pad + 2 * (cell + pad)
        H = pad + len(chunk) * (cell + head + pad)
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        ranks = []
        for i, r in enumerate(chunk):
            rank = start + i + 1
            ranks.append(rank)
            y = pad + i * (cell + head + pad)
            title = f"#{rank}  {r['design_id']}  '{str(r.get('title', ''))[:32]}'  {r['src_w']}x{r['src_h']} -> " \
                    f"{r['preset']} {r['tgt_w']}x{r['tgt_h']}"
            d.text((pad, y), title, fill=INK, font=f_big)
            d.text((pad, y + 22), defects_text(r)[:120], fill=RED, font=f_small)
            d.text((pad, y + 40), f"winner: {r.get('winner', '')}  score {r.get('score_total', '-')}  "
                                  f"{r.get('elapsed', '-')}s", fill=GREEN, font=f_small)
            meta = index.get(r["design_id"])
            src_img = out_img = None
            if meta is not None:
                try:
                    src_img = render(_load_source(_design_path(meta, data_dir)))
                except Exception:
                    src_img = None
            else:
                p = ROOT / "input" / f"{r['design_id']}.json"
                if p.exists():
                    src_img = render(_load_source(p))
            op = _output_path(run_dir, r)
            if op.exists():
                out_img = render(json.loads(op.read_text()))
            for col, im in enumerate((src_img, out_img)):
                x = pad + col * (cell + pad)
                if im is None:
                    d.rectangle([x, y + head, x + cell, y + head + cell], outline=(200, 200, 200))
                    d.text((x + 10, y + head + 10), "no render", fill=INK, font=f_small)
                    continue
                th = _fit(im, cell, cell)
                img.paste(th, (x, y + head))
                d.rectangle([x - 1, y + head - 1, x + th.width, y + head + th.height], outline=(190, 190, 190))
        name = f"worst_{start + 1:02d}-{start + len(chunk):02d}.png"
        img.save(out_dir / name)
        sheets.append((name, ranks))
    return sheets


def auto_patterns(rows: list[dict[str, Any]], s: dict[str, Any]) -> list[str]:
    """Numbers-driven observations the report always carries."""
    L: list[str] = []
    n = max(1, len(rows))
    fr = s.get("failure_rate", {})
    order = sorted(((k, v) for k, v in fr.items() if k not in ("any_defect", "judge_hard", "fallback")),
                   key=lambda kv: -kv[1])
    L.append("Defect types by frequency: " + ", ".join(f"{k} {100 * v:.1f}%" for k, v in order[:6]) + ".")
    pairs = s.get("by_family_pair", {})
    worst_pairs = sorted(pairs.items(), key=lambda kv: -kv[1]["any_defect"])[:4]
    L.append("Hardest source -> target families: " +
             ", ".join(f"{k} ({100 * v['any_defect']:.0f}% with a defect, n={v['n']})" for k, v in worst_pairs) + ".")
    presets = s.get("by_preset", {})
    wp = sorted(presets.items(), key=lambda kv: -kv[1]["any_defect"])[:4]
    L.append("Hardest presets: " + ", ".join(f"{k} ({100 * v['any_defect']:.0f}%)" for k, v in wp) + ".")
    # which strategy fails more
    by_strat: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        by_strat[r.get("strategy") or "error"].append(r)
    L.append("Defect rate by winning strategy: " + ", ".join(
        f"{k} {100 * sum(1 for r in v if r.get('defect_n')) / len(v):.1f}% (n={len(v)})"
        for k, v in sorted(by_strat.items())) + ".")
    # overflow: which fonts / how many lines
    ov = [r for r in rows if r.get("overflow_n")]
    if ov:
        small = sum(1 for r in ov if (r.get("min_font") or 99) <= 10)
        L.append(f"Text overflow: {len(ov)} cases; in {small} of them the smallest font is already <= 10px "
                 f"(the fitter hit its floor), the rest overflow at a comfortable size (box too small for the "
                 f"wrapped text, e.g. a single over-wide word or a hard line break).")
    oc = [r for r in rows if r.get("offcanvas_n")]
    if oc:
        L.append(f"Off-canvas: {len(oc)} cases, median worst fraction outside = "
                 f"{sorted(float(r.get('offcanvas_worst_frac') or 0) for r in oc)[len(oc) // 2]:.2f}.")
    ol = [r for r in rows if r.get("overlap_n")]
    if ol:
        fl = sum(1 for r in ol if r.get("strategy") == "floorplan")
        L.append(f"Unwanted overlap: {len(ol)} cases ({fl} floor-plan winners, {len(ol) - fl} anchor winners); "
                 f"median overlap area {100 * sorted(float(r.get('overlap_frac') or 0) for r in ol)[len(ol) // 2]:.2f}% of the canvas.")
    comp = s.get("score_components_mean", {})
    if comp:
        low = sorted(comp.items(), key=lambda kv: kv[1])[:3]
        L.append("Weakest judge components on average: " + ", ".join(f"{k} {v:.2f}" for k, v in low) + ".")
    gt = s.get("ground_truth")
    if gt:
        L.append(f"Against the designers' own versions ({gt['n_cases']} cases): mean centre error "
                 f"{gt['pos_err_mean']:.3f} of the diagonal, reading-order tau {gt['order_tau_mean']:.2f}, "
                 f"size-hierarchy rho {gt['size_rho_mean']:.2f}, our type is {gt['font_ratio_p50']:.2f}x theirs "
                 f"(median, canvas-normalised), our text boxes {gt['width_ratio_p50']:.2f}x as wide.")
    return L


def write_markdown(run_dir: Path, rows: list[dict[str, Any]], s: dict[str, Any], worst: list[dict[str, Any]],
                   sheets: list[tuple[str, list[int]]], notes: str | None, out_md: Path, sheet_dir: Path) -> None:
    rel = sheet_dir.relative_to(out_md.parent) if sheet_dir.is_relative_to(out_md.parent) else sheet_dir
    L: list[str] = []
    L.append("# EVAL v1 — the judge_v1 engine on real Crello designs\n")
    L.append(f"Generated {dt.date.today().isoformat()} by `eval/report.py` from run `{run_dir.name}` "
             f"(`{run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}`).\n")
    L.append("Harness: `eval/crello_convert.py` (Crello -> schema v0.9, brand-kit stand-in assets), "
             "`eval/run_eval.py` (design x preset catalogue, metrics in `eval/metrics.py`), this report. "
             "See the CLAUDE.md note for how to run it.\n")
    L.append("Caveats: assets are the three Solstice stand-ins chosen by shape, fonts are Solstice "
             "Serif/Sans by serif-likeness, so *contrast* fails from the judge mostly reflect the "
             "substitution (white text that sat on a photo now sits on the white canvas) and are reported "
             "separately, not counted as defects. Everything else (ids, off-canvas, overflow, overlap, "
             "aspect, font floors) is measured exactly as the engine's own scorer measures it.\n")
    L.append("## Summary\n")
    L.append(summary_markdown(s))
    L.append("\n## Automatically detected patterns\n")
    for p in auto_patterns(rows, s):
        L.append(f"- {p}")
    L.append(f"\n## Worst {len(worst)} cases\n")
    L.append("Contact sheets (source left, our output right): " +
             ", ".join(f"[{name}]({rel}/{name})" for name, _ in sheets) + "\n")
    L.append("| # | design | source | target | defects | winner | score |\n|---:|---|---|---|---|---|---:|")
    for i, r in enumerate(worst, 1):
        L.append(f"| {i} | `{r['design_id']}` {str(r.get('title', ''))[:30]} | {r['src_w']}x{r['src_h']} | "
                 f"{r['preset']} {r['tgt_w']}x{r['tgt_h']} | {defects_text(r)} | {r.get('winner', '')} | "
                 f"{r.get('score_total', '-')} |")
    for name, ranks in sheets:
        L.append(f"\n![worst {ranks[0]}-{ranks[-1]}]({rel}/{name})")
    if notes:
        L.append("\n" + notes.strip() + "\n")
    out_md.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="full", help="run name under eval/data/runs/ (or a path)")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--worst", type=int, default=30)
    ap.add_argument("--out-dir", default=str(DOCS_DIR / "eval_v1"), help="where the contact sheets go")
    ap.add_argument("--md", default=str(DOCS_DIR / "EVAL_V1.md"))
    ap.add_argument("--notes", default=None, help="markdown file with hand-written observations to append")
    a = ap.parse_args(argv)
    run_dir = Path(a.run) if Path(a.run).exists() else RUNS_DIR / a.run
    rows = read_results(run_dir)
    if not rows:
        raise SystemExit(f"no results in {run_dir}")
    s = summarize(rows)
    worst = rank_worst(rows, a.worst)
    sheet_dir = Path(a.out_dir)
    sheets = contact_sheets(worst, run_dir, Path(a.data_dir), sheet_dir)
    notes = Path(a.notes).read_text() if a.notes else None
    write_markdown(run_dir, rows, s, worst, sheets, notes, Path(a.md), sheet_dir)
    print(f"{len(rows)} cases; {len(sheets)} sheets in {sheet_dir}; wrote {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
