"""Skema konfigurasi (pydantic), baris kejadian, rekaman tweet, dan skema Parquet (pyarrow)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- config
class PathsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kejadian: Path
    raw_jsonl: Path
    crawl_log: Path
    crawl_progress: Path
    twscrape_db: Path
    crawled: Path
    preprocessed: Path
    dedup: Path
    final: Path
    input_1_4: Path
    logs_dir: Path
    alur_data: Path
    sampel_kueri: Path
    dedup_ringkasan: Path
    kalibrasi: Path
    kalibrasi_laporan: Path


class CrawlCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    only_pilot: bool
    max_tweets_per_query: int = Field(gt=0)
    use_system_certs: bool = True
    padding_hari_sebelum: int = Field(default=0, ge=0)
    padding_hari_sesudah: int = Field(default=0, ge=0)
    sleep_between_queries_s: float = Field(ge=0)
    max_query_chars: int = Field(gt=50)
    lang_operator: str
    retweet_operator: str
    negative_keywords: list[str]
    summary_sample_n: int = Field(ge=0)
    sample_per_query: int = Field(ge=0)
    keywords: dict[str, list[str]]


class SaringCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lang: str


class PreprocessCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_token: str
    user_token: str
    min_words: int = Field(ge=1)
    hapus_mention: bool = True
    hapus_hashtag: bool = True


class DedupCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shingle_size: int = Field(ge=1)
    num_perm: int = Field(ge=16)
    lsh_threshold: float = Field(gt=0, lt=1)
    fuzz_threshold: float = Field(ge=0, le=100)


class CalibCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bin_start: int
    bin_end: int
    bin_width: int = Field(gt=0)
    per_bin: int = Field(gt=0)
    target_precision: float = Field(gt=0, le=1)


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    paths: PathsCfg
    crawl: CrawlCfg
    saring_dasar: SaringCfg
    preprocess: PreprocessCfg
    dedup: DedupCfg
    calibration: CalibCfg


# --------------------------------------------------------------------------- kejadian
class Kejadian(BaseModel):
    """Satu baris config/kejadian.csv (hanya kolom yang dibaca kode)."""

    event_id: str
    jenis: str
    alias_wilayah: list[str]
    tanggal_mulai: date
    tanggal_selesai: date
    pilot: bool
    urutan_crawl: int | None = None

    @field_validator("alias_wilayah", mode="before")
    @classmethod
    def _split_alias(cls, v):
        if isinstance(v, str):
            return [a.strip() for a in v.split(";") if a.strip()]
        return v

    @field_validator("pilot", mode="before")
    @classmethod
    def _parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"true", "1", "ya", "yes"}
        return bool(v)

    @field_validator("urutan_crawl", mode="before")
    @classmethod
    def _parse_urutan(cls, v):
        if v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and not v.strip()):
            return None
        return int(float(v))


class Kueri(BaseModel):
    """Satu kueri pencarian X hasil penyusunan otomatis."""

    query_id: str
    text: str
    event_ids: list[str]
    keyword: str
    aliases: list[str]
    since: date  # inklusif
    until: date  # eksklusif (seperti operator until: di X)


# --------------------------------------------------------------------------- tweet
class CrawledTweet(BaseModel):
    """Satu tweet setelah anonimisasi + penggabungan tweet_id (keluaran 1.1)."""

    model_config = ConfigDict(extra="forbid")

    tweet_id: str
    created_at: datetime
    text: str
    lang: str | None
    hashtags: list[str]
    urls: list[str]
    is_reply: bool
    coordinates: list[float] | None  # [longitude, latitude]
    query_id: list[str]
    event_id: list[str]
    user_hash: str | None
    drop_reason: str | None

    @field_validator("tweet_id", mode="before")
    @classmethod
    def _id_str(cls, v):
        if not isinstance(v, str):
            raise ValueError("tweet_id harus string")
        if not v.isdigit():
            raise ValueError(f"tweet_id tidak valid: {v!r}")
        return v


# --------------------------------------------------------------------------- parquet
_LIST_STR = pa.list_(pa.string())

FIELDS: dict[str, pa.DataType] = {
    "tweet_id": pa.string(),
    "created_at": pa.timestamp("us", tz="UTC"),
    "text": pa.string(),
    "text_raw": pa.string(),
    "text_clean": pa.string(),
    "lang": pa.string(),
    "hashtags": _LIST_STR,
    "urls": _LIST_STR,
    "is_reply": pa.bool_(),
    "coordinates": pa.list_(pa.float64()),
    "query_id": _LIST_STR,
    "event_id": _LIST_STR,
    "user_hash": pa.string(),
    "too_short": pa.bool_(),
    "cluster_id": pa.string(),
    "is_representatif": pa.bool_(),
    "member_tweet_ids": _LIST_STR,
    "cluster_size": pa.int64(),
    "drop_reason": pa.string(),
}

CRAWLED_COLS = [
    "tweet_id", "created_at", "text", "lang", "hashtags", "urls", "is_reply",
    "coordinates", "query_id", "event_id", "user_hash", "drop_reason",
]
PREPROCESSED_COLS = CRAWLED_COLS[:3] + ["text_raw", "text_clean"] + CRAWLED_COLS[3:-1] + [
    "too_short", "drop_reason",
]
FINAL_COLS = [
    "tweet_id", "created_at", "text", "text_raw", "text_clean", "lang", "hashtags", "urls",
    "is_reply", "coordinates", "query_id", "event_id", "user_hash", "too_short", "cluster_id",
    "is_representatif", "member_tweet_ids", "cluster_size", "drop_reason",
]
DEDUP_COLS = FINAL_COLS
INPUT_1_4_COLS = ["tweet_id", "created_at", "text_raw", "member_tweet_ids", "cluster_size", "event_id"]


def arrow_schema(cols: list[str]) -> pa.Schema:
    return pa.schema([pa.field(c, FIELDS[c], nullable=True) for c in cols])


# Nilai drop_reason yang dipakai di seluruh pipeline
DROP_BUKAN_ID = "bukan_id"
DROP_RETWEET = "retweet"
DROP_DI_LUAR_JENDELA = "di_luar_jendela"  # created_at di luar since/until kueri asal (mis. tweet yang dikutip)
DROP_TERLALU_PENDEK = "terlalu_pendek"
DROP_BUKAN_WAKIL = "bukan_wakil"
