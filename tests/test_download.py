from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from piper_voice_catalog.catalog import CatalogError, build_catalog
from piper_voice_catalog.download import DownloadError, download_voice


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def artifact(role: str, filename: str, payload: bytes):
    return {
        "role": role,
        "path": filename,
        "filename": filename,
        "url": f"https://example.invalid/{filename}",
        "size": len(payload),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


def voice():
    return {
        "id": "v",
        "artifacts": {
            "model_card": artifact("model_card", "MODEL_CARD", b"card"),
            "model": artifact("model", "v.onnx", b"model"),
            "config": artifact("config", "v.onnx.json", b"{}"),
        },
    }


def payloads():
    return {
        "https://example.invalid/MODEL_CARD": b"card",
        "https://example.invalid/v.onnx": b"model",
        "https://example.invalid/v.onnx.json": b"{}",
    }


def test_download_voice_writes_exact_three_files(monkeypatch, tmp_path: Path) -> None:
    values = payloads()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: Response(values[request.full_url]),
    )
    paths = download_voice(voice(), tmp_path / "nested" / "voice")
    assert {path.name for path in paths} == {"MODEL_CARD", "v.onnx", "v.onnx.json"}
    assert {path.name for path in (tmp_path / "nested" / "voice").iterdir()} == {
        "MODEL_CARD",
        "v.onnx",
        "v.onnx.json",
    }


def test_matching_existing_files_are_reused_without_network(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "voice"
    target.mkdir()
    for filename, value in [
        ("MODEL_CARD", b"card"),
        ("v.onnx", b"model"),
        ("v.onnx.json", b"{}"),
    ]:
        (target / filename).write_bytes(value)

    def fail(*args, **kwargs):
        raise AssertionError("network should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert len(download_voice(voice(), target)) == 3


def test_corrupt_existing_file_requires_overwrite(monkeypatch, tmp_path: Path) -> None:
    values = payloads()
    target = tmp_path / "voice"
    target.mkdir()
    (target / "MODEL_CARD").write_bytes(b"corrupt")
    with pytest.raises(DownloadError, match="use --overwrite"):
        download_voice(voice(), target)

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: Response(values[request.full_url]),
    )
    download_voice(voice(), target, overwrite=True)
    assert (target / "MODEL_CARD").read_bytes() == b"card"


def test_network_failure_removes_partial_file(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "voice"

    def fail(request, timeout=0):
        raise OSError("network failed")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(OSError, match="network failed"):
        download_voice(voice(), target)
    assert not list(target.glob("*.part"))


def test_wrong_size_and_md5_remove_partial_file(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "voice"
    values = payloads()
    bad = voice()
    bad["artifacts"]["model"]["size"] += 1
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: Response(values[request.full_url]),
    )
    with pytest.raises(DownloadError, match="expected"):
        download_voice(bad, target)
    assert not list(target.glob("*.part"))

    bad = voice()
    bad["artifacts"]["model"]["md5"] = "0" * 32
    with pytest.raises(DownloadError, match="MD5 mismatch"):
        download_voice(bad, target)
    assert not list(target.glob("*.part"))


@pytest.mark.parametrize("filename", ["../x", "../../x", "/absolute/path", r"..\x"])
def test_unsafe_filenames_are_rejected(filename: str, tmp_path: Path) -> None:
    bad = voice()
    bad["artifacts"]["model"]["filename"] = filename
    with pytest.raises(DownloadError, match="Unsafe artifact filename"):
        download_voice(bad, tmp_path)
    assert not (tmp_path / "x").exists()


def test_catalog_rejects_voice_id_traversal() -> None:
    data = {
        "../outside": {
            "key": "../outside",
            "name": "voice",
            "language": {"code": "en_US", "family": "en"},
            "quality": "medium",
            "num_speakers": 1,
            "speaker_id_map": {},
            "aliases": [],
            "files": {
                "voice/MODEL_CARD": {"size_bytes": 1, "md5_digest": "0" * 32},
                "voice/voice.onnx": {"size_bytes": 1, "md5_digest": "1" * 32},
                "voice/voice.onnx.json": {"size_bytes": 1, "md5_digest": "2" * 32},
            },
        }
    }
    with pytest.raises(CatalogError, match="path separators"):
        build_catalog(data)


def test_symlink_destination_is_rejected(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "voice"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "MODEL_CARD").symlink_to(outside / "MODEL_CARD")
    with pytest.raises(DownloadError, match="symlink"):
        download_voice(voice(), target)
