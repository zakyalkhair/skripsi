"""Bangun GeoJSON batas kab/kota (kode Kemendagri) yang disederhanakan untuk dashboard.

Sumber: shapefile "Batas Kabupaten" Kemendagri 2020 (514 kab/kota) dari
github.com/Alf-Anas/batas-administrasi-indonesia (folder 2020/, diekstrak dari portal GIS Dukcapil).

    python dashboard/scripts/build_geo.py "path/ke/Batas Kabupaten.shp"

Keluaran (frontend/public/geo/):
  kabkota.geojson  - semua kab/kota; provinsi dalam DETAIL_PROV disederhanakan lebih halus
  provinsi.geojson - garis batas provinsi (gabungan kab/kota, kasar) untuk tampilan nasional
Penyederhanaan Douglas-Peucker (shapely, preserve_topology) hanya untuk visualisasi.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import shapefile  # pyshp
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "geo"
DETAIL_PROV = {"35"}  # Jawa Timur: cakupan data contoh
TOL_DETAIL, TOL_KASAR, TOL_PROV = 0.0025, 0.02, 0.05


def rnd(o, nd):
    if isinstance(o, (list, tuple)):
        return [rnd(x, nd) for x in o] if not isinstance(o[0], (int, float)) else [round(o[0], nd), round(o[1], nd)]
    return o


def title(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split())


def main(shp: str) -> None:
    r = shapefile.Reader(shp)
    geoms, props = defaultdict(list), {}
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        kode = str(rec["Kode_Kab"]).strip()
        if not kode.isdigit() or len(kode) != 4:
            continue  # objek non-administratif (danau/hutan)
        g = shape(sr.shape.__geo_interface__)
        if not g.is_valid:
            g = g.buffer(0)
        geoms[kode].append(g)
        nama = title(rec["Kab_Kota"])
        props[kode] = {"kode_kab": kode, "nama": nama if nama.startswith("Kota ") else f"Kab. {nama}",
                       "provinsi": title(rec["Provinsi"]), "kode_prov": kode[:2]}
    feats, by_prov = [], defaultdict(list)
    for kode in sorted(geoms):
        g = unary_union(geoms[kode])
        by_prov[kode[:2]].append(g)
        detail = kode[:2] in DETAIL_PROV
        s = g.simplify(TOL_DETAIL if detail else TOL_KASAR, preserve_topology=True)
        if s.is_empty:
            continue
        feats.append({"type": "Feature", "properties": props[kode],
                      "geometry": {**mapping(s), "coordinates": rnd(mapping(s)["coordinates"], 4 if detail else 3)}})
    prov = []
    for kp, gs in sorted(by_prov.items()):
        s = unary_union(gs).simplify(TOL_PROV, preserve_topology=True)
        nama = next(p["provinsi"] for p in props.values() if p["kode_prov"] == kp)
        prov.append({"type": "Feature", "properties": {"kode_prov": kp, "nama": nama},
                     "geometry": {**mapping(s), "coordinates": rnd(mapping(s)["coordinates"], 3)}})
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"sumber": "Kemendagri 2020 via github.com/Alf-Anas/batas-administrasi-indonesia", "disederhanakan": True}
    for name, fs in (("kabkota", feats), ("provinsi", prov)):
        (OUT / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "metadata": meta, "features": fs},
                                                        separators=(",", ":")), encoding="utf-8")
        print(name, len(fs), round((OUT / f"{name}.geojson").stat().st_size / 1e6, 2), "MB")
    # daftar wilayah untuk backend (GET /api/wilayah)
    wil = [{"kode_kab": p["kode_kab"], "nama": p["nama"], "kode_prov": p["kode_prov"], "provinsi": p["provinsi"]}
           for p in (f["properties"] for f in feats)]
    (OUT.parents[2] / "data" / "wilayah.json").write_text(json.dumps(wil, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
