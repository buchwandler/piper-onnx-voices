#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from piper_voice_catalog.catalog import fetch_and_build_catalog, verify_catalog

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "catalog" / "voices.json"


def main() -> int:
    catalog = fetch_and_build_catalog()
    verify_catalog(catalog)
    OUTPUT.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(catalog['voices'])} voices at {catalog['source']['revision']} to {OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
