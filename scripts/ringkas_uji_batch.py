"""Ringkasan uji jumlah tweet per permintaan (5 vs 3, opsional 1) pada data pengembangan 2025.

    python scripts/ringkas_uji_batch.py

Membaca dev_2025/data/interim/llm_labels_1_4.jsonl, memisahkan run per prompt_hash (5 = utama,
3 = profil qwen_b3, 1 = qwen_b1), lalu mencetak & menulis dev_2025/reports/uji_batch_2025.json:
- tweet berlabel, status percobaan pertama (gagal/hilang), jumlah kirim ulang, sumber akhir
- waktu per permintaan & per tweet (dari selisih collected_at antar permintaan)
- kesepakatan label antar-run pada tweet yang sama (persen setuju + kappa)
Akurasi terhadap label manusia dihitung terpisah setelah anotasi selesai.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modul1.filter_llm import cohen_kappa, load_labels, load_system_prompt, prompt_hash  # noqa: E402
from modul1.io_utils import apply_profil, load_config  # noqa: E402

runs = {}
for nama, profil in [("5", None), ("3", "qwen_b3"), ("1", "qwen_b1")]:
    cfg = load_config(ROOT / "config_2025.yaml", ROOT / "dev_2025")
    apply_profil(cfg, profil)
    runs[nama] = prompt_hash(load_system_prompt(cfg), cfg)
labels = pd.DataFrame(load_labels(cfg.paths.llm_labels))
if labels.empty:
    sys.exit("Belum ada label. Jalankan uji dulu (scripts/uji_batch_2025.ps1).")
labels["t"] = pd.to_datetime(labels["collected_at"], utc=True, format="mixed")

hasil, akhir = {}, {}
for nama, ph in runs.items():
    g = labels[labels["prompt_hash"] == ph]
    if g.empty:
        continue
    pertama = g[g.get("percobaan").isna()] if "percobaan" in g else g
    ulang = g[g["percobaan"] == "ulang_satu"] if "percobaan" in g else g.iloc[0:0]
    req = pertama.groupby("chunk")["t"].min().sort_values()
    dt = req.diff().dt.total_seconds().dropna()
    dt = dt[dt < 1800]  # abaikan jeda panjang (run dihentikan/dilanjutkan)
    per_req = float(dt.median()) if len(dt) else None
    ok = g[g["status"] == "ok"].sort_values("t").groupby("tweet_id")["label"].last()
    akhir[nama] = ok
    hasil[nama] = {
        "tweet_per_permintaan": int(nama),
        "tweet_dikirim": int(pertama["tweet_id"].nunique()),
        "permintaan": int(pertama["chunk"].nunique()),
        "status_percobaan_pertama": pertama["status"].value_counts().to_dict(),
        "persen_gagal_percobaan_pertama": round(100 * (pertama["status"] != "ok").mean(), 1),
        "dikirim_ulang_satu": int(ulang["tweet_id"].nunique()),
        "tetap_gagal_setelah_ulang": int(len(set(ulang["tweet_id"]) - set(ok.index))),
        "label_ok": int(len(ok)),
        "persen_informatif": round(100 * (ok == "informatif").mean(), 1) if len(ok) else None,
        "median_detik_per_permintaan": round(per_req, 1) if per_req else None,
        "perkiraan_detik_per_tweet": round(per_req / int(nama), 1) if per_req else None,
    }

banding = {}
names = list(akhir)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = akhir[names[i]], akhir[names[j]]
        common = a.index.intersection(b.index)
        if len(common):
            la, lb = a[common].tolist(), b[common].tolist()
            banding[f"{names[i]}_vs_{names[j]}"] = {
                "tweet_sama": len(common),
                "persen_setuju": round(100 * sum(x == y for x, y in zip(la, lb)) / len(common), 1),
                "kappa": None if (k := cohen_kappa(la, lb)) is None else round(k, 3),
                "beda_tweet_id": [t for t, x, y in zip(common, la, lb) if x != y],
            }

out = {"run": hasil, "kesepakatan": banding}
(ROOT / "dev_2025" / "reports" / "uji_batch_2025.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=2, ensure_ascii=False))
