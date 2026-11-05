"""Repositori Neo4j (BACA SAJA): sesi READ_ACCESS + execute_read, Cypher berparameter dari queries.py.
Belum diuji terhadap graf hasil pipeline; lihat README bagian "Integrasi Neo4j"."""
from __future__ import annotations

import json
from datetime import date, timedelta

from .. import service
from ..adapter import build_graph
from ..config import Settings
from ..domain import Filter, Graph
from . import queries as Q
from .base import NotFound, Repository


def _p(f: Filter) -> dict:
    return {"jenis": sorted(f.jenis) if f.jenis is not None else None,
            "dari": f.dari.isoformat() if f.dari else None, "sampai": f.sampai.isoformat() if f.sampai else None}


class Neo4jRepository(Repository):
    sumber = "neo4j"

    def __init__(self, s: Settings):
        super().__init__(s)
        from neo4j import READ_ACCESS, GraphDatabase

        self._driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
        self._read = READ_ACCESS
        gaz = s.gazetteer_file  # gazetteer lokal (tingkat & kode_kab tiap gazetteer_id)
        self._gaz = json.loads(gaz.read_text(encoding="utf-8")) if gaz.exists() else {}

    def _run(self, cypher: str, **params) -> list[dict]:
        with self._driver.session(database=self.settings.neo4j_database, default_access_mode=self._read) as s:
            return s.execute_read(lambda tx: [r.data() for r in tx.run(cypher, **params)])

    def metadata(self) -> dict:
        r = self._run(Q.RENTANG)[0]
        return {"sumber": self.sumber, "label": "Graf Neo4j", "keterangan": None, "contoh": False,
                "rentang": {"awal": r["awal"], "akhir": r["akhir"]}}

    def kab_dengan_data(self) -> set[str]:
        return {r["kode_kab"] for r in self._run(Q.KAB_DENGAN_DATA) if r["kode_kab"]}

    def kab_agregat(self, f: Filter, prov: str | None = None) -> dict:
        if prov:
            self.cek_prov(prov)
        if f.jenis is not None and not f.jenis:
            return service.kab_agregat(Graph(), f, prov)
        rows = [r for r in self._run(Q.KAB_AGREGAT, **_p(f), prov=prov) if r["kode_kab"]]
        ring = self._run(Q.RINGKASAN, **_p(f), prov=prov)[0]
        return {"filter": {**f.as_dict(), "prov": prov}, "kab": rows, "ringkasan": ring}

    def graph_ekspor(self, f: Filter, prov: str | None, kab: str | None, lokasi: str | None) -> Graph:
        if lokasi:
            return self.graph_lokasi(lokasi, f)
        if kab:
            return self.graph_kab(kab, f)
        return self._subgraf(self._run(Q.MENTION_IDS_SEMUA, prov=prov)[0]["ids"])

    def histogram(self, f: Filter, kab: str | None, prov: str | None = None, lokasi: str | None = None) -> dict:
        if kab:
            self.cek_kab(kab)
        if prov:
            self.cek_prov(prov)
        r = self._run(Q.RENTANG)[0]
        if not r["awal"]:
            return service.histogram(Graph(), f, kab)
        lo, hi = date.fromisoformat(r["awal"]), date.fromisoformat(r["akhir"])
        weeks: dict[str, dict[str, int]] = {}
        w = service.monday(lo)
        while w <= service.monday(hi):
            weeks[w.isoformat()] = {}
            w += timedelta(days=7)
        if f.jenis is None or f.jenis:
            for row in self._run(Q.HISTOGRAM, jenis=_p(f)["jenis"], kab=kab, prov=prov, gid=lokasi):
                weeks.setdefault(row["mulai"], {})[row["jenis"]] = row["n"]
        return {"filter": {"jenis": f.as_dict()["jenis"], "kab": kab, "prov": prov, "lokasi": lokasi},
                "cakupan": "lokasi" if lokasi else "kab" if kab else "prov" if prov else "nasional",
                "satuan": "laporan kejadian (EventMention) unik",
                "minggu": [{"mulai": k, "total": sum(v.values()), "per_jenis": dict(sorted(v.items()))}
                           for k, v in sorted(weeks.items())],
                "rentang": {"awal": r["awal"], "akhir": r["akhir"]}}

    # ---- subgraf
    def _subgraf(self, ids: list[str], gid: str | None = None) -> Graph:
        nodes = {k: [] for k in ("Tweet", "EventMention", "DisasterEvent", "Location", "AffectedObject",
                                 "HumanitarianNeed", "Organization")}
        rels, gids, org_ids, seen = [], set(), set(), set()

        def add(kind, key, obj):
            if (kind, obj[key]) not in seen:
                seen.add((kind, obj[key]))
                nodes[kind].append(obj)

        for r in self._run(Q.SUBGRAF, ids=ids):
            m = r["m"]
            add("EventMention", "mention_id", m)
            if r["e"]:
                add("DisasterEvent", "event_id", r["e"])
                rels.append({"type": "CONSOLIDATED_INTO", "from": m["mention_id"], "to": r["e"]["event_id"]})
            for t in r["tweets"]:
                add("Tweet", "tweet_id", t)
                rels.append({"type": "REPORTS", "from": t["tweet_id"], "to": m["mention_id"]})
            for l in r["locs"]:
                gids.add(l)
                rels.append({"type": "MENTIONS", "from": m["mention_id"], "to": l})
            for l in r["evac"]:
                gids.add(l)
                rels.append({"type": "EVACUATED_TO", "from": m["mention_id"], "to": l})
            for a in r["aos"]:
                add("AffectedObject", "id", a["a"])
                rels.append({"type": "AFFECTED", "from": m["mention_id"], "to": a["a"]["id"]})
                for l in a["locs"]:
                    gids.add(l)
                    rels.append({"type": "LOCATED_IN", "from": a["a"]["id"], "to": l})
            for h in r["needs"]:
                add("HumanitarianNeed", "id", h)
                rels.append({"type": "REQUIRES", "from": m["mention_id"], "to": h["id"]})
                if h.get("lokasi"):
                    gids.add(h["lokasi"])
            for o in r["orgs"]:
                org_ids.add(o)
                rels.append({"type": "HANDLES", "from": o, "to": m["mention_id"]})
        for r in self._run(Q.ORGANISASI, org_ids=sorted(org_ids), gid=gid):
            add("Organization", "id", r["o"])
            for l in r["dep"]:
                gids.add(l)
                rels.append({"type": "DEPLOYED_TO", "from": r["o"]["id"], "to": l})
            for p in r["induk"]:
                add("Organization", "id", p)
                rels.append({"type": "PART_OF", "from": r["o"]["id"], "to": p["id"]})
        if gid:
            gids.add(gid)
        for l in self._run(Q.LOKASI, gids=sorted(gids)):
            nodes["Location"].append(l)
        return build_graph(nodes, rels, self._gaz)

    def graph_all(self) -> Graph:  # tidak dipakai untuk agregat (ditimpa di atas)
        raise NotImplementedError("Neo4jRepository tidak memuat seluruh graf")

    def graph_kab(self, kode: str, f: Filter) -> Graph:
        return self._subgraf(self._run(Q.MENTION_IDS_KAB, kode=kode)[0]["ids"])

    def graph_lokasi(self, gid: str, f: Filter) -> Graph:
        r = self._run(Q.MENTION_IDS_LOKASI, gid=gid)[0]
        if not r["ada"]:
            raise NotFound(f"lokasi {gid} tidak ditemukan")
        return self._subgraf(r["ids"], gid=gid)
