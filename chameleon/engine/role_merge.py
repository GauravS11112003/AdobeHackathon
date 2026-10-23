"""Combine the analyzer's rule roles with the learned classifier's roles.

    from engine.role_merge import merged_roles, apply_to_analysis
    roles = merged_roles(source, analysis.roles)          # {id: role}
    apply_to_analysis(analysis, source)                    # rewrites roles/units in place

Nothing here edits engine/analyze.py: callers that want the model's opinion
run `analyze()` as usual and then pass the result through `apply_to_analysis`
(no-op unless `CHAMELEON_ROLE_MODEL=1`, or `force=True`).

Merge policy ("rules are the floor, the model votes on what the rules guess"):

* Structural roles stay with the rules: background, panel and decorative are
  geometric facts (covers the canvas / big flat shape / faint or bleeding)
  that the layouts rely on; the model never changes them, nor promotes
  anything into them.
* A group keeps one role for all its members. The model's vote for a group is
  the probability mass of its text members (a button is named by its label);
  only cta / badge / image-ish group roles are considered.
* The model overrides a text / image / shape role only when it is confident
  (`MIN_CONF`) and clearly ahead of the rule's own role under the model
  (`MIN_MARGIN`), and only inside the element's type family (a text never
  becomes a logo).
* Design-level consistency after the vote: exactly one headline among free
  texts (the one with the highest P(headline); the previous headline becomes
  subhead), at most one hero and one logo among images (highest P), at most
  one CTA (the model's best, else the rules').
* `CHAMELEON_ROLE_MODEL=0` (default) returns the rule roles untouched.
"""

from __future__ import annotations

import os
from typing import Any

from engine import role_model as RM

MIN_CONF = 0.55       # model must be at least this sure of its role
MIN_MARGIN = 0.25     # ... and ahead of the rule role's probability by this much
# The rules' headline / CTA / logo / fine-print decisions fire on specific
# structure and are precise when they fire (legal copy at 12 px is fine print
# even when it reads like body): the model needs to be this sure to take them away.
# (It can still *add* a better headline: the consistency pass then keeps the
# one with the higher P(headline).)
STICKY = {"headline": 0.75, "cta": 0.75, "logo": 0.80, "fine_print": 0.75}
FROZEN = {"background", "panel", "decorative"}     # the rules own these
TEXT_ROLES = {"headline", "subhead", "body", "cta", "badge", "fine_print", "text"}
IMAGE_ROLES = {"logo", "hero", "image"}
SHAPE_ROLES = {"shape"}


def enabled(force: bool | None = None) -> bool:
    if force is not None:
        return force
    return RM.enabled()


def merged_roles(source: dict[str, Any], rule_roles: dict[str, str], probs: dict[str, dict[str, float]] | None = None,
                 force: bool | None = None, min_conf: float = MIN_CONF, min_margin: float = MIN_MARGIN,
                 units: list[list[str]] | None = None) -> dict[str, str]:
    """Rule roles with the model's confident disagreements applied. Returns a
    new dict; `rule_roles` is not modified. `units` lists ids that the analyzer
    treats as one piece of furniture beyond `group_id` (a label in its holder
    shape, a host with attachments): they vote and move together like groups."""
    roles = dict(rule_roles)
    if not enabled(force):
        return roles
    if probs is None:
        probs = RM.predict_proba(source)
    if not probs:
        return roles

    elements = list(source.get("elements") or [])
    by_id = {str(el.get("id")): el for el in elements}
    groups: dict[str, list[str]] = {}
    for el in elements:
        gid = el.get("group_id")
        if gid:
            groups.setdefault(str(gid), []).append(str(el["id"]))
    for k, ids in enumerate(units or []):
        ids = [str(i) for i in ids if str(i) in by_id]
        if len(ids) > 1 and not any(i in g for g in groups.values() for i in ids):
            groups[f"unit:{k}"] = ids
    grouped = {eid for ids in groups.values() for eid in ids}

    # 1. free elements
    for el in elements:
        eid = str(el["id"])
        if eid in grouped or eid not in probs:
            continue
        rule = roles.get(eid)
        if rule in FROZEN or rule is None or el.get("type") == "shape":
            continue        # shapes take their role from the text they hold: the rules' call
        family = _family(str(el.get("type", "")))
        p = {r: v for r, v in probs[eid].items() if r in family}
        if not p:
            continue
        best, conf = max(p.items(), key=lambda t: t[1])
        if best == rule or conf < max(min_conf, STICKY.get(rule, 0.0)) or conf - p.get(rule, 0.0) < min_margin:
            continue
        roles[eid] = best

    # 2. groups: vote with the text members (or all members when there is no text)
    for gid, ids in groups.items():
        rule = roles.get(ids[0])
        if rule in FROZEN or rule is None:
            continue
        voters = [i for i in ids if by_id[i].get("type") == "text"] or ids
        acc: dict[str, float] = {}
        n = 0
        for i in voters:
            if i not in probs:
                continue
            n += 1
            for r, v in probs[i].items():
                acc[r] = acc.get(r, 0.0) + v
        if not n:
            continue
        has_text = any(by_id[i].get("type") == "text" for i in voters)
        family = _family("text") if has_text else _family(str(by_id[voters[0]].get("type", "")))
        p = {r: v / n for r, v in acc.items() if r in family}
        if not p:
            continue
        best, conf = max(p.items(), key=lambda t: t[1])
        if best == rule or conf < max(min_conf, STICKY.get(rule, 0.0)) or conf - p.get(rule, 0.0) < min_margin:
            continue
        mixed = has_text and any(by_id[i].get("type") != "text" for i in ids)
        if mixed and rule in ("badge", "cta") and best not in ("badge", "cta"):
            continue   # a shape + label is a button / chip even if its text reads like copy
        for i in ids:
            roles[i] = best

    _make_consistent(elements, roles, probs, grouped, groups)
    return roles


def _family(etype: str) -> set[str]:
    if etype == "text":
        return TEXT_ROLES - {"text"}
    if etype == "image":
        return IMAGE_ROLES
    return SHAPE_ROLES


def _make_consistent(elements: list[dict[str, Any]], roles: dict[str, str], probs: dict[str, dict[str, float]],
                     grouped: set[str], groups: dict[str, list[str]]) -> None:
    def p(eid: str, role: str) -> float:
        return probs.get(eid, {}).get(role, 0.0)

    free_text = [str(el["id"]) for el in elements
                 if el.get("type") == "text" and str(el["id"]) not in grouped and roles.get(str(el["id"])) in TEXT_ROLES]
    # exactly one headline among free texts
    if free_text:
        heads = [i for i in free_text if roles[i] == "headline"]
        if len(heads) != 1:
            cands = [i for i in free_text if roles[i] not in ("fine_print", "cta")] or free_text
            best = max(cands, key=lambda i: (p(i, "headline"), _font(elements, i)))
            for i in heads:
                if i != best:
                    roles[i] = "subhead"
            roles[best] = "headline"
    # at most one hero and one logo among free images
    for role in ("hero", "logo"):
        have = [str(el["id"]) for el in elements if roles.get(str(el["id"])) == role
                and el.get("type") == "image" and str(el["id"]) not in grouped]
        if len(have) > 1:
            best = max(have, key=lambda i: p(i, role))
            for i in have:
                if i != best:
                    roles[i] = "image"
    # at most one CTA (free text or group)
    cta_units: list[tuple[str, float]] = []
    for i in free_text:
        if roles[i] == "cta":
            cta_units.append((i, p(i, "cta")))
    for gid, ids in groups.items():
        if roles.get(ids[0]) == "cta":
            texts = [i for i in ids if i in probs and any(el.get("type") == "text" for el in elements if str(el["id"]) == i)]
            score = max((p(i, "cta") for i in texts), default=0.0)
            cta_units.append((f"group:{gid}", score))
    if len(cta_units) > 1:
        keep = max(cta_units, key=lambda t: t[1])[0]
        for key, _ in cta_units:
            if key == keep:
                continue
            if key.startswith("group:"):
                for i in groups[key[6:]]:
                    roles[i] = "badge"
            else:
                roles[key] = "body"


def _font(elements: list[dict[str, Any]], eid: str) -> float:
    for el in elements:
        if str(el["id"]) == eid:
            return float(el.get("font_size", 0.0) or 0.0)
    return 0.0


def apply_to_analysis(analysis: Any, source: dict[str, Any], force: bool | None = None) -> dict[str, str]:
    """Rewrite `analysis.roles` and every unit's role / importance with the
    merged roles. Returns {id: (old role) } for the elements that changed.
    Unit membership, anchors and reading order are untouched."""
    if not enabled(force):
        return {}
    units = [list(u.ids) for u in analysis.units if len(u.ids) > 1]
    merged = merged_roles(source, analysis.roles, force=force, units=units)
    changed = {eid: analysis.roles[eid] for eid, r in merged.items() if analysis.roles.get(eid) != r}
    if not changed:
        return {}
    analysis.roles.update(merged)
    try:
        from engine.analyze import IMPORTANCE
    except Exception:  # noqa: BLE001
        IMPORTANCE = {}
    for u in analysis.units:
        new = merged.get(u.ids[0], u.role)
        if new != u.role:
            u.role = new
            u.importance = IMPORTANCE.get(new, u.importance)
            for i in u.ids:
                analysis.roles[i] = new
    heads = [u for u in analysis.units if u.role == "headline"]
    if heads and hasattr(analysis, "headline_font_size"):
        fonts = [float(el.get("font_size", 0.0) or 0.0) for el in source.get("elements", [])
                 if str(el.get("id")) in heads[0].ids and el.get("type") == "text"]
        if fonts:
            analysis.headline_font_size = max(fonts)
    return changed


def summary(source: dict[str, Any], rule_roles: dict[str, str]) -> list[dict[str, Any]]:
    """Side-by-side view for the playground / docs: per element the rule
    role, the model's role + confidence and the merged role."""
    probs = RM.predict_proba(source)
    merged = merged_roles(source, rule_roles, probs=probs, force=True) if probs else dict(rule_roles)
    rows = []
    for el in source.get("elements", []):
        eid = str(el["id"])
        p = probs.get(eid, {})
        best = max(p.items(), key=lambda t: t[1]) if p else ("", 0.0)
        rows.append({"id": eid, "type": el.get("type"), "rule": rule_roles.get(eid), "model": best[0],
                     "confidence": round(best[1], 3), "merged": merged.get(eid)})
    return rows


def flag_value() -> str:
    return os.environ.get("CHAMELEON_ROLE_MODEL", "0")
