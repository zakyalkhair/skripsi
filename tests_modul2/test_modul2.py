import json

import pandas as pd

from modul2 import extract as X
from modul2 import schema as S
from modul2.validate import find_span, parse_json, petakan_jabatan, validate, _jabatan_default

TWEET = ("Banjir merendam Ds. Ngroto, Kec. Gubug, Grobogan sejak Selasa (12/3). 85 rumah terendam. "
         "BPBD Grobogan evakuasi warga. Gempa M5,2 juga terasa.")


def _out(**k):
    o = S.kosong()
    o.update(k)
    return json.dumps(o)


def _kode(log):
    return {x["kode"] for x in log}


def test_parse_json_fence_and_noise():
    assert parse_json('```json\n{"a":1}\n```') == {"a": 1}
    assert parse_json('jawaban: {"a": 2} selesai') == {"a": 2}
    assert parse_json("bukan json") is None


def test_find_span_variants():
    assert find_span("Kec. Gubug", TWEET)[2] == "exact"
    assert find_span("kec. gubug", TWEET)[2] == "case"
    assert find_span("Kec.  Gubug", TWEET)[2] == "space"
    assert find_span("Banjir Demak", "Waspada #BanjirDemak hari ini") is not None
    assert find_span("Pangkalan Bun", TWEET) is None


def test_find_span_punct_ok_but_joined_list_rejected():
    # v3: tanda baca/spasi berbeda masih cocok ...
    t = "banjir bandang di Bima ( NTB) kemarin"
    sp = find_span("Bima (NTB)", t)
    assert sp is not None and sp[2] == "punct" and t[sp[0]:sp[1]].startswith("Bima")
    # ... tetapi gabungan dua tempat yang dipisah kata lain tidak boleh cocok
    t2 = "Tim ke Mencirim, Binjai Timur, dan mendatangi rumah. Posko di Medan, Langkat."
    assert find_span("Binjai Timur, Medan, Langkat", t2) is None
    assert find_span("Medan, Langkat", t2) is not None


def test_validate_good_and_bad():
    raw = _out(
        event_mention=[{"id": "E1", "jenis": "banjir", "subtipe": "banjir_bandang_x", "faktualitas": "lampau",
                        "tipe_laporan": "laporan", "waktu_teks": "sejak Selasa (12/3)", "magnitudo": 5.2},
                       {"id": "E2", "jenis": "gempa", "magnitudo": 5.2, "faktualitas": "terjadi"},
                       {"id": "E3", "jenis": None}],
        location=[{"id": "L1", "teks": "Ds. Ngroto, Kec. Gubug, Grobogan", "provinsi": "Jawa Tengah",
                   "kab_kota": "Grobogan", "kecamatan": "Gubug", "desa": "Ngroto"},
                  {"id": "L2", "teks": "Pangkalan Bun"}],
        affected_object=[{"id": "A1", "kelas": "rumah", "status": "terendam", "jumlah": "85", "satuan": "unit",
                          "lokasi": "L1"},
                         {"id": "A2", "kelas": "rumah", "status": "meninggal", "jumlah": 1},
                         {"id": "A3", "kelas": "manusia", "status": "mengungsi", "lokasi": "L2"}],
        humanitarian_need=[{"id": "N1", "kategori": "air", "status": "demanded"},
                           {"id": "N2", "kategori": "makanan", "status": "needed"}],
        organization=[{"id": "O1", "nama": "BPBD Grobogan"}],
        relations=[{"type": "LOCATED_IN", "from": "E1", "to": "L1"}, {"type": "LOCATED_IN", "from": "E1", "to": "L1"},
                   {"type": "AFFECTED", "from": "E1", "to": "A1"}, {"type": "ORIGINATES_FROM", "from": "O1", "to": "L1"},
                   {"type": "AFFECTED", "from": "L1", "to": "A1"}, {"type": "DEPLOYED_TO", "from": "O1", "to": "L1",
                                                                     "aksi": "evakuasi"}])
    out, log = validate("1", TWEET, raw)
    kode = _kode(log)
    assert [m["jenis"] for m in out["event_mention"]] == ["banjir", "gempabumi"]
    e1 = out["event_mention"][0]
    assert e1["subtipe"] is None and "faktualitas" not in e1 and e1["tipe_laporan"] is None
    assert "W_FAKTUALITAS_DIHAPUS" in kode
    assert e1["magnitudo"] is None  # bukan gempa
    assert out["event_mention"][1]["magnitudo"] == 5.2  # "5,2" tertulis
    loc = out["location"][0]
    assert loc["provinsi"] is None and loc["kab_kota"] is None and loc["start"] == TWEET.find("Ds.")
    assert loc["kecamatan"] == "Gubug" and loc["desa"] == "Ngroto"      # ada penanda "Kec." / "Ds."
    assert loc["wilayah_dugaan"] == {"kab_kota": "Grobogan"}            # tanpa penanda -> dugaan
    assert len(out["location"]) == 1
    assert [a["id"] for a in out["affected_object"]] == ["A1", "A3"]
    assert out["affected_object"][0]["jumlah"] == 85 and out["affected_object"][1]["lokasi"] is None
    assert out["humanitarian_need"][0]["kategori"] == "lainnya" and len(out["humanitarian_need"]) == 1
    assert {"E_JENIS_NULL", "W_ENUM_SYNONYM", "E_SPAN_NOT_FOUND", "E_ENUM_COMBO", "W_SLOT_UNSUPPORTED",
            "W_SLOT_TANPA_PENANDA", "E_ENUM_REL", "E_REL_DOMAIN", "W_REL_DUP", "W_LOKASI_DANGLING", "W_ORPHAN",
            "E_ENUM_STATUS_NEED"} <= kode
    assert len(out["relations"]) == 3


def test_validate_parse_fail():
    out, log = validate("2", TWEET, "maaf saya tidak bisa")
    assert out["validasi"]["status"] == "failed" and log[0]["kode"] == "E_PARSE"


# ---- v3: cakupan jenis
def test_v3_jenis_di_luar_cakupan_dibuang_bukan_galat():
    t = "Gempa M7,1 memicu tsunami di Kab. Nusa Barat. Kekeringan juga melanda."
    raw = _out(event_mention=[{"id": "E1", "jenis": "gempabumi"}, {"id": "E2", "jenis": "tsunami"},
                              {"id": "E3", "jenis": "kekeringan", "subtipe": "kekeringan_pertanian"},
                              {"id": "E4", "jenis": "gelombang_pasang_abrasi"}])
    out, log = validate("3", t, raw)
    assert [m["jenis"] for m in out["event_mention"]] == ["gempabumi"]
    assert sum(x["kode"] == "W_JENIS_DI_LUAR_CAKUPAN" for x in log) == 3
    assert not [x for x in log if x["kode"] == "E_ENUM_JENIS"]


# ---- v3: kelas dampak Juklak
def test_v3_kelas_juklak_objek_dan_status():
    t = "Sembilan rumah terdampak, satu warung rusak, jembatan putus, wisata terendam, 7 warga meninggal."
    raw = _out(event_mention=[{"id": "E1", "jenis": "erupsi", "subtipe": "banjir_lahar"}],
               affected_object=[
                   {"id": "A1", "kelas": "rumah", "status": "terdampak", "jumlah": 9, "satuan": "unit"},
                   {"id": "A2", "kelas": "sosial_ekonomi", "objek": "kios_toko", "status": "rusak", "jumlah": 1},
                   {"id": "A3", "kelas": "prasarana_vital", "objek": "jembatan", "status": "terganggu"},
                   {"id": "A4", "kelas": "lainnya", "status": "terendam"},
                   {"id": "A5", "kelas": "manusia", "status": "meninggal", "jumlah": 7, "satuan": "jiwa"},
                   {"id": "A6", "kelas": "pelayanan_dasar", "objek": "jembatan", "status": "rusak"},
                   {"id": "A7", "kelas": "orang", "status": "luka"},
                   {"id": "A8", "kelas": "lahan_pertanian", "status": "terendam"}],
               relations=[{"type": "AFFECTED", "from": "E1", "to": f"A{i}"} for i in range(1, 9)])
    out, log = validate("4", t, raw)
    ao = {a["id"]: a for a in out["affected_object"]}
    assert len(ao) == 8
    assert ao["A6"]["objek"] is None and "W_ENUM_OBJEK" in _kode(log)       # jembatan bukan objek pelayanan_dasar
    assert ao["A7"]["kelas"] == "manusia" and ao["A8"]["kelas"] == "sosial_ekonomi" and ao["A8"]["objek"] == "lahan"
    assert "W_KELAS_SINONIM" in _kode(log) and not [x for x in log if x["kode"].startswith("E_")]
    assert S.kombinasi_sah("manusia", "meninggal") and not S.kombinasi_sah("rumah", "meninggal")


# ---- v3: slot wilayah hanya dengan kata penanda
def test_v3_slot_wilayah_butuh_penanda():
    t = "Banjir di Dusun Sumberlangsep, Desa Jugosari, Kecamatan Candipuro, Lumajang dan 45 km Tenggara KAB-GARUT-JABAR."
    raw = _out(location=[
        {"id": "L1", "teks": "Dusun Sumberlangsep, Desa Jugosari, Kecamatan Candipuro, Lumajang",
         "kab_kota": "Lumajang", "kecamatan": "Candipuro", "desa": "Jugosari", "detail": "Dusun Sumberlangsep"},
        {"id": "L2", "teks": "45 km Tenggara KAB-GARUT-JABAR", "kab_kota": "GARUT", "provinsi": "JABAR"}])
    out, log = validate("5", t, raw)
    l1, l2 = out["location"]
    assert (l1["kecamatan"], l1["desa"], l1["kab_kota"]) == ("Candipuro", "Jugosari", None)
    assert l1["wilayah_dugaan"] == {"kab_kota": "Lumajang"} and l1["detail"] == "Dusun Sumberlangsep"
    assert l2["kab_kota"] == "GARUT" and l2["provinsi"] is None and l2["wilayah_dugaan"] == {"provinsi": "JABAR"}


def test_v3_lokasi_kata_umum_dan_angka():
    t = "Banjir bandang di wilayah Bima ( NTB). 6 RT dan 1 Ruas Jalan di Jakarta terendam."
    raw = _out(location=[{"id": "L1", "teks": "wilayah Bima ( NTB)"},
                         {"id": "L2", "teks": "6 RT dan 1 Ruas Jalan di Jakarta"}])
    out, log = validate("6", t, raw)
    assert out["location"][0]["teks"] == "Bima ( NTB)" and "W_LOKASI_KATA_UMUM" in _kode(log)
    assert "W_LOKASI_ANGKA" in _kode(log)


# ---- v3: lembaga
def test_v3_lembaga_nama_orang_jabatan_dan_aksi():
    t = ("Kepala BNPB, Letjen TNI Suharyanto meresmikan jembatan. Plt. Ketua DPW PSI Sumut, Bang Sahat menyalurkan "
         "paket pangan. Lurah Selagalas hadir. Bang Hasanul ikut. Menurut BMKG hujan berlanjut.")
    raw = _out(
        event_mention=[{"id": "E1", "jenis": "banjir"}],
        humanitarian_need=[{"id": "N1", "kategori": "makanan", "item": "paket pangan", "status": "supplied"}],
        organization=[{"id": "O1", "nama": "Kepala BNPB, Letjen TNI Suharyanto"},
                      {"id": "O2", "nama": "Plt. Ketua DPW PSI Sumut, Bang Sahat"},
                      {"id": "O3", "nama": "Lurah Selagalas"},
                      {"id": "O4", "nama": "Bang Hasanul"},
                      {"id": "O5", "nama": "BMKG"}],
        relations=[{"type": "HANDLES", "from": "O2", "to": "N1", "aksi": "menyalurkan"},
                   {"type": "REQUIRES", "from": "E1", "to": "N1"}])
    out, log = validate("7", t, raw)
    orgs = {o["id"]: o for o in out["organization"]}
    assert "O4" not in orgs and "W_NAMA_ORANG_DIBUANG" in _kode(log)
    assert orgs["O1"]["nama"] == "Kepala BNPB" and orgs["O1"]["nama_lembaga"] == "BNPB" and orgs["O1"]["dari_jabatan"]
    assert orgs["O2"]["nama_lembaga"] == "DPW PSI Sumut"
    assert orgs["O3"]["nama_lembaga"] == "Kelurahan Selagalas"
    assert orgs["O5"]["dari_jabatan"] is False and orgs["O5"]["nama_lembaga"] == "BMKG"
    tanpa_aksi = {x["entitas"] for x in log if x["kode"] == "W_ORG_TANPA_AKSI"}
    assert tanpa_aksi == {"O1", "O3", "O5"} and "W_NAMA_ORANG_DIPOTONG" in _kode(log)


def test_v3_pemetaan_jabatan():
    d = _jabatan_default()
    assert petakan_jabatan("Petugas Pos Pengamatan Gunung Semeru", d) == (True, "Pos Pengamatan Gunung Semeru")
    assert petakan_jabatan("Bupati Agam", d) == (True, "Pemerintah Kabupaten Agam")
    assert petakan_jabatan("Presiden", d) == (True, "Presiden RI")   # keputusan 17 Okt: dicatat apa adanya
    assert petakan_jabatan("Presiden Direktur PT X", d) == (True, None)
    assert petakan_jabatan("BPBD Demak", d) == (False, None)


# ---- v3: petunjuk wilayah
def test_v3_petunjuk_wilayah():
    t = "#InfoBanjirTNG Jalan Raden Saleh, Karang Tengah terendam banjir sore ini."
    raw = _out(event_mention=[{"id": "E1", "jenis": "banjir"}],
               location=[{"id": "L1", "teks": "Jalan Raden Saleh, Karang Tengah", "detail": "Jalan Raden Saleh, Karang Tengah"}],
               petunjuk_wilayah=[{"id": "P1", "teks": "#InfoBanjirTNG"}, "#TidakAda"],
               relations=[{"type": "LOCATED_IN", "from": "E1", "to": "L1"}])
    out, log = validate("8", t, raw)
    assert [p["teks"] for p in out["petunjuk_wilayah"]] == ["#InfoBanjirTNG"]
    assert out["petunjuk_wilayah"][0]["asal"] == "tagar"
    assert "W_PETUNJUK_TIDAK_DITEMUKAN" in _kode(log) and not [x for x in log if x["kode"].startswith("E_")]


# ---- v3: penanda relasi hilang
def test_v3_penanda_lokasi_tanpa_relasi():
    t = "banjir bandang di wilayah Bima"
    base = dict(event_mention=[{"id": "E1", "jenis": "banjir"}], location=[{"id": "L1", "teks": "Bima"}])
    _, log = validate("9", t, _out(**base))
    assert "W_LOKASI_TANPA_RELASI" in _kode(log)
    _, log2 = validate("9", t, _out(**base, relations=[{"type": "LOCATED_IN", "from": "E1", "to": "L1"}]))
    assert "W_LOKASI_TANPA_RELASI" not in _kode(log2)
    _, log3 = validate("9", t, _out(event_mention=[{"id": "E1", "jenis": "banjir"}]))   # tanpa lokasi: tidak ditandai
    assert "W_LOKASI_TANPA_RELASI" not in _kode(log3)


# ---- contoh few-shot dan prompt
def test_fewshot_v3_clean():
    ab = X.load_abbrev()
    rows = X.load_fewshot(versi="v3")
    assert len(rows) >= 12
    for ex in rows:
        out, log = validate("fs", ex["tweet"], json.dumps(ex["output"]), ab)
        bad = [x for x in log if x["kode"].startswith("E_") or x["kode"] in (
            "W_SLOT_UNSUPPORTED", "W_SLOT_TANPA_PENANDA", "W_REL_DUP", "W_EPISENTRUM_TANDA", "W_SLOT_PREFIX",
            "W_ORPHAN", "W_LOKASI_TANPA_RELASI", "W_JENIS_DI_LUAR_CAKUPAN", "W_KELAS_SINONIM", "W_ENUM_OBJEK",
            "W_LOKASI_ANGKA", "W_LOKASI_KATA_UMUM", "W_JABATAN_TANPA_PEMETAAN", "W_NAMA_ORANG_DIPOTONG")]
        assert not bad, (ex["tweet"][:40], bad)


def test_system_prompt_v3_terisi():
    s = X.build_system(versi="v3")
    assert "GEO_SINGKATAN" not in s and "Jateng=Jawa Tengah" in s
    for kunci in ("petunjuk_wilayah", "Pengandaian", "BERBUAT", "diperkirakan"):
        assert kunci in s


class FakeClient:
    model = "palsu"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, max_tokens):
        self.calls.append(max_tokens)
        content, fr = self.replies.pop(0)
        return {"content": content, "finish_reason": fr, "prompt_tokens": 3000, "completion_tokens": 200,
                "durasi_s": 10.0, "prompt_s": 1.0, "gen_s": 9.0}


def test_extract_tiers_and_checkpoint(tmp_path):
    rows = [{"tweet_id": "1", "text_raw": TWEET, "created_at": "2025-07-01"},
            {"tweet_id": "2", "text_raw": "x", "created_at": "2025-07-02"}]
    c = FakeClient([('{"event_mention":[', "length"), (_out(), "stop"), ("rusak", "stop"), (_out(), "stop")])
    out = tmp_path / "raw.jsonl"
    X.run(rows, c, out, "sys", [], [1024, 4096], "pX", 2000, log=lambda s: None)
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    assert recs[0]["tahap"] == 2 and recs[0]["status"] == "ok" and c.calls[:2] == [1024, 4096]
    assert recs[1]["panggilan"] == 2 and recs[1]["status"] == "ok"
    c2 = FakeClient([])
    X.run(rows, c2, out, "sys", [], [1024, 4096], "pX", 2000, log=lambda s: None)
    assert c2.calls == []
    r = X.ringkas_waktu(out, 2000)
    assert r["n"] == 2 and r["estimasi_2000_tweet_jam"] > 0


def test_load_input_filters(tmp_path):
    df = pd.DataFrame({"tweet_id": [1, 2, 3], "text_raw": ["a", "b", None], "created_at": ["x"] * 3,
                       "label": ["informatif", "noninformatif", "informatif"], "is_representatif": [True, True, True]})
    p = tmp_path / "h.parquet"
    df.to_parquet(p)
    rows = X.load_input(p, None, False)
    assert [r["tweet_id"] for r in rows] == ["1"]


# ---- perbaikan v2 yang masih berlaku
def test_v2_fixes_from_real_cases():
    t = "Dahsyatnya banjir bandang di Kabupaten Aceh Tamiang khususnya Kecamatan Kejuruan Muda."
    raw = _out(event_mention=[{"id": "E1", "jenis": "banjir_bandang", "faktualitas": "terjadi"}],
               location=[{"id": "L1", "teks": "Kabupaten Aceh Tamiang", "kab_kota": "Kab. Aceh Tamiang"}],
               relations=[{"type:": "LOCATED_IN", "from": "E1", "to": "L1"}])
    out, log = validate("1", t, raw)
    k = _kode(log)
    assert out["event_mention"][0]["jenis"] == "banjir" and out["event_mention"][0]["subtipe"] == "banjir_bandang"
    assert "W_SUBTIPE_SEBAGAI_JENIS" in k and "W_REL_KEY_FIX" in k and len(out["relations"]) == 1
    assert out["location"][0]["kab_kota"] == "Aceh Tamiang" and "W_SLOT_PREFIX" in k


def test_v3_abbrev_provinsi_tanpa_penanda_jadi_dugaan():
    ab = X.load_abbrev()
    t = "Erupsi di Kecamatan Wulanggitang, Kabupaten Flores Timur, Nusa Tenggara Timur."
    raw = _out(location=[{"id": "L1", "teks": "Kecamatan Wulanggitang, Kabupaten Flores Timur, Nusa Tenggara Timur",
                          "provinsi": "NTT", "kab_kota": "Flores Timur"}])
    out, log = validate("2", t, raw, ab)
    loc = out["location"][0]
    assert loc["kab_kota"] == "Flores Timur" and loc["provinsi"] is None
    assert loc["wilayah_dugaan"] == {"provinsi": "NTT"}
    assert not [x for x in log if x["kode"] == "W_SLOT_UNSUPPORTED"]


def test_v2_episentrum_sign_and_text():
    t = "Info Gempa Mag:2.8, Lok:7.3 LS - 106.40 BT (38 km BaratDaya KAB-SUKABUMI-JABAR), Kedlmn: 37 Km"
    raw = _out(event_mention=[{"id": "E1", "jenis": "gempabumi", "faktualitas": "terjadi", "magnitudo": 2.8,
                               "kedalaman_km": 37, "episentrum": {"lat": 7.3, "lon": 106.4}}])
    out, log = validate("3", t, raw)
    assert out["event_mention"][0]["episentrum"] == {"lat": -7.3, "lon": 106.4}
    raw2 = _out(event_mention=[{"id": "E1", "jenis": "gempabumi", "episentrum": {"lat": 0.82, "lon": 127.77}}])
    out2, _ = validate("4", t, raw2)
    assert out2["event_mention"][0]["episentrum"] is None


def test_v3_objek_lainnya_dan_juklak():
    from modul2.schema import objek_sah, KELAS_LAMA
    assert objek_sah("lainnya", "wisata") and objek_sah("lainnya", "ternak")
    assert not objek_sah("sosial_ekonomi", "ternak")        # ternak tidak ada di Juklak 7/2023
    assert KELAS_LAMA["ternak"] == ("lainnya", "ternak")


def test_v6_pangkas_teks_lokasi_tanpa_menambah_teks():
    from modul2.validate import _pangkas_lokasi
    t = "Angin kencang melanda Lumajang, Jawa Timur, merusak rumah di Dusun Kotokan, Desa Jatiroto, rusak berat."
    c, sp = _pangkas_lokasi("Dusun Kotokan, Desa Jatiroto, Lumajang, Jawa Timur", t)
    assert c == "Dusun Kotokan, Desa Jatiroto" and t[sp[0]:sp[1]].startswith("Dusun Kotokan")
    assert _pangkas_lokasi("Kota Atlantis, Provinsi Mu", t) is None      # tidak ada bagian yang tertulis
    assert _pangkas_lokasi("Desa", t) is None                            # kata penanda saja tidak diterima
    raw = _out(event_mention=[{"id": "E1", "jenis": "banjir"}],
               location=[{"id": "L1", "teks": "Konda, Provinsi Sulawesi Tenggara"}],
               relations=[{"type": "LOCATED_IN", "from": "E1", "to": "L1"}])
    out, log = validate("9", "Kebakaran lahan padam di Konda pagi ini", raw)
    assert out["location"][0]["teks"] == "Konda" and "W_SPAN_DIPANGKAS" in _kode(log) and "E_REL_DANGLING" not in _kode(log)
