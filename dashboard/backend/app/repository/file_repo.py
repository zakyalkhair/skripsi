from __future__ import annotations

import json

from ..adapter import build_graph
from ..config import Settings
from ..domain import Graph
from .base import Repository


class FileRepository(Repository):
    """Membaca data contoh (graf.json + gazetteer.json) sekali saat start; tidak pernah menulis."""

    sumber = "file"

    def __init__(self, s: Settings):
        super().__init__(s)
        raw = json.loads((s.contoh_dir / "graf.json").read_text(encoding="utf-8"))
        gaz = json.loads((s.contoh_dir / "gazetteer.json").read_text(encoding="utf-8"))
        self._meta = raw.get("metadata", {})
        self._g = build_graph(raw["nodes"], raw["relationships"], gaz)

    def graph_all(self) -> Graph:
        return self._g

    def metadata(self) -> dict:
        ds = sorted(m["tanggal_lokal"] for m in self._g.mentions.values())
        return {"sumber": self.sumber, "label": self._meta.get("label", "Data Contoh"),
                "keterangan": self._meta.get("keterangan"), "contoh": True,
                "rentang": {"awal": ds[0] if ds else None, "akhir": ds[-1] if ds else None}}
