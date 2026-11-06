import json
from pathlib import Path

from modul2 import pilih
from modul2.resolve import Gazetir, resolusi_record

SQL = """INSERT INTO wilayah (kode, nama)
VALUES
('33','Jawa Tengah'),
('33.01','Kabupaten Cilacap'),
('33.01.01','Dayeuhluhur'),
('33.01.01.2001','Kalipenggung'),
('35','Jawa Timur'),
('35.08','Kabupaten Lumajang'),
('35.08.18','Randuagung'),
('35.08.18.2005','Kalipenggung');
"""


class Palsu:
    model = "palsu"

    def __init__(self, jawab):
        self.jawab, self.n = jawab, 0

    def chat(self, msgs, max_tokens):
        self.n += 1
        if isinstance(self.jawab, Exception):
            raise self.jawab
        return {"content": self.jawab, "durasi_s": 0.1}


def _siapkan(tmp_path):
    f = tmp_path / "w.sql"; f.write_text(SQL, encoding="utf-8")
    gaz = Gazetir(f)
    rec = {"tweet_id": "1", "text_raw": "Banjir di Kalipenggung, warga mengungsi",
           "location": [{"id": "L1", "teks": "Kalipenggung", "luar_negeri": False}],
           "relations": [{"type": "LOCATED_IN", "from": "E1", "to": "L1"}]}
    rec, _ = resolusi_record(rec, gaz)
    p = tmp_path / "res.jsonl"; p.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    return gaz, rec, p


def _jalan(tmp_path, jawab, **kw):
    gaz, rec, p = _siapkan(tmp_path)
    out, raw, lg = tmp_path / "o.jsonl", tmp_path / "raw.jsonl", tmp_path / "l.csv"
    c = Palsu(jawab)
    ringkas = pilih.jalankan(p, out, raw, lg, gaz, c, **kw)
    return gaz, c, ringkas, json.loads(out.read_text(encoding="utf-8").splitlines()[0]), raw


def test_parse():
    assert pilih.parse_jawaban('{"pilihan":"b","alasan":"x"}', 2) == ("dipilih", "B")
    assert pilih.parse_jawaban('{"pilihan":"C"}', 2)[0] == "invalid"
    assert pilih.parse_jawaban('{"pilihan":"tidak_dapat_ditentukan"}', 2)[0] == "tidak_dapat_ditentukan"
    assert pilih.parse_jawaban("ngawur", 2)[0] == "invalid"
    assert pilih.parse_jawaban(None, 2)[0] == "invalid"


def test_urutan_acak_tetap_per_lokasi(tmp_path):
    gaz, rec, _ = _siapkan(tmp_path)
    loc = rec["location"][0]
    a = pilih.susun_pesan(rec, loc, gaz)[1]
    assert a == pilih.susun_pesan(rec, loc, gaz)[1]
    assert {pilih.kunci(c) for c in a} == {"33.01.01.2001", "35.08.18.2005"}


def test_pilih_wilayah_jadi_r_ok_dengan_nama_dari_gazetir(tmp_path):
    gaz, rec, _ = _siapkan(tmp_path)
    kand = pilih.susun_pesan(rec, rec["location"][0], gaz)[1]
    huruf = "ABCDE"[[pilih.kunci(c) for c in kand].index("35.08.18.2005")]
    _, c, ringkas, out, _ = _jalan(tmp_path, json.dumps({"pilihan": huruf, "alasan": "x"}))
    r = out["location"][0]["resolution"]
    assert r["kode_hasil"] == "R_OK" and r["gazetteer_id"] == "kemendagri:35.08.18.2005"
    assert r["metode"] == "llm_pilih_kandidat" and r["llm_dipakai"] and r["status"] == "resolved"
    assert ringkas["dipanggil"] == 1 and c.n == 1


def test_tidak_dapat_ditentukan(tmp_path):
    _, _, _, out, _ = _jalan(tmp_path, '{"pilihan":"tidak_dapat_ditentukan","alasan":"tidak ada petunjuk"}')
    r = out["location"][0]["resolution"]
    assert r["kode_hasil"] == "U_AMBIG_LLM" and r["status"] != "resolved"


def test_jawaban_tidak_sah(tmp_path):
    _, _, _, out, _ = _jalan(tmp_path, "saya pilih Jawa")
    assert out["location"][0]["resolution"]["kode_hasil"] == "U_LLM_INVALID"


def test_galat_jaringan_tidak_mengubah_dan_dicatat(tmp_path):
    _, _, _, out, _ = _jalan(tmp_path, RuntimeError("ollama mati"))
    r = out["location"][0]["resolution"]
    assert r["kode_hasil"] == "U_WIL_AMBIG" and "llm_galat" in r["catatan"]


def test_dry_run_tanpa_panggil(tmp_path):
    gaz, rec, p = _siapkan(tmp_path)
    c = Palsu("x"); pesan = []
    pilih.jalankan(p, tmp_path / "o", tmp_path / "r", tmp_path / "l", gaz, c, dry_run=True, log=pesan.append)
    assert c.n == 0 and not (tmp_path / "o").exists() and "Kalipenggung" in pesan[0]


def test_lanjut_dari_checkpoint(tmp_path):
    gaz, rec, p = _siapkan(tmp_path)
    out, raw, lg = tmp_path / "o.jsonl", tmp_path / "raw.jsonl", tmp_path / "l.csv"
    pilih.jalankan(p, out, raw, lg, gaz, Palsu('{"pilihan":"A","alasan":"x"}'))
    c2 = Palsu("jangan dipanggil")
    pilih.jalankan(p, out, raw, lg, gaz, c2)
    assert c2.n == 0
