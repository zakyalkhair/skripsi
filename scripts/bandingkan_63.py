"""Bandingkan hasil ekstraksi 63 tweet: prompt v2 (asli), v2 divalidasi ulang dengan 2.2 baru, dan prompt v3.

Jalankan dari folder skripsi:
  python scripts/bandingkan_63.py
Keluaran: tabel di layar + dev_2025/reports/perbandingan_v2_v3.csv + daftar perbedaan per tweet
(dev_2025/reports/perbandingan_v2_v3_per_tweet.csv). Hanya membaca data pengembangan 2025.

Tiga kolom:
  v2_asli        : keluaran lama dengan validasi 2.2 LAMA (file extraction_valid_63.jsonl)
  v2_val_baru    : keluaran lama (extraction_raw_63.jsonl) dengan validasi 2.2 BARU -> pembanding adil untuk v3
  v3             : keluaran prompt v3 dengan validasi 2.2 baru
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from modul2 import extract as X  # noqa: E402
from modul2.validate import validate  # noqa: E402

P = {
    "v2_valid": ROOT / "dev_2025/data/processed/extraction_valid_63.jsonl",
    "v2_raw": ROOT / "dev_2025/data/interim/extraction_raw_63.jsonl",
    "v2_log": ROOT / "dev_2025/reports/validation_log_63.csv",
    "v3_valid": ROOT / "dev_2025/data/processed/extraction_valid_63_v3.jsonl",
    "v3_raw": ROOT / "dev_2025/data/interim/extraction_raw_63_v3.jsonl",
    "v3_log": ROOT / "dev_2025/reports/validation_log_63_v3.csv",
    "out": ROOT / "dev_2025/reports/perbandingan_v2_v3.csv",
    "out_tweet": ROOT / "dev_2025/reports/perbandingan_v2_v3_per_tweet.csv",
}


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def revalidasi(raw_path: Path, teks: dict[str, str]) -> tuple[list[dict], list[dict]]:
    ab = X.load_abbrev()
    out, logs = [], []
    for r in jl(raw_path):
        t = teks.get(str(r["tweet_id"]))
        if t is None:
            continue
        o, lg = validate(str(r["tweet_id"]), t, r["raw"], ab)
        o["text_raw"] = t
        out.append(o)
        logs += lg
    return out, logs


def baca_log(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8")))


def metrik(valid: list[dict], log: list[dict], raw: list[dict] | None) -> dict:
    ev = [r for r in valid if r["event_mention"]]
    per_kode: dict[str, set] = {}
    for x in log:
        per_kode.setdefault(x["kode"], set()).add(x["tweet_id"])
    n_lines = Counter(x["kode"] for x in log)

    def tanpa_relasi(r: dict) -> bool:
        lok = [l for l in r["location"] if not l.get("luar_negeri")]
        return bool(r["event_mention"] and lok and not any(q["type"] == "LOCATED_IN" for q in r["relations"]))

    kelas = Counter(a["kelas"] for r in valid for a in r["affected_object"])
    m = {
        "tweet_total": len(valid),
        "tweet_punya_kejadian": len(ev),
        "kejadian": sum(len(r["event_mention"]) for r in valid),
        "kejadian_faktualitas_prediksi": sum(1 for r in valid for e in r["event_mention"] if e.get("faktualitas") == "prediksi"),
        "lokasi": sum(len(r["location"]) for r in valid),
        "lokasi_dengan_slot_wilayah_terisi": sum(1 for r in valid for l in r["location"] if any(l.get(k) for k in ("provinsi", "kab_kota", "kecamatan", "desa"))),
        "lokasi_dengan_wilayah_dugaan": sum(1 for r in valid for l in r["location"] if l.get("wilayah_dugaan")),
        "petunjuk_wilayah": sum(len(r.get("petunjuk_wilayah", [])) for r in valid),
        "dampak": sum(len(r["affected_object"]) for r in valid),
        "dampak_yatim": sum(1 for r in valid for a in r["affected_object"] if a.get("orphan")),
        "kebutuhan": sum(len(r["humanitarian_need"]) for r in valid),
        "lembaga": sum(len(r["organization"]) for r in valid),
        "lembaga_dari_jabatan": sum(1 for r in valid for o in r["organization"] if o.get("dari_jabatan")),
        "relasi": sum(len(r["relations"]) for r in valid),
        "TWEET_KEJADIAN_DAN_LOKASI_TANPA_RELASI": sum(tanpa_relasi(r) for r in valid),
        "tweet_dengan_lembaga_tanpa_aksi": len(per_kode.get("W_ORG_TANPA_AKSI", ())),
        "tweet_span_tidak_ditemukan": len(per_kode.get("E_SPAN_NOT_FOUND", ())),
        "baris_E_SPAN_NOT_FOUND": n_lines.get("E_SPAN_NOT_FOUND", 0),
        "baris_E_REL_DANGLING": n_lines.get("E_REL_DANGLING", 0),
        "baris_E_ENUM_total": sum(v for k, v in n_lines.items() if k.startswith("E_ENUM")),
        "baris_E_total": sum(v for k, v in n_lines.items() if k.startswith("E_")),
        "baris_W_ORPHAN": n_lines.get("W_ORPHAN", 0),
        "kelas_dampak": dict(kelas),
    }
    if raw:
        d = [r["durasi_s"] for r in raw]
        m["detik_median_per_tweet"] = round(statistics.median(d[1:] or d), 1)
        m["jam_total"] = round(sum(d) / 3600, 2)
        m["status_2_1"] = dict(Counter(r["status"] for r in raw))
        m["token_keluar_median"] = statistics.median([r.get("completion_tokens") or 0 for r in raw])
    return m


def main() -> None:
    v2 = jl(P["v2_valid"])
    teks = {str(r["tweet_id"]): r["text_raw"] for r in v2}
    v2_raw = jl(P["v2_raw"])
    v2r, v2r_log = revalidasi(P["v2_raw"], teks)
    cols = {"v2_asli": metrik(v2, baca_log(P["v2_log"]), v2_raw),
            "v2_val_baru": metrik(v2r, v2r_log, v2_raw)}
    if P["v3_valid"].exists():
        cols["v3"] = metrik(jl(P["v3_valid"]), baca_log(P["v3_log"]), jl(P["v3_raw"]) if P["v3_raw"].exists() else None)
    else:
        print("(belum ada hasil v3: jalankan ekstrak dan validasi dengan config_modul2_63_v3.yaml)")
    keys = list(cols["v2_asli"].keys()) + [k for k in ("detik_median_per_tweet",) if False]
    for c in cols.values():
        for k in c:
            if k not in keys:
                keys.append(k)
    w = max(len(k) for k in keys)
    print(f"{'metrik':<{w}}  " + "  ".join(f"{c:>14}" for c in cols))
    with open(P["out"], "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["metrik", *cols])
        for k in keys:
            vals = [cols[c].get(k, "") for c in cols]
            print(f"{k:<{w}}  " + "  ".join(f"{str(v):>14}" for v in vals) if not isinstance(vals[0], dict)
                  else f"{k:<{w}}  " + " | ".join(str(v) for v in vals))
            wr.writerow([k, *[json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for v in vals]])
    print("\n->", P["out"])
    if "v3" in cols:
        v3 = {str(r["tweet_id"]): r for r in jl(P["v3_valid"])}
        base = {str(r["tweet_id"]): r for r in v2r}
        with open(P["out_tweet"], "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["no", "tweet_id", "kejadian_v2", "kejadian_v3", "lokasi_v2", "lokasi_v3", "dampak_v2", "dampak_v3",
                         "relasi_v2", "relasi_v3", "teks"])
            for i, (tid, a) in enumerate(base.items(), 1):
                b = v3.get(tid)
                if not b:
                    continue
                wr.writerow([i, tid, len(a["event_mention"]), len(b["event_mention"]), len(a["location"]), len(b["location"]),
                             len(a["affected_object"]), len(b["affected_object"]), len(a["relations"]), len(b["relations"]),
                             a["text_raw"][:120].replace("\n", " ")])
        beda = [tid for tid, a in base.items() if tid in v3 and bool(a["event_mention"]) != bool(v3[tid]["event_mention"])]
        print(f"Tweet yang status 'ada kejadian' berubah: {len(beda)}")
        for tid in beda:
            print(" ", tid, "v2:", len(base[tid]["event_mention"]), "-> v3:", len(v3[tid]["event_mention"]), "|", base[tid]["text_raw"][:90].replace("\n", " "))
        print("->", P["out_tweet"])


if __name__ == "__main__":
    main()
