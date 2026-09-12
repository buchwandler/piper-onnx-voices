# piper-onnx-voices

A small, dependency-free catalog and downloader for the runtime-ready voices in
[`rhasspy/piper-voices`](https://huggingface.co/rhasspy/piper-voices). The project
tracks metadata and download URLs. It does not mirror the upstream voice files.

Each selected voice exposes exactly three required artifacts:

1. `MODEL_CARD`, for license and attribution information.
2. The Piper `.onnx` model.
3. The matching `.onnx.json` configuration.

## Quick start

```bash
python -m pip install -e .

# Live catalog from upstream main.
piper-voices list
piper-voices list --language et --quality medium
piper-voices show et_EE-news-medium
piper-voices urls et_EE-news-medium
piper-voices download et_EE-news-medium
```

The downloader verifies upstream byte size and MD5 metadata before atomically
installing each file. MD5 is retained because it is supplied by upstream and is
useful for corruption detection. It is not presented as a modern
cryptographic supply-chain identity.

## Materialized catalog and offline use

The repository contains the canonical generated snapshot in
`catalog/voices.json` and matching provenance in `catalog/source.json`.
Generation resolves the requested upstream revision to an exact 40-character
commit SHA before fetching `voices.json`. Every generated artifact URL uses that
same SHA, so a committed snapshot does not change when upstream `main` moves.

```bash
python scripts/refresh_catalog.py
python scripts/verify_catalog.py

# Use the snapshot without contacting Hugging Face.
piper-voices --catalog catalog/voices.json list
piper-voices --catalog catalog/voices.json download et_EE-news-medium
```

The Python wheel is intentionally network-first. It does not bundle the
repository catalog or schema as package data. Applications that need offline
behavior should copy or vendor the committed snapshot and pass `--catalog`.
The JSON Schema for independent consumers is
`schemas/voice-catalog.schema.json`.

## Browser selector

A small no-framework selector is available at `web/index.html`:

```bash
python scripts/serve_catalog.py --offline
# Open http://127.0.0.1:8000/web/
```

Without `--offline`, the server refreshes the committed catalog before serving
it. The page loads the materialized catalog and displays the three pinned
artifact links. If the page is served without a local snapshot, it has a live
upstream fallback for development only.

## Catalog contract

The verifier enforces:

- exact source provider, repository, requested revision, commit SHA, URL, digest,
  and voice count;
- complete language, quality, speaker, and alias metadata;
- one `MODEL_CARD`, one `.onnx`, and one `.onnx.json` per voice;
- safe relative paths and local filenames with no traversal or absolute paths;
- role, extension, filename, path, URL, size, and MD5 consistency;
- globally unambiguous aliases and unique artifact URLs.

Refresh output is deterministic UTF-8 JSON with sorted keys, stable indentation,
and one terminal newline. GitHub Actions verifies the committed snapshot on
pushes and pull requests. Scheduled refreshes rebase, regenerate, verify, and
push only validated metadata.

## Python integration

```python
from pathlib import Path

from piper_voice_catalog import download_voice, get_voice, load_catalog

catalog = load_catalog(Path("catalog/voices.json"))
voice = get_voice(catalog, "et_EE-news-medium")
download_voice(voice, Path("voices") / voice["id"])
```

## Naming and licensing

The public names are:

- repository: `piper-onnx-voices`;
- Python distribution: `piper-onnx-voices`;
- import package: `piper_voice_catalog`;
- CLI: `piper-voices`.

The MIT license applies to repository-authored code and documentation. Voice
models, configuration files, datasets, names, `MODEL_CARD` content, and other
upstream artifacts remain subject to their upstream terms and are not relicensed
by this project. `MODEL_CARD` is mandatory for every catalog voice so consumers
can review those terms and attribution requirements.
