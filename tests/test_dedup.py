from modul1.dedup import cluster, dedup_df, number_signature, tweet_id_key
from modul1.preprocess import clean_text, fix_text

from .conftest import make_df


def _clean(t):
    return clean_text(fix_text(t))


def test_templat_gempa_angka_berbeda_tidak_digabung(cfg):
    # format bot BMKG: M5.2 / 10 km / 08:15 WIB vs M4.8 / 12 km / 09:40 WIB
    a = _clean("Info Gempa Mag:5.2, 15-Agu-26 08:15:22 WIB, Lok:8.61 LS, 121.63 BT (25 km BaratLaut ENDE-NTT), "
               "Kedlmn:10 Km, tidak berpotensi tsunami #BMKG https://t.co/aa1")
    b = _clean("Info Gempa Mag:4.8, 15-Agu-26 09:40:05 WIB, Lok:8.61 LS, 121.63 BT (25 km BaratLaut ENDE-NTT), "
               "Kedlmn:12 Km, tidak berpotensi tsunami #BMKG https://t.co/bb2")
    df = make_df([
        {"tweet_id": "100", "created_at": "2026-08-15T01:00:00Z", "text_clean": a},
        {"tweet_id": "101", "created_at": "2026-08-15T02:00:00Z", "text_clean": b},
    ])
    out, st, _, results = cluster(df, cfg.dedup, cfg.seed)
    assert out["cluster_size"].tolist() == [1, 1]
    assert out["is_representatif"].all()
    # pasangan ini memang kandidat & skornya tinggi — yang menolak adalah penjaga angka
    assert st.kandidat_lsh == 1 and st.skor_ge_ambang == 1 and st.dibatalkan_penjaga_angka == 1


def test_parafrasa_angka_sama_digabung(cfg):
    a = _clean("BNPB: korban meninggal gempa Flores bertambah menjadi 111 orang, 950 rumah rusak https://t.co/x1")
    b = _clean("BNPB: korban meninggal gempa Flores bertambah jadi 111 orang, 950 rumah rusak berat https://t.co/y9")
    df = make_df([
        {"tweet_id": "200", "created_at": "2026-08-16T05:00:00Z", "text_clean": b},
        {"tweet_id": "201", "created_at": "2026-08-16T04:00:00Z", "text_clean": a},
    ])
    out, st, _, _ = cluster(df, cfg.dedup, cfg.seed)
    assert out["cluster_size"].tolist() == [2, 2]
    assert out.set_index("tweet_id")["is_representatif"].to_dict() == {"200": False, "201": True}
    assert st.lolos_verifikasi == 1


def test_rantai_a_b_c_satu_cluster_wakil_paling_awal(cfg):
    base = "pengungsi gempa di ende kekurangan air bersih dan selimut mohon bantuan segera dari pemerintah daerah"
    a = base
    b = base.replace("segera", "secepatnya")
    c = b.replace("pemerintah daerah", "pemda setempat")
    df = make_df([
        {"tweet_id": "301", "created_at": "2026-08-17T03:00:00Z", "text_clean": a},
        {"tweet_id": "302", "created_at": "2026-08-17T01:00:00Z", "text_clean": b},
        {"tweet_id": "303", "created_at": "2026-08-17T02:00:00Z", "text_clean": c},
    ])
    out, _, texts, results = cluster(df, cfg.dedup, cfg.seed)
    accepted = {(texts[r.i], texts[r.j]) for r in results if r.accepted}
    assert (a, c) not in accepted and (c, a) not in accepted  # A dan C tidak mirip langsung
    assert out["cluster_id"].nunique() == 1
    assert out["cluster_size"].tolist() == [3, 3, 3]
    rep = out[out["is_representatif"]]
    assert rep["tweet_id"].tolist() == ["302"]
    assert sorted(out["member_tweet_ids"].iloc[0]) == ["301", "302", "303"]


def test_exact_dan_seri_waktu_pilih_tweet_id_terkecil_numerik(cfg):
    t = "banjir di demak sudah setinggi pinggang orang dewasa"
    df = make_df([
        {"tweet_id": "1000000000000000010", "created_at": "2026-01-16T01:00:00Z", "text_clean": t},
        {"tweet_id": "999999999999999999", "created_at": "2026-01-16T01:00:00Z", "text_clean": t},
    ])
    out, st, _, _ = cluster(df, cfg.dedup, cfg.seed)
    assert st.grup_exact == 1
    assert out[out["is_representatif"]]["tweet_id"].tolist() == ["999999999999999999"]


def test_penjaga_angka_memakai_placeholder_url():
    assert number_signature("gempa m5 2 <URL>") == ["2", "5"]
    assert tweet_id_key("9") < tweet_id_key("10")


def test_dedup_df_tidak_menghapus_baris_dan_mengabaikan_yang_sudah_dibuang(cfg):
    t = "banjir di demak sudah setinggi pinggang orang dewasa"
    df = make_df([
        {"tweet_id": "1", "created_at": "2026-01-16T01:00:00Z", "text_clean": t},
        {"tweet_id": "2", "created_at": "2026-01-16T02:00:00Z", "text_clean": t},
        {"tweet_id": "3", "created_at": "2026-01-16T00:00:00Z", "text_clean": t, "drop_reason": "retweet"},
        {"tweet_id": "4", "created_at": "2026-01-16T00:00:00Z", "text_clean": "banjir", "too_short": True,
         "drop_reason": "terlalu_pendek"},
    ])
    out, _, _, _ = dedup_df(df, cfg)
    assert len(out) == 4
    by = out.set_index("tweet_id")
    assert by.loc["1", "is_representatif"] and by.loc["1", "drop_reason"] is None
    assert by.loc["2", "drop_reason"] == "bukan_wakil"
    assert by.loc["3", "drop_reason"] == "retweet" and by.loc["3", "cluster_id"] is None
    assert by.loc["4", "drop_reason"] == "terlalu_pendek" and not by.loc["4", "is_representatif"]


def test_deterministik(cfg):
    rows = [{"tweet_id": str(i), "created_at": f"2026-08-15T0{i % 10}:00:00Z",
             "text_clean": f"relawan mengevakuasi warga terdampak gempa flores di desa nomor {i % 4}"} for i in range(20)]
    a, _, _, _ = cluster(make_df(rows), cfg.dedup, cfg.seed)
    b, _, _, _ = cluster(make_df(rows), cfg.dedup, cfg.seed)
    assert a["cluster_id"].tolist() == b["cluster_id"].tolist()
