"""2.3 Resolusi lokasi — tahap administratif (27 Okt 2026). Rancangan: claude/TEKNIS-2.3.md.

Yang dikerjakan di sini (deterministik, tanpa LLM): R0 seleksi, R1 normalisasi, R3 resolusi wilayah dari atas ke bawah
terhadap gazetir Kemendagri (provinsi, kab/kota, kecamatan, desa/kelurahan), pemecah seri dari lokasi lain di tweet yang
sama (R5 butir 1), dan fallback ke wilayah yang tertulis (R6). Koordinat TIDAK ada di sini (belum ada poligon/titik pusat).
Detail di bawah desa (jalan, sungai, POI = jalur C/D) menunggu fitur OSM lokal: dicatat `detail_belum_diresolusi`.
Koordinat dan nama wilayah selalu dari gazetir, tidak pernah dari LLM.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz, process

LEVEL = {2: "prov", 5: "kab", 8: "kec", 13: "desa"}
DEPTH = {"prov": 1, "kab": 2, "kec": 3, "desa": 4}
REL_TUJUAN = {"LOCATED_IN", "EVACUATED_TO", "DEPLOYED_TO"}
_PENANDA = [  # (pola awalan, tingkat petunjuk)
    (r"kabupaten|kab", "kab"), (r"kota|kodya", "kota"), (r"kecamatan|kec", "kec"),
    (r"desa|ds|kelurahan|kel|nagari|gampong", "desa"), (r"provinsi|prov", "prov"),
]
_PREFIX_NAMA = re.compile(r"^(?:kabupaten administrasi|kota administrasi|kabupaten|kota|daerah khusus ibukota|"
                          r"daerah istimewa|provinsi)\s+", re.I)


def norm(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s.lower().replace("-", " "))
    return re.sub(r"\s+", " ", s).strip()


def pisah_penanda(seg: str) -> tuple[str | None, str]:
    """'Kec. Gubug' -> ('kec', 'gubug'); tanpa penanda -> (None, norm)."""
    t = seg.strip()
    for pola, lv in _PENANDA:
        m = re.match(rf"^(?:{pola})\.?\s+(.+)$", t, re.I)
        if m:
            return lv, norm(m.group(1))
    return None, norm(t)


class Gazetir:
    def __init__(self, sql: Path, abbrev: Path | None = None, titik: Path | None = None):
        self.titik: dict[str, tuple[float, float]] = {}
        if titik and Path(titik).exists():
            for r in csv.DictReader(open(titik, encoding="utf-8")):
                self.titik[r["kode"]] = (float(r["lat"]), float(r["lon"]))
        self.nama: dict[str, str] = {}
        self.jenis: dict[str, str] = {}              # kode -> prov|kabupaten|kota|kec|desa
        self.idx: dict[str, dict[str, list[str]]] = {lv: defaultdict(list) for lv in DEPTH}
        for line in open(sql, encoding="utf-8"):
            m = re.match(r"\('([\d.]+)','(.*)'\)[,;]", line)
            if not m:
                continue
            kode, nama = m.group(1), m.group(2).replace("''", "'").strip()
            lv = LEVEL.get(len(kode))
            if lv is None:
                continue
            self.nama[kode] = nama
            if lv == "kab":
                self.jenis[kode] = "kota" if nama.lower().startswith("kota") else "kabupaten"
            else:
                self.jenis[kode] = lv
            keys = {norm(_PREFIX_NAMA.sub("", nama)), norm(nama)}
            if lv == "prov":
                keys |= {"dki jakarta"} if "jakarta" in nama.lower() else set()
                keys |= {"diy", "di yogyakarta"} if "yogyakarta" in nama.lower() else set()
            for k in keys:
                if k and kode not in self.idx[lv][k]:
                    self.idx[lv][k].append(kode)
        self.singkatan: dict[str, str] = {}
        if abbrev and abbrev.exists():
            for r in csv.DictReader(open(abbrev, encoding="utf-8")):
                self.singkatan[norm(r["singkatan"])] = norm(r["nama_resmi"])
        self.nama_kunci = {lv: list(d) for lv, d in self.idx.items()}

    def path(self, kode: str) -> list[str]:
        """Kode induk dari provinsi ke bawah, termasuk kode itu sendiri."""
        return [kode[:n] for n in (2, 5, 8, 13) if n <= len(kode) and kode[:n] in self.nama]

    def kandidat(self, hint: str | None, nm: str) -> list[str]:
        """Semua kode bernama nm; hint membatasi tingkat. Fuzzy hanya prov/kab/kec, nama > 5 huruf."""
        nm = self.singkatan.get(nm, nm)
        levels = {"prov": ["prov"], "kab": ["kab"], "kota": ["kab"], "kec": ["kec"], "desa": ["desa"]}.get(hint or "", list(DEPTH))
        hasil: list[str] = []
        for lv in levels:
            hasil += self.idx[lv].get(nm, [])
        if hint == "kab":
            hasil = [k for k in hasil if self.jenis[k] == "kabupaten"] or hasil
        elif hint == "kota":
            hasil = [k for k in hasil if self.jenis[k] == "kota"] or hasil
        if not hasil and len(nm) > 5:
            for lv in levels:
                if lv == "desa":
                    continue
                for cand, skor, _ in process.extract(nm, self.nama_kunci[lv], scorer=fuzz.ratio, score_cutoff=92, limit=3):
                    hasil += self.idx[lv][cand]
        return list(dict.fromkeys(hasil))


def _segmen(loc: dict) -> list[tuple[str | None, str, str]]:
    """-> [(hint, nama_ternormalisasi, asal)] dari teks lokasi (pisah koma) + slot terisi + wilayah_dugaan."""
    segs: list[tuple[str | None, str, str]] = []
    teks = loc.get("teks") or ""
    teks = re.sub(r"\(([^)]*)\)", r", \1", teks)                # "Bima ( NTB)" -> "Bima , NTB"
    for s in re.split(r",|;|\bdan\b|&", teks):
        s = s.strip()
        if s:
            hint, nm = pisah_penanda(s)
            if nm:
                segs.append((hint, nm, "teks"))
    ada = {nm for _, nm, _ in segs}
    for slot, hint in (("provinsi", "prov"), ("kab_kota", None), ("kecamatan", "kec"), ("desa", "desa")):
        if loc.get(slot):
            h, nm = pisah_penanda(str(loc[slot]))
            if nm not in ada:
                segs.append((hint if h is None else h, nm, "slot")); ada.add(nm)
    for slot, v in (loc.get("wilayah_dugaan") or {}).items():
        hint = {"provinsi": "prov", "kecamatan": "kec", "desa": "desa"}.get(slot)
        h, nm = pisah_penanda(str(v))
        if nm not in ada:
            segs.append((hint if h is None else h, nm, "dugaan")); ada.add(nm)
    return list(dict.fromkeys(segs))


def _induk_bersama(kodes: list[str]) -> str | None:
    """Kode induk administratif (provinsi/kab/kec) yang dimiliki semua kode, terdalam."""
    for n in (8, 5, 2):
        if all(len(k) > n and k[:n] == kodes[0][:n] for k in kodes):
            return kodes[0][:n]
    return None


def resolusi_lokasi(loc: dict, gaz: Gazetir, konteks: set[str] | None = None) -> dict:
    segs = _segmen(loc)
    cand: list[tuple[int, str]] = []                            # (indeks segmen, kode)
    for i, (hint, nm, _) in enumerate(segs):
        for k in gaz.kandidat(hint, nm):
            cand.append((i, k))
    # satu sebutan yang cocok dengan wilayah DAN anak wilayahnya (Tabanan = kab, juga kecamatan): pilih yang lebih luas,
    # kecuali penanda tingkatnya tertulis (Kec. Tabanan)
    cand = [(i, k) for i, k in cand
            if segs[i][0] is not None or not any(i2 == i and k != k2 and k.startswith(k2) for i2, k2 in cand)]
    if not cand:
        return {"status": "unresolved", "kode_hasil": "U_NOT_IN_GAZ", "k_kandidat": 0}
    skor: dict[str, tuple[int, int]] = {}
    for i, k in cand:
        cakupan = {i} | {j for j, k2 in cand if j != i and k2 != k and k.startswith(k2) and k2 in gaz.nama
                         and len(k2) in (2, 5, 8)}
        skor[k] = (len(cakupan), 0)                              # cakupan terbanyak; seri tidak dipecah dengan menebak tingkat
    terbaik = max(skor.values())
    top = [k for k, v in skor.items() if v == terbaik]
    metode = "exact_hierarki" if terbaik[0] > 1 else "exact"
    if len(top) > 1 and konteks:                                # pemecah seri: wilayah lokasi lain di tweet yang sama
        saring = [k for k in top if any(k.startswith(c) for c in konteks)]
        if saring and len(saring) < len(top):
            top, metode = saring, "konteks_tweet"
    kand = [{"kode": k, "nama": gaz.nama[k], "path": [gaz.nama[p] for p in gaz.path(k)]} for k in top[:5]]
    if len(top) > 1:
        induk = _induk_bersama(top)
        if induk is None:
            return {"status": "unresolved", "kode_hasil": "U_WIL_AMBIG", "k_kandidat": len(top), "kandidat": kand,
                    "perlu_llm": len(top) <= 5}                # 2-5 kandidat: bahan langkah pemilihan LLM (belum dikerjakan)
        k, metode, kode_hasil = induk, "fallback_induk", "R_FALLBACK"
        alasan = "kab_kota_ambigu" if len({LEVEL[len(x)] for x in top}) == 1 and LEVEL[len(top[0])] == "kab" else "wilayah_ambigu_induk"
    else:
        k, kode_hasil, alasan = top[0], "R_OK", None
    lv = LEVEL[len(k)]
    sumber = {segs[i][2] for i, kk in cand if kk == k or k.startswith(kk)}
    t = gaz.titik.get(k)
    catatan = ([] if t else ["koordinat_belum_ada"]) + (["detail_belum_diresolusi"] if loc.get("detail") else [])
    return {"status": "resolved", "kode_hasil": kode_hasil, "alasan": alasan, "path": "B",
            "gazetteer_id": f"kemendagri:{k}", "level_admin": lv, "nama_resmi": gaz.nama[k],
            "jenis_wilayah": gaz.jenis[k], "admin_path": gaz.path(k), "admin_nama": [gaz.nama[p] for p in gaz.path(k)],
            "metode": metode, "dasar": sorted(sumber), "k_kandidat": len(top), "kandidat": kand if len(top) > 1 else None,
            "perlu_llm": 2 <= len(top) <= 5 and kode_hasil == "R_OK",
            "lat": t[0] if t else None, "lon": t[1] if t else None,
            "presisi_koordinat": "titik_pusat_wilayah" if t else None, "catatan": catatan}


def resolusi_record(rec: dict, gaz: Gazetir, osm=None) -> tuple[dict, list[dict]]:
    """Menambah kotak `resolution` pada tiap lokasi. -> (record, baris_log)."""
    log: list[dict] = []
    tujuan = {r["to"] for r in rec.get("relations", []) if r.get("type") in REL_TUJUAN}
    hasil: dict[str, dict] = {}
    for loc in rec.get("location", []):
        if loc.get("luar_negeri"):
            hasil[loc["id"]] = {"status": "skipped", "kode_hasil": "S_FOREIGN"}
        elif loc["id"] not in tujuan:
            hasil[loc["id"]] = {"status": "skipped", "kode_hasil": "S_NO_REL"}
    for loc in rec.get("location", []):                         # lintasan 1: tanpa konteks
        if loc["id"] not in hasil:
            hasil[loc["id"]] = resolusi_lokasi(loc, gaz)
    konteks = {c for r in hasil.values() if r.get("status") == "resolved" and r.get("k_kandidat") == 1
               for c in r["admin_path"][:2]}                   # provinsi dan kab/kota lokasi lain yang sudah pasti
    for loc in rec.get("location", []):                         # lintasan 2: ulang yang ambigu dengan konteks
        if hasil[loc["id"]].get("kode_hasil") == "U_WIL_AMBIG":
            hasil[loc["id"]] = resolusi_lokasi(loc, gaz, konteks)
    if osm is not None and osm.ada:                              # jalur detail (OSM lokal)
        from .osm import hasil_osm, kueri_detail
        def _kons():
            return tuple(sorted({c for r in hasil.values() if r.get("status") == "resolved" and r.get("k_kandidat") == 1
                                 for c in r["admin_path"][-1:]})) or None
        for lintasan in (1, 2):                                  # lintasan 2: ulang yang ambigu dengan wilayah/kecamatan lokasi lain
          kons = _kons()
          for loc in rec.get("location", []):
              r = hasil[loc["id"]]
              if lintasan == 2 and r.get("kode_hasil") != "U_DETAIL_AMBIG":
                  continue
              q = kueri_detail(loc)
              if not q or r.get("status") == "skipped":
                  continue
              if r.get("kode_hasil") in ("U_NOT_IN_GAZ", "U_DETAIL_AMBIG"):                      # jalur D
                  rows = osm.cari(q)
                  if len(rows) > 1 and kons:
                      sar = osm.cari(q, kons)
                      if sar:
                          rows, met = sar, "osm_exact_konteks_tweet"
                      else:
                          met = "osm_exact"
                  else:
                      met = "osm_exact"
                  if len(rows) == 1:
                      hasil[loc["id"]] = hasil_osm(rows, met)
                  elif len(rows) > 1:
                      hasil[loc["id"]] = {"status": "unresolved", "kode_hasil": "U_DETAIL_AMBIG", "k_kandidat": len(rows),
                                          "kandidat": [{"id": f"osm:{x['tipe_osm']}/{x['osm_id']}", "nama": x["nama"], "jenis": x["jenis"],
                                                        "kode_kec": x["kode_kec"], "tipe_osm": x["tipe_osm"], "osm_id": x["osm_id"],
                                                        "lat": x["lat"], "lon": x["lon"]} for x in rows[:5]],
                                          "perlu_llm": len(rows) <= 5}
                  else:
                      r["catatan"] = (r.get("catatan") or []) + ["osm_tidak_ditemukan"]
              elif r.get("status") == "resolved" and loc.get("detail") and r.get("level_admin") != "detail":   # jalur C
                  rows = osm.cari(q, tuple(r["admin_path"][-1:]))
                  if len(rows) == 1:
                      hasil[loc["id"]] = hasil_osm(rows, "osm_exact_di_bawah_wilayah", r)
                  elif len(rows) > 1:
                      r["catatan"] = [c for c in r["catatan"] if c != "detail_belum_diresolusi"] + ["detail_ambigu_di_wilayah"]
                  else:
                      r["catatan"] = [c for c in r["catatan"] if c != "detail_belum_diresolusi"] + ["detail_tidak_ditemukan_di_osm"]
    for loc in rec.get("location", []):
        r = hasil[loc["id"]]
        loc["resolution"] = r
        log.append({"tweet_id": rec["tweet_id"], "loc_id": loc["id"], "teks": loc.get("teks"),
                    "kode": r["kode_hasil"], "status": r["status"],
                    "hasil": r.get("gazetteer_id", ""), "level": r.get("level_admin", ""),
                    "k": r.get("k_kandidat", ""), "metode": r.get("metode", "")})
    return rec, log
