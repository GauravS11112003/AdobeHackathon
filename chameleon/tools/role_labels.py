"""Map DesignAsCode group themes (free text, GPT-distilled) to the engine's role set.

DesignAsCode (HF `Tony1109/DesignAsCode-training-data`, MIT) labels every
Crello *train* design with groups of layer indices and a short theme such as
"main title text", "call-to-action button", "decorative lines" or "contact
information". Layer indices are Crello layer order, which is exactly the
`el_NN` id the eval converter (`eval/crello_convert.py`) gives each element,
so the themes join onto our converted designs without any pixel data.

Themes are mapped with ordered keyword rules per element type (text / image /
shape), then resolved per design: one headline (the largest-font text among
the headline-like ones, the rest demoted to subhead or body), one hero (the
largest photo-like image >= 3 % of the canvas), text chips only when short.
`label_design()` returns {element id: role} plus a text-hierarchy rank.

Dev tool: used by tools/train_role_model.py, never imported by the engine.
"""

from __future__ import annotations

import re
from typing import Any

from engine.geometry import Box

ROLES = ["headline", "subhead", "body", "cta", "badge", "fine_print",
         "logo", "hero", "image", "background", "decorative", "shape"]
TEXT_ROLES = ("headline", "subhead", "body", "cta", "badge", "fine_print")
# hierarchy tier of a text role (0 = most prominent)
TIER = {"headline": 0, "subhead": 1, "cta": 2, "badge": 3, "body": 3, "fine_print": 4}

CHIP_MAX_CHARS = 40
CHIP_MAX_WORDS = 6
HERO_MIN_SHARE = 0.03
BG_MIN_COVER = 0.5


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I)


RX_CTA = _rx(r"call[- ]?to[- ]?action", r"\bcta\b", r"button", r"swipe[- ]up", r"shop now", r"subscribe",
             r"\bdonate\b", r"\bregister\b", r"sign[- ]up", r"book now", r"order now", r"learn more",
             r"buy now", r"get tickets", r"apply now", r"join now", r"download")
RX_LOGO = _rx(r"\blogo", r"\bbrand(ing)?\b", r"\bemblem\b", r"\bmonogram\b", r"\bwordmark\b")
RX_ATTRIB = _rx(r"attribution", r"\bauthor\b", r"quote (by|source)", r"signature", r"credit")
RX_FINE = _rx(r"contact", r"website", r"\burl\b", r"\blink", r"address", r"phone", r"e-?mail", r"footer",
              r"copyright", r"legal", r"disclaimer", r"terms", r"social", r"handle", r"hashtag",
              r"fine print", r"small print", r"\bwww\b", r"follow us", r"find us", r"\bnote\b")
RX_HEADLINE = _rx(r"title", r"headline", r"heading", r"header text", r"main text", r"main message",
                  r"\bquote\b", r"announcement", r"promotional text", r"main (discount|offer|number|price)",
                  r"large number", r"recipient name", r"certificate", r"slogan", r"main (heading|header)",
                  r"key message", r"statement", r"hero text", r"big text", r"primary text", r"main word",
                  r"main copy", r"lettering", r"main typography", r"main headline", r"name and title",
                  r"event name", r"brand name", r"greeting", r"main label", r"question text", r"big number")
RX_SUBHEAD = _rx(r"sub-?title", r"sub-?heading", r"sub-?header", r"sub-?headline", r"tagline",
                 r"secondary (text|headline|title|heading|message)", r"supporting (text|copy|message|line)",
                 r"sub-?text", r"caption", r"intro(duction|ductory)? text", r"kicker", r"eyebrow",
                 r"lead text", r"pre-?title", r"descriptor", r"secondary line")
RX_CHIP = _rx(r"\bdate\b", r"\btime\b", r"price", r"discount", r"percent", r"\bsale\b", r"\boffer\b",
              r"badge", r"sticker", r"\btag\b", r"\blabel", r"number", r"\byear\b", r"\bday\b", r"\bstep\b",
              r"ribbon", r"highlight", r"promo", r"limited", r"\bnew\b", r"\bfree\b", r"coupon", r"\bcode\b",
              r"rating", r"award", r"stamp", r"seal", r"\bpill\b", r"\bchip\b", r"category", r"location",
              r"venue", r"\bage\b", r"season", r"edition", r"pricing")
RX_DECOR = _rx(r"decorat", r"accent", r"divider", r"separator", r"\bline(s)?\b", r"underline", r"\bdots?\b",
               r"pattern", r"texture", r"ornament", r"embellish", r"flourish", r"sparkle", r"confetti",
               r"\bstar", r"heart", r"arrow", r"shadow", r"swirl", r"wave", r"blob", r"doodle", r"frame",
               r"border", r"stroke", r"outline", r"scatter", r"floating", r"abstract", r"geometric",
               r"circle", r"triangle", r"squiggle", r"\bicon", r"bullet", r"glow", r"splash", r"brush",
               r"leaf", r"leaves", r"floral", r"flower", r"ornate", r"drip", r"stripe", r"grid lines",
               r"corner (element|shape|graphic)", r"glitter", r"snowflake", r"balloon", r"ribbons",
               r"garland", r"zigzag", r"dash", r"rule", r"cross")
RX_BACKGROUND = _rx(r"background", r"overlay", r"backdrop", r"base layer", r"canvas", r"full[- ]bleed",
                    r"\bwash\b", r"gradient", r"\bbase\b", r"\bfill\b", r"\bpanel", r"\bcard\b",
                    r"container", r"\bbox\b", r"\bblock\b", r"section", r"\barea\b", r"\bband\b",
                    r"\bbar\b", r"\bstrip\b", r"\bbanner\b", r"sidebar", r"column", r"\bzone\b",
                    r"plate", r"backing", r"tab\b", r"shape behind", r"color field", r"colour field")
RX_HERO = _rx(r"main image", r"central image", r"\bhero\b", r"product", r"photo", r"portrait", r"scene",
              r"featured", r"focal", r"key visual", r"illustration", r"picture", r"character", r"mascot",
              r"artwork", r"graphic", r"image", r"visual", r"figure", r"food", r"drawing", r"painting")


def theme_role(theme: str, etype: str, group_types: set[str]) -> str:
    """The raw role for one element from its group theme and converted type
    ('text' | 'image' | 'shape'). `group_types` are the converted types of the
    whole DesignAsCode group. Returns a role, or 'hero?' for an image that may
    become the hero after per-design resolution, or 'chip?' for a text that is a
    badge only when short, or 'bg?' for a shape/image that is background only
    when it covers the canvas."""
    th = theme.lower()
    if etype == "text":
        if RX_CTA.search(th):
            return "cta"
        if RX_ATTRIB.search(th):
            return "fine_print"
        if RX_FINE.search(th):
            return "fine_print"
        if RX_LOGO.search(th) and not RX_HEADLINE.search(th):
            return "chip?"          # brand name / tagline set in type: a small label
        if RX_SUBHEAD.search(th):      # before headline: "subtitle" contains "title"
            return "subhead"
        if RX_HEADLINE.search(th):
            return "headline"
        if RX_CHIP.search(th):
            return "chip?"
        return "body"
    if etype == "image":
        if RX_LOGO.search(th):
            return "logo"
        if RX_CTA.search(th):
            return "cta" if "text" in group_types else "image"
        if RX_BACKGROUND.search(th) and not RX_HERO.search(th.replace("background image", "")):
            return "bg?"
        if re.search(r"background (image|photo)", th):
            return "bg?"
        if RX_DECOR.search(th) and not RX_HERO.search(th):
            return "decorative"
        if RX_CHIP.search(th) and "text" in group_types:
            return "badge"
        return "hero?"
    # shape
    if RX_CTA.search(th):
        return "cta" if "text" in group_types else "shape"
    if (RX_CHIP.search(th) or re.search(r"badge|sticker|tag\b|ribbon|label", th)) and "text" in group_types \
            and not RX_BACKGROUND.search(th):
        return "badge"
    if RX_BACKGROUND.search(th):
        return "bg?"
    if RX_DECOR.search(th):
        return "decorative"
    return "shape"


def _is_short(content: str) -> bool:
    words = re.findall(r"\S+", content)
    return len(content.strip()) <= CHIP_MAX_CHARS and len(words) <= CHIP_MAX_WORDS


def label_design(source: dict[str, Any], layer_themes: dict[int, dict[str, Any]],
                 ) -> tuple[dict[str, str], dict[str, int], dict[str, str]]:
    """Resolve per-element roles for one converted design.

    `layer_themes` maps Crello layer index -> {"theme", "gid"} (from
    DesignAsCode). Elements whose layer has no theme get role "" (unlabelled).
    Returns (roles, text hierarchy rank per text id, raw theme-rule per id)."""
    canvas = source["canvas"]
    W, H = float(canvas["width"]), float(canvas["height"])
    cbox = Box(0.0, 0.0, W, H)
    elements = source["elements"]
    idx_of = {el["id"]: int(el["id"].split("_")[1]) for el in elements}

    # converted types per DesignAsCode group
    group_types: dict[str, set[str]] = {}
    for el in elements:
        lt = layer_themes.get(idx_of[el["id"]])
        if lt:
            group_types.setdefault(lt["gid"], set()).add(el["type"])

    raw: dict[str, str] = {}
    for el in elements:
        lt = layer_themes.get(idx_of[el["id"]])
        if not lt:
            raw[el["id"]] = ""
            continue
        raw[el["id"]] = theme_role(lt["theme"], el["type"], group_types.get(lt["gid"], {el["type"]}))

    roles: dict[str, str] = {}
    by_id = {el["id"]: el for el in elements}

    # background-ish: background when it covers half the canvas, else a shape / image
    for el in elements:
        r = raw[el["id"]]
        if r == "bg?":
            cover = cbox.intersection_area(Box.of(el)) / (W * H)
            if cover >= BG_MIN_COVER:
                roles[el["id"]] = "background"
            else:
                roles[el["id"]] = "shape" if el["type"] == "shape" else "hero?"
                raw[el["id"]] = roles[el["id"]]
        elif r and r not in ("hero?", "chip?"):
            roles[el["id"]] = r

    # hero: the largest photo-like image that is at least HERO_MIN_SHARE of the canvas
    hero_cands = [el for el in elements if raw[el["id"]] == "hero?"]
    hero_cands.sort(key=lambda el: -cbox.intersection_area(Box.of(el)))
    hero_done = False
    for el in hero_cands:
        share = cbox.intersection_area(Box.of(el)) / (W * H)
        if not hero_done and share >= HERO_MIN_SHARE:
            roles[el["id"]] = "hero"
            hero_done = True
        else:
            roles[el["id"]] = "image"

    # text chips: short -> badge, long -> body
    for el in elements:
        if raw[el["id"]] == "chip?":
            roles[el["id"]] = "badge" if _is_short(str(el.get("content", ""))) else "body"

    # one headline per design
    texts = [el for el in elements if el["type"] == "text" and roles.get(el["id"])]
    heads = [el for el in texts if roles[el["id"]] == "headline"]
    if heads:
        heads.sort(key=lambda el: -float(el["font_size"]))
        top = float(heads[0]["font_size"])
        for el in heads[1:]:
            fs = float(el["font_size"])
            short = _is_short(str(el.get("content", "")))
            if fs >= 0.35 * top:
                roles[el["id"]] = "subhead"      # a kicker / second line of the title
            elif short:
                roles[el["id"]] = "badge"
            else:
                roles[el["id"]] = "body"
    else:
        # no title-like theme (e.g. a plain quote poster): the largest text that is
        # neither a chip nor fine print nor the CTA is the headline
        cands = [el for el in texts if roles[el["id"]] in ("subhead", "body")]
        if cands:
            best = max(cands, key=lambda el: float(el["font_size"]))
            roles[best["id"]] = "headline"

    # a subhead smaller than 35 % of the headline and long is body copy
    if heads or any(roles.get(el["id"]) == "headline" for el in texts):
        head_fs = max(float(el["font_size"]) for el in texts if roles[el["id"]] == "headline")
        for el in texts:
            if roles[el["id"]] == "subhead" and float(el["font_size"]) < 0.35 * head_fs \
                    and not _is_short(str(el.get("content", ""))):
                roles[el["id"]] = "body"

    # text hierarchy rank: by tier, then font size (largest first)
    ranked = sorted(texts, key=lambda el: (TIER[roles[el["id"]]], -float(el["font_size"]), idx_of[el["id"]]))
    h_rank = {el["id"]: r for r, el in enumerate(ranked)}

    for el in elements:
        roles.setdefault(el["id"], "")
    return roles, h_rank, raw
