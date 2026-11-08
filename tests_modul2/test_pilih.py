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


# --- petunjuk wilayah dari nama lembaga (8 Nov 2026) ---------------------------------------------------------------
SQL_ORG = """INSERT INTO wilayah (kode, nama)
VALUES
('32','Jawa Barat'),
('32.01','Kabupaten Bogor'),
('32.01.05','Cibinong'),
('32.03','Kabupaten Cianjur'),
('32.03.20','Cibinong'),
('32.71','Kota Bogor'),
('33','Jawa Tengah'),
('33.21','Kabupaten Demak'),
('33.76','Kota Pekalongan'),
('33.26','Kabupaten Pekalongan');
"""


def _gaz_org(tmp_path):
    f = tmp_path / "o.sql"; f.write_text(SQL_ORG, encoding="utf-8")
    a = tmp_path / "ab.csv"; a.write_text("singkatan,nama_resmi\nJabar,Jawa Barat\n", encoding="utf-8")
    return Gazetir(f, a)


def _rec_org(*nama):
    return {"tweet_id": "9", "text_raw": "x", "organization": [{"id": f"O{i}", "nama": n} for i, n in enumerate(nama)]}


def test_petunjuk_lembaga_dengan_penanda(tmp_path):
    gaz = _gaz_org(tmp_path)
    assert pilih.petunjuk_lembaga(_rec_org("BPBD Kab. Bogor"), gaz) == ["BPBD Kab. Bogor = Kabupaten Bogor (Jawa Barat)"]
    assert pilih.petunjuk_lembaga(_rec_org("Damkar Kota Bogor"), gaz) == ["Damkar Kota Bogor = Kota Bogor (Jawa Barat)"]


def test_petunjuk_lembaga_tanpa_penanda_dan_singkatan(tmp_path):
    gaz = _gaz_org(tmp_path)
    assert pilih.petunjuk_lembaga(_rec_org("BPBD Demak"), gaz) == ["BPBD Demak = Kabupaten Demak (Jawa Tengah)"]
    assert pilih.petunjuk_lembaga(_rec_org("Pemprov Jabar"), gaz) == ["Pemprov Jabar = Jawa Barat"]


def test_petunjuk_lembaga_ambigu_atau_tidak_ada_dilewati(tmp_path):
    gaz = _gaz_org(tmp_path)
    # "Bogor" cocok kabupaten dan kota -> ambigu; "Pekalongan" juga; lembaga nasional tidak punya wilayah
    assert pilih.petunjuk_lembaga(_rec_org("BPBD Bogor", "Polres Pekalongan", "BNPB", "Basarnas"), gaz) == []
    assert pilih.petunjuk_lembaga({"tweet_id": "1", "text_raw": "x"}, gaz) == []


def test_petunjuk_lembaga_tidak_menebak_bila_penanda_tidak_cocok(tmp_path):
    gaz = _gaz_org(tmp_path)
    assert pilih.petunjuk_lembaga(_rec_org("BPBD Kab. Atlantis"), gaz) == []
    assert pilih.petunjuk_lembaga(_rec_org("BPBD Kab. Pekalongan"), gaz) == ["BPBD Kab. Pekalongan = Kabupaten Pekalongan (Jawa Tengah)"]


def test_pesan_memuat_petunjuk_lembaga_sebagai_petunjuk_lemah(tmp_path):
    gaz = _gaz_org(tmp_path)
    rec = {"tweet_id": "9", "text_raw": "Banjir Cibinong, BPBD Kab. Bogor kerahkan perahu",
           "location": [{"id": "L1", "teks": "Cibinong", "luar_negeri": False}],
           "relations": [{"type": "LOCATED_IN", "from": "E1", "to": "L1"}],
           "organization": [{"id": "O1", "nama": "BPBD Kab. Bogor"}]}
    rec, _ = resolusi_record(rec, gaz)
    rec["organization"] = [{"id": "O1", "nama": "BPBD Kab. Bogor"}]
    msgs, kand = pilih.susun_pesan(rec, rec["location"][0], gaz)
    u = msgs[1]["content"]
    assert "Wilayah lembaga yang bertindak (petunjuk lemah, bukan lokasi kejadian): BPBD Kab. Bogor = Kabupaten Bogor (Jawa Barat)" in u
    assert "Lokasi lain di unggahan yang sudah pasti" not in u          # lembaga bukan lokasi pasti
    assert "petunjuk LEMAH" in msgs[0]["content"]
    # kandidat tetap sama dan nama lembaga tidak menambah/mengurangi kandidat
    assert {pilih.kunci(c) for c in kand} == {"32.01.05", "32.03.20"}


def test_pesan_tanpa_lembaga_tidak_berubah(tmp_path):
    gaz, rec, _ = _siapkan(tmp_path)
    u = pilih.susun_pesan(rec, rec["location"][0], gaz)[0][1]["content"]
    assert "Wilayah lembaga" not in u


def test_checkpoint_dari_prompt_lain_tidak_dilanjutkan(tmp_path):
    gaz, rec, p = _siapkan(tmp_path)
    out, raw, lg = tmp_path / "o.jsonl", tmp_path / "raw.jsonl", tmp_path / "l.csv"
    # jawaban lama tanpa hash prompt (atau hash lain) harus diulang, bukan dipakai
    raw.write_text(json.dumps({"key": "1|L1", "urutan": [], "content": '{"pilihan":"A","alasan":"lama"}',
                               "prompt_hash": "hashlain"}) + "\n", encoding="utf-8")
    c = Palsu('{"pilihan":"A","alasan":"baru"}')
    pilih.jalankan(p, out, raw, lg, gaz, c)
    assert c.n == 1
    baris = [json.loads(l) for l in raw.read_text(encoding="utf-8").splitlines()]
    assert baris[-1]["prompt_hash"] == pilih.PROMPT_HASH


def test_hash_prompt_pemilih_stabil_dan_berasal_dari_system():
    import hashlib
    assert len(pilih.PROMPT_HASH) == 12
    assert pilih.PROMPT_HASH == hashlib.sha256((pilih.SYSTEM + "\n" + pilih.FORMAT_VERSI).encode()).hexdigest()[:12]
