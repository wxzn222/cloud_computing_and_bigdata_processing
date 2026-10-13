"""Content identities with the same relative-path ordering on every platform."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from .common import sha256


def directory_files(directory: Path) -> dict[str, Path]:
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Artifact directory not found: {directory}")
    files = {path.relative_to(directory).as_posix(): path
             for path in directory.rglob("*") if path.is_file()}
    # Sort strings, never Path objects (WindowsPath compares case-insensitively).
    return dict(sorted(files.items()))


def revision_from_hashes(files: Iterable[tuple[str, str]]) -> str:
    entries = list(files)
    if len({name for name, _ in entries}) != len(entries):
        raise ValueError("Duplicate artifact path")
    return hashlib.sha256(
        "".join(name + digest for name, digest in sorted(entries)).encode("utf-8")
    ).hexdigest()


def directory_revision(directory: Path) -> str:
    return revision_from_hashes((name, sha256(path))
                                for name, path in directory_files(directory).items())
