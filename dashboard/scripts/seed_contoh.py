"""Muat data contoh ke Neo4j LOKAL (terpisah dari dashboard yang baca-saja).

    cd dashboard/backend && .venv/bin/python ../scripts/seed_contoh.py [--hapus-contoh]

Memakai NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD dari backend/.env. Hanya MERGE node data contoh
(semua id berawalan contoh/DE/EM/T/AO/HN/ORG dari graf.json); --hapus-contoh menghapus node yang
ditandai `contoh: true` lebih dulu. Jangan dijalankan ke graf produksi.
"""
import json
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.adapter import REL  # noqa: E402
from app.config import Settings  # noqa: E402

KEY = {"Tweet": "tweet_id", "EventMention": "mention_id", "DisasterEvent": "event_id", "Location": "gazetteer_id",
       "AffectedObject": "id", "HumanitarianNeed": "id", "Organization": "id"}
DATE_FIELDS = {"EventMention": ["tanggal_lokal"], "DisasterEvent": ["start_time", "end_time"]}


def main() -> None:
    s = Settings()
    data = json.loads((s.contoh_dir / "graf.json").read_text(encoding="utf-8"))
    label_of = {n[KEY[lbl]]: lbl for lbl, ns in data["nodes"].items() for n in ns}
    drv = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with drv.session(database=s.neo4j_database) as ses:
        if "--hapus-contoh" in sys.argv:
            ses.run("MATCH (n {contoh: true}) DETACH DELETE n")
        for lbl, key in KEY.items():
            ses.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{lbl}) REQUIRE n.{key} IS UNIQUE")
        for lbl, ns in data["nodes"].items():
            key = KEY[lbl]
            for n in ns:
                props = {k: v for k, v in n.items() if k not in ("coordinates",) and v is not None}
                c = n.get("coordinates")
                dates = DATE_FIELDS.get(lbl, [])
                sets = ", ".join(f"n.{d} = date($p.{d})" for d in dates if d in props)
                ses.run(f"MERGE (n:{lbl} {{{key}: $p.{key}}}) SET n += $p, n.contoh = true"
                        + (f", {sets}" if sets else "")
                        + (", n.coordinates = point({latitude: $lat, longitude: $lon})" if c else ""),
                        p=props, lat=c["latitude"] if c else None, lon=c["longitude"] if c else None)
        for r in data["rels"] if "rels" in data else data["relationships"]:
            a, b, t = r["from"], r["to"], r["type"]
            la, lb = label_of[a], label_of[b]
            assert la in REL[t][0].split("|") and lb == REL[t][1], (t, la, lb)
            ses.run(f"MATCH (a:{la} {{{KEY[la]}: $a}}), (b:{lb} {{{KEY[lb]}: $b}}) MERGE (a)-[:{t}]->(b)", a=a, b=b)
    drv.close()
    print("Data contoh dimuat ke", s.neo4j_uri, "— jalankan dashboard dengan DATA_SOURCE=neo4j")


if __name__ == "__main__":
    os.environ.setdefault("DATA_SOURCE", "neo4j")
    main()
