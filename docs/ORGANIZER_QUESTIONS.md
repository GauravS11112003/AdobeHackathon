# Message to the CHAMELEON organizers (draft, 2026-10-20)

Subject: CHAMELEON stage one: container runtime on Apple Silicon, plus three rule questions

Hi team,

We have the starter kit running and wanted to flag one thing we found while testing the Docker
setup, and confirm three rules the brief says are still being finalized.

**1. The amd64 image hangs on Apple Silicon unless Rosetta is on.**
Following the README exactly (`docker build --platform linux/amd64`, then `docker run --network none`)
on an M-series Mac with Docker Desktop, the container starts but never writes output. Every import
succeeds, but the first call into the renderer (`render_design_to_png`, i.e. skia) segfaults under
QEMU emulation, so the process hangs at 0% CPU. This happens with the untouched baseline engine too,
not just ours. Rebuilding the same Dockerfile for linux/arm64 runs the three samples offline in about
four seconds.

Since the reference machine is an Apple M5 Pro, could you confirm how the image will be run there?
Specifically: is "Use Rosetta for x86_64/amd64 emulation" enabled in Docker Desktop on the scoring
machine, or would you accept a multi-arch or arm64 image? We are happy to ship whichever you prefer.

**2. Reference hardware.** RULES.md lists the M5 Pro with CPU, RAM and disk still to be confirmed.
Could you share the core count, memory, and whether the GPU is usable from inside the container?

**3. Model size cap and approved list.** The brief mentions a shared size limit and a list of
permitted open models. Are these available yet? We are currently model-free and would only add a
small open vision model as a ranking tie-breaker if it is allowed.

**4. Two small schema questions.** Is changing an image's `fit` (contain/cover) allowed, and is
low-opacity decorative bleed off the canvas tolerated by the structural check, as in the Level 2
sample's corner circle?

Thanks for the well-built starter kit; the renderer-in-the-loop setup is a great way to work.

Best,
Gaurav
