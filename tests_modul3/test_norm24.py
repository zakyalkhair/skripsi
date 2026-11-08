from datetime import date
from modul3.zona import zona_provinsi, waktu_lokal
from modul3.norm24 import parse_waktu, pecah_record

REF = date(2025, 12, 7)  # Minggu


def test_zona():
    assert zona_provinsi("52") == "WITA" and zona_provinsi("91") == "WIT" and zona_provinsi("32") == "WIB"


def test_lintas_tengah_malam():
    assert waktu_lokal("2025-12-06 20:30:00+00:00", "WIB").date() == date(2025, 12, 7)
    assert waktu_lokal("2025-12-06 20:30:00+00:00", "WITA").hour == 4


def test_tanggal_mutlak():
    assert parse_waktu("Sabtu, 6 Desember 2025", REF) == ([date(2025, 12, 6)], "pasti", "teks")
    assert parse_waktu("Minggu (06/07/2025)", REF)[0] == [date(2025, 7, 6)]
    assert parse_waktu("Kamis, 27 November pukul 17.26 WIB", REF)[0] == [date(2025, 11, 27)]


def test_rentang():
    d, k, _ = parse_waktu("Kamis (4/12/2025) hingga 6 Desember 2025", REF)
    assert k == "rentang" and d[0] == date(2025, 12, 4) and d[-1] == date(2025, 12, 6)


def test_relatif():
    assert parse_waktu("Selasa kemarin", REF)[0] == [date(2025, 12, 2)]
    assert parse_waktu("kemarin", REF)[0] == [date(2025, 12, 6)]
    assert parse_waktu("Senin sore", REF)[0] == [date(2025, 12, 1)]
    assert parse_waktu("sore ini", REF)[1] == "pasti"
    assert parse_waktu(None, REF) == ([REF], "pasti", "unggah")


def _loc(i, kode, path):
    return {"id": i, "resolution": {"status": "resolved", "admin_path": path, "admin_nama": ["P", "K"] + ["x"] * (len(path) - 2)}}


def test_pecah_dua_kab():
    rec = {"tweet_id": "1", "created_at": "2025-12-06 03:00:00+00:00", "text_raw": "t",
           "event_mention": [{"id": "E1", "jenis": "banjir", "tipe_laporan": "kejadian"}],
           "location": [_loc("L1", 0, ["52", "52.71"]), _loc("L2", 0, ["52", "52.01"])],
           "affected_object": [{"id": "A1", "lokasi": "L1"}, {"id": "A2", "lokasi": "L2"}, {"id": "A3", "lokasi": None}],
           "humanitarian_need": [],
           "relations": [{"type": "LOCATED_IN", "from": "E1", "to": "L1"}, {"type": "LOCATED_IN", "from": "E1", "to": "L2"},
                         {"type": "AFFECTED", "from": "E1", "to": "A1"}, {"type": "AFFECTED", "from": "E1", "to": "A2"},
                         {"type": "AFFECTED", "from": "E1", "to": "A3"}]}
    m = pecah_record(rec)
    assert [x["mention_id"] for x in m] == ["1_E1_52.71", "1_E1_52.01"]
    assert m[0]["objek_ids"] == ["A1"] and m[1]["objek_ids"] == ["A2"]   # A3 tak dilekatkan
    assert m[0]["zona"] == "WITA"


def test_prov_saja_dan_tanpa_lokasi():
    base = {"tweet_id": "2", "created_at": "2025-12-06 03:00:00+00:00", "event_mention": [{"id": "E1", "jenis": "banjir"}],
            "affected_object": [], "humanitarian_need": [], "text_raw": ""}
    r1 = dict(base, location=[_loc("L1", 0, ["52"])], relations=[{"type": "LOCATED_IN", "from": "E1", "to": "L1"}])
    assert pecah_record(r1)[0]["status_pecah"] == "prov_saja"
    r2 = dict(base, location=[], relations=[])
    assert pecah_record(r2)[0]["status_pecah"] == "tanpa_lokasi"


def test_di_luar_periode():
    rec = {"tweet_id": "3", "created_at": "2025-06-02 03:00:00+00:00", "text_raw": "", "location": [],
           "event_mention": [{"id": "E1", "jenis": "banjir", "waktu_teks": "per 31 Desember 2024"}],
           "affected_object": [], "humanitarian_need": [], "relations": []}
    assert pecah_record(rec)[0]["di_luar_periode"] is True


def test_rentang_tahun_eksplisit_lebih_depan_dari_unggah():
    d, k, _ = parse_waktu("Kamis (4/12/2025) hingga 6 Desember 2025", date(2025, 12, 5))
    assert d == [date(2025, 12, 4), date(2025, 12, 6)]
