#!/usr/bin/env python3
"""Fetch upstream Piper voices and rebuild catalog/voices.json and catalog/source.json."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_REPOSITORY = "rhasspy/piper-voices"
DEFAULT_REVISION = "main"
USER_AGENT = "piper-onnx-voices/refresh"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{32}$")
_SAFE_NAME_RE = re.compile(r"^[^\W_][\w.-]*$", re.UNICODE)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"
SOURCE = ROOT / "catalog" / "source.json"


class CatalogError(ValueError):
    """Raised when upstream or normalized catalog data is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def _safe_name(value: Any, label: str) -> None:
    _require(isinstance(value, str) and value, f"{label}: must be a non-empty string")
    _require(
        "/" not in value and "\\" not in value,
        f"{label}: path separators are forbidden",
    )
    _require(value not in {".", ".."}, f"{label}: dot segments are forbidden")
    _require(not Path(value).is_absolute(), f"{label}: absolute paths are forbidden")
    _require(_SAFE_NAME_RE.fullmatch(value) is not None, f"{label}: unsafe name")


def _canonical_json(data: Any) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def huggingface_resolve_url(repository: str, revision: str, path: str) -> str:
    repo = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
    rev = urllib.parse.quote(revision, safe="")
    asset = urllib.parse.quote(path, safe="/")
    return f"https://huggingface.co/{repo}/resolve/{rev}/{asset}?download=true"


def huggingface_api_url(repository: str, revision: str) -> str:
    repo = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
    rev = urllib.parse.quote(revision, safe="")
    return f"https://huggingface.co/api/models/{repo}/revision/{rev}"


def _read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise CatalogError(f"Unable to fetch {url}") from exc


def resolve_revision(repository: str, revision: str = DEFAULT_REVISION) -> str:
    """Resolve a Hub branch or tag to an exact lowercase commit SHA."""
    payload = _read_url(huggingface_api_url(repository, revision))
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError(
            "Hugging Face repository metadata is not valid UTF-8 JSON"
        ) from exc
    resolved = data.get("sha") if isinstance(data, dict) else None
    _require(
        isinstance(resolved, str) and _SHA_RE.fullmatch(resolved.lower()) is not None,
        "Unable to resolve an exact 40-character commit SHA",
    )
    return resolved.lower()


def _fetch_upstream_catalog_metadata(
    *, repository: str = DEFAULT_REPOSITORY, revision: str = DEFAULT_REVISION
) -> tuple[dict[str, Any], str, str, str]:
    resolved_revision = resolve_revision(repository, revision)
    url = huggingface_resolve_url(repository, resolved_revision, "voices.json")
    payload = _read_url(url)
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("Upstream voices.json is not valid UTF-8 JSON") from exc
    _require(isinstance(data, dict) and bool(data), "Upstream voices.json is empty")
    return data, resolved_revision, url, hashlib.sha256(payload).hexdigest()


def _pick_artifact_paths(files: dict[str, Any], voice_id: str) -> dict[str, str]:
    roles: dict[str, list[str]] = {"model_card": [], "model": [], "config": []}
    for path in files:
        if path.endswith("/MODEL_CARD") or path == "MODEL_CARD":
            roles["model_card"].append(path)
        elif path.endswith(".onnx.json"):
            roles["config"].append(path)
        elif path.endswith(".onnx"):
            roles["model"].append(path)
    for role, matches in roles.items():
        _require(
            len(matches) == 1,
            f"{voice_id}: expected exactly one {role} artifact, found {len(matches)}",
        )
    return {role: paths[0] for role, paths in roles.items()}


def _artifact(
    *, role: str, path: str, metadata: dict[str, Any], repository: str, revision: str
) -> dict[str, Any]:
    size = metadata.get("size_bytes")
    md5 = metadata.get("md5_digest")
    _require(
        isinstance(size, int) and not isinstance(size, bool) and size > 0,
        f"{path}: invalid size_bytes",
    )
    _require(
        isinstance(md5, str) and _DIGEST_RE.fullmatch(md5.lower()) is not None,
        f"{path}: invalid md5_digest",
    )
    return {
        "role": role,
        "path": path,
        "filename": Path(path).name,
        "url": huggingface_resolve_url(repository, revision, path),
        "size": size,
        "md5": md5.lower(),
    }


def build_catalog(
    upstream: dict[str, Any],
    *,
    repository: str = DEFAULT_REPOSITORY,
    requested_revision: str = DEFAULT_REVISION,
    resolved_revision: str | None = None,
    catalog_url: str | None = None,
    catalog_sha256: str | None = None,
) -> dict[str, Any]:
    """Normalize all entries from upstream voices.json into the catalog contract."""
    _require(isinstance(upstream, dict) and bool(upstream), "Upstream catalog is empty")
    revision = (resolved_revision or requested_revision).lower()
    _require(isinstance(revision, str), "Catalog revision must be a string")
    voices: dict[str, Any] = {}
    for voice_id in sorted(upstream):
        _safe_name(voice_id, "voice id")
        item = upstream[voice_id]
        _require(isinstance(item, dict), f"{voice_id}: entry must be an object")
        _require(item.get("key") == voice_id, f"{voice_id}: key does not match map key")
        files = item.get("files")
        _require(isinstance(files, dict), f"{voice_id}: files must be an object")
        paths = _pick_artifact_paths(files, voice_id)
        language = item.get("language")
        _require(isinstance(language, dict), f"{voice_id}: language must be an object")
        name = item.get("name")
        quality = item.get("quality")
        num_speakers = item.get("num_speakers")
        _require(isinstance(name, str) and name, f"{voice_id}: invalid name")
        _require(isinstance(quality, str) and quality, f"{voice_id}: invalid quality")
        _require(
            isinstance(num_speakers, int)
            and not isinstance(num_speakers, bool)
            and num_speakers >= 1,
            f"{voice_id}: invalid num_speakers",
        )
        speaker_id_map = item.get("speaker_id_map") or {}
        aliases = item.get("aliases") or []
        _require(
            isinstance(speaker_id_map, dict),
            f"{voice_id}: speaker_id_map must be an object",
        )
        _require(
            isinstance(aliases, list)
            and all(isinstance(alias, str) for alias in aliases),
            f"{voice_id}: aliases must be strings",
        )
        voices[voice_id] = {
            "id": voice_id,
            "name": name,
            "language": language,
            "quality": quality,
            "num_speakers": num_speakers,
            "speaker_id_map": speaker_id_map,
            "aliases": aliases,
            "artifacts": {
                role: _artifact(
                    role=role,
                    path=paths[role],
                    metadata=files[paths[role]],
                    repository=repository,
                    revision=revision,
                )
                for role in ("model_card", "model", "config")
            },
        }
    return {
        "schema": 1,
        "kind": "piper-voice-catalog",
        "source": {
            "provider": "huggingface",
            "repository": repository,
            "requested_revision": requested_revision,
            "revision": revision,
            "catalog_url": catalog_url
            or huggingface_resolve_url(repository, revision, "voices.json"),
            "catalog_sha256": catalog_sha256
            or hashlib.sha256(_canonical_json(upstream)).hexdigest(),
            "upstream_catalog_path": "voices.json",
            "voice_count": len(voices),
        },
        "voices": voices,
    }


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    repository = DEFAULT_REPOSITORY
    revision = DEFAULT_REVISION

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: refresh_catalog.py [--repository REPO] [--revision REV]")
        print()
        print("Fetch upstream Piper voices and rebuild catalog/voices.json")
        print("and catalog/source.json.")
        print()
        print("Options:")
        print("  --repository REPO  Hugging Face repository (default: rhasspy/piper-voices)")
        print("  --revision REV     Git revision to resolve (default: main)")
        return 0

    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg == "--repository" and args:
            repository = args.pop(0)
        elif arg == "--revision" and args:
            revision = args.pop(0)
        else:
            print(f"Unknown argument: {arg}", file=sys.stderr)
            return 1

    upstream, resolved_revision, source_url, catalog_sha256 = (
        _fetch_upstream_catalog_metadata(repository=repository, revision=revision)
    )
    catalog = build_catalog(
        upstream,
        repository=repository,
        requested_revision=revision,
        resolved_revision=resolved_revision,
        catalog_url=source_url,
        catalog_sha256=catalog_sha256,
    )
    _write_json(CATALOG, catalog)
    source = {"schema": 1, **catalog["source"]}
    _write_json(SOURCE, source)
    print(
        f"Wrote {len(catalog['voices'])} voices at {catalog['source']['revision']} to {CATALOG}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
