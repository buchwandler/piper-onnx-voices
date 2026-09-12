#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from piper_voice_catalog.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"


def main() -> int:
    catalog = load_catalog(CATALOG)
    print(
        f"Verified {len(catalog['voices'])} voices; "
        f"revision={catalog['source']['revision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
