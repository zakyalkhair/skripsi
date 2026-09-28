"""Kalibrasi ambang fuzz.ratio untuk 1.3: `calib-sample` (ekspor sampel berlabel kosong) dan
`calib-report` (presisi per ambang dari file yang sudah dilabeli manusia)."""

from __future__ import annotations

import random

import pandas as pd

from .dedup import candidate_pairs, verify_pairs
from .io_utils import read_parquet, setup_logger
from .schemas import CalibCfg, Config

LABEL_YA = {"1", "ya", "y", "true", "t", "dup", "duplikat"}
LABEL_TIDAK = {"0", "tidak", "n", "no", "false", "f", "bukan"}


def bin_edges(c: CalibCfg) -> list[int]:
    """Batas bawah bin: 70, 75, ..., 95 (bin terakhir menyertakan skor 100)."""
    return list(range(c.bin_start, c.bin_end, c.bin_width))


def bin_of(score: float, c: CalibCfg) -> int | None:
    if score < c.bin_start or score > c.bin_end:
        return None
    edges = bin_edges(c)
    for lo in reversed(edges):
        if score >= lo:
            return lo
    return None


def bin_label(lo: int, c: CalibCfg) -> str:
    return f"{lo}-{min(lo + c.bin_width, c.bin_end)}"


def build_sample(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Pasangan kandidat LSH yang lolos penjaga angka, dibin menurut skor, disampel per bin."""
    c = cfg.calibration
    elig = df[df["drop_reason"].isna()].copy()
    elig["_idkey"] = elig["tweet_id"].map(lambda t: (len(t), t))
    elig = elig.sort_values(["created_at", "_idkey"], kind="mergesort")
    first = elig.drop_duplicates("text_clean", keep="first")
    texts = first["text_clean"].tolist()
    ids = first["tweet_id"].tolist()
    raws = first["text_raw"].tolist()

    pairs = candidate_pairs(texts, cfg.dedup, cfg.seed)
    results = [r for r in verify_pairs(texts, pairs, cfg.dedup.fuzz_threshold) if r.numbers_equal]
    by_bin: dict[int, list] = {lo: [] for lo in bin_edges(c)}
    for r in results:
        lo = bin_of(r.score, c)
        if lo is not None:
            by_bin[lo].append(r)

    rng = random.Random(cfg.seed)
    rows = []
    for lo in bin_edges(c):
        pop = by_bin[lo]
        chosen = pop if len(pop) <= c.per_bin else rng.sample(pop, c.per_bin)
        chosen = sorted(chosen, key=lambda r: (r.i, r.j))
        for r in chosen:
            rows.append({
                "pair_id": f"{ids[r.i]}_{ids[r.j]}",
                "bin": bin_label(lo, c),
                "bin_bawah": lo,
                "skor": round(r.score, 2),
                "n_populasi_bin": len(pop),
                "tweet_id_1": ids[r.i],
                "tweet_id_2": ids[r.j],
                "text_raw_1": raws[r.i],
                "text_raw_2": raws[r.j],
                "text_clean_1": texts[r.i],
                "text_clean_2": texts[r.j],
                "label_duplikat": "",
            })
    return pd.DataFrame(rows, columns=[
        "pair_id", "bin", "bin_bawah", "skor", "n_populasi_bin", "tweet_id_1", "tweet_id_2",
        "text_raw_1", "text_raw_2", "text_clean_1", "text_clean_2", "label_duplikat",
    ])


def parse_label(v) -> int | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    s = str(v).strip().lower()
    if s in LABEL_YA:
        return 1
    if s in LABEL_TIDAK:
        return 0
    if s == "":
        return None
    raise ValueError(f"label_duplikat tidak dikenal: {v!r} (pakai 1/0 atau ya/tidak)")


def precision_table(labeled: pd.DataFrame, c: CalibCfg) -> pd.DataFrame:
    """Presisi per ambang t (= batas bawah bin). Presisi berbobot memakai ukuran populasi bin,
    karena sampel diambil sama banyak per bin (stratified) — presisi mentah akan bias."""
    lab = labeled.copy()
    lab["y"] = lab["label_duplikat"].map(parse_label)
    lab = lab[lab["y"].notna()]
    per_bin = {}
    for lo in bin_edges(c):
        b = lab[lab["bin_bawah"].astype(int) == lo]
        pop_col = labeled.loc[labeled["bin_bawah"].astype(int) == lo, "n_populasi_bin"]
        pop = int(pop_col.iloc[0]) if len(pop_col) else 0
        per_bin[lo] = (len(b), int(b["y"].sum()) if len(b) else 0, pop)
    rows = []
    for t in bin_edges(c):
        bins = [lo for lo in per_bin if lo >= t]
        n_lab = sum(per_bin[lo][0] for lo in bins)
        n_dup = sum(per_bin[lo][1] for lo in bins)
        w_num = sum(per_bin[lo][2] * per_bin[lo][1] / per_bin[lo][0] for lo in bins if per_bin[lo][0])
        w_den = sum(per_bin[lo][2] for lo in bins if per_bin[lo][0])
        pop_total = sum(per_bin[lo][2] for lo in bins)
        rows.append({
            "ambang": t,
            "n_berlabel": n_lab,
            "n_duplikat": n_dup,
            "presisi_mentah": round(n_dup / n_lab, 4) if n_lab else None,
            "presisi_berbobot": round(w_num / w_den, 4) if w_den else None,
            "populasi_pasangan": pop_total,
            "populasi_tanpa_label": sum(per_bin[lo][2] for lo in bins if not per_bin[lo][0]),
        })
    return pd.DataFrame(rows)


def suggest_threshold(table: pd.DataFrame, target: float) -> int | None:
    ok = table[table["presisi_berbobot"].notna() & (table["presisi_berbobot"] >= target)]
    return int(ok["ambang"].min()) if len(ok) else None


def run_sample(cfg: Config) -> pd.DataFrame:
    log = setup_logger("calib_sample", cfg.paths.logs_dir)
    df = read_parquet(cfg.paths.preprocessed)
    sample = build_sample(df, cfg)
    cfg.paths.kalibrasi.parent.mkdir(parents=True, exist_ok=True)
    if cfg.paths.kalibrasi.exists():
        raise FileExistsError(
            f"{cfg.paths.kalibrasi} sudah ada (mungkin sudah dilabeli). Pindahkan/hapus dulu bila ingin sampel ulang."
        )
    sample.to_csv(cfg.paths.kalibrasi, index=False, encoding="utf-8-sig")
    for b, g in sample.groupby("bin", sort=False):
        log.info("Bin %s: populasi %d, disampel %d", b, int(g["n_populasi_bin"].iloc[0]), len(g))
    log.info("Ditulis %d pasangan ke %s — isi kolom label_duplikat (1/0), lalu jalankan calib-report",
             len(sample), cfg.paths.kalibrasi)
    return sample


def run_report(cfg: Config, path=None) -> tuple[pd.DataFrame, int | None]:
    log = setup_logger("calib_report", cfg.paths.logs_dir)
    path = path or cfg.paths.kalibrasi
    labeled = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    table = precision_table(labeled, cfg.calibration)
    best = suggest_threshold(table, cfg.calibration.target_precision)
    table.to_csv(cfg.paths.kalibrasi_laporan, index=False, encoding="utf-8")
    log.info("Presisi per ambang:\n%s", table.to_string(index=False))
    if best is None:
        log.warning("Tidak ada ambang dengan presisi berbobot >= %.2f", cfg.calibration.target_precision)
    else:
        log.info("Saran ambang: %d (terendah dengan presisi berbobot >= %.2f). Ambang di config saat ini: %.0f",
                 best, cfg.calibration.target_precision, cfg.dedup.fuzz_threshold)
    return table, best
