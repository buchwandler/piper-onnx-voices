from __future__ import annotations

import hashlib
import io
from pathlib import Path

from piper_voice_catalog.download import download_voice


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


def test_download_voice_writes_exact_three_files(monkeypatch, tmp_path: Path) -> None:
    payloads = {
        "https://example.invalid/MODEL_CARD": b"card",
        "https://example.invalid/v.onnx": b"model",
        "https://example.invalid/v.onnx.json": b"{}",
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: Response(payloads[request.full_url]),
    )
    voice = {
        "id": "v",
        "artifacts": {
            "model_card": artifact("model_card", "MODEL_CARD", b"card"),
            "model": artifact("model", "v.onnx", b"model"),
            "config": artifact("config", "v.onnx.json", b"{}"),
        },
    }
    paths = download_voice(voice, tmp_path)
    assert {p.name for p in paths} == {"MODEL_CARD", "v.onnx", "v.onnx.json"}
    assert {p.name for p in tmp_path.iterdir()} == {
        "MODEL_CARD",
        "v.onnx",
        "v.onnx.json",
    }
