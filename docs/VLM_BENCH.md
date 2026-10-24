# VLM bench & packaging (workstream S0) — 2026-10-24

Goal: run a small vision-language model inside the engine, offline, and measure what it costs and what it
can do for us. Adapter: `chameleon/engine/vlm.py` (not wired into `resize()` yet). Bench:
`chameleon/tools/vlm_bench.py`. Tests: `chameleon/tests/test_vlm.py` (45, stub backend, no weights).
Raw results: `chameleon/eval/data/vlm_bench/<model>.json` (gitignored); example probe images in
`docs/vlm_bench/`.

## TL;DR

- **Packaging works.** llama-cpp-python 0.3.36 (pinned) with Qwen3-VL GGUF runs offline in the arm64 image
  (`--network none`), weights fetched and sha256-checked at build time. `CHAMELEON_VLM=0` never imports
  the adapter, so output is byte-identical to the engine without it.
- **Perception (set-of-marks roles): Qwen3-VL-4B, hinted prompt, 448 px.** 0.43 exact / 0.75 coarse
  agreement with the analyzer and 17/20 on the boxes whose sample ids give ground truth (2B: 0.40 / 0.70 /
  11/20; the fast tier is at chance). "Hinted" = the prompt lists each box's element type and text, which
  every task gives the engine; it is worth +0.1 exact / +0.2 coarse for both Qwen models.
- **Judging (good vs perturbed render): only Qwen3-VL-4B with two separate images is above chance** —
  12/20 designs picked right in both presentation orders (9 of the 14 with real collisions), 6/20
  position-locked. Everything else is position-locked or ties: the A|B composite fails even for the 4B
  (1/20), the 2B and the fast tier get 0–4/20, absolute 1–5 scores tie on most designs.
- **Cost on CPU (M3 Pro, 8 threads):** 2B ≈ 3 s per call at 448 px, 4.5 s at 672 px; 4B ≈ 7 s at 448 px,
  9 s at 672 px, 12 s for a two-image judge call. Inside Docker (arm64) with the optimised build the 2B takes
  12–14 s per call (~2× native). The prebuilt aarch64 wheel is 8× slower (generic ARMv8, no dot-product
  kernels), so the Dockerfile rebuilds llama.cpp for ARMv8.2 on arm64. Model load: 1–3 s.

## Candidates (GGUF)

| model | HF repo | file | size | sha256 |
|---|---|---|---|---|
| Qwen3-VL-2B-Instruct | `Qwen/Qwen3-VL-2B-Instruct-GGUF` | `Qwen3VL-2B-Instruct-Q4_K_M.gguf` | 1 107 409 952 B | `089d75c52f4b7ffc56ba998ffc50aae89fcafc755f9e7208aacca281dca6c2ae` |
| | | `mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf` | 445 053 216 B | `f9a68fabba69c3b81e153367b2c7521030b0fa8bb0de400c9599c8e6725f9c82` |
| Qwen3-VL-4B-Instruct | `Qwen/Qwen3-VL-4B-Instruct-GGUF` | `Qwen3VL-4B-Instruct-Q4_K_M.gguf` | 2 497 281 664 B | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` |
| | | `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` | 453 974 304 B | `30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d` |
| LFM2-VL-1.6B (fast tier) | `LiquidAI/LFM2-VL-1.6B-GGUF` | `LFM2-VL-1.6B-Q4_0.gguf` | 695 756 352 B | `ce0d4b122d328d14390ef160785da3a51a527f96844f392a04cb2db96f134e5d` |
| | | `mmproj-LFM2-VL-1.6B-Q8_0.gguf` | 564 133 440 B | `65ec437db88d65fff93f472d00c145e09880769ac67fedff5cd1c0f8d8301d87` |
| SmolVLM2-500M-Video-Instruct (fast tier) | `ggml-org/SmolVLM2-500M-Video-Instruct-GGUF` | `SmolVLM2-500M-Video-Instruct-Q8_0.gguf` | 436 836 992 B | `6f67b8036b2469fcd71728702720c6b51aebd759b78137a8120733b4d66438bc` |
| | | `mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf` | 108 823 616 B | `921dc7e259f308e5b027111fa185efcbf33db13f6e35749ddf7f5cdb60ef520b` |
| Moondream2 (2025-04-14, fast tier) | `ggml-org/moondream2-20250414-GGUF` | `moondream2-text-model-f16_ct-vicuna.gguf` | 2 839 456 768 B (f16 only) | `925bcb666baf69ed747e26121af287b16ae7764483be9548b1382f29783689a5` |
| | | `moondream2-mmproj-f16-20250414.gguf` | 909 770 752 B | `4cc1cb3660d87ff56432ebeb7884ad35d67c48c7b9f6b2856f305e39c38eed8f` |
| Qwen2.5-VL-3B-Instruct (fallback, not needed, not fetched) | `ggml-org/Qwen2.5-VL-3B-Instruct-GGUF` | `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | 1 929 901 056 B | `d02fe9b69ad8cadbbd228e387667af66612c44bed29ffc8eb1e7caf9ac486c12` |
| | | `mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf` | 844 757 728 B | `980c9b2f78c04e6cff93d277ada09e768394f112d75db3b4e9dea8a69f9fb904` |

Notes: the sha256 values are the Hugging Face LFS object ids (the oid *is* the file's sha256) and were
re-verified locally after download and again by the Dockerfile. The official `Qwen/*-GGUF` repos are used
(same bytes as `unsloth/*` Q4_K_M); `ggml-org/Qwen3-VL-4B-Instruct-GGUF` and `ggml-org/LFM2-VL-1.6B-GGUF`
are gated. SmolVLM2-500M has a Q8_0 GGUF with mmproj (no 4-bit); the 256M variant was not needed.
Moondream2 only exists as f16 (3.7 GB for both files), so it is "fast" in parameters, not in bytes.
Weights live in `chameleon/models/` (gitignored, excluded from the Docker context by `.dockerignore`).

All five run through llama.cpp's `mtmd` vision path with the same adapter; none needed another runtime.
Moondream2's GGUF carries no usable chat template (`tokenizer.chat_template = "vicuna"`), so the bench
passes its native `<image>\n\nQuestion: …\n\nAnswer:` format through `CHAMELEON_VLM_CHAT_TEMPLATE`.

Qwen3-VL in llama.cpp needs a build from 2025-10-30 or later (qwen3vl arch + deepstack mmproj); the
llama.cpp vendored in llama-cpp-python 0.3.36 is from 2026-10-01 and has `src/models/qwen3vl.cpp`, so the
Qwen2.5-VL fallback was not needed.

## Runtime: llama-cpp-python 0.3.36 (pinned)

- PyPI ships **source only** (76 MB sdist, needs cmake + C++). The project's own index
  `https://abetlen.github.io/llama-cpp-python/whl/cpu` has prebuilt **CPU** wheels for
  `manylinux2014_x86_64` and `manylinux2014_aarch64` (`py3-none`, any Python 3); both zips verified intact.
  `requirements.txt` carries the `--extra-index-url` line and the pin, so the organizers' plain
  `pip install -r requirements.txt` installs cleanly on both Docker platforms.
- **The aarch64 wheel is generic ARMv8** (`NEON | ARM_FMA | OPENMP`; no `DOTPROD`, `MATMUL_INT8`,
  `FP16_VA`). In the container the 2B ran a call in 36–60 s instead of 5–7 s (2.5 tok/s vs 40). The
  Dockerfile therefore has a stage that, on aarch64 only, rebuilds the wheel from the sdist with
  `-DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+i8mm+fp16` (51 s compile, needs `libgomp1` at
  run time) and force-reinstalls it; x86_64 keeps the AVX2 wheel. The M5 Pro supports all three extensions.
- The **macOS metal wheels** on that index (0.3.35 and 0.3.36) are corrupt (bad zip from
  `lib/cmake/ggml/ggml-config.cmake` on; `unzip -t` fails). The Mac venv was built from the sdist: the sdist's
  CMakeLists forces Metal on for every Apple build, so it was patched to `GGML_METAL OFF` (CPU only, like the
  reference machine: `llama_supports_gpu_offload() == False`), with
  `SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk` because the default 27.0 SDK's
  `libSystem.tbd` breaks `ld` ("unknown architecture arm64e.x1-macos"). `brew install cmake` first.
- Vision goes through `mtmd`; the adapter uses the generic `MTMDChatHandler` (chat template from the GGUF
  metadata, image marker inserted and encoded with the mmproj). JSON output is grammar-constrained from the
  JSON schema (`response_format={"type": "json_object", "schema": …}`), temperature 0, `top_k=1`, fixed seed,
  `repeat_penalty=1.0`. The grammar enforces keys, types and enums but **not** `minimum`/`maximum`: the
  adapter validates after parsing.
- Threads: llama.cpp's performance-core heuristic matters. On the M3 Pro (5P + 6E) 8 threads beat 11
  (prefill 2.1 s vs 2.5 s at 448 px for the 2B); the adapter defaults to `min(8, cpu_count)`
  (`CHAMELEON_VLM_THREADS`).
- Image tokens (Qwen3-VL, 32 px patches): 448 px → 196, 672 px → 441, 896 px → 784 for a square render.
  M-RoPE counts an image as its grid height in positions, so `n_past` in the stats is not a token count.

## Adapter contract (`engine/vlm.py`)

`describe(image, prompt, schema, max_tokens=256, timeout_s=30, max_side=672) -> dict | None`; `image` is a
PIL image or a list of them ("Image 1", "Image 2" in the prompt). Never raises. `CHAMELEON_VLM=0` = off
(no import of llama_cpp, no model load). Model from `CHAMELEON_VLM_MODEL` + `CHAMELEON_VLM_MMPROJ`, else the
first text + `mmproj-*` GGUF pair in `models/` (`CHAMELEON_VLM_DIR`), pairing by the "2B"/"4B" size tag.
Threads `CHAMELEON_VLM_THREADS`, context `CHAMELEON_VLM_CTX` (4096), seed `CHAMELEON_VLM_SEED` (7), optional
`CHAMELEON_VLM_CHAT_TEMPLATE`. Results cached by (image hashes, prompt, schema, max_tokens, model) in memory
(256 entries) and on disk when `CHAMELEON_VLM_CACHE_DIR` is set; rejected answers are cached as None too.
Timeouts are cooperative (no threads, no subprocesses): the token stream is stopped at the deadline; the
uninterruptible image encode + prompt evaluation is measured and counts as a timeout when it alone
overshoots. Two timeouts or two backend exceptions switch the adapter off for the process (`vlm.status()`
says why; `vlm.stats()` has load time and the last call's prefill/generation timings).
`python -m engine.vlm [task.json …]` is the smoke test: renders each source and asks one question.

## Bench protocol (`tools/vlm_bench.py`)

20 designs: the three samples + 17 Crello designs from `eval/data/designs` (seeded shuffle, 3–14 elements),
rendered at 896 px with `engine.render.render_design`; CPU only, 8 threads, each model alone on the machine.

1. **Set-of-marks roles.** One numbered magenta box per analyzer unit (groups as one box, backgrounds
   skipped, reading order); the model returns `{"roles": {n: role}}` with the role enum from
   `engine/analyze.py` (grammar-enforced). Two prompt variants: *plain* (image only) and *hinted* (the
   prompt also lists each box's element types and text content — information every task gives the engine).
   Agreement is per box against the **current** analyzer (`A.analyze`, S3's v3 roles); *coarse* merges
   hero/image, badge/shape/decorative/panel and subhead/body/fine_print. *known-id* is the agreement on the
   sample boxes whose ids name the role (`headline`, `cta`, `badge1_bg`, …). Run at 448 and 672 px.
2. **Judge probes.** The source render (good) vs a copy with 40 % of the content units shifted by 30 % of
   the canvas (bad; 14 of the 20 perturbations cause new collisions per `rectify.unwanted_overlaps`).
   *composite*: one A|B image; *two_images*: both renders in one prompt; both asked **in both orders** and
   counted correct only if the model picks the good one twice (*position-locked* = same answer in both
   orders). *absolute*: each render scored 1–5 on overlap_free / readable / balanced / intentional, correct
   if the good render's sum is higher.

Per call the adapter reports prefill (image encode + prompt eval), generation time and tokens.

## Results

### Set-of-marks role labelling

| model | GGUF (text + mmproj) | load s | variant | exact | coarse | known-id acc | prefill s | gen s | tok/s | total s per call (p50 / max) |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen3vl-4b | 2.50 + 0.45 GB | 2.8 | hinted@448 | 0.43 | 0.75 | 16/20 | 4.9 | 2.4 | 23 | 7.4 / 13.1 |
| qwen3vl-4b | | | hinted@672 | 0.43 | 0.75 | 17/20 | 7.7 | 2.3 | 22 | 9.3 / 16.3 |
| qwen3vl-4b | | | plain@448 | 0.34 | 0.55 | 16/20 | 4.1 | 2.1 | 23 | 6.7 / 16.5 |
| qwen3vl-4b | | | plain@672 | 0.29 | 0.53 | 17/20 | 7.0 | 2.1 | 22 | 8.4 / 18.9 |
| qwen3vl-2b | 1.11 + 0.45 GB | 1.2 | hinted@448 | 0.40 | 0.70 | 11/20 | 2.2 | 1.1 | 41 | 3.1 / 4.7 |
| qwen3vl-2b | | | hinted@672 | 0.40 | 0.69 | 11/20 | 3.7 | 1.1 | 41 | 4.5 / 9.0 |
| qwen3vl-2b | | | plain@448 | 0.30 | 0.44 | 6/20 | 2.0 | 1.1 | 41 | 2.9 / 4.4 |
| qwen3vl-2b | | | plain@672 | 0.34 | 0.48 | 12/20 | 3.6 | 1.1 | 40 | 4.2 / 8.4 |
| lfm2vl-1.6b | 0.70 + 0.56 GB | 0.4 | hinted@448 | 0.15 | 0.27 | 8/20 | 1.7 | 0.6 | 83 | 2.2 / 3.5 |
| lfm2vl-1.6b | | | hinted@672 | 0.17 | 0.31 | 8/20 | 3.3 | 0.6 | 83 | 3.5 / 4.6 |
| lfm2vl-1.6b | | | plain@448 | 0.14 | 0.22 | 6/20 | 1.6 | 0.6 | 82 | 2.1 / 3.5 |
| lfm2vl-1.6b | | | plain@672 | 0.08 | 0.18 | 3/20 | 3.1 | 0.6 | 83 | 3.5 / 4.6 |
| smolvlm2-500m | 0.44 + 0.11 GB | 0.3 | hinted@448 | 0.14 | 0.27 | 1/20 | 1.5 | 0.4 | 112 | 1.9 / 2.3 |
| smolvlm2-500m | | | hinted@672 | 0.13 | 0.26 | 1/20 | 1.5 | 0.5 | 111 | 2.0 / 2.3 |
| smolvlm2-500m | | | plain@448 | 0.13 | 0.19 | 6/20 | 1.4 | 0.4 | 113 | 1.8 / 2.5 |
| smolvlm2-500m | | | plain@672 | 0.14 | 0.20 | 6/20 | 1.4 | 0.4 | 114 | 1.9 / 2.2 |
| moondream2 | 2.84 + 0.91 GB | 1.1 | all | [pending rerun] | | | ~5.4 | 1.3 | 30 | 6.7 |

Reading the 4B's hinted@672 confusion: logo 3/3, badge 4/4, headline 15/20, cta 6/9, hero → "image" 9/11
(the enum's hero/image distinction is ours, not the model's), subhead 5/14 and body 1/21 (the Crello
"body" boxes are mostly short lines the model calls badge/headline/cta — the analyzer's label is a guess
there too), and the analyzer's "shape" boxes come back as decorative/panel (merged by *coarse*). Where the
sample ids give ground truth the 4B is right on 17 of 20 boxes; its misses are ribbon → cta (L3) and the
L2 decorative circles → panel.

Reading the 2B's hinted@672 confusion (analyzer role → what the model said): headline 15/20 right;
hero → "image" 11/11 and panel → "shape" 17/17 (both merged by *coarse*); logo → "image" 3/3 (bad: the
logo asset is a small sun + wordmark); body/subhead are split between headline/subhead/body about evenly
(the analyzer's own body/subhead split on Crello text is not ground truth either). SmolVLM2 answers almost
the same role for every box; LFM2-VL is a little better but still near chance. SmolVLM2 ignores the image
size (its preprocessor resizes to a fixed grid), so 448 and 672 cost the same.

### Judge probes (good vs perturbed render)

| model | probe | correct (both orders) | correct on the 14 with real collisions | position-locked | prefill s | gen s | total s per call (p50 / max) |
|---|---|---|---|---|---|---|---|
| qwen3vl-4b | composite@672 | 1/20 | 1/14 | 19/20 | 5.7 | 1.2 | 7.2 / 14.5 |
| qwen3vl-4b | two_images@672 | **12/20** | **9/14** | 6/20 | 10.9 | 1.2 | 11.9 / 46.7 |
| qwen3vl-4b | absolute@672 | 5/20, 14 ties | 3/14 | – | 6.0 | 1.2 | 7.1 / 24.3 |
| qwen3vl-2b | composite@672 | 0/20 | 0/14 | 20/20 | 2.6 | 1.0 | 3.7 / 27.9 |
| qwen3vl-2b | two_images@672 | 4/20 | 4/14 | 14/20 | 5.7 | 1.0 | 6.7 / 17.7 |
| qwen3vl-2b | absolute@672 | [rerun pending; first run: 2/20, 13 ties] | | – | 3.0 | 0.7 | 3.7 / 7.3 |
| lfm2vl-1.6b | composite@672 | 1/20 | 1/14 | 19/20 | 2.5 | 0.5 | 3.1 / 4.1 |
| lfm2vl-1.6b | two_images@672 | 0/20 | 0/14 | 20/20 | 5.8 | 0.5 | 6.3 / 7.1 |
| lfm2vl-1.6b | absolute@672 | [rerun pending] | | – | 3.0 | 0.3 | 3.3 / 3.9 |
| smolvlm2-500m | composite@672 | 0/20 | 0/14 | 20/20 | 1.3 | 0.4 | 1.7 / 2.0 |
| smolvlm2-500m | two_images@672 | 0/20 | 0/14 | 20/20 | 2.5 | 0.3 | 2.9 / 3.2 |
| smolvlm2-500m | absolute@672 | [rerun pending] | | – | 1.3 | 0.2 | 1.5 / 1.7 |
| moondream2 | all | [pending rerun] | | | | | |

The 2B's composite answers are boilerplate ("Design A has a clean, balanced layout … while B has
misaligned…") for every design regardless of content: it is not looking. The first absolute run used keys
`collisions`/`readability`/… and the models answered "collisions: 0" (a count, not a 1–5 score), which the
schema's `minimum` rejected — the rerun uses `overlap_free`/`readable`/`balanced`/`intentional`.

### Docker

| image | build | size | 2B call in the container (`--network none`) |
|---|---|---|---|
| linux/arm64, prebuilt wheel (generic ARMv8) | ok | 4.42 GB on disk | 36–60 s per call (prefill 23–49 s, 2.5 tok/s) — 8× native, see above |
| linux/arm64, llama.cpp rebuilt for ARMv8.2 (`DOTPROD, MATMUL_INT8, FP16_VA` confirmed in the image) | ok (compile 51 s) | 4.54 GB on disk | 12–14 s per call (prefill 7.6–10.2 s, 8–9 tok/s), load 1.3 s — ~2× native, the Docker VM's share |
| linux/amd64 (the organizers' build; AVX2 wheel, weights, llama.cpp imports under QEMU) | ok | 1.84 GB reported (shared layers) | not timed: QEMU, and skia segfaults there (docs/DOCKER_CHECK.md) |

`python -m engine.main` with `CHAMELEON_VLM=0` in the arm64 container writes all three outputs (the two that
differ from today's local run differ only because score.py/floorplan.py/candidates.py changed after the
image was built; a local run with `CHAMELEON_VLM=0` and `=1` on the same tree is byte-identical on all three
samples, and `tests/test_vlm.py` asserts that `engine.resize`/`engine.main` never import the adapter).

Base engine image for comparison: 1.24 GB. The weights add 1.55 GB (2B) uncompressed; the 4B pair would
add 2.95 GB. Build-time download: `ARG VLM_BASE_URL` (default Hugging Face) with the sha256 pinned in the
Dockerfile; locally `python3 -m http.server 8787 --directory models` + `--build-arg
VLM_BASE_URL=http://host.docker.internal:8787` builds from the mirror in seconds.

## Recommendation

**Ship Qwen3-VL-4B-Instruct Q4_K_M + mmproj Q8_0 (2.95 GB) as the one model in the image.** The 2B is
not a usable judge and only a marginal perceiver; the fast tier is at chance on both tasks and should be
dropped (LFM2-VL / SmolVLM2 / Moondream2 all ran fine through the same adapter, so this is a capability
verdict, not a packaging one). The 4B's cost on the reference-class CPU is ~7 s per perception call at
448 px and ~12 s per two-image judge call at 672 px natively, roughly 2× that inside Docker on arm64 — so
1 perception call + 3 judge calls ≈ 45 s native / ~90 s in the container per task, within the plan's
60–120 s budget with the heuristic winner as fallback.

**Perception (S1):** use the 4B with the *hinted* set-of-marks prompt at **448 px** (672 px buys nothing
on roles and costs 2 s more). Expect ~0.75 coarse agreement; trust it for logo / hero vs decorative /
headline / CTA / badge (17/20 on the labelled sample boxes) and merge, do not replace: the hero↔image,
panel↔shape↔decorative and subhead↔body distinctions are ones the model does not share with the analyzer,
so S1 should map the model's answer onto coarse classes and let the rules keep the fine split. Keep the
number tag at the box's top-left and the enum short; grammar-constrained output means a parse failure is
never the problem, a wrong enum choice is.

**Judging (S2):** usable only as *4B, two images in one prompt, both orders, 672 px*, i.e. 2 calls (~24 s)
per comparison, accepting a verdict only when both orders agree — this reorders the clean top-K at best
pairwise, 60 % both-order accuracy on this perturbation set (64 % where the perturbation actually
collides; a single-order pick is at ~70 % but inflated by the position bias). Do not use the A|B
composite (position-locked even for the 4B) or absolute 1–5 scores (ties). Given that, S2's plan to
calibrate against human labels still decides it: if the geometric scorer's agreement with humans beats
~60–65 %, the VLM judge is not worth its 24 s per pair and the whole VLM budget should go to perception.

**Packaging:** keep `llama-cpp-python==0.3.36` from the CPU wheel index in `requirements.txt`, keep the
arm64 rebuild stage (the generic wheel is 8× slower), keep `libgomp1`, and switch the Dockerfile's default
`VLM_*` args to the 4B files (sha256 above) once S1/S2 confirm. Image size grows from 1.24 GB to ~6 GB on
disk (weights 2.95 GB); ask the organizers about the cap before freezing.
