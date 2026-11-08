import json
import re

import pandas as pd
import pytest
from pydantic import ValidationError

from modul1 import filter_llm as fl
from modul1.io_utils import read_parquet, write_parquet
from modul1.schemas import INPUT_1_4_COLS, AturanCfg

BMKG = ("#Gempa Mag:4.6, 29-Aug-2026 23:32:11WIB, Lok:7.86LS, 120.36BT "
        "(84 km BaratLaut RUTENG-MANGGARAI-NTT), Kedlmn:19 Km #BMKG")
BMKG_KECIL = BMKG.replace("Mag:4.6", "Mag:2.3")
BMKG_NTB = ("#Gempa Mag:5.1, 18-Aug-2026 01:10:06WIB, Lok:8.10LS, 117.20BT "
            "(125 km TimurLaut SARINGI-NTB), Kedlmn:10 Km #BMKG")

TWEETS = {
    "101": BMKG,                                                   # aturan laporan_otomatis_gempa -> noninformatif
    "102": "BNPB: 105 orang meninggal akibat gempa M7,7 Flores, 179.037 warga mengungsi",  # LLM
    "103": "Ngapain sih nanyain MBG di depan korban gempa NTT?!",   # aturan topik_lain
    "104": "Ada yang tahu kabar jalan ke Ruteng hari ini?",           # tidak cocok aturan -> LLM
    "105": "Semoga saudara kita di NTT diberi kekuatan",            # aturan doa_tanpa_fakta
}
KE_LLM = ["102", "104"]


FAKTA = ['\\d', r'\b(meninggal|tewas|wafat|korban\s+jiwa|luka|hilang|tertimbun)',
         r'\b(mengungsi|pengungsi|pengungsian|posko|tenda)', r'\b(rusak|roboh|ambruk|runtuh|retak|hancur|putus)',
         r'\b(butuh|kebutuhan|kekurangan|minim|logistik|air\s+bersih|selimut|obat|sembako)',
         r'\b(susulan|tsunami|evakuasi|dievakuasi|sar\b|basarnas|bnpb|bpbd|bmkg)']


@pytest.fixture
def cfg(cfg):
    """Sejak 7 Okt 2026 config hanya memuat aturan positif (bmkg). Mekanisme aturan negatif tetap diuji
    dengan aturan uji di bawah (salinan aturan lama), tanpa memengaruhi config produksi."""
    cfg.filter_llm.aturan = list(cfg.filter_llm.aturan) + [
        AturanCfg(nama="topik_lain", label="noninformatif",
                  salah_satu=[r'\bmbg\b', r'makan\s+bergizi', r'\bkarnaval\b', r'\b17\s+agustus(an)?\b',
                              r'\bhut\s+(ri|ke)', r'\bkemerdekaan\b', r'\bpesta\b', r'\bkonser\b'], kecuali=FAKTA),
        AturanCfg(nama="doa_tanpa_fakta", label="noninformatif",
                  salah_satu=[r'\bsemoga\b', r'\bdoa\b', r'\bmendoakan\b', r'\bpray', r'turut\s+berduka', r'\bberduka\b',
                              r'ya\s*allah', 'innalillahi', r'\baa?mii?n\b', r'\btuhan\b', r'\bstay\s+safe\b', r'\bget\s+well\b'],
                  kecuali=FAKTA),
    ]
    return cfg


@pytest.fixture
def ready(cfg):
    df = pd.DataFrame({
        "tweet_id": list(TWEETS), "text_raw": list(TWEETS.values()),
        "created_at": pd.to_datetime(["2026-08-20T00:00:00Z"] * len(TWEETS), utc=True),
        "member_tweet_ids": [[t] for t in TWEETS], "cluster_size": [1] * len(TWEETS),
        "event_id": [["GP07"]] * len(TWEETS),
    })
    write_parquet(df, cfg.paths.input_1_4, INPUT_1_4_COLS)
    cfg.filter_llm.jeda_antar_permintaan_s = 0
    return cfg


def tweets_in(payload):
    """(id lokal, teks) dari pesan pengguna."""
    return re.findall(r'<tweet id="(\d+)">\n(.*?)\n</tweet>', payload["messages"][1]["content"], flags=re.DOTALL)


def sent_ids(client):
    by_text = {v: k for k, v in TWEETS.items()}
    return [by_text[t] for p in client.payloads for _, t in tweets_in(p)]


class FakeClient:
    """Meniru OpenAICompatClient.chat; `answer(id, teks)` -> label, atau None untuk dihilangkan."""

    def __init__(self, answer, errors=None):
        self.answer, self.errors = answer, list(errors or [])
        self.payloads = []

    def chat(self, payload):
        self.payloads.append(payload)
        if self.errors:
            raise self.errors.pop(0)
        hasil = [{"id": i, "label": lab} for i, t in tweets_in(payload)
                 if (lab := self.answer(i, t)) is not None]
        return json.dumps({"hasil": hasil}), {"total_tokens": 1234, "finish_reason": "stop"}


def by_text(i, t):
    return "informatif" if "BNPB" in t else "noninformatif"


# --------------------------------------------------------------------------- aturan regex
def rule_of(cfg, text, ev=("GP07",)):
    r = fl.first_rule(text, list(ev), fl.load_events(cfg.paths.kejadian), cfg.filter_llm.aturan)
    return (r.nama, r.label) if r else None


def test_laporan_otomatis_gempa_noninformatif_di_seluruh_wilayah(cfg):
    # 8 Nov: laporan otomatis berformat templat = noninformatif, dari daerah mana pun
    assert rule_of(cfg, BMKG) == ("laporan_otomatis_gempa", "noninformatif")
    assert rule_of(cfg, BMKG_NTB) == ("laporan_otomatis_gempa", "noninformatif")
    assert rule_of(cfg, BMKG_NTB, ev=("NAS-GP",)) == ("laporan_otomatis_gempa", "noninformatif")
    # tanpa pola "Gempa Mag: ... Lok:" -> bukan templat (ke LLM)
    assert rule_of(cfg, "Gempa Flores, BMKG catat 1.624 gempa susulan") is None


@pytest.mark.parametrize("mag", ["0.8", "2.3", "4.0", "4,0", "4.6", "5.1", "7.7", "10.0"])
def test_laporan_otomatis_gempa_berapa_pun_magnitudo_dan_dirasakan(cfg, mag):
    # 8 Nov: tanpa batas magnitudo dan tanpa pengecualian "Dirasakan"/MMI
    t = BMKG.replace("Mag:4.6", f"Mag:{mag}")
    assert rule_of(cfg, t) == ("laporan_otomatis_gempa", "noninformatif")
    assert rule_of(cfg, t + ", Dirasakan II-III MMI di Ruteng ::BMKG") == ("laporan_otomatis_gempa", "noninformatif")


def test_aturan_bmkg_kecil_bukan_templat_ke_llm(cfg):
    assert rule_of(cfg, "Gempa Mag: 3 kecil di Garut tanpa koordinat") is None   # tanpa "Lok:" bukan templat
    assert rule_of(cfg, "Gempa M3,2 mengguncang Ruteng, warga panik") is None


def test_syarat_wilayah_tetap_berfungsi_bila_dipakai(cfg):
    # mekanisme lama (alias wilayah) tetap benar bila suatu saat diaktifkan lagi
    assert not fl.mentions_region("gunung Kendeng", ["Ende"])  # alias harus kata utuh
    assert fl.mentions_region("(40 km ENDE-NTT)", ["Ende"])


@pytest.mark.parametrize("text,expected", [
    # topik lain tanpa fakta -> noninformatif
    ("Masyarakat Terdampak Gempa NTT, Ingin Program MBG dilanjutkan", ("topik_lain", "noninformatif")),
    ("NTT berduka tapi mereka tetap bikin karnaval nusantara di monas", ("topik_lain", "noninformatif")),
    # topik lain + fakta -> diserahkan ke LLM
    ("Prabowo di Nagekeo bahas MBG, padahal 105 orang meninggal", None),
    ("Gempa susulan saat upacara HUT RI, peserta berhamburan", None),
    # doa murni -> noninformatif; doa + fakta -> LLM
    ("Duka mendalam untuk saudara di NTT, semoga kuat 🙏", ("doa_tanpa_fakta", "noninformatif")),
    ("Ya Allah lindungi Flores", ("doa_tanpa_fakta", "noninformatif")),
    ("Semoga kuat, 68 orang meninggal dan ratusan luka", None),
    ("Semoga bantuan logistik segera sampai ke posko Riung", None),
    # bukan doa/topik lain -> LLM
    ("Update BNPB korban meninggal jadi 105 orang", None),
    ("Pura pura kerja", None),
])
def test_aturan_noninformatif_presisi_tinggi(cfg, text, expected):
    assert rule_of(cfg, text) == expected


def test_aturan_config_divalidasi():
    with pytest.raises(ValidationError):
        AturanCfg(nama="x", label="noninformatif")  # tanpa semua/salah_satu
    with pytest.raises(ValidationError):
        AturanCfg(nama="x", label="noninformatif", salah_satu=["(tidak ditutup"])  # regex rusak
    with pytest.raises(ValidationError):
        AturanCfg(nama="x", label="mungkin", salah_satu=["a"])


# --------------------------------------------------------------------------- permintaan & parse
def test_payload_berisi_konteks_nomor_lokal_dan_parameter(cfg):
    events = fl.load_events(cfg.paths.kejadian)
    p = fl.build_payload(["Gempa di Ende", "Doa untuk NTT"], ["GP07"], events, "SYS", cfg)
    assert p["model"] == "qwen2.5-cpu" and p["temperature"] == 0
    assert p["response_format"] == {"type": "json_object"} and "reasoning_effort" not in p
    assert p["messages"][0] == {"role": "system", "content": "SYS"}
    assert "Kejadian acuan" not in p["messages"][1]["content"] and "GP07" not in p["messages"][1]["content"]
    assert tweets_in(p) == [("1", "Gempa di Ende"), ("2", "Doa untuk NTT")]


def test_parse_labels_toleran_dan_ketat():
    assert fl.parse_labels('{"hasil":[{"id":"1","label":"informatif"},{"id":2,"label":"Noninformatif"}]}', 2) \
        == {1: "informatif", 2: "noninformatif"}
    assert fl.parse_labels('```json\n{"hasil":[{"id":"1","label":"informatif"}]}\n```', 1) == {1: "informatif"}
    assert fl.parse_labels('{"hasil":[{"id":"5","label":"informatif"},{"id":"1","label":"mungkin"}]}', 2) == {}
    assert fl.parse_labels("bukan json", 2) is None
    assert fl.parse_labels(None, 2) is None


def test_prompt_hash_berubah_bila_prompt_model_atau_provider_berubah(cfg):
    a = fl.prompt_hash("prompt", cfg)
    assert a == fl.prompt_hash("prompt", cfg) and a != fl.prompt_hash("prompt v2", cfg)
    cfg.filter_llm.base_url = "http://192.168.1.10:11434/v1"
    assert a != fl.prompt_hash("prompt", cfg)


def test_chunk_acak_berseed_tanpa_pengelompokan_kueri(ready):
    df = read_parquet(ready.paths.input_1_4)
    df.loc[df["tweet_id"] == "105", "event_id"] = pd.Series([["ER03", "GP07"]], index=df.index[df["tweet_id"] == "105"])
    a = [list(g["tweet_id"]) for _, g in fl.make_chunks(df, 2, seed=42)]
    b = [list(g["tweet_id"]) for _, g in fl.make_chunks(df.sample(frac=1, random_state=7), 2, seed=42)]
    assert a == b  # deterministik, tidak bergantung urutan masukan
    assert [len(x) for x in a] == [2, 2, 1] and sorted(sum(a, [])) == sorted(TWEETS)


# --------------------------------------------------------------------------- alur penuh
def test_run_hibrida_label_keluaran_dan_alur(ready):
    cfg = ready
    client = FakeClient(by_text)
    fl.run(cfg, client)
    assert sorted(sent_ids(client)) == KE_LLM  # yang ditangani aturan tidak dikirim

    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert len(out) == 5  # tidak ada baris hilang
    assert out["label_sumber"].to_dict() == {
        "101": "aturan:laporan_otomatis_gempa", "102": "llm", "103": "aturan:topik_lain", "104": "llm", "105": "aturan:doa_tanpa_fakta"}
    assert out["label"].to_dict() == {
        "101": "noninformatif", "102": "informatif", "103": "noninformatif", "104": "noninformatif",
        "105": "noninformatif"}
    assert out.loc["102", "llm_model"] == "qwen2.5-cpu" and out.loc["103", "llm_model"] is None
    assert sorted(read_parquet(cfg.paths.informatif)["tweet_id"]) == ["102"]
    alur = pd.read_csv(cfg.paths.alur_data).set_index("tahap")
    assert (alur.loc["filter informatif", "masuk"], alur.loc["filter informatif", "keluar"],
            alur.loc["filter informatif", "dibuang"]) == (5, 1, 4)
    assert "aturan:topik_lain/noninformatif=1" in alur.loc["filter informatif", "alasan"]
    assert alur.loc["Siap ke Modul 2", "masuk"] == 1

    client2 = FakeClient(by_text)
    fl.run(cfg, client2)
    assert client2.payloads == []  # semua sudah berlabel: tidak ada yang dikirim ulang


def test_tanpa_llm_memakai_label_default(ready):
    cfg = ready
    cfg.filter_llm.pakai_llm = False
    cfg.filter_llm.label_default = "noninformatif"
    client = FakeClient(by_text)
    fl.run(cfg, client)
    assert client.payloads == []
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert out.loc["102", "label"] == "noninformatif" and out.loc["102", "label_sumber"] == "default"
    assert out.loc["101", "label_sumber"] == "aturan:laporan_otomatis_gempa"


def test_jawaban_hilang_dikirim_ulang_dan_label_ok_tidak_ditimpa(ready):
    cfg = ready
    fl.run(cfg, FakeClient(lambda i, t: None if "Ruteng hari ini" in t else by_text(i, t)))
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    # dikirim ulang satu-satu, tetap hilang -> informatif dengan sumber 'gagal→informatif'
    assert out.loc["104", "label"] == "informatif" and out.loc["104", "label_sumber"] == "gagal→informatif"
    assert out.loc["104", "llm_status"] == "hilang_dari_jawaban"
    ulang = [r for r in fl.load_labels(cfg.paths.llm_labels) if r.get("percobaan") == "ulang_satu"]
    assert [r["tweet_id"] for r in ulang] == ["104"]

    client = FakeClient(by_text)
    fl.run(cfg, client)
    assert sent_ids(client) == ["104"]
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert out["label"].notna().all() and out.loc["104", "label"] == "noninformatif"


def test_429_singkat_dicoba_ulang_kuota_harian_berhenti_rapi(ready):
    cfg = ready
    cfg.filter_llm.tweet_per_permintaan = 1
    sleeps = []
    fl.run(cfg, FakeClient(by_text, errors=[fl.RateLimited(5)]), sleep_fn=sleeps.append)
    assert 5 in sleeps and read_parquet(cfg.paths.hasil_1_4)["label"].notna().all()

    cfg.paths.llm_labels.unlink()
    client = FakeClient(by_text, errors=[fl.RateLimited(3600)])  # kuota harian
    fl.run(cfg, client, sleep_fn=lambda s: None)
    assert len(client.payloads) == 1  # berhenti setelah permintaan pertama
    out = read_parquet(cfg.paths.hasil_1_4)
    assert (out["llm_status"] == "belum_dikirim").sum() == 2


def test_galat_server_dicatat_lalu_lanjut(ready):
    cfg = ready
    cfg.filter_llm.max_retry = 0
    fl.run(cfg, FakeClient(by_text, errors=[fl.ApiError("http_500:x", retryable=True)]), sleep_fn=lambda s: None)
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    recs = fl.load_labels(cfg.paths.llm_labels)
    assert any(r["status"] == "errored:http_500:x" for r in recs)  # galat dicatat
    # lalu dikirim ulang satu-satu dan berhasil
    assert out["label_sumber"].isin(["llm", "aturan:laporan_otomatis_gempa", "aturan:topik_lain", "aturan:doa_tanpa_fakta"]).all()


def test_limit_sampel_deterministik(ready):
    cfg = ready
    a = FakeClient(by_text)
    fl.run(cfg, a, limit=1)
    assert len(sent_ids(a)) == 1
    cfg.paths.llm_labels.unlink()
    b = FakeClient(by_text)
    fl.run(cfg, b, limit=1)
    assert sent_ids(b) == sent_ids(a)


def test_make_client_tanpa_kunci_memberi_pesan_jelas(cfg, monkeypatch):
    import logging

    monkeypatch.delenv("KUNCI_UJI", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    cfg.crawl.use_system_certs = False
    cfg.filter_llm.api_key_env = "KUNCI_UJI"  # penyedia API berkunci (hipotetis)
    with pytest.raises(RuntimeError, match="KUNCI_UJI"):
        fl.make_client(cfg, logging.getLogger("t"))
    cfg.filter_llm.api_key_env = None  # Ollama lokal: tanpa kunci
    assert fl.make_client(cfg, logging.getLogger("t")) is not None


# --------------------------------------------------------------------------- profil & perbandingan
def test_profil_menimpa_filter_llm_dan_akhiran_keluaran(cfg):
    from modul1.io_utils import apply_profil

    phash = fl.prompt_hash("p", cfg)
    labels, informatif = cfg.paths.llm_labels, cfg.paths.informatif
    apply_profil(cfg, "ollama")
    assert cfg.filter_llm.base_url == "http://localhost:11434/v1" and cfg.filter_llm.api_key_env is None
    assert cfg.filter_llm.aturan  # aturan regex tidak ikut hilang
    assert fl.prompt_hash("p", cfg) != phash
    assert cfg.paths.informatif.name == "informatif_ollama.parquet" and cfg.paths.informatif.parent == informatif.parent
    assert cfg.paths.hasil_1_4.name == "hasil_1_4_ollama.parquet" and cfg.paths.alur_data.name == "alur_data_ollama.csv"
    assert cfg.paths.llm_labels == labels  # label bersama agar bisa dibandingkan


def test_profil_tidak_dikenal_dan_kolom_salah(cfg):
    from modul1.io_utils import apply_profil
    from modul1.schemas import Config

    with pytest.raises(ValueError, match="tidak ada di profil_llm"):
        apply_profil(cfg, "tidakada")
    raw = cfg.model_dump()
    raw["profil_llm"] = {"x": {"modle": "a"}}
    with pytest.raises(ValidationError, match="kolom tidak dikenal"):
        Config.model_validate(raw)


def test_cohen_kappa():
    I, N = "informatif", "noninformatif"
    assert fl.cohen_kappa([I, I, N, N], [I, N, N, N]) == pytest.approx(0.5)
    assert fl.cohen_kappa([I, N], [I, N]) == 1
    assert fl.cohen_kappa([I, I], [I, I]) is None and fl.cohen_kappa([], []) is None


def test_bandingkan_dua_model(ready):
    cfg = ready
    fl.run(cfg, FakeClient(by_text))  # model config -> 102 informatif, 104 noninformatif
    base = {"status": "ok", "model": "manual", "prompt_hash": "pmanual"}
    fl.write_jsonl(cfg.paths.llm_labels, [base | {"tweet_id": "102", "label": "informatif"},
                                          base | {"tweet_id": "104", "label": "informatif"}], append=True)
    lap = fl.compare(cfg, "manual", cfg.filter_llm.model)
    assert (lap["n_bersama"], lap["setuju"], lap["persen_setuju"]) == (2, 1, 50.0)
    assert lap["matriks"]["informatif"] == {"informatif": 1, "noninformatif": 1}
    assert json.loads(cfg.paths.bandingkan_laporan.read_text())["cohen_kappa"] == lap["cohen_kappa"]
    beda = list(fl.iter_jsonl(cfg.paths.bandingkan_beda))
    assert [(r["tweet_id"], r["label_a"], r["label_b"], r["label_final"]) for r in beda] == [
        ("104", "informatif", "noninformatif", None)]
    with pytest.raises(ValueError, match="model tersedia"):
        fl.compare(cfg, "tidakada", "manual")


def test_anggota_klaster_mewarisi_label_wakil(ready):
    cfg = ready
    df = read_parquet(cfg.paths.input_1_4)
    df.loc[df["tweet_id"] == "102", "member_tweet_ids"] = pd.Series([["102", "902"]], index=df.index[df["tweet_id"] == "102"])
    write_parquet(df, cfg.paths.input_1_4, INPUT_1_4_COLS)
    full = pd.concat([df, pd.DataFrame({"tweet_id": ["902"], "text_raw": [TWEETS["102"] + " (salinan)"],
                                        "created_at": pd.to_datetime(["2026-08-21T00:00:00Z"], utc=True),
                                        "member_tweet_ids": [["102", "902"]], "cluster_size": [2],
                                        "event_id": [["GP07"]]})], ignore_index=True)
    full["is_representatif"] = full["tweet_id"] != "902"
    write_parquet(full, cfg.paths.final, INPUT_1_4_COLS + ["is_representatif"])
    fl.run(cfg, FakeClient(by_text))
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert out.loc["902", "label"] == "informatif" and out.loc["902", "label_sumber"] == "warisan_wakil"
    assert not out.loc["902", "is_representatif"]
    assert "902" not in set(read_parquet(cfg.paths.informatif)["tweet_id"])  # Modul 2 = wakil saja


def test_config_produksi_aturan_laporan_otomatis_saja():
    # 7 Okt: hanya aturan positif berbasis format baku. 17 Okt: SATU pengecualian yang disetujui user, berbasis angka
    # pada format baku (bukan makna): laporan otomatis gempa berformat templat -> noninformatif (8 Nov, alasan komputasi). Tidak boleh ada aturan lain.
    from modul1.io_utils import PROJECT_ROOT, load_config
    for nama in ("config.yaml", "config_2025.yaml"):
        c = load_config(PROJECT_ROOT / nama)
        assert [(a.nama, a.label) for a in c.filter_llm.aturan] == [("laporan_otomatis_gempa", "noninformatif")]


def test_model_tidak_ada_menghentikan_run_tanpa_mencatat(ready):
    cfg = ready
    with pytest.raises(SystemExit):
        fl.run(cfg, FakeClient(by_text, errors=[fl.ApiError("http_404:model not found", retryable=False)]))
    assert not cfg.paths.llm_labels.exists() or not fl.load_labels(cfg.paths.llm_labels)


def test_ids_membatasi_tweet(ready):
    client = FakeClient(by_text)
    fl.run(ready, client, ids={"104"})
    assert sent_ids(client) == ["104"]
