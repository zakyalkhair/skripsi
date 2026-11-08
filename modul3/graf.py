"""3.3 Bangun baris node & relasi graf dari CSV keluaran modul3.run (murni Python, tanpa Neo4j)."""
import csv, json, os, re
from . import wilayah as W

LIST_KOLOM = {"admin_path", "admin_nama", "kode_provinsi", "kode_wilayah", "jenis_tambahan", "memenuhi_ambang", "alias"}
LEVEL = {2: "provinsi", 5: "kab_kota", 8: "kecamatan", 13: "desa"}


def baca(dir_, nama):
    p = os.path.join(dir_, nama)
    if not os.path.exists(p) or os.path.getsize(p) == 0: return []
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8")):
        o = {}
        for k, v in r.items():
            if v == "" or v is None: o[k] = None
            elif k in LIST_KOLOM: o[k] = json.loads(v)
            else: o[k] = v
        out.append(o)
    return out


def _f(x): return float(x) if x not in (None, "") else None
def _i(x):
    x = _f(x); return None if x is None else (int(x) if x == int(x) else x)
def _b(x): return str(x).lower() == "true"
def iso_dt(s): return s.replace(" ", "T") if s else s


def bangun(dir_, nama_wil=None):
    nama_wil = nama_wil if nama_wil is not None else W.muat()
    T = {r["tweet_id"]: r for r in baca(dir_, "tweet.csv")}
    EM, EMLOK = baca(dir_, "event_mention.csv"), baca(dir_, "mention_lokasi.csv")
    OB, ND, LOK = baca(dir_, "affected_object.csv"), baca(dir_, "humanitarian_need.csv"), baca(dir_, "location.csv")
    ORGS, ORG, REL = baca(dir_, "organisasi_sebutan.csv"), baca(dir_, "organization.csv"), baca(dir_, "relasi_organisasi.csv")
    DE, CI = baca(dir_, "disaster_event.csv"), baca(dir_, "consolidated_into.csv")

    g = {}
    g["tweets"] = [{"tweet_id": t["tweet_id"], "created_at": iso_dt(t["created_at"]), "text_raw": t["text_raw"]} for t in T.values()]
    g["mentions"] = [{"mention_id": m["mention_id"], "tweet_id": m["tweet_id"], "jenis": m["jenis"], "subtipe": m["subtipe"],
                      "tipe_laporan": m["tipe_laporan"], "kode_kab": m["kode_kab"], "tanggal_lokal": m["tanggal_lokal"],
                      "tanggal_akhir": m["tanggal_akhir"], "ketepatan": m["ketepatan"], "zona": m["zona"],
                      "magnitudo": _f(m["magnitudo"]), "di_luar_periode": _b(m["di_luar_periode"])} for m in EM]
    # Location: resolved + leluhur administratif (PART_OF)
    locs, part_of = {}, set()
    def simpul(gid, nama, level, path, lat=None, lon=None, sumber=None):
        n = locs.setdefault(gid, {"gazetteer_id": gid, "nama": nama, "level": level, "admin_path": path, "lat": lat, "lon": lon, "sumber": sumber})
        if nama and not n["nama"]: n["nama"] = nama
        return n
    kunci_loc = {}
    for l in LOK:
        gid = l["gazetteer_id"]; kunci_loc[(l["tweet_id"], l["loc_id"])] = gid
        path, nm = l["admin_path"] or [], l["admin_nama"] or []
        simpul(gid, l["nama"], l["level"], path, _f(l["lat"]), _f(l["lon"]), gid.split(":")[0])
        rantai = path[:-1] if gid.startswith("kemendagri:") else path
        for i, kode in enumerate(path):
            kid = "kemendagri:" + kode
            nama = (nm[i] if i < len(nm) and nm[i] else None) or nama_wil.get(kode)
            simpul(kid, nama, LEVEL.get(len(kode)), path[:i + 1], sumber="kemendagri")
        urut = ["kemendagri:" + k for k in path]
        if not gid.startswith("kemendagri:"): urut = urut + [gid]
        for a, b in zip(urut[1:], urut[:-1]): part_of.add((a, b))
    g["locations"] = list(locs.values())
    g["part_of"] = [{"anak": a, "induk": b} for a, b in sorted(part_of)]
    g["mentions_tweet_loc"] = [{"tweet_id": t, "gazetteer_id": gid} for (t, _), gid in sorted(set(kunci_loc.items()))]
    g["located_in"] = [{"mention_id": r["mention_id"], "gazetteer_id": kunci_loc[(r["tweet_id"], r["loc_id"])]}
                       for r in EMLOK if (r["tweet_id"], r["loc_id"]) in kunci_loc]
    g["affected"] = [{"mention_id": o["mention_id"], "id": f'{o["mention_id"]}_{o["obj_id"]}', "kelas": o["kelas"], "objek": o["objek"],
                      "status": o["status"], "jumlah": _i(o["jumlah"]), "satuan": o["satuan"],
                     "lokasi": kunci_loc.get((o["tweet_id"], o["lokasi"])), "tweet_id": o["tweet_id"]} for o in OB]
    g["needs"] = [{"mention_id": n["mention_id"], "id": f'{n["mention_id"]}_{n["need_id"]}', "kategori": n["kategori"], "item": n["item"],
                   "status": n["status"], "lokasi": kunci_loc.get((n["tweet_id"], n["lokasi"])), "tweet_id": n["tweet_id"]} for n in ND]
    g["organizations"] = [{"nama_kanonik": o["nama_kanonik"], "alias": o["alias"], "wilayah": o["wilayah"], "tingkat": o["tingkat"]} for o in ORG]
    kan = {(r["tweet_id"], r["org_id"]): r["nama_kanonik"] for r in ORGS}
    pemilik_ao = {}
    for o in OB: pemilik_ao[(o["tweet_id"], o["obj_id"])] = f'{o["mention_id"]}_{o["obj_id"]}'
    for n in ND: pemilik_ao[(n["tweet_id"], n["need_id"])] = f'{n["mention_id"]}_{n["need_id"]}'
    em_ids = {m["mention_id"] for m in EM}
    g["deployed_to"], g["handles"], g["evacuated_to"] = [], [], []
    for r in REL:
        org = kan.get((r["tweet_id"], r["from"]))
        if r["type"] == "HANDLES":
            tgt = pemilik_ao.get((r["tweet_id"], r["to"]))
            if org and tgt: g["handles"].append({"nama_kanonik": org, "id": tgt, "aksi": r["aksi"], "tweet_id": r["tweet_id"]})
        elif r["type"] == "DEPLOYED_TO":
            gid = kunci_loc.get((r["tweet_id"], r["to"]))
            if org and gid: g["deployed_to"].append({"nama_kanonik": org, "gazetteer_id": gid, "aksi": r["aksi"], "tweet_id": r["tweet_id"]})
        elif r["type"] == "EVACUATED_TO":
            gid = kunci_loc.get((r["tweet_id"], r["to"]))
            src = pemilik_ao.get((r["tweet_id"], r["from"])) or r["mention_id"]
            if gid and src: g["evacuated_to"].append({"sumber_id": src, "gazetteer_id": gid})
    g["handles_a"] = [h for h in g["handles"] if h["id"].rsplit("_", 1)[-1].startswith("A")]
    g["handles_n"] = [h for h in g["handles"] if h["id"].rsplit("_", 1)[-1].startswith("N")]
    del g["handles"]
    g["events"] = [{"event_id": d["event_id"], "nama": d["nama"], "jenis": d["jenis"], "jenis_tambahan": d["jenis_tambahan"] or [],
                    "start_time": d["start_time"], "end_time": d["end_time"], "status": d["status"],
                    "sumber_tanggal": d["sumber_tanggal"], "kode_provinsi": d["kode_provinsi"] or [], "kode_wilayah": d["kode_wilayah"] or []} for d in DE]
    g["consolidated"] = [{"mention_id": c["mention_id"], "event_id": c["event_id"], "aturan": c["aturan"]} for c in CI]
    return g


def ringkas(g):
    return {k: len(v) for k, v in g.items()}


if __name__ == "__main__":
    import sys
    g = bangun(sys.argv[1]); print(json.dumps(ringkas(g), indent=1))
