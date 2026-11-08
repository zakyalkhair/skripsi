"""Akses fakta graf. Satu antarmuka, dua pintu: Neo4jRepo (Cypher, dipakai sungguhan) dan MemRepo (dari CSV modul3, untuk uji tanpa Neo4j)."""
from collections import defaultdict
from modul3 import wilayah as W

JENIS = ["banjir", "tanah_longsor", "cuaca_ekstrem", "karhutla", "gempabumi", "erupsi"]


def _s(x): return None if x is None else str(x)


class Repo:
    nama_wil = None
    def _nama(self):
        if self.nama_wil is None: self.nama_wil = W.muat()
        return self.nama_wil
    def nama_kab(self, kode): return self._nama().get(kode, kode)
    def tambah_nama(self, k):
        for r in k["laporan"] + k["dampak"] + k["kebutuhan"]:
            if r.get("kode_kab"): r["kab_nama"] = self.nama_kab(r["kode_kab"])
        return k


class Neo4jRepo(Repo):
    def __init__(self, sesi): self.s = sesi
    def q(self, cy, **p): return [dict(r) for r in self.s.run(cy, **p)]

    def tweets(self):
        return [{"tweet_id": r["id"], "created_at": _s(r["dt"]), "text_raw": r["txt"]}
                for r in self.q("MATCH (t:Tweet) RETURN t.tweet_id AS id, toString(t.created_at) AS dt, t.text_raw AS txt ORDER BY id")]

    def jumlah_node(self): return {r["l"]: r["n"] for r in self.q("MATCH (n) RETURN labels(n)[0] AS l, count(*) AS n")}

    def daftar_de(self, jenis=None, kab=None, prov=None, mulai=None, selesai=None, limit=5):
        rows = self.q("""MATCH (d:DisasterEvent)
            WHERE ($jenis IS NULL OR d.jenis = $jenis OR $jenis IN d.jenis_tambahan)
              AND ($prov IS NULL OR $prov IN d.kode_provinsi) AND ($kab IS NULL OR $kab IN d.kode_wilayah)
              AND ($mulai IS NULL OR d.end_time >= date($mulai)) AND ($selesai IS NULL OR d.start_time <= date($selesai))
            OPTIONAL MATCH (d)<-[:CONSOLIDATED_INTO]-(m:EventMention)
            RETURN d.event_id AS event_id, d.nama AS nama, d.jenis AS jenis, d.jenis_tambahan AS jenis_tambahan,
                   toString(d.start_time) AS start_time, toString(d.end_time) AS end_time, d.status AS status,
                   d.sumber_tanggal AS sumber_tanggal, d.kode_provinsi AS kode_provinsi, d.kode_wilayah AS kode_wilayah, count(m) AS n_mention
            ORDER BY n_mention DESC, start_time LIMIT $limit""", jenis=jenis, kab=kab, prov=prov, mulai=mulai, selesai=selesai, limit=limit)
        return rows

    def kerangka(self, de):
        base = "MATCH (t:Tweet)-[:REPORTS]->(m:EventMention)-[c:CONSOLIDATED_INTO]->(d:DisasterEvent {event_id: $de}) "
        d = self.q("MATCH (d:DisasterEvent {event_id: $de}) RETURN d.event_id AS event_id, d.nama AS nama, d.jenis AS jenis, d.jenis_tambahan AS jenis_tambahan, "
                   "toString(d.start_time) AS start_time, toString(d.end_time) AS end_time, d.status AS status, d.sumber_tanggal AS sumber_tanggal, "
                   "d.kode_provinsi AS kode_provinsi, d.kode_wilayah AS kode_wilayah", de=de)
        if not d: return None
        k = {"de": d[0]}
        k["laporan"] = self.q(base + "RETURN m.mention_id AS mention_id, t.tweet_id AS tweet_id, toString(t.created_at) AS created_at, t.text_raw AS text, "
                              "m.kode_kab AS kode_kab, toString(m.tanggal_lokal) AS tanggal_lokal, m.tipe_laporan AS tipe_laporan, m.subtipe AS subtipe, c.aturan AS aturan "
                              "ORDER BY m.tanggal_lokal, t.created_at", de=de)
        k["dampak"] = self.q(base + "MATCH (m)-[:AFFECTED]->(a:AffectedObject) RETURN t.tweet_id AS tweet_id, toString(t.created_at) AS created_at, "
                             "m.mention_id AS mention_id, m.kode_kab AS kode_kab, toString(m.tanggal_lokal) AS tanggal_lokal, a.kelas AS kelas, a.objek AS objek, "
                             "a.status AS status, a.jumlah AS jumlah, a.satuan AS satuan ORDER BY m.tanggal_lokal, t.created_at", de=de)
        k["kebutuhan"] = self.q(base + "MATCH (m)-[:REQUIRES]->(n:HumanitarianNeed) RETURN t.tweet_id AS tweet_id, toString(t.created_at) AS created_at, "
                                "m.kode_kab AS kode_kab, n.kategori AS kategori, n.item AS item, n.status AS status ORDER BY t.created_at", de=de)
        k["lembaga"] = self.q(base + "MATCH (m)-[:AFFECTED|REQUIRES]->(x)<-[h:HANDLES]-(o:Organization) RETURN DISTINCT t.tweet_id AS tweet_id, "
                              "o.nama_kanonik AS nama_kanonik, h.aksi AS aksi, labels(x)[0] AS sasaran, coalesce(x.kategori, x.kelas) AS jenis_sasaran "
                              "UNION " + base + "MATCH (m)-[:LOCATED_IN]->(l:Location)<-[dep:DEPLOYED_TO]-(o:Organization) RETURN DISTINCT t.tweet_id AS tweet_id, "
                              "o.nama_kanonik AS nama_kanonik, dep.aksi AS aksi, 'Location' AS sasaran, l.nama AS jenis_sasaran", de=de)
        k["lokasi"] = self.q(base + "MATCH (m)-[:LOCATED_IN]->(l:Location) RETURN DISTINCT t.tweet_id AS tweet_id, l.nama AS nama, l.level AS level, l.admin_path AS admin_path", de=de)
        k["pengungsian"] = self.q(base + "MATCH (x)-[:EVACUATED_TO]->(l:Location) WHERE x = m OR (m)-[:AFFECTED]->(x) RETURN DISTINCT t.tweet_id AS tweet_id, l.nama AS lokasi", de=de)
        return self.tambah_nama(k)


class MemRepo(Repo):
    """Pintu yang sama, bersumber CSV modul3 (hasil `python -m modul3 proses`)."""
    def __init__(self, dir_):
        from modul3.graf import bangun
        self.g = bangun(dir_)
        self.tw = {t["tweet_id"]: t for t in self.g["tweets"]}
        self.em = {m["mention_id"]: m for m in self.g["mentions"]}
        self.ev = {e["event_id"]: e for e in self.g["events"]}
        self.anggota = defaultdict(list)
        for c in self.g["consolidated"]: self.anggota[c["event_id"]].append(c)
        self.loc = {l["gazetteer_id"]: l for l in self.g["locations"]}

    def tweets(self): return sorted(self.g["tweets"], key=lambda t: t["tweet_id"])
    def jumlah_node(self):
        return {"Tweet": len(self.g["tweets"]), "EventMention": len(self.g["mentions"]), "DisasterEvent": len(self.g["events"]), "Location": len(self.g["locations"])}

    def daftar_de(self, jenis=None, kab=None, prov=None, mulai=None, selesai=None, limit=5):
        out = []
        for e in self.g["events"]:
            if jenis and not (e["jenis"] == jenis or jenis in e["jenis_tambahan"]): continue
            if prov and prov not in e["kode_provinsi"]: continue
            if kab and kab not in e["kode_wilayah"]: continue
            if mulai and e["end_time"] < mulai: continue
            if selesai and e["start_time"] > selesai: continue
            out.append(dict(e, n_mention=len(self.anggota[e["event_id"]])))
        out.sort(key=lambda e: (-e["n_mention"], e["start_time"]))
        return out[:limit]

    def kerangka(self, de):
        e = self.ev.get(de)
        if not e: return None
        ids = {c["mention_id"]: c["aturan"] for c in self.anggota[de]}
        T = lambda m: self.tw[self.em[m]["tweet_id"]]
        k = {"de": e, "laporan": [], "dampak": [], "kebutuhan": [], "lembaga": [], "lokasi": [], "pengungsian": []}
        for mid, aturan in ids.items():
            m, t = self.em[mid], T(mid)
            k["laporan"].append({"mention_id": mid, "tweet_id": t["tweet_id"], "created_at": t["created_at"], "text": t["text_raw"], "kode_kab": m["kode_kab"],
                                 "tanggal_lokal": m["tanggal_lokal"], "tipe_laporan": m["tipe_laporan"], "subtipe": m["subtipe"], "aturan": aturan})
        base = lambda mid: {"tweet_id": self.em[mid]["tweet_id"], "created_at": T(mid)["created_at"], "mention_id": mid,
                            "kode_kab": self.em[mid]["kode_kab"], "tanggal_lokal": self.em[mid]["tanggal_lokal"]}
        aff = {a["id"]: a for a in self.g["affected"]}; need = {n["id"]: n for n in self.g["needs"]}
        for a in self.g["affected"]:
            if a["mention_id"] in ids: k["dampak"].append(dict(base(a["mention_id"]), kelas=a["kelas"], objek=a["objek"], status=a["status"], jumlah=a["jumlah"], satuan=a["satuan"]))
        for n in self.g["needs"]:
            if n["mention_id"] in ids: k["kebutuhan"].append(dict(base(n["mention_id"]), kategori=n["kategori"], item=n["item"], status=n["status"]))
        for r in self.g["handles_a"] + self.g["handles_n"]:
            tgt = aff.get(r["id"]) or need.get(r["id"])
            if tgt and tgt["mention_id"] in ids:
                k["lembaga"].append({"tweet_id": self.em[tgt["mention_id"]]["tweet_id"], "nama_kanonik": r["nama_kanonik"], "aksi": r["aksi"],
                                     "sasaran": "AffectedObject" if r["id"] in aff else "HumanitarianNeed", "jenis_sasaran": tgt.get("kelas") or tgt.get("kategori")})
        li = defaultdict(list)
        for x in self.g["located_in"]: li[x["mention_id"]].append(x["gazetteer_id"])
        for mid in ids:
            for gid in li[mid]:
                l = self.loc[gid]
                k["lokasi"].append({"tweet_id": self.em[mid]["tweet_id"], "nama": l["nama"], "level": l["level"], "admin_path": l["admin_path"]})
                for d in self.g["deployed_to"]:
                    if d["gazetteer_id"] == gid:
                        k["lembaga"].append({"tweet_id": self.em[mid]["tweet_id"], "nama_kanonik": d["nama_kanonik"], "aksi": d["aksi"], "sasaran": "Location", "jenis_sasaran": l["nama"]})
        for ev in self.g["evacuated_to"]:
            sid = ev["sumber_id"]; mid = sid if sid in ids else next((a["mention_id"] for a in [aff.get(sid)] if a and a["mention_id"] in ids), None)
            if mid: k["pengungsian"].append({"tweet_id": self.em[mid]["tweet_id"], "lokasi": self.loc[ev["gazetteer_id"]]["nama"]})
        return self.tambah_nama(k)
