"""Small, dependency-free downloader for frozen domestic course artifacts."""

from __future__ import annotations

import hashlib
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


BLOCKED_HOST_SUFFIXES = (
    "huggingface.co",
    "hf.co",
    "xethub.hf.co",
    "xethub.com",
)


def public_url(url: str) -> str:
    """Remove query and fragment so signed download credentials are never recorded."""
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _host_allowed(host: str, allowed_hosts: set[str]) -> bool:
    host = host.lower().rstrip(".")
    if any(host == item or host.endswith("." + item) for item in BLOCKED_HOST_SUFFIXES):
        return False
    return any(host == item or host.endswith("." + item) for item in allowed_hosts)


class _RestrictedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]):
        self.allowed_hosts = {item.lower().rstrip(".") for item in allowed_hosts}
        self.redirect_hosts: list[str] = []
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = (urlsplit(newurl).hostname or "").lower()
        if not _host_allowed(host, self.allowed_hosts):
            raise RuntimeError(f"Download redirect left the approved domestic hosts: {host}")
        self.redirect_hosts.append(host)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_verified(url: str, destination: Path, expected_bytes: int,
                      expected_sha256: str, allowed_hosts: set[str], *,
                      total_timeout_seconds: float = 1800) -> dict:
    """Stream to a temporary file, verify it, then atomically publish it."""
    if type(expected_bytes) is not int or expected_bytes < 0:
        raise ValueError("expected_bytes must be a nonnegative integer")
    if not 0 < total_timeout_seconds < float("inf"):
        raise ValueError("total_timeout_seconds must be positive and finite")
    deadline = time.monotonic() + total_timeout_seconds
    initial_host = (urlsplit(url).hostname or "").lower()
    normalized = {item.lower().rstrip(".") for item in allowed_hosts}
    if not _host_allowed(initial_host, normalized):
        raise RuntimeError(f"Download host is not approved: {initial_host}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    handler = _RestrictedRedirectHandler(normalized)
    opener = urllib.request.build_opener(handler)
    digest = hashlib.sha256()
    size = 0
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "BDP-course-artifact/1", "Accept-Encoding": "identity"}
        )
        with opener.open(request, timeout=min(120, total_timeout_seconds)) as response, temporary.open("wb") as output:
            final_host = (urlsplit(response.geturl()).hostname or "").lower()
            if not _host_allowed(final_host, normalized):
                raise RuntimeError(f"Download final host is not approved: {final_host}")
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Artifact download exceeded its total deadline")
                # One extra byte detects an oversized response without consuming it all.
                block = response.read(min(1024 * 1024, expected_bytes - size + 1))
                if time.monotonic() >= deadline:
                    raise TimeoutError("Artifact download exceeded its total deadline")
                if not block:
                    break
                if size + len(block) > expected_bytes:
                    raise RuntimeError(f"Artifact byte size exceeds expected {expected_bytes}")
                output.write(block)
                digest.update(block)
                size += len(block)
        actual_sha256 = digest.hexdigest()
        if size != expected_bytes:
            raise RuntimeError(f"Artifact byte size mismatch: expected {expected_bytes}, got {size}")
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"Artifact SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "request_url": public_url(url),
        "redirect_hosts": handler.redirect_hosts,
        "final_host": final_host,
        "bytes": size,
        "sha256": actual_sha256,
    }
