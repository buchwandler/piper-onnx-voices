# Changelog

## 0.1.0 - 2026-09-16

Initial release.

### Added

- Dependency-free Python API and `piper-voices` CLI.
- Catalog normalization for all entries from `rhasspy/piper-voices`.
- Pinned Hugging Face artifact URLs using an exact upstream commit SHA.
- Required `MODEL_CARD`, `.onnx`, and `.onnx.json` artifacts for every voice.
- Voice aliases, locale and language metadata, qualities, and speaker maps.
- Atomic downloader with byte-size and upstream MD5 verification.
- Materialized `catalog/voices.json` plus `catalog/source.json` provenance.
- JSON Schema for external catalog consumers.
- Deterministic catalog refresh and verification scripts.
- GitHub Actions checks and scheduled catalog refresh.

### Catalog snapshot

- 176 voices.
- Upstream revision:
  `1162a9173d0ce503555aed757976b7a9912eae4c`.
