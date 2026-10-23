"""Join Crello train metadata with DesignAsCode themes and write the role dataset.

    .venv/bin/python tools/build_role_dataset.py --dac /path/to/dataset.jsonl

Reads every cached `eval/data/raw/train-*.parquet` shard (fetch them with
`eval.crello_convert.fetch_shard`), converts each template with the eval
converter (same schema the engine sees, normalised text boxes), maps the
DesignAsCode themes to roles (tools/role_labels.py), computes
`engine.role_features` per element and writes:

    eval/data/roles/dataset.npz   X (float32), y (int role index), h_rank, n_text,
                                  design (group key index), elem_type
    eval/data/roles/meta.json     role names, feature names, group keys, per-design ids,
                                  mapping coverage statistics

Dev tool, never shipped.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import role_features as RF  # noqa: E402
from eval.crello_convert import SkipTemplate, convert_template, detect_angle_unit, load_raw  # noqa: E402
from tools.role_labels import ROLES, label_design  # noqa: E402

OUT_DIR = ROOT / "eval" / "data" / "roles"


def load_dac(path: Path) -> dict[str, dict[int, dict[str, str]]]:
    out: dict[str, dict[int, dict[str, str]]] = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            m = re.search(r"<grouping>\s*(\[.*?\])\s*</grouping>", r.get("grouping", ""), re.S)
            if not m:
                continue
            try:
                groups = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            layers: dict[int, dict[str, str]] = {}
            for g in groups:
                theme = str(g.get("theme", "")).strip()
                for c in g.get("children") or []:
                    try:
                        ci = int(c)
                    except (TypeError, ValueError):
                        continue
                    layers.setdefault(ci, {"theme": theme, "gid": str(g.get("group_id", ""))})
            out[str(r["id"])] = layers
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dac", required=True, help="DesignAsCode dataset.jsonl")
    ap.add_argument("--raw-glob", default="train-*.parquet")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--max-elements", type=int, default=40)
    ap.add_argument("--raw-boxes", action="store_true", help="keep Crello text boxes (no normalisation)")
    ap.add_argument("--no-augment", action="store_true",
                    help="skip the augmented copies (raw-box copy, synthetic groups); default is to add them")
    args = ap.parse_args(argv)

    dac = load_dac(Path(args.dac))
    print(f"DesignAsCode: {len(dac)} labelled designs")
    paths = sorted((ROOT / "eval" / "data" / "raw").glob(args.raw_glob))
    rows = load_raw(paths)
    unit = detect_angle_unit(rows)
    print(f"{len(rows)} raw templates from {len(paths)} shards (angles in {unit})")

    X: list[list[float]] = []
    y: list[int] = []
    h_rank: list[int] = []
    n_text: list[int] = []
    design_idx: list[int] = []
    sample_idx: list[int] = []        # design x copy: one evaluated "design" per augmented copy
    etype: list[int] = []
    design_ids: list[str] = []
    raw_counter: collections.Counter[str] = collections.Counter()
    role_counter: collections.Counter[str] = collections.Counter()
    skipped: collections.Counter[str] = collections.Counter()
    n_designs = n_unlabelled = n_elements = 0
    type_map = {"text": 0, "image": 1, "shape": 2}
    for r in rows:
        cid = str(r.get("id"))
        if cid not in dac:
            skipped["not in DesignAsCode"] += 1
            continue
        copies: list[tuple[dict, bool]] = []       # (source, counts toward statistics)
        try:
            d = convert_template(r, angle_unit=unit, max_elements=args.max_elements,
                                 normalize_boxes=not args.raw_boxes)
            copies.append((d["source"], True))
            if not args.no_augment:
                # the same design with Crello's tight text boxes: the hidden tasks' box
                # convention is unknown, the model must not lean on box height
                d2 = convert_template(r, angle_unit=unit, max_elements=args.max_elements,
                                      normalize_boxes=args.raw_boxes)
                copies.append((d2["source"], False))
        except SkipTemplate as exc:
            skipped[str(exc).split(" (")[0][:30]] += 1
            continue
        n_designs += 1
        design_ids.append(cid)
        for k, (src, count) in enumerate(copies):
            retype_logo_shapes(src, dac[cid])     # single-colour SVG logos are images in the hidden tasks
            if not args.no_augment and (n_designs + k) % 2 == 0:
                synthesize_groups(src)            # button-like shape + label pairs get a group_id
            roles, ranks, raw = label_design(src, dac[cid])
            ids, feats = RF.features(src)
            texts = sum(1 for el in src["elements"] if el["type"] == "text")
            for eid, row, el in zip(ids, feats, src["elements"]):
                role = roles.get(eid, "")
                if count:
                    n_elements += 1
                    raw_counter[raw.get(eid, "")] += 1
                if not role:
                    if count:
                        n_unlabelled += 1
                    continue
                if count:
                    role_counter[role] += 1
                X.append(row)
                y.append(ROLES.index(role))
                h_rank.append(ranks.get(eid, -1))
                n_text.append(texts)
                design_idx.append(len(design_ids) - 1)
                sample_idx.append((len(design_ids) - 1) * 4 + k)
                etype.append(type_map[el["type"]])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "dataset.npz", X=np.asarray(X, dtype=np.float32), y=np.asarray(y, dtype=np.int16),
                        h_rank=np.asarray(h_rank, dtype=np.int16), n_text=np.asarray(n_text, dtype=np.int16),
                        design=np.asarray(design_idx, dtype=np.int32), sample=np.asarray(sample_idx, dtype=np.int32),
                        etype=np.asarray(etype, dtype=np.int8))
    meta = {
        "roles": ROLES,
        "feature_names": RF.FEATURE_NAMES,
        "design_ids": design_ids,
        "design_group": _design_groups(rows, dac, design_ids),   # title key per design, for grouped CV
        "n_designs": n_designs,
        "n_elements": n_elements,
        "n_labelled": len(y),
        "n_unlabelled": n_unlabelled,
        "skipped": dict(skipped),
        "role_counts": dict(role_counter),
        "raw_rule_counts": dict(raw_counter),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"designs {n_designs}, elements {n_elements}, labelled {len(y)}, unlabelled {n_unlabelled}")
    print("skipped:", dict(skipped))
    print("roles:", dict(role_counter.most_common()))
    return 0


def retype_logo_shapes(src: dict, layer_themes: dict[int, dict[str, str]]) -> int:
    """Crello logos are mostly single-colour SVGs, which the eval converter turns
    into shape rectangles; the hidden tasks ship logos as images (the sample
    lockup). Re-type a shape whose DesignAsCode theme names a logo as a
    `contain` image so the classifier sees logos the way it will meet them."""
    from tools.role_labels import RX_LOGO

    n = 0
    for el in src["elements"]:
        if el["type"] != "shape":
            continue
        lt = layer_themes.get(int(el["id"].split("_")[1]))
        if not lt or not RX_LOGO.search(lt["theme"]) or re.search(r"text|name|tagline|title", lt["theme"]):
            continue
        for key in ("shape_type", "fill_color", "stroke_color", "stroke_width", "corner_radius"):
            el.pop(key, None)
        el.update({"type": "image", "asset_id": "solstice_logo_lockup.png", "fit": "contain"})
        n += 1
    return n


def synthesize_groups(src: dict) -> int:
    """Give `group_id`s to button / chip structures the way the sample tasks
    do (badge_bg + badge_label): a small flat shape (< 15 % of the canvas) that
    holds exactly one text (>= 80 % inside it, drawn above it) and no other text.
    Crello has no groups, so without this the grouping features are never seen
    in training. Returns the number of groups made."""
    from engine.geometry import Box

    els = src["elements"]
    W, H = float(src["canvas"]["width"]), float(src["canvas"]["height"])
    boxes = {el["id"]: Box.of(el) for el in els}
    z = {el["id"]: float(el.get("z_index", i)) for i, el in enumerate(els)}
    made = 0
    for sh in els:
        if sh["type"] != "shape" or sh.get("group_id"):
            continue
        sb = boxes[sh["id"]]
        if sb.area <= 0 or sb.area / (W * H) > 0.15:
            continue
        inside = [t for t in els if t["type"] == "text" and z[t["id"]] > z[sh["id"]]
                  and sb.contains_fraction(boxes[t["id"]]) >= 0.8]
        if len(inside) != 1 or inside[0].get("group_id"):
            continue
        t = inside[0]
        if boxes[t["id"]].area < 0.15 * sb.area:
            continue
        gid = f"grp_{made}"
        sh["group_id"] = gid
        t["group_id"] = gid
        made += 1
    return made


def _design_groups(rows: list[dict], dac: dict, design_ids: list[str]) -> list[int]:
    title = {str(r.get("id")): (str(r.get("title") or "").strip().lower()) for r in rows}
    keys: dict[str, int] = {}
    out = []
    for cid in design_ids:
        k = title.get(cid) or cid
        out.append(keys.setdefault(k, len(keys)))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
