"""Tahap 1.2 — Preprocessing: `text_raw` (hanya perbaikan) dan `text_clean` (untuk dedup)."""

from __future__ import annotations

import html
import re
import unicodedata

import ftfy
import pandas as pd

from .io_utils import none_if_na, read_parquet, setup_logger, update_alur_data, write_parquet
from .schemas import DROP_TERLALU_PENDEK, PREPROCESSED_COLS, Config

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@\w+")
HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
WS_RE = re.compile(r"\s+")


def fix_text(text: str) -> str:
    """Langkah 1–4, dipakai untuk `text_raw` dan `text_clean`.

    Hanya memperbaiki (encoding, entitas HTML, NFKC, spasi); tidak ada kata yang dihapus/diganti.
    """
    s = ftfy.fix_text(text)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    return WS_RE.sub(" ", s).strip()


def _strip_non_word(segment: str) -> str:
    """Langkah 8: emoji, simbol, dan tanda baca -> spasi (hanya huruf, angka, spasi yang tersisa)."""
    return "".join(
        ch if (unicodedata.category(ch)[0] in "LN" or ch.isspace()) else " " for ch in segment
    )


def clean_text(text_raw: str, url_token: str = "<URL>", user_token: str = "<USER>",
               hapus_mention: bool = True, hapus_hashtag: bool = True) -> str:
    """Langkah 5–9 atas `text_raw`. Placeholder dilindungi dari penghapusan tanda baca & lowercase.

    hapus_mention: True = mention `@x` dihapus seluruhnya; False = diganti `<USER>`.
    hapus_hashtag: True = hashtag `#Kata` dihapus seluruhnya; False = hanya tanda `#` dibuang.
    URL diproses lebih dulu agar `#`/`@` di dalam URL tidak ikut terbaca sebagai hashtag/mention.
    """
    s = URL_RE.sub(f" {url_token} ", text_raw)                              # 5
    s = MENTION_RE.sub(" " if hapus_mention else f" {user_token} ", s)      # 6
    s = HASHTAG_RE.sub(" ", s) if hapus_hashtag else s.replace("#", "")     # 7
    placeholder_re = re.compile(f"({re.escape(url_token)}|{re.escape(user_token)})")
    parts = placeholder_re.split(s)
    out = []
    for part in parts:
        if part in (url_token, user_token):
            out.append(f" {part} ")
        else:
            out.append(_strip_non_word(part).lower())    # 8, 9
    return WS_RE.sub(" ", "".join(out)).strip()


def is_too_short(text_clean: str, min_words: int, url_token: str = "<URL>",
                 user_token: str = "<USER>") -> bool:
    """Langkah 10: jumlah kata di luar placeholder < min_words."""
    words = [w for w in text_clean.split() if w not in (url_token, user_token)]
    return len(words) < min_words


def preprocess_df(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    p = cfg.preprocess
    df = df.copy()
    df["text_raw"] = df["text"].map(lambda t: fix_text(t or ""))
    df["text_clean"] = df["text_raw"].map(
        lambda t: clean_text(t, p.url_token, p.user_token, p.hapus_mention, p.hapus_hashtag)
    )
    df["too_short"] = df["text_clean"].map(
        lambda t: is_too_short(t, p.min_words, p.url_token, p.user_token)
    )
    # drop_reason dari tahap sebelumnya (bukan_id / retweet) tidak ditimpa
    eligible = df["drop_reason"].isna()
    df.loc[eligible & df["too_short"], "drop_reason"] = DROP_TERLALU_PENDEK
    df["drop_reason"] = none_if_na(df["drop_reason"])
    return df


def run(cfg: Config) -> pd.DataFrame:
    log = setup_logger("preprocess", cfg.paths.logs_dir)
    df = read_parquet(cfg.paths.crawled)
    eligible_in = int(df["drop_reason"].isna().sum())
    log.info("Masuk: %d baris (%d lolos saring dasar)", len(df), eligible_in)

    out = preprocess_df(df, cfg)
    n_short = int((out["drop_reason"] == DROP_TERLALU_PENDEK).sum())
    eligible_out = int(out["drop_reason"].isna().sum())
    changed = int((out["text"] != out["text_raw"]).sum())
    log.info("text_raw berubah dari text asli (ftfy/HTML/NFKC/spasi): %d baris", changed)
    log.info("Keluar ke 1.3: %d; ditandai terlalu_pendek: %d (tidak dihapus dari file)",
             eligible_out, n_short)

    write_parquet(out, cfg.paths.preprocessed, PREPROCESSED_COLS)
    log.info("Ditulis: %s", cfg.paths.preprocessed)
    update_alur_data(cfg.paths.alur_data, "preprocessing", eligible_in, eligible_out, n_short,
                     f"{DROP_TERLALU_PENDEK}={n_short}")
    return out
