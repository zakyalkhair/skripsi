"""Sampel anotasi data pengembangan 2025 untuk menyusun aturan & prompt filter informatif.

Dibuat 7 Okt 2026. Jalankan: python scripts/sampel_anotasi_dev.py
Keluaran (di dev_2025/reports/):
  anotasi_dev_2025.csv   -> diisi anotator (TANPA info aturan/kueri agar tidak bias)
  anotasi_dev_2025_kunci.csv -> pemetaan tweet_id ke lapisan sampel & aturan yang cocok (jangan dibuka saat anotasi)
Lapisan: (a) 20 wakil per jenis kueri tunggal yang tidak tertangkap aturan (9 jenis = 180),
         (b) 30 tweet yang tertangkap aturan doa_tanpa_fakta + semua topik_lain (uji presisi aturan negatif),
         (c) 20 tweet yang tertangkap aturan bmkg (uji salinan BMKG).
"""
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modul1.filter_llm import first_rule, load_events  # noqa: E402
from modul1.io_utils import load_config  # noqa: E402

cfg = load_config(ROOT / "config_2025.yaml", ROOT / "dev_2025")
SEED = cfg.seed
df = pd.read_parquet(cfg.paths.input_1_4)
ev = load_events(cfg.paths.kejadian)
df["aturan"] = [getattr(first_rule(t, list(e), ev, cfg.filter_llm.aturan), "nama", None)
                for t, e in zip(df["text_raw"], df["event_id"])]
df["jenis_kueri"] = df["event_id"].map(lambda l: ";".join(sorted({re.sub(r"-25\d\d$", "", x) for x in l})))
df = df.sort_values("tweet_id", key=lambda s: s.map(lambda t: (len(t), t))).reset_index(drop=True)

parts = []
tunggal = df[df["aturan"].isna() & ~df["jenis_kueri"].str.contains(";")]
for j, g in tunggal.groupby("jenis_kueri"):
    parts.append(g.sample(n=min(20, len(g)), random_state=SEED).assign(lapisan=f"jenis:{j}"))
doa = df[df["aturan"] == "doa_tanpa_fakta"]
parts.append(doa.sample(n=min(30, len(doa)), random_state=SEED).assign(lapisan="aturan:doa_tanpa_fakta"))
parts.append(df[df["aturan"] == "topik_lain"].assign(lapisan="aturan:topik_lain"))
bm = df[df["aturan"] == "bmkg"]
parts.append(bm.sample(n=min(20, len(bm)), random_state=SEED).assign(lapisan="aturan:bmkg"))
s = pd.concat(parts, ignore_index=True)
order = list(range(len(s)))
random.Random(SEED).shuffle(order)  # urutan acak agar anotator tidak tahu lapisan
s = s.iloc[order].reset_index(drop=True)
s.insert(0, "no", range(1, len(s) + 1))

out = ROOT / "dev_2025" / "reports"
s[["no", "tweet_id", "text_raw"]].assign(label="", kode_kriteria="", catatan="").to_csv(
    out / "anotasi_dev_2025.csv", index=False, encoding="utf-8-sig")
s[["no", "tweet_id", "lapisan", "aturan", "jenis_kueri", "created_at"]].to_csv(
    out / "anotasi_dev_2025_kunci.csv", index=False, encoding="utf-8-sig")
print(len(s), s["lapisan"].value_counts().to_dict())
