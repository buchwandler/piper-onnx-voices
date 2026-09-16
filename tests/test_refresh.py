from __future__ import annotations

import json
from pathlib import Path

from scripts.refresh_catalog import _write_json

ROOT = Path(__file__).resolve().parents[1]


def test_committed_source_metadata_matches_catalog() -> None:
    catalog = json.loads((ROOT / "catalog/voices.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "catalog/source.json").read_text(encoding="utf-8"))
    assert source == {"schema": 1, **catalog["source"]}


def test_refresh_json_writer_is_byte_deterministic(tmp_path: Path) -> None:
    data = {"z": "é", "nested": {"b": 2, "a": 1}}
    output = tmp_path / "catalog.json"
    _write_json(output, data)
    first = output.read_bytes()
    _write_json(output, data)
    second = output.read_bytes()
    assert first == second
    assert first.endswith(b"\n")
    assert b"\r" not in first
