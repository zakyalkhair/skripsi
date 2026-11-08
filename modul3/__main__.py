"""Satu pintu: python -m modul3 <proses|muat|cq|semua> [opsi]
  proses  2.4 + perataan + 3.1 + 3.2  -> CSV      (tanpa Neo4j)
  muat    3.3 ingesti ke Neo4j                    (butuh .env)
  cq      3.4 lapis isi graf: 24 CQ               (butuh .env)
  semua   proses -> muat -> cq
"""
import argparse, sys
from . import run, muat, cq

MASUK = "dev_2025/data/processed/extraction_resolved_filter200_v6pangkas.jsonl"
KELUAR = "dev_2025/data/modul3"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perintah", choices=["proses", "muat", "cq", "semua"])
    ap.add_argument("--masuk", default=MASUK); ap.add_argument("--keluar", default=KELUAR)
    ap.add_argument("--bersihkan", action="store_true", help="kosongkan database sebelum muat")
    a = ap.parse_args()
    if a.perintah in ("proses", "semua"): run.main(["--masuk", a.masuk, "--keluar", a.keluar])
    if a.perintah in ("muat", "semua"): muat.main(["--data", a.keluar] + (["--bersihkan"] if a.bersihkan else []))
    if a.perintah in ("cq", "semua"): cq.main(["--jalankan"])


main()
