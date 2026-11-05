"""Semua Cypher dashboard (BACA SAJA, berparameter). Arah relasi mengikuti adapter.REL.

Hitungan memakai count(DISTINCT ...) dan pattern comprehension agar join ke banyak dampak,
kebutuhan, lembaga, atau lokasi tidak menggandakan baris.
"""

# kode_kab kejadian = modus kode_kab laporannya (adapter.event_kode_kab; DisasterEvent belum punya kode_kab)
EVENT_KAB = """
MATCH (m:EventMention)-[:CONSOLIDATED_INTO]->(e:DisasterEvent)
WITH e, m.kode_kab AS k, count(DISTINCT m) AS n
ORDER BY n DESC, k
WITH e, collect(k)[0] AS kode_kab
"""

_EVENT_FILTER = """
WHERE ($jenis IS NULL OR e.jenis IN $jenis)
  AND ($sampai IS NULL OR date(e.start_time) <= date($sampai))
  AND ($dari IS NULL OR date(e.end_time) >= date($dari))
"""

_MENTION_FILTER = """
WHERE ($jenis IS NULL OR m2.jenis IN $jenis)
  AND ($dari IS NULL OR date(m2.tanggal_lokal) >= date($dari))
  AND ($sampai IS NULL OR date(m2.tanggal_lokal) <= date($sampai))
"""

KAB_AGREGAT = EVENT_KAB + _EVENT_FILTER + """
OPTIONAL MATCH (m2:EventMention)-[:CONSOLIDATED_INTO]->(e)
""" + _MENTION_FILTER + """
OPTIONAL MATCH (t:Tweet)-[:REPORTS]->(m2)
RETURN kode_kab, count(DISTINCT e) AS jumlah_kejadian, count(DISTINCT m2) AS jumlah_laporan,
       count(DISTINCT t) AS jumlah_tweet
ORDER BY kode_kab
"""

RINGKASAN = EVENT_KAB + _EVENT_FILTER + """
OPTIONAL MATCH (m2:EventMention)-[:CONSOLIDATED_INTO]->(e)
""" + _MENTION_FILTER + """
OPTIONAL MATCH (t:Tweet)-[:REPORTS]->(m2)
RETURN count(DISTINCT e) AS jumlah_kejadian, count(DISTINCT m2) AS jumlah_laporan,
       count(DISTINCT t) AS jumlah_tweet, count(DISTINCT kode_kab) AS jumlah_kab
"""

KAB_DENGAN_DATA = EVENT_KAB + "RETURN DISTINCT kode_kab"

RENTANG = """
MATCH (m:EventMention)
RETURN toString(min(date(m.tanggal_lokal))) AS awal, toString(max(date(m.tanggal_lokal))) AS akhir
"""

HISTOGRAM = """
MATCH (m:EventMention)-[:CONSOLIDATED_INTO]->(:DisasterEvent)
WHERE ($jenis IS NULL OR m.jenis IN $jenis) AND ($kab IS NULL OR m.kode_kab = $kab)
WITH date.truncate('week', date(m.tanggal_lokal)) AS w, m.jenis AS jenis, count(DISTINCT m) AS n
RETURN toString(w) AS mulai, jenis, n
"""

# id laporan untuk subgraf: semua laporan dari kejadian yang relevan (agar kode_kab kejadian tetap benar)
MENTION_IDS_KAB = EVENT_KAB + """
WHERE kode_kab = $kode
MATCH (m2:EventMention)-[:CONSOLIDATED_INTO]->(e)
RETURN collect(DISTINCT m2.mention_id) AS ids
"""

MENTION_IDS_LOKASI = """
OPTIONAL MATCH (l:Location {gazetteer_id: $gid})
OPTIONAL MATCH (m:EventMention)-[:MENTIONS|EVACUATED_TO]->(l)
OPTIONAL MATCH (m)-[:CONSOLIDATED_INTO]->(e:DisasterEvent)<-[:CONSOLIDATED_INTO]-(m2:EventMention)
RETURN count(l) > 0 AS ada, collect(DISTINCT m2.mention_id) AS ids
"""

SUBGRAF = """
MATCH (m:EventMention) WHERE m.mention_id IN $ids
OPTIONAL MATCH (m)-[:CONSOLIDATED_INTO]->(e:DisasterEvent)
RETURN m{.*} AS m, e{.*} AS e,
  [(t:Tweet)-[:REPORTS]->(m) | t{.*}] AS tweets,
  [(m)-[:MENTIONS]->(l:Location) | l.gazetteer_id] AS locs,
  [(m)-[:EVACUATED_TO]->(l:Location) | l.gazetteer_id] AS evac,
  [(m)-[:AFFECTED]->(a:AffectedObject) | {a: a{.*}, locs: [(a)-[:LOCATED_IN]->(x:Location) | x.gazetteer_id]}] AS aos,
  [(m)-[:REQUIRES]->(h:HumanitarianNeed) | h{.*}] AS needs,
  [(o:Organization)-[:HANDLES]->(m) | o.id] AS orgs
"""

ORGANISASI = """
MATCH (o:Organization)
WHERE o.id IN $org_ids OR ($gid IS NOT NULL AND EXISTS { (o)-[:DEPLOYED_TO]->(:Location {gazetteer_id: $gid}) })
RETURN o{.*} AS o, [(o)-[:DEPLOYED_TO]->(l:Location) | l.gazetteer_id] AS dep,
       [(o)-[:PART_OF]->(p:Organization) | p{.*}] AS induk
"""

LOKASI = """
MATCH (l:Location) WHERE l.gazetteer_id IN $gids
RETURN l.gazetteer_id AS gazetteer_id, l.nama AS nama, l.admin_path AS admin_path,
       CASE WHEN l.coordinates IS NULL THEN null
            ELSE {latitude: l.coordinates.latitude, longitude: l.coordinates.longitude} END AS coordinates
"""
