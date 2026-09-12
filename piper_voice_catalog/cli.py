"""Command line interface for the Piper voice catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .catalog import (
    DEFAULT_REPOSITORY,
    DEFAULT_REVISION,
    CatalogError,
    fetch_and_build_catalog,
    get_voice,
    list_voices,
    load_catalog,
    verify_catalog,
)
from .download import DownloadError, download_voice


def _catalog(args: argparse.Namespace) -> dict[str, Any]:
    if args.catalog:
        return load_catalog(args.catalog)
    return fetch_and_build_catalog(repository=args.repository, revision=args.revision)


def _write_json(data: Any) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="piper-voices",
        description="List and download voices from rhasspy/piper-voices",
    )
    parser.add_argument(
        "--catalog", type=Path, help="Use a materialized catalog/voices.json"
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Write a pinned local catalog")
    refresh.add_argument("--output", type=Path, default=Path("catalog/voices.json"))

    verify = sub.add_parser("verify", help="Verify a materialized catalog")
    verify.add_argument(
        "path", type=Path, nargs="?", default=Path("catalog/voices.json")
    )

    listing = sub.add_parser("list", help="List voices")
    listing.add_argument("--language")
    listing.add_argument("--quality")
    listing.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show one voice and its three artifact URLs")
    show.add_argument("voice")
    show.add_argument("--json", action="store_true")

    urls = sub.add_parser("urls", help="Print the three direct download URLs")
    urls.add_argument("voice")

    download = sub.add_parser(
        "download", help="Download exactly MODEL_CARD + ONNX + JSON"
    )
    download.add_argument("voice")
    download.add_argument("--output", type=Path, default=Path("downloads"))
    download.add_argument(
        "--flat", action="store_true", help="Write directly into --output"
    )
    download.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "refresh":
            catalog = fetch_and_build_catalog(
                repository=args.repository, revision=args.revision
            )
            verify_catalog(catalog)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            print(
                f"Wrote {len(catalog['voices'])} voices to {args.output} "
                f"at revision {catalog['source']['revision']}"
            )
            return 0
        if args.command == "verify":
            catalog = load_catalog(args.path)
            print(f"Verified {len(catalog['voices'])} Piper voices")
            return 0

        catalog = _catalog(args)
        if args.command == "list":
            voices = list_voices(catalog, language=args.language, quality=args.quality)
            if args.json:
                _write_json(voices)
            else:
                for voice in voices:
                    language = voice.get("language", {}).get("code", "?")
                    print(
                        f"{voice['id']}\t{language}\t{voice['quality']}\t"
                        f"speakers={voice['num_speakers']}"
                    )
                print(f"# {len(voices)} voice(s)")
            return 0
        voice = get_voice(catalog, args.voice)
        if args.command == "show":
            if args.json:
                _write_json(voice)
            else:
                print(f"id: {voice['id']}")
                print(f"language: {voice['language'].get('code')}")
                print(f"quality: {voice['quality']}")
                print(f"speakers: {voice['num_speakers']}")
                for role in ("model_card", "model", "config"):
                    print(f"{role}: {voice['artifacts'][role]['url']}")
            return 0
        if args.command == "urls":
            for role in ("model_card", "model", "config"):
                print(voice["artifacts"][role]["url"])
            return 0
        if args.command == "download":
            target = args.output if args.flat else args.output / voice["id"]
            paths = download_voice(voice, target, overwrite=args.overwrite)
            for path in paths:
                print(path)
            return 0
    except (CatalogError, DownloadError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("unhandled command")
    return 2
