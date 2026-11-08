"""Perataan: keluaran 2.4 + record -> tabel objek, kebutuhan, lokasi, organisasi, relasi organisasi."""


def ratakan(rec, mentions):
    objs = {a["id"]: a for a in rec.get("affected_object", [])}
    needs = {n["id"]: n for n in rec.get("humanitarian_need", [])}
    locs = {l["id"]: l for l in rec.get("location", [])}
    tid = rec["tweet_id"]
    o_rows, n_rows, l_rows, org_rows, rel_rows = [], [], [], [], []
    pemilik = {}
    for m in mentions:
        for i in m["objek_ids"]:
            o = objs[i]
            o_rows.append({"mention_id": m["mention_id"], "tweet_id": tid, "obj_id": i, "kelas": o.get("kelas"), "objek": o.get("objek"),
                           "status": o.get("status"), "jumlah": o.get("jumlah"), "satuan": o.get("satuan"), "lokasi": o.get("lokasi")})
            pemilik[i] = m["mention_id"]
        for i in m["kebutuhan_ids"]:
            n = needs[i]
            n_rows.append({"mention_id": m["mention_id"], "tweet_id": tid, "need_id": i, "kategori": n.get("kategori"),
                           "item": n.get("item"), "status": n.get("status"), "lokasi": n.get("lokasi")})
            pemilik[i] = m["mention_id"]
    for lid, l in locs.items():
        r = l.get("resolution") or {}
        if r.get("status") == "resolved":
            l_rows.append({"tweet_id": tid, "loc_id": lid, "gazetteer_id": r["gazetteer_id"], "nama": r.get("nama_resmi"),
                           "level": r.get("level_admin"), "admin_path": r.get("admin_path"), "admin_nama": r.get("admin_nama"),
                           "lat": r.get("lat"), "lon": r.get("lon")})
    for o in rec.get("organization", []):
        org_rows.append({"tweet_id": tid, "org_id": o["id"], "nama": o["nama"], "nama_lembaga": o.get("nama_lembaga") or o["nama"]})
    for r in rec.get("relations", []):
        if r["type"] in ("HANDLES", "DEPLOYED_TO", "EVACUATED_TO"):
            rel_rows.append({"tweet_id": tid, "type": r["type"], "from": r["from"], "to": r["to"], "aksi": r.get("aksi"),
                             "mention_id": pemilik.get(r["to"]) or pemilik.get(r["from"])})
    return o_rows, n_rows, l_rows, org_rows, rel_rows
