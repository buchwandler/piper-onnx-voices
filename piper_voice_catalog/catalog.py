"""Fetch and normalize the upstream Piper voice inventory."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_REPOSITORY = "rhasspy/piper-voices"
DEFAULT_REVISION = "main"
USER_AGENT = "piper-onnx-voices-catalog/0.1"
_SHA_FROM_RESOLVE_RE = re.compile(r"/([0-9a-f]{40})/voices\.json(?:[?]|$)")


class CatalogError(ValueError):
    """Raised when upstream or normalized catalog data is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def huggingface_resolve_url(repository: str, revision: str, path: str) -> str:
    repo = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
    rev = urllib.parse.quote(revision, safe="")
    asset = urllib.parse.quote(path, safe="/")
    return f"https://huggingface.co/{repo}/resolve/{rev}/{asset}?download=true"


def fetch_upstream_catalog(
    *, repository: str = DEFAULT_REPOSITORY, revision: str = DEFAULT_REVISION
) -> tuple[dict[str, Any], str, str]:
    """Return upstream voices.json, resolved revision, and source URL.

    Hugging Face redirects resolve URLs through a cache URL containing the exact
    commit SHA. When available, that SHA is used for all generated artifact URLs.
    """

    url = huggingface_resolve_url(repository, revision, "voices.json")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        final_url = response.geturl()
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("Upstream voices.json is not valid UTF-8 JSON") from exc
    _require(isinstance(data, dict) and bool(data), "Upstream voices.json is empty")
    match = _SHA_FROM_RESOLVE_RE.search(final_url)
    resolved_revision = match.group(1) if match else revision
    return data, resolved_revision, url


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
    _require(isinstance(size, int) and size > 0, f"{path}: invalid size_bytes")
    _require(
        isinstance(md5, str) and re.fullmatch(r"[0-9a-fA-F]{32}", md5) is not None,
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
) -> dict[str, Any]:
    """Normalize all entries from upstream voices.json into the MVP contract."""

    _require(isinstance(upstream, dict) and bool(upstream), "Upstream catalog is empty")
    revision = resolved_revision or requested_revision
    voices: dict[str, Any] = {}
    for voice_id in sorted(upstream):
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
            isinstance(num_speakers, int) and not isinstance(num_speakers, bool) and num_speakers >= 1,
            f"{voice_id}: invalid num_speakers",
        )
        speaker_id_map = item.get("speaker_id_map") or {}
        aliases = item.get("aliases") or []
        _require(isinstance(speaker_id_map, dict), f"{voice_id}: speaker_id_map must be an object")
        _require(
            isinstance(aliases, list) and all(isinstance(x, str) for x in aliases),
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
            or huggingface_resolve_url(repository, requested_revision, "voices.json"),
        },
        "voices": voices,
    }


def fetch_and_build_catalog(
    *, repository: str = DEFAULT_REPOSITORY, revision: str = DEFAULT_REVISION
) -> dict[str, Any]:
    upstream, resolved_revision, source_url = fetch_upstream_catalog(
        repository=repository, revision=revision
    )
    return build_catalog(
        upstream,
        repository=repository,
        requested_revision=revision,
        resolved_revision=resolved_revision,
        catalog_url=source_url,
    )


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Unable to load catalog: {path}") from exc
    verify_catalog(data)
    return data


def verify_catalog(catalog: dict[str, Any]) -> None:
    _require(catalog.get("schema") == 1, "Catalog schema must be 1")
    _require(catalog.get("kind") == "piper-voice-catalog", "Unexpected catalog kind")
    source = catalog.get("source")
    _require(isinstance(source, dict), "Catalog source must be an object")
    voices = catalog.get("voices")
    _require(isinstance(voices, dict) and bool(voices), "Catalog has no voices")
    seen_urls: set[str] = set()
    for voice_id, voice in voices.items():
        _require(voice.get("id") == voice_id, f"{voice_id}: mismatched id")
        artifacts = voice.get("artifacts")
        _require(isinstance(artifacts, dict), f"{voice_id}: artifacts must be an object")
        _require(
            set(artifacts) == {"model_card", "model", "config"},
            f"{voice_id}: voice must expose exactly model_card/model/config",
        )
        for role, artifact in artifacts.items():
            _require(artifact.get("role") == role, f"{voice_id}: wrong role for {role}")
            _require(isinstance(artifact.get("size"), int) and artifact["size"] > 0, f"{voice_id}/{role}: invalid size")
            _require(re.fullmatch(r"[0-9a-f]{32}", artifact.get("md5", "")) is not None, f"{voice_id}/{role}: invalid md5")
            url = artifact.get("url")
            _require(isinstance(url, str) and url.startswith("https://"), f"{voice_id}/{role}: invalid URL")
            _require(url not in seen_urls, f"Duplicate artifact URL: {url}")
            seen_urls.add(url)


def get_voice(catalog: dict[str, Any], voice_id_or_alias: str) -> dict[str, Any]:
    voices = catalog["voices"]
    if voice_id_or_alias in voices:
        return voices[voice_id_or_alias]
    matches = [
        voice for voice in voices.values() if voice_id_or_alias in voice.get("aliases", [])
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CatalogError(f"Alias is ambiguous: {voice_id_or_alias}")
    raise CatalogError(f"Unknown Piper voice: {voice_id_or_alias}")


def list_voices(
    catalog: dict[str, Any], *, language: str | None = None, quality: str | None = None
) -> list[dict[str, Any]]:
    values = list(catalog["voices"].values())
    if language:
        wanted = language.casefold()
        values = [
            voice
            for voice in values
            if str(voice.get("language", {}).get("code", "")).casefold() == wanted
            or str(voice.get("language", {}).get("family", "")).casefold() == wanted
        ]
    if quality:
        wanted_quality = quality.casefold()
        values = [voice for voice in values if voice.get("quality", "").casefold() == wanted_quality]
    return sorted(values, key=lambda voice: voice["id"])
