"""3.4 lapis isi graf: 24 competency question (Cypher) + pelari uji jawab.
Pakai: python -m modul3.cq --jalankan [--keluar DIR]   |   python -m modul3.cq --cetak"""
import argparse, csv, itertools, json, os
from .neo4j_conn import driver

DE_ = "(d:DisasterEvent {event_id: $de})<-[:CONSOLIDATED_INTO]-(m:EventMention)"
CQ = [
 (1, "Situasi kejadian", "Kejadian bencana apa saja di kabupaten $kab pada rentang $t1-$t2?", ["kab", "t1", "t2"],
  "MATCH (d:DisasterEvent)<-[:CONSOLIDATED_INTO]-(m:EventMention) WHERE m.kode_kab = $kab AND d.start_time >= date($t1) AND d.start_time <= date($t2) "
  "RETURN DISTINCT d.nama, d.jenis, d.start_time, d.sumber_tanggal ORDER BY d.start_time"),
 (2, "Situasi kejadian", "Kapan kejadian $de mulai dan dari mana tanggal itu diketahui?", ["de"],
  "MATCH (d:DisasterEvent {event_id: $de}) RETURN d.nama, d.start_time, d.end_time, d.sumber_tanggal"),
 (3, "Situasi kejadian", "Kabupaten/desa mana saja yang terdampak kejadian $de?", ["de"],
  f"MATCH {DE_}-[:LOCATED_IN]->(l:Location) OPTIONAL MATCH (l)-[:PART_OF*0..3]->(a:Location) "
  "RETURN DISTINCT l.nama, l.level, collect(DISTINCT a.nama) AS wilayah_induk"),
 (4, "Situasi kejadian", "Jenis bencana apa paling banyak di provinsi $prov per bulan?", ["prov"],
  "MATCH (d:DisasterEvent) WHERE $prov IN d.kode_provinsi RETURN d.jenis, d.start_time.year AS tahun, d.start_time.month AS bulan, count(*) AS n ORDER BY tahun, bulan, n DESC"),
 (5, "Situasi kejadian", "Apakah $de tergolong bencana (Juklak) dan laporan mana yang memenuhi ambang?", ["de"],
  f"MATCH (d:DisasterEvent {{event_id: $de}}) OPTIONAL MATCH {DE_}-[:AFFECTED]->(a:AffectedObject) "
  "WHERE a.status IN ['meninggal','luka','mengungsi','terdampak'] OR a.status STARTS WITH 'rusak' "
  "RETURN d.status AS bencana, m.mention_id, a.kelas, a.status, a.jumlah, a.satuan"),
 (6, "Situasi kejadian", "Status darurat apa yang berlaku untuk $de? (atribut belum diekstraksi)", ["de"],
  "MATCH (d:DisasterEvent {event_id: $de}) WHERE d.status_darurat IS NOT NULL RETURN d.status_darurat"),
 (7, "Situasi kejadian", "Berapa kekuatan gempa $de menurut semua laporan?", ["de"],
  f"MATCH {DE_} WHERE m.magnitudo IS NOT NULL RETURN m.mention_id, m.magnitudo"),
 (8, "Situasi kejadian", "Kejadian majemuk di kabupaten $kab dan jenis tambahannya?", ["kab"],
  "MATCH (d:DisasterEvent)<-[:CONSOLIDATED_INTO]-(m:EventMention) WHERE m.kode_kab = $kab AND size(coalesce(d.jenis_tambahan, [])) > 0 "
  "RETURN DISTINCT d.nama, d.jenis, d.jenis_tambahan, d.start_time"),
 (9, "Dampak kejadian", "Berapa korban/kerusakan dilaporkan untuk $de, per laporan dan kabupaten?", ["de"],
  f"MATCH {DE_}-[:AFFECTED]->(a:AffectedObject), (t:Tweet)-[:REPORTS]->(m) "
  "RETURN m.kode_kab, a.kelas, a.status, a.jumlah, a.satuan, t.tweet_id, t.created_at ORDER BY t.created_at"),
 (10, "Dampak kejadian", "Bagaimana angka $status untuk $de berkembang antar laporan?", ["de", "status"],
  f"MATCH {DE_}-[:AFFECTED]->(a:AffectedObject {{status: $status}}), (t:Tweet)-[:REPORTS]->(m) "
  "RETURN t.created_at, a.kelas, a.jumlah, a.satuan, m.kode_kab, t.tweet_id ORDER BY t.created_at"),
 (11, "Dampak kejadian", "Pada $de, adakah laporan dengan angka berbeda untuk kelas+status yang sama, dan rentangnya?", ["de"],
  f"MATCH {DE_}-[:AFFECTED]->(a:AffectedObject) WHERE a.jumlah IS NOT NULL "
  "WITH m.kode_kab AS kab, a.kelas AS kelas, a.status AS status, a.satuan AS satuan, min(a.jumlah) AS terkecil, max(a.jumlah) AS terbesar, count(a) AS laporan "
  "WHERE laporan > 1 AND terkecil <> terbesar RETURN kab, kelas, status, satuan, terkecil, terbesar, laporan"),
 (12, "Dampak kejadian", "Bangunan/prasarana apa yang dilaporkan rusak pada $de?", ["de"],
  f"MATCH {DE_}-[:AFFECTED]->(a:AffectedObject) WHERE a.kelas IN ['rumah','pelayanan_dasar','prasarana_vital'] "
  "RETURN m.kode_kab, a.kelas, a.objek, a.status, count(*) AS laporan, collect(DISTINCT a.jumlah) AS angka_dilaporkan"),
 (13, "Dampak kejadian", "Warga terdampak $de mengungsi ke mana?", ["de"],
  "MATCH (d:DisasterEvent {event_id: $de})<-[:CONSOLIDATED_INTO]-(m:EventMention) MATCH (x)-[:EVACUATED_TO]->(l:Location) "
  "WHERE x = m OR (m)-[:AFFECTED]->(x) RETURN DISTINCT l.nama, l.level"),
 (14, "Kebutuhan kemanusiaan", "Kebutuhan apa yang masih diminta di kabupaten $kab dan sejak kapan?", ["kab"],
  "MATCH (t:Tweet)-[:REPORTS]->(m:EventMention {kode_kab: $kab})-[:REQUIRES]->(n:HumanitarianNeed {status: 'demanded'}) "
  "RETURN n.kategori, n.item, min(t.created_at) AS sejak, count(*) AS laporan"),
 (15, "Kebutuhan kemanusiaan", "Bantuan apa yang sudah disalurkan untuk $de, di kabupaten mana?", ["de"],
  f"MATCH {DE_}-[:REQUIRES]->(n:HumanitarianNeed {{status: 'supplied'}}) RETURN m.kode_kab, n.kategori, n.item, count(*) AS laporan"),
 (16, "Kebutuhan kemanusiaan", "Kebutuhan mana yang diminta tetapi belum ada laporan penyalurannya untuk $de?", ["de"],
  f"MATCH {DE_}-[:REQUIRES]->(n:HumanitarianNeed) WITH n.kategori AS kat, collect(DISTINCT n.status) AS st "
  "WHERE 'demanded' IN st AND NOT 'supplied' IN st RETURN kat"),
 (17, "Penanganan", "Lembaga apa bertugas di lokasi $de dan apa tindakannya?", ["de"],
  f"MATCH {DE_}-[:LOCATED_IN]->(l:Location)<-[dep:DEPLOYED_TO]-(o:Organization) RETURN DISTINCT o.nama_kanonik, dep.aksi, l.nama"),
 (18, "Penanganan", "Lembaga apa menangani kebutuhan/dampak apa pada $de, dan tindakannya?", ["de"],
  f"MATCH {DE_}-[:REQUIRES|AFFECTED]->(x)<-[h:HANDLES]-(o:Organization) "
  "RETURN o.nama_kanonik, h.aksi, labels(x)[0] AS sasaran, coalesce(x.kategori, x.kelas) AS jenis_sasaran, m.kode_kab"),
 (19, "Penanganan", "Lembaga nasional apa terlibat di lebih dari satu kejadian pada bulan $b?", ["b"],
  "MATCH (o:Organization {tingkat: 'nasional'})-[:HANDLES]->(x)<-[:REQUIRES|AFFECTED]-(m:EventMention)-[:CONSOLIDATED_INTO]->(d:DisasterEvent) "
  "WHERE toString(d.start_time) STARTS WITH $b WITH o, count(DISTINCT d) AS n WHERE n > 1 RETURN o.nama_kanonik, n"),
 (20, "Penanganan", "Untuk lembaga $nama: tingkat, wilayah, dan nama-nama yang disatukan?", ["nama"],
  "MATCH (o:Organization {nama_kanonik: $nama}) RETURN o.nama_kanonik, o.tingkat, o.wilayah, o.alias"),
 (21, "Keterlacakan", "Dari tweet mana informasi $de berasal dan aturan apa yang menggabungkannya?", ["de"],
  f"MATCH (t:Tweet)-[:REPORTS]->(m:EventMention)-[c:CONSOLIDATED_INTO]->(d:DisasterEvent {{event_id: $de}}) RETURN t.tweet_id, t.created_at, m.mention_id, c.aturan"),
 (22, "Keterlacakan", "Tweet mana yang menyebut lokasi $loc tetapi bukan sebagai lokasi kejadian?", ["loc"],
  "MATCH (t:Tweet)-[:MENTIONS]->(l:Location {gazetteer_id: $loc}) WHERE NOT (t)-[:REPORTS]->(:EventMention)-[:LOCATED_IN]->(l) RETURN t.tweet_id, t.created_at, t.text_raw"),
 (23, "Cakupan administratif", "Kejadian apa di provinsi $prov, termasuk yang dilaporkan di tingkat desa/kecamatan?", ["prov"],
  "MATCH (p:Location {gazetteer_id: 'kemendagri:' + $prov}) MATCH (l:Location)-[:PART_OF*0..3]->(p) "
  "MATCH (m:EventMention)-[:LOCATED_IN]->(l), (m)-[:CONSOLIDATED_INTO]->(d:DisasterEvent) RETURN DISTINCT d.nama, d.jenis, d.start_time"),
 (24, "Cakupan administratif", "Untuk kecamatan $kec pada $de: dampak, kebutuhan, dan lembaga dalam satu jawaban?", ["de", "kec"],
  f"MATCH {DE_}-[:LOCATED_IN]->(l:Location) WHERE $kec IN l.admin_path OPTIONAL MATCH (m)-[:AFFECTED]->(a:AffectedObject) "
  "OPTIONAL MATCH (m)-[:REQUIRES]->(n:HumanitarianNeed) OPTIONAL MATCH (o:Organization)-[:DEPLOYED_TO]->(l) "
  "RETURN l.nama, collect(DISTINCT [a.kelas, a.status, a.jumlah]) AS dampak, collect(DISTINCT [n.kategori, n.status]) AS kebutuhan, collect(DISTINCT o.nama_kanonik) AS lembaga"),
]

KANDIDAT = {   # parameter -> kueri pencari nilai nyata (diurutkan dari yang paling kaya data)
 "de": "MATCH (d:DisasterEvent) RETURN d.event_id AS v ORDER BY size([(d)<-[:CONSOLIDATED_INTO]-(m)-[]->(x) | x]) DESC LIMIT 20",
 "kab": "MATCH (m:EventMention)-[:CONSOLIDATED_INTO]->() WHERE m.kode_kab IS NOT NULL RETURN DISTINCT m.kode_kab AS v LIMIT 20",
 "t1": "MATCH (d:DisasterEvent) RETURN toString(min(d.start_time)) AS v",
 "t2": "MATCH (d:DisasterEvent) RETURN toString(max(d.end_time)) AS v",
 "prov": "MATCH (d:DisasterEvent) UNWIND d.kode_provinsi AS v RETURN DISTINCT v LIMIT 20",
 "status": None,
 "loc": "MATCH (:Tweet)-[:MENTIONS]->(l:Location) RETURN DISTINCT l.gazetteer_id AS v LIMIT 30",
 "nama": "MATCH (o:Organization) RETURN o.nama_kanonik AS v LIMIT 30",
 "b": "MATCH (d:DisasterEvent) RETURN DISTINCT substring(toString(d.start_time), 0, 7) AS v LIMIT 20",
 "kec": "MATCH (l:Location) WHERE size(l.admin_path) >= 3 RETURN DISTINCT l.admin_path[2] AS v LIMIT 30",
}
STATUS = ["meninggal", "mengungsi", "luka", "terdampak"]
MAKS_COBA = 60


def cetak():
    for no, kel, tanya, par, cy in CQ:
        print(f"-- {no} [{kel}] {tanya}\n-- parameter: {', '.join(par)}\n{cy};\n")


def cari_kandidat(sesi):
    k = {}
    for nama, q in KANDIDAT.items():
        k[nama] = STATUS if q is None else [r["v"] for r in sesi.run(q) if r["v"] is not None]
    return k


def jalankan_cq(sesi, kandidat):
    hasil = []
    for no, kel, tanya, par, cy in CQ:
        pools = [kandidat.get(p, []) for p in par]
        status, baris, param, galat, n_coba = "kosong", [], None, None, 0
        if any(not p for p in pools):
            hasil.append({"no": no, "kelompok": kel, "pertanyaan": tanya, "status": "kosong", "baris": 0, "parameter": "tidak ada nilai kandidat",
                          "contoh": "", "galat": ""}); continue
        for combo in itertools.islice(itertools.product(*pools), MAKS_COBA):
            n_coba += 1; p = dict(zip(par, combo))
            try:
                rows = sesi.run(cy, **p).data()
            except Exception as e:                 # galat sintaks / properti hilang = temuan, bukan alasan berhenti
                status, galat, param = "galat", str(e).splitlines()[0][:200], p; break
            if rows: status, baris, param = "terjawab", rows, p; break
            param = p
        hasil.append({"no": no, "kelompok": kel, "pertanyaan": tanya, "status": status, "baris": len(baris),
                      "parameter": json.dumps(param, ensure_ascii=False, default=str), "percobaan": n_coba,
                      "contoh": json.dumps(baris[:2], ensure_ascii=False, default=str)[:400], "galat": galat or ""})
    return hasil


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--jalankan", action="store_true"); ap.add_argument("--cetak", action="store_true")
    ap.add_argument("--keluar", default="dev_2025/reports")
    a = ap.parse_args(argv)
    if a.cetak or not a.jalankan: return cetak()
    drv, db = driver()
    with drv, drv.session(database=db) as s:
        hasil = jalankan_cq(s, cari_kandidat(s))
    os.makedirs(a.keluar, exist_ok=True)
    p = os.path.join(a.keluar, "cq_hasil.csv")
    cols = ["no", "kelompok", "pertanyaan", "status", "baris", "percobaan", "parameter", "contoh", "galat"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore"); w.writeheader(); w.writerows(hasil)
    from collections import Counter
    print(Counter(h["status"] for h in hasil)); print("Disimpan:", p)
    for h in hasil:
        if h["status"] != "terjawab": print(f'  {h["no"]:>2} {h["status"]:7} {h["pertanyaan"][:70]} {h["galat"]}')


if __name__ == "__main__":
    main()
