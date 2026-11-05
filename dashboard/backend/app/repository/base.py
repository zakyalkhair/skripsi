from __future__ import annotations

import json
from abc import ABC, abstractmethod

from .. import service
from ..config import Settings
from ..domain import Filter, Graph


class NotFound(Exception):
    pass


class Repository(ABC):
    """Antarmuka baca-saja. Subkelas cukup menyediakan subgraf; agregasi ada di service.py
    (atau ditimpa dengan agregasi Cypher di Neo4jRepository)."""

    sumber = "?"

    def __init__(self, s: Settings):
        self.settings = s
        self._wilayah = json.loads(s.wilayah_file.read_text(encoding="utf-8"))
        self._kab_names = {w["kode_kab"]: w for w in self._wilayah}

    # ---- subgraf
    @abstractmethod
    def graph_all(self) -> Graph: ...

    def graph_kab(self, kode: str, f: Filter) -> Graph:
        return self.graph_all()

    def graph_lokasi(self, gid: str, f: Filter) -> Graph:
        return self.graph_all()

    @abstractmethod
    def metadata(self) -> dict: ...

    def kab_dengan_data(self) -> set[str]:
        return {k["kode_kab"] for k in service.kab_agregat(self.graph_all(), Filter())["kab"]}

    # ---- endpoint
    def wilayah(self) -> dict:
        ada = self.kab_dengan_data()
        prov: dict[str, str] = {}
        kab = []
        for w in self._wilayah:
            prov[w["kode_prov"]] = w["provinsi"]
            kab.append({**w, "ada_data": w["kode_kab"] in ada})
        return {"provinsi": [{"kode_prov": k, "nama": v} for k, v in sorted(prov.items())], "kab": kab,
                "dataset": self.metadata()}

    def cek_kab(self, kode: str) -> dict:
        if kode not in self._kab_names:
            raise NotFound(f"kab/kota {kode} tidak dikenal")
        return self._kab_names[kode]

    def kab_agregat(self, f: Filter) -> dict:
        return service.kab_agregat(self.graph_all(), f)

    def kab_kejadian(self, kode: str, f: Filter) -> dict:
        return {**service.kab_kejadian(self.graph_kab(kode, f), kode, f), "nama": self.cek_kab(kode)["nama"]}

    def kab_titik(self, kode: str, f: Filter) -> dict:
        self.cek_kab(kode)
        out = service.kab_titik(self.graph_kab(kode, f), kode, f)
        for t in out["titik"]:
            w = self._kab_names.get(t["kode_kab_lokasi"] or "")
            t["nama_kab_lokasi"] = w["nama"] if w else None
        return out

    def titik_ringkasan(self, gid: str, f: Filter) -> dict:
        g = self.graph_lokasi(gid, f)
        if gid not in g.locations:
            raise NotFound(f"lokasi {gid} tidak ditemukan")
        out = service.titik_ringkasan(g, gid, f)
        for k in out["kejadian"]:
            w = self._kab_names.get(k["kode_kab"] or "")
            k["nama_kab"] = w["nama"] if w else None
        return out

    def histogram(self, f: Filter, kab: str | None) -> dict:
        if kab:
            self.cek_kab(kab)
        return service.histogram(self.graph_all(), f, kab)
