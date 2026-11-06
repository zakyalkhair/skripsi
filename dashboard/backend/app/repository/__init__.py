"""Repositori data: FileRepository (DATA_SOURCE=file) dan Neo4jRepository (DATA_SOURCE=neo4j).
Keduanya mengembalikan bentuk respons yang sama karena respons disusun oleh service.py."""
from __future__ import annotations

from ..config import Settings
from .base import Repository


def make_repository(s: Settings) -> Repository:
    if s.data_source == "neo4j":
        from .neo4j_repo import Neo4jRepository

        return Neo4jRepository(s)
    if s.data_source != "file":
        raise ValueError(f"DATA_SOURCE tidak dikenal: {s.data_source!r} (pilih file atau neo4j)")
    from .file_repo import FileRepository

    return FileRepository(s)
