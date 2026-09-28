import pandas as pd

from modul1.preprocess import clean_text, fix_text, is_too_short, preprocess_df


def test_contoh_wajib_html_hashtag_emoji_url_mention():
    t = "Banjir &amp; longsor di #Demak!! 🌊 https://t.co/x @bpbd"
    raw = fix_text(t)
    assert raw == "Banjir & longsor di #Demak!! 🌊 https://t.co/x @bpbd"
    # mode default: hashtag & mention dihapus seluruhnya
    assert clean_text(raw) == "banjir longsor di <URL>"
    # mode spesifikasi awal (hapus_mention/hapus_hashtag = false)
    assert clean_text(raw, hapus_mention=False, hapus_hashtag=False) == "banjir longsor di demak <URL> <USER>"


def test_hapus_hashtag_dan_mention_seluruhnya():
    t = "@bnpb_indonesia Gempa M7,7 guncang Flores #PrayForNTT #gempa_flores https://t.co/a#x cc @bmkg"
    assert clean_text(fix_text(t)) == "gempa m7 7 guncang flores <URL> cc"
    # dua tweet yang hanya beda hashtag/mention jadi identik -> satu grup exact di dedup
    a = clean_text(fix_text("Update korban gempa Ende 111 orang #PrayForFlores @bnpb"))
    b = clean_text(fix_text("@detikcom Update korban gempa Ende 111 orang #GempaNTT"))
    assert a == b == "update korban gempa ende 111 orang"
    # email & tanda # di tengah kata tidak dianggap mention/hashtag
    assert clean_text("kontak a@b.com no#1") == "kontak a b com no 1"


def test_mojibake_diperbaiki_ftfy():
    assert fix_text("banjir ðŸŒŠ") == "banjir 🌊"


def test_huruf_tebal_unicode_dinormalkan_di_kedua_kolom():
    raw = fix_text("𝗕𝗮𝗻𝗷𝗶𝗿")
    assert raw == "Banjir"
    assert clean_text(raw) == "banjir"


def test_text_raw_tidak_menghapus_kata_atau_tanda_baca():
    t = "  GEMPA!!  @bmkg   cek   https://t.co/Ab1 #Flores \n\n😭 "
    raw = fix_text(t)
    assert raw == "GEMPA!! @bmkg cek https://t.co/Ab1 #Flores 😭"


def test_hashtag_tidak_dipecah_dan_tanda_baca_jadi_spasi():
    assert clean_text("#BanjirDemak laki-laki M5.2", hapus_hashtag=False) == "banjirdemak laki laki m5 2"


def test_email_bukan_mention_dan_url_www():
    assert clean_text("kirim ke a@b.com atau www.bnpb.go.id/x") == "kirim ke a b com atau <URL>"


def test_too_short_tidak_menghitung_placeholder():
    assert is_too_short("banjir lagi <URL> <USER>", 3)
    assert not is_too_short("banjir lagi di demak <URL>", 3)


def test_preprocess_df_menandai_tanpa_menghapus_dan_tidak_menimpa_drop_reason(cfg):
    df = pd.DataFrame({
        "tweet_id": ["1", "2", "3"],
        "text": ["banjir lagi 😭", "Banjir besar melanda Demak pagi ini", "RT @x: banjir"],
        "drop_reason": [None, None, "retweet"],
    })
    out = preprocess_df(df, cfg)
    assert len(out) == 3
    assert out["too_short"].tolist() == [True, False, True]
    assert out["drop_reason"].tolist() == ["terlalu_pendek", None, "retweet"]
    assert out["text"].tolist() == df["text"].tolist()  # teks asli tetap
