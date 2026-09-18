# piper-onnx-voices

A normalized, reproducible Piper voice catalog for consumers such as [OnnxVoice](https://github.com/nahrstaedt/wandler).

## What this repository is

- Canonical generated Piper voice catalog data.
- Source/provenance metadata.
- The public JSON catalog contract/schema.
- Documentation about the catalog and model licensing.
- CI that validates the committed data.
- Scheduled refresh automation.

## What it is not

- Not a Python package.
- Not a model mirror.
- Not a downloader.
- Not a synthesis runtime.

## Canonical files

```text
catalog/voices.json
catalog/source.json
schemas/voice-catalog.schema.json
```

## Source

```text
provider: Hugging Face
repository: rhasspy/piper-voices
requested revision: main
resolved revision: exact SHA in catalog/source metadata
```

## Consumer example

```python
from onnxvoice import OnnxVoice

ov = OnnxVoice()
ov.install("piper:en_US-lessac-medium")
```

## Catalog contract

The catalog is validated against `schemas/voice-catalog.schema.json`. The verifier ensures:

- Exact catalog kind/schema.
- Valid source provider/repository/revision.
- Source voice count equals catalog voice count.
- Catalog/source digest relationship is valid.
- Every voice has exactly model/config/MODEL_CARD.
- Safe IDs/aliases/paths/filenames.
- Artifact URLs use the exact resolved upstream SHA.
- Artifact sizes are positive.
- MD5 fields are valid.
- Aliases are globally unambiguous.
- Speaker map IDs satisfy the current contract.
- Deterministic output for the same source.

## Refresh

The catalog is refreshed daily via GitHub Actions. The workflow:

1. Resolves upstream `main` to an exact commit SHA.
2. Fetches and normalizes `voices.json` from Hugging Face.
3. Writes `catalog/voices.json` and `catalog/source.json`.
4. Validates the committed data.
5. Commits and pushes only if the catalog changed.

Manual refresh:

```bash
python scripts/refresh_catalog.py
python scripts/verify_catalog.py
```

## Licensing

- Repository-authored metadata/docs use the MIT license.
- Model/config/MODEL_CARD content belongs to upstream licensing.
- Every voice requires MODEL_CARD.
