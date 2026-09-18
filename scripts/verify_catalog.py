#!/usr/bin/env python3
"""Validate catalog/voices.json against the JSON schema and verify source.json consistency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"
SOURCE = ROOT / "catalog" / "source.json"
SCHEMA = ROOT / "schemas" / "voice-catalog.schema.json"


def main() -> int:
    # Load schema
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Unable to load schema: {SCHEMA}: {exc}", file=sys.stderr)
        return 1

    # Load catalog
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Unable to load catalog: {CATALOG}: {exc}", file=sys.stderr)
        return 1

    # Load source
    try:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Unable to load source: {SOURCE}: {exc}", file=sys.stderr)
        return 1

    # Validate catalog against schema
    try:
        jsonschema.validate(instance=catalog, schema=schema)
    except jsonschema.ValidationError as exc:
        print(f"ERROR: Catalog validation failed: {exc.message}", file=sys.stderr)
        return 1

    # Verify source.json matches catalog source metadata
    expected_source = {"schema": 1, **catalog["source"]}
    if source != expected_source:
        print(
            "ERROR: catalog/source.json does not match catalog/voices.json source metadata",
            file=sys.stderr,
        )
        return 1

    # Verify voice count
    actual_count = len(catalog["voices"])
    expected_count = catalog["source"]["voice_count"]
    if actual_count != expected_count:
        print(
            f"ERROR: Voice count mismatch: catalog has {actual_count} voices, "
            f"source declares {expected_count}",
            file=sys.stderr,
        )
        return 1

    print(
        f"Verified {actual_count} Piper voices; "
        f"revision={catalog['source']['revision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
