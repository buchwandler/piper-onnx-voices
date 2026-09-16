#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from piper_voice_catalog.catalog import fetch_and_build_catalog, verify_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"
SOURCE = ROOT / "catalog" / "source.json"


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
    catalog = fetch_and_build_catalog()
    verify_catalog(catalog)
    _write_json(CATALOG, catalog)
    source = {"schema": 1, **catalog["source"]}
    _write_json(SOURCE, source)
    print(
        f"Wrote {len(catalog['voices'])} voices at {catalog['source']['revision']} to {CATALOG}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
