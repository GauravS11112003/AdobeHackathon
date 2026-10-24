# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: fetch the VLM weights (GGUF) at BUILD time and verify them.
# Stage-one scoring runs with --network none, so the model must be baked in.
# Override VLM_BASE_URL to build from a local mirror (e.g. a `python -m
# http.server` serving ./models) instead of Hugging Face; the checksums are
# verified either way.
FROM --platform=$BUILDPLATFORM python:3.11-slim AS weights

# Qwen3-VL-4B-Instruct (docs/VLM_BENCH.md); the 2B pair is
# Qwen3VL-2B-Instruct-Q4_K_M.gguf 089d75c52f4b7ffc56ba998ffc50aae89fcafc755f9e7208aacca281dca6c2ae +
# mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf f9a68fabba69c3b81e153367b2c7521030b0fa8bb0de400c9599c8e6725f9c82
# in Qwen/Qwen3-VL-2B-Instruct-GGUF.
ARG VLM_BASE_URL=https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main
ARG VLM_MODEL_FILE=Qwen3VL-4B-Instruct-Q4_K_M.gguf
ARG VLM_MODEL_SHA256=66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a
ARG VLM_MMPROJ_FILE=mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
ARG VLM_MMPROJ_SHA256=30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d

WORKDIR /models
RUN python - "$VLM_BASE_URL" "$VLM_MODEL_FILE" "$VLM_MODEL_SHA256" "$VLM_MMPROJ_FILE" "$VLM_MMPROJ_SHA256" <<'PY'
import hashlib, sys, time, urllib.request
base, pairs = sys.argv[1].rstrip("/"), list(zip(sys.argv[2::2], sys.argv[3::2]))
for name, want in pairs:
    url = base + "/" + name
    for attempt in range(5):
        try:
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=120) as r, open(name, "wb") as f:
                while True:
                    chunk = r.read(1 << 22)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
            got = h.hexdigest()
            if got != want:
                raise RuntimeError("sha256 mismatch for %s: %s != %s" % (name, got, want))
            print("fetched", name, "sha256", got, flush=True)
            break
        except Exception as exc:
            print("attempt", attempt + 1, "failed:", exc, flush=True)
            if attempt == 4:
                raise
            time.sleep(10)
PY

# ---------------------------------------------------------------------------
# Stage 2 (arm64 only): rebuild llama-cpp-python with the ARMv8.2 CPU kernels.
# The prebuilt aarch64 wheel is compiled for generic ARMv8 (no DOTPROD /
# MATMUL_INT8 / FP16): ~8x slower on Apple Silicon. On x86_64 the wheel
# (AVX2) is kept and this stage only leaves an empty /wheels directory.
FROM python:3.11-slim AS lcp
WORKDIR /wheels
RUN if [ "$(uname -m)" = "aarch64" ]; then \
        apt-get update && apt-get install -y --no-install-recommends build-essential cmake ninja-build \
        && rm -rf /var/lib/apt/lists/* \
        && CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+i8mm+fp16" \
           CMAKE_BUILD_PARALLEL_LEVEL=8 \
           pip wheel --no-cache-dir --no-deps --no-binary llama-cpp-python -w /wheels llama-cpp-python==0.3.36; \
    fi

# ---------------------------------------------------------------------------
# Stage 3: the engine image (as shipped by the organizers, plus the weights).
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# System libs some renderer backends (e.g. skia) need at runtime, plus git
# (build-time only) so pip can install cr-renderer straight from its repo,
# plus libgomp1 (OpenMP runtime of the llama.cpp build from stage 2).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libegl1 \
    libglib2.0-0 \
    fontconfig \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# arm64: swap in the optimised llama-cpp-python build from stage 2 (no-op on x86_64)
COPY --from=lcp /wheels/ /wheels/
RUN if ls /wheels/*.whl >/dev/null 2>&1; then pip install --no-cache-dir --no-deps --force-reinstall /wheels/*.whl; fi \
    && rm -rf /wheels

# If you add dependencies for your own resize() approach, add them to
# requirements.txt above — everything needed must install at BUILD time.
# Stage-one scoring runs with --network none, so nothing at runtime can
# reach out to the internet (no pip installs, no API calls, no model
# downloads at run time — pull those in during the build instead).

COPY chameleon_design_schema_v0.9.json .
COPY brand_kit/ ./brand_kit/
COPY renderer/ ./renderer/
COPY engine/ ./engine/

# VLM weights from stage 1 (engine/vlm.py finds them in /app/models;
# CHAMELEON_VLM=0 disables the model entirely).
COPY --from=weights /models/ ./models/

# input/ and output/ are mounted as volumes at run time (see README) —
# not baked into the image.
RUN mkdir -p /app/input /app/output

ENTRYPOINT ["python", "-m", "engine.main"]
