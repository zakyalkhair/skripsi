from modul3.konsol import Konsol, DE, atribut_de
from modul3 import ambang as AMB
from modul3.org_er import resolusi_organisasi, parse_org

_n = [0]


def M(jenis, tgl, kab="35.08", tipe="kejadian", text="", prov=None, **kw):
    _n[0] += 1
    m = {"mention_id": f"t{_n[0]}_E1", "tweet_id": f"t{_n[0]}", "jenis": jenis, "subtipe": None, "tipe_laporan": tipe,
         "kode_kab": kab, "kode_prov": prov or (kab.split(".")[0] if kab else None), "kab_nama": None, "status_pecah": "ok",
         "zona": "WIB", "tanggal_lokal": tgl, "tanggal_akhir": kw.pop("akhir", tgl), "ketepatan": kw.pop("ket", "pasti"),
         "sumber_tanggal": kw.pop("sumber", "teks"), "di_luar_periode": False, "lokasi_detail": [], "text": text,
         "waktu_teks": None, "magnitudo": None, "objek_ids": [], "kebutuhan_ids": []}
    m.update(kw); return m


def jalan(ms):
    DE.n = 0; k = Konsol(); k.jalankan(ms); return k


def test_banjir_jeda_3_hari_dan_lebih():
    k = jalan([M("banjir", "2025-12-01"), M("banjir", "2025-12-04"), M("banjir", "2025-12-09")])
    assert [len(d.anggota) for d in k.de] == [2, 1]


def test_banjir_penanda_lanjutan_7_hari():
    k = jalan([M("banjir", "2025-12-01"), M("banjir", "2025-12-07", text="banjir masih belum surut")])
    assert len(k.de) == 1 and k.de[0].anggota[1][1] == "penanda_lanjutan_7_hari"


def test_banjir_gelombang_baru_dan_beda_kab():
    k = jalan([M("banjir", "2025-12-01"), M("banjir", "2025-12-02", text="banjir kembali melanda"), M("banjir", "2025-12-02", kab="35.09")])
    assert len(k.de) == 3


def test_penanganan_14_hari():
    k = jalan([M("banjir", "2025-12-01"), M("banjir", "2025-12-14", tipe="penanganan"), M("banjir", "2025-12-30", tipe="penanganan")])
    assert len(k.de) == 2 and k.de[0].anggota[1][1] == "penanganan_14_hari"


def test_cuaca_ekstrem_tanggal_sama_dan_beda():
    k = jalan([M("cuaca_ekstrem", "2025-10-06"), M("cuaca_ekstrem", "2025-10-06"), M("cuaca_ekstrem", "2025-10-07")])
    assert [len(d.anggota) for d in k.de] == [2, 1]


def test_cuaca_ekstrem_tanpa_tanggal_h_min_1():
    k = jalan([M("cuaca_ekstrem", "2025-10-06"), M("cuaca_ekstrem", "2025-10-07", sumber="unggah")])
    assert len(k.de) == 1


def test_longsor_akibat_gempa():
    k = jalan([M("gempabumi", "2025-10-06"), M("tanah_longsor", "2025-10-06", text="longsor akibat gempa")])
    assert len(k.de) == 1 and "tanah_longsor" in k.de[0].tambahan


def test_gempa_lintas_wilayah_magnitudo():
    k = jalan([M("gempabumi", "2025-08-15", magnitudo=6.0), M("gempabumi", "2025-08-15", kab="53.01", magnitudo=6.2),
               M("gempabumi", "2025-08-15", kab="72.04", magnitudo=4.0)])
    assert [sorted(d.kab) for d in k.de] == [["35.08", "53.01"], ["72.04"]]


def test_gempa_susulan_masa_aktif_14_hari():
    k = jalan([M("gempabumi", "2025-08-15"), M("gempabumi", "2025-08-25")])
    assert len(k.de) == 1


def test_erupsi_episode_14_hari():
    k = jalan([M("erupsi", "2025-08-04", text="Gunung Semeru erupsi"), M("erupsi", "2025-08-15", text="Gn. Semeru awan panas"),
               M("erupsi", "2025-12-06", text="Gunung Semeru erupsi")])
    assert [len(d.anggota) for d in k.de] == [2, 1]


def test_karhutla_provinsi_dan_pulau_diabaikan():
    k = jalan([M("karhutla", "2025-07-03", kab="12.17"), M("karhutla", "2025-07-10", kab="12.01"), M("karhutla", "2025-08-20", kab="12.01"),
               M("karhutla", "2025-07-03", kab=None, prov=None)])
    assert [len(d.anggota) for d in k.de] == [2, 1] and len(k.tidak) == 1


def test_rentang_hanya_menempel():
    k = jalan([M("banjir", "2025-12-05"), M("banjir", "2025-12-01", akhir="2025-12-06", ket="rentang"),
               M("banjir", "2025-11-01", akhir="2025-11-05", ket="rentang")])
    assert len(k.de) == 1 and len(k.de[0].anggota) == 2 and len(k.tidak) == 1


def test_di_luar_periode_dan_tanpa_wilayah():
    k = jalan([M("banjir", "2024-12-31", di_luar_periode=True), M("banjir", "2025-12-01", kab=None, prov=None)])
    assert k.de == [] and len(k.tidak) == 2


def test_luas_satu_kandidat():
    k = jalan([M("banjir", "2025-12-01"), M("banjir", "2025-12-02", kab=None, prov="35")])
    assert len(k.de) == 1 and len(k.de[0].anggota) == 2


def test_majemuk_tipe_utama():
    a, b = M("banjir", "2025-12-01"), M("tanah_longsor", "2025-12-01")
    b["tweet_id"] = a["tweet_id"]
    k = jalan([a, b])
    assert len(k.de) == 1 and k.de[0].jenis == "banjir" and k.de[0].tambahan == {"tanah_longsor"}


def test_ambang_juklak():
    man = lambda st, j: {"kelas": "manusia", "status": st, "jumlah": j}
    assert AMB.is_bencana([[man("meninggal", 1)]])[0] == "ya"
    assert AMB.is_bencana([[man("luka", 49)]])[0] == "tidak"
    assert AMB.is_bencana([[man("mengungsi", 50)]])[0] == "ya"
    rumah = {"kelas": "rumah", "status": "rusak_berat", "jumlah": 5, "satuan": "unit"}
    assert AMB.is_bencana([[rumah]])[0] == "ya"
    assert AMB.is_bencana([[dict(rumah, status="terendam")]])[0] == "tidak"     # terendam/terdampak bukan rusak
    assert AMB.is_bencana([[{"kelas": "sosial_ekonomi", "status": "terendam", "jumlah": 1, "satuan": "ha"}]])[0] == "ya"
    assert AMB.is_bencana([[man("luka", 30)], [man("luka", 30)]])[0] == "tidak"   # per laporan
    assert AMB.is_bencana([[man("luka", 30)], [man("luka", 30)]], dict(AMB.KONFIG, mode="jumlah"))[0] == "ya"


def test_org_er():
    rows = [{"tweet_id": str(i), "org_id": "O1", "nama": n, "nama_lembaga": n} for i, n in
            enumerate(["BPBD Kabupaten Agam", "BPBD Kab. Agam", "BPBD Kota Padang", "TNI AU", "TNI"])]
    out, tab, _ = resolusi_organisasi(rows)
    nama = [r["nama_kanonik"] for r in out]
    assert nama[0] == nama[1] == "BPBD Kabupaten Agam" and nama[2] != nama[0] and nama[3] != nama[4]
    assert parse_org("BPBD Provinsi Aceh")["tingkat"] == "provinsi"
