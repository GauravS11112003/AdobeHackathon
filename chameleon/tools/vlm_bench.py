"""Benchmark candidate VLMs (GGUF under models/) on rendered designs.

For every model: load time, then on N designs (the three samples + a
deterministic slice of eval/data/designs):

  (i)  set-of-marks role labelling: numbered boxes are drawn over the source
       render; the model returns {number: role}; agreement is measured
       against the analyzer's roles and, for the samples, the roles implied
       by the element ids (headline, cta, badge1_bg, ...). Run at 448 and 672 px.
  (ii) a pairwise rubric judgement: the source render (good) next to a copy
       where 40 % of the content elements were shifted by 30 % of the canvas
       (bad), labelled A/B in random order; the model says which is better.

Per call: prefill time (image encode + prompt), generation time, tokens,
tokens/s. Results go to eval/data/vlm_bench/<model>.json and a markdown
summary is printed (copied into docs/VLM_BENCH.md by hand).

    .venv/bin/python tools/vlm_bench.py --models qwen3vl-2b,qwen3vl-4b --n 20
    .venv/bin/python tools/vlm_bench.py --summarize           # tables from saved JSON
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from engine import analyze as A  # noqa: E402
from engine import render as R  # noqa: E402
from engine import vlm  # noqa: E402
from engine.rectify import unwanted_overlaps  # noqa: E402

# name -> (text model, mmproj[, chat template for GGUFs that carry none])
MODELS = {
    "qwen3vl-2b": ("Qwen3VL-2B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"),
    "qwen3vl-4b": ("Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"),
    "qwen25vl-3b": ("Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf", "mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf"),
    # fast tier
    "lfm2vl-1.6b": ("LFM2-VL-1.6B-Q4_0.gguf", "mmproj-LFM2-VL-1.6B-Q8_0.gguf"),
    "smolvlm2-500m": ("SmolVLM2-500M-Video-Instruct-Q8_0.gguf", "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf"),
    "moondream2": ("moondream2-text-model-f16_ct-vicuna.gguf", "moondream2-mmproj-f16-20250414.gguf",
                   # moondream2's GGUF has no usable chat template ("vicuna"); its native
                   # format is "<image>\n\nQuestion: ...\n\nAnswer:" (the first content part
                   # is the image marker, the rest is the prompt)
                   "{% for message in messages %}{% if message['role'] == 'user' %}"
                   "{% for part in message['content'] %}{% if loop.first %}{{ part['text'] }}\n\nQuestion: "
                   "{% elif part['type'] == 'text' %}{{ part['text'] }}{% endif %}{% endfor %}"
                   "\n\nAnswer:{% endif %}{% endfor %}"),
}
OUT_DIR = ROOT / "eval" / "data" / "vlm_bench"
DOC_IMG_DIR = ROOT.parent / "docs" / "vlm_bench"

ROLES = ["logo", "hero", "image", "headline", "subhead", "body", "cta", "badge",
         "fine_print", "decorative", "panel", "shape"]
ROLE_HELP = {
    "logo": "brand logo",
    "hero": "the main product photo or key image",
    "image": "another, secondary photo or illustration",
    "headline": "the main message, the largest or most prominent text",
    "subhead": "supporting text under or near the headline",
    "body": "longer descriptive text",
    "cta": "a button or call-to-action label (e.g. Shop now, Learn more)",
    "badge": "a small sticker, pill, label, tag or ribbon (e.g. NEW, 50% OFF)",
    "fine_print": "legal, disclaimer or very small text",
    "decorative": "an ornamental shape with no content (circle, blob, line)",
    "panel": "a large flat colour area that sits behind other content",
    "shape": "any other shape",
}
# the sample ids say what each element is (hidden tasks will not)
KNOWN_BY_ID = [("bg", "background"), ("logo", "logo"), ("headline", "headline"), ("subhead", "subhead"),
               ("cta", "cta"), ("badge", "badge"), ("ribbon", "badge"), ("product", "hero"),
               ("deco", "decorative"), ("legal", "fine_print"), ("watermark", "image")]
# roles that are interchangeable for a layout engine (coarse agreement)
COARSE = {"hero": "picture", "image": "picture", "badge": "minor", "shape": "minor", "decorative": "minor",
          "panel": "minor", "subhead": "secondary", "body": "secondary", "fine_print": "secondary"}


# ---------------------------------------------------------------------------
# designs


def load_designs(n: int, seed: int = 0) -> list[dict]:
    out = []
    for f in sorted((ROOT / "input").glob("*.json")):
        task = json.loads(f.read_text())
        out.append({"id": f.stem.replace("chameleon_sample_", ""), "source": task["source"], "sample": True})
    pool = sorted((ROOT / "eval" / "data" / "designs").glob("*.json"))
    rng = random.Random(seed)
    rng.shuffle(pool)
    for f in pool:
        if len(out) >= n:
            break
        d = json.loads(f.read_text())
        src = d.get("source", d)
        n_content = sum(1 for e in src["elements"] if e["type"] != "image" or e["width"] * e["height"]
                        < 0.9 * src["canvas"]["width"] * src["canvas"]["height"])
        if n_content < 3 or len(src["elements"]) > 14:
            continue
        out.append({"id": d.get("id", f.stem), "source": src, "sample": False})
    return out[:n]


def known_roles(source: dict) -> dict[str, str]:
    roles = {}
    for el in source["elements"]:
        for key, role in KNOWN_BY_ID:
            if key in el["id"].lower():
                roles[el["id"]] = role
                break
    return roles


# ---------------------------------------------------------------------------
# set of marks


def marks(source: dict, analysis: A.Analysis) -> list[dict]:
    """One mark per unit (groups as one box), reading order, backgrounds skipped."""
    units = [u for u in analysis.units if u.role != A.BACKGROUND]
    units.sort(key=lambda u: (round(u.box.y / 40.0), u.box.x))
    out = []
    for i, u in enumerate(units, 1):
        out.append({"n": i, "ids": list(u.ids), "role": u.role, "box": [u.box.x, u.box.y, u.box.w, u.box.h]})
    return out


def draw_marks(img: Image.Image, source: dict, mk: list[dict]) -> Image.Image:
    s = img.width / float(source["canvas"]["width"])
    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    size = max(14, int(img.width / 36))
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:  # old Pillow
        font = ImageFont.load_default()
    lw = max(2, int(img.width / 300))
    for m in mk:
        x, y, w, h = [v * s for v in m["box"]]
        d.rectangle([x, y, x + w, y + h], outline=(255, 0, 200), width=lw)
        label = str(m["n"])
        tw = d.textlength(label, font=font)
        tx, ty = max(0, x), max(0, y - size - 4)
        if ty < 0:
            ty = y
        d.rectangle([tx, ty, tx + tw + 8, ty + size + 4], fill=(255, 0, 200))
        d.text((tx + 4, ty + 1), label, fill=(255, 255, 255), font=font)
    return out


def hints(source: dict, mk: list[dict]) -> str:
    """What the engine knows about each box without looking: element types
    and the text they contain (hidden tasks give type and content too)."""
    by_id = {e["id"]: e for e in source["elements"]}
    lines = []
    for m in mk:
        els = [by_id[i] for i in m["ids"]]
        kinds = []
        for e in els:
            if e["type"] == "text":
                t = " ".join(str(e.get("content", "")).split())
                kinds.append("text \"%s\"" % (t[:50] + ("..." if len(t) > 50 else "")))
            elif e["type"] == "image":
                kinds.append("image")
            else:
                kinds.append("shape")
        lines.append("%d: %s" % (m["n"], " + ".join(kinds)))
    return "\n".join(lines)


def som_prompt(mk: list[dict], hint_text: str | None = None) -> tuple[str, dict]:
    n = len(mk)
    roles_txt = "; ".join("%s = %s" % (r, ROLE_HELP[r]) for r in ROLES)
    prompt = (
        "This is a marketing design. %d numbered magenta boxes are drawn over its elements "
        "(the number tag sits at the top-left corner of each box). For every box number say what "
        "the element inside it is. Roles: %s. "
        % (n, roles_txt)
    )
    if hint_text:
        prompt += "The boxes contain:\n%s\nJudge their role from how they look and where they sit. " % hint_text
    prompt += "Reply with JSON only: {\"roles\": {\"1\": role, ..., \"%d\": role}}." % n
    schema = {
        "type": "object",
        "properties": {"roles": {
            "type": "object",
            "properties": {str(m["n"]): {"type": "string", "enum": ROLES} for m in mk},
            "required": [str(m["n"]) for m in mk],
            "additionalProperties": False,
        }},
        "required": ["roles"],
        "additionalProperties": False,
    }
    return prompt, schema


# ---------------------------------------------------------------------------
# pairwise judgement


def perturb(source: dict, analysis: A.Analysis, seed: int, frac: float = 0.4, shift: float = 0.3) -> dict:
    rng = random.Random(seed)
    bad = copy.deepcopy(source)
    cw, ch = source["canvas"]["width"], source["canvas"]["height"]
    content = [u for u in analysis.content_units()]
    k = max(1, round(frac * len(content)))
    chosen = rng.sample(content, k) if len(content) >= k else content
    by_id = {e["id"]: e for e in bad["elements"]}
    for u in chosen:
        axis = rng.choice(["x", "y"])
        sign = rng.choice([-1, 1])
        dx = dy = 0.0
        for ax in (axis, "y" if axis == "x" else "x"):
            if ax == "x":
                room_neg, room_pos, d = u.box.x, cw - (u.box.x + u.box.w), shift * cw
            else:
                room_neg, room_pos, d = u.box.y, ch - (u.box.y + u.box.h), shift * ch
            # move the full distance in the chosen direction, else the other
            # way, else as far as the canvas allows on this axis
            if sign < 0 and room_neg >= d:
                move = -d
            elif sign > 0 and room_pos >= d:
                move = d
            elif room_neg >= d:
                move = -d
            elif room_pos >= d:
                move = d
            else:
                move = -room_neg if room_neg >= room_pos else room_pos
            if abs(move) >= 0.5 * d:
                if ax == "x":
                    dx = move
                else:
                    dy = move
                break
        for eid in u.ids:
            e = by_id[eid]
            e["x"] = round(e["x"] + dx, 2)
            e["y"] = round(e["y"] + dy, 2)
    return bad


def side_by_side(a: Image.Image, b: Image.Image, labels=("A", "B")) -> Image.Image:
    gap = 24
    h = max(a.height, b.height)
    size = max(18, h // 24)
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    top = size + 12
    out = Image.new("RGB", (a.width + b.width + gap, h + top), (255, 255, 255))
    out.paste(a, (0, top))
    out.paste(b, (a.width + gap, top))
    d = ImageDraw.Draw(out)
    d.text((a.width // 2 - size // 3, 4), labels[0], fill=(0, 0, 0), font=font)
    d.text((a.width + gap + b.width // 2 - size // 3, 4), labels[1], fill=(0, 0, 0), font=font)
    d.rectangle([a.width, 0, a.width + gap, h + top], fill=(128, 128, 128))
    return out


PAIR_PROMPT = (
    "Two versions of the same marketing design are shown side by side: A on the left, B on the right. "
    "One of them is the designer's original; in the other some elements were moved so that they overlap, "
    "misalign or sit awkwardly. Judge them like an art director: no unwanted overlaps or collisions, "
    "text readable, balanced and intentional composition. Which one is the better design? "
    "Reply with JSON only: {\"better\": \"A\" or \"B\", \"reason\": short sentence}."
)
PAIR2_PROMPT = (
    "Image 1 and Image 2 are two versions of the same marketing design. One is the designer's original; "
    "in the other some elements were moved so that they overlap, misalign or sit awkwardly. Judge them "
    "like an art director: no unwanted overlaps or collisions, text readable, balanced and intentional "
    "composition. Which image is the better design? Reply with JSON only: "
    "{\"better\": 1 or 2, \"reason\": short sentence}."
)
PAIR2_SCHEMA = {
    "type": "object",
    "properties": {"better": {"type": "integer", "enum": [1, 2]},
                   "reason": {"type": "string", "maxLength": 160}},
    "required": ["better", "reason"],
    "additionalProperties": False,
}
ABS_KEYS = ("overlap_free", "readable", "balanced", "intentional")
ABS_PROMPT = (
    "Rate this marketing design like an art director. Give a score from 1 (worst) to 5 (best) for each of: "
    "overlap_free (5 = no element overlaps or cuts off another, 1 = bad collisions), readable (5 = all text "
    "legible and uncramped), balanced (5 = aligned, evenly spaced, visually balanced), intentional (5 = looks "
    "deliberately designed, 1 = looks accidental). Reply with JSON only: {\"overlap_free\": n, \"readable\": n, "
    "\"balanced\": n, \"intentional\": n}."
)
ABS_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "integer", "minimum": 0, "maximum": 5} for k in ABS_KEYS},
    "required": list(ABS_KEYS),
    "additionalProperties": False,
}
PAIR_SCHEMA = {
    "type": "object",
    "properties": {"better": {"type": "string", "enum": ["A", "B"]},
                   "reason": {"type": "string", "maxLength": 160}},
    "required": ["better", "reason"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# running


def use_model(name: str, threads: int | None) -> None:
    text, proj = MODELS[name][:2]
    vlm._reset_for_tests()
    os.environ["CHAMELEON_VLM_MODEL"] = str(ROOT / "models" / text)
    os.environ["CHAMELEON_VLM_MMPROJ"] = str(ROOT / "models" / proj)
    os.environ.pop("CHAMELEON_VLM_CHAT_TEMPLATE", None)
    if len(MODELS[name]) > 2:
        os.environ["CHAMELEON_VLM_CHAT_TEMPLATE"] = MODELS[name][2]
    if threads:
        os.environ["CHAMELEON_VLM_THREADS"] = str(threads)


def release_model() -> None:
    b = vlm._state.get("backend")
    if b is not None and hasattr(b, "llm"):
        try:
            b.llm.close()
        except Exception:
            pass
    vlm.set_backend(None)
    import gc
    gc.collect()


def timing() -> dict:
    last = vlm.stats()["last"]
    out = {k: round(v, 3) if isinstance(v, float) else v for k, v in last.items()}
    if last.get("gen_s") and last.get("gen_tokens"):
        out["tok_s"] = round(last["gen_tokens"] / last["gen_s"], 2)
    return out


def run_model(name: str, designs: list[dict], sides: list[int], pair_sides: list[int],
              threads: int | None, timeout: float, save_images: bool,
              probes: tuple[str, ...] = ("som", "pair", "absolute")) -> dict:
    use_model(name, threads)
    t0 = time.perf_counter()
    backend = vlm.load()
    if backend is None:
        raise RuntimeError("could not load %s: %s" % (name, vlm.status()))
    load_s = time.perf_counter() - t0
    print("[%s] loaded in %.1fs (%d threads)" % (name, load_s, backend.n_threads), flush=True)
    rec = {"model": name, "files": MODELS[name][:2], "load_s": round(load_s, 2), "threads": backend.n_threads,
           "sizes_mb": [round((ROOT / "models" / f).stat().st_size / 1e6, 1) for f in MODELS[name][:2]],
           "designs": []}
    previous = {}
    if (OUT_DIR / (name + ".json")).is_file():      # a partial rerun keeps the other probes' results
        try:
            previous = {d["id"]: d for d in json.loads((OUT_DIR / (name + ".json")).read_text())["designs"]}
        except Exception:
            previous = {}
    DOC_IMG_DIR.mkdir(parents=True, exist_ok=True)
    for di, d in enumerate(designs):
        src = d["source"]
        analysis = A.analyze(src)
        R.begin_task()                      # the renderer's per-task budget: one "task" per design here
        img = R.render_design(src, max_size=896)
        if img is None:
            print("  %s: no render, skipped" % d["id"])
            continue
        mk = marks(src, analysis)
        marked = draw_marks(img, src, mk)
        if save_images and di < 4:
            marked.save(DOC_IMG_DIR / ("som_%s.png" % d["id"]))
        known = known_roles(src) if d["sample"] else {}
        entry = previous.get(d["id"]) or {"id": d["id"], "sample": d["sample"], "n_marks": len(mk), "som": {}, "pair": {}}
        hint_text = hints(src, mk)
        for variant in ("plain", "hinted") if "som" in probes else ():
            prompt, schema = som_prompt(mk, hint_text if variant == "hinted" else None)
            for side in sides:
                t = time.perf_counter()
                out = vlm.describe(marked, prompt, schema, max_tokens=24 + 8 * len(mk), timeout_s=timeout,
                                   max_side=side, use_cache=False)
                dt = time.perf_counter() - t
                r = {"ok": out is not None, "total_s": round(dt, 2), "timing": timing(), "roles": {}}
                if out:
                    roles = out["roles"]
                    exact = coarse = known_hits = known_n = 0
                    for m in mk:
                        got = roles.get(str(m["n"]))
                        r["roles"][str(m["n"])] = got
                        exact += got == m["role"]
                        coarse += COARSE.get(got, got) == COARSE.get(m["role"], m["role"])
                        kr = {known[i] for i in m["ids"] if i in known}
                        if kr:
                            known_n += 1
                            known_hits += got in kr
                    r.update({"agree_exact": exact / len(mk), "agree_coarse": coarse / len(mk),
                              "known_n": known_n, "known_hits": known_hits})
                entry["som"]["%s@%d" % (variant, side)] = r
                print("  %s som %s@%d: %s %.1fs %s" % (
                    d["id"], variant, side, "ok" if out else "FAIL", dt,
                    ("exact %.2f coarse %.2f" % (r["agree_exact"], r["agree_coarse"])) if out else ""), flush=True)
        # pairwise: composite A|B and two images, both orders; absolute scores
        bad = perturb(src, analysis, seed=di)
        entry["bad_collisions"] = len(unwanted_overlaps(analysis, bad["elements"]))
        bad_img = R.render_design(bad, max_size=896)
        if bad_img is not None and pair_sides:
            side = pair_sides[0]
            if save_images and di < 4:
                side_by_side(img, bad_img).save(DOC_IMG_DIR / ("pair_%s.png" % d["id"]))
            for mode in ("composite", "two_images") if "pair" in probes else ():
                picks = []
                for good_first in (True, False):
                    t = time.perf_counter()
                    if mode == "composite":
                        pair = side_by_side(img, bad_img) if good_first else side_by_side(bad_img, img)
                        out = vlm.describe(pair, PAIR_PROMPT, PAIR_SCHEMA, max_tokens=64, timeout_s=timeout,
                                           max_side=side, use_cache=False)
                        pick = {"A": 1, "B": 2}.get(out["better"]) if out else None
                    else:
                        ims = [img, bad_img] if good_first else [bad_img, img]
                        out = vlm.describe(ims, PAIR2_PROMPT, PAIR2_SCHEMA, max_tokens=64, timeout_s=timeout,
                                           max_side=side, use_cache=False)
                        pick = out["better"] if out else None
                    dt = time.perf_counter() - t
                    good_pos = 1 if good_first else 2
                    picks.append({"ok": out is not None, "total_s": round(dt, 2), "timing": timing(),
                                  "good_pos": good_pos, "pick": pick,
                                  "correct": (pick == good_pos) if pick else None,
                                  "reason": (out or {}).get("reason", "")})
                both = all(p["correct"] for p in picks)
                entry["pair"]["%s@%d" % (mode, side)] = {"orders": picks, "correct_both": both,
                                                        "position_locked": picks[0]["pick"] == picks[1]["pick"]}
                print("  %s pair %s@%d: %s" % (d["id"], mode, side,
                                                "correct in both orders" if both else
                                                ("position-locked" if picks[0]["pick"] == picks[1]["pick"] else "wrong")), flush=True)
            scores = []
            for which, im in (("good", img), ("bad", bad_img)) if "absolute" in probes else ():
                t = time.perf_counter()
                out = vlm.describe(im, ABS_PROMPT, ABS_SCHEMA, max_tokens=48, timeout_s=timeout,
                                   max_side=side, use_cache=False)
                scores.append({"ok": out is not None, "total_s": round(time.perf_counter() - t, 2),
                               "timing": timing(), "which": which, "scores": out,
                               "sum": sum(out.values()) if out else None})
            if scores:
                ok = all(sc["ok"] for sc in scores)
                entry["pair"]["absolute@%d" % side] = {"renders": scores,
                                                       "correct": ok and scores[0]["sum"] > scores[1]["sum"],
                                                       "tie": ok and scores[0]["sum"] == scores[1]["sum"]}
                print("  %s absolute@%d: good %s bad %s" % (d["id"], side, scores[0]["sum"], scores[1]["sum"]), flush=True)
        rec["designs"].append(entry)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / (name + ".json")).write_text(json.dumps(rec, indent=1))
    release_model()
    return rec


# ---------------------------------------------------------------------------
# summary


def _med(rows, key):
    vals = [r["timing"].get(key) for r in rows if r["timing"].get(key) is not None]
    return statistics.median(vals) if vals else 0.0


def ensure_collisions(rec: dict) -> None:
    """Older records: recompute how many collisions the perturbation caused."""
    if all("bad_collisions" in d for d in rec["designs"]):
        return
    designs = {d["id"]: d for d in load_designs(len(rec["designs"]) + 5)}
    for di, d in enumerate(rec["designs"]):
        if "bad_collisions" in d or d["id"] not in designs:
            continue
        src = designs[d["id"]]["source"]
        analysis = A.analyze(src)
        d["bad_collisions"] = len(unwanted_overlaps(analysis, perturb(src, analysis, seed=di)["elements"]))


def summarize(recs: list[dict]) -> str:
    lines = []
    for rec in recs:
        ensure_collisions(rec)
    lines.append("Set-of-marks role labelling (agreement with the analyzer per box; known-id = sample boxes whose id names the role)")
    lines.append("")
    lines.append("| model | load s | variant | calls ok | exact | coarse | known-id acc | prefill s | gen s | tok/s | total s (p50 / max) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for rec in recs:
        keys = sorted({k for d in rec["designs"] for k in d["som"]})
        for key in keys:
            rows = [d["som"][key] for d in rec["designs"] if key in d["som"]]
            ok = [r for r in rows if r["ok"]]
            if not rows:
                continue
            exact = statistics.mean(r["agree_exact"] for r in ok) if ok else 0
            coarse = statistics.mean(r["agree_coarse"] for r in ok) if ok else 0
            kn = sum(r.get("known_n", 0) for r in ok)
            kh = sum(r.get("known_hits", 0) for r in ok)
            tot = [r["total_s"] for r in rows]
            lines.append("| %s | %.1f | %s | %d/%d | %.2f | %.2f | %s | %.1f | %.1f | %.1f | %.1f / %.1f |" % (
                rec["model"], rec["load_s"], key, len(ok), len(rows), exact, coarse,
                ("%d/%d" % (kh, kn)) if kn else "-", _med(ok, "prefill_s"), _med(ok, "gen_s"),
                _med(ok, "tok_s"), statistics.median(tot), max(tot)))
    lines.append("")
    lines.append("Good vs perturbed render (pairwise: both orders asked; position-locked = same answer in both orders)")
    lines.append("")
    lines.append("| model | probe | designs | correct | correct where the perturbation collides | position-locked | prefill s | gen s | total s per call (p50 / max) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for rec in recs:
        keys = sorted({k for d in rec["designs"] for k in d["pair"]})
        for key in keys:
            pairs = [(d["pair"][key], d.get("bad_collisions", 0)) for d in rec["designs"] if key in d["pair"]]
            rows = [r for r, _ in pairs]
            hard = [r for r, c in pairs if c > 0]
            if not rows:
                continue
            flag = "correct" if key.startswith("absolute") else "correct_both"
            sub = "%d/%d" % (sum(1 for r in hard if r[flag]), len(hard))
            if key.startswith("absolute"):
                calls = [c for r in rows for c in r["renders"]]
                correct = sum(1 for r in rows if r["correct"])
                ties = sum(1 for r in rows if r["tie"])
                n_ok = sum(1 for c in calls if c["ok"])
                key = "%s (%d/%d calls ok)" % (key, n_ok, len(calls))
                tot = [c["total_s"] for c in calls]
                lines.append("| %s | %s | %d | %d/%d (%.0f%%), %d ties | %s | - | %.1f | %.1f | %.1f / %.1f |" % (
                    rec["model"], key, len(rows), correct, len(rows), 100.0 * correct / max(1, len(rows)), ties,
                    sub, _med(calls, "prefill_s"), _med(calls, "gen_s"), statistics.median(tot), max(tot)))
            else:
                calls = [c for r in rows for c in r["orders"]]
                correct = sum(1 for r in rows if r["correct_both"])
                locked = sum(1 for r in rows if r["position_locked"])
                tot = [c["total_s"] for c in calls]
                lines.append("| %s | %s | %d | %d/%d (%.0f%%) | %s | %d/%d | %.1f | %.1f | %.1f / %.1f |" % (
                    rec["model"], key, len(rows), correct, len(rows), 100.0 * correct / max(1, len(rows)),
                    sub, locked, len(rows), _med(calls, "prefill_s"), _med(calls, "gen_s"),
                    statistics.median(tot), max(tot)))
    return "\n".join(lines)


def confusion(rec: dict, side: str) -> str:
    """analyzer role -> what the model said (counts), for the doc."""
    from collections import Counter, defaultdict

    table = defaultdict(Counter)
    # need the marks again: re-analyze
    designs = {d["id"]: d for d in load_designs(len(rec["designs"]) + 5)}
    for d in rec["designs"]:
        if d["id"] not in designs or side not in d["som"] or not d["som"][side]["ok"]:  # side = "plain@672"
            continue
        src = designs[d["id"]]["source"]
        mk = marks(src, A.analyze(src))
        for m in mk:
            table[m["role"]][d["som"][side]["roles"].get(str(m["n"]))] += 1
    lines = ["| analyzer role | model said |", "|---|---|"]
    for role in sorted(table, key=lambda r: -sum(table[r].values())):
        lines.append("| %s | %s |" % (role, ", ".join("%s %d" % (k, v) for k, v in table[role].most_common())))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3vl-2b,qwen3vl-4b")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--sides", default="448,672")
    ap.add_argument("--pair-sides", default="672", help="first value is used for the pair probes")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--probes", default="som,pair,absolute", help="subset to (re)run; other probes keep their saved results")
    ap.add_argument("--summarize", action="store_true", help="only print tables from saved JSON")
    ap.add_argument("--confusion", default=None, help="model:variant@side, e.g. qwen3vl-2b:hinted@672")
    args = ap.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("engine.vlm").setLevel(logging.INFO)   # shows rejected model output in the err log

    names = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.summarize:
        recs = [json.loads((OUT_DIR / (m + ".json")).read_text()) for m in names if (OUT_DIR / (m + ".json")).is_file()]
        print(summarize(recs))
        if args.confusion:
            m, side = args.confusion.split(":")
            print()
            print(confusion(json.loads((OUT_DIR / (m + ".json")).read_text()), side))
        return 0
    designs = load_designs(args.n)
    print("designs:", [d["id"] for d in designs])
    if not R.enabled():
        raise SystemExit("renderer unavailable: " + R.status())
    recs = []
    for name in names:
        try:
            recs.append(run_model(name, designs, [int(s) for s in args.sides.split(",")],
                                  [int(s) for s in args.pair_sides.split(",")], args.threads, args.timeout,
                                  not args.no_images, tuple(args.probes.split(","))))
        except Exception as exc:
            print("[%s] FAILED: %s" % (name, exc), flush=True)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / (name + ".error.txt")).write_text(str(exc))
            release_model()
    print()
    print(summarize(recs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
