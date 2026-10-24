"""engine.vlm: the VLM adapter without any weights (stub backends).

Covers JSON parsing and schema validation, the CHAMELEON_VLM=0 off switch,
the timeout and failure fallbacks (never raising into the engine), the
result cache (memory + disk), image preparation and model-path discovery."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

from engine import vlm

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["ad", "poster"]},
        "roles": {"type": "object", "patternProperties": {"^[0-9]+$": {"type": "string"}},
                  "additionalProperties": False},
        "order": {"type": "array", "items": {"type": "integer", "minimum": 0}, "maxItems": 5},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["kind", "roles"],
    "additionalProperties": False,
}
GOOD = {"kind": "ad", "roles": {"1": "headline", "2": "cta"}, "order": [1, 2], "score": 0.5}


class Stub:
    """A backend that returns canned text, optionally slowly or by raising."""

    def __init__(self, text=None, delay=0.0, raise_exc=None, stop_at_deadline=False):
        self.text = json.dumps(GOOD) if text is None else text
        self.delay = delay
        self.raise_exc = raise_exc
        self.stop_at_deadline = stop_at_deadline
        self.calls = 0
        self.last = {}
        self.model_path = Path("stub.gguf")

    def complete(self, png, prompt, schema, max_tokens, deadline):
        self.calls += 1
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        if self.raise_exc:
            raise self.raise_exc
        if self.delay:
            time.sleep(self.delay)
        self.last = {"prefill_s": self.delay, "gen_s": 0.0, "gen_tokens": 3,
                     "stopped_at_deadline": self.stop_at_deadline}
        return self.text


@pytest.fixture
def fresh(monkeypatch):
    vlm._reset_for_tests()
    for k in ("CHAMELEON_VLM", "CHAMELEON_VLM_MODEL", "CHAMELEON_VLM_MMPROJ",
              "CHAMELEON_VLM_DIR", "CHAMELEON_VLM_CACHE_DIR"):
        monkeypatch.delenv(k, raising=False)
    yield
    vlm._reset_for_tests()


def image(w=1200, h=800, color=(200, 30, 30)):
    return Image.new("RGB", (w, h), color)


# ---------------------------------------------------------------------------
# parsing / validation


@pytest.mark.parametrize("text", [
    json.dumps(GOOD),
    "```json\n" + json.dumps(GOOD) + "\n```",
    "Sure, here is the answer:\n" + json.dumps(GOOD) + "\nHope that helps.",
    json.dumps(GOOD, indent=2),
])
def test_parse_json_finds_the_object(text):
    assert vlm.parse_json(text) == GOOD


def test_parse_json_handles_braces_inside_strings():
    obj = {"headline": "Wow } { \"quoted\"", "n": 1}
    assert vlm.parse_json("x " + json.dumps(obj) + " y") == obj


@pytest.mark.parametrize("text", ["", "   ", "[1, 2]", "42", "{not json", None, "{} trailing {", "\"str\""])
def test_parse_json_rejects_non_objects(text):
    assert vlm.parse_json(text) in (None, {})


def test_validate_accepts_good():
    assert vlm.validate(GOOD, SCHEMA) == []


@pytest.mark.parametrize("bad", [
    {"kind": "banner", "roles": {}},                       # enum
    {"roles": {}},                                          # required
    {"kind": "ad", "roles": {}, "extra": 1},                # additionalProperties
    {"kind": "ad", "roles": {"x": "headline"}},             # patternProperties key
    {"kind": "ad", "roles": {"1": 2}},                      # value type
    {"kind": "ad", "roles": {}, "order": [1, -1]},          # minimum
    {"kind": "ad", "roles": {}, "order": [1, 2, 3, 4, 5, 6]},   # maxItems
    {"kind": "ad", "roles": {}, "order": [True]},           # bool is not integer
    {"kind": "ad", "roles": {}, "score": 2},                # maximum
    [GOOD],                                                 # not an object
])
def test_validate_rejects_bad(bad):
    assert vlm.validate(bad, SCHEMA)


# ---------------------------------------------------------------------------
# switches and fallbacks


def test_off_switch_never_touches_the_backend(fresh, monkeypatch):
    monkeypatch.setenv("CHAMELEON_VLM", "0")
    stub = Stub()
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p", SCHEMA) is None
    assert stub.calls == 0
    assert not vlm.available()
    assert vlm.status().startswith("off: CHAMELEON_VLM=0")


def test_no_model_files_means_none_without_raising(fresh, monkeypatch, tmp_path):
    monkeypatch.setenv("CHAMELEON_VLM_DIR", str(tmp_path))
    assert vlm.model_paths() is None
    assert not vlm.available()
    assert vlm.describe(image(), "p", SCHEMA) is None
    assert vlm.status().startswith("off: no model")


def test_stub_backend_round_trip(fresh):
    stub = Stub()
    vlm.set_backend(stub)
    assert vlm.available()
    out = vlm.describe(image(), "what?", SCHEMA)
    assert out == GOOD
    assert stub.calls == 1
    st = vlm.stats()
    assert st["calls"] == 1 and st["last"]["cached"] is False and "total_s" in st["last"]


@pytest.mark.parametrize("text", ["not json at all", json.dumps({"kind": "banner", "roles": {}}), "[1,2]", ""])
def test_bad_output_is_none(fresh, text):
    vlm.set_backend(Stub(text=text))
    assert vlm.describe(image(), "p", SCHEMA) is None


def test_raising_backend_is_contained_and_eventually_disabled(fresh):
    stub = Stub(raise_exc=RuntimeError("boom"))
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p1", SCHEMA) is None
    assert vlm.status().startswith("on") or vlm.status().startswith("ready")
    assert vlm.describe(image(), "p2", SCHEMA) is None
    assert vlm.status().startswith("off: backend raised 2 times")
    assert vlm.describe(image(), "p3", SCHEMA) is None
    assert stub.calls == 2           # disabled: no further backend calls


def test_timeout_returns_none_and_disables_after_two(fresh):
    stub = Stub(text='{"kind": "ad", "ro', delay=0.05)
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p1", SCHEMA, timeout_s=0.01) is None
    assert vlm.stats()["timeouts"] == 1
    assert vlm.describe(image(), "p2", SCHEMA, timeout_s=0.01) is None
    assert vlm.status().startswith("off: 2 calls timed out")
    assert vlm.describe(image(), "p3", SCHEMA, timeout_s=10) is None
    assert stub.calls == 2


def test_timed_out_call_with_complete_json_is_still_used(fresh):
    stub = Stub(stop_at_deadline=True)
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p", SCHEMA, timeout_s=5) == GOOD
    assert vlm.stats()["timeouts"] == 1


def test_describe_never_raises_on_garbage_input(fresh):
    vlm.set_backend(Stub())
    assert vlm.describe("not an image", "p", SCHEMA) is None
    assert vlm.describe(image(), "p", "not a schema") is None or True


# ---------------------------------------------------------------------------
# cache


def test_memory_cache_by_image_and_prompt(fresh):
    stub = Stub()
    vlm.set_backend(stub)
    a = vlm.describe(image(), "p", SCHEMA)
    b = vlm.describe(image(), "p", SCHEMA)
    assert a == b == GOOD and stub.calls == 1
    assert vlm.stats()["last"] == {"cached": True}
    a["roles"]["9"] = "mutated"
    assert vlm.describe(image(), "p", SCHEMA) == GOOD          # cache hands out copies
    vlm.describe(image(), "other prompt", SCHEMA)
    assert stub.calls == 2
    vlm.describe(image(color=(0, 0, 255)), "p", SCHEMA)
    assert stub.calls == 3
    vlm.describe(image(), "p", SCHEMA, max_tokens=999)
    assert stub.calls == 4
    vlm.describe(image(), "p", SCHEMA, use_cache=False)
    assert stub.calls == 5


def test_bad_answers_are_cached_too(fresh):
    stub = Stub(text="garbage")
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p", SCHEMA) is None
    assert vlm.describe(image(), "p", SCHEMA) is None
    assert stub.calls == 1


def test_disk_cache_survives_a_reset(fresh, monkeypatch, tmp_path):
    monkeypatch.setenv("CHAMELEON_VLM_CACHE_DIR", str(tmp_path / "cache"))
    stub = Stub()
    vlm.set_backend(stub)
    assert vlm.describe(image(), "p", SCHEMA) == GOOD
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1
    vlm._reset_for_tests()
    stub2 = Stub(text="garbage")
    vlm.set_backend(stub2)
    assert vlm.describe(image(), "p", SCHEMA) == GOOD
    assert stub2.calls == 0


# ---------------------------------------------------------------------------
# images and model discovery


@pytest.mark.parametrize("size,max_side,expected", [
    ((1200, 800), 672, (672, 448)),
    ((800, 1200), 448, (299, 448)),
    ((300, 200), 672, (300, 200)),      # never upscaled
    ((1080, 1080), 672, (672, 672)),
])
def test_prepare_image_downscales_long_side(size, max_side, expected):
    png = vlm.prepare_image(Image.new("RGBA", size, (1, 2, 3, 255)), max_side)
    img = Image.open(__import__("io").BytesIO(png))
    assert img.size == expected and img.mode == "RGB"


def test_model_paths_pair_text_model_with_matching_mmproj(fresh, monkeypatch, tmp_path):
    for name in ("Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf",
                 "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setenv("CHAMELEON_VLM_DIR", str(tmp_path))
    text, proj = vlm.model_paths()
    assert text.name == "Qwen3VL-4B-Instruct-Q4_K_M.gguf"
    assert proj.name == "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"
    monkeypatch.setenv("CHAMELEON_VLM_MODEL", str(tmp_path / "a.gguf"))
    monkeypatch.setenv("CHAMELEON_VLM_MMPROJ", str(tmp_path / "b.gguf"))
    assert vlm.model_paths() == (tmp_path / "a.gguf", tmp_path / "b.gguf")
    assert not vlm.available()                      # the explicit files do not exist


def test_engine_does_not_import_the_adapter():
    """CHAMELEON_VLM=0 output is byte-identical to the engine without the
    adapter: resize() does not even import it (yet)."""
    code = "import sys, engine.resize, engine.main; print('engine.vlm' in sys.modules, 'llama_cpp' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(Path(__file__).resolve().parent.parent))
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False False"


def test_several_images_go_to_the_backend_in_order(fresh):
    class Multi(Stub):
        def complete(self, png, prompt, schema, max_tokens, deadline):
            self.calls += 1
            self.seen = png
            return self.text

    stub = Multi()
    vlm.set_backend(stub)
    assert vlm.describe([image(), image(color=(0, 0, 255))], "which?", SCHEMA) == GOOD
    assert isinstance(stub.seen, list) and len(stub.seen) == 2 and stub.seen[0] != stub.seen[1]
    assert vlm.describe([image(), image(color=(0, 0, 255))], "which?", SCHEMA) == GOOD
    assert stub.calls == 1                                   # cached by both images
    assert vlm.describe([image(color=(0, 0, 255)), image()], "which?", SCHEMA) == GOOD
    assert stub.calls == 2                                   # order matters
