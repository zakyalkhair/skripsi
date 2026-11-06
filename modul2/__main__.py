"""CLI Modul 2 (prompt v3, 17 Okt 2026).

Contoh (dari folder skripsi, data pengembangan 2025):
  python -m modul2 ekstrak  --config config_modul2.yaml --limit 20          # uji kecepatan dulu
  python -m modul2 ekstrak  --config config_modul2.yaml --limit 2000
  python -m modul2 validasi --config config_modul2.yaml
  python -m modul2 estimasi --config config_modul2.yaml --target 2000
  python -m modul2 resolusi --config config_modul2.yaml      # 2.3 tahap administratif (butuh data/gazetir/wilayah.sql)
  python -m modul2 pilih --config config_modul2.yaml         # 2.3 pemilihan kandidat ambigu oleh LLM (butuh Ollama; --dry-run = cetak prompt saja)
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import time
from pathlib import Path

import yaml

from . import extract as X
from .validate import validate


def _cfg(path: str) -> tuple[dict, Path]:
    p = Path(path).resolve()
    return yaml.safe_load(p.read_text(encoding="utf-8")), p.parent


def _logger(logdir: Path, nama: str):
    logdir.mkdir(parents=True, exist_ok=True)
    fn = logdir / f"{nama}_{time.strftime('%Y%m%d-%H%M%S')}.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.FileHandler(fn, encoding="utf-8"), logging.StreamHandler()])
    return logging.getLogger("modul2").info


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="modul2")
    ap.add_argument("perintah", choices=["ekstrak", "validasi", "estimasi", "resolusi", "pilih"])
    ap.add_argument("--config", default="config_modul2.yaml")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="pilih: hanya cetak prompt, tanpa memanggil LLM")
    ap.add_argument("--target", type=int, default=2000, help="jumlah tweet untuk estimasi waktu")
    ap.add_argument("--fewshot", type=int, default=None, help="jumlah contoh few-shot (default semua)")
    a = ap.parse_args(argv)
    cfg, base = _cfg(a.config)
    P = {k: (base / v) for k, v in cfg["paths"].items()}
    log = _logger(P["logs_dir"], a.perintah)
    m = cfg["llm"]
    if a.perintah == "resolusi":
        from collections import Counter
        from .resolve import Gazetir, resolusi_record
        rs = cfg.get("resolusi", {})
        gaz = Gazetir(base / rs.get("gazetir_sql", "data/gazetir/wilayah.sql"),
                      Path(__file__).parent / "prompt" / "geo_abbrev.csv",
                      base / rs.get("titik_csv", "data/gazetir/titik_wilayah.csv"))
        out_p = base / rs.get("resolved", str(P["valid"]).replace("valid", "resolved"))
        log_p = base / rs.get("resolution_log", str(P["valid"]).replace("extraction_valid", "resolution_log").replace(".jsonl", ".csv"))
        from .osm import OsmIndex, kueri_detail, norm_osm
        osm_csv = base / rs.get("osm_csv", "data/gazetir/osm_feat.csv")
        dicari = set()
        for line in open(P["valid"], encoding="utf-8"):
            for loc in json.loads(line).get("location", []):
                q = kueri_detail(loc)
                if q:
                    dicari.add(norm_osm(q))
        osm = OsmIndex.muat(osm_csv, dicari)
        log(f"OSM: {'dimuat ' + str(sum(len(v) for v in osm.baris.values())) + ' baris untuk ' + str(len(dicari)) + ' kueri' if osm.ada else 'osm_feat.csv belum ada -> jalur detail dilewati'}")
        n = Counter(); baris = []
        with open(out_p, "w", encoding="utf-8") as fo:
            for line in open(P["valid"], encoding="utf-8"):
                rec, lg = resolusi_record(json.loads(line), gaz, osm)
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                baris += lg
        n.update(x["kode"] for x in baris)
        with open(log_p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["tweet_id", "loc_id", "teks", "kode", "status", "hasil", "level", "k", "metode"])
            w.writeheader(); w.writerows(baris)
        diresolusi = sum(v for k, v in n.items() if not k.startswith("S_"))
        log(f"Lokasi: {len(baris)} | dilewati (luar negeri / bukan tujuan relasi): {len(baris) - diresolusi} | diresolusi: {diresolusi}")
        log(f"Kode: {dict(n.most_common())}")
        log(f"-> {out_p} ; {log_p}")
        return

    if a.perintah == "pilih":
        from .pilih import jalankan
        from .resolve import Gazetir
        rs = cfg.get("resolusi", {})
        gaz = Gazetir(base / rs.get("gazetir_sql", "data/gazetir/wilayah.sql"),
                      Path(__file__).parent / "prompt" / "geo_abbrev.csv",
                      base / rs.get("titik_csv", "data/gazetir/titik_wilayah.csv"))
        inp = base / rs["resolved"]
        out = base / rs.get("dipilih", str(rs["resolved"]).replace("resolved", "dipilih"))
        raw = base / rs.get("pilih_raw", str(P["raw"]).replace("extraction_raw", "pilih_raw"))
        lg = base / rs.get("pilih_log", str(rs["resolution_log"]).replace("resolution_log", "pilih_log"))
        client = X.Client(m["base_url"], m["model"], api=m.get("api", "ollama"), timeout_s=m["timeout_s"],
                          num_ctx=rs.get("pilih_num_ctx", 4096))
        log(f"Pemilihan kandidat | model {m['model']} | masukan {inp.name}" + (" | DRY-RUN" if a.dry_run else ""))
        t0 = time.time()
        r = jalankan(inp, out, raw, lg, gaz, client, limit=a.limit, dry_run=a.dry_run, log=log)
        log(f"Dipanggil: {r['dipanggil']} | hasil: {r['hasil']} | {time.time()-t0:.0f} dtk")
        if not a.dry_run:
            log(f"-> {out} ; {lg} ; {raw}")
        return

    if a.perintah == "ekstrak":
        system = X.build_system(versi=cfg["prompt_versi"])
        few = X.load_fewshot(versi=cfg["prompt_versi"], n=a.fewshot)
        ph = X.prompt_hash(system, few, m["model"])
        client = X.Client(m["base_url"], m["model"], api=m.get("api", "ollama"), timeout_s=m["timeout_s"],
                          num_ctx=m["num_ctx"], api_key=os.getenv(m["api_key_env"]) if m.get("api_key_env") else None)
        rows = X.load_input(P["input"], a.limit or cfg.get("limit"), cfg.get("acak", True), cfg.get("seed", 42))
        log(f"Model {m['model']} ({m.get('api','ollama')}) | prompt {cfg['prompt_versi']} {ph} | few-shot {len(few)}")
        X.run(rows, client, P["raw"], system, few, m["max_tokens_tingkat"], ph, a.target, log)
        log(json.dumps(X.ringkas_waktu(P["raw"], a.target), ensure_ascii=False))

    elif a.perintah == "validasi":
        abbrev = X.load_abbrev()
        texts = {r["tweet_id"]: r for r in X.load_input(P["input"], None, False)}
        recs = [json.loads(l) for l in P["raw"].read_text(encoding="utf-8").splitlines() if l.strip()]
        n = 0
        with open(P["valid"], "w", encoding="utf-8") as fv, open(P["validation_log"], "w", newline="", encoding="utf-8") as fl:
            w = csv.DictWriter(fl, fieldnames=["tweet_id", "cek", "kode", "entitas", "detail"])
            w.writeheader()
            for r in recs:
                t = texts.get(str(r["tweet_id"]))
                if not t:
                    continue
                out, lg = validate(r["tweet_id"], t["text_raw"], r["raw"], abbrev)
                out.update({"created_at": r["created_at"], "text_raw": t["text_raw"], "status_2_1": r["status"]})
                fv.write(json.dumps(out, ensure_ascii=False) + "\n")
                w.writerows(lg)
                n += 1
        log(f"Validasi {n} tweet -> {P['valid']} ; log -> {P['validation_log']}")
        _ringkas_validasi(P["valid"], P["validation_log"], log)

    else:
        log(json.dumps(X.ringkas_waktu(P["raw"], a.target), ensure_ascii=False, indent=1))


def _ringkas_validasi(valid: Path, logcsv: Path, log) -> None:
    from collections import Counter
    v = [json.loads(l) for l in valid.read_text(encoding="utf-8").splitlines()]
    kode = Counter(r["kode"] for r in csv.DictReader(open(logcsv, encoding="utf-8")))
    jenis = Counter(m["jenis"] for r in v for m in r["event_mention"])
    log(f"Tweet: {len(v)} | punya kejadian: {sum(bool(r['event_mention']) for r in v)} | "
        f"kejadian {sum(jenis.values())}, lokasi {sum(len(r['location']) for r in v)}, "
        f"dampak {sum(len(r['affected_object']) for r in v)}, kebutuhan {sum(len(r['humanitarian_need']) for r in v)}, "
        f"lembaga {sum(len(r['organization']) for r in v)}")
    log(f"Jenis: {dict(jenis)}")
    log(f"Kode log terbanyak: {kode.most_common(12)}")
    # penanda v3 (dihitung per tweet, bukan per baris log)
    per_tweet: dict[str, set[str]] = {}
    for r in csv.DictReader(open(logcsv, encoding="utf-8")):
        per_tweet.setdefault(r["kode"], set()).add(r["tweet_id"])
    n_ev = sum(bool(r["event_mention"]) for r in v)
    for k in ("W_LOKASI_TANPA_RELASI", "W_ORG_TANPA_AKSI", "W_SLOT_TANPA_PENANDA", "W_JENIS_DI_LUAR_CAKUPAN",
              "W_KELAS_SINONIM", "W_JABATAN_TANPA_PEMETAAN", "E_SPAN_NOT_FOUND", "W_ORPHAN"):
        log(f"  {k}: {len(per_tweet.get(k, ()))} tweet (dari {n_ev} yang punya kejadian)")


if __name__ == "__main__":
    main()
