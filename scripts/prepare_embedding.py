"""Prepare or verify the frozen BGE directory without student-side network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from coursekit.download_policy import download_verified
from coursekit.artifact_identity import directory_files, revision_from_hashes
from coursekit.model_config import (
    BGE_FILES,
    BGE_MODEL_ID,
    BGE_REVISION,
    BGE_SOURCE_REVISION,
    MODELSCOPE_ENDPOINT,
)


DEFAULT_TARGET = ROOT / "models" / "bge-small-zh-v1.5"
DEFAULT_MANIFEST = ROOT / "models" / "embedding-manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_directory(target: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (manifest.get("model_id") != BGE_MODEL_ID
            or manifest.get("upstream_revision") != BGE_REVISION
            or manifest.get("source_revision") != BGE_SOURCE_REVISION):
        raise RuntimeError("Embedding manifest does not identify the frozen BGE release")
    expected_files = {path: (size, digest) for path, size, digest in BGE_FILES}
    actual_files = {item.get("path"): (item.get("bytes"), item.get("sha256"))
                    for item in manifest.get("files", [])}
    if actual_files != expected_files or len(actual_files) != len(manifest.get("files", [])):
        raise RuntimeError("Embedding manifest file list differs from the frozen release")
    on_disk = set(directory_files(target))
    if on_disk != set(expected_files):
        raise RuntimeError(f"Embedding directory inventory mismatch; "
                           f"missing={sorted(set(expected_files) - on_disk)}, "
                           f"extra={sorted(on_disk - set(expected_files))}")
    revision_input = []
    for item in manifest.get("files", []):
        path = target / item["path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing embedding artifact: {item['path']}")
        if path.stat().st_size != item["bytes"]:
            raise RuntimeError(f"Embedding byte size mismatch: {item['path']}")
        actual = file_sha256(path)
        if actual != item["sha256"]:
            raise RuntimeError(f"Embedding SHA256 mismatch: {item['path']}")
        revision_input.append((item["path"], actual))
    if not (target / "model.safetensors").is_file():
        raise RuntimeError("Required safetensors weight missing")
    actual_revision = revision_from_hashes(revision_input)
    if manifest.get("directory_revision") != actual_revision:
        raise RuntimeError("Embedding directory revision mismatch")
    return manifest


def prepare(source: Path, target: Path, manifest_path: Path, source_kind: str,
            endpoint: str | None, downloads: list[dict] | None = None) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    extra = set(directory_files(target)) - {name for name, _, _ in BGE_FILES}
    if extra:
        raise RuntimeError(f"Embedding directory inventory mismatch; extra={sorted(extra)}")
    files = []
    for relative_name, expected_bytes, expected_sha256 in BGE_FILES:
        item = source / relative_name
        if not item.is_file():
            raise FileNotFoundError(f"Missing frozen BGE artifact: {relative_name}")
        if item.stat().st_size != expected_bytes or file_sha256(item) != expected_sha256:
            raise RuntimeError(f"Frozen BGE artifact mismatch: {relative_name}")
        relative = Path(relative_name)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item.resolve() != destination.resolve():
            temporary = destination.with_name(destination.name + ".part")
            try:
                shutil.copyfile(item, temporary)
                os.replace(temporary, destination)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        files.append({"path": relative.as_posix(), "bytes": expected_bytes,
                      "sha256": expected_sha256})
    if not (target / "model.safetensors").is_file():
        raise RuntimeError("Required safetensors weight missing")
    directory_revision = revision_from_hashes((item["path"], item["sha256"]) for item in files)
    manifest = {
        "model_id": BGE_MODEL_ID,
        "upstream_revision": BGE_REVISION,
        "source_revision": BGE_SOURCE_REVISION,
        "source_kind": source_kind,
        "download_endpoint": endpoint,
        "source_url_template": (
            f"{MODELSCOPE_ENDPOINT}/models/{BGE_MODEL_ID}/resolve/"
            f"{BGE_SOURCE_REVISION}/{{path}}"
        ),
        "download_hosts": sorted({record["final_host"] for record in (downloads or [])}),
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
        "directory_revision": directory_revision,
        "purpose": "Teacher-prepared frozen BGE directory for offline student use.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    verify_directory(target, manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or verify the frozen offline BGE directory")
    parser.add_argument("--local-source", type=Path,
                        help="Verified local snapshot; omit to download on the teacher machine")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        manifest = verify_directory(args.target, args.manifest)
    else:
        endpoint = None
        if args.local_source:
            source = args.local_source.resolve()
            if not source.is_dir():
                raise FileNotFoundError(f"Local BGE directory not found: {source}")
            source_kind = "local"
        else:
            endpoint = MODELSCOPE_ENDPOINT
            source = args.target.resolve()
            downloads = []
            for relative_name, expected_bytes, expected_sha256 in BGE_FILES:
                destination = source / relative_name
                url = (f"{MODELSCOPE_ENDPOINT}/models/{BGE_MODEL_ID}/resolve/"
                       f"{BGE_SOURCE_REVISION}/{quote(relative_name, safe='/')}")
                downloads.append(download_verified(
                    url, destination, expected_bytes, expected_sha256, {"modelscope.cn"}
                ))
            source_kind = "modelscope"
            manifest = prepare(source, args.target.resolve(), args.manifest.resolve(),
                               source_kind, endpoint, downloads)
            print(json.dumps({"status": "verified", "model_id": manifest["model_id"],
                              "revision": manifest["upstream_revision"], "target": str(args.target),
                              "manifest": str(args.manifest)}, ensure_ascii=False))
            return
        manifest = prepare(source, args.target.resolve(), args.manifest.resolve(), source_kind, endpoint)

    print(json.dumps({"status": "verified", "model_id": manifest["model_id"],
                      "revision": manifest["upstream_revision"], "target": str(args.target),
                      "manifest": str(args.manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
