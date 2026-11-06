from pathlib import Path

from modul2.resolve import Gazetir, pisah_penanda, resolusi_record

SQL = """INSERT INTO wilayah (kode, nama)
VALUES
('33','Jawa Tengah'),
('33.01','Kabupaten Cilacap'),
('33.01.01','Dayeuhluhur'),
('33.01.01.2001','Kalipenggung'),
('33.76','Kota Tegal'),
('33.28','Kabupaten Tegal'),
('51','Bali'),
('51.02','Kabupaten Tabanan'),
('51.02.05','Tabanan'),
('35','Jawa Timur'),
('35.08','Kabupaten Lumajang'),
('35.08.18','Randuagung'),
('35.08.18.2005','Kalipenggung'),
"""


def _gaz(tmp_path: Path) -> Gazetir:
    f = tmp_path / "w.sql"; f.write_text(SQL.rstrip(",\n") + ";\n", encoding="utf-8")
    return Gazetir(f)


def _rec(teks, **kw):
    loc = {"id": "L1", "teks": teks, "luar_negeri": False} | kw
    return {"tweet_id": "1", "location": [loc], "relations": [{"type": "LOCATED_IN", "from": "E1", "to": "L1"}]}


def _res(tmp_path, teks, **kw):
    rec, log = resolusi_record(_rec(teks, **kw), _gaz(tmp_path))
    return rec["location"][0]["resolution"]


def test_penanda():
    assert pisah_penanda("Kec. Gubug") == ("kec", "gubug") and pisah_penanda("Gubug")[0] is None


def test_hierarki_memecah_nama_kembar(tmp_path):
    r = _res(tmp_path, "Kalipenggung, Kecamatan Randuagung, Lumajang")
    assert r["gazetteer_id"] == "kemendagri:35.08.18.2005" and r["level_admin"] == "desa"


def test_nama_kembar_tanpa_induk_ambigu(tmp_path):
    r = _res(tmp_path, "Kalipenggung")
    assert r["kode_hasil"] == "U_WIL_AMBIG" and r["k_kandidat"] == 2 and r["perlu_llm"]


def test_kab_dan_kota_sama_nama_fallback_ke_induk(tmp_path):
    r = _res(tmp_path, "Tegal")
    assert r["kode_hasil"] == "R_FALLBACK" and r["gazetteer_id"] == "kemendagri:33" and r["alasan"] == "kab_kota_ambigu"


def test_penanda_tingkat_memilih(tmp_path):
    assert _res(tmp_path, "Kota Tegal")["gazetteer_id"] == "kemendagri:33.76"
    assert _res(tmp_path, "Kab. Tegal")["gazetteer_id"] == "kemendagri:33.28"


def test_kab_lebih_luas_bila_nama_sama_dengan_kecamatannya(tmp_path):
    assert _res(tmp_path, "Tabanan, Bali")["gazetteer_id"] == "kemendagri:51.02"
    assert _res(tmp_path, "Kec. Tabanan, Bali")["gazetteer_id"] == "kemendagri:51.02.05"


def test_tidak_ada_dan_dilewati(tmp_path):
    assert _res(tmp_path, "Atlantis")["kode_hasil"] == "U_NOT_IN_GAZ"
    assert _res(tmp_path, "Tegal", luar_negeri=True)["kode_hasil"] == "S_FOREIGN"
    rec = _rec("Tegal"); rec["relations"] = []
    rec, _ = resolusi_record(rec, _gaz(tmp_path))
    assert rec["location"][0]["resolution"]["kode_hasil"] == "S_NO_REL"


def test_koordinat_tidak_pernah_dari_llm(tmp_path):
    r = _res(tmp_path, "Kabupaten Lumajang", lat=1.0, lon=2.0)
    assert r["lat"] is None and r["lon"] is None


def test_titik_pusat_wilayah_terisi_dan_masuk_akal():
    from pathlib import Path
    from modul2.resolve import Gazetir, resolusi_lokasi
    base = Path(__file__).resolve().parent.parent / "data" / "gazetir"
    if not (base / "titik_wilayah.csv").exists():
        return
    gaz = Gazetir(base / "wilayah.sql", None, base / "titik_wilayah.csv")
    r = resolusi_lokasi({"id": "L1", "teks": "Kabupaten Tabanan, Bali", "luar_negeri": False}, gaz)
    assert r["status"] == "resolved" and r["presisi_koordinat"] == "titik_pusat_wilayah"
    assert -8.8 < r["lat"] < -8.2 and 114.8 < r["lon"] < 115.4


# ---- jalur detail (OSM lokal) ----
import csv as _csv

from modul2.osm import OsmIndex, norm_osm

_KOL = ["osm_id", "tipe_osm", "nama", "nama_norm", "jenis", "lat", "lon", "kode_kec", "panjang_km"]


def _osm(tmp_path, rows, dicari):
    f = tmp_path / "osm.csv"
    with open(f, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh); w.writerow(_KOL)
        for i, (nama, jenis, lat, lon, kec) in enumerate(rows, 1):
            w.writerow([i, "way", nama, norm_osm(nama), jenis, lat, lon, kec, ""])
    return OsmIndex.muat(f, {norm_osm(d) for d in dicari})


def _recd(locs, rel_to):
    return {"tweet_id": "9", "location": locs,
            "relations": [{"type": "LOCATED_IN", "from": "E1", "to": i} for i in rel_to]}


def test_norm_osm_alias_jalan():
    assert norm_osm("Jl. Lodan  Raya") == "jalan lodan raya"


def test_osm_jalur_d_unik(tmp_path):
    osm = _osm(tmp_path, [("Pelabuhan Sunda Kelapa", "pelabuhan", -6.122, 106.836, "31.72.05")], ["Pelabuhan Sunda Kelapa"])
    rec, _ = resolusi_record(_recd([{"id": "L1", "teks": "Pelabuhan Sunda Kelapa", "luar_negeri": False}], ["L1"]), _gaz(tmp_path), osm)
    r = rec["location"][0]["resolution"]
    assert r["status"] == "resolved" and r["gazetteer_id"] == "osm:way/1" and r["path"] == "D"
    assert (r["lat"], r["lon"]) == (-6.122, 106.836) and r["presisi_koordinat"] == "titik_fitur_osm"


def test_osm_jalur_d_ambigu_lalu_konteks_tweet(tmp_path):
    rows = [("Jalan Raya", "jalan", 1.0, 1.0, "51.02.05"), ("Jalan Raya", "jalan", 2.0, 2.0, "35.08.18")]
    osm = _osm(tmp_path, rows, ["Jalan Raya"])
    a = {"id": "L1", "teks": "Jalan Raya", "luar_negeri": False}
    r1 = resolusi_record(_recd([a], ["L1"]), _gaz(tmp_path), osm)[0]["location"][0]["resolution"]
    assert r1["kode_hasil"] == "U_DETAIL_AMBIG" and r1["k_kandidat"] == 2 and r1["perlu_llm"]
    b = {"id": "L2", "teks": "Kabupaten Tabanan", "luar_negeri": False}
    rec, _ = resolusi_record(_recd([dict(a), b], ["L1", "L2"]), _gaz(tmp_path), osm)
    r2 = rec["location"][0]["resolution"]
    assert r2["status"] == "resolved" and r2["lat"] == 1.0 and r2["metode"] == "osm_exact_konteks_tweet"


def test_osm_jalur_c_naik_atau_tetap_wilayah(tmp_path):
    osm = _osm(tmp_path, [("Jalan Gubug", "jalan", -8.4, 115.1, "51.02.05")], ["Jalan Gubug", "Jalan Hilang"])
    ada = {"id": "L1", "teks": "Jalan Gubug, Kecamatan Tabanan, Kabupaten Tabanan", "detail": "Jalan Gubug", "luar_negeri": False}
    tdk = {"id": "L2", "teks": "Jalan Hilang, Kecamatan Tabanan, Kabupaten Tabanan", "detail": "Jalan Hilang", "luar_negeri": False}
    rec, _ = resolusi_record(_recd([ada, tdk], ["L1", "L2"]), _gaz(tmp_path), osm)
    r1, r2 = rec["location"][0]["resolution"], rec["location"][1]["resolution"]
    assert r1["level_admin"] == "detail" and r1["path"] == "C" and r1["admin_path"][-1] == "51.02.05"
    assert r2["level_admin"] == "kec" and "detail_tidak_ditemukan_di_osm" in r2["catatan"]


def test_osm_tidak_ada_berkas_perilaku_lama(tmp_path):
    osm = OsmIndex.muat(tmp_path / "tidak_ada.csv", {"x"})
    rec, _ = resolusi_record(_recd([{"id": "L1", "teks": "Pelabuhan X", "luar_negeri": False}], ["L1"]), _gaz(tmp_path), osm)
    assert rec["location"][0]["resolution"]["kode_hasil"] == "U_NOT_IN_GAZ"


def test_osm_ruas_dan_jembatan_sama_kecamatan_digabung_dan_konteks_dari_lokasi_osm_lain(tmp_path):
    rows = [("Jalan Lodan Raya", "jalan", -6.130, 106.828, "31.72.05"), ("Jalan Lodan Raya", "jembatan", -6.129, 106.830, "31.72.05"),
            ("Jalan Lodan Raya", "jalan", -6.195, 106.895, "31.75.02"), ("Pelabuhan Sunda Kelapa", "pelabuhan", -6.122, 106.836, "31.72.05")]
    osm = _osm(tmp_path, rows, ["Jalan Lodan Raya", "Pelabuhan Sunda Kelapa"])
    a = {"id": "L1", "teks": "Jalan Lodan Raya", "luar_negeri": False}
    b = {"id": "L2", "teks": "Pelabuhan Sunda Kelapa", "luar_negeri": False}
    sendiri = resolusi_record(_recd([dict(a)], ["L1"]), _gaz(tmp_path), osm)[0]["location"][0]["resolution"]
    assert sendiri["kode_hasil"] == "U_DETAIL_AMBIG" and sendiri["k_kandidat"] == 2          # 3 baris -> 2 (jalan+jembatan Pademangan digabung)
    rec, _ = resolusi_record(_recd([a, b], ["L1", "L2"]), _gaz(tmp_path), osm)
    r = rec["location"][0]["resolution"]
    assert r["status"] == "resolved" and r["admin_path"][-1] == "31.72.05" and r["metode"] == "osm_exact_konteks_tweet"
