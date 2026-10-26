# S6 — a text-only LLM reading the design JSON: bench, decision, what ships (2026-10-26)

Workstream S6: can a small instruction-tuned language model (no vision) that *reads the element list* give
the engine better roles, semantic groups and a plan prior? Bench and all numbers: docs/LLM_BENCH.md.
Code: `chameleon/engine/llm.py` (adapter), `chameleon/tools/llm_bench.py` (bench), `chameleon/tests/test_llm.py`
(12 tests, stub backend). Nothing committed; nothing wired.

## TL;DR

- **No gain. Nothing is wired, nothing ships on by default, no weights go into the image.** Three public
  Q4_K_M GGUFs (Qwen3-1.7B, Qwen3-4B-Instruct-2507, Gemma-3-4B-it) were benched on the 60 DesignAsCode-labelled
  designs S1 used (ids stripped) and on the 60 designer-reference designs. Coarse role agreement alone: 0.581 /
  0.618 / 0.674 against the rules' 0.713 and the classifier's 0.825 (in-sample); none names a logo (0/4), the
  best hero top-1 is 15/28 (rules 20, classifier 24). As the third voter next to rules + classifier the best
  case (Gemma) is +0.9 pp coarse and +3 headline top-1 of 58, for 12 s per source design. Semantic groups are
  weakly above chance (members adjacent in ≥ 80 % of the designer's formats: 0.45–0.48 vs 0.31 for random pairs
  and 0.88 for what the analyzer already infers) and the plan prior is a constant (hero left / chips row / keep
  true on 59–60 of 60 designs). Latency p50 / p95: 6.6 / 9.8 s (1.7B), 14.4 / 22.4 s (Qwen3-4B, plus two
  unexplained stalls of 116 and 182 s), 12.1 / 19.1 s (Gemma), native; only the 1.7B, the worst reader, fits
  the 8 s budget.
- The gate in the brief was "beats the classifier on roles and is reliable"; no model passes, so step 2
  (wiring), step 3 (end-to-end eval) and the Docker bake were not done. The engine's output is byte-for-byte
  unchanged: `engine/resize.py`, `candidates.py`, `role_merge.py`, the Dockerfile and `requirements.txt` are
  untouched, and `engine/llm.py` is never imported by the engine (test).
- What a text model *does* read that the rules and classifier cannot: 12–13 of 463 units, almost all
  headlines whose words say title but whose size does not ("CERTIFICATE", "RIDE SAFE NIGHT", "SEASONAL"), and
  photos the rules call logo. The right shape for that, if a future round wants it, is a targeted question on
  the designs where the rules' headline is a guess, not a third vote over everything.

## 1. What was built

`engine/llm.py` — the engine/vlm.py pattern without the image:

- `read(source, analysis, budget=None) -> Reading`: one call per source design, cached by source hash (memory
  + `CHAMELEON_LLM_CACHE_DIR`), never raises; `Reading(roles={unit: (coarse, confidence)}, fine, element_roles,
  groups=[(ids, reason)], archetype, focal, importance, plans={family: {...}}, status, elapsed, raw)`.
  `Reading.perception()` is a `perceive.Perception`, so `role_merge.apply_votes` could take it as the third
  voter unchanged.
- Off unless `CHAMELEON_LLM` is explicitly on (default off; then `llama_cpp` is never imported). Model from
  `CHAMELEON_LLM_MODEL`, else the first of `DEFAULT_MODELS` found in `models/` (`CHAMELEON_LLM_DIR`). Budget
  `CHAMELEON_LLM_BUDGET_S` (8 s, covers load + call; < 1 s left → skipped); cooperative deadline on the
  streamed generation; two timeouts or two backend errors switch the adapter off for the process. Threads
  `CHAMELEON_LLM_THREADS` (min(8, cpus)), context `CHAMELEON_LLM_CTX` (4096), seed `CHAMELEON_LLM_SEED` (7).
- The listing (`llm.listing`) is id-free and canonical (reading order, integer % of the canvas, font-size
  rank, group letters, "in #k" holder hints; texts first, then images, then the largest shapes beyond 45
  elements); renaming ids / groups and shuffling the element list leave it byte-identical (test). The answer
  is grammar-constrained JSON (temperature 0, top_k 1, fixed seed, no repeat penalty): roles keyed by element
  number with the enum of the element's type, groups with a one-word reason, importance, archetype, focal, and
  per-family plans in `floorplan.PlanOptions` vocabulary; element numbers are string enums so the grammar can
  only name listed elements (llama.cpp does not enforce integer bounds). The GGUF's own chat template is
  rendered with jinja2 and thinking switched off (Qwen3's `enable_thinking=False`); the fixed 799-token system
  prompt is re-used from llama.cpp's KV cache across calls.
- `python -m engine.llm input/*.json` prints the listing, the raw answer and the per-unit roles.

`tools/llm_bench.py` — `roles` (DaC designs, six voters, primary top-1, validity, self-consistency),
`groups` (designer references: kept / adjacent per group set, latency, plan-prior distribution), `report`.
`tests/test_llm.py` — 12 tests: default off, engine never imports it, id-free / order-free listing, element
cap, per-type schema and grammar order, interpretation (units, groups, plans, type conflicts, diluted
duplicate headlines), cache by source (memory + disk), bad answers / exceptions / budget / timeouts never
raise, no model → no opinion.

## 2. Bench (docs/LLM_BENCH.md has every table)

| model | GGUF | latency p50 / p95 s (4–18-element designs) | coarse alone | headline / cta / logo / hero top-1 | rules + classifier + LLM | groups: adjacent ≥ 80 % | plan prior |
|---|---|---|---:|---|---:|---:|---|
| Qwen3-1.7B | 1.11 GB | 6.6 / 9.8 | 0.581 | 33/58, 4/13, 0/4, 6/28 | 0.745 (= without it) | no groups | constant |
| Qwen3-4B-Instruct-2507 | 2.50 GB | 14.4 / 22.4 (+ 2 stalls) | 0.618 | 40/58, 7/13, 0/4, 15/28 | 0.741 (−0.4 pp) | 0.48 | constant (59/60) |
| Gemma-3-4B-it | 2.49 GB | 12.1 / 19.1 | 0.674 | 37/58, 4/13, 0/4, 5/28 | 0.754 (+0.9 pp) | 0.45 | constant |
| rules | – | – | 0.713 | 46/58, 6/13, 3/4, 20/28 | – | analyzer units 0.88 | – |
| classifier (S4, in-sample) | 0.4 MB | 0.003 | 0.825 | 47/58, 9/13, 4/4, 24/28 | rules + classifier 0.745 | random pairs 0.31 | – |

Valid JSON 360/360 (grammar). The classifier's row is in-sample (trained on these designs' labels); its
grouped-CV top-1 on held-out designs is headline 0.87 / cta 0.90 / logo 0.98 / hero 0.92, still far above
every LLM.

## 3. What was wired

Nothing. The plan, for the record, so the next round does not have to redesign it: (a) roles —
`Reading.perception()` into `role_merge.apply_votes` as the VLM's seat, confidence from `llm.BASE_CONF`
(per-class bench accuracy, like `perceive.BASE_CONF`); (b) groups — every LLM group whose members are all
content elements becomes one analyzer unit when it does not split a rule unit and does not cross a
background / panel; (c) plans — a `PLAN_PENALTY` on floor-plan variants that contradict the LLM's per-family
hero side / chips / text flow, and `keep` steering the structure prior, both through the existing
`Candidate.prior` mechanism (`candidates.archetype_prior` style; never removing candidates). With the bench
numbers (b) and (c) would feed noise and (a) would reproduce S1's mixed result at a higher price.

## 4. Off → on

Not measured end to end: there is no "on". Flag off is byte-identical by construction (no engine file
changed); `tests/test_llm.py::test_engine_does_not_import_llm_or_llama_cpp_by_default` asserts the engine
never imports `engine.llm` or `llama_cpp`, and the golden fixtures of `tests/test_perceive.py` still pass.

## 5. Runtime and size

Per source design, native M3 Pro, 8 threads (the budget would cover the first task's extra ≈ 12 s of
system-prompt prefill and model load of 1–2.5 s): 1.7B ≈ 0.6 s per element, 4B models ≈ 1.3–1.5 s per element
(≈ 10 answer tokens per element at 20–25 tokens/s plus ≈ 35 prompt tokens per element at 130–150 tokens/s).
Every target of one source is a cache hit. Image size: +1.1 GB (1.7B) or +2.5 GB (either 4B) on top of the
1.24 GB engine image (7.3 GB with the VLM weights); the model cap is still unstated (docs/ORGANIZER_QUESTIONS.md).
The arm64 container ran the VLM at ≈ 1× native (docs/S1_PERCEPTION.md); an x86 scorer with the generic AVX2
wheel is unmeasured.

## 6. Docker: how the weights stage would bake a text model (not done)

The Dockerfile's stage 1 already verifies any number of (file, sha256) pairs: the Python fetch loop reads
`sys.argv[2::2]` / `sys.argv[3::2]`. A second file set needs three build args and one more pair on the
command line, e.g.

```dockerfile
ARG LLM_BASE_URL=https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main
ARG LLM_MODEL_FILE=gemma-3-4b-it-Q4_K_M.gguf
ARG LLM_MODEL_SHA256=882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863
# second invocation of the same fetch script, skipped when LLM_MODEL_FILE is empty:
RUN if [ -n "$LLM_MODEL_FILE" ]; then python /fetch.py "$LLM_BASE_URL" "$LLM_MODEL_FILE" "$LLM_MODEL_SHA256"; fi
```

(the inline heredoc script would move to `/fetch.py` once it is called twice). The other two files:
`unsloth/Qwen3-4B-Instruct-2507-GGUF` / `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` /
`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`; `unsloth/Qwen3-1.7B-GGUF` /
`Qwen3-1.7B-Q4_K_M.gguf` / `b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897`. `engine/llm.py`
finds the file in `/app/models` through `DEFAULT_MODELS` (or `CHAMELEON_LLM_MODEL`). No runtime dependency
beyond the pinned llama-cpp-python 0.3.36 already in `requirements.txt`; text models need no mmproj and no
mtmd handler. The image was not built (the freeze session may be building; and there is nothing to ship).

## 7. Recommendation

Keep `CHAMELEON_LLM` off and bake no text model, whatever the size cap turns out to be: the feature has no
measured gain and a 12–22 s cost per task. Keep `engine/llm.py` and the bench in the tree (off they cost
nothing, the listing / grammar / cache plumbing is reusable, and the cached answers make the bench reports
rebuild in seconds). The one experiment worth a future hour is the targeted one: ask Gemma (the best reader,
no stalls) only when the rules' headline is a guess — the largest text is not the headline candidate or
several texts are within 15 % of it — and take its headline when it names one with a title-like text; that
touches ~1 in 6 designs, where the LLM-only hits were, and leaves everything else to the rules and the
classifier.
