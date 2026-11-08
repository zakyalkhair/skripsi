"""Koneksi Neo4j: kredensial hanya dari variabel lingkungan / .env (tidak pernah ditulis di kode atau dokumen)."""
import os
from pathlib import Path


def muat_env(path=".env"):
    p = Path(path)
    if not p.exists(): return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def driver():
    muat_env()
    try:
        from neo4j import GraphDatabase
    except ImportError as e:
        raise SystemExit("Paket neo4j belum terpasang: pip install neo4j") from e
    uri, user, pw = os.environ.get("NEO4J_URI"), os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD")
    if not uri or not pw:
        raise SystemExit("Isi NEO4J_URI dan NEO4J_PASSWORD di file .env (lihat .env.example).")
    try:        # relasi yang belum ada di data (mis. EVACUATED_TO) hanya memicu peringatan; matikan agar keluaran bersih
        d = GraphDatabase.driver(uri, auth=(user, pw), notifications_min_severity="OFF")
    except TypeError:
        d = GraphDatabase.driver(uri, auth=(user, pw))
    return d, os.environ.get("NEO4J_DATABASE", "neo4j")
