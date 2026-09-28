"""Utilitas I/O: config, JSONL, Parquet, logging, dan pencatatan alur data."""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from .schemas import Config, arrow_schema

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Urutan baku baris reports/alur_data.csv
ALUR_TAHAP = ["hasil crawl", "saring dasar", "preprocessing", "dedup", "Siap ke 1.4"]
ALUR_KOLOM = ["tahap", "masuk", "keluar", "dibuang", "alasan"]


# --------------------------------------------------------------------------- config
def load_config(config_path: str | Path | None = None, workdir: str | Path | None = None) -> Config:
    """Baca config.yaml; resolve `kejadian` relatif ke folder config, sisanya ke workdir."""
    config_path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    config_path = config_path.resolve()
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    cfg = Config.model_validate(raw)
    base = Path(workdir).resolve() if workdir else config_path.parent
    for name in type(cfg.paths).model_fields:
        p = getattr(cfg.paths, name)
        if not p.is_absolute():
            root = config_path.parent if name == "kejadian" else base
            setattr(cfg.paths, name, (root / p).resolve())
    return cfg


def none_if_na(s: pd.Series) -> pd.Series:
    """Kolom teks nullable -> object dengan None (bukan NaN), agar konsisten antar tahap."""
    return s.astype(object).where(s.notna(), None)


# --------------------------------------------------------------------------- jsonl
def iter_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: JSON rusak: {e}") from e


def dumps_jsonl(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str) + "\n"


def write_jsonl(path: str | Path, rows: Iterable[dict], append: bool = False) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "a" if append else "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(dumps_jsonl(r))
            n += 1
    return n


# --------------------------------------------------------------------------- parquet
def _to_list(v):
    """Nilai list dari Parquet/pandas bisa berupa numpy array; seragamkan ke list/None."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (list, tuple)):
        return list(v)
    if hasattr(v, "tolist"):
        return v.tolist()
    return v


def write_parquet(df: pd.DataFrame, path: str | Path, cols: list[str]) -> None:
    """Tulis Parquet dengan skema eksplisit (tweet_id selalu string)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = arrow_schema(cols)
    data = {}
    for field in schema:
        col = df[field.name] if field.name in df.columns else pd.Series([None] * len(df))
        values = col.tolist()
        if pa.types.is_list(field.type):
            values = [_to_list(v) for v in values]
        elif pa.types.is_timestamp(field.type):
            values = pd.to_datetime(pd.Series(values), utc=True).tolist()
            values = [None if pd.isna(v) else v for v in values]
        else:
            values = [None if (not isinstance(v, (list, str)) and pd.isna(v)) else v for v in values]
        if field.name == "tweet_id":
            bad = [v for v in values if not isinstance(v, str)]
            if bad:
                raise TypeError(f"tweet_id harus string, ditemukan {type(bad[0]).__name__}")
        data[field.name] = pa.array(values, type=field.type)
    table = pa.Table.from_pydict(data, schema=schema)
    tmp = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, path)


def read_parquet(path: str | Path) -> pd.DataFrame:
    """Baca Parquet; kolom list dikembalikan sebagai list Python, tweet_id tetap string."""
    table = pq.read_table(path)
    df = table.to_pandas(types_mapper={pa.int64(): pd.Int64Dtype()}.get)
    for field in table.schema:
        if pa.types.is_list(field.type):
            df[field.name] = df[field.name].map(_to_list).astype(object)
        elif pa.types.is_string(field.type) or pa.types.is_large_string(field.type):
            df[field.name] = df[field.name].astype(object).where(df[field.name].notna(), None)
    return df


# --------------------------------------------------------------------------- logging
def setup_logger(stage: str, logs_dir: str | Path) -> logging.Logger:
    """Logger per tahap: ke layar dan ke logs/<stage>_<waktu>.log. Jangan pernah log rahasia."""
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logger = logging.getLogger(f"modul1.{stage}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh = logging.FileHandler(logs_dir / f"{stage}_{stamp}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- alur data
def update_alur_data(path: str | Path, tahap: str, masuk: int | None, keluar: int | None,
                     dibuang: int | None, alasan: str = "") -> None:
    """Tambah/ganti baris `tahap` di reports/alur_data.csv (idempoten bila tahap dijalankan ulang)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict] = {}
    if path.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                rows[r["tahap"]] = r
    rows[tahap] = {
        "tahap": tahap,
        "masuk": "" if masuk is None else int(masuk),
        "keluar": "" if keluar is None else int(keluar),
        "dibuang": "" if dibuang is None else int(dibuang),
        "alasan": alasan,
    }
    order = {t: i for i, t in enumerate(ALUR_TAHAP)}
    ordered = sorted(rows.values(), key=lambda r: order.get(r["tahap"], len(order)))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ALUR_KOLOM)
        w.writeheader()
        w.writerows(ordered)
