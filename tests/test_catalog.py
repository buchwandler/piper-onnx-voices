from __future__ import annotations

import json
from pathlib import Path

import pytest

from piper_voice_catalog.catalog import (
    CatalogError,
    build_catalog,
    get_voice,
    list_voices,
    verify_catalog,
)

FIXTURE = Path(__file__).parent / "fixtures" / "upstream_voices.json"


def upstream():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_build_catalog_exposes_exact_three_artifacts_and_pinned_urls() -> None:
    catalog = build_catalog(
        upstream(),
        requested_revision="main",
        resolved_revision="a" * 40,
    )
    verify_catalog(catalog)
    voice = catalog["voices"]["et_EE-news-medium"]
    assert list(voice["artifacts"]) == ["model_card", "model", "config"]
    assert voice["artifacts"]["model"]["url"].endswith(
        "/resolve/"
        + "a" * 40
        + "/et/et_EE/news/medium/et_EE-news-medium.onnx?download=true"
    )
    assert voice["artifacts"]["model_card"]["filename"] == "MODEL_CARD"


def test_alias_and_filters() -> None:
    catalog = build_catalog(upstream())
    assert get_voice(catalog, "es-sharvard-medium")["id"] == "es_ES-sharvard-medium"
    assert [v["id"] for v in list_voices(catalog, language="et")] == [
        "et_EE-news-medium"
    ]
    assert len(list_voices(catalog, quality="medium")) == 2


def test_missing_model_card_is_rejected() -> None:
    data = upstream()
    del data["et_EE-news-medium"]["files"]["et/et_EE/news/medium/MODEL_CARD"]
    with pytest.raises(CatalogError, match="model_card"):
        build_catalog(data)
