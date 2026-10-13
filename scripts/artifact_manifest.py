"""Create or verify SHA256 manifests for offline course artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(directory: Path) -> list[dict]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Artifact directory not found: {directory}")
    return [
        {"path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size,
         "sha256": file_sha256(path)}
        for path in sorted(directory.rglob("*")) if path.is_file()
    ]


def create_manifest(directory: Path, manifest_path: Path) -> dict:
    files = inventory(directory)
    if not files:
        raise RuntimeError("Artifact directory is empty")
    manifest = {"schema": 1, "directory": directory.name, "files": files,
                "total_bytes": sum(item["bytes"] for item in files)}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verify_manifest(directory: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = {item["path"]: item for item in manifest.get("files", [])}
    actual = {item["path"]: item for item in inventory(directory)}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise RuntimeError(f"Artifact inventory mismatch; missing={missing}, extra={extra}")
    for name, item in expected.items():
        if actual[name]["bytes"] != item["bytes"] or actual[name]["sha256"] != item["sha256"]:
            raise RuntimeError(f"Artifact SHA256 mismatch: {name}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify an offline artifact manifest")
    parser.add_argument("action", choices=["create", "verify"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    operation = create_manifest if args.action == "create" else verify_manifest
    manifest = operation(args.directory.resolve(), args.manifest.resolve())
    print(json.dumps({"status": args.action + "d", "files": len(manifest["files"]),
                      "total_bytes": manifest["total_bytes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
