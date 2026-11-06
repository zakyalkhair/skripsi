"""Pulihkan label uji yang ikut terpindah (7 Okt 2026, kesalahan Claude).

Saat memindahkan label gagal (model belum ada) ke llm_labels_1_4_GAGAL_model_belum_ada.jsonl, label SAH
dari run uji 5 tweet (60) dan 9 label awal run uji 3 tweet ikut terpindah. Skrip ini menyalin kembali
HANYA baris status "ok" yang belum ada di llm_labels_1_4.jsonl. Aman dijalankan berulang.
"""
import json
from pathlib import Path

d = Path(__file__).resolve().parents[1] / "dev_2025" / "data" / "interim"
src, dst = d / "llm_labels_1_4_GAGAL_model_belum_ada.jsonl", d / "llm_labels_1_4.jsonl"
if not src.exists():
    raise SystemExit("Tidak ada file sumber; tidak ada yang dipulihkan.")
ada = set()
if dst.exists():
    ada = {(r["prompt_hash"], r["tweet_id"]) for r in map(json.loads, dst.open(encoding="utf-8")) if r["status"] == "ok"}
baru = [r for r in map(json.loads, src.open(encoding="utf-8"))
        if r["status"] == "ok" and (r["prompt_hash"], r["tweet_id"]) not in ada]
with dst.open("a", encoding="utf-8") as fh:
    for r in baru:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"Dipulihkan {len(baru)} label sah.")
