"""Konfigurasi dari environment (.env). Tidak ada rahasia di kode."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # python-dotenv opsional
    pass

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Settings:
    data_source: str = field(default_factory=lambda: os.environ.get("DATA_SOURCE", "file").lower())
    contoh_dir: Path = field(default_factory=lambda: Path(os.environ.get("CONTOH_DIR", DATA_DIR / "contoh")))
    wilayah_file: Path = DATA_DIR / "wilayah.json"
    gazetteer_file: Path = field(default_factory=lambda: Path(
        os.environ.get("GAZETTEER_FILE", DATA_DIR / "contoh" / "gazetteer.json")))
    neo4j_uri: str = field(default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD", ""))
    neo4j_database: str = field(default_factory=lambda: os.environ.get("NEO4J_DATABASE", "neo4j"))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()))
