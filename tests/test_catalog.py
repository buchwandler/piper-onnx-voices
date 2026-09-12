from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import piper_voice_catalog.catalog as catalog_module
from piper_voice_catalog.catalog import (
    CatalogError,
    build_catalog,
    fetch_and_build_catalog,
    get_voice,
    list_voices,
    resolve_revision,
    verify_catalog,
)

FIXTURE = Path(__file__).parent / "fixtures" / "upstream_voices.json"


def upstream() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def catalog() -> dict:
    return build_catalog(upstream(), requested_revision="main", resolved_revision="a" * 40)


def test_build_catalog_exposes_exact_three_artifacts_and_pinned_urls() -> None:
    data = catalog()
    verify_catalog(data)
    voice = data["voices"]["et_EE-news-medium"]
    assert list(voice["artifacts"]) == ["model_card", "model", "config"]
    assert voice["artifacts"]["model"]["url"].endswith(
        "/resolve/" + "a" * 40 + "/et/et_EE/news/medium/et_EE-news-medium.onnx?download=true"
    )
    assert voice["artifacts"]["model_card"]["filename"] == "MODEL_CARD"


def test_alias_and_filters() -> None:
    data = build_catalog(upstream())
    assert get_voice(data, "es-sharvard-medium")["id"] == "es_ES-sharvard-medium"
    assert [voice["id"] for voice in list_voices(data, language="et")] == ["et_EE-news-medium"]
    assert len(list_voices(data, quality="medium")) == 2


def test_missing_model_card_is_rejected() -> None:
    data = upstream()
    del data["et_EE-news-medium"]["files"]["et/et_EE/news/medium/MODEL_CARD"]
    with pytest.raises(CatalogError, match="model_card"):
        build_catalog(data)


def test_revision_is_resolved_before_catalog_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    revision = "b" * 40
    payload = json.dumps(upstream()).encode()

    def resolve(repository: str, requested: str) -> str:
        calls.append(f"resolve:{repository}:{requested}")
        return revision

    def read(url: str) -> bytes:
        calls.append(f"fetch:{url}")
        return payload

    monkeypatch.setattr(catalog_module, "resolve_revision", resolve)
    monkeypatch.setattr(catalog_module, "_read_url", read)
    result = fetch_and_build_catalog()

    assert calls == [
        "resolve:rhasspy/piper-voices:main",
        f"fetch:https://huggingface.co/rhasspy/piper-voices/resolve/{revision}/voices.json?download=true",
    ]
    assert result["source"]["revision"] == revision
    assert all(revision in artifact["url"] for voice in result["voices"].values() for artifact in voice["artifacts"].values())


def test_resolve_revision_requires_exact_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog_module, "_read_url", lambda url: b'{"sha":"main"}')
    with pytest.raises(CatalogError, match="exact 40-character"):
        resolve_revision("example/repo", "main")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data["source"].update(revision="main"), "revision"),
        (lambda data: data["voices"]["et_EE-news-medium"]["language"].pop("code"), "language code"),
        (lambda data: data["voices"]["et_EE-news-medium"].update(num_speakers=True), "num_speakers"),
        (lambda data: data["voices"]["es_ES-sharvard-medium"]["speaker_id_map"].update(M=1), "duplicate numeric"),
        (lambda data: data["voices"]["et_EE-news-medium"].update(aliases=["es_ES-sharvard-medium"]), "collides"),
        (lambda data: data["voices"]["et_EE-news-medium"]["artifacts"]["model"].update(filename="../x"), "path separators"),
        (lambda data: data["voices"]["et_EE-news-medium"]["artifacts"]["model"].update(path="../x"), "unsafe path"),
        (lambda data: data["voices"]["et_EE-news-medium"]["artifacts"]["config"].update(role="model"), "wrong role"),
        (lambda data: data["voices"]["et_EE-news-medium"]["artifacts"]["model"].update(url="https://example.invalid/x"), "pinned source path"),
    ],
)
def test_verify_rejects_malformed_catalogs(change, message: str) -> None:
    data = catalog()
    change(data)
    with pytest.raises(CatalogError, match=message):
        verify_catalog(data)


def test_verify_rejects_alias_ambiguity() -> None:
    data = catalog()
    data["voices"]["et_EE-news-medium"]["aliases"] = ["shared"]
    data["voices"]["es_ES-sharvard-medium"]["aliases"] = ["shared"]
    with pytest.raises(CatalogError, match="ambiguous"):
        verify_catalog(data)


def test_verify_rejects_duplicate_speaker_ids() -> None:
    data = catalog()
    data["voices"]["es_ES-sharvard-medium"]["speaker_id_map"] = {"M": 0, "F": 0}
    with pytest.raises(CatalogError, match="duplicate numeric"):
        verify_catalog(data)


def test_catalog_digest_is_deterministic() -> None:
    first = build_catalog(upstream(), resolved_revision="a" * 40)
    second = build_catalog(upstream(), resolved_revision="a" * 40)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(second, sort_keys=True, separators=(",", ":"))
    assert first["source"]["catalog_sha256"] == hashlib.sha256(
        (json.dumps(upstream(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def test_schema_file_is_valid_json() -> None:
    schema = json.loads(Path("schemas/voice-catalog.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["source"]["properties"]["revision"]["pattern"] == "^[0-9a-f]{40}$"


def test_missing_model_card_is_rejected_by_verifier() -> None:
    data = catalog()
    del data["voices"]["et_EE-news-medium"]["artifacts"]["model_card"]
    with pytest.raises(CatalogError, match="exactly model_card/model/config"):
        verify_catalog(data)
