"""Jalankan 2.4 -> perataan -> 3.1 -> 3.2 pada keluaran 2.3. Pakai: python -m modul3.run --masuk X.jsonl --keluar DIR"""
import argparse, csv, json, os, re
from collections import defaultdict
from .norm24 import pecah_record
from .flat3 import ratakan
from .org_er import resolusi_organisasi
from . import wilayah as W
from .konsol import Konsol, atribut_de, DE


def tulis_csv(path, rows):
    if not rows: open(path, "w").close(); return
    cols = list(rows[0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, set)) else v) for k, v in r.items()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--masuk", required=True); ap.add_argument("--keluar", required=True)
    ap.add_argument("--ambang-org", type=float, default=90)
    a = ap.parse_args(argv)
    os.makedirs(a.keluar, exist_ok=True)
    M, O, N, L, ORG, REL, TW = [], [], [], [], [], [], []
    for line in open(a.masuk, encoding="utf-8"):
        rec = json.loads(line)
        ms = pecah_record(rec)
        o, n, l, org, rel = ratakan(rec, ms)
        M += ms; O += o; N += n; L += l; ORG += org; REL += rel
        TW.append({"tweet_id": rec["tweet_id"], "created_at": rec["created_at"], "text_raw": rec.get("text_raw")})
    NAMA = W.muat(); IDX = W.indeks_kab(NAMA)
    for m in M:
        if m["kode_kab"]: m["kab_nama"] = NAMA.get(m["kode_kab"], m["kab_nama"])
    org_out, org_tab, org_log = resolusi_organisasi(ORG, a.ambang_org)
    for t in org_tab:       # kode wilayah organisasi: hanya bila nama wilayah cocok persis & tak ambigu
        c = IDX.get(re.sub(r"\s+", " ", t["wilayah_nama"] or ""), []) if t["wilayah_nama"] else []
        t["wilayah"] = c[0] if len(c) == 1 else None
    DE.n = 0
    k = Konsol(); k.jalankan(M)
    obj_m = defaultdict(list)
    for o in O: obj_m[o["mention_id"]].append(o)
    de_rows, anggota = [], []
    for de in k.de:
        at = atribut_de(de, obj_m, nama_wil=NAMA); de_rows.append(at)
        for m, aturan in de.anggota:
            anggota.append({"mention_id": m["mention_id"], "event_id": at["event_id"], "aturan": aturan})
    simpan = lambda nama, rows: tulis_csv(os.path.join(a.keluar, nama), rows)
    simpan("tweet.csv", TW)
    simpan("mention_lokasi.csv", [{"mention_id": m["mention_id"], "tweet_id": m["tweet_id"], "loc_id": l["id"]}
                                  for m in M for l in m["lokasi_detail"]])
    simpan("event_mention.csv", [{k_: v for k_, v in m.items() if k_ not in ("lokasi_detail", "text")} for m in M])
    simpan("affected_object.csv", O); simpan("humanitarian_need.csv", N); simpan("location.csv", L)
    simpan("organisasi_sebutan.csv", org_out); simpan("organization.csv", org_tab); simpan("relasi_organisasi.csv", REL)
    simpan("disaster_event.csv", de_rows); simpan("consolidated_into.csv", anggota)
    simpan("log_konsolidasi.csv", k.log); simpan("log_er_organisasi.csv", org_log)
    print(f"mention={len(M)} DE={len(de_rows)} anggota={len(anggota)} tidak_dikonsolidasi={len(k.tidak)} org_sebutan={len(ORG)} org_kanonik={len(org_tab)}")
    return k, de_rows


if __name__ == "__main__":
    main()
