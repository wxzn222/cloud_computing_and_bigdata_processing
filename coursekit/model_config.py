"""Frozen defaults for the optional local-model teaching path.

The base lexical/extractive path does not import or use this module's model
dependencies.  Challenge models must be selected explicitly and are not part
of the release-validated default combination.
"""

from __future__ import annotations

import os


MODELSCOPE_ENDPOINT = "https://modelscope.cn"

BGE_MODEL_ID = "BAAI/bge-small-zh-v1.5"
BGE_REVISION = "7999e1d3359715c523056ef9478215996d62a620"
BGE_SOURCE_REVISION = "8399f11f8da998fe932df2684586c92024219d05"
BGE_FILES = (
    ("1_Pooling/config.json", 190, "aaa8861589f80c961a03cc86c7eeaef7605c1676b9ab55329d33a304738769c6"),
    ("config.json", 776, "3853a7979202c348751b753e36f579c41d8da7d36af617d3d907e1fc9b441f2a"),
    ("config_sentence_transformers.json", 124, "940d5f50db195fa6e5e6a4f122c095f77880de259d74b14a65779ed48bdd7c56"),
    ("model.safetensors", 95_827_648, "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026"),
    ("modules.json", 349, "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf"),
    ("README.md", 27_670, "c48a4eeea77f6b1d38b48ec1c5b8d4f86d5550cc43fa345a0db1b2ca1d082369"),
    ("sentence_bert_config.json", 52, "84e39fda68ccbff05bfa723ae9c0e70e23e2ec373b76e0f8c6e71af72a693cbf"),
    ("special_tokens_map.json", 125, "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3"),
    ("tokenizer.json", 439_125, "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26"),
    ("tokenizer_config.json", 367, "e6f3b96db926a37d4039995fbf5ad17de158dfb8f6343d607e4dbaad18d75f5a"),
    ("vocab.txt", 109_540, "45bbac6b341c319adc98a532532882e91a9cefc0329aa57bac9ae761c27b291c"),
)

GENERATION_REPO_ID = "ggml-org/Qwen3.5-0.8B-GGUF"
GENERATION_REPO_REVISION = "8fea620810c4afa23dd6443f999a48574c1611a3"
GENERATION_SOURCE_REVISION = "f4fd0fca9036bac9116b2abf38797fad94b0087e"
GENERATION_GGUF_FILE = "Qwen3.5-0.8B-Q8_0.gguf"
GENERATION_GGUF_BYTES = 833_592_096
GENERATION_GGUF_SHA256 = "37ae482d336108d23516fa35e8e0c4126688d81018b87178a18d752a1357814f"
GENERATION_QUANTIZATION = "Q8_0"
DEFAULT_OLLAMA_MODEL = "bdp-qwen35:0.8b-q8_0"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_CONTEXT = 2048
DEFAULT_OLLAMA_PREDICT = 256
DEFAULT_OLLAMA_THREADS = 2
DEFAULT_OLLAMA_GPU_LAYERS = 0
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def ollama_runtime_config() -> dict:
    """Return explicit local runtime settings; never auto-enable a GPU."""
    return {
        "model": os.environ.get("BDP_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        "base_url": os.environ.get("BDP_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/"),
        "timeout_seconds": _bounded_int(
            "BDP_OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT_SECONDS, 1, 600
        ),
        "options": {
            "temperature": 0,
            "num_predict": _bounded_int(
                "BDP_OLLAMA_NUM_PREDICT", DEFAULT_OLLAMA_PREDICT, 1, 4096
            ),
            "num_gpu": _bounded_int(
                "BDP_OLLAMA_NUM_GPU", DEFAULT_OLLAMA_GPU_LAYERS, 0, 999
            ),
            "num_ctx": _bounded_int(
                "BDP_OLLAMA_NUM_CTX", DEFAULT_OLLAMA_CONTEXT, 256, 32768
            ),
            "num_thread": _bounded_int(
                "BDP_OLLAMA_NUM_THREAD", DEFAULT_OLLAMA_THREADS, 1, 128
            ),
        },
    }
