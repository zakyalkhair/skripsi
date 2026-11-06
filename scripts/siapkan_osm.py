"""Siapkan fitur OSM bernama untuk resolusi lokasi 2.3 (jalur detail: jalan, tempat, gunung, sungai).  (30 Okt 2026)

Cara pakai (di laptop; Python Windows yang biasa dipakai):
    pip install osmium shapely
    # unduh dulu https://download.geofabrik.de/asia/indonesia-latest.osm.pbf  -> data\\raw\\indonesia-latest.osm.pbf
    python scripts\\siapkan_osm.py --pbf data\\raw\\indonesia-latest.osm.pbf
    python scripts\\siapkan_osm.py --pbf ... --limit-kec 50     # uji kecil dulu

Hasil: data/gazetir/osm_feat.csv  (kolom: osm_id, tipe_osm, nama, nama_norm, jenis, lat, lon, kode_kec, panjang_km)
Setiap fitur diberi `kode_kec` lewat titik-dalam-poligon kecamatan (data/gazetir/poligon_kec.csv; sumber
cahyadsn/wilayah_boundaries, MIT). Titik di luar semua poligon (laut) mendapat kode_kec kosong.
Data OSM: (c) OpenStreetMap contributors, lisensi ODbL. Catat tanggal unduh pbf di data/gazetir/SUMBER.md.

Jenis (hanya fitur BERNAMA):
  jalan (highway bernama, ruas bersambung bernama sama di kecamatan sama digabung), sungai (waterway=river|stream|canal),
  gunung (natural=peak|volcano), pulau (place=island|islet), permukiman (place=village|hamlet|suburb|neighbourhood|quarter),
  rumah_sakit, sekolah, masjid, jembatan, pelabuhan (harbour/ferry_terminal/man_made=pier), bandara, stasiun, pasar,
  lainnya (amenity/tourism/leisure/natural=bay|beach|water bernama).
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

import osmium
from shapely import wkt
from shapely.geometry import Point
from shapely.strtree import STRtree

NORM = re.compile(r"[^a-z0-9 ]+")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", NORM.sub(" ", s.lower())).strip()


def jenis_dari(tags) -> str | None:
    g = tags.get
    if g("natural") in ("peak", "volcano"):
        return "gunung"
    if g("waterway") in ("river", "stream", "canal", "drain"):
        return "sungai"
    if g("place") in ("island", "islet"):
        return "pulau"
    if g("place") in ("village", "hamlet", "suburb", "neighbourhood", "quarter", "town", "city", "locality"):
        return "permukiman"
    if g("amenity") in ("hospital", "clinic") or g("healthcare") == "hospital":
        return "rumah_sakit"
    if g("amenity") in ("school", "college", "university", "kindergarten"):
        return "sekolah"
    if g("amenity") == "place_of_worship":
        return "masjid" if g("religion") == "muslim" else "ibadah_lain"
    if g("man_made") in ("bridge", "pier") or g("bridge") == "yes" and g("highway"):
        return "jembatan" if g("man_made") != "pier" else "pelabuhan"
    if g("amenity") == "ferry_terminal" or g("harbour") == "yes" or g("landuse") == "port" or g("industrial") == "port":
        return "pelabuhan"
    if g("aeroway") in ("aerodrome", "terminal"):
        return "bandara"
    if g("railway") in ("station", "halt") or g("public_transport") == "station":
        return "stasiun"
    if g("amenity") == "marketplace" or g("shop") == "mall":
        return "pasar"
    if g("highway") and g("highway") not in ("footway", "path", "steps", "cycleway", "pedestrian", "corridor", "bus_stop", "street_lamp", "crossing", "traffic_signals"):
        return "jalan"
    if g("tourism") in ("attraction", "viewpoint", "museum", "zoo", "theme_park", "camp_site", "hotel", "guest_house") or g("leisure") in ("park", "stadium", "sports_centre"):
        return "lainnya"
    if g("natural") in ("bay", "beach", "water", "cape", "strait"):
        return "lainnya"
    return None


class Penampung(osmium.SimpleHandler):
    def __init__(self, tulis, kec_tree, kec_kode, batas=None):
        super().__init__()
        self.tulis, self.tree, self.kode, self.n = tulis, kec_tree, kec_kode, 0
        self.jalan = {}          # (nama_norm, kode_kec) -> [jumlah_ruas, panjang_km, sum_lat, sum_lon, osm_id, nama]
        self.t0 = time.time()

    def _kec(self, lat, lon):
        p = Point(lon, lat)
        for i in self.tree.query(p, predicate="within"):
            return self.kode[int(i)]
        # pesisir/batas: poligon disederhanakan (0,002 derajat) bisa menyisakan celah -> poligon terdekat <= ±1 km
        dekat = self.tree.query_nearest(p, max_distance=0.01)
        return self.kode[int(dekat[0])] if len(dekat) else ""

    def _catat(self, osm_id, tipe, nama, jenis, lat, lon, panjang=""):
        self.tulis.writerow([osm_id, tipe, nama, norm(nama), jenis, round(lat, 6), round(lon, 6), self._kec(lat, lon), panjang])
        self.n += 1
        if self.n % 200000 == 0:
            print(f"  {self.n:,} fitur, {time.time()-self.t0:.0f} dtk", file=sys.stderr)

    def node(self, n):
        nama = n.tags.get("name")
        if not nama or not n.location.valid():
            return
        j = jenis_dari(n.tags)
        if j and j != "jalan" and j != "sungai":
            self._catat(n.id, "node", nama, j, n.location.lat, n.location.lon)

    def way(self, w):
        nama = w.tags.get("name")
        if not nama:
            return
        j = jenis_dari(w.tags)
        if not j:
            return
        try:
            pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        except osmium.InvalidLocationError:
            return
        if not pts:
            return
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        if j in ("jalan", "sungai"):
            panjang = 0.0
            for (a, b), (c, d) in zip(pts, pts[1:]):
                panjang += (((a - c) * 111.2) ** 2 + ((b - d) * 111.2 * 0.99) ** 2) ** 0.5
            kk = (j, norm(nama), self._kec(lat, lon))
            r = self.jalan.setdefault(kk, [0, 0.0, 0.0, 0.0, w.id, nama])
            r[0] += 1; r[1] += panjang; r[2] += lat; r[3] += lon
        else:
            self._catat(w.id, "way", nama, j, lat, lon)

    def selesai(self):
        for (j, nn, kec), (cnt, pj, sl, so, oid, nama) in self.jalan.items():
            self.tulis.writerow([oid, "way", nama, nn, j, round(sl / cnt, 6), round(so / cnt, 6), kec, round(pj, 3)])
            self.n += 1


def main():
    csv.field_size_limit(2**31 - 1)   # Windows: batas C long 32-bit
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", required=True)
    ap.add_argument("--poligon", default="data/gazetir/poligon_kec.csv")
    ap.add_argument("--out", default="data/gazetir/osm_feat.csv")
    ap.add_argument("--limit-kec", type=int, default=None, help="hanya N kecamatan pertama (uji kecil; fitur di luar poligon tetap ditulis tanpa kode)")
    a = ap.parse_args()
    kode, geoms = [], []
    for r in csv.DictReader(open(a.poligon, encoding="utf-8")):
        kode.append(r["kode"]); geoms.append(wkt.loads(r["wkt"]))
        if a.limit_kec and len(kode) >= a.limit_kec:
            break
    print(f"{len(kode)} poligon kecamatan dimuat", file=sys.stderr)
    tree = STRtree(geoms)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["osm_id", "tipe_osm", "nama", "nama_norm", "jenis", "lat", "lon", "kode_kec", "panjang_km"])
        h = Penampung(w, tree, kode)
        h.apply_file(a.pbf, locations=True, idx="flex_mem")
        h.selesai()
    print(f"selesai: {h.n:,} fitur -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
