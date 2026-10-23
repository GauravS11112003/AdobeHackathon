# Docker check — 2026-10-20

Machine: Apple Silicon Mac, Docker Desktop 29.5, Rosetta for x86 emulation **off** (QEMU used).

## What was run

```
docker build --platform linux/amd64 -t my-chameleon-engine .          # as in README
docker run --rm --network none -v input:/app/input -v out:/app/output my-chameleon-engine
```

## Results

| Image | Build | Run offline | Outcome |
|---|---|---|---|
| linux/amd64 (the Dockerfile as shipped) | 10m45s, OK | **hangs** | Container sits at 0% CPU with no output. Every Python import (numpy, PIL, skia, pyarrow, datasets, cr_renderer, engine) finishes in ~2 s, but both `resize()` and the organizers' own `render_design_to_png()` hang. QEMU logs `uncaught target signal 11 (Segmentation fault)`: skia crashes under QEMU x86 emulation. |
| linux/arm64 (same Dockerfile, `--platform` line dropped) | ~6 min, OK | **4 s** | All six outputs written, real renders. Level 1 JSON identical to the local run. |

Level 2/3 JSON differed slightly from the local run, most likely because the judge-loop session was
editing engine/*.py between the image build and the local comparison (Level 1, which that work did
not touch at the time, was byte-identical). Re-check once the engine is stable: rebuild and diff.

## Why this matters

The reference scoring machine is an Apple M5 Pro, i.e. Apple Silicon. If the organizers build and
run the `linux/amd64` image there with Rosetta disabled, the renderer segfaults and **every** engine
hangs, including the baseline. With Rosetta enabled (Docker Desktop default on recent versions) it
may work; unverified here.

## Actions

1. Ask the organizers (add to the open-questions list): do they run the amd64 image under Rosetta, or
   can we ship a multi-arch / arm64 image? Mention that `render_design_to_png` segfaults under QEMU.
2. Keep our engine free of anything that makes emulation worse (no extra native extensions, no
   multiprocessing). Rendering inside `resize()` for scoring candidates is the one risk: if the
   renderer is broken in the judges' container, resize() must still return a layout. Guard the
   render call with a timeout/fallback so a renderer failure degrades to heuristic scoring.
3. Before submission: rebuild amd64, test on a machine with Rosetta on (or ask a teammate with an
   Intel Mac / Linux box), and diff outputs against the local run.

## Handy commands

Native image for fast local Docker testing (not what the judges build):

```
sed 's#^FROM --platform=linux/amd64 #FROM #' Dockerfile > /tmp/Dockerfile.arm64
docker build --platform linux/arm64 -f /tmp/Dockerfile.arm64 -t my-chameleon-engine:arm64 .
docker run --rm --network none --platform linux/arm64 -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" my-chameleon-engine:arm64
```
