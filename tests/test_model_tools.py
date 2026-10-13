import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from coursekit.intelligence import answer, build_index, embedding_model_selection, local_model_revision
from coursekit.model_config import BGE_MODEL_ID
from coursekit import download_policy
from coursekit.artifact_identity import revision_from_hashes
from coursekit.model_config import DEFAULT_OLLAMA_MODEL, ollama_runtime_config
from scripts import artifact_manifest, prepare_embedding, prepare_generation


def test_runtime_defaults_and_explicit_gpu(monkeypatch):
    for name in ("BDP_OLLAMA_MODEL", "BDP_OLLAMA_NUM_GPU", "BDP_OLLAMA_NUM_CTX",
                 "BDP_OLLAMA_NUM_PREDICT", "BDP_OLLAMA_NUM_THREAD"):
        monkeypatch.delenv(name, raising=False)
    baseline = ollama_runtime_config()
    assert baseline["model"] == DEFAULT_OLLAMA_MODEL
    assert baseline["options"] == {
        "temperature": 0, "num_predict": 256, "num_gpu": 0, "num_ctx": 2048, "num_thread": 2
    }
    monkeypatch.setenv("BDP_OLLAMA_NUM_GPU", "12")
    assert ollama_runtime_config()["options"]["num_gpu"] == 12


def test_local_embedding_path_has_stable_public_identity(monkeypatch, tmp_path):
    model_dir = tmp_path / "private-profile" / "bge-small-zh-v1.5"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BDP_EMBED_MODEL", str(model_dir))
    monkeypatch.delenv("BDP_EMBED_MODEL_ID", raising=False)
    model_id, location, local = embedding_model_selection()
    assert model_id == BGE_MODEL_ID
    assert location == str(model_dir)
    assert local is True
    assert local_model_revision(location) == hashlib.sha256(
        ("config.json" + hashlib.sha256(b"{}").hexdigest()).encode()
    ).hexdigest()


def test_default_ollama_request_fields(monkeypatch, tmp_path):
    source = tmp_path / "documents.jsonl"
    source.write_text(json.dumps({"doc_id": "quota", "title": "配额", "version": 1,
                                  "visibility": "public", "text": "模拟服务的用户每周配额120分钟。"},
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    index = build_index(source, tmp_path / "index.json")
    chunk_id = index["chunks"][0]["chunk_id"]
    captured = {}

    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    def fake_post(url, json, timeout):
        captured.update(url=url, request=json, timeout=timeout)
        return Response({"message": {"content": f"120分钟 [{chunk_id}]"}, "eval_count": 3})

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: Response(
        {"models": [{"name": DEFAULT_OLLAMA_MODEL, "digest": "digest"}]}
    ))
    result = answer("模拟服务的用户每周配额是多少分钟？", generator="ollama", index=index)
    assert captured["request"]["model"] == DEFAULT_OLLAMA_MODEL
    assert captured["request"]["think"] is False
    assert captured["request"]["options"]["num_gpu"] == 0
    assert captured["request"]["options"]["num_ctx"] == 2048
    assert result["model_digest"] == "digest"


def test_generation_hash_mismatch_is_rejected(monkeypatch, tmp_path):
    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"bad!")
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_BYTES", 4)
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        prepare_generation.verify_gguf(artifact)


def test_custom_generation_url_requires_explicit_host(tmp_path):
    with pytest.raises(ValueError, match="requires at least one --allowed-host"):
        prepare_generation.prepare(
            None, tmp_path / "models", tmp_path / "manifest.json",
            "https://mirror.example.com/model.gguf", set(),
        )


def test_local_generation_prepare_and_verify(monkeypatch, tmp_path):
    content = b"small-test-gguf"
    source = tmp_path / "source.gguf"
    source.write_bytes(content)
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_FILE", "test.gguf")
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_BYTES", len(content))
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_SHA256", hashlib.sha256(content).hexdigest())
    output = tmp_path / "models"
    manifest = tmp_path / "generation-manifest.json"
    prepare_generation.prepare(source, output, manifest)
    verified = prepare_generation.verify_prepared(output, manifest)
    assert verified["source_kind"] == "local-distribution"
    assert verified["source_revision"] == prepare_generation.GENERATION_SOURCE_REVISION
    assert verified["ollama_tag"] == DEFAULT_OLLAMA_MODEL


def test_local_embedding_prepare_and_verify(monkeypatch, tmp_path):
    source = tmp_path / "bge-source"
    source.mkdir()
    (source / "model.safetensors").write_bytes(b"weights")
    (source / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(prepare_embedding, "BGE_FILES", (
        ("config.json", 2, hashlib.sha256(b"{}").hexdigest()),
        ("model.safetensors", 7, hashlib.sha256(b"weights").hexdigest()),
    ))
    target = tmp_path / "bge"
    manifest = tmp_path / "embedding-manifest.json"
    prepare_embedding.prepare(source, target, manifest, "local", None)
    assert prepare_embedding.verify_directory(target, manifest)["source_kind"] == "local"
    (target / "config.json").write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mismatch"):
        prepare_embedding.verify_directory(target, manifest)


def test_artifact_manifest_rejects_tamper(tmp_path):
    directory = tmp_path / "wheelhouse"
    directory.mkdir()
    wheel = directory / "example.whl"
    wheel.write_bytes(b"wheel")
    manifest = tmp_path / "wheelhouse-manifest.json"
    artifact_manifest.create_manifest(directory, manifest)
    artifact_manifest.verify_manifest(directory, manifest)
    wheel.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        artifact_manifest.verify_manifest(directory, manifest)


def test_domestic_download_rejects_foreign_final_host(monkeypatch, tmp_path):
    class Response(io.BytesIO):
        def geturl(self):
            return "https://huggingface.co/foreign/model.bin"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    class Opener:
        def open(self, request, timeout):
            return Response(b"safe")

    monkeypatch.setattr(download_policy.urllib.request, "build_opener", lambda handler: Opener())
    destination = tmp_path / "artifact.bin"
    with pytest.raises(RuntimeError, match="final host is not approved"):
        download_policy.download_verified(
            "https://modelscope.cn/model.bin", destination, 4,
            hashlib.sha256(b"safe").hexdigest(), {"modelscope.cn"},
        )
    assert not destination.exists()
    assert not destination.with_name("artifact.bin.part").exists()


@pytest.mark.parametrize("script", [
    "scripts/prepare_embedding.py", "scripts/prepare_generation.py",
    "scripts/artifact_manifest.py",
])
def test_direct_script_entrypoints(script):
    result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def frozen_embedding(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    contents = {"config.json": b"{}", "model.safetensors": b"weights", "README.md": b"model card"}
    for name, content in contents.items():
        (source / name).write_bytes(content)
    files = tuple((name, len(data), hashlib.sha256(data).hexdigest()) for name, data in contents.items())
    monkeypatch.setattr(prepare_embedding, "BGE_FILES", files)
    target, path = tmp_path / "target", tmp_path / "embedding-manifest.json"
    manifest = prepare_embedding.prepare(source, target, path, "local", None)
    return source, target, path, manifest


def test_embedding_identity_is_platform_independent(frozen_embedding):
    _, target, path, manifest = frozen_embedding
    entries = [(item["path"], item["sha256"]) for item in manifest["files"]]
    posix = sorted(entries, key=lambda item: PurePosixPath(item[0]))
    windows = sorted(entries, key=lambda item: PureWindowsPath(item[0]))
    assert posix != windows  # This fixture actually exercises the original failure.
    expected = hashlib.sha256("".join(name + digest for name, digest in posix).encode()).hexdigest()
    assert revision_from_hashes(windows) == revision_from_hashes(posix) == expected
    assert local_model_revision(str(target)) == manifest["directory_revision"] == expected
    # Manifest serialization order must not change the content identity either.
    manifest["files"].reverse()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert prepare_embedding.verify_directory(target, path)["directory_revision"] == expected


def test_embedding_rejects_extras_in_verify_and_prepare(frozen_embedding):
    source, target, path, _ = frozen_embedding
    before = path.read_bytes()
    (target / "extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="extra.json"):
        prepare_embedding.verify_directory(target, path)
    with pytest.raises(RuntimeError, match="extra.json"):
        prepare_embedding.prepare(source, target, path, "local", None)
    assert path.read_bytes() == before


def test_embedding_rejects_duplicate_manifest_entries(frozen_embedding):
    _, target, path, manifest = frozen_embedding
    manifest["files"].append(manifest["files"][0])
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="file list"):
        prepare_embedding.verify_directory(target, path)


def test_ollama_import_and_digest_use_selected_server(monkeypatch, tmp_path):
    content = b"test-gguf"
    source = tmp_path / "test.gguf"
    source.write_bytes(content)
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_FILE", source.name)
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_BYTES", len(content))
    monkeypatch.setattr(prepare_generation, "GENERATION_GGUF_SHA256", hashlib.sha256(content).hexdigest())
    target, path = tmp_path / "model", tmp_path / "generation-manifest.json"
    prepare_generation.prepare(source, target, path)
    old_server, selected = "http://127.0.0.1:11434", "http://127.0.0.1:11435"
    monkeypatch.setenv("OLLAMA_HOST", old_server)
    servers = {old_server: "old-on-A", selected: "old-on-B"}
    calls = []
    def create(argv, *, check, env):
        assert check is True
        assert argv[1:3] == ["create", DEFAULT_OLLAMA_MODEL]
        calls.append(env["OLLAMA_HOST"])
        servers[env["OLLAMA_HOST"]] = "just-imported"
    def digest(url, tag):
        assert tag == DEFAULT_OLLAMA_MODEL
        calls.append(url)
        return servers[url]
    monkeypatch.setattr(prepare_generation.subprocess, "run", create)
    monkeypatch.setattr(prepare_generation, "ollama_digest", digest)
    result = prepare_generation.import_ollama(target, path, selected + "/")
    assert calls == [selected, selected]
    assert result["ollama_digest"] == "just-imported"
    assert result["ollama_base_url"] == selected
    assert servers[old_server] == "old-on-A"
    assert os.environ["OLLAMA_HOST"] == old_server


@pytest.mark.parametrize("content, error", [(b"safe", None), (b"bad!", "SHA256 mismatch"),
                                          (b"saf", "byte size mismatch"), (b"safe-more", "exceeds")])
def test_downloader_bounds_stream_and_preserves_previous_artifact(monkeypatch, tmp_path, content, error):
    reads = []
    class Response(io.BytesIO):
        def geturl(self):
            return "https://modelscope.cn/model.bin"
        def read(self, size):
            reads.append(size)
            return super().read(size)
    class Opener:
        def open(self, request, timeout):
            return Response(content)
    monkeypatch.setattr(download_policy.urllib.request, "build_opener", lambda handler: Opener())
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"previous")
    def download():
        return download_policy.download_verified("https://modelscope.cn/model.bin", target, 4,
            hashlib.sha256(b"safe").hexdigest(), {"modelscope.cn"})
    if error:
        with pytest.raises(RuntimeError, match=error):
            download()
        assert target.read_bytes() == b"previous"
    else:
        assert download()["bytes"] == 4
        assert target.read_bytes() == b"safe"
    if error == "exceeds":
        assert reads == [5]  # Reject on the first excessive byte, without reading EOF.
    assert not target.with_name(target.name + ".part").exists()


def test_download_total_deadline_rejects_continuous_data(monkeypatch, tmp_path):
    class Response(io.BytesIO):
        def geturl(self):
            return "https://modelscope.cn/model.bin"
    class Opener:
        def open(self, request, timeout):
            assert timeout == 1
            return Response(b"safe")
    monkeypatch.setattr(download_policy.urllib.request, "build_opener", lambda handler: Opener())
    times = iter([0, 0, 2])
    monkeypatch.setattr(download_policy.time, "monotonic", lambda: next(times))
    target = tmp_path / "artifact.bin"
    with pytest.raises(TimeoutError, match="total deadline"):
        download_policy.download_verified("https://modelscope.cn/model.bin", target, 4,
            hashlib.sha256(b"safe").hexdigest(), {"modelscope.cn"}, total_timeout_seconds=1)
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()
