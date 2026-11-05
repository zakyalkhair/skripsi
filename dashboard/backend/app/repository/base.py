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

    def cek_prov(self, kode: str) -> str:
        nama = next((w["provinsi"] for w in self._wilayah if w["kode_prov"] == kode), None)
        if nama is None:
            raise NotFound(f"provinsi {kode} tidak dikenal")
        return nama

    def kab_agregat(self, f: Filter, prov: str | None = None) -> dict:
        if prov:
            self.cek_prov(prov)
        return service.kab_agregat(self.graph_all(), f, prov)

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

    def histogram(self, f: Filter, kab: str | None, prov: str | None = None, lokasi: str | None = None) -> dict:
        if kab:
            self.cek_kab(kab)
        if prov:
            self.cek_prov(prov)
        g = self.graph_all()
        if lokasi and lokasi not in g.locations:
            raise NotFound(f"lokasi {lokasi} tidak ditemukan")
        return service.histogram(g, f, kab, prov=prov, lokasi=lokasi)

    def graph_ekspor(self, f: Filter, prov: str | None, kab: str | None, lokasi: str | None) -> Graph:
        return self.graph_all()

    def ekspor(self, f: Filter, prov: str | None = None, kab: str | None = None, lokasi: str | None = None) -> dict:
        """Tabel ekspor + manifest. Nama wilayah dilengkapi dari data wilayah resmi (kode Kemendagri)."""
        if kab:
            self.cek_kab(kab)
        if prov:
            self.cek_prov(prov)
        g = self.graph_ekspor(f, prov, kab, lokasi)
        if lokasi and lokasi not in g.locations:
            raise NotFound(f"lokasi {lokasi} tidak ditemukan")
        tabel = service.ekspor(g, f, prov=prov, kab=kab, lokasi=lokasi)
        for r in tabel["kejadian"]:
            w = self._kab_names.get(r["kode_kab"] or "")
            r["nama_kab"] = w["nama"] if w else None
            r["provinsi"] = w["provinsi"] if w else None
        meta = self.metadata()
        cakupan = {"tingkat": "lokasi" if lokasi else "kab" if kab else "prov" if prov else "nasional",
                   "kode_prov": prov, "kode_kab": kab, "gazetteer_id": lokasi,
                   "nama": (g.locations[lokasi]["nama"] if lokasi else self._kab_names[kab]["nama"] if kab
                            else self.cek_prov(prov) if prov else "Indonesia")}
        return {"tabel": tabel, "cakupan": cakupan, "dataset": meta}
