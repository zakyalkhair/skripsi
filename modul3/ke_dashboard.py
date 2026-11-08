"""Ekspor hasil Modul 3 ke format file dashboard (dashboard/data/<nama>/graf.json + gazetteer.json).
Pemetaan: jenis nama pipeline -> nama dashboard; kode kab '35.08' -> '3508'; MENTIONS dashboard = LOCATED_IN pipeline (EventMention -> Location);
LOCATED_IN dashboard = PART_OF pipeline (Location -> induk). Hanya EventMention yang sudah terkonsolidasi ke DisasterEvent yang diekspor."""
import argparse, json, os, re
from collections import defaultdict
from .graf import bangun
from . import wilayah as W

JENIS = {"banjir": "banjir", "tanah_longsor": "longsor", "cuaca_ekstrem": "cuaca", "karhutla": "karhutla", "gempabumi": "gempa", "erupsi": "erupsi"}
TINGKAT_ORG = {"nasional": "nasional", "provinsi": "provinsi", "kab": "kabupaten", "kec": "kecamatan", "desa": "desa"}


def k4(kode): return kode.replace(".", "") if kode else None


def tingkat_lokasi(gid, level, nama):
    if gid.startswith("kemendagri:"):
        return {"prov": "provinsi", "kab": "kota" if (nama or "").lower().startswith("kota") else "kabupaten", "kec": "kecamatan", "desa": "desa"}.get(level, "desa")
    n = (nama or "").lower()
    return "jalan" if re.match(r"(jalan|jl\b)", n) else "jembatan" if "jembatan" in n else "gunung" if re.match(r"(gunung|gn\b)", n) else "bangunan"


def ekspor(dir_in, dir_out, label="Data Pipeline", keterangan=""):
    g = bangun(dir_in); NAMA = W.muat()
    ev_ok = {e["event_id"] for e in g["events"]}
    em_ke_de = {c["mention_id"]: c["event_id"] for c in g["consolidated"] if c["event_id"] in ev_ok}
    EM = [m for m in g["mentions"] if m["mention_id"] in em_ke_de and m["kode_kab"]]
    em_ids = {m["mention_id"] for m in EM}
    tw_ids = {m["tweet_id"] for m in EM}
    nodes = {"Tweet": [], "EventMention": [], "DisasterEvent": [], "Location": [], "AffectedObject": [], "HumanitarianNeed": [], "Organization": []}
    rels = []
    for t in g["tweets"]:
        if t["tweet_id"] in tw_ids:
            nodes["Tweet"].append({"tweet_id": t["tweet_id"], "upload": t["created_at"], "text": t["text_raw"], "url": f"https://x.com/i/web/status/{t['tweet_id']}"})
    for m in EM:
        nodes["EventMention"].append({"mention_id": m["mention_id"], "jenis": JENIS[m["jenis"]], "kode_kab": k4(m["kode_kab"]), "tanggal_lokal": m["tanggal_lokal"]})
        rels.append({"type": "REPORTS", "from": m["tweet_id"], "to": m["mention_id"]})
        rels.append({"type": "CONSOLIDATED_INTO", "from": m["mention_id"], "to": em_ke_de[m["mention_id"]]})
    dipakai_de = set(em_ke_de[m["mention_id"]] for m in EM)
    for e in g["events"]:
        if e["event_id"] in dipakai_de:
            nodes["DisasterEvent"].append({"event_id": e["event_id"], "nama": e["nama"], "jenis": JENIS[e["jenis"]], "start_time": e["start_time"], "end_time": e["end_time"], "status": e["status"]})
    loc_all = {l["gazetteer_id"]: l for l in g["locations"]}
    diacu = set()
    for x in g["located_in"]:
        if x["mention_id"] in em_ids: rels.append({"type": "MENTIONS", "from": x["mention_id"], "to": x["gazetteer_id"]}); diacu.add(x["gazetteer_id"])
    aff = [a for a in g["affected"] if a["mention_id"] in em_ids]; need = [n for n in g["needs"] if n["mention_id"] in em_ids]
    for a in aff:
        if a["lokasi"]: diacu.add(a["lokasi"])
        nodes["AffectedObject"].append({"id": a["id"], "kelas": a["kelas"], "status": a["status"], "jumlah": a["jumlah"], "satuan": a["satuan"], "lokasi": a["lokasi"], "objek": a["objek"]})
        rels.append({"type": "AFFECTED", "from": a["mention_id"], "to": a["id"]})
    for n in need:
        if n["lokasi"]: diacu.add(n["lokasi"])
        nodes["HumanitarianNeed"].append({"id": n["id"], "kategori": n["kategori"], "item": n["item"], "status": n["status"], "lokasi": n["lokasi"]})
        rels.append({"type": "REQUIRES", "from": n["mention_id"], "to": n["id"]})
    for ev in g["evacuated_to"]:
        if ev["sumber_id"] in em_ids: rels.append({"type": "EVACUATED_TO", "from": ev["sumber_id"], "to": ev["gazetteer_id"]}); diacu.add(ev["gazetteer_id"])
    ids_ao = {a["id"] for a in aff} | {n["id"] for n in need}
    org_id, orgs = {}, {o["nama_kanonik"]: o for o in g["organizations"]}
    def oid(nama):
        if nama not in org_id:
            org_id[nama] = f"ORG{len(org_id) + 1:03d}"; o = orgs.get(nama, {})
            nodes["Organization"].append({"id": org_id[nama], "nama_kanonik": nama, "wilayah": o.get("wilayah"), "tingkat": TINGKAT_ORG.get(o.get("tingkat"), o.get("tingkat"))})
        return org_id[nama]
    for h in g["handles_a"] + g["handles_n"]:
        if h["id"] in ids_ao: rels.append({"type": "HANDLES", "from": oid(h["nama_kanonik"]), "to": h["id"], "props": {"aksi": h["aksi"], "sumber": h["tweet_id"]}})
    for d in g["deployed_to"]:
        if d["tweet_id"] in tw_ids and d["gazetteer_id"] in diacu | set(loc_all):
            rels.append({"type": "DEPLOYED_TO", "from": oid(d["nama_kanonik"]), "to": d["gazetteer_id"], "props": {"aksi": d["aksi"], "sumber": d["tweet_id"]}}); diacu.add(d["gazetteer_id"])
    # Location: yang dirujuk + leluhurnya (untuk hierarki)
    induk = defaultdict(set)
    for p in g["part_of"]: induk[p["anak"]].add(p["induk"])
    perlu, antre = set(), list(diacu)
    while antre:
        x = antre.pop()
        if x in perlu or x not in loc_all: continue
        perlu.add(x); antre += list(induk[x])
    gaz = {}
    for gid in sorted(perlu):
        l = loc_all[gid]; path = l["admin_path"] or []
        nama = l["nama"] or NAMA.get(path[-1] if path else "", gid)
        nm = " > ".join(NAMA.get(c, c) for c in path[:2]) if path else ""
        coords = {"latitude": l["lat"], "longitude": l["lon"]} if l["lat"] is not None and l["lon"] is not None and l["level"] not in ("prov", "kab") else None
        nodes["Location"].append({"gazetteer_id": gid, "nama": nama, "admin_path": nm + (" > " + nama if gid.startswith("kemendagri:") and len(path) > 2 else ""), "coordinates": coords})
        kab = next((c for c in path if len(c) == 5), None)
        gaz[gid] = {"tingkat": tingkat_lokasi(gid, l["level"], nama), "kode_kab": k4(kab) if kab else None}
        for ind in induk[gid]:
            if ind in perlu: rels.append({"type": "LOCATED_IN", "from": gid, "to": ind})
    os.makedirs(dir_out, exist_ok=True)
    meta = {"label": label, "keterangan": keterangan, "contoh": False}
    json.dump({"metadata": meta, "nodes": nodes, "relationships": rels}, open(os.path.join(dir_out, "graf.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(gaz, open(os.path.join(dir_out, "gazetteer.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {k: len(v) for k, v in nodes.items()} | {"relasi": len(rels)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--masuk", default="dev_2025/data/modul3"); ap.add_argument("--keluar", default="dashboard/data/nyata")
    ap.add_argument("--label", default="Hasil pipeline (sampel pengembangan 2025)")
    ap.add_argument("--keterangan", default="Hasil Modul 1-3 pada sampel kecil; bukan pemantauan bencana nyata.")
    a = ap.parse_args(); print(ekspor(a.masuk, a.keluar, a.label, a.keterangan))
