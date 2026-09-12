"""Download exactly the three runtime artifacts for one Piper voice."""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from .catalog import USER_AGENT


class DownloadError(RuntimeError):
    """Raised when an artifact download does not match the catalog."""


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download_artifact(artifact: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(artifact["url"], headers={"User-Agent": USER_AGENT})
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size != artifact["size"]:
            raise DownloadError(
                f"{artifact['role']}: expected {artifact['size']} bytes, got {temporary.stat().st_size}"
            )
        digest = _md5(temporary)
        if digest != artifact["md5"]:
            raise DownloadError(
                f"{artifact['role']}: MD5 mismatch (expected {artifact['md5']}, got {digest})"
            )
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def download_voice(
    voice: dict[str, Any], target: Path, *, overwrite: bool = False
) -> list[Path]:
    """Download MODEL_CARD, .onnx, and .onnx.json into *target*.

    The destination directory contains exactly the upstream filenames. Existing
    matching files are reused; mismatches fail unless ``overwrite`` is true.
    """

    target.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for role in ("model_card", "model", "config"):
        artifact = voice["artifacts"][role]
        destination = target / artifact["filename"]
        if destination.exists() and not overwrite:
            if destination.stat().st_size == artifact["size"] and _md5(destination) == artifact["md5"]:
                downloaded.append(destination)
                continue
            raise DownloadError(
                f"Existing file does not match catalog: {destination}; use --overwrite"
            )
        _download_artifact(artifact, destination)
        downloaded.append(destination)
    return downloaded
