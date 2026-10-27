"""v10 backdrop awareness: measurement helpers (dev tool, not shipped).

    .venv/bin/python -m eval.backdrop_report census                 pattern kinds over the corpus, samples, designer sources
    .venv/bin/python -m eval.backdrop_report moves bg_off bg_on <out_dir> [--n 10]
                                                                   contact sheet of the cases whose headline / subhead /
                                                                   CTA landed on a different backdrop: source | off | on
    .venv/bin/python -m eval.backdrop_report runtime [--limit 40]   single-process runtime p50 / p95, flag off vs on
    .venv/bin/python -m eval.backdrop_report slides bg_on           how often the slide / quiet move / patterns fired
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import backdrop as B  # noqa: E402
from engine.analyze import analyze  # noqa: E402
from engine.geometry import Box  # noqa: E402
from engine.rectify import visible_box  # noqa: E402
from engine.textfit import default_measurer  # noqa: E402
from eval.run_eval import RUNS_DIR, read_results  # noqa: E402

DESIGNS = ROOT / "eval" / "data" / "designs"
INPUT = ROOT / "input"
DESIGNER_SRC = [ROOT.parent / "docs" / "designer", ROOT.parent / "docs" / "designer2"]


def _sources() -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for p in sorted(DESIGNS.glob("*.json")):
        d = json.loads(p.read_text())
        out.append(("corpus", p.stem, d["source"] if "source" in d else d))
    for p in sorted(INPUT.glob("*.json")):
        out.append(("sample", p.stem, json.loads(p.read_text())["source"]))
    seen = {k for _, k, _ in out}
    for folder in DESIGNER_SRC:
        for p in sorted(folder.glob("src_*.json")):
            d = json.loads(p.read_text())
            key = p.stem.split("_", 2)[-1]
            if key in seen:
                continue
            seen.add(key)
            out.append(("designer", key, d["source"] if "source" in d else d))
    return out


def census(_args) -> int:
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    sizes: dict[str, list[int]] = collections.defaultdict(list)
    totals: collections.Counter = collections.Counter()
    for kind, key, src in _sources():
        totals[kind] += 1
        an = analyze(src)
        for p in an.patterns:
            counts[kind][p.kind] += 1
            sizes[p.kind].append(len(p.keys))
    kinds = ("corners", "edge", "diagonal", "mirrored", "scatter")
    print("| set | designs | with a pattern | " + " | ".join(kinds) + " |")
    print("|---|---:|---:|" + "---:|" * len(kinds))
    for kind in ("corpus", "sample", "designer"):
        c = counts[kind]
        print(f"| {kind} | {totals[kind]} | {sum(c.values())} | " + " | ".join(str(c[k]) for k in kinds) + " |")
    print("\nitems per pattern (median): " + ", ".join(f"{k} {statistics.median(v):g}" for k, v in sizes.items()))
    return 0


def _source_of(design_id: str) -> dict[str, Any] | None:
    p = DESIGNS / f"{design_id}.json"
    if p.exists():
        d = json.loads(p.read_text())
        return d["source"] if "source" in d else d
    p = INPUT / f"{design_id}.json"
    if p.exists():
        return json.loads(p.read_text())["source"]
    return None


def _safe(key: str) -> str:
    return key.replace("|", "__").replace(" ", "_").replace("/", "-").replace(":", "-")


def _output_of(run: str, key: str) -> dict[str, Any] | None:
    p = RUNS_DIR / run / "outputs" / f"{_safe(key)}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _text_sigs(design: dict[str, Any], ids: set[str], m) -> dict[str, B.Signature]:
    mp = B.from_json(design)
    if mp is None:
        return {}
    out = {}
    for el in design["elements"]:
        if el["type"] != "text" or el["id"] not in ids or not str(el.get("content", "")).strip():
            continue
        ink = visible_box(el, Box.of(el), float(el["font_size"]), m)
        out[el["id"]] = mp.signature(ink)
    return out


def moves(args) -> int:
    from eval.sanity_sheet import _font, _fit, render
    from PIL import Image, ImageDraw

    m = default_measurer()
    a_rows = {r["key"]: r for r in read_results(RUNS_DIR / args.off) if r.get("key")}
    b_rows = {r["key"]: r for r in read_results(RUNS_DIR / args.on) if r.get("key")}
    keys = sorted(set(a_rows) & set(b_rows))
    found: list[dict[str, Any]] = []
    cache: dict[str, Any] = {}
    for key in keys:
        row = b_rows[key]
        did = row["design_id"]
        if did not in cache:
            src = _source_of(did)
            cache[did] = (src, analyze(src)) if src else (None, None)
        src, an = cache[did]
        if src is None:
            continue
        off, on = _output_of(args.off, key), _output_of(args.on, key)
        if off is None or on is None:
            continue
        ids = {eid for eid, r in an.roles.items() if r in B.JUDGE_ROLES and an.source_elements[eid]["type"] == "text"}
        if not ids:
            continue
        s_src = _text_sigs(src, ids, m)
        s_off, s_on = _text_sigs(off, ids, m), _text_sigs(on, ids, m)
        for eid in ids:
            if eid not in s_src or eid not in s_off or eid not in s_on:
                continue
            change = B.distance(s_off[eid], s_on[eid])
            d_off, d_on = B.distance(s_src[eid], s_off[eid]), B.distance(s_src[eid], s_on[eid])
            if change >= args.min_change:
                found.append({"key": key, "design_id": did, "eid": eid, "role": an.roles[eid], "change": change,
                              "d_off": d_off, "d_on": d_on, "gain": d_off - d_on,
                              "win_off": a_rows[key].get("winner"), "win_on": row.get("winner"),
                              "hard_off": a_rows[key].get("judge_hard_n"), "hard_on": row.get("judge_hard_n"),
                              "score_off": a_rows[key].get("score_total"), "score_on": row.get("score_total")})
    found.sort(key=lambda f: -f["change"])
    # one row per case; the biggest change first
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in found:
        if f["key"] in seen:
            continue
        seen.add(f["key"])
        picked.append(f)
        if len(picked) >= args.n:
            break
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "backdrop_moves.json").write_text(json.dumps(picked, indent=1))
    print(f"{len(found)} text moves onto a different backdrop in {len(keys)} common cases; showing {len(picked)}")
    cell, pad, head = 360, 16, 46
    cols = 3
    sheet = Image.new("RGB", (pad + cols * (cell + pad), 50 + len(picked) * (cell + head + pad)), (245, 241, 234))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), f"v10 backdrop: texts that landed on a different backdrop  ({args.off} | {args.on})",
           fill=(34, 34, 34), font=_font(22, True))
    for i, f in enumerate(picked):
        src, an = cache[f["design_id"]]
        off, on = _output_of(args.off, f["key"]), _output_of(args.on, f["key"])
        y = 50 + i * (cell + head + pad)
        for c, (label, design) in enumerate((("source", src), (args.off, off), (args.on, on))):
            x = pad + c * (cell + pad)
            img = render(design, max_size=cell)
            d.rectangle([x, y, x + cell, y + cell], outline=(205, 205, 205))
            if img is not None:
                k = img.width / float(design["canvas"]["width"])
                el = next(e for e in design["elements"] if e["id"] == f["eid"])
                dd = ImageDraw.Draw(img)
                b = Box.of(el)
                dd.rectangle([b.x * k, b.y * k, b.right * k, b.bottom * k], outline=(255, 0, 180), width=2)
                th = _fit(img, cell, cell)
                sheet.paste(th, (x + (cell - th.width) // 2, y + (cell - th.height) // 2))
            d.text((x, y + cell + 4), label, fill=(34, 34, 34), font=_font(15, True))
        info = (f"{f['design_id'][:12]} {f['key'].split('|')[-1]}  {f['role']} {f['eid']}: distance to the source backdrop "
                f"{f['d_off']:.2f} -> {f['d_on']:.2f}  judge {f['score_off']} -> {f['score_on']}  hard {f['hard_off']} -> {f['hard_on']}")
        d.text((pad, y + cell + 22), info[:150], fill=(90, 90, 90), font=_font(13))
        d.text((pad, y + cell + 36), f"winner {str(f['win_off'])[:40]} -> {str(f['win_on'])[:40]}", fill=(120, 120, 120), font=_font(12))
    sheet.save(out / "backdrop_moves.png")
    print("wrote", out / "backdrop_moves.png")
    better = sum(f["gain"] > 0.05 for f in found)
    worse = sum(f["gain"] < -0.05 for f in found)
    print(f"of all {len(found)} moves: closer to the source backdrop {better}, farther {worse}, about the same {len(found) - better - worse}")
    return 0


def runtime(args) -> int:
    from engine.resize import resize_with_candidates
    from eval.run_eval import load_presets

    presets = load_presets()
    sources = [s for s in _sources() if s[0] == "sample"] + [s for s in _sources() if s[0] == "corpus"][: args.limit]
    for flag in ("0", "1"):
        os.environ["CHAMELEON_BACKGROUND"] = flag
        times = []
        for _, _, src in sources:
            for _name, w, h in presets:
                t0 = time.perf_counter()
                resize_with_candidates(src, {"width": w, "height": h})
                times.append(time.perf_counter() - t0)
        times.sort()
        p = lambda q: times[min(len(times) - 1, int(round(q * (len(times) - 1))))]
        print(f"flag {flag}: {len(times)} tasks, p50 {p(0.5):.3f} s, p95 {p(0.95):.3f} s, mean {statistics.fmean(times):.3f} s")
    return 0


def slides(args) -> int:
    """How often the v10 mechanisms acted in a run: the winner's notes name
    a slide, a quiet move or a '+fix:...quiet area' candidate; patterns are
    counted from the analysis."""
    rows = read_results(RUNS_DIR / args.run)
    quiet_wins = sum("quiet area" in str(r.get("winner", "")) for r in rows)
    strat = collections.Counter(r.get("strategy") for r in rows)
    print(f"{len(rows)} cases; winner strategies {dict(strat)}; a 'quiet area' repair won {quiet_wins}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("census").set_defaults(fn=census)
    mv = sub.add_parser("moves")
    mv.add_argument("off")
    mv.add_argument("on")
    mv.add_argument("out")
    mv.add_argument("--n", type=int, default=10)
    mv.add_argument("--min-change", type=float, default=0.25)
    mv.set_defaults(fn=moves)
    rt = sub.add_parser("runtime")
    rt.add_argument("--limit", type=int, default=40)
    rt.set_defaults(fn=runtime)
    sl = sub.add_parser("slides")
    sl.add_argument("run")
    sl.set_defaults(fn=slides)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
