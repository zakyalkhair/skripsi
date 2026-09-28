"""Tahap 1.3 — Deduplikasi near-duplicate: exact hash + MinHash-LSH + (penjaga angka AND fuzz.ratio).

Tidak ada tweet yang dihapus: setiap baris mendapat cluster_id, is_representatif, member_tweet_ids,
cluster_size. Baris yang tidak ikut 1.3 (sudah punya drop_reason) dibiarkan dengan kolom cluster null.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

import pandas as pd
from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz

from .io_utils import (
    none_if_na,
    read_parquet,
    setup_logger,
    update_alur_data,
    write_parquet,
)
from .schemas import DEDUP_COLS, DROP_BUKAN_WAKIL, FINAL_COLS, INPUT_1_4_COLS, Config, DedupCfg

DIGIT_RE = re.compile(r"\d+")


# --------------------------------------------------------------------------- primitif
def number_signature(text_clean: str) -> list[str]:
    """Penjaga angka: multiset angka dalam text_clean (placeholder <URL> menyembunyikan angka t.co)."""
    return sorted(DIGIT_RE.findall(text_clean))


def shingles(text: str, k: int) -> set[str]:
    if len(text) <= k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def make_minhash(text: str, k: int, num_perm: int, seed: int) -> MinHash:
    m = MinHash(num_perm=num_perm, seed=seed)
    m.update_batch([s.encode("utf-8") for s in shingles(text, k)])
    return m


def tweet_id_key(tid: str) -> tuple[int, str]:
    """Urutan numerik untuk tweet_id string tanpa konversi ke int/float."""
    return (len(tid), tid)


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


# --------------------------------------------------------------------------- pasangan
@dataclass
class PairResult:
    i: int  # indeks teks unik
    j: int
    score: float
    numbers_equal: bool
    accepted: bool


def candidate_pairs(texts: list[str], cfg: DedupCfg, seed: int) -> list[tuple[int, int]]:
    """Blocking MinHash-LSH: pasangan kandidat hanya dari ember yang sama (bukan semua-lawan-semua)."""
    lsh = MinHashLSH(threshold=cfg.lsh_threshold, num_perm=cfg.num_perm)
    hashes = []
    for idx, t in enumerate(texts):
        m = make_minhash(t, cfg.shingle_size, cfg.num_perm, seed)
        hashes.append(m)
        lsh.insert(idx, m)
    pairs: set[tuple[int, int]] = set()
    for idx, m in enumerate(hashes):
        for other in lsh.query(m):
            if other != idx:
                pairs.add((min(idx, other), max(idx, other)))
    return sorted(pairs)


def verify_pairs(texts: list[str], pairs: list[tuple[int, int]], threshold: float) -> list[PairResult]:
    """Dua syarat (AND): (a) angka identik, (b) fuzz.ratio >= ambang.

    Skor tetap dihitung untuk semua pasangan agar laporan bisa menghitung berapa pasangan
    ber-skor tinggi yang dibatalkan penjaga angka, dan untuk kalibrasi.
    """
    sigs = [number_signature(t) for t in texts]
    out = []
    for i, j in pairs:
        eq = sigs[i] == sigs[j]
        score = fuzz.ratio(texts[i], texts[j])
        out.append(PairResult(i, j, score, eq, eq and score >= threshold))
    return out


# --------------------------------------------------------------------------- clustering
@dataclass
class DedupStats:
    masuk: int = 0
    teks_unik: int = 0
    grup_exact: int = 0
    tweet_dalam_grup_exact: int = 0
    kandidat_lsh: int = 0
    skor_ge_ambang: int = 0
    dibatalkan_penjaga_angka: int = 0
    lolos_verifikasi: int = 0
    cluster_gt1: int = 0
    tweet_dalam_cluster_gt1: int = 0
    cluster_terbesar: int = 0
    wakil: int = 0
    ambang_fuzz: float = 0
    params: dict = field(default_factory=dict)


def cluster(df: pd.DataFrame, cfg: DedupCfg, seed: int) -> tuple[pd.DataFrame, DedupStats, list[str], list[PairResult]]:
    """Clustering atas baris df (semua ikut). Mengembalikan df + kolom cluster, statistik,
    daftar teks unik, dan hasil verifikasi pasangan (indeks pada teks unik)."""
    df = df.reset_index(drop=True).copy()
    stats = DedupStats(masuk=len(df), ambang_fuzz=cfg.fuzz_threshold, params=cfg.model_dump() | {"seed": seed})
    if df.empty:
        for c in ("cluster_id", "is_representatif", "member_tweet_ids", "cluster_size"):
            df[c] = pd.Series(dtype=object)
        return df, stats, [], []

    # 1. exact
    sha = df["text_clean"].map(lambda t: hashlib.sha1(t.encode("utf-8")).hexdigest())
    uniq_hashes = list(dict.fromkeys(sha))  # urutan kemunculan pertama, deterministik
    h2u = {h: u for u, h in enumerate(uniq_hashes)}
    row_u = sha.map(h2u).tolist()
    texts: list[str] = [None] * len(uniq_hashes)  # type: ignore[list-item]
    for r, u in enumerate(row_u):
        if texts[u] is None:
            texts[u] = df.at[r, "text_clean"]
    group_sizes = sha.value_counts()
    stats.teks_unik = len(uniq_hashes)
    stats.grup_exact = int((group_sizes > 1).sum())
    stats.tweet_dalam_grup_exact = int(group_sizes[group_sizes > 1].sum())

    # 2–3. blocking + verifikasi pada teks unik
    pairs = candidate_pairs(texts, cfg, seed)
    results = verify_pairs(texts, pairs, cfg.fuzz_threshold)
    stats.kandidat_lsh = len(pairs)
    stats.skor_ge_ambang = sum(r.score >= cfg.fuzz_threshold for r in results)
    stats.dibatalkan_penjaga_angka = sum(
        (r.score >= cfg.fuzz_threshold) and not r.numbers_equal for r in results
    )
    stats.lolos_verifikasi = sum(r.accepted for r in results)

    # 4. union-find atas teks unik (grup exact otomatis satu node)
    uf = UnionFind(len(texts))
    for r in results:
        if r.accepted:
            uf.union(r.i, r.j)
    root = [uf.find(u) for u in row_u]
    df["_root"] = root

    # 5. wakil: created_at paling awal, seri -> tweet_id terkecil (numerik)
    df["_idkey"] = df["tweet_id"].map(tweet_id_key)
    order = df.sort_values(["created_at", "_idkey"], kind="mergesort").index
    rep_of_root: dict[int, str] = {}
    members: dict[int, list[str]] = {}
    for r in order:
        rt = df.at[r, "_root"]
        rep_of_root.setdefault(rt, df.at[r, "tweet_id"])
        members.setdefault(rt, []).append(df.at[r, "tweet_id"])
    df["cluster_id"] = df["_root"].map(lambda rt: f"c{rep_of_root[rt]}")
    df["is_representatif"] = df["tweet_id"] == df["_root"].map(rep_of_root)
    df["member_tweet_ids"] = df["_root"].map(lambda rt: list(members[rt])).astype(object)
    df["cluster_size"] = df["_root"].map(lambda rt: len(members[rt])).astype("int64")
    df = df.drop(columns=["_root", "_idkey"])

    sizes = pd.Series({rt: len(m) for rt, m in members.items()})
    stats.cluster_gt1 = int((sizes > 1).sum())
    stats.tweet_dalam_cluster_gt1 = int(sizes[sizes > 1].sum())
    stats.cluster_terbesar = int(sizes.max())
    stats.wakil = int(df["is_representatif"].sum())
    return df, stats, texts, results


def dedup_df(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, DedupStats, list[str], list[PairResult]]:
    """Jalankan clustering hanya pada baris yang lolos (drop_reason null); gabungkan kembali semua baris."""
    df = df.reset_index(drop=True).copy()
    df["drop_reason"] = none_if_na(df["drop_reason"])
    eligible = df["drop_reason"].isna()
    sub, stats, texts, results = cluster(df[eligible], cfg.dedup, cfg.seed)
    for c in ("cluster_id", "member_tweet_ids"):
        df[c] = pd.Series([None] * len(df), dtype=object)
    df["is_representatif"] = False
    df["cluster_size"] = pd.array([pd.NA] * len(df), dtype="Int64")
    idx = df.index[eligible]
    df.loc[idx, "cluster_id"] = sub["cluster_id"].to_numpy()
    df.loc[idx, "is_representatif"] = sub["is_representatif"].to_numpy()
    df.loc[idx, "cluster_size"] = sub["cluster_size"].to_numpy()
    member_col = df["member_tweet_ids"].tolist()
    for pos, lst in zip(idx, sub["member_tweet_ids"].tolist()):
        member_col[pos] = lst
    df["member_tweet_ids"] = pd.Series(member_col, dtype=object)
    df.loc[eligible & ~df["is_representatif"].astype(bool), "drop_reason"] = DROP_BUKAN_WAKIL
    df["drop_reason"] = none_if_na(df["drop_reason"])
    return df, stats, texts, results


def run(cfg: Config) -> pd.DataFrame:
    log = setup_logger("dedup", cfg.paths.logs_dir)
    df = read_parquet(cfg.paths.preprocessed)
    log.info("Masuk: %d baris; ikut 1.3 (drop_reason kosong): %d", len(df), int(df["drop_reason"].isna().sum()))

    out, st, _, _ = dedup_df(df, cfg)
    log.info("Grup exact (ukuran>1): %d (%d tweet); teks unik: %d", st.grup_exact, st.tweet_dalam_grup_exact, st.teks_unik)
    log.info("Pasangan kandidat LSH: %d", st.kandidat_lsh)
    log.info("Pasangan skor >= %.0f: %d", st.ambang_fuzz, st.skor_ge_ambang)
    log.info("Pasangan skor >= ambang yang dibatalkan penjaga angka: %d", st.dibatalkan_penjaga_angka)
    log.info("Pasangan lolos verifikasi (angka sama AND skor >= ambang): %d", st.lolos_verifikasi)
    log.info("Cluster >1: %d (%d tweet); cluster terbesar: %d; wakil: %d",
             st.cluster_gt1, st.tweet_dalam_cluster_gt1, st.cluster_terbesar, st.wakil)

    write_parquet(out, cfg.paths.dedup, DEDUP_COLS)
    write_parquet(out, cfg.paths.final, FINAL_COLS)
    ready = out[out["is_representatif"].astype(bool)]
    write_parquet(ready, cfg.paths.input_1_4, INPUT_1_4_COLS)
    cfg.paths.dedup_ringkasan.parent.mkdir(parents=True, exist_ok=True)
    cfg.paths.dedup_ringkasan.write_text(json.dumps(asdict(st), indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Ditulis: %s, %s, %s, %s", cfg.paths.dedup, cfg.paths.final, cfg.paths.input_1_4, cfg.paths.dedup_ringkasan)

    n_bukan_wakil = int((out["drop_reason"] == DROP_BUKAN_WAKIL).sum())
    update_alur_data(cfg.paths.alur_data, "dedup", st.masuk, st.wakil, n_bukan_wakil,
                     f"{DROP_BUKAN_WAKIL}={n_bukan_wakil} (dicatat di member_tweet_ids)")
    update_alur_data(cfg.paths.alur_data, "Siap ke 1.4", len(ready), None, None, "")
    return out
