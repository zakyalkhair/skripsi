"""Tulis data dummy BESAR dari parquet crawl -> dashboard/data/contoh_besar/*.json (butuh pandas + pyarrow).

Teks & waktu berasal dari tweet hasil crawl (handle, tautan, dan id asli dihapus). Kab/kota, titik lokasi,
dan pengelompokan kejadian SEBAGIAN dikarang: dipakai untuk menguji dashboard pada volume besar, BUKAN hasil
ekstraksi dan bukan data bencana yang sah. Kekeringan tidak dipakai karena bukan jenis di dashboard.
Pakai: CONTOH_DIR=data/contoh_besar GAZETTEER_FILE=data/contoh_besar/gazetteer.json (lihat README).
"""
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / "data" / "contoh_besar"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
JENIS = {"GP": "gempa", "KH": "karhutla", "BJ": "banjir", "CE": "cuaca"}
NAMA_JENIS = {"gempa": "Gempabumi", "karhutla": "Kebakaran Lahan", "banjir": "Banjir", "cuaca": "Cuaca Ekstrem"}
RELEVAN = {"gempa": r"gempa|lindu", "karhutla": r"karhutla|kebakaran|terbakar|asap|\bapi\b",
           "banjir": r"banjir|\brob\b|tergenang|terendam", "cuaca": r"angin|puting|cuaca|hujan|badai"}
BOBOT = {"gempa": 0.4, "karhutla": 0.3, "cuaca": 0.2, "banjir": 0.1}  # porsi tiap jenis; sisa kuota dialihkan
MAKS_BMKG = 150  # laporan otomatis BMKG sangat banyak dan seragam
TIAP_KEJADIAN = 40  # laporan per kejadian sebelum dipecah ke kejadian berikutnya di kab/kota yang sama

DAMPAK = re.compile(r"(\d[\d.]*)\s*(rumah|warga|jiwa|orang|KK|hektare|hektar|ha|bangunan)\b(?:\s+(rusak|terendam|terbakar|mengungsi|meninggal))?", re.I)
KELAS = {"rumah": ("rumah", "unit"), "bangunan": ("bangunan", "unit"), "warga": ("penduduk", "jiwa"), "jiwa": ("penduduk", "jiwa"),
         "orang": ("penduduk", "jiwa"), "kk": ("penduduk", "KK"), "hektare": ("lahan", "hektare"), "hektar": ("lahan", "hektare"), "ha": ("lahan", "hektare")}
KEBUTUHAN = {"air bersih": "logistik", "masker": "logistik", "sembako": "logistik", "selimut": "logistik", "tenda": "hunian",
             "terpal": "hunian", "obat": "kesehatan", "relawan": "personel"}
ORG = {"BNPB": "nasional", "Basarnas": "nasional", "PMI": "nasional", "Manggala Agni": "nasional", "BPBD": "provinsi"}


def bersih(t: str) -> str:
    t = re.sub(r"https?://\S+", "", t)
    return re.sub(r"\s+", " ", re.sub(r"@\w+", "@pengguna", t)).strip()


def dalam(pt, cincin) -> bool:
    x, y, ok = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(cincin, cincin[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ok = not ok
    return ok


def titik_acak(rng, geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    luar = max((p[0] for p in polys), key=len)
    xs, ys = [c[0] for c in luar], [c[1] for c in luar]
    for _ in range(300):
        p = (rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)))
        if dalam(p, luar):
            return p
    return luar[0][0], luar[0][1]


def pilih_tweet() -> pd.DataFrame:
    d = pd.read_parquet(REPO / "data" / "processed" / "input_1_4.parquet")
    hasil = pd.read_parquet(REPO / "data" / "processed" / "hasil_1_4_ollama_qwen.parquet")
    bukan = set(hasil.loc[hasil.label.notna() & (hasil.label != "informatif"), "tweet_id"])
    d = d[~d.tweet_id.isin(bukan)].copy()
    d["ev"] = d.event_id.map(lambda e: next((x for x in e if x[:2] in JENIS), None))
    d = d[d.ev.notna()]
    d["jenis"] = d.ev.str[:2].map(JENIS)
    d = d[[bool(re.search(RELEVAN[j], t, re.I)) for j, t in zip(d.jenis, d.text_raw)]]
    bmkg = d.text_raw.str.contains("#BMKG", regex=False)
    d = pd.concat([d[~bmkg], d[bmkg].sample(min(MAKS_BMKG, int(bmkg.sum())), random_state=7)])
    bagian = []
    for j, b in BOBOT.items():
        g = d[d.jenis == j]
        bagian.append(g.sample(min(len(g), round(N * b)), random_state=7))
    pilih = pd.concat(bagian)
    if len(pilih) < N:
        sisa = d.drop(pilih.index)
        pilih = pd.concat([pilih, sisa.sample(min(len(sisa), N - len(pilih)), random_state=7)])
    return pilih.sort_values("created_at").reset_index(drop=True)


def main() -> None:
    rng = random.Random(7)
    wil = json.loads((ROOT / "data" / "wilayah.json").read_text(encoding="utf-8"))
    geo = {f["properties"]["kode_kab"]: f["geometry"] for f in
           json.loads((ROOT / "frontend" / "public" / "geo" / "kabkota.geojson").read_text(encoding="utf-8"))["features"]}
    with open(REPO / "config" / "kejadian.csv", encoding="utf-8") as f:
        kej = {r["event_id"]: r for r in csv.DictReader(f)}
    per_prov = defaultdict(list)
    for w in wil:
        w["pendek"] = re.sub(r"^(Kab\.|Kota)\s+", "", w["nama"]).lower()
        per_prov[w["provinsi"].lower()].append(w)
    wmap = {w["kode_kab"]: w for w in wil}

    def tentukan_kab(ev: str, teks: str) -> dict:
        calon = per_prov[kej[ev]["wilayah"].lower()]
        assert calon, f"provinsi tidak dikenal: {kej[ev]['wilayah']}"
        cocok = [w for w in calon if re.search(rf"\b{re.escape(w['pendek'])}\b", teks, re.I)]
        if cocok:
            return rng.choice(cocok)
        alias = [a.lower() for a in kej[ev]["alias_wilayah"].split(";")]
        dekat = [w for w in calon if w["pendek"] in alias]
        return rng.choice(dekat) if dekat and rng.random() < 0.5 else rng.choice(calon)  # dummy

    nodes = {k: [] for k in ("Tweet", "EventMention", "DisasterEvent", "Location", "AffectedObject", "HumanitarianNeed", "Organization")}
    rels, gaz, lok_kab, kejadian, org_id = [], {}, {}, {}, {}

    def lokasi(kode: str) -> list[str]:
        if kode not in lok_kab:
            w, ids = wmap[kode], []
            g = f"kab:{kode}"
            nodes["Location"].append({"gazetteer_id": g, "nama": w["nama"], "admin_path": f"{w['provinsi']} > {w['nama']}", "coordinates": None})
            gaz[g] = {"tingkat": "kabupaten", "kode_kab": kode}
            for i in range(1, rng.randint(3, 7) + 1):
                tingkat = rng.choice(("kecamatan", "desa", "desa", "jalan"))
                nama = f"{tingkat.capitalize()} Contoh {i} {w['pendek'].title()}"
                gid = f"dummy:{kode}/{i}"
                lon, lat = titik_acak(rng, geo[kode])
                nodes["Location"].append({"gazetteer_id": gid, "nama": nama, "admin_path": f"{w['provinsi']} > {w['nama']} > {nama}",
                                          "coordinates": {"latitude": round(lat, 5), "longitude": round(lon, 5)}})
                gaz[gid] = {"tingkat": tingkat, "kode_kab": kode}
                rels.append({"type": "LOCATED_IN", "from": gid, "to": g})
                ids.append(gid)
            lok_kab[kode] = ids
        return lok_kab[kode]

    tw = pilih_tweet()
    for i, r in enumerate(tw.itertuples(), 1):
        teks = bersih(r.text_raw)
        w = tentukan_kab(r.ev, teks)
        kode, ts = w["kode_kab"], r.created_at.tz_convert("Asia/Jakarta")
        tid, mid, tgl = f"TD{i:04d}", f"EMD{i:04d}", ts.date().isoformat()
        titik = lokasi(kode)
        terpilih = [f"kab:{kode}"] if rng.random() < 0.2 else rng.sample(titik, rng.choice((1, 1, 2)))
        ke = kejadian.setdefault((r.ev, kode), {"ids": {}, "bagian": 1, "n": 0})
        if ke["n"] >= TIAP_KEJADIAN:
            ke.update(bagian=ke["bagian"] + 1, n=0)
        ke["n"] += 1
        eid = f"DD-{r.ev}-{kode}-{ke['bagian']}"
        ke["ids"].setdefault(eid, []).append(tgl)
        nodes["Tweet"].append({"tweet_id": tid, "upload": ts.isoformat(timespec="seconds"), "text": teks, "url": None})
        nodes["EventMention"].append({"mention_id": mid, "jenis": r.jenis, "kode_kab": kode, "tanggal_lokal": tgl})
        rels += [{"type": "REPORTS", "from": tid, "to": mid}, {"type": "CONSOLIDATED_INTO", "from": mid, "to": eid}]
        rels += [{"type": "MENTIONS", "from": mid, "to": g} for g in terpilih]
        lok1 = next((g for g in terpilih if not g.startswith("kab:")), None)
        for j, m in enumerate(list(DAMPAK.finditer(teks))[:2], 1):
            angka = m.group(1).replace(".", "")
            if not angka:
                continue
            kelas, sat = KELAS[m.group(2).lower()]
            aid = f"AOD{i:04d}-{j}"
            nodes["AffectedObject"].append({"id": aid, "kelas": kelas, "status": (m.group(3) or "terdampak").lower(), "jumlah": int(angka), "satuan": sat})
            rels.append({"type": "AFFECTED", "from": mid, "to": aid})
            if lok1:
                rels.append({"type": "LOCATED_IN", "from": aid, "to": lok1})
        for item, kat in KEBUTUHAN.items():
            if re.search(rf"\b(butuh|dibutuhkan|kebutuhan|perlu)\b.*\b{item}\b", teks, re.I):
                hid = f"HND{i:04d}-{item.replace(' ', '')}"
                nodes["HumanitarianNeed"].append({"id": hid, "kategori": kat, "item": item, "status": "demanded", "lokasi": lok1})
                rels.append({"type": "REQUIRES", "from": mid, "to": hid})
        for nama, tingkat in ORG.items():
            if re.search(rf"\b{nama}\b", teks):
                kanon = f"{nama} {w['provinsi']}" if tingkat == "provinsi" else nama
                if kanon not in org_id:
                    org_id[kanon] = f"ORGD{len(org_id) + 1:03d}"
                    nodes["Organization"].append({"id": org_id[kanon], "nama_kanonik": kanon, "wilayah": w["provinsi"] if tingkat == "provinsi" else "Indonesia", "tingkat": tingkat})
                rels.append({"type": "HANDLES", "from": org_id[kanon], "to": mid})
    for (ev, kode), ke in kejadian.items():
        j = JENIS[ev[:2]]
        for k, (eid, tgl) in enumerate(ke["ids"].items(), 1):
            nama = f"{NAMA_JENIS[j]} {wmap[kode]['nama']}" + (f" (bagian {k})" if k > 1 else "")
            nodes["DisasterEvent"].append({"event_id": eid, "nama": nama, "jenis": j, "start_time": min(tgl), "end_time": max(tgl), "status": "tidak"})
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"label": "Data Contoh", "keterangan": "Data dummy dari teks crawl; lokasi dan pengelompokan kejadian dikarang, bukan pemantauan bencana nyata."}
    (OUT / "graf.json").write_text(json.dumps({"metadata": meta, "nodes": nodes, "relationships": rels}, ensure_ascii=False), encoding="utf-8")
    (OUT / "gazetteer.json").write_text(json.dumps(gaz, ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in nodes.items()}, "rel", len(rels), "kab", len(lok_kab), "jenis", tw.jenis.value_counts().to_dict())


if __name__ == "__main__":
    main()
