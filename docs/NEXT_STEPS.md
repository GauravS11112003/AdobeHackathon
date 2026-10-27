# Next steps for the engine (written 2026-10-26, after v10)

State when this was written: engine v10 on main (analyze → candidates → rectify → fitted judge → optimiser →
critic loop → backdrop awareness). Hold-out designer agreement 0.615, eval slice 13 hard defects of 4,198 (all
headline / CTA below the floor on strips), 0 overflow / overlap / off canvas, p50 0.3–0.4 s per task. VLM (S1) and
text LLM (S6) benched and rejected; the 391 KB role classifier is the only model that beats the rules
(0.83 vs 0.71 on roles) and is still off by default pending the freeze measurement.

## Still to do before submission (S5 freeze card)
1. Defaults: measure `CHAMELEON_ROLE_MODEL=1` end to end (eval slice + 720 references, hold-out apart); on only
   if defects do not rise and hold-out agreement does not fall.
2. Container truth: build the v10 tree for arm64 and amd64, make the VLM weights stage skippable
   (`--build-arg WITH_VLM=0`), run the eval slice inside the Linux image (text widths up to 18 % wider than macOS),
   record sizes and timings. Nothing of v7–v10 has been run in Docker yet.
3. Organizer answers still open: Rosetta on the M5 Pro or arm64 accepted, size cap, per-task time, submission form.

## The five implementations that would move layout quality most (in order of expected gain per day)

1. **Composition library for wide and banner formats, mined from the 720 references.** Banners agree with the
   designers at 0.51 vs 0.76 on squares. Designers use compositions we never generate: header-left with a one-line
   message, logo / CTA bookends with a centred headline, hero bleeding off one edge with stacked copy beside it,
   two-tier text with badges as a thin strip. Mine docs/designer*/out per format family, encode 6–10 general
   parameterised plans in floorplan.py (templates, not retrieval), let the judge choose. Measure on the hold-out.
2. **Exact minimal-move constraint pass after every candidate.** The rectifier is greedy and pairwise. Solve
   positions jointly (alignment groups stay aligned, stack gaps equal, margins, no overlap, hierarchy) with the
   smallest displacement from the plan: a small numpy projected-gradient / ADMM solver, no native deps. Makes
   "looks intentional" exact (edges to the pixel, even rhythm, lockups never drift). Keep it behind a flag with
   byte-identical off.
3. **Typographic scale and whitespace as plan constraints.** References beat us on breathing room and hierarchy
   and lose on fill; the judge still rewards tidy-and-full. In the planner: a type scale (headline 1.6–2.6× body,
   body ≈ 2.5× legal), line-measure limits (45–75 chars, headline ≤ 3 lines), an explicit whitespace budget per
   slot that the shrink factor cannot eat below a floor. Whitespace is allocated, not leftover.
4. **Smarter units: compound phrases, text-only lockups, secondary images.** Known analyzer gaps: text-only
   groups and secondary images are sized like badge chips; phrases split across elements (price + currency,
   weekday + date, a line ending in "of / and") move independently. Add compound-phrase union (geometry + language
   cues, the one idea worth borrowing from the sweep-3 rivals, in our own words), text-only lockups, a real
   secondary-image role with its own sizing.
5. **Tiny-format composer with content triage.** 160×600 and 728×90 are where "holds up everywhere" is decided
   and where every remaining hard defect lives. A dedicated strip composer: reading-order triage keeping logo,
   headline (1–2 lines), CTA and hero readable, badges and legal pushed to a deliberate minimum strip, the longest
   unbreakable word measured before the font is chosen. The references for those two formats are the spec.

Enabler for 1 and 3: a second human A/B round (the 80 hold-out misses + banner cases) on /label, then fit the
readability block of the judge (frozen today: 109 pairs are too few). The designer-agreement metric rewards the
proportional copy, so new composition work needs human eyes to be judged fairly.

## Things measured and closed (do not redo)
- VLM as judge / perceiver (docs/S1_PERCEPTION.md, docs/VLM_BENCH.md): no.
- Text-only LLM for roles / groups / plan (docs/LLM_S6.md): no.
- Learned rankers over the breakdown (docs/EVAL_V8.md §3): the 16-weight linear judge wins on the hold-out.
- `read.backdrop` judge term (docs/EVAL_V10.md): hurts designer agreement at every weight; off.
- Retargeting is not a solved problem anywhere (docs/SOLUTIONS_SWEEP.md); the field converges on
  generate → repair → fitted judge → critic, which is what we have.
