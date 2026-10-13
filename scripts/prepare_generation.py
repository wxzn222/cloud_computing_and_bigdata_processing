"""Prepare, verify, and optionally import the frozen local Qwen GGUF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from coursekit.model_config import (
    DEFAULT_OLLAMA_CONTEXT,
    DEFAULT_OLLAMA_GPU_LAYERS,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_PREDICT,
    GENERATION_GGUF_BYTES,
    GENERATION_GGUF_FILE,
    GENERATION_GGUF_SHA256,
    GENERATION_QUANTIZATION,
    GENERATION_REPO_ID,
    GENERATION_REPO_REVISION,
    GENERATION_SOURCE_REVISION,
    MODELSCOPE_ENDPOINT,
)
from coursekit.download_policy import download_verified, public_url


DEFAULT_OUTPUT = ROOT / "models" / "qwen35"
DEFAULT_MANIFEST = ROOT / "models" / "generation-manifest.json"
DEFAULT_ARTIFACT_URL = (
    f"{MODELSCOPE_ENDPOINT}/models/{GENERATION_REPO_ID}/resolve/"
    f"{GENERATION_SOURCE_REVISION}/{GENERATION_GGUF_FILE}"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_gguf(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"GGUF not found: {path}")
    size = path.stat().st_size
    if size != GENERATION_GGUF_BYTES:
        raise RuntimeError(f"GGUF byte size mismatch: expected {GENERATION_GGUF_BYTES}, got {size}")
    digest = file_sha256(path)
    if digest != GENERATION_GGUF_SHA256:
        raise RuntimeError(f"GGUF SHA256 mismatch: expected {GENERATION_GGUF_SHA256}, got {digest}")
    return {"bytes": size, "sha256": digest}


def modelfile_text() -> str:
    return (
        f"FROM ./{GENERATION_GGUF_FILE}\n"
        f"PARAMETER num_ctx {DEFAULT_OLLAMA_CONTEXT}\n"
        f"PARAMETER num_predict {DEFAULT_OLLAMA_PREDICT}\n"
        f"PARAMETER num_gpu {DEFAULT_OLLAMA_GPU_LAYERS}\n"
        "PARAMETER temperature 0\n"
    )


def write_prepared_manifest(output_dir: Path, manifest_path: Path, source_kind: str,
                            download: dict | None = None) -> dict:
    gguf = output_dir / GENERATION_GGUF_FILE
    verified = verify_gguf(gguf)
    modelfile = output_dir / "Modelfile"
    modelfile.write_text(modelfile_text(), encoding="utf-8")
    manifest = {
        "schema": 2,
        "repo_id": GENERATION_REPO_ID,
        "repo_revision": GENERATION_REPO_REVISION,
        "source_repo_id": GENERATION_REPO_ID,
        "source_revision": GENERATION_SOURCE_REVISION,
        "filename": GENERATION_GGUF_FILE,
        "quantization": GENERATION_QUANTIZATION,
        "artifact_bytes": verified["bytes"],
        "artifact_sha256": verified["sha256"],
        "source_kind": source_kind,
        "download_endpoint": MODELSCOPE_ENDPOINT,
        "source_reference_url": DEFAULT_ARTIFACT_URL,
        "source_url": download.get("request_url") if download else None,
        "redirect_hosts": download.get("redirect_hosts", []) if download else [],
        "final_host": download.get("final_host") if download else None,
        "ollama_tag": DEFAULT_OLLAMA_MODEL,
        "modelfile": str(modelfile.relative_to(manifest_path.parent)).replace("\\", "/")
        if modelfile.is_relative_to(manifest_path.parent) else str(modelfile),
        "modelfile_sha256": file_sha256(modelfile),
        "runtime_defaults": {
            "think": False,
            "num_ctx": DEFAULT_OLLAMA_CONTEXT,
            "num_predict": DEFAULT_OLLAMA_PREDICT,
            "num_gpu": DEFAULT_OLLAMA_GPU_LAYERS,
        },
        "note": "Community GGUF conversion, distinct from the official Ollama tag and digest.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def prepare(local_file: Path | None, output_dir: Path, manifest_path: Path,
            artifact_url: str = DEFAULT_ARTIFACT_URL,
            allowed_hosts: set[str] | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / GENERATION_GGUF_FILE
    if local_file:
        source = local_file.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Local GGUF not found: {source}")
        verify_gguf(source)
        if source != destination.resolve():
            temporary = destination.with_name(destination.name + ".part")
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, destination)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        source_kind = "local-distribution"
        download = None
    else:
        hosts = set(allowed_hosts or ())
        if public_url(artifact_url) == DEFAULT_ARTIFACT_URL:
            hosts.add("modelscope.cn")
            source_kind = "modelscope"
        else:
            if not hosts:
                raise ValueError("A custom --artifact-url requires at least one --allowed-host")
            source_kind = "custom-mirror"
        download = download_verified(
            artifact_url, destination, GENERATION_GGUF_BYTES,
            GENERATION_GGUF_SHA256, hosts,
        )
    return write_prepared_manifest(output_dir, manifest_path, source_kind, download)


def verify_prepared(output_dir: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = {
        "repo_id": GENERATION_REPO_ID,
        "repo_revision": GENERATION_REPO_REVISION,
        "source_repo_id": GENERATION_REPO_ID,
        "source_revision": GENERATION_SOURCE_REVISION,
        "source_reference_url": DEFAULT_ARTIFACT_URL,
        "filename": GENERATION_GGUF_FILE,
        "quantization": GENERATION_QUANTIZATION,
        "artifact_bytes": GENERATION_GGUF_BYTES,
        "artifact_sha256": GENERATION_GGUF_SHA256,
        "ollama_tag": DEFAULT_OLLAMA_MODEL,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise RuntimeError(f"Generation manifest mismatch for {key}")
    verified = verify_gguf(output_dir / GENERATION_GGUF_FILE)
    modelfile = output_dir / "Modelfile"
    if not modelfile.is_file() or file_sha256(modelfile) != manifest.get("modelfile_sha256"):
        raise RuntimeError("Modelfile missing or SHA256 mismatch")
    if modelfile.read_text(encoding="utf-8-sig") != modelfile_text():
        raise RuntimeError("Modelfile settings differ from the frozen CPU defaults")
    return manifest


def ollama_digest(base_url: str, tag: str) -> str:
    with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=10) as response:
        body = json.load(response)
    digest = next((item.get("digest") for item in body.get("models", [])
                   if item.get("name") == tag or item.get("model") == tag), None)
    if not digest:
        raise RuntimeError(f"Imported Ollama tag not found: {tag}")
    return digest


def import_ollama(output_dir: Path, manifest_path: Path, base_url: str) -> dict:
    manifest = verify_prepared(output_dir, manifest_path)
    base_url = base_url.rstrip("/")
    environment = {**os.environ, "OLLAMA_HOST": base_url}
    subprocess.run(["ollama", "create", DEFAULT_OLLAMA_MODEL, "-f", str(output_dir / "Modelfile")],
                   check=True, env=environment)
    digest = ollama_digest(base_url, DEFAULT_OLLAMA_MODEL)
    manifest["ollama_digest"] = digest
    manifest["ollama_base_url"] = base_url.rstrip("/")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the frozen Qwen3.5 GGUF for offline Ollama")
    parser.add_argument("action", choices=["prepare", "verify", "import-ollama"])
    parser.add_argument("--local-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--artifact-url", default=DEFAULT_ARTIFACT_URL,
                        help="Pinned ModelScope URL, or a custom static mirror with the same SHA256")
    parser.add_argument("--allowed-host", action="append", default=[],
                        help="Additional allowed redirect host for a custom mirror")
    parser.add_argument("--ollama-url", default=os.environ.get("BDP_OLLAMA_URL", "http://127.0.0.1:11434"))
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    manifest_path = args.manifest.resolve()
    if args.action == "prepare":
        result = prepare(args.local_file, output_dir, manifest_path,
                         args.artifact_url, set(args.allowed_host))
    elif args.action == "verify":
        result = verify_prepared(output_dir, manifest_path)
    else:
        result = import_ollama(output_dir, manifest_path, args.ollama_url)
    print(json.dumps({"status": args.action, "tag": result["ollama_tag"],
                      "sha256": result["artifact_sha256"],
                      "ollama_digest": result.get("ollama_digest")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
