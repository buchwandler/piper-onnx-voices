#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from piper_voice_catalog.catalog import CatalogError, load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"
SOURCE = ROOT / "catalog" / "source.json"


def main() -> int:
    catalog = load_catalog(CATALOG)
    try:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Unable to load source metadata: {SOURCE}") from exc
    expected_source = {"schema": 1, **catalog["source"]}
    if source != expected_source:
        raise CatalogError("catalog/source.json does not match catalog/voices.json source metadata")
    print(
        f"Verified {len(catalog['voices'])} Piper voices; "
        f"revision={catalog['source']['revision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
