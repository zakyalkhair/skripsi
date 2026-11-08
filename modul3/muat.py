"""3.3 Ingesti ke Neo4j: constraint + indeks + MERGE berbatch (idempoten).
Pakai: python -m modul3.muat --data dev_2025/data/modul3 [--bersihkan] [--run-id X]"""
import argparse, datetime
from .graf import bangun, ringkas
from .neo4j_conn import driver

CONSTRAINTS = [
    "CREATE CONSTRAINT tweet_pk IF NOT EXISTS FOR (t:Tweet) REQUIRE t.tweet_id IS UNIQUE",
    "CREATE CONSTRAINT ment_pk IF NOT EXISTS FOR (m:EventMention) REQUIRE m.mention_id IS UNIQUE",
    "CREATE CONSTRAINT event_pk IF NOT EXISTS FOR (d:DisasterEvent) REQUIRE d.event_id IS UNIQUE",
    "CREATE CONSTRAINT loc_pk IF NOT EXISTS FOR (l:Location) REQUIRE l.gazetteer_id IS UNIQUE",
    "CREATE CONSTRAINT org_pk IF NOT EXISTS FOR (o:Organization) REQUIRE o.nama_kanonik IS UNIQUE",
    "CREATE CONSTRAINT aff_pk IF NOT EXISTS FOR (a:AffectedObject) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT need_pk IF NOT EXISTS FOR (n:HumanitarianNeed) REQUIRE n.id IS UNIQUE",
    "CREATE POINT INDEX location_point_idx IF NOT EXISTS FOR (l:Location) ON (l.koordinat)",
]

# (kunci baris di graf, cypher dengan $rows)
LANGKAH = [
    ("tweets", """UNWIND $rows AS r MERGE (t:Tweet {tweet_id: r.tweet_id})
        SET t.created_at = datetime(r.created_at), t.text_raw = r.text_raw, t.run_id = $run_id"""),
    ("locations", """UNWIND $rows AS r MERGE (l:Location {gazetteer_id: r.gazetteer_id})
        SET l.nama = r.nama, l.level = r.level, l.admin_path = r.admin_path, l.sumber = r.sumber
        FOREACH (_ IN CASE WHEN r.lat IS NULL OR r.lon IS NULL THEN [] ELSE [1] END |
            SET l.koordinat = point({latitude: r.lat, longitude: r.lon}))"""),
    ("part_of", """UNWIND $rows AS r MATCH (a:Location {gazetteer_id: r.anak}), (b:Location {gazetteer_id: r.induk})
        MERGE (a)-[:PART_OF]->(b)"""),
    ("mentions", """UNWIND $rows AS r MERGE (m:EventMention {mention_id: r.mention_id})
        SET m.jenis = r.jenis, m.subtipe = r.subtipe, m.tipe_laporan = r.tipe_laporan, m.kode_kab = r.kode_kab,
            m.tanggal_lokal = date(r.tanggal_lokal), m.tanggal_akhir = date(r.tanggal_akhir), m.ketepatan = r.ketepatan,
            m.zona = r.zona, m.magnitudo = r.magnitudo, m.di_luar_periode = r.di_luar_periode, m.run_id = $run_id
        WITH m, r MATCH (t:Tweet {tweet_id: r.tweet_id}) MERGE (t)-[:REPORTS]->(m)"""),
    ("mentions_tweet_loc", """UNWIND $rows AS r MATCH (t:Tweet {tweet_id: r.tweet_id}), (l:Location {gazetteer_id: r.gazetteer_id})
        MERGE (t)-[:MENTIONS]->(l)"""),
    ("located_in", """UNWIND $rows AS r MATCH (m:EventMention {mention_id: r.mention_id}), (l:Location {gazetteer_id: r.gazetteer_id})
        MERGE (m)-[:LOCATED_IN]->(l)"""),
    ("affected", """UNWIND $rows AS r MERGE (a:AffectedObject {id: r.id})
        SET a.kelas = r.kelas, a.objek = r.objek, a.status = r.status, a.jumlah = r.jumlah, a.satuan = r.satuan
        WITH a, r MATCH (m:EventMention {mention_id: r.mention_id}) MERGE (m)-[:AFFECTED]->(a)"""),
    ("needs", """UNWIND $rows AS r MERGE (n:HumanitarianNeed {id: r.id})
        SET n.kategori = r.kategori, n.item = r.item, n.status = r.status, n.lokasi = r.lokasi
        WITH n, r MATCH (m:EventMention {mention_id: r.mention_id}) MERGE (m)-[:REQUIRES]->(n)"""),
    ("organizations", """UNWIND $rows AS r MERGE (o:Organization {nama_kanonik: r.nama_kanonik})
        SET o.alias = r.alias, o.wilayah = r.wilayah, o.tingkat = r.tingkat"""),
    ("handles_a", """UNWIND $rows AS r MATCH (o:Organization {nama_kanonik: r.nama_kanonik}), (x:AffectedObject {id: r.id})
        MERGE (o)-[h:HANDLES {aksi: coalesce(r.aksi, "")}]->(x)"""),
    ("handles_n", """UNWIND $rows AS r MATCH (o:Organization {nama_kanonik: r.nama_kanonik}), (x:HumanitarianNeed {id: r.id})
        MERGE (o)-[h:HANDLES {aksi: coalesce(r.aksi, "")}]->(x)"""),
    ("deployed_to", """UNWIND $rows AS r MATCH (o:Organization {nama_kanonik: r.nama_kanonik}), (l:Location {gazetteer_id: r.gazetteer_id})
        MERGE (o)-[d:DEPLOYED_TO {aksi: coalesce(r.aksi, "")}]->(l)"""),
    ("evacuated_to", """UNWIND $rows AS r MATCH (x) WHERE (x:AffectedObject AND x.id = r.sumber_id) OR (x:EventMention AND x.mention_id = r.sumber_id)
        MATCH (l:Location {gazetteer_id: r.gazetteer_id}) MERGE (x)-[:EVACUATED_TO]->(l)"""),
    ("events", """UNWIND $rows AS r MERGE (d:DisasterEvent {event_id: r.event_id})
        SET d.nama = r.nama, d.jenis = r.jenis, d.jenis_tambahan = r.jenis_tambahan, d.start_time = date(r.start_time),
            d.end_time = date(r.end_time), d.status = r.status, d.sumber_tanggal = r.sumber_tanggal,
            d.kode_provinsi = r.kode_provinsi, d.kode_wilayah = r.kode_wilayah, d.run_id = $run_id"""),
    ("consolidated", """UNWIND $rows AS r MATCH (m:EventMention {mention_id: r.mention_id}), (d:DisasterEvent {event_id: r.event_id})
        MERGE (m)-[c:CONSOLIDATED_INTO]->(d) SET c.aturan = r.aturan"""),
]


def muat(g, sesi, run_id, batch=1000):
    for q in CONSTRAINTS: sesi.run(q)
    for kunci, cy in LANGKAH:
        rows = g[kunci]
        for i in range(0, len(rows), batch):
            sesi.run(cy, rows=rows[i:i + batch], run_id=run_id)
        print(f"  {kunci}: {len(rows)} baris")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--bersihkan", action="store_true", help="hapus SEMUA node/relasi dulu")
    ap.add_argument("--run-id", default=datetime.datetime.now().strftime("run_%Y%m%d_%H%M%S"))
    a = ap.parse_args(argv)
    g = bangun(a.data); print("Siap dimuat:", ringkas(g))
    drv, db = driver()
    with drv, drv.session(database=db) as s:
        if a.bersihkan:
            if input("Hapus SEMUA data di database ini? ketik 'ya': ").strip() != "ya": raise SystemExit("dibatalkan")
            s.run("MATCH (n) DETACH DELETE n")
        muat(g, s, a.run_id)
        r = s.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC").data()
        print("Isi graf:", r)


if __name__ == "__main__":
    main()
