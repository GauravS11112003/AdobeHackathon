# Plan: adding a vision model to the engine (2026-10-23 → deadline 2026-10-30)

Organizers confirmed (verbally, to Gaurav, 2026-10-23) that a locally hosted VLM baked into the Docker
image is allowed. Size cap still unstated. Reference machine: Apple M5 Pro, assume CPU only.

## The thesis: where a model actually changes the outcome

Our engine is generate → fix → score → pick. Two places decide quality, and both are perception, not geometry:

1. **Understanding the source.** Every downstream choice (what to feature, what may shrink, which layout
   family) depends on roles and hierarchy. Our rules fail on text-heavy designs (Boynton: headline
   misread, underline bars orphaned). A VLM *sees* hierarchy the way a human does.
2. **Choosing the winner.** The official scorer is an AI looking at the rendered PNG against a rubric
   (collisions, readability, brand, intentional). Our scorer measures geometry proxies. A VLM judging our
   renders with the same rubric aligns our objective with theirs. This is the single largest lever:
   DesignSense (Adobe MDSR) reports +3.6% win rate just from generate-10-and-rank with a judge.

What a model must **not** do: write coordinates (benso10's dead end; structural checks fail it) or replace
the rules (they are the floor that guarantees validity and speed).

## Architecture after the change

```
source JSON ──render──► source PNG + numbered boxes ──VLM call 1──► roles, importance order,
                                                                   design archetype, "must survive" set
            analyze() (rules) ◄── merge: VLM overrides low-confidence rule decisions; rules fill gaps
candidates (recipes, floor plans, anchor, preserve) → rectify → geometric score → top-K clean
top-K renders ──VLM call 2 (rubric scoring / pairwise)──► final winner; guard: never a hard-fail candidate
time budget per task; any VLM failure/timeout → today's heuristic winner
```

## Model choice

Candidates that run on CPU via llama.cpp GGUF (Q4_K_M), deterministic (temp 0, fixed seed):

| Model | Weights Q4 | Notes |
|---|---|---|
| **Qwen3-VL-4B-Instruct** | ≈ 2.8 GB | best accuracy/size for grounding + JSON; first choice |
| Qwen3-VL-2B-Instruct | ≈ 1.5 GB | fallback if latency or cap bites |
| Qwen2.5-VL-3B-Instruct | ≈ 2.4 GB | proven set-of-marks behaviour; alternative |
| SmolVLM2-2.2B / Moondream2 | ≈ 1.3 GB | fastest; weaker JSON discipline |

Decide on day 1 by benchmarking latency and role-agreement on 50 Crello designs. Hard requirement: a run
with the model disabled must produce exactly today's output (flag `CHAMELEON_VLM=0`).

## Expected cost (to verify day 1)

Per VLM call on an M-class CPU, 4B Q4, image ≤ 672 px: ~2–4 s vision encode + ~3–5 s prompt + ~3–5 s for
~120 output tokens ≈ 10 s. Plan: 1 understanding call + ≤ 3 judging calls ≈ 40 s per task native; 2–3×
under Rosetta. No hard limit in the rules; "speed" is a minor row. Guardrail: per-task budget (default 60 s),
after which the heuristic winner ships.

## Workstreams (parallel sessions)

**S0 — Model bench & packaging (day 1–2).** llama-cpp-python pinned in requirements; weights downloaded in
the Dockerfile build stage (public HF repo, checksum); multi-arch image (arm64 native + amd64); latency
table native/Rosetta/QEMU; `engine/vlm.py` adapter with JSON-only prompts, strict parsing, timeout, cache
by image hash. Done = `CHAMELEON_VLM=1 python -m engine.main` works offline in Docker on arm64.

**S1 — VLM perception (day 2–4).** Render source once; draw numbered boxes (set-of-marks). Prompt returns
`{roles: {n: role}, importance: [n...], archetype: product_ad|event_poster|editorial|quote|grid|other,
must_keep: [n...], hierarchy: [n...]}`. Merge into analyze(): VLM wins when rule confidence < 0.7 or
archetype is editorial/text-heavy; groups always honoured. Validate: role agreement vs DesignAsCode labels
and our 450 Crello designs; target ≥ 0.85 agreement on headline/logo/hero/CTA, and Boynton fixed. Also feed
archetype into candidate generation (editorial → XY-cut/two-column family, not product banner).

**S2 — VLM judge (day 3–5).** Rubric prompt mirroring the brief's five rows; returns per-row 1–5 + verdict.
Modes: (a) absolute scoring of top-K, (b) pairwise against the heuristic winner. Calibrate on human labels:
add a quick A/B labelling page to the eval browser, label 150 pairs, measure VLM-vs-human agreement, and
compare with our geometric scorer's agreement. Ship only if VLM agreement > geometric. Guards: candidates
with any hard fail are never eligible; VLM can only reorder the clean top-K.

**S3 — Rule upgrades (day 2–4, independent).** From docs/COMPETITORS.md: no-render contrast estimate, units
beyond group_id (holders, panels, hosts, sibling rows), tight painted text boxes + per-role floors,
source-relative penalties + adaptation penalty. Raises every candidate's floor; also gives the judge
better material.

**S4 — Learned role classifier (day 3–5, backup to S1).** Gradient-boosted classifier on analyzer features
trained on Crello + DesignAsCode labels; < 5 MB; used when the VLM is off or times out, and as a third
vote in the merge.

**S5 — Hardening & submission (day 6–7).** Full 6k-case eval with VLM on and off (defect rate, runtime p95,
judge agreement); adversarial synthetic corpus; Docker rebuild + offline run; README explaining approach,
model, fallbacks, how to run; freeze.

## Stretch (only if S1/S2 land by day 5)

DesignSense-style judge fine-tune: LoRA on the 4B model using automatic labels (our hard-fail detector +
perturbation negatives: shift 20–50% / scale 0.8–1.2× of 70% of elements) plus the 150 human pairs; train
with MLX on the Mac; weights on a public HF repo as the rules require. High upside, high risk; cut first.

## How this makes our designs the best (and the honest limits)

- Alignment: our picker and the official judge both look at pixels against the same rubric.
- Perception: hierarchy and archetype from vision fix the failure class our harness found (text-heavy
  sources, extreme targets).
- Search: cheaper contrast + more candidates + a judge = inference-time scaling, the one technique shown to
  move the needle in Adobe's own research.
- Limits: 2–4B models judge *defects* well (cut off, overlapping, cramped, tiny) and *aesthetics* only
  modestly. So the VLM reorders clean candidates; it does not invent layouts. Latency is the main risk;
  the budget and the off-switch make it safe.

## Open questions for the organizers (ask now)

1. Image size cap and whether weights count toward it.
2. Will the amd64 image run under Rosetta on the M5 Pro, or can we ship arm64/multi-arch?
3. Approximate wall-clock they consider acceptable per task.
