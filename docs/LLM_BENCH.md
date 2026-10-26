# S6 — text-only LLM reading of the design JSON: bench (2026-10-26)

Question: does a small instruction-tuned language model (no vision) that *reads the design JSON* give the
engine something the rules and the learned classifier do not: better roles, semantic groups, a plan prior?
Adapter: `chameleon/engine/llm.py` (the engine/vlm.py pattern, text only). Bench: `chameleon/tools/llm_bench.py`.
Tests: `chameleon/tests/test_llm.py` (12, stub backend, no weights). Raw results: `chameleon/eval/data/llm_bench/`
(gitignored; every answer cached under `cache/`, keyed by source hash + prompt version + model).

## Candidates (GGUF, Q4_K_M, public repos, fetched 2026-10-26)

| model | HF repo | file | bytes | sha256 |
|---|---|---|---|---|
| Qwen3-1.7B (hybrid thinking, thinking off) | `unsloth/Qwen3-1.7B-GGUF` | `Qwen3-1.7B-Q4_K_M.gguf` | 1 107 409 472 | `b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897` |
| Qwen3-4B-Instruct-2507 | `unsloth/Qwen3-4B-Instruct-2507-GGUF` | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | 2 497 281 120 | `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` |
| Gemma-3-4B-it | `ggml-org/gemma-3-4b-it-GGUF` | `gemma-3-4b-it-Q4_K_M.gguf` | 2 489 757 856 | `882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863` |

The sha256 values are the Hugging Face LFS object ids, re-verified after download (`shasum -a 256`). The
official `Qwen/*-GGUF` repos have no Q4_K_M of these two models (and `Qwen/Qwen3-4B-Instruct-2507-GGUF` does
not exist); `unsloth`'s files are the standard llama.cpp quantisations. None of the three repos is gated.
Runtime: the venv's llama-cpp-python 0.3.36 (CPU build), the same one the VLM uses; no new dependency.

## What the model is asked (`engine/llm.py`)

One call per source design, cached by source hash:

- **Listing** (`llm.listing`): one line per element in reading order (y, then x), scale-free, id-free:
  `#6 text "Introducing the All-New Limited-Batch Solstice Chase the Li…" 40px rank1/5 bold serif #FFFFFF x8 y46 w83 h16 z5`,
  `#8 shape rect fill #E86A3A rounded x6 y76 w27 h4 z3 grp B`, `#9 text "LIMITED EDITION" 15px rank4/5 bold #FFFFFF x6 y76 w27 h2 z5 grp B in #8`.
  Positions are integer % of the canvas, `rankK/N` the font-size rank among the texts, `grp A` the schema
  `group_id` (letters in order of appearance), `in #k` the smallest flat shape / image drawn below the element
  that holds ≥ 80 % of it (the analyzer's holder test). Texts first, then images, then the largest shapes when
  a design has more than 45 elements. Renaming ids / groups or shuffling the element list leaves the text
  byte-identical (test). ≈ 35 tokens per element; the fixed system prompt is 799 tokens (Qwen tokenizer) and
  is re-used from llama.cpp's KV cache after the first call of a process.
- **Answer** (grammar-constrained JSON, temperature 0, `top_k=1`, seed 7; the property order is the answer
  order): `roles` keyed by element number, each restricted by the grammar to the enum of its element type
  (text: headline / subhead / body / cta / badge / fine_print; image: logo / hero / image / background /
  decorative / badge; shape: background / panel / decorative / badge / cta / shape); `groups` (≤ 8 sets of
  element numbers, each with a one-word reason from button / badge / sticker / lockup / caption / list / frame /
  logo / contact / other; the prompt says not to repeat the `grp` groups); `importance` (1–5 element numbers);
  `archetype` (product_ad / event_poster / editorial / quote / grid / other); `focal` (hero / headline);
  `plans` per family — tall: chips (row / corner / beside_cta), keep; square and wide: hero (left / right /
  stack), chips, keep; banner: hero (left / right), text (stacked / inline / column), chips (row / corner /
  stack), keep — i.e. `floorplan.PlanOptions` values plus a keep-the-source-structure bit. Element numbers are
  string enums in the schema so the grammar (which does not enforce integer bounds) can only name listed
  elements; the first Gemma run returned `"m": [-1, -1]` before that change.
- **Interpretation** (`llm.interpret`): element roles → unit roles (the members that name a unit vote,
  text members for a text unit), mapped onto the coarse classes of `engine.perceive` with a derived
  confidence (`llm.BASE_CONF`, the bench accuracy per class, diluted among units sharing a unique role like
  perceive.confidence); `Reading.perception()` is a `perceive.Perception`, so `role_merge.apply_votes` takes
  the LLM in the VLM's seat unchanged. Groups come back as element-id sets, plans as cleaned dicts.

## Method

- **Roles**: the 60 DesignAsCode-labelled Crello designs S1 used (`tools/eval_perception.dac_designs`: train
  shards 0–2, seed 0, 3–14 elements, ≥ 60 % labelled; the same 60 ids), ids stripped before anything runs.
  Agreement per analyzer unit on the coarse classes (picture / headline / cta / logo / badge / secondary /
  minor) and on the fine role, for six voters: rules, classifier (S4, argmax in the type family), llm, rules +
  classifier (S4 merge), rules + llm (two-voter merge with the LLM in the VLM's seat), all three. Primary-role
  top-1 (the unit a voter calls X is the labelled X). Caveat as in S1: the classifier was *trained* on these
  designs' labels, so its row is an in-sample upper bound; its grouped-CV top-1 (docs/ROLE_MODEL.md: headline
  0.873, cta 0.897, logo 0.975, hero 0.922) is the fair yardstick for the primary roles.
- **Groups**: the 60 designer-reference designs (docs/designer*/out, 12 formats each, 720 layouts; eval designs
  with 4–25 elements). A group is *kept* in a reference layout when its members still form one cluster there:
  linking two members when their boxes overlap or lie within τ, with τ = max(1.5 × the group's connecting gap
  in the source scaled to the reference canvas, 2 % of the reference diagonal), where the connecting gap is the
  largest edge of the minimum spanning tree of pairwise box gaps (the smallest τ at which the group is
  connected in the source). `kept` per group = share of the 12 formats; reported as the mean over groups and as
  the share of groups kept in ≥ 80 % of formats, for: LLM groups, LLM groups the analyzer does not already
  have as one unit ("novel"), schema `group_id` groups, the analyzer's inferred units (holder / host / row),
  and random pairs of content elements that are not one unit (chance level).
- **Latency**: wall time of `llm.read` per uncached call, native (Apple M3 Pro, 11 cores, 8 threads, CPU
  only; the reference M5 Pro should be faster), the models alone on the machine, on the 60 designer designs
  (4–25 elements) and on the 60 DaC designs (3–14 elements); the first call of a process includes the
  system-prompt prefill.
- **Validity**: share of calls whose answer parses and validates against the schema; self-consistency: exactly
  one headline among the texts, ≤ 1 hero / logo / cta.

## Results

### Summary per model

Roles on the 60 DesignAsCode designs (463 labelled units, ids stripped), groups and latency on the 60
designer-reference designs. "alone" = the LLM's own roles per unit; "three" = rules + classifier + LLM
merged by `role_merge.vote_roles` (the LLM in the VLM's seat); top-1 = the unit the voter calls X is the
labelled X. Reference rows at the bottom.

| model | GGUF | latency p50 / p95 s, designer designs (4–18 elements) | DaC designs (3–14) | coarse alone | exact alone | headline / cta / logo / hero top-1 | rules + LLM | three | valid JSON | one headline | groups per design | LLM groups adjacent in ≥ 80 % of formats |
|---|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|
| Qwen3-1.7B | 1.11 GB | 6.6 / 9.8 | 6.0 / 7.8 | 0.581 | 0.343 | 33/58, 4/13, 0/4, 6/28 | 0.685 | 0.745 | 60/60 | 26/60 | 0.0 | – (no groups at all) |
| Qwen3-4B-Instruct-2507 | 2.50 GB | 14.4 / 22.4 (+ 2 stalls: 116 s, 182 s) | 13.1 / 18.7 | 0.618 | 0.387 | 40/58, 7/13, 0/4, 15/28 | 0.695 | 0.741 | 60/60 | 58/60 | 2.4 | 0.48 |
| Gemma-3-4B-it | 2.49 GB | 12.1 / 19.1 | 11.8 / 15.7 | 0.674 | 0.451 | 37/58, 4/13, 0/4, 5/28 | 0.713 | 0.754 | 60/60 | 38/60 | 0.6 | 0.45 |
| *rules (engine/analyze.py)* | – | – | – | 0.713 | 0.454 | 46/58, 6/13, 3/4, 20/28 | – | – | – | – | – | analyzer units 0.88 |
| *classifier (S4, in-sample)* | 0.4 MB | 3 ms | 3 ms | 0.825 | 0.747 | 47/58, 9/13, 4/4, 24/28 | rules + classifier 0.745 | – | – | – | – | random pairs 0.31 |
| *VLM Qwen3-VL-4B (S1, same designs)* | 2.95 GB | 9.0 / 12.3 | – | 0.687 | 0.445 | 43/58, 9/13, 2/4, 6/28 | – | 0.747 | – | – | – | – |

The 1.7B's designer-design latency is from its first run (the saved file was recomputed from the cache
after the adjacency metric was added). The classifier's grouped-CV top-1 on held-out designs
(docs/ROLE_MODEL.md: headline 0.873, cta 0.897, logo 0.975, hero 0.922) is the fair yardstick for the
primary roles; every LLM is far below it too (best: headline 0.69, cta 0.54, logo 0.0, hero 0.54).

### Roles, per class (coarse hits / labelled units)

| voter | coarse | exact | minor | secondary | badge | headline | picture | cta | logo |
|---|---:|---:|---|---|---|---|---|---|---|
| rules | 0.713 | 0.454 | 157/183 | 86/100 | 3/59 | 46/58 | 29/40 | 6/19 | 3/4 |
| classifier (in-sample) | 0.825 | 0.747 | 177/183 | 74/100 | 32/59 | 48/58 | 34/40 | 13/19 | 4/4 |
| Qwen3-1.7B | 0.581 | 0.343 | 129/183 | 51/100 | 4/59 | 48/58 | 32/40 | 5/19 | 0/4 |
| Qwen3-4B | 0.618 | 0.387 | 112/183 | 79/100 | 12/59 | 41/58 | 35/40 | 7/19 | 0/4 |
| Gemma-3-4B | 0.674 | 0.451 | 150/183 | 58/100 | 16/59 | 44/58 | 38/40 | 6/19 | 0/4 |
| rules + classifier | 0.745 | 0.492 | 157/183 | 84/100 | 15/59 | 47/58 | 29/40 | 9/19 | 4/4 |
| rules + Gemma | 0.713 | 0.467 | 157/183 | 71/100 | 16/59 | 47/58 | 33/40 | 6/19 | 0/4 |
| rules + classifier + Qwen3-4B | 0.741 | 0.508 | 157/183 | 85/100 | 11/59 | 49/58 | 29/40 | 9/19 | 3/4 |
| rules + classifier + Gemma | 0.754 | 0.512 | 157/183 | 84/100 | 16/59 | 50/58 | 32/40 | 7/19 | 3/4 |

Where the text models are right and both the rules and the classifier are wrong (12 units for Qwen3-4B, 13
for Gemma, of 463): headlines whose *words* say title but whose size does not ("CERTIFICATE", "RIDE SAFE
NIGHT", "FIONA WILSON", "Friendship", "SEASONAL", "ONEDITO": the rules call them body because another text
is larger, the classifier badge / subhead), small top-of-canvas images the rules and classifier call logo
that are pictures, a "10% OFF" the rules make the headline that is a badge. Where they alone are wrong
(73 units for Qwen3-4B, 44 for Gemma): ornaments and plain shapes called *badge* (40 of the 4B's 73; harmless
in the merge, which leaves shapes to the rules), headline ↔ subhead swaps, fine print called cta or badge,
logos called image (all three models: logo 0/4, they never name a logo from a listing). Self-consistency:
Qwen3-4B keeps one headline in 58/60 designs, Gemma in 38/60, the 1.7B in 26/60 (it spends the role on
several texts, which the merge then dilutes).

### Groups

`kept` = the members still connect within max(1.5 × their source gap, 2 % of the diagonal) in a reference
layout; `adjacent` = within 3 % of the reference diagonal regardless of the source. Random pairs score
0.79 on `kept` (designers move things proportionally, so a pair that was far apart stays about as far
apart), which is why the absolute `adjacent` column is the one that discriminates.

| set (over the 60 designer designs × 12 formats) | groups | kept, mean | kept ≥ 80 % | adjacent, mean | adjacent ≥ 80 % | source gap (frac. of diagonal) |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-4B groups | 142 | 0.843 | 0.74 | 0.553 | 0.48 | 0.092 |
| Qwen3-4B groups beyond the analyzer's units | 119 | 0.817 | 0.70 | 0.506 | 0.42 | 0.105 |
| Gemma-3-4B groups | 38 | 0.906 | 0.82 | 0.524 | 0.45 | 0.140 |
| Gemma-3-4B groups beyond the analyzer's units | 37 | 0.903 | 0.81 | 0.511 | 0.43 | 0.144 |
| Qwen3-1.7B groups | 0 | – | – | – | – | – |
| schema `group_id` groups | 7 | 1.000 | 1.00 | 1.000 | 1.00 | 0.000 |
| analyzer units (holder / host / row, not schema groups) | 73 | 0.885 | 0.78 | 0.942 | 0.88 | 0.002 |
| random content pairs that are not one unit | 472 | 0.793 | 0.64 | 0.395 | 0.31 | 0.129 |

The LLM's groups are mostly pairs that already sit 9–14 % of the diagonal apart in the source (a
headline with its subhead, a photo with the text beside it: `lockup` 37, `caption` 31, `badge` 31 of the
4B's 142) and the designers keep them adjacent in 42–48 % of the formats — above chance (31 %) and far
below the analyzer's own inferred units (88 %). 11 of the 142 touch a background or panel. Qwen3-4B also
repeats the schema groups it was told not to repeat (23 of 142 are existing units); Gemma proposes a
group in 22 of 60 designs; the 1.7B never.

### Plan prior

Degenerate for every model. Qwen3-4B: hero left, chips row, keep true, banner text stacked in 59 of 60
designs; Gemma: hero left and keep true in 60/60, chips corner for tall / square in 47–48; the 1.7B: hero
left 57, keep true 60, chips row 41 / corner 19 with no visible relation to the design. Archetype:
Qwen3-4B 47 product_ad / 12 event_poster on the DaC set (the VLM saw 20 / 18 / 16 editorial / 6 quote on the
same designs), Gemma 56 product_ad, the 1.7B 44 event_poster; `focal` = headline for 60/60 (Qwen3-4B) or
37/60 (Gemma). There is nothing here for `candidates.py` to act on.

### Latency and reliability

Native, Apple M3 Pro, 8 threads, CPU only, model alone on the machine, uncached calls; the first call of a
process also prefills the 799-token system prompt (its KV cache is reused afterwards).

| model | designer designs p50 / p95 / max s | DaC designs p50 / p95 / max s | first call s | prefill / generation p50 s | tokens generated p50 | s per element |
|---|---|---|---|---|---:|---:|
| Qwen3-1.7B | 6.6 / 9.8 / – (first run) | 6.0 / 7.8 / 8.2 | 11.1 | 1.3 / 4.7 | 188 | ~0.6 |
| Qwen3-4B | 14.4 / 22.4 / 182 | 13.1 / 18.7 / 21.1 | 26.7 | 3.7 / 10.7 | 240 | 1.48 |
| Gemma-3-4B | 12.1 / 19.1 / 21.8 | 11.8 / 15.7 / 18.1 | 23.8 | 2.8 / 9.4 | 198 | 1.30 |

Generation dominates (≈ 10 answer tokens per element at 20–25 tokens/s for the 4B models); the listing's
prefill is ≈ 35 tokens per element at 130–150 tokens/s. Two of the Qwen3-4B's 120 calls stalled (39 tokens
in 168 s, 155 tokens in 106 s, consecutive, the samples `level1_warmup` and `5fa50e1e`; the same prompts
ran in 8–15 s before); nothing else was running and the cause is unknown. In the engine such a call would
hit the budget and, after two of them, switch the adapter off for the process (the vlm.py policy), so it
is a lost opinion, not a lost output, but it is a reliability flag. All 360 answers were valid JSON (the
grammar guarantees it; the one earlier failure mode, `"m": [-1, -1]` from Gemma, was closed by making the
element numbers string enums). Against the 8 s default budget only the 1.7B fits (p95 9.8 s on the
designer designs); the 4B models need ≈ 25 s (p95 + the first-call prefill), 3× the VLM's budget-relative
cost for a design the VLM reads in 9 s.

## Verdict: no model is picked; stop at the bench

The gate was "beats the classifier on roles and is reliable". Nobody comes close: the best text model alone
(Gemma, 0.674 coarse) is below the rules (0.713) and 15 points below the classifier (0.825, in-sample; on
the fair held-out yardstick the LLMs' primary-role top-1 is 0.5–0.7 against 0.87–0.98). As a replacement
for the classifier vote (rules + LLM) Gemma lands exactly on the rules (0.713) and the Qwen models below
them. As a *third* voter next to the classifier the best case is +0.9 pp coarse (0.745 → 0.754) and +3
headline top-1 (47 → 50 of 58) at 12 s per source design — the same size of gain S1 measured for the VLM
(+0.2 pp, 10 s), whose end-to-end effect on the 300-design eval was mixed and whose default is off. The two
new signals this workstream was meant to add are empty: the groups are at best weakly above chance
(adjacent 0.45–0.48 vs 0.31 random and 0.88 for what the analyzer already infers), and the plan prior is a
constant.

So nothing is wired: `engine/resize.py`, `candidates.py` and `role_merge.py` are untouched, `engine/llm.py`
is a standalone, tested adapter (the engine never imports it: `tests/test_llm.py`), and the output of the
engine is byte-for-byte what it was. What the bench did show, for a future round: a text model reads
*meaning* the rules and the classifier cannot (a title that is not the largest text, a photo the rules
call logo), 12–13 units in 463; the cheap way to harvest that is not a third vote over everything but a
targeted question on the ~1 in 6 designs where the rules' headline is a guess (S1's suggestion), which
would also keep the cost to a fraction of the designs.

## Reproduce

```bash
cd chameleon
.venv/bin/python tools/llm_bench.py roles  --models qwen3-1.7b,qwen3-4b,gemma3-4b   # DaC designs, ~45 min
.venv/bin/python tools/llm_bench.py groups --models qwen3-1.7b,qwen3-4b,gemma3-4b   # designer designs, ~45 min
.venv/bin/python tools/llm_bench.py report                                          # tables -> eval/data/llm_bench/report.md
CHAMELEON_LLM=1 CHAMELEON_LLM_MODEL=models/gemma-3-4b-it-Q4_K_M.gguf .venv/bin/python -m engine.llm input/*.json   # see one listing and answer
```

The weights are in `chameleon/models/` (gitignored, 6.1 GB for the three); the DesignAsCode labels come from
the S4 scratchpad path `tools/eval_perception.DAC_DEFAULT` (re-download: `huggingface-cli download
Tony1109/DesignAsCode-training-data`). Every answer is cached under `eval/data/llm_bench/cache/`, so the
reports rebuild in seconds.
