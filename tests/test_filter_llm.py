import json
import re

import pandas as pd
import pytest
from pydantic import ValidationError

from modul1 import filter_llm as fl
from modul1.io_utils import read_parquet, write_parquet
from modul1.schemas import INPUT_1_4_COLS, AturanCfg

BMKG = ("#Gempa Mag:2.3, 29-Aug-2026 23:32:11WIB, Lok:7.86LS, 120.36BT "
        "(84 km BaratLaut RUTENG-MANGGARAI-NTT), Kedlmn:19 Km #BMKG")
BMKG_NTB = ("#Gempa Mag:5.1, 18-Aug-2026 01:10:06WIB, Lok:8.10LS, 117.20BT "
            "(125 km TimurLaut SARINGI-NTB), Kedlmn:10 Km #BMKG")

TWEETS = {
    "101": BMKG,                                                   # aturan bmkg -> informatif
    "102": "BNPB: 105 orang meninggal akibat gempa M7,7 Flores, 179.037 warga mengungsi",  # LLM
    "103": "Ngapain sih nanyain MBG di depan korban gempa NTT?!",   # aturan topik_lain
    "104": BMKG_NTB,                                               # BMKG wilayah lain -> LLM
    "105": "Semoga saudara kita di NTT diberi kekuatan",            # aturan doa_tanpa_fakta
}
KE_LLM = ["102", "104"]


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


def test_aturan_bmkg_hanya_untuk_wilayah_kejadian(cfg):
    assert rule_of(cfg, BMKG) == ("bmkg", "informatif")
    assert rule_of(cfg, BMKG_NTB) is None  # wilayah lain -> LLM
    assert rule_of(cfg, "Gempa Flores, BMKG catat 1.624 gempa susulan") is None
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
    assert p["model"] == "openai/gpt-oss-120b" and p["temperature"] == 0
    assert p["response_format"] == {"type": "json_object"} and p["reasoning_effort"] == "low"
    assert p["messages"][0] == {"role": "system", "content": "SYS"}
    assert "GP07: Gempa M7,7 Flores" in p["messages"][1]["content"]
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
    cfg.filter_llm.base_url = "http://localhost:11434/v1"
    assert a != fl.prompt_hash("prompt", cfg)


def test_chunk_per_kejadian_dan_ukuran(ready):
    df = read_parquet(ready.paths.input_1_4)
    df.loc[df["tweet_id"] == "105", "event_id"] = pd.Series([["ER03", "GP07"]], index=df.index[df["tweet_id"] == "105"])
    chunks = fl.make_chunks(df, 2)
    assert [(ev, list(g["tweet_id"])) for ev, g in chunks] == [
        (["ER03", "GP07"], ["105"]), (["GP07"], ["101", "102"]), (["GP07"], ["103", "104"])]


# --------------------------------------------------------------------------- alur penuh
def test_run_hibrida_label_keluaran_dan_alur(ready):
    cfg = ready
    client = FakeClient(by_text)
    fl.run(cfg, client)
    assert sent_ids(client) == KE_LLM  # yang ditangani aturan tidak dikirim

    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert len(out) == 5  # tidak ada baris hilang
    assert out["label_sumber"].to_dict() == {
        "101": "aturan:bmkg", "102": "llm", "103": "aturan:topik_lain", "104": "llm", "105": "aturan:doa_tanpa_fakta"}
    assert out["label"].to_dict() == {
        "101": "informatif", "102": "informatif", "103": "noninformatif", "104": "noninformatif",
        "105": "noninformatif"}
    assert out.loc["102", "llm_model"] == "openai/gpt-oss-120b" and out.loc["103", "llm_model"] is None
    assert sorted(read_parquet(cfg.paths.informatif)["tweet_id"]) == ["101", "102"]
    alur = pd.read_csv(cfg.paths.alur_data).set_index("tahap")
    assert (alur.loc["filter informatif", "masuk"], alur.loc["filter informatif", "keluar"],
            alur.loc["filter informatif", "dibuang"]) == (5, 2, 3)
    assert "aturan:topik_lain/noninformatif=1" in alur.loc["filter informatif", "alasan"]
    assert alur.loc["Siap ke Modul 2", "masuk"] == 2

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
    assert out.loc["101", "label_sumber"] == "aturan:bmkg"


def test_jawaban_hilang_dikirim_ulang_dan_label_ok_tidak_ditimpa(ready):
    cfg = ready
    fl.run(cfg, FakeClient(lambda i, t: None if "SARINGI" in t else by_text(i, t)))
    out = read_parquet(cfg.paths.hasil_1_4).set_index("tweet_id")
    assert out.loc["104", "label"] is None and out.loc["104", "llm_status"] == "hilang_dari_jawaban"
    assert "belum berlabel=1" in pd.read_csv(cfg.paths.alur_data).set_index("tahap").loc["filter informatif", "alasan"]

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
    assert out.loc["102", "llm_status"] == "errored:http_500:x" and out.loc["102", "label"] is None


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

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    cfg.crawl.use_system_certs = False
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        fl.make_client(cfg, logging.getLogger("t"))
    cfg.filter_llm.api_key_env = None  # Ollama lokal: tanpa kunci
    assert fl.make_client(cfg, logging.getLogger("t")) is not None
