# piper-onnx-voices-mvp

A small Piper counterpart to a model registry such as `kokoro-onnx-models`.
It does **not** mirror the roughly 12 GB `rhasspy/piper-voices` repository.
Instead, it treats upstream `voices.json` as discovery metadata, normalizes every
voice into one catalog record, and lets a consumer download exactly the three
files needed for a selected Piper voice:

1. `MODEL_CARD` — license / attribution information;
2. `<voice>.onnx` — the Piper ONNX model;
3. `<voice>.onnx.json` — the matching Piper config.

The upstream Piper documentation also describes the ONNX + JSON pair as the two
runtime files and calls out `MODEL_CARD` for voice-specific licensing. This MVP
therefore makes the model card a required third artifact rather than optional
metadata.

## Why this shape

`rhasspy/piper-voices` already publishes a machine-readable `voices.json` with
language, quality, speaker metadata, aliases, paths, byte sizes, and MD5 digests.
Re-scraping the repository tree would duplicate that logic. The refresh step
uses the upstream file, requires exactly one `MODEL_CARD`, one `.onnx`, and one
`.onnx.json` per voice, and generates a smaller client contract with explicit
artifact roles and direct download URLs.

When Hugging Face redirects `main` to a cache URL containing a 40-character
commit SHA, the generated catalog pins all artifact URLs to that exact SHA. This
makes a committed `catalog/voices.json` reproducible while still allowing a
future refresh from `main`.

## Quick start

No third-party runtime dependencies are required.

```bash
python -m pip install -e .

# Live list: fetches all voices from upstream main.
piper-voices list

# Filter by language family/locale and quality.
piper-voices list --language et --quality medium

# Inspect the three URLs for one voice.
piper-voices show et_EE-news-medium
piper-voices urls et_EE-news-medium

# Download exactly the three files into downloads/et_EE-news-medium/.
piper-voices download et_EE-news-medium
```

The downloaded directory is intentionally simple:

```text
downloads/et_EE-news-medium/
├── MODEL_CARD
├── et_EE-news-medium.onnx
└── et_EE-news-medium.onnx.json
```

Downloads are written atomically and verified against the upstream byte size and
MD5 before the final filename is installed.

## Materialize a catalog for your Piper application

For an application, CI build, mobile bundle, or API server, commit a normalized
snapshot instead of contacting Hugging Face just to list voices:

```bash
python scripts/refresh_catalog.py
python scripts/verify_catalog.py
```

This writes `catalog/voices.json`. Your app can then read `voices` and let the
user select by `id`, language, quality, or alias. Each record contains:

```json
{
  "id": "et_EE-news-medium",
  "name": "news",
  "language": {"code": "et_EE", "family": "et"},
  "quality": "medium",
  "num_speakers": 1,
  "speaker_id_map": {},
  "aliases": [],
  "artifacts": {
    "model_card": {"filename": "MODEL_CARD", "url": "...", "size": 449, "md5": "..."},
    "model": {"filename": "et_EE-news-medium.onnx", "url": "...", "size": 76800000, "md5": "..."},
    "config": {"filename": "et_EE-news-medium.onnx.json", "url": "...", "size": 5000, "md5": "..."}
  }
}
```

The numbers above are illustrative; the generated catalog always preserves the
actual upstream metadata.

A daily GitHub Actions workflow is included. It refreshes `catalog/voices.json`,
verifies the contract, and commits only when upstream changed.

## Minimal Python integration

```python
from pathlib import Path

from piper_voice_catalog import fetch_and_build_catalog, get_voice, download_voice

catalog = fetch_and_build_catalog()
voice = get_voice(catalog, "et_EE-news-medium")
download_voice(voice, Path("voices") / voice["id"])
```

If your application ships a materialized snapshot:

```python
from pathlib import Path
from piper_voice_catalog import load_catalog, get_voice

catalog = load_catalog(Path("catalog/voices.json"))
voice = get_voice(catalog, selected_voice_id)
```

## Browser MVP

The repo also includes a tiny no-framework selector. The recommended path is:

```bash
python scripts/serve_catalog.py
```

That refreshes `catalog/voices.json`, starts a local server, and prints the URL.
The page filters all voices and exposes three download links for the selected
voice. `--offline` serves an existing catalog without refreshing.

## Multi-speaker voices

Some Piper models contain multiple speakers. The catalog keeps `num_speakers`
and `speaker_id_map` from upstream. Selecting a model still downloads the same
three files; your Piper runtime chooses a speaker ID at synthesis time.

## Catalog contract

`scripts/verify_catalog.py` enforces these MVP invariants:

- every voice exposes exactly `model_card`, `model`, and `config`;
- each artifact has a positive size and 32-character MD5;
- artifact URLs use HTTPS;
- aliases remain resolvable;
- a committed refreshed catalog uses the revision resolved during refresh.

The JSON Schema is in `schemas/voice-catalog.schema.json` for consumers that want
independent validation.

## Licensing

The code in this MVP is MIT licensed. The voice artifacts are not relicensed.
Always retain and surface the selected voice's `MODEL_CARD`; individual voice
models and datasets may have terms or attribution requirements beyond the code
in this repository.
