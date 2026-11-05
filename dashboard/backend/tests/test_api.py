"""Uji API mode file terhadap data contoh (kasus tepi dari spesifikasi)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def get(url, code=200):
    r = c.get(url)
    assert r.status_code == code, r.text
    return r.json()


def kab_row(j, kode):
    return next((r for r in j["kab"] if r["kode_kab"] == kode), None)


def test_agregat_menghitung_kejadian_unik():
    j = get("/api/kab-agregat")
    assert j["ringkasan"] == {"jumlah_kejadian": 15, "jumlah_laporan": 33, "jumlah_tweet": 31, "jumlah_kab": 7}
    assert kab_row(j, "3514")["jumlah_kejadian"] == 3  # dua banjir Bangil terpisah + karhutla
    assert sum(r["jumlah_kejadian"] for r in j["kab"]) == 15


def test_tweet_lintas_kab_dihitung_sekali():
    j = get("/api/kab-agregat?jenis=erupsi")
    # T01 melaporkan erupsi di Lumajang dan Malang: 7 laporan, 6 tweet unik
    assert j["ringkasan"]["jumlah_laporan"] == 7 and j["ringkasan"]["jumlah_tweet"] == 6


def test_filter_tanggal_memakai_irisan_interval_kejadian():
    j = get("/api/kab-agregat?dari=2026-01-13&sampai=2026-01-13")
    # DE01 (12–27 Jan) dan DE03 (12–15 Jan) beririsan walau tidak ada laporan tepat 13 Jan
    assert {r["kode_kab"] for r in j["kab"]} == {"3507", "3508"}
    assert j["ringkasan"]["jumlah_laporan"] == 0
    kartu = get("/api/kab/3508/kejadian?dari=2026-01-13&sampai=2026-01-13")["kejadian"]
    assert [k["event_id"] for k in kartu] == ["DE01"]
    assert kartu[0]["jumlah_laporan_periode"] == 0 and kartu[0]["jumlah_laporan_total"] == 5


def test_jenis_kosong_berbeda_dari_semua():
    assert get("/api/kab-agregat?jenis=")["ringkasan"]["jumlah_kejadian"] == 0
    assert get("/api/kab-agregat")["ringkasan"]["jumlah_kejadian"] == 15
    get("/api/kab-agregat?jenis=tsunami", 422)
    get("/api/kab-agregat?dari=2026-03-01&sampai=2026-01-01", 422)


def test_titik_unik_dan_banyak_jenis():
    t = {x["gazetteer_id"]: x for x in get("/api/kab/3579/titik")["titik"]}
    sb = t["contoh:desa/sumberbrantas"]
    assert sb["jenis"] == ["banjir", "cuaca", "longsor"] and sb["jumlah_laporan"] == 4
    assert len(t) == 2  # satu penanda per gazetteer_id
    j = get("/api/titik/contoh:desa/sumberbrantas/ringkasan")
    assert j["jumlah_laporan"] == 4 and j["jumlah_tweet"] == 3  # T14 melaporkan dua laporan
    assert {k["event_id"] for k in j["kejadian"]} == {"DE06", "DE07", "DE08"}


def test_gunung_lintas_kab_tidak_diduplikasi():
    malang = {x["gazetteer_id"]: x for x in get("/api/kab/3507/titik")["titik"]}
    sm = malang["contoh:gunung/semeru"]
    assert sm["di_luar_kab"] is True and sm["kode_kab_lokasi"] == "3508" and sm["nama_kab_lokasi"] == "Kab. Lumajang"
    j = get("/api/titik/contoh:gunung/semeru/ringkasan")
    assert {k["event_id"]: k["kode_kab"] for k in j["kejadian"]} == {"DE01": "3508", "DE03": "3507"}


def test_dampak_tanpa_atribusi_lokasi_tetap_di_tingkat_kejadian():
    j = get("/api/titik/contoh:desa/kalirejo/ringkasan")
    assert j["dampak_lokasi"] == []
    assert [(d["kelas"], d["jumlah"]) for d in j["dampak_tanpa_lokasi"]] == [("rumah", 12)]
    kartu = get("/api/kab/3507/kejadian")["kejadian"]
    cuaca = next(k for k in kartu if k["event_id"] == "DE05")
    assert cuaca["dampak"][0]["lokasi"] == [] and cuaca["kebutuhan"][0]["lokasi"] is None


def test_laporan_tingkat_kab_tidak_menjadi_titik():
    j = get("/api/kab/3509/titik")
    assert {x["gazetteer_id"] for x in j["titik"]} == {"contoh:kec/puger", "contoh:kec/panti"}
    assert j["laporan_tanpa_titik"] == 1  # laporan gempa tingkat kab tanpa titik pusat gempa


def test_histogram_mingguan_laporan_unik():
    j = get("/api/histogram")
    assert sum(w["total"] for w in j["minggu"]) == 33
    assert all(w["mulai"] for w in j["minggu"]) and len({w["mulai"] for w in j["minggu"]}) == len(j["minggu"])
    assert sum(w["total"] for w in get("/api/histogram?kab=3514&jenis=banjir")["minggu"]) == 5
    assert sum(w["total"] for w in get("/api/histogram?jenis=")["minggu"]) == 0


def test_validasi_dan_hanya_baca():
    get("/api/kab/35x8/titik", 422)
    get("/api/kab/9999/kejadian", 404)
    get("/api/titik/contoh:tidak-ada/ringkasan", 404)
    get("/api/titik/contoh%3Adesa%2Fsupiturang/ringkasan")  # id ter-encode
    for m in (c.post, c.put, c.delete):
        assert m("/api/kab-agregat").status_code == 405


def test_wilayah():
    j = get("/api/wilayah")
    assert len(j["kab"]) == 514 and sum(k["ada_data"] for k in j["kab"]) == 7
    assert j["dataset"]["contoh"] is True and j["dataset"]["label"] == "Data Contoh"


# --------------------------------------------------------------------------- berpusat-kejadian
def test_lokasi_mengelompokkan_fakta_per_kejadian():
    j = get("/api/titik/contoh:kec/bangil/ringkasan")
    ev = {k["event_id"]: k for k in j["kejadian"]}
    assert set(ev) == {"DE09", "DE10"}  # dua banjir terpisah di lokasi yang sama
    assert [(d["jumlah"], d["atribusi"]) for d in ev["DE09"]["dampak"]] == [(350, "lokasi_ini")]
    assert [(d["jumlah"], d["atribusi"]) for d in ev["DE10"]["dampak"]] == [(90, "lokasi_ini")]
    assert ev["DE09"]["dampak"][0]["sumber"] == [{"mention_id": "EM21", "tanggal_lokal": "2026-01-09", "tweet_ids": ["T19"]}]
    assert [n["item"] for n in ev["DE09"]["kebutuhan"]] == ["air bersih"] and ev["DE10"]["kebutuhan"] == []
    assert [o["nama_kanonik"] for o in ev["DE09"]["penanganan"]] == ["BPBD Kabupaten Pasuruan"]
    assert ev["DE10"]["penanganan"] == []


def test_atribusi_lokasi_ini_lain_dan_kejadian():
    sup = {k["event_id"]: k for k in get("/api/titik/contoh:desa/supiturang/ringkasan")["kejadian"]}["DE01"]
    atr = {d["id"]: (d["atribusi"], [l["nama"] for l in d["lokasi"]]) for d in sup["dampak"]}
    assert atr == {"AO01": ("lokasi_ini", ["Desa Supiturang"]), "AO02": ("lokasi_lain", ["Desa Sumberwuluh"])}
    kal = get("/api/titik/contoh:desa/kalirejo/ringkasan")["kejadian"][0]
    assert [(d["kelas"], d["jumlah"], d["atribusi"]) for d in kal["dampak"]] == [("rumah", 12, "kejadian")]
    assert [(n["item"], n["atribusi"]) for n in kal["kebutuhan"]] == [("terpal", "kejadian")]


def test_tujuan_evakuasi_terhubung_ke_kejadian():
    j = get("/api/titik/contoh:kec/candipuro/ringkasan")
    de01 = next(k for k in j["kejadian"] if k["event_id"] == "DE01")
    assert [x["relasi"] for x in de01["laporan"]] == ["evakuasi"]
    assert de01["evakuasi"][0]["tujuan"][0]["nama"] == "Kec. Candipuro"


def test_kartu_membawa_sumber_per_fakta():
    j = get("/api/kab/3508/kejadian")
    de01 = next(k for k in j["kejadian"] if k["event_id"] == "DE01")
    assert all(d["sumber"] and d["sumber"][0]["tweet_ids"] for d in de01["dampak"])
    assert {lap["mention_id"] for lap in de01["laporan"]} == {"EM01", "EM02", "EM03", "EM04", "EM05"}
    assert set(j["tweets"]) >= {"T01", "T02", "T05"}


# --------------------------------------------------------------------------- cakupan linimasa & provinsi
def test_histogram_tingkat_lokasi_dan_provinsi():
    sem = get("/api/histogram?lokasi=contoh:gunung/semeru")
    assert sem["cakupan"] == "lokasi" and sum(w["total"] for w in sem["minggu"]) == 3  # bukan seluruh Kab. Malang
    assert sum(w["total"] for w in get("/api/histogram?kab=3507")["minggu"]) == 6
    assert sum(w["total"] for w in get("/api/histogram?prov=35")["minggu"]) == 33
    assert sum(w["total"] for w in get("/api/histogram?prov=11")["minggu"]) == 0
    get("/api/histogram?lokasi=contoh:tidak-ada", 404)
    get("/api/histogram?prov=3x", 422)


def test_agregat_provinsi():
    assert get("/api/kab-agregat?prov=35")["ringkasan"] == get("/api/kab-agregat")["ringkasan"]
    assert get("/api/kab-agregat?prov=11")["ringkasan"]["jumlah_kejadian"] == 0
    get("/api/kab-agregat?prov=99", 404)


# --------------------------------------------------------------------------- ekspor
def test_ekspor_zip_ternormalisasi():
    import csv
    import io
    import json
    import zipfile

    r = c.get("/api/ekspor?kab=3514&jenis=banjir")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    man = json.loads(z.read("manifest.json"))
    assert man["filter"]["jenis"] == ["banjir"] and man["cakupan"]["kode_kab"] == "3514"
    assert any("bukan data resmi BNPB" in x for x in man["catatan"])
    rows = lambda n: list(csv.DictReader(io.StringIO(z.read(n).decode("utf-8-sig"))))
    assert {r["event_id"] for r in rows("kejadian.csv")} == {"DE09", "DE10"}  # karhutla tersaring
    dampak = {(r["event_id"], r["jumlah"]) for r in rows("dampak.csv")}
    assert dampak == {("DE09", "350"), ("DE10", "90")}  # tidak dijumlahkan
    assert z.read("kejadian.csv").startswith("﻿".encode())
    assert man["tabel"]["laporan"]["baris"] == 5
    get("/api/ekspor?jenis=", 404)


def test_sel_ekspor_mencegah_injeksi_formula():
    from app.main import _sel

    assert _sel("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert _sel("+62 812") == "'+62 812" and _sel("@user") == "'@user"
    assert _sel("1234567890123456789") == "1234567890123456789" and _sel(None) == ""
