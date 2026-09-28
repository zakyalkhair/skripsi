import pandas as pd

from modul1.calib import bin_of, parse_label, precision_table, suggest_threshold
from modul1.io_utils import read_parquet, update_alur_data, write_parquet
from modul1.schemas import FINAL_COLS


def test_tweet_id_19_digit_tetap_string_di_parquet(tmp_path):
    df = pd.DataFrame({
        "tweet_id": ["1969307187192924196"], "created_at": pd.to_datetime(["2026-08-15T01:00:00Z"], utc=True),
        "text": ["Gempa 🌊"], "member_tweet_ids": [["1969307187192924196", "1969307187192924197"]],
        "cluster_size": [2], "is_reply": [False], "drop_reason": [None],
    })
    p = tmp_path / "x.parquet"
    write_parquet(df, p, FINAL_COLS)
    back = read_parquet(p)
    assert back.loc[0, "tweet_id"] == "1969307187192924196"
    assert back.loc[0, "member_tweet_ids"] == ["1969307187192924196", "1969307187192924197"]
    assert back.loc[0, "text"] == "Gempa 🌊"
    assert back.loc[0, "drop_reason"] is None
    assert str(back["cluster_size"].dtype) == "Int64"


def test_write_parquet_menolak_tweet_id_numerik(tmp_path):
    import pytest

    with pytest.raises(TypeError):
        write_parquet(pd.DataFrame({"tweet_id": [1969307187192924196]}), tmp_path / "x.parquet", ["tweet_id"])


def test_alur_data_upsert_dan_urut(tmp_path):
    p = tmp_path / "alur.csv"
    update_alur_data(p, "dedup", 10, 8, 2, "bukan_wakil=2")
    update_alur_data(p, "hasil crawl", 20, 20, 0)
    update_alur_data(p, "dedup", 11, 9, 2, "bukan_wakil=2")
    df = pd.read_csv(p)
    assert df["tahap"].tolist() == ["hasil crawl", "dedup"]
    assert df.set_index("tahap").loc["dedup", "masuk"] == 11


def test_bin_dan_label(cfg):
    c = cfg.calibration
    assert bin_of(69.9, c) is None and bin_of(70, c) == 70 and bin_of(84.99, c) == 80 and bin_of(100, c) == 95
    assert parse_label("Ya") == 1 and parse_label("0") == 0 and parse_label("") is None


def test_precision_table_berbobot_dan_saran(cfg):
    c = cfg.calibration
    rows = []
    # bin 70–80: separuh duplikat; bin 85+: semua duplikat
    for lo, pop, ys in [(70, 1000, [1, 0]), (75, 1000, [1, 0]), (80, 500, [1, 1, 0, 1]), (85, 400, [1, 1]),
                        (90, 400, [1, 1]), (95, 400, [1])]:
        rows += [{"bin_bawah": str(lo), "n_populasi_bin": str(pop), "label_duplikat": str(y)} for y in ys]
    t = precision_table(pd.DataFrame(rows), c)
    assert t.set_index("ambang").loc[85, "presisi_berbobot"] == 1.0
    assert t.set_index("ambang").loc[80, "presisi_berbobot"] < 1.0
    assert suggest_threshold(t, 0.95) == 85
