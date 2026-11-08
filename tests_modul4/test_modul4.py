import json, os, re
import pytest
from modul4.llm import Hasil, ekstrak_json, pisah
from modul4 import laporan, qa, evaluasi as ev, korpus
from modul4.repo import MemRepo

DATA = "dev_2025/data/modul3"
pytestmark = pytest.mark.skipif(not os.path.exists(DATA + "/disaster_event.csv"), reason="jalankan python -m modul3 proses dulu")


class Palsu:
    """LLM tiruan: perilaku ditentukan dari isi prompt."""
    def __init__(self, mode="baik"): self.mode, self.pakai, self.panggilan = mode, {"panggilan": 0}, []
    def chat(self, pesan, json_mode=False, maks_token=None):
        sistem, user = pesan[0]["content"], pesan[1]["content"]; self.panggilan.append(sistem[:30])
        if sistem.startswith("Ubah pertanyaan"):
            t = user.lower()
            p = {"jenis": "banjir" if "banjir" in t else None, "wilayah": "Aceh Tamiang" if "aceh tamiang" in t else ("Narnia" if "narnia" in t else ("Sikka" if "sikka" in t else None)),
                 "tanggal_mulai": None, "tanggal_selesai": None, "info": "korban"}
            return Hasil(json.dumps(p), "palsu", "m", 10, 10)
        if sistem.startswith("Kamu menjawab"):
            ids = re.findall(r"\[(\d{6,})\]", user)
            return Hasil(f"Ada laporan terkait [{ids[0]}]." if ids else "Tidak ada informasi di data untuk pertanyaan ini.", "palsu", "m", 100, 20)
        if sistem.startswith("Kamu menyusun laporan"):
            f = json.loads(user); l = f["laporan"][0]
            kal = f"Banjir dilaporkan pada tanggal tersebut [{l['tweet_id']}]." if self.mode == "baik" else f"Korban 99999 orang [{l['tweet_id']}]."
            return Hasil(json.dumps({"kronologi": [{"tanggal": l["tanggal"], "kalimat": kal}], "kondisi_mutakhir": f"Masih ditangani [{l['tweet_id']}]."}), "palsu", "m", 50, 50)
        if sistem.startswith("Kamu penilai kesetiaan"): return Hasil(json.dumps({"klaim": [{"teks": "x", "didukung": 1}, {"teks": "y", "didukung": 0}]}), "palsu", "m")
        if sistem.startswith("Kamu penilai."): return Hasil(json.dumps({"pemenang": "A"}), "palsu", "m")
        return Hasil("tidak tahu", "palsu", "m")


@pytest.fixture(scope="module")
def repo(): return MemRepo(DATA)


def test_ekstrak_json_dan_spec():
    assert ekstrak_json('```json\n{"a": 1}\n``` selesai') == {"a": 1}
    assert pisah("groq:llama-3.3-70b-versatile") == ("groq", "llama-3.3-70b-versatile")
    with pytest.raises(ValueError): pisah("openai:gpt")


def test_korpus_lolos(repo, tmp_path):
    m = korpus.kunci(repo, str(tmp_path), "dev_2025/data/processed/extraction_resolved_filter200_v6pangkas.jsonl")
    assert m["lolos"] and m["n_tweet"] == 59 and len(m["hash_korpus"]) == 64


def test_laporan_valid_dan_kerangka(repo):
    de = max(repo.g["events"], key=lambda e: len(repo.anggota[e["event_id"]]))
    k = repo.kerangka(de["event_id"])
    r = laporan.buat_laporan(k, Palsu("baik"))
    assert r["valid"] and "## 10. Sumber" in r["markdown"] and "bukan data resmi" in r["markdown"]
    assert all(i in {x["tweet_id"] for x in k["laporan"]} for i in laporan.ids_sitasi(r["markdown"]))


def test_laporan_menolak_angka_karangan(repo):
    k = repo.kerangka(repo.g["events"][0]["event_id"])
    r = laporan.buat_laporan(k, Palsu("ngarang"))
    assert not r["valid"] and any("99999" in m for m in r["masalah"])
    assert "tidak lolos validasi" in r["markdown"] and "99999" not in r["markdown"]     # jatuh ke kutipan tweet


def test_qa_menjawab_dan_abstain(repo):
    L, w = Palsu(), qa.Wilayah()
    r = qa.tanya("Berapa korban banjir di Aceh Tamiang?", repo, L, w)
    assert not r["abstain"] and r["sitasi_valid"] is True and r["event_ids"]
    assert qa.tanya("Berapa korban banjir di Narnia?", repo, L, w)["abstain"]               # wilayah tak dikenal
    n = len(L.panggilan); r5 = qa.tanya("Berapa korban banjir di Sikka?", repo, L, w)
    assert r5["abstain"] and r5["jawaban"] == qa.TIDAK_ADA and len(L.panggilan) == n + 1       # tak ada DE -> tanpa panggilan jawaban


def test_evaluasi_ujung_ke_ujung(repo, tmp_path):
    soal = ev.buat_soal_draf(repo)
    assert {s["kelompok"] for s in soal} >= {"Q1", "Q3", "Q5"}
    L, w = Palsu(), qa.Wilayah()
    baris, ring = ev.evaluasi(soal[:6] + [s for s in soal if s["kelompok"] == "Q5"][:2], lambda q: qa.tanya(q, repo, L, w), L, L, str(tmp_path))
    assert ring["n_soal"] == 8 and os.path.exists(tmp_path / "evaluasi_qa.csv")
    assert ev.skor_nugget(qa.TIDAK_ADA, ["ABSTAIN"]) == 1.0 and ev.skor_nugget("terjadi pada 2025-12-02", ["2025-12-02"]) == 1.0
    assert ev.skor_nugget("ada 1.500 jiwa", ["1500"]) == 1.0


def test_judge_harus_beda():
    from modul4.__main__ import main
    with pytest.raises(SystemExit): main(["korpus", "--backend", "csv", "--gen", "groq:a", "--judge", "groq:a"])


def test_think_dibuang_dan_default_model():
    import re
    assert re.sub(r"<think>.*?</think>", "", "<think>x</think>jawab", flags=re.S).strip() == "jawab"
    from modul4 import __main__ as m
    import inspect
    src = inspect.getsource(m)
    assert "groq:qwen/qwen3.8-27b" in src and "groq:openai/gpt-oss-120b" in src


def test_provinsi_dan_default_antarmuka(repo):
    class P(Palsu):
        def chat(self, pesan, json_mode=False, maks_token=None):
            if pesan[0]["content"].startswith("Ubah pertanyaan"):
                return Hasil(json.dumps({"jenis": None, "wilayah": "Aceh", "info": "situasi"}), "palsu", "m")
            return super().chat(pesan, json_mode, maks_token)
    r = qa.tanya("Ada kejadian apa di Aceh?", repo, P(), qa.Wilayah())
    assert r["event_ids"], "nama provinsi harus menemukan kejadian di kabupatennya"
    class Q(Palsu):
        def chat(self, pesan, json_mode=False, maks_token=None):
            if pesan[0]["content"].startswith("Ubah pertanyaan"):
                return Hasil(json.dumps({"jenis": None, "wilayah": None, "info": "situasi"}), "palsu", "m")
            return super().chat(pesan, json_mode, maks_token)
    de = repo.g["events"][0]
    assert qa.tanya("Apa yang terjadi?", repo, Q(), qa.Wilayah(), default={"event_id": de["event_id"]})["event_ids"] == [de["event_id"]]
    kab = de["kode_wilayah"][0]
    assert de["event_id"] in qa.tanya("Apa yang terjadi?", repo, Q(), qa.Wilayah(), default={"kab": kab})["event_ids"] + [x for x in [de["event_id"]]]
