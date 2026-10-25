"""Source | VLM off | VLM on, one row per labelled case (dev tool, S1).

    .venv/bin/python -m eval.s1_sheet <out_dir> [--cases eval/s1_cases.json] [--cell 420]

Each case is {"design_id", "preset"} (the "both bad" pairs of
docs/LABELS_V1.md by default: eval/data/labels.jsonl rows with decision
both_bad). The design is resized twice, with CHAMELEON_VLM / CHAMELEON_ROLE_MODEL
off and with both on (the 4B model, perception cache under
eval/data/perception/cache), and the three renders go side by side with the
winner's name, the archetype and the roles the vote changed. Writes
<out_dir>/<id>_<WxH>.png per case and <out_dir>/s1_sheet.png.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.run_eval import load_presets  # noqa: E402
from eval.sanity_sheet import BG, GREY, INK, _fit, _font, load_design, render  # noqa: E402

CACHE_DIR = ROOT / "eval" / "data" / "perception" / "cache"
ON = {"CHAMELEON_VLM": "1", "CHAMELEON_ROLE_MODEL": "1", "CHAMELEON_VLM_CACHE_DIR": str(CACHE_DIR),
      "CHAMELEON_VLM_MODEL": str(ROOT / "models" / "Qwen3VL-4B-Instruct-Q4_K_M.gguf"),
      "CHAMELEON_VLM_MMPROJ": str(ROOT / "models" / "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf")}
OFF = {"CHAMELEON_VLM": "0", "CHAMELEON_ROLE_MODEL": "0"}


def both_bad_cases(labels: Path, limit: int) -> list[dict]:
    seen: list[tuple[str, str]] = []
    for line in labels.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("decision") != "both_bad":
            continue
        key = (r["design_id"], r["preset"])
        if key not in seen:
            seen.append(key)
    return [{"design_id": d, "preset": p} for d, p in seen[:limit]]


def set_env(values: dict[str, str]) -> None:
    for k, v in values.items():
        os.environ[k] = v


def run(source: dict, w: int, h: int, env: dict[str, str]):
    from engine import resize as RZ

    set_env(env)
    t0 = time.perf_counter()
    best, judged = RZ.resize_with_candidates(source, {"width": w, "height": h})
    dt = time.perf_counter() - t0
    info = (RZ.LAST_ANALYSIS.perception or {}) if RZ.LAST_ANALYSIS is not None else {}
    changed = []
    for key, d in (info.get("decisions") or {}).items():
        if d.get("role") != d.get("rule"):
            changed.append(f"{key[:14]} {d['rule']}→{d['role']} ({d['by']})")
    return best, judged, dt, info.get("archetype"), info.get("vlm"), changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("--cases", default=None, help="JSON list of {design_id, preset}; default: both-bad labels")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--cell", type=int, default=400)
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    presets = {name: (w, h) for name, w, h in load_presets()}
    cases = json.loads(Path(a.cases).read_text()) if a.cases else both_bad_cases(ROOT / "eval" / "data" / "labels.jsonl", a.limit)

    cell, pad, head = a.cell, 20, 64
    rows_img: list[Image.Image] = []
    summary = []
    for c in cases:
        source, title = load_design(c["design_id"])
        w, h = presets[c["preset"]]
        off, j_off, t_off, _, _, _ = run(source, w, h, OFF)
        on, j_on, t_on, arche, vlm_status, changed = run(source, w, h, ON)
        same = json.dumps(off, sort_keys=True) == json.dumps(on, sort_keys=True)
        row = Image.new("RGB", (pad + 3 * (cell + pad), head + cell + 40), BG)
        d = ImageDraw.Draw(row)
        d.text((pad, 8), f"{title[:48]}  ·  {source['canvas']['width']}x{source['canvas']['height']} → {c['preset']} {w}x{h}"
                         f"  ·  archetype {arche or '–'}  ·  VLM {vlm_status}", fill=INK, font=_font(20, True))
        d.text((pad, 36), ("roles changed: " + "; ".join(changed)[:150]) if changed else "roles: unchanged by the vote",
               fill=GREY, font=_font(15))
        for i, (label, design, judged, dt) in enumerate((("source", source, None, None), ("VLM off", off, j_off, t_off),
                                                         ("VLM + classifier on", on, j_on, t_on))):
            x, y = pad + i * (cell + pad), head
            img = render(design, max_size=max(cell, 600))
            d.rectangle([x, y, x + cell, y + cell], outline=(205, 205, 205))
            if img is not None:
                th = _fit(img, cell, cell)
                row.paste(th, (x + (cell - th.width) // 2, y + (cell - th.height) // 2))
            cap = label
            if judged is not None:
                hard = "; ".join(judged[0].score.hard)[:30]
                cap += f"  ·  {judged[0].name[:28]}  ·  {judged[0].score.total:.1f}  ·  {dt * 1000:.0f} ms"
                if hard:
                    cap += "  ·  HARD " + hard
            if i == 2 and same:
                cap += "  ·  identical to VLM off"
            d.text((x, y + cell + 8), cap[:95], fill=INK, font=_font(14))
        row.save(out / f"{c['design_id']}_{w}x{h}.png")
        rows_img.append(row)
        summary.append({"design_id": c["design_id"], "title": title, "preset": c["preset"], "size": f"{w}x{h}",
                        "archetype": arche, "vlm": vlm_status, "changed": changed, "identical": same,
                        "off": {"winner": j_off[0].name, "total": round(j_off[0].score.total, 2), "hard": j_off[0].score.hard, "s": round(t_off, 2)},
                        "on": {"winner": j_on[0].name, "total": round(j_on[0].score.total, 2), "hard": j_on[0].score.hard, "s": round(t_on, 2)}})
        print(f"{title[:40]:40s} {c['preset']:18s} off={j_off[0].name[:26]:26s} {j_off[0].score.total:6.1f} | "
              f"on={j_on[0].name[:26]:26s} {j_on[0].score.total:6.1f} | {arche} | {'same' if same else 'DIFFERENT'} | {len(changed)} roles", flush=True)
    if rows_img:
        sheet = Image.new("RGB", (rows_img[0].width, sum(r.height for r in rows_img)), BG)
        y = 0
        for r in rows_img:
            sheet.paste(r, (0, y))
            y += r.height
        sheet.save(out / "s1_sheet.png")
    (out / "s1_summary.json").write_text(json.dumps(summary, indent=1))
    print("wrote", out / "s1_sheet.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
