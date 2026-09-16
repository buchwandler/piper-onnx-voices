"""Catalog and downloader for Piper ONNX voices."""

from .catalog import (
    DEFAULT_REPOSITORY,
    DEFAULT_REVISION,
    CatalogError,
    build_catalog,
    fetch_and_build_catalog,
    get_voice,
    list_voices,
    load_catalog,
    resolve_revision,
)
from .download import DownloadError, download_voice

__all__ = [
    "DEFAULT_REPOSITORY",
    "DEFAULT_REVISION",
    "CatalogError",
    "DownloadError",
    "build_catalog",
    "download_voice",
    "fetch_and_build_catalog",
    "get_voice",
    "list_voices",
    "load_catalog",
    "resolve_revision",
]
