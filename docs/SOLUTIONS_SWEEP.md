# Is design retargeting already solved? Sweep of products, papers and code (2026-10-26)

Question: is there a product, method or open-source library that takes a finished design (elements + canvas)
and returns the same elements composed for another canvas, cleanly? Short answer: no. What exists:

## Products
| Product | What it does | Why it is not the answer |
|---|---|---|
| Canva Magic Switch (ex Magic Resize) | one-click resize to many formats; reflow + subject-aware image crop | algorithm undocumented; known for overflow, awkward crops, tiny logos; relies on templates authored with responsive intent |
| Adobe Express Resize, Firefly Design Intelligence "Resize" (Illustrator), GenStudio GenExpand (2026) | keeps element relationships / brand standards; GenExpand adapts assets across channel ratios | product features, no published method; GenExpand leans on generative expand (forbidden here) |
| Adobe XD Responsive Resize (old) | predicts constraints from relative positions when an artboard resizes | heuristic constraint inference, UI screens, not posters |
| Bannerflow, Celtra, Smartly, Storyteq, Viewst | "one master -> many sizes" creative automation | a designer authors the master with per-breakpoint rules; the hard part (intent) is human input |
| Bannerify (Figma plugin) | bulk banner resizer from a source frame | heuristic, closed |

## Research
| Work | Relevance |
|---|---|
| O'Donovan et al. 2014, *Learning Layouts for Single-Page Graphic Designs* (TVCG) | the one paper that defines retargeting to a new size as a task; energy model + optimisation, parameters learned from few examples; compared against a professional designer; "too slow for interactive use". Our energy optimiser uses its terms. |
| Attribute-conditioned LayoutGAN (2020) | GAN conditioned on element attributes incl. aspect ratio and reading order; notes GAN-style models fail retargeting with user-supplied elements |
| FlexDM / CanvasVAE (CyberAgent, Crello) | masked-field prediction on Crello documents; aspect ratio is an input attribute; generation, not retargeting |
| DesignSense (Adobe, 2026) | Crello re-layouts at 3 ratios via AesthetiQ + human 4-class labels -> VLM judge; data not released |
| AutoPoster (2023) | multi-size poster generation from one image; adapts elements rather than linear scaling |
| Constrained Preferential BO for banner ads (IJCAI 2025) | designer-preference optimisation under a CTR constraint; elements as fixed-aspect rectangles with alignment/overlap constraints, post-processed by a minimal-move constrained optimiser |
| One Figure, Every Canvas (2026) | flowchart relayout to 5 aspect ratios via parse/style/layout agents each with a critic (deterministic checks + VLM); 68.6 % content fidelity vs 11-41 % for prior work. Same critic-loop shape as our v9. |
| Graphic-Design-Bench (2026), InfoEdit (2026) | benchmarks mentioning aspect-ratio adaptation / reflow; no released solver |

## Open source
No retargeting library exists. Closest: Sony BannerAgency (banner generation from scratch with multimodal agents,
13 sizes), Salesforce BannerGen (generation), small canvas utilities. Nothing takes an existing layout in.

## Reading
- The "pure" solution is constraint-based responsive layout (CSS / auto layout / creative-automation masters). It
  needs the author's intent as input; our input has none, so the problem is inferring intent, then composing.
- Every serious attempt is generate-and-rank or energy-and-optimise with a learned or fitted judge
  (O'Donovan, DesignSense, One Figure Every Canvas, us). Learned coordinate emitters lose (Angelo's and
  tailsgit's results in docs/COMPETITORS.md, our S1/S6).
- Ideas confirmed by this sweep: critics with deterministic checks + visual feedback (we have the checks; the
  visual half is the v10 backdrop work), minimal-move constrained post-processing (our rectifier), subject-aware
  image handling (Canva, Parinagpal) which the schema does not allow us to express.
