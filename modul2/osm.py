"""2.3 jalur detail (jalan, tempat, gunung, sungai) terhadap ekstrak OSM lokal `data/gazetir/osm_feat.csv`
(dibuat `scripts/siapkan_osm.py`; (c) OpenStreetMap contributors, ODbL). Hanya pencocokan nama PERSIS (ternormalisasi);
fuzzy menunggu kalibrasi dengan gold. Koordinat dari OSM, tidak pernah dari LLM.

Memori: CSV dipindai sekali dan hanya baris yang namanya dicari yang disimpan (`OsmIndex.muat(csv, nama_dicari)`).
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

_NON = re.compile(r"[^a-z0-9 ]+")
_ALIAS = {"jl": "jalan", "gg": "gang"}


def norm_osm(s: str) -> str:
    t = re.sub(r"\s+", " ", _NON.sub(" ", (s or "").lower())).strip()
    return " ".join(_ALIAS.get(w, w) for w in t.split())


class OsmIndex:
    def __init__(self):
        self.baris: dict[str, list[dict]] = defaultdict(list)
        self.ada = False

    @classmethod
    def muat(cls, path: Path, dicari: set[str]) -> "OsmIndex":
        ix = cls()
        if not Path(path).exists():
            return ix
        csv.field_size_limit(2**31 - 1)   # Windows: batas C long 32-bit
        ix.ada = True
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r["nama_norm"] in dicari:
                ix.baris[r["nama_norm"]].append(r)
        return ix

    def cari(self, nama: str, prefix_kode: tuple[str, ...] | None = None) -> list[dict]:
        rows = self.baris.get(norm_osm(nama), [])
        if prefix_kode:
            rows = [r for r in rows if any((r["kode_kec"] or "").startswith(p) for p in prefix_kode)]
        return gabung_ruas(rows)


_RUAS = {"jalan", "jembatan", "sungai"}


def gabung_ruas(rows: list[dict]) -> list[dict]:
    """Ruas/jembatan bernama sama di kecamatan yang sama = satu jalan: gabung (pilih ruas terpanjang, jembatan belakangan).
    Fitur lain (sekolah, masjid, dll.) tidak digabung. Jumlah ruas digabung disimpan di `n_digabung`."""
    out, grup = [], {}
    for r in rows:
        if r["jenis"] in _RUAS:
            g = grup.setdefault((r["kode_kec"], "sungai" if r["jenis"] == "sungai" else "jalan"), [])
            g.append(r)
        else:
            out.append(r)
    for g in grup.values():
        g.sort(key=lambda r: (r["jenis"] != "jalan", -float(r["panjang_km"] or 0)))
        pilih = dict(g[0]); pilih["n_digabung"] = len(g)
        out.append(pilih)
    return out


def kueri_detail(loc: dict) -> str | None:
    """Teks yang dicari di OSM: `detail` bila ada, kalau tidak teks lokasi utuh."""
    q = (loc.get("detail") or loc.get("teks") or "").strip()
    return q or None


def hasil_osm(rows: list[dict], metode: str, admin: dict | None = None) -> dict:
    """Satu kandidat OSM -> kotak resolusi. `admin` = hasil administratif (bila ada) sebagai induk."""
    r = rows[0]
    return {"status": "resolved", "kode_hasil": "R_OK", "alasan": None, "path": "C" if admin else "D",
            "gazetteer_id": f"osm:{r['tipe_osm']}/{r['osm_id']}", "level_admin": "detail",
            "nama_resmi": r["nama"], "jenis_wilayah": r["jenis"],
            "admin_path": (admin or {}).get("admin_path") or ([r["kode_kec"][:2], r["kode_kec"][:5], r["kode_kec"]] if r["kode_kec"] else []),
            "admin_nama": (admin or {}).get("admin_nama"), "metode": metode, "dasar": ["osm"], "k_kandidat": 1,
            "kandidat": None, "perlu_llm": False, "lat": float(r["lat"]), "lon": float(r["lon"]),
            "presisi_koordinat": "titik_fitur_osm" if r["jenis"] not in ("jalan", "sungai") else "titik_tengah_ruas_osm",
            "catatan": ["koordinat_jalan_adalah_rata_rata_ruas"] if r["jenis"] in ("jalan", "sungai") else []}
