#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import json
from pathlib import Path

from piper_voice_catalog.catalog import (
    fetch_and_build_catalog,
    load_catalog,
    verify_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "voices.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the catalog and serve the MVP browser UI"
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use existing catalog/voices.json"
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.offline:
        catalog = load_catalog(CATALOG)
    else:
        catalog = fetch_and_build_catalog()
        verify_catalog(catalog)
        CATALOG.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"Catalog contains {len(catalog['voices'])} voices")
    print(f"Open http://127.0.0.1:{args.port}/web/")
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(ROOT)
    )
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
