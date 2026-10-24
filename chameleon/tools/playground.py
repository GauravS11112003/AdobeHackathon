"""Local playground for the CHAMELEON engine.

    cd chameleon && .venv/bin/python tools/playground.py   # http://localhost:8765

Pick a sample (or paste / upload any design JSON), choose a target format,
run. Shows source vs output renders (fit or 1:1, with optional role-colored
element boxes), the naive stretch baseline for comparison, every candidate
the judge ranked with its score breakdown, what the analyzer inferred, the
self-check warnings, the output JSON, and an "all formats" gallery that runs
the engine against every preset at once. Engine modules are reloaded on
every run, so edits to engine/*.py show up without restarting.

/eval is the eval browser (harness runs under eval/data/runs/), /label the
pairwise labelling page for the scorer calibration (eval/labeling.py,
eval/calibrate.py, docs/CALIBRATION.md).

Dev tool only - not part of the submission (the Dockerfile does not copy tools/).
"""

from __future__ import annotations

import base64
import copy
import importlib
import io
import json
import sys
import tempfile
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INPUT_DIR = ROOT / "input"
ASSETS_DIR = ROOT / "brand_kit" / "assets"
PORT = 8765

PRESETS = [
    ("Instagram post", 1080, 1080),
    ("Instagram portrait", 1080, 1350),
    ("Story / Reel", 1080, 1920),
    ("YouTube thumbnail", 1280, 720),
    ("Twitter / X post", 1600, 900),
    ("Facebook cover", 820, 312),
    ("LinkedIn banner", 1584, 396),
    ("Wide web banner", 1600, 400),
    ("Leaderboard ad", 728, 90),
    ("Skyscraper ad", 160, 600),
    ("Pinterest pin", 1000, 1500),
    ("A4 poster", 1240, 1754),
]


# ---------------------------------------------------------------------------
# engine glue


def _reload_engine():
    """Re-import the engine so edits are picked up."""
    for n in [n for n in list(sys.modules) if n == "engine" or n.startswith("engine.")]:
        del sys.modules[n]
    import engine.resize  # noqa: F401
    return importlib.import_module("engine.resize"), importlib.import_module("engine.analyze")


def _render_png_b64(design: dict, max_size: int | None = None) -> str:
    """Render via the engine's in-memory renderer when a thumbnail is wanted,
    else via the organizers' file-based entry point (full size)."""
    if max_size:
        try:
            from engine.render import render_design

            img = render_design(design, max_size=max_size)
            if img is not None:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:  # fall through to the file renderer
            pass
    from renderer.converter.convert import render_design_to_png

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
    render_design_to_png(design, ASSETS_DIR, path, max_size=max_size or 2048)
    data = Path(path).read_bytes()
    Path(path).unlink(missing_ok=True)
    return base64.b64encode(data).decode("ascii")


def _self_check(source: dict, output: dict) -> list[str]:
    from engine import main as engine_main

    return engine_main.self_check(source, output)


def _analysis_rows(analyze_mod, source: dict) -> list[dict]:
    a = analyze_mod.analyze(source)
    return [{
        "unit": u.key, "role": u.role, "ids": u.ids, "importance": u.importance,
        "anchor": f"{u.anchor_x} / {u.anchor_y}", "order": u.reading_index,
    } for u in a.units]


def _stretch_baseline(source: dict, width: int, height: int) -> dict:
    """The starter kit's uniform stretch, for side-by-side shame."""
    sx = width / source["canvas"]["width"]
    sy = height / source["canvas"]["height"]
    out = []
    for el in source["elements"]:
        el = copy.deepcopy(el)
        el["x"], el["y"] = el["x"] * sx, el["y"] * sy
        el["width"], el["height"] = el["width"] * sx, el["height"] * sy
        if el["type"] == "text":
            el["font_size"] = max(1.0, el["font_size"] * min(sx, sy))
        out.append(el)
    return {"canvas": {"width": width, "height": height}, "elements": out}


def _judged_candidates(resize_mod, source: dict, target: dict):
    """Best design plus judged candidates; tolerates an engine without the judge API."""
    if hasattr(resize_mod, "resize_with_candidates"):
        return resize_mod.resize_with_candidates(source, target)
    return resize_mod.resize(source, target), []


def run_resize(source: dict, width: int, height: int, *, light: bool = False,
               baseline: bool = False) -> dict:
    resize_mod, analyze_mod = _reload_engine()
    target = {"width": int(width), "height": int(height)}
    t0 = time.time()
    output, judged = _judged_candidates(resize_mod, source, target)
    elapsed = time.time() - t0
    result: dict = {"elapsed": elapsed, "output": output, "warnings": _self_check(source, output)}
    t1 = time.time()
    if light:
        # Gallery mode: just the output thumbnail.
        result["output_png"] = _render_png_b64(output, max_size=640)
    else:
        result["analysis"] = _analysis_rows(analyze_mod, source)
        result["source_png"] = _render_png_b64(source)
        result["output_png"] = _render_png_b64(output)
        if baseline:
            result["baseline_png"] = _render_png_b64(_stretch_baseline(source, int(width), int(height)))
        result["candidates"] = []
        for j in judged:
            try:
                summ = j.summary()
            except Exception:
                summ = {"name": getattr(j, "name", "?"), "total": 0.0, "hard": [], "breakdown": {}, "elapsed": 0.0}
            result["candidates"].append({**summ, "design": j.design,
                                         "png": _render_png_b64(j.design, max_size=480)})
    result["render_elapsed"] = time.time() - t1
    return result


# ---------------------------------------------------------------------------
# eval browser (reads what eval/run_eval.py wrote under eval/data/runs/<run>/)

EVAL_DATA = ROOT / "eval" / "data"
_eval_cache: dict[str, list[dict]] = {}

LIST_FIELDS = ["key", "design_id", "title", "src_w", "src_h", "src_family", "preset", "tgt_w", "tgt_h",
               "tgt_family", "n_elements", "n_text", "gt_id", "error", "ratio_change", "overflow_n",
               "below_floor_n", "overlap_n", "offcanvas_n", "aspect_fail_n", "judge_contrast_fail_n",
               "judge_hard_n", "fallback", "strategy", "winner", "score_total", "elapsed", "defect_n"]
DEFECT_FILTERS = {
    "any": lambda r: r.get("defect_n", 0) > 0 or bool(r.get("error")),
    "none": lambda r: r.get("defect_n", 0) == 0 and not r.get("error"),
    "overflow": lambda r: r.get("overflow_n", 0) > 0,
    "below_floor": lambda r: r.get("below_floor_n", 0) > 0,
    "overlap": lambda r: r.get("overlap_n", 0) > 0,
    "offcanvas": lambda r: r.get("offcanvas_n", 0) > 0,
    "aspect": lambda r: r.get("aspect_fail_n", 0) > 0,
    "contrast": lambda r: r.get("judge_contrast_fail_n", 0) > 0,
    "fallback": lambda r: bool(r.get("fallback")),
    "error": lambda r: bool(r.get("error")),
    "gt": lambda r: bool(r.get("gt_id")),
}


def _eval_runs() -> list[dict]:
    runs = []
    for d in sorted((EVAL_DATA / "runs").glob("*")) if (EVAL_DATA / "runs").exists() else []:
        f = d / "results.jsonl"
        if f.is_file():
            runs.append({"name": d.name, "cases": sum(1 for _ in f.open())})
    return runs


def _eval_rows(run: str) -> list[dict]:
    rows = _eval_cache.get(run)
    f = EVAL_DATA / "runs" / run / "results.jsonl"
    if rows is None and f.is_file():
        rows = [json.loads(line) for line in f.open() if line.strip()]
        _eval_cache[run] = rows
    return rows or []


def _eval_cases(q: dict) -> dict:
    run = q.get("run", "full")
    rows = _eval_rows(run)
    sel = rows
    for field in ("preset", "src_family", "tgt_family", "strategy"):
        v = q.get(field)
        if v:
            sel = [r for r in sel if str(r.get(field)) == v]
    if q.get("defect") in DEFECT_FILTERS:
        sel = [r for r in sel if DEFECT_FILTERS[q["defect"]](r)]
    if q.get("q"):
        needle = q["q"].lower()
        sel = [r for r in sel if needle in str(r.get("title", "")).lower() or needle in str(r.get("design_id", "")).lower()]
    sort = q.get("sort", "score")
    keyfn = {
        "score": lambda r: r.get("score_total", 0),
        "score_desc": lambda r: -r.get("score_total", 0),
        "defects": lambda r: -r.get("defect_n", 0),
        "elapsed": lambda r: -r.get("elapsed", 0),
        "elements": lambda r: -r.get("n_elements", 0),
        "ratio": lambda r: -r.get("ratio_change", 0),
    }.get(sort, lambda r: r.get("score_total", 0))
    sel = sorted(sel, key=keyfn)
    offset, limit = int(q.get("offset", 0)), int(q.get("limit", 60))
    facets = {
        "presets": sorted({r["preset"] for r in rows if not str(r.get("preset", "")).startswith("gt:")}),
        "src_families": sorted({r.get("src_family", "") for r in rows}),
        "tgt_families": sorted({r.get("tgt_family", "") for r in rows}),
        "strategies": sorted({r.get("strategy", "") for r in rows}),
    }
    stats = {
        "n": len(sel),
        "defects": sum(1 for r in sel if r.get("defect_n", 0) > 0 or r.get("error")),
        "score_mean": (sum(r.get("score_total", 0) for r in sel) / len(sel)) if sel else 0,
        "elapsed_mean": (sum(r.get("elapsed", 0) for r in sel) / len(sel)) if sel else 0,
    }
    return {"run": run, "total": len(rows), "stats": stats, "facets": facets,
            "rows": [{k: r.get(k) for k in LIST_FIELDS} for r in sel[offset:offset + limit]]}


def _eval_case(q: dict) -> dict:
    run, key = q.get("run", "full"), q.get("key", "")
    row = next((r for r in _eval_rows(run) if r.get("key") == key), None)
    if row is None:
        raise KeyError(f"no case {key!r} in run {run!r}")
    safe = key.replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")
    out_path = EVAL_DATA / "runs" / run / "outputs" / f"{safe}.json"
    design_path = EVAL_DATA / "designs" / f"{row['design_id']}.json"
    if not design_path.exists():  # the three shipped samples live in input/
        for p in INPUT_DIR.glob("*.json"):
            if p.stem == row["design_id"]:
                design_path = p
    doc = json.loads(design_path.read_text())
    source = doc["source"]
    result = {"row": row, "source": source, "meta": doc.get("meta"), "sidecar": doc.get("sidecar"),
              "source_png": _render_png_b64(source, max_size=720)}
    if out_path.exists():
        output = json.loads(out_path.read_text())
        result["output"] = output
        result["output_png"] = _render_png_b64(output, max_size=720)
        result["warnings"] = _self_check(source, output)
    if row.get("gt_id"):
        gt_path = EVAL_DATA / "designs" / f"{row['gt_id']}.json"
        if gt_path.exists():
            gt = json.loads(gt_path.read_text())["source"]
            result["gt"] = gt
            result["gt_png"] = _render_png_b64(gt, max_size=720)
    return result


# ---------------------------------------------------------------------------
# labelling page (eval/labeling.py does the sampling and the label store)

LABEL_THUMB = 720


def _labeling():
    from eval import labeling

    return labeling


def _label_next(q: dict) -> dict:
    """An unlabelled pair with renders. Reloads the engine first (edits to
    engine/*.py show up), balances formats with the labels so far."""
    import random

    L = _labeling()
    _reload_engine()
    mode = q.get("mode", "candidates")
    runs = (q.get("run_a", ""), q.get("run_b", "")) if mode == "runs" else None
    seed = q.get("seed")
    rng = random.Random(int(seed)) if seed else random.Random()
    stats = L.label_stats()
    rec = L.next_pair(mode, rng, stats=stats, runs=runs)
    size = int(q.get("size", LABEL_THUMB))
    t0 = time.time()
    rec["a_png"] = _render_png_b64(rec["a"]["design"], max_size=size)
    rec["b_png"] = _render_png_b64(rec["b"]["design"], max_size=size)
    rec["source_png"] = _render_png_b64(_labeling().load_source({"file": rec["design_file"], "id": rec["design_id"]}),
                                        max_size=360)
    rec["render_elapsed"] = time.time() - t0
    return rec


def _label_save(req: dict) -> dict:
    L = _labeling()
    rec = dict(req["pair"])
    for k in ("a_png", "b_png", "source_png", "render_elapsed"):
        rec.pop(k, None)
    saved = L.append_label(rec, req["decision"], seconds=req.get("seconds"))
    return {"saved": L._brief(saved), "stats": L.label_stats()}


def _label_undo() -> dict:
    L = _labeling()
    removed = L.undo_label()
    return {"removed": L._brief(removed) if removed else None, "stats": L.label_stats()}


# ---------------------------------------------------------------------------
# http


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/api/tasks":
            tasks = []
            for p in sorted(INPUT_DIR.glob("*.json")):
                t = json.loads(p.read_text())
                tasks.append({"name": p.name, "difficulty": t.get("difficulty", ""),
                              "target": t.get("target_canvas"), "source": t["source"]})
            self._json(200, {"tasks": tasks, "presets": PRESETS})
        elif url.path == "/eval":
            body = EVAL_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/label":
            body = LABEL_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path.startswith("/api/label/"):
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/api/label/next":
                    self._json(200, _label_next(q))
                elif url.path == "/api/label/stats":
                    self._json(200, {"stats": _labeling().label_stats(), "runs": _eval_runs()})
                else:
                    self.send_error(404)
            except Exception:
                self._json(500, {"error": traceback.format_exc()})
        elif url.path.startswith("/api/eval/"):
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/api/eval/runs":
                    self._json(200, {"runs": _eval_runs()})
                elif url.path == "/api/eval/cases":
                    self._json(200, _eval_cases(q))
                elif url.path == "/api/eval/case":
                    self._json(200, _eval_case(q))
                else:
                    self.send_error(404)
            except Exception:
                self._json(500, {"error": traceback.format_exc()})
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path not in ("/api/resize", "/api/label/save", "/api/label/undo"):
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            if url.path == "/api/label/save":
                self._json(200, _label_save(req))
            elif url.path == "/api/label/undo":
                self._json(200, _label_undo())
            else:
                result = run_resize(req["source"], req["width"], req["height"],
                                    light=bool(req.get("light")), baseline=bool(req.get("baseline")))
                self._json(200, result)
        except Exception:
            self._json(500, {"error": traceback.format_exc()})


# ---------------------------------------------------------------------------
# page

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Chameleon playground</title>
<style>
  :root { --bg:#f5f1ea; --panel:#fff; --ink:#222; --muted:#777; --accent:#e86a3a; --line:#ddd; --ok:#1a9a55; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); }
  header { padding:12px 20px; background:#2b1b2e; color:#fff; display:flex; gap:16px; align-items:baseline; }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header span { color:#c9b8cc; font-size:13px; }
  main { display:grid; grid-template-columns: 300px minmax(0,1fr); gap:16px; padding:16px 20px; align-items:start; }
  aside { position:sticky; top:12px; max-height:calc(100vh - 24px); overflow:auto; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; min-width:0; }
  .panel + .panel { margin-top:14px; }
  .panel h2 { font-size:13px; margin:0 0 8px; display:flex; justify-content:space-between; align-items:center; gap:8px; }
  .panel h2 .stat { margin:0; }
  label { display:block; font-size:11px; color:var(--muted); margin:10px 0 4px; text-transform:uppercase; letter-spacing:.04em; }
  select, input, textarea, button { font:inherit; }
  select, input[type=number] { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; }
  .presets { display:flex; flex-wrap:wrap; gap:5px; }
  .presets button, .chip { padding:4px 9px; border:1px solid var(--line); background:#fafafa; border-radius:999px; cursor:pointer; font-size:12px; }
  .presets button.on, .chip.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  .wh { display:grid; grid-template-columns:1fr auto 1fr; gap:6px; align-items:center; }
  #run { width:100%; margin-top:12px; padding:10px; background:var(--accent); color:#fff; border:0; border-radius:8px; font-weight:600; cursor:pointer; }
  #run:disabled, #runAll:disabled { opacity:.5; }
  #runAll { width:100%; margin-top:6px; padding:8px; background:#fff; color:var(--ink); border:1px solid var(--line); border-radius:8px; cursor:pointer; }
  textarea { width:100%; height:160px; font:12px/1.4 ui-monospace, Menlo, monospace; border:1px solid var(--line); border-radius:6px; padding:8px; }
  .stat { font-size:12px; color:var(--muted); margin-top:8px; }
  .opts { display:flex; flex-wrap:wrap; gap:6px 14px; font-size:12px; color:#444; margin-top:8px; }
  .opts label { display:inline-flex; gap:5px; align-items:center; margin:0; text-transform:none; letter-spacing:0; font-size:12px; color:#444; cursor:pointer; }
  .renders { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; }
  .renders.one2one { display:block; overflow-x:auto; white-space:nowrap; }
  .renders.one2one figure { display:inline-block; vertical-align:top; margin-right:14px; white-space:normal; }
  .renders figure { margin:0; min-width:0; }
  .renders figcaption { font-size:12px; color:var(--muted); margin-bottom:6px; display:flex; justify-content:space-between; gap:8px; }
  .frame { position:relative; display:inline-block; max-width:100%; line-height:0; }
  .frame img { max-width:100%; max-height:62vh; width:auto; height:auto; border:1px solid var(--line); background:#111; display:block; }
  .one2one .frame img { max-width:none; max-height:none; }
  .frame svg { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .frame svg rect { fill:none; stroke-width:2; vector-effect:non-scaling-stroke; }
  .frame svg text { font:600 1px sans-serif; paint-order:stroke; stroke:#000; stroke-width:.15px; }
  .hidden { display:none !important; }
  table { width:100%; border-collapse:collapse; font-size:12px; margin-top:4px; }
  th, td { text-align:left; padding:4px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:500; }
  .role { display:inline-block; padding:1px 7px; border-radius:999px; background:#eee; font-size:11px; }
  .role.headline,.role.cta,.role.logo { background:#fde3d6; color:#8a3312; }
  .role.hero,.role.image { background:#dff0f7; color:#114a63; }
  .role.background,.role.decorative { background:#eee; color:#666; }
  .role.badge,.role.subhead,.role.body,.role.fine_print,.role.text,.role.shape { background:#ece7f7; color:#3d2a7a; }
  .warn { color:#a33; font-size:12px; white-space:pre-wrap; margin-top:8px; }
  details { margin-top:10px; } summary { cursor:pointer; color:var(--muted); font-size:12px; }
  pre { font:11px/1.4 ui-monospace, Menlo, monospace; background:#fafafa; border:1px solid var(--line); border-radius:6px; padding:8px; max-height:420px; overflow:auto; }
  .err { background:#fdecec; color:#8a1f1f; padding:10px; border-radius:8px; white-space:pre-wrap; font-size:12px; margin-bottom:14px; }
  .row { display:flex; gap:8px; }
  .row button, .row label.btn { flex:1; padding:6px; border:1px solid var(--line); background:#fafafa; border-radius:6px; cursor:pointer; font-size:12px; text-align:center; margin:0; text-transform:none; letter-spacing:0; color:var(--ink); }
  .cands { display:flex; gap:12px; overflow-x:auto; padding:6px 0 4px; }
  .cand { flex:0 0 280px; border:1px solid var(--line); border-radius:8px; padding:8px; background:#fafafa; font-size:11px; cursor:pointer; }
  .cand.best { border-color:var(--ok); box-shadow:0 0 0 2px #c9ecd9; }
  .cand.sel { outline:2px solid var(--accent); }
  .cand img { width:100%; height:auto; border:1px solid var(--line); background:#111; margin:6px 0; }
  .cand .nm { font-weight:600; font-size:12px; display:flex; justify-content:space-between; gap:6px; }
  .cand .hard { color:#a33; }
  .cand .bd { display:grid; grid-template-columns:1fr 1fr; gap:0 10px; color:#555; }
  .cand .bd b { color:#222; font-weight:500; }
  .gallery { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:12px; }
  .gcell { border:1px solid var(--line); border-radius:8px; padding:8px; background:#fafafa; font-size:11px; }
  .gcell .t { display:flex; justify-content:space-between; font-weight:600; font-size:12px; margin-bottom:6px; }
  .gcell .box { height:150px; display:flex; align-items:center; justify-content:center; background:#111; border-radius:4px; overflow:hidden; }
  .gcell img { max-width:100%; max-height:100%; }
  .gcell .w { color:#a33; margin-top:4px; }
  .gcell.bad { border-color:#e0a0a0; }
  .legend { display:flex; flex-wrap:wrap; gap:6px 12px; font-size:11px; color:#555; margin-top:6px; }
  .legend i { display:inline-block; width:10px; height:10px; border:2px solid; margin-right:4px; vertical-align:-1px; }
</style></head>
<body>
<header><h1>Chameleon playground</h1><span>pick a design, pick a canvas, run the engine</span><span style="margin-left:auto"><a href="/eval" style="color:#f0c9a8">Eval browser →</a> &nbsp; <a href="/label" style="color:#f0c9a8">Label pairs →</a></span></header>
<main>
  <aside class="panel">
    <label>Source design</label>
    <select id="task"></select>
    <div class="row" style="margin-top:6px">
      <label class="btn">Upload JSON<input type="file" id="file" accept=".json,application/json" class="hidden"></label>
      <button id="reset">Reset to sample</button>
    </div>
    <label>Target format</label>
    <div class="presets" id="presets"></div>
    <label>Custom size</label>
    <div class="wh"><input type="number" id="w" value="1080"><span>×</span><input type="number" id="h" value="1350"></div>
    <div class="row" style="margin-top:6px"><button id="swap">Swap W/H</button><button id="useTask">Use sample's target</button></div>
    <button id="run">Run resize</button>
    <button id="runAll">Run all formats</button>
    <div class="stat" id="timing"></div>
    <label>View</label>
    <div class="opts">
      <label><input type="checkbox" id="optBoxes"> element boxes</label>
      <label><input type="checkbox" id="optBaseline"> stretch baseline</label>
      <label><input type="checkbox" id="optOne"> 1:1 pixels</label>
    </div>
    <div class="legend" id="legend"></div>
    <div class="row" style="margin-top:12px"><button id="dlJson">Download JSON</button><button id="dlPng">Download PNG</button></div>
    <details><summary>Edit source JSON</summary><textarea id="src"></textarea></details>
  </aside>
  <section>
    <div id="error"></div>
    <div class="panel">
      <div class="renders" id="renders">
        <figure><figcaption><span>Source</span><span id="srcDim"></span></figcaption><div class="frame"><img id="srcImg" alt=""><svg id="srcOv"></svg></div></figure>
        <figure id="baseFig" class="hidden"><figcaption><span>Stretch baseline (starter kit)</span><span id="baseDim"></span></figcaption><div class="frame"><img id="baseImg" alt=""></div></figure>
        <figure><figcaption><span id="outLabel">Output</span><span id="outDim"></span></figcaption><div class="frame"><img id="outImg" alt=""><svg id="outOv"></svg></div></figure>
      </div>
      <div class="warn" id="warnings"></div>
    </div>
    <div class="panel" id="candPanel">
      <h2>Candidates the judge ranked <span class="stat" id="candStat"></span></h2>
      <div class="cands" id="cands"></div>
    </div>
    <div class="panel hidden" id="galleryPanel">
      <h2>All formats <span class="stat" id="galleryStat"></span></h2>
      <div class="gallery" id="gallery"></div>
    </div>
    <div class="panel">
      <h2>What the analyzer inferred</h2>
      <table id="analysis"><thead><tr><th>#</th><th>Unit</th><th>Role</th><th>Anchor</th><th>Elements</th></tr></thead><tbody></tbody></table>
      <details><summary>Output JSON</summary><pre id="outJson"></pre></details>
    </div>
  </section>
</main>
<script>
let tasks = [], presets = [], last = null, roles = {}, shownOutput = null;
const $ = s => document.querySelector(s);
const ROLE_COLOR = { headline:'#ff8a4c', cta:'#ff5e3a', logo:'#ffd166', hero:'#4cc9f0', image:'#4cc9f0',
  badge:'#c77dff', subhead:'#b8c0ff', body:'#b8c0ff', fine_print:'#9aa0b4', text:'#b8c0ff', shape:'#b8c0ff',
  background:'#666', decorative:'#888' };

async function init() {
  const d = await (await fetch('/api/tasks')).json();
  tasks = d.tasks; presets = d.presets;
  $('#task').innerHTML = tasks.map((t,i)=>`<option value="${i}">${t.name.replace('chameleon_sample_','').replace('.json','')} · ${t.source.canvas.width}×${t.source.canvas.height} → ${t.target.width}×${t.target.height}</option>`).join('');
  $('#presets').innerHTML = presets.map(p=>`<button data-w="${p[1]}" data-h="${p[2]}" title="${p[0]}">${p[0]} ${p[1]}×${p[2]}</button>`).join('');
  $('#legend').innerHTML = Object.entries(ROLE_COLOR).filter(([k])=>!['text','shape','body'].includes(k)).map(([k,c])=>`<span><i style="border-color:${c}"></i>${k}</span>`).join('');
  $('#presets').addEventListener('click', e => { const b = e.target.closest('button'); if(!b) return;
    markPreset(b); $('#w').value = b.dataset.w; $('#h').value = b.dataset.h; run(); });
  $('#task').addEventListener('change', loadTask);
  $('#reset').addEventListener('click', loadTask);
  $('#file').addEventListener('change', loadFile);
  $('#swap').addEventListener('click', ()=>{ const w=$('#w').value; $('#w').value=$('#h').value; $('#h').value=w; markPreset(null); run(); });
  $('#useTask').addEventListener('click', ()=>{ const t=tasks[$('#task').value]; $('#w').value=t.target.width; $('#h').value=t.target.height; markPreset(null); run(); });
  ['#w','#h'].forEach(s=>$(s).addEventListener('change', ()=>{ markPreset(null); run(); }));
  $('#run').addEventListener('click', run);
  $('#runAll').addEventListener('click', runAll);
  $('#optBoxes').addEventListener('change', drawOverlays);
  $('#optBaseline').addEventListener('change', ()=>{ if (last && !last.baseline_png && $('#optBaseline').checked) run(); else showBaseline(); });
  $('#optOne').addEventListener('change', ()=> $('#renders').classList.toggle('one2one', $('#optOne').checked));
  $('#dlJson').addEventListener('click', ()=> shownOutput && download('design_'+shownOutput.canvas.width+'x'+shownOutput.canvas.height+'.json', 'data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(shownOutput,null,2))));
  $('#dlPng').addEventListener('click', ()=> $('#outImg').src && download('design_'+$('#outDim').textContent+'.png', $('#outImg').src));
  // Hand-off from the eval browser: {source, width, height} parked in localStorage.
  let handoff = null; try { handoff = JSON.parse(localStorage.getItem('chameleon_load') || 'null'); localStorage.removeItem('chameleon_load'); } catch(e) {}
  if (handoff && handoff.source) { $('#src').value = JSON.stringify(handoff.source, null, 2); $('#w').value = handoff.width; $('#h').value = handoff.height; run(); }
  else loadTask();
}
function markPreset(b){ document.querySelectorAll('.presets button').forEach(x=>x.classList.toggle('on', x===b)); }
function download(name, href){ const a=document.createElement('a'); a.href=href; a.download=name; a.click(); }
function loadTask() {
  const t = tasks[$('#task').value];
  $('#src').value = JSON.stringify(t.source, null, 2);
  $('#w').value = t.target.width; $('#h').value = t.target.height;
  markPreset(null); run();
}
function loadFile(e) {
  const f = e.target.files[0]; if (!f) return;
  f.text().then(txt => {
    let j; try { j = JSON.parse(txt); } catch(err) { showErr('Not valid JSON: '+err.message); return; }
    const design = j.source || j;
    if (!design.canvas || !design.elements) { showErr('Expected {canvas, elements} or a task file with "source".'); return; }
    $('#src').value = JSON.stringify(design, null, 2);
    if (j.target_canvas) { $('#w').value = j.target_canvas.width; $('#h').value = j.target_canvas.height; }
    markPreset(null); run();
  });
  e.target.value = '';
}
function showErr(m){ $('#error').innerHTML = `<div class="err">${m}</div>`; }
function currentSource(){ try { return JSON.parse($('#src').value); } catch(e) { showErr('Source JSON is not valid: '+e.message); return null; } }

async function run() {
  const source = currentSource(); if (!source) return;
  $('#run').disabled = true; $('#timing').textContent = 'running…'; $('#error').innerHTML = '';
  const r = await fetch('/api/resize', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({source, width:+$('#w').value, height:+$('#h').value, baseline: $('#optBaseline').checked})});
  const d = await r.json();
  $('#run').disabled = false;
  if (d.error) { showErr(d.error); $('#timing').textContent=''; return; }
  last = d; last.source = source;
  roles = {}; (d.analysis||[]).forEach(u => u.ids.forEach(id => roles[id] = u.role));
  $('#srcImg').src = 'data:image/png;base64,' + d.source_png;
  $('#srcDim').textContent = `${source.canvas.width}×${source.canvas.height}`;
  showOutput(d.output, d.output_png, 'Output (judge\'s pick)');
  showBaseline();
  const n = source.elements.length, rc = Math.max(+$('#w').value/source.canvas.width, +$('#h').value/source.canvas.height) / Math.min(+$('#w').value/source.canvas.width, +$('#h').value/source.canvas.height);
  $('#timing').textContent = `${n} elements · ratio change ${rc.toFixed(2)}× · resize ${(d.elapsed*1000).toFixed(0)} ms · render ${(d.render_elapsed*1000).toFixed(0)} ms`;
  $('#warnings').textContent = d.warnings.length ? 'Self-check: ' + d.warnings.join('\n') : '';
  const cands = d.candidates || [];
  $('#candPanel').classList.toggle('hidden', !cands.length);
  $('#candStat').textContent = cands.length ? `${cands.length} candidates, best first · click one to view it as the output` : '';
  $('#cands').innerHTML = cands.map((c,i)=>`<div class="cand ${i===0?'best':''}" data-i="${i}">
      <div class="nm"><span>#${i+1} ${c.name}${c.fallback?' (fallback)':''}</span><span>${(+c.total).toFixed(1)}</span></div>
      ${(c.hard||[]).length ? `<div class="hard">${c.hard.map(h=>'✗ '+h).join('<br>')}</div>` : ''}
      <img src="data:image/png;base64,${c.png}" alt="">
      <div class="bd">${Object.entries(c.breakdown||{}).map(([k,v])=>`<span>${k} <b>${(+v).toFixed(2)}</b></span>`).join('')}</div>
      <div class="stat">${c.strategy||''} · ${((c.elapsed||0)*1000).toFixed(0)} ms</div>
    </div>`).join('');
  document.querySelectorAll('.cand').forEach(el => el.addEventListener('click', () => {
    const i = +el.dataset.i; const c = cands[i];
    document.querySelectorAll('.cand').forEach(x=>x.classList.toggle('sel', x===el));
    showOutput(c.design || d.output, c.png, i===0 ? 'Output (judge\'s pick)' : `Candidate #${i+1}: ${c.name}`);
  }));
  $('#analysis tbody').innerHTML = (d.analysis||[]).map(u=>`<tr><td>${u.order>=0?u.order:'–'}</td><td>${u.unit}</td><td><span class="role ${u.role}">${u.role}</span></td><td>${u.anchor}</td><td>${u.ids.join(', ')}</td></tr>`).join('');
}
function showOutput(design, png, label) {
  shownOutput = design;
  $('#outImg').src = 'data:image/png;base64,' + png;
  $('#outDim').textContent = `${design.canvas.width}×${design.canvas.height}`;
  $('#outLabel').textContent = label;
  $('#outJson').textContent = JSON.stringify(design, null, 2);
  drawOverlays();
}
function showBaseline() {
  const on = $('#optBaseline').checked && last && last.baseline_png;
  $('#baseFig').classList.toggle('hidden', !on);
  if (on) { $('#baseImg').src = 'data:image/png;base64,' + last.baseline_png; $('#baseDim').textContent = $('#outDim').textContent; }
}
function overlay(svg, design) {
  if (!$('#optBoxes').checked || !design) { svg.innerHTML = ''; return; }
  const W = design.canvas.width, H = design.canvas.height, fs = Math.max(8, Math.min(W, H) / 32);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('preserveAspectRatio', 'none');
  svg.innerHTML = design.elements.map(e => {
    const role = roles[e.id] || e.type, c = ROLE_COLOR[role] || '#fff';
    if (role === 'background') return '';
    const cx = e.x + e.width/2, cy = e.y + e.height/2, rot = e.rotation ? ` transform="rotate(${e.rotation} ${cx} ${cy})"` : '';
    return `<g${rot}><rect x="${e.x}" y="${e.y}" width="${e.width}" height="${e.height}" stroke="${c}"/>
      <text x="${e.x+2}" y="${e.y - fs*0.3}" fill="${c}" font-size="${fs}">${e.id}${e.font_size?' '+Math.round(e.font_size)+'px':''}</text></g>`;
  }).join('');
}
function drawOverlays() { overlay($('#srcOv'), last && last.source); overlay($('#outOv'), shownOutput); }

async function runAll() {
  const source = currentSource(); if (!source) return;
  $('#runAll').disabled = true; $('#galleryPanel').classList.remove('hidden');
  $('#gallery').innerHTML = presets.map(p=>`<div class="gcell" id="g${p[1]}x${p[2]}"><div class="t"><span>${p[0]}</span><span>${p[1]}×${p[2]}</span></div><div class="box"><span style="color:#888">running…</span></div></div>`).join('');
  let bad = 0, t0 = performance.now();
  for (const p of presets) {
    const cell = $(`#g${p[1]}x${p[2]}`);
    try {
      const r = await fetch('/api/resize', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({source, width:p[1], height:p[2], light:true})});
      const d = await r.json();
      if (d.error) throw new Error(d.error.split('\n').slice(-2).join(' '));
      cell.querySelector('.box').innerHTML = `<img src="data:image/png;base64,${d.output_png}" title="click to open in the main view">`;
      cell.querySelector('img').addEventListener('click', ()=>{ $('#w').value=p[1]; $('#h').value=p[2]; markPreset([...document.querySelectorAll('.presets button')].find(b=>+b.dataset.w===p[1]&&+b.dataset.h===p[2])); run(); window.scrollTo({top:0, behavior:'smooth'}); });
      if (d.warnings.length) { bad++; cell.classList.add('bad'); cell.insertAdjacentHTML('beforeend', `<div class="w">${d.warnings.join('<br>')}</div>`); }
      cell.insertAdjacentHTML('beforeend', `<div class="stat">${(d.elapsed*1000).toFixed(0)} ms</div>`);
    } catch (e) { bad++; cell.classList.add('bad'); cell.querySelector('.box').innerHTML = `<span style="color:#f99;padding:8px;font-size:11px">${e.message}</span>`; }
    $('#galleryStat').textContent = `${bad} with warnings · ${((performance.now()-t0)/1000).toFixed(1)} s`;
  }
  $('#runAll').disabled = false;
}
init();
</script>
</body></html>
"""


EVAL_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Chameleon eval browser</title>
<style>
  :root { --bg:#f5f1ea; --panel:#fff; --ink:#222; --muted:#777; --accent:#e86a3a; --line:#ddd; --ok:#1a9a55; --bad:#c0392b; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); }
  header { padding:12px 20px; background:#2b1b2e; color:#fff; display:flex; gap:16px; align-items:baseline; }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header span { color:#c9b8cc; font-size:13px; }
  header a { color:#f0c9a8; }
  main { display:grid; grid-template-columns: 250px 380px minmax(0,1fr); gap:14px; padding:14px 20px; align-items:start; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px; min-width:0; }
  aside { position:sticky; top:12px; max-height:calc(100vh - 24px); overflow:auto; }
  label { display:block; font-size:11px; color:var(--muted); margin:8px 0 3px; text-transform:uppercase; letter-spacing:.04em; }
  select, input { width:100%; padding:5px 7px; border:1px solid var(--line); border-radius:6px; font:inherit; }
  .stats { font-size:12px; color:#444; margin-top:10px; line-height:1.6; }
  .stats b { font-weight:600; }
  .list { max-height:calc(100vh - 60px); overflow:auto; }
  .case { padding:8px 8px; border-bottom:1px solid var(--line); cursor:pointer; font-size:12px; }
  .case:hover { background:#fbf7f1; }
  .case.sel { background:#fde3d6; }
  .case .t { font-weight:600; display:flex; justify-content:space-between; gap:6px; }
  .case .t .s { font-weight:500; color:var(--muted); }
  .case .m { color:var(--muted); }
  .case .d { color:var(--bad); }
  .tag { display:inline-block; padding:0 6px; border-radius:999px; background:#eee; font-size:11px; margin-right:3px; }
  .tag.bad { background:#fde0dc; color:#8a1f1f; }
  .tag.ok { background:#dff4e7; color:#1b5e36; }
  .pager { display:flex; justify-content:space-between; align-items:center; padding:8px; font-size:12px; color:var(--muted); }
  .pager button, .btn { padding:5px 10px; border:1px solid var(--line); background:#fafafa; border-radius:6px; cursor:pointer; font-size:12px; }
  .pager button:disabled { opacity:.4; }
  .renders { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; }
  .renders figure { margin:0; min-width:0; }
  .renders figcaption { font-size:12px; color:var(--muted); margin-bottom:5px; display:flex; justify-content:space-between; }
  .renders img { max-width:100%; max-height:58vh; width:auto; height:auto; border:1px solid var(--line); background:#111; display:block; }
  h2 { font-size:14px; margin:0 0 8px; display:flex; justify-content:space-between; gap:8px; align-items:center; }
  .bars { display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:4px 14px; font-size:11px; margin-top:8px; }
  .bar { display:grid; grid-template-columns:96px 1fr 32px; gap:6px; align-items:center; }
  .bar i { display:block; height:7px; background:#eee; border-radius:4px; overflow:hidden; }
  .bar i b { display:block; height:100%; background:var(--ok); }
  .bar i b.lo { background:#e8a33a; } .bar i b.vlo { background:var(--bad); }
  .kv { font-size:12px; color:#444; display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap:2px 14px; margin-top:8px; }
  .defects { font-size:12px; color:var(--bad); white-space:pre-wrap; margin-top:8px; }
  .err { background:#fdecec; color:#8a1f1f; padding:10px; border-radius:8px; white-space:pre-wrap; font-size:12px; }
  .hint { color:var(--muted); font-size:13px; padding:30px; text-align:center; }
  details { margin-top:8px; } summary { cursor:pointer; color:var(--muted); font-size:12px; }
  pre { font:11px/1.4 ui-monospace, Menlo, monospace; background:#fafafa; border:1px solid var(--line); border-radius:6px; padding:8px; max-height:320px; overflow:auto; }
</style></head>
<body>
<header><h1>Eval browser</h1><span>browse every case the harness ran</span><span style="margin-left:auto"><a href="/">← Playground</a> &nbsp; <a href="/label">Label pairs →</a></span></header>
<main>
  <aside class="panel">
    <label>Run</label><select id="run"></select>
    <label>Target format</label><select id="preset"><option value="">all</option></select>
    <label>Source shape</label><select id="src_family"><option value="">all</option></select>
    <label>Target shape</label><select id="tgt_family"><option value="">all</option></select>
    <label>Defect</label>
    <select id="defect">
      <option value="">all cases</option><option value="any">any defect</option><option value="none">clean</option>
      <option value="overflow">text overflow</option><option value="below_floor">font below floor</option>
      <option value="overlap">unwanted overlap</option><option value="offcanvas">off canvas</option>
      <option value="aspect">image aspect</option><option value="contrast">contrast (judge)</option>
      <option value="fallback">fallback used</option><option value="error">engine error</option>
      <option value="gt">has designer version</option>
    </select>
    <label>Strategy</label><select id="strategy"><option value="">all</option></select>
    <label>Sort</label>
    <select id="sort"><option value="score">worst score first</option><option value="score_desc">best score first</option><option value="defects">most defects</option><option value="elapsed">slowest</option><option value="elements">most elements</option><option value="ratio">biggest shape change</option></select>
    <label>Search title / id</label><input id="q" placeholder="e.g. conference">
    <div class="stats" id="stats"></div>
  </aside>
  <section class="panel" style="padding:0">
    <div class="list" id="list"></div>
    <div class="pager"><button id="prev">← Prev</button><span id="pageInfo"></span><button id="next">Next →</button></div>
  </section>
  <section id="detail"><div class="panel hint">Pick a case on the left.</div></section>
</main>
<script>
const $ = s => document.querySelector(s);
const F = ['run','preset','src_family','tgt_family','defect','strategy','sort'];
let offset = 0, LIMIT = 60, rows = [], selKey = null, total = 0;
function qs() { const p = new URLSearchParams(); F.forEach(k => { if ($('#'+k).value) p.set(k, $('#'+k).value); }); if ($('#q').value) p.set('q', $('#q').value); p.set('offset', offset); p.set('limit', LIMIT); return p.toString(); }
async function init() {
  const r = await (await fetch('/api/eval/runs')).json();
  if (!r.runs.length) { $('#list').innerHTML = '<div class="hint">No eval runs found under chameleon/eval/data/runs/. Run <code>.venv/bin/python -m eval.run_eval</code> first.</div>'; return; }
  $('#run').innerHTML = r.runs.map(x => `<option value="${x.name}" ${x.name==='full'?'selected':''}>${x.name} (${x.cases} cases)</option>`).join('');
  F.forEach(k => $('#'+k).addEventListener('change', () => { offset = 0; load(); }));
  let t; $('#q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { offset = 0; load(); }, 250); });
  $('#prev').addEventListener('click', () => { offset = Math.max(0, offset - LIMIT); load(); });
  $('#next').addEventListener('click', () => { offset += LIMIT; load(); });
  document.addEventListener('keydown', e => { if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return; if (e.key === 'j') step(1); if (e.key === 'k') step(-1); });
  await load(true);
}
function fill(sel, vals, keep) { const cur = $(sel).value; $(sel).innerHTML = '<option value="">all</option>' + vals.map(v => `<option value="${v}">${v}</option>`).join(''); if (keep) $(sel).value = cur; }
async function load(first) {
  const d = await (await fetch('/api/eval/cases?' + qs())).json();
  if (d.error) { $('#list').innerHTML = `<div class="err">${d.error}</div>`; return; }
  rows = d.rows; total = d.stats.n;
  if (first) { fill('#preset', d.facets.presets); fill('#src_family', d.facets.src_families); fill('#tgt_family', d.facets.tgt_families); fill('#strategy', d.facets.strategies); }
  $('#stats').innerHTML = `<b>${d.stats.n}</b> of ${d.total} cases<br><b>${d.stats.defects}</b> with a defect (${d.stats.n ? (100*d.stats.defects/d.stats.n).toFixed(1) : 0}%)<br>mean score <b>${d.stats.score_mean.toFixed(1)}</b><br>mean time <b>${(d.stats.elapsed_mean*1000).toFixed(0)} ms</b><br><span style="color:var(--muted)">j / k = next / previous case</span>`;
  $('#list').innerHTML = rows.map(r => {
    const tags = [];
    if (r.error) tags.push('<span class="tag bad">error</span>');
    if (r.overflow_n) tags.push(`<span class="tag bad">overflow ×${r.overflow_n}</span>`);
    if (r.below_floor_n) tags.push(`<span class="tag bad">font floor ×${r.below_floor_n}</span>`);
    if (r.overlap_n) tags.push(`<span class="tag bad">overlap ×${r.overlap_n}</span>`);
    if (r.offcanvas_n) tags.push(`<span class="tag bad">off canvas</span>`);
    if (r.aspect_fail_n) tags.push(`<span class="tag bad">aspect</span>`);
    if (r.judge_contrast_fail_n) tags.push(`<span class="tag">contrast ×${r.judge_contrast_fail_n}</span>`);
    if (r.fallback) tags.push('<span class="tag">fallback</span>');
    if (!tags.length) tags.push('<span class="tag ok">clean</span>');
    const tgt = r.preset.startsWith('gt:') ? `designer ${r.tgt_w}×${r.tgt_h}` : `${r.preset} ${r.tgt_w}×${r.tgt_h}`;
    return `<div class="case ${r.key===selKey?'sel':''}" data-key="${r.key}"><div class="t"><span>${r.title || r.design_id}</span><span class="s">${(+r.score_total).toFixed(0)}</span></div><div class="m">${r.src_w}×${r.src_h} → ${tgt} · ${r.n_elements} el · ${r.strategy}</div><div>${tags.join('')}</div></div>`;
  }).join('') || '<div class="hint">No cases match.</div>';
  document.querySelectorAll('.case').forEach(el => el.addEventListener('click', () => show(el.dataset.key)));
  $('#pageInfo').textContent = total ? `${offset+1}–${Math.min(offset+LIMIT, total)} of ${total}` : '';
  $('#prev').disabled = offset === 0; $('#next').disabled = offset + LIMIT >= total;
}
function step(dir) { const i = rows.findIndex(r => r.key === selKey); const j = i + dir; if (j >= 0 && j < rows.length) show(rows[j].key); }
async function show(key) {
  selKey = key; document.querySelectorAll('.case').forEach(el => el.classList.toggle('sel', el.dataset.key === key));
  const el = document.querySelector(`.case[data-key="${CSS.escape(key)}"]`); if (el) el.scrollIntoView({block:'nearest'});
  $('#detail').innerHTML = '<div class="panel hint">Rendering…</div>';
  const d = await (await fetch('/api/eval/case?run=' + encodeURIComponent($('#run').value) + '&key=' + encodeURIComponent(key))).json();
  if (d.error) { $('#detail').innerHTML = `<div class="err">${d.error}</div>`; return; }
  const r = d.row;
  const comps = Object.entries(r).filter(([k]) => /^(read|layout|faith)\./.test(k));
  const bars = comps.map(([k,v]) => `<div class="bar"><span>${k}</span><i><b class="${v<0.4?'vlo':v<0.7?'lo':''}" style="width:${Math.max(0,Math.min(1,v))*100}%"></b></i><span>${(+v).toFixed(2)}</span></div>`).join('');
  const defects = [r.error && 'engine error: '+r.error, r.overflow_ids && 'overflow: '+r.overflow_ids, r.below_floor_ids && 'font below floor: '+r.below_floor_ids, r.overlap_pairs && 'overlap: '+r.overlap_pairs, r.offcanvas_ids && 'off canvas: '+r.offcanvas_ids, r.judge_hard && 'judge: '+r.judge_hard].filter(Boolean).join('\n');
  const meta = d.meta ? `${d.meta.format || ''} · ${d.meta.category || ''}` : '';
  $('#detail').innerHTML = `
    <div class="panel">
      <h2><span>${r.title || r.design_id} <span style="color:var(--muted);font-weight:400">${meta}</span></span>
        <span><button class="btn" id="openPg">Open in playground</button> <button class="btn" id="dl">Output JSON</button></span></h2>
      <div class="renders">
        <figure><figcaption><span>Source</span><span>${r.src_w}×${r.src_h}</span></figcaption><img src="data:image/png;base64,${d.source_png}"></figure>
        ${d.output_png ? `<figure><figcaption><span>Our output · ${r.winner}</span><span>${r.tgt_w}×${r.tgt_h}</span></figcaption><img src="data:image/png;base64,${d.output_png}"></figure>` : '<figure><figcaption>Our output</figcaption><div class="hint">no output stored (engine error)</div></figure>'}
        ${d.gt_png ? `<figure><figcaption><span>Designer's own version</span><span>${d.gt.canvas.width}×${d.gt.canvas.height}</span></figcaption><img src="data:image/png;base64,${d.gt_png}"></figure>` : ''}
      </div>
      ${defects ? `<div class="defects">${defects}</div>` : '<div class="defects" style="color:var(--ok)">no hard defects</div>'}
      <div class="kv"><span>score <b>${(+r.score_total).toFixed(1)}</b></span><span>strategy <b>${r.strategy}</b> (${r.n_candidates} candidates, ${r.n_clean_candidates} clean)</span><span>time <b>${(r.elapsed*1000).toFixed(0)} ms</b></span><span>shape change <b>${(+r.ratio_change).toFixed(2)}×</b></span><span>min font <b>${r.min_font}px</b></span><span>runner-up gap <b>${r.runner_up_gap}</b></span></div>
      <div class="bars">${bars}</div>
      ${d.sidecar ? `<details><summary>Original fonts / assets (before brand-kit substitution)</summary><pre>${JSON.stringify(d.sidecar, null, 2)}</pre></details>` : ''}
      <details><summary>Output JSON</summary><pre>${d.output ? JSON.stringify(d.output, null, 2) : '—'}</pre></details>
    </div>`;
  $('#openPg').addEventListener('click', () => { localStorage.setItem('chameleon_load', JSON.stringify({source: d.source, width: r.tgt_w, height: r.tgt_h})); window.open('/', '_blank'); });
  $('#dl').addEventListener('click', () => { if (!d.output) return; const a = document.createElement('a'); a.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(d.output, null, 2)); a.download = key.replace(/[|:/ ]/g,'_') + '.json'; a.click(); });
}
init();
</script>
</body></html>
"""


LABEL_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Chameleon · label pairs</title>
<style>
  :root { --bg:#f5f1ea; --panel:#fff; --ink:#222; --muted:#777; --accent:#e86a3a; --line:#ddd; --ok:#1a9a55; --bad:#c0392b; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); }
  header { padding:10px 20px; background:#2b1b2e; color:#fff; display:flex; gap:16px; align-items:baseline; }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header span { color:#c9b8cc; font-size:13px; }
  header a { color:#f0c9a8; }
  main { padding:12px 20px; display:grid; gap:12px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px; min-width:0; }
  .top { display:grid; grid-template-columns:auto minmax(0,1fr) auto; gap:16px; align-items:start; }
  .top img { max-height:150px; max-width:260px; border:1px solid var(--line); background:#111; display:block; }
  .info { font-size:13px; color:#444; line-height:1.6; }
  .info b { font-weight:600; }
  .ctl { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; font-size:12px; color:#444; }
  .ctl select { padding:4px 6px; border:1px solid var(--line); border-radius:6px; font:inherit; }
  .ctl label { display:inline-flex; gap:5px; align-items:center; cursor:pointer; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  figure { margin:0; min-width:0; position:relative; }
  figure .tag { position:absolute; top:8px; left:8px; background:rgba(43,27,46,.85); color:#fff; font-weight:700; font-size:20px; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; }
  figure img { width:100%; max-height:66vh; object-fit:contain; border:1px solid var(--line); background:#111; display:block; }
  figure.win img { outline:3px solid var(--ok); }
  figcaption { font-size:12px; color:var(--muted); margin-top:5px; min-height:16px; display:flex; justify-content:space-between; gap:8px; }
  .btns { display:grid; grid-template-columns:repeat(4, 1fr) auto auto; gap:8px; }
  .btns button { padding:12px 10px; border:1px solid var(--line); background:#fafafa; border-radius:8px; cursor:pointer; font:inherit; font-weight:600; }
  .btns button.a, .btns button.b { background:var(--accent); color:#fff; border-color:var(--accent); }
  .btns button kbd { font:11px ui-monospace, Menlo, monospace; background:rgba(0,0,0,.12); padding:1px 5px; border-radius:4px; margin-left:6px; }
  .btns button:disabled { opacity:.5; cursor:default; }
  .stats { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:12px; color:#444; }
  .stats b { font-weight:600; }
  .last { font-size:12px; color:#444; margin-top:6px; min-height:16px; }
  .last .ok { color:var(--ok); } .last .bad { color:var(--bad); }
  .err { background:#fdecec; color:#8a1f1f; padding:10px; border-radius:8px; white-space:pre-wrap; font-size:12px; }
  .hint { color:var(--muted); font-size:13px; padding:30px; text-align:center; }
  .bd { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px,1fr)); gap:2px 12px; font-size:11px; color:#555; margin-top:6px; }
  .hidden { display:none !important; }
</style></head>
<body>
<header><h1>Label pairs</h1><span>which of the two looks better designed for this canvas?</span><span style="margin-left:auto"><a href="/">← Playground</a> &nbsp; <a href="/eval">Eval browser</a></span></header>
<main>
  <div class="panel ctl">
    <label>Mode <select id="mode"><option value="candidates">two candidates of the engine</option><option value="runs">two harness runs</option></select></label>
    <label id="runsCtl" class="hidden">A run <select id="runA"></select> &nbsp; B run <select id="runB"></select></label>
    <label><input type="checkbox" id="reveal"> show names and scores before deciding</label>
    <span style="margin-left:auto;color:var(--muted)">keys: <b>a</b> / <b>b</b> better · <b>t</b> tie · <b>x</b> both bad · <b>s</b> skip · <b>z</b> undo</span>
  </div>
  <div id="error"></div>
  <div class="panel top">
    <img id="srcImg" alt="source">
    <div class="info" id="info">Loading the first pair…</div>
    <div class="stats" id="stats"></div>
  </div>
  <div class="panel">
    <div class="pair">
      <figure id="figA"><span class="tag">A</span><img id="imgA" alt="A"><figcaption id="capA"></figcaption></figure>
      <figure id="figB"><span class="tag">B</span><img id="imgB" alt="B"><figcaption id="capB"></figcaption></figure>
    </div>
    <div class="bd hidden" id="bd"></div>
  </div>
  <div class="panel">
    <div class="btns">
      <button class="a" data-d="a">A better<kbd>a</kbd></button>
      <button data-d="tie">Tie<kbd>t</kbd></button>
      <button class="b" data-d="b">B better<kbd>b</kbd></button>
      <button data-d="both_bad">Both bad<kbd>x</kbd></button>
      <button id="skip">Skip<kbd>s</kbd></button>
      <button id="undo">Undo<kbd>z</kbd></button>
    </div>
    <div class="last" id="last"></div>
  </div>
</main>
<script>
const $ = s => document.querySelector(s);
let cur = null, nextP = null, shownAt = 0, busy = false, stats = null;
function qs() { const p = new URLSearchParams(); p.set('mode', $('#mode').value); if ($('#mode').value === 'runs') { p.set('run_a', $('#runA').value); p.set('run_b', $('#runB').value); } return p.toString(); }
function fetchPair() { return fetch('/api/label/next?' + qs()).then(r => r.json()); }
function prefetch() { nextP = fetchPair(); }
function fmtHard(h) { return h && h.length ? ` · <span style="color:var(--bad)">${h.length} hard</span>` : ''; }
function renderStats(s) {
  stats = s; if (!s) return;
  const fam = Object.entries(s.by_tgt_family || {}).map(([k,v]) => `${k} ${v}`).join(' · ') || '—';
  const agree = s.scorer_n ? `${s.scorer_agree}/${s.scorer_n} (${(100*s.scorer_agree/s.scorer_n).toFixed(0)}%)` : '—';
  const dec = Object.entries(s.by_decision || {}).map(([k,v]) => `${k} ${v}`).join(' · ') || '—';
  $('#stats').innerHTML = `<span><b>${s.n}</b> labels · ${s.designs} designs</span><span>scorer agrees <b>${agree}</b></span><span>by target: ${fam}</span><span>decisions: ${dec}</span>`;
}
function show(rec) {
  cur = rec; shownAt = performance.now();
  $('#error').innerHTML = '';
  $('#srcImg').src = 'data:image/png;base64,' + rec.source_png;
  $('#imgA').src = 'data:image/png;base64,' + rec.a_png;
  $('#imgB').src = 'data:image/png;base64,' + rec.b_png;
  const c = rec.a.design.canvas;
  $('#info').innerHTML = `<b>${rec.title || rec.design_id}</b> <span style="color:var(--muted)">${rec.design_id}</span><br>${rec.src_family} source → <b>${rec.preset}</b> ${rec.target.width}×${rec.target.height} (${rec.tgt_family}, shape change ${(+rec.ratio_change).toFixed(2)}×)<br><span style="color:var(--muted)">${rec.mode === 'runs' ? 'runs ' + rec.runs.join(' vs ') : 'two engine candidates'} · rendered in ${(rec.render_elapsed*1000).toFixed(0)} ms</span>`;
  ['A','B'].forEach(k => { $('#fig'+k).classList.remove('win'); });
  reveal($('#reveal').checked);
  document.querySelectorAll('.btns button').forEach(b => b.disabled = false);
}
function reveal(on) {
  if (!cur) return;
  const cap = (s) => on ? `<span>${s.name}</span><span>${(+s.total).toFixed(1)}${fmtHard(s.hard)}</span>` : '<span>&nbsp;</span>';
  $('#capA').innerHTML = cap(cur.a); $('#capB').innerHTML = cap(cur.b);
  $('#bd').classList.toggle('hidden', !on);
  if (on) $('#bd').innerHTML = Object.keys(cur.a.breakdown).map(k => { const a = cur.a.breakdown[k], b = cur.b.breakdown[k]; const d = a - b; return `<span>${k}: ${a.toFixed(2)} vs ${b.toFixed(2)} <b style="color:${d>0.005?'var(--ok)':d<-0.005?'var(--bad)':'#999'}">${d>0?'+':''}${d.toFixed(2)}</b></span>`; }).join('');
}
async function advance() {
  busy = true; document.querySelectorAll('.btns button').forEach(b => b.disabled = true);
  $('#info').innerHTML = 'Rendering the next pair…';
  try {
    const rec = await (nextP || fetchPair());
    nextP = null;
    if (rec.error) throw new Error(rec.error);
    show(rec);
    prefetch();
  } catch (e) {
    $('#error').innerHTML = `<div class="err">${e.message}</div><button id="retry" style="margin-top:8px">Retry</button>`;
    $('#retry').addEventListener('click', () => { nextP = null; advance(); });
    $('#undo').disabled = false; $('#skip').disabled = false;
  }
  busy = false;
}
async function decide(d) {
  if (!cur || busy) return;
  busy = true;
  const pair = cur, seconds = (performance.now() - shownAt) / 1000;
  const r = await (await fetch('/api/label/save', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pair, decision: d, seconds})})).json();
  busy = false;
  if (r.error) { $('#error').innerHTML = `<div class="err">${r.error}</div>`; return; }
  renderStats(r.stats);
  const s = r.saved, scorer = s.scorer, agree = (d === 'a' || d === 'b') ? (scorer === d ? '<span class="ok">scorer agreed</span>' : `<span class="bad">scorer picked ${scorer.toUpperCase()}</span>`) : `scorer picked ${scorer}`;
  $('#last').innerHTML = `Saved: <b>${s.case_key}</b> — you said <b>${d}</b>, ${agree}. A = ${pair.a.name} (${(+pair.a.total).toFixed(1)}${pair.a.hard.length?', '+pair.a.hard.length+' hard':''}), B = ${pair.b.name} (${(+pair.b.total).toFixed(1)}${pair.b.hard.length?', '+pair.b.hard.length+' hard':''})`;
  advance();
}
async function undo() {
  if (busy) return;
  const r = await (await fetch('/api/label/undo', {method:'POST'})).json();
  if (r.error) { $('#error').innerHTML = `<div class="err">${r.error}</div>`; return; }
  renderStats(r.stats);
  $('#last').innerHTML = r.removed ? `Undone: <b>${r.removed.case_key}</b> (was <b>${r.removed.decision}</b>). ${r.stats.n} labels left.` : 'Nothing to undo.';
}
async function init() {
  const d = await (await fetch('/api/label/stats')).json();
  renderStats(d.stats);
  const opts = (d.runs || []).map(r => `<option value="${r.name}">${r.name} (${r.cases})</option>`).join('');
  $('#runA').innerHTML = opts; $('#runB').innerHTML = opts;
  if (d.runs && d.runs.length > 1) $('#runB').selectedIndex = d.runs.length - 1;
  $('#mode').addEventListener('change', () => { $('#runsCtl').classList.toggle('hidden', $('#mode').value !== 'runs'); nextP = null; advance(); });
  ['#runA', '#runB'].forEach(s => $(s).addEventListener('change', () => { nextP = null; advance(); }));
  $('#reveal').addEventListener('change', () => reveal($('#reveal').checked));
  document.querySelectorAll('.btns button[data-d]').forEach(b => b.addEventListener('click', () => decide(b.dataset.d)));
  $('#skip').addEventListener('click', () => { if (!busy) advance(); });
  $('#undo').addEventListener('click', undo);
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.metaKey || e.ctrlKey) return;
    const k = e.key.toLowerCase();
    if (k === 'a' || k === 'arrowleft') decide('a'); else if (k === 'b' || k === 'arrowright') decide('b');
    else if (k === 't') decide('tie'); else if (k === 'x') decide('both_bad');
    else if (k === 's') { if (!busy) advance(); } else if (k === 'z') undo();
    else if (k === 'r') { $('#reveal').checked = !$('#reveal').checked; reveal($('#reveal').checked); }
  });
  advance();
}
init();
</script>
</body></html>
"""


def main(argv: list[str] | None = None) -> None:
    import argparse
    import os

    ap = argparse.ArgumentParser(description="Chameleon playground / eval browser / labelling page")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or PORT))
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Chameleon playground: http://localhost:{args.port}  (eval browser /eval, labelling /label)")
    server.serve_forever()


if __name__ == "__main__":
    main()
