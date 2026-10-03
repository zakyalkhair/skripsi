import asyncio
import json
import logging

import pandas as pd

from modul1 import crawl
from modul1.crawl import (
    build_queries,
    fetch,
    load_accounts_from_env,
    load_kejadian,
    parse_raw,
    query_id_of,
)
from modul1.io_utils import write_jsonl


def test_load_kejadian_hanya_pilot_urut_urutan_crawl(cfg):
    ks = load_kejadian(cfg.paths.kejadian, only_pilot=True)
    assert [k.event_id for k in ks] == ["GP07", "ER03", "LS01", "GP05", "BJ03", "KH05",
                                          "CE01", "CE02", "CE03", "CE04", "CE05", "KK01", "KK02"]
    assert len(load_kejadian(cfg.paths.kejadian, only_pilot=False)) == 34
    assert [k.event_id for k in load_kejadian(cfg.paths.kejadian, True, ["er03", "GP07"])] == ["GP07", "ER03"]


def test_build_queries_or_per_kata_kunci(cfg):
    ks = load_kejadian(cfg.paths.kejadian, True, ["GP07"])
    qs = build_queries(ks, cfg)
    assert [q.keyword for q in qs] == ["gempa", "gempa bumi", "gempa susulan", "pengungsi"]
    q = qs[1]
    assert q.text.startswith('"gempa bumi" (NTT OR Flores OR Ende OR Manggarai OR "Manggarai Timur"')
    assert q.text.endswith(") -filter:retweets -kecelakaan since:2026-08-14 until:2026-08-30")
    assert "lang:id" not in q.text and "  " not in q.text
    assert (q.since.isoformat(), q.until.isoformat()) == ("2026-08-14", "2026-08-30")
    assert q.query_id == query_id_of(q.text) and q.event_ids == ["GP07"]
    # stabil antar pemanggilan
    assert [x.query_id for x in build_queries(ks, cfg)] == [x.query_id for x in qs]
    # operator bahasa masih bisa diaktifkan lagi lewat config
    cfg.crawl.lang_operator = "lang:id"
    assert "lang:id -filter:retweets" in build_queries(ks, cfg)[1].text


def test_padding_tanggal_memperlebar_jendela(cfg):
    cfg.crawl.padding_hari_sebelum = 3
    cfg.crawl.padding_hari_sesudah = 14
    q = build_queries(load_kejadian(cfg.paths.kejadian, True, ["GP07"]), cfg)[0]
    # kejadian.csv: mulai 2026-08-14, selesai 2026-08-29
    assert q.text.endswith("since:2026-08-11 until:2026-09-13")


def test_build_queries_dipecah_bila_terlalu_panjang(cfg):
    cfg.crawl.max_query_chars = 120
    qs = build_queries(load_kejadian(cfg.paths.kejadian, True, ["GP07"]), cfg)
    assert all(len(q.text) <= 120 or len(q.aliases) == 1 for q in qs)
    gempa = [q for q in qs if q.keyword == "gempa"]
    assert len(gempa) > 1
    assert sum((q.aliases for q in gempa), []) == ["NTT", "Flores", "Ende", "Manggarai", "Manggarai Timur",
                                                    "Manggarai Barat", "Nagekeo", "Sikka", "Ngada", "Bima"]


def test_akun_dari_env_tanpa_bocor():
    env = {"X_ACCOUNT_1_USERNAME": "a", "X_ACCOUNT_1_COOKIES": "auth_token=x; ct0=y",
           "X_ACCOUNT_2_USERNAME": "b", "X_ACCOUNT_2_PASSWORD": "p", "X_ACCOUNT_3_USERNAME": "kosong"}
    accs = load_accounts_from_env(env)
    assert [a["username"] for a in accs] == ["a", "b"]


def test_cookies_tanpa_nama_auth_token_ditolak_tanpa_mencetak_nilai():
    import pytest

    env = {"X_ACCOUNT_1_USERNAME": "a", "X_ACCOUNT_1_COOKIES": "abc123rahasia; ct0=def456"}
    with pytest.raises(ValueError) as e:
        load_accounts_from_env(env)
    assert "auth_token" in str(e.value) and "abc123rahasia" not in str(e.value)


def _raw(tid, text, lang="in", **kw):
    d = {"id": int(tid), "id_str": tid, "date": "2026-08-15T01:02:03+00:00", "lang": lang, "rawContent": text,
         "user": {"id": 42, "id_str": "42", "username": "rahasia", "displayname": "Nama Asli", "location": "Ende"},
         "hashtags": ["Gempa"], "links": [{"url": "https://bnpb.go.id/x", "text": None, "tcourl": "https://t.co/a"}],
         "retweetedTweet": None, "quotedTweet": None, "coordinates": None, "inReplyToTweetId": None,
         "query_id": "qA", "event_ids": ["GP07"], "crawled_at": "2026-09-28T00:00:00+00:00"}
    d.update(kw)
    return d


def test_parse_raw_anonim_gabung_id_dan_saring(tmp_path):
    rows = [
        _raw("1969307187192924196", "Gempa kuat di Ende"),
        _raw("1969307187192924196", "Gempa kuat di Ende", query_id="qB", event_ids=["ER03"]),
        _raw("1969307187192924197", "Strong quake", lang="en"),
        _raw("1969307187192924198", "RT @bnpb: gempa", retweetedTweet={"id": 1}),
        _raw("1969307187192924199", "Balasan soal gempa", inReplyToTweetId=5, coordinates={"longitude": 121.6, "latitude": -8.8}),
        _raw("1969307187192924200", "Komentar saya sendiri", quotedTweet={"rawContent": "teks kutipan"}),
    ]
    p = tmp_path / "raw.jsonl"
    write_jsonl(p, rows)
    df, st = parse_raw(p, salt="garam", lang_id="in")
    assert st == {"baris_raw": 6, "tweet_unik": 5, "duplikat_id": 1, "retweet": 1, "bukan_id": 1,
                  "di_luar_jendela": 0, "lolos": 3, "balasan": 1}
    by = df.set_index("tweet_id")
    assert by.index.map(type).unique().tolist() == [str]
    assert by.loc["1969307187192924196", "query_id"] == ["qA", "qB"]
    assert by.loc["1969307187192924196", "event_id"] == ["ER03", "GP07"]
    assert by.loc["1969307187192924197", "drop_reason"] == "bukan_id"
    assert by.loc["1969307187192924198", "drop_reason"] == "retweet"
    assert by.loc["1969307187192924199", "is_reply"] and by.loc["1969307187192924199", "coordinates"] == [121.6, -8.8]
    assert by.loc["1969307187192924200", "text"] == "Komentar saya sendiri"
    assert str(df["created_at"].dt.tz) == "UTC"
    blob = df.to_json(date_format="iso")
    assert "rahasia" not in blob and "Nama Asli" not in blob and "username" not in df.columns
    assert by.loc["1969307187192924196", "user_hash"] is not None and len(by.loc["1969307187192924196", "user_hash"]) == 64

    df2, _ = parse_raw(p, salt=None, lang_id="in")
    assert df2["user_hash"].isna().all()


def test_tweet_di_luar_jendela_kueri_ditandai(tmp_path):
    w = ["2026-08-14", "2026-08-30"]  # [since, until)
    rows = [
        _raw("1969307187192924301", "gempa Flores hari ini", query_window=w),
        # tweet lama yang ikut terbawa karena dikutip (twscrape mengembalikannya juga)
        _raw("1969307187192924302", "gempa Maret", date="2026-03-22T05:00:00+00:00", query_window=w),
        # batas: until eksklusif (tepat 30 Agt 00:00 UTC -> di luar)
        _raw("1969307187192924303", "gempa batas", date="2026-08-30T00:00:00+00:00", query_window=w),
        # di luar jendela kueri A tapi di dalam jendela kueri B -> lolos
        _raw("1969307187192924304", "gempa sept", date="2026-09-05T00:00:00+00:00", query_window=w),
        _raw("1969307187192924304", "gempa sept", date="2026-09-05T00:00:00+00:00", query_id="qB",
             query_window=["2026-09-01", "2026-09-10"]),
        # raw lama tanpa query_window -> tidak ditandai
        _raw("1969307187192924305", "gempa lama", date="2020-01-01T00:00:00+00:00"),
    ]
    p = tmp_path / "raw.jsonl"
    write_jsonl(p, rows)
    df, st = parse_raw(p, salt=None, lang_id="in")
    by = df.set_index("tweet_id")["drop_reason"].to_dict()
    assert by == {"1969307187192924301": None, "1969307187192924302": "di_luar_jendela",
                  "1969307187192924303": "di_luar_jendela", "1969307187192924304": None,
                  "1969307187192924305": None}
    assert st["di_luar_jendela"] == 2 and len(df) == 5


class _Tw:
    def __init__(self, d):
        self._d = d

    def dict(self):
        return self._d


class FakeAPI:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    async def search(self, q, limit=-1):
        self.calls.append(q)
        if self.fail_on and self.fail_on in q:
            raise RuntimeError("rate limit")
        for i in range(3):
            yield _Tw({"id": 10 + i, "id_str": str(1969307187192924000 + i), "lang": "in",
                       "rawContent": f"gempa tiruan {i}", "date": "2026-08-15T00:00:00+00:00"})


def test_fetch_menulis_raw_log_dan_bisa_dilanjutkan(cfg):
    cfg.crawl.sleep_between_queries_s = 0
    ks = load_kejadian(cfg.paths.kejadian, True, ["LS01"])
    qs = build_queries(ks, cfg)
    log = logging.getLogger("test")
    api = FakeAPI(fail_on="tertimbun")
    asyncio.run(fetch(cfg, qs, ks, api, log))
    assert len(api.calls) == 3
    lines = [json.loads(l) for l in cfg.paths.raw_jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 6 and all(l["query_id"] and l["crawled_at"] and l["event_ids"] == ["LS01"] for l in lines)
    assert all(l["query_window"] == ["2026-01-23", "2026-02-08"] for l in lines)
    log_df = pd.read_csv(cfg.paths.crawl_log, dtype=str)
    assert list(log_df.columns) == crawl.CRAWL_LOG_COLS
    assert (log_df["status"] == "selesai").sum() == 2 and log_df["status"].str.startswith("gagal").sum() == 1

    # run kedua: hanya kueri yang gagal diulang
    api2 = FakeAPI()
    asyncio.run(fetch(cfg, qs, ks, api2, log))
    assert len(api2.calls) == 1 and "tertimbun" in api2.calls[0]


class EmptyAPI:
    def __init__(self):
        self.calls = []

    async def search(self, q, limit=-1):
        self.calls.append(q)
        return
        yield


def test_kueri_nol_hasil_tidak_ditandai_selesai(cfg):
    cfg.crawl.sleep_between_queries_s = 0
    ks = load_kejadian(cfg.paths.kejadian, True, ["LS01"])
    qs = build_queries(ks, cfg)
    log = logging.getLogger("test")
    asyncio.run(fetch(cfg, qs, ks, EmptyAPI(), log))
    assert (pd.read_csv(cfg.paths.crawl_log)["status"] == "kosong").all()
    api2 = EmptyAPI()
    asyncio.run(fetch(cfg, qs, ks, api2, log))
    assert len(api2.calls) == 3  # semua diulang




def test_run_skip_fetch_menulis_parquet_sampel_dan_alur(cfg):
    write_jsonl(cfg.paths.raw_jsonl, [_raw(str(1969307187192924100 + i), f"gempa di ende nomor {i}") for i in range(60)]
                + [_raw("1969307187192924300", "quake", lang="en")])
    df = crawl.run(cfg, skip_fetch=True)
    assert len(df) == 61
    s = pd.read_csv(cfg.paths.sampel_kueri, dtype=str, encoding="utf-8-sig")
    assert len(s) == 50
    alur = pd.read_csv(cfg.paths.alur_data)
    assert alur["tahap"].tolist() == ["hasil crawl", "saring dasar"]
    assert alur.set_index("tahap").loc["saring dasar", "keluar"] == 60


def test_build_queries_jenis_tanpa_wilayah(cfg):
    ks = load_kejadian(cfg.paths.kejadian, True, ["CE01", "GP07"])
    qs = build_queries(ks, cfg.model_copy(update={"crawl": cfg.crawl.model_copy(
        update={"jenis_tanpa_wilayah": ["cuaca_ekstrem"]})}))
    ce = [q for q in qs if q.event_ids == ["CE01"]]
    assert ce and all("(" not in q.text and q.aliases == [] for q in ce)
    assert all("(" in q.text for q in qs if q.event_ids == ["GP07"])
