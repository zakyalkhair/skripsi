"""Satu-satunya tempat logika yang bergantung pada skema (pertanyaan skema yang belum selesai):

1. DisasterEvent belum punya kode_kab -> diturunkan dari kode_kab EventMention (modus).
2. AffectedObject belum pasti punya atribusi lokasi -> hanya lewat relasi LOCATED_IN eksplisit.
3. Tingkat lokasi (desa, kecamatan, gunung, ...) dan kab/kota lokasi diambil dari gazetteer lokal,
   bukan properti Location.

Arah relasi yang diasumsikan (REL) dipakai bersama oleh FileRepository, kueri Cypher, dan skrip seed.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from .domain import Graph

REL = {
    "REPORTS": ("Tweet", "EventMention"),
    "CONSOLIDATED_INTO": ("EventMention", "DisasterEvent"),
    "MENTIONS": ("EventMention", "Location"),
    "LOCATED_IN": ("Location|AffectedObject", "Location"),
    "EVACUATED_TO": ("EventMention", "Location"),
    "AFFECTED": ("EventMention", "AffectedObject"),
    "REQUIRES": ("EventMention", "HumanitarianNeed"),
    "DEPLOYED_TO": ("Organization", "Location"),
    "HANDLES": ("Organization", "EventMention"),
    "PART_OF": ("Organization", "Organization"),
}
TINGKAT_POLIGON = {"provinsi", "kabupaten", "kota"}  # ditampilkan sebagai poligon, bukan titik


def to_date(v) -> date:
    if isinstance(v, date):
        return v
    if hasattr(v, "to_native"):  # neo4j.time.Date
        return v.to_native()
    return date.fromisoformat(str(v)[:10])


def event_kode_kab(g: Graph, event_id: str) -> str | None:
    kab = Counter(g.mentions[m]["kode_kab"] for m, e in g.m_event.items() if e == event_id and m in g.mentions)
    return kab.most_common(1)[0][0] if kab else None


def tingkat(g: Graph, gid: str) -> str:
    return g.gazetteer.get(gid, {}).get("tingkat", "tidak diketahui")


def kab_lokasi(g: Graph, gid: str) -> str | None:
    return g.gazetteer.get(gid, {}).get("kode_kab")


def koordinat(loc: dict) -> tuple[float, float] | None:
    c = loc.get("coordinates")
    if not c or c.get("latitude") is None or c.get("longitude") is None:
        return None
    return float(c["latitude"]), float(c["longitude"])


def is_titik(g: Graph, gid: str) -> bool:
    """Lokasi halus yang boleh tampil sebagai penanda: bukan tingkat poligon dan punya koordinat."""
    loc = g.locations.get(gid)
    return bool(loc) and tingkat(g, gid) not in TINGKAT_POLIGON and koordinat(loc) is not None


def build_graph(nodes: dict, rels: list[dict], gazetteer: dict) -> Graph:
    g = Graph(gazetteer=gazetteer)
    g.tweets = {t["tweet_id"]: t for t in nodes.get("Tweet", [])}
    g.mentions = {m["mention_id"]: m for m in nodes.get("EventMention", [])}
    g.events = {e["event_id"]: e for e in nodes.get("DisasterEvent", [])}
    g.locations = {l["gazetteer_id"]: l for l in nodes.get("Location", [])}
    g.affected = {a["id"]: a for a in nodes.get("AffectedObject", [])}
    g.needs = {n["id"]: n for n in nodes.get("HumanitarianNeed", [])}
    g.orgs = {o["id"]: o for o in nodes.get("Organization", [])}
    for r in rels:
        t, a, b = r["type"], r["from"], r["to"]
        if t == "REPORTS":
            g.m_tweets[b].add(a)
        elif t == "CONSOLIDATED_INTO":
            g.m_event[a] = b
        elif t == "MENTIONS":
            if b not in g.m_locs[a]:
                g.m_locs[a].append(b)
        elif t == "LOCATED_IN":
            (g.ao_loc if a in g.affected else g.loc_parent)[a].add(b)
        elif t == "EVACUATED_TO":
            g.m_evac[a].add(b)
        elif t == "AFFECTED":
            g.m_affected[a].add(b)
        elif t == "REQUIRES":
            g.m_needs[a].add(b)
        elif t == "DEPLOYED_TO":
            g.org_deployed[a].add(b)
        elif t == "HANDLES":
            g.org_handles[a].add(b)
        elif t == "PART_OF":
            g.org_parent[a] = b
    return g
