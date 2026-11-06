# Rencana Implementasi — Peta Situasi Bencana

## Temuan awal (Fase A)
- `peta-situasi-bencana.html` **tidak ada** di repositori → spesifikasi dipakai langsung dan data contoh
  ilustratif dibuat baru (bukan data prototipe asli).
- Batas wilayah berkode Kemendagri tidak ada secara lokal → diambil dari shapefile Kemendagri 2020
  (github.com/Alf-Anas/batas-administrasi-indonesia), disederhanakan dengan `scripts/build_geo.py`.
- Dashboard dibuat di folder terpisah `dashboard/`, tidak menyentuh pipeline `modul1/`.

## Arsitektur
```
dashboard/
  data/contoh/graf.json, gazetteer.json   data contoh (node + relasi ontologi), gazetteer lokal
  data/wilayah.json                       514 kab/kota (kode Kemendagri)
  backend/app/                            FastAPI baca-saja
    domain.py      Graph + Filter (semantik tanggal)
    adapter.py     SATU-SATUNYA logika bergantung skema (kode_kab kejadian, tingkat lokasi, arah relasi)
    service.py     penyusun respons, hitungan distinct
    repository/    file_repo (DATA_SOURCE=file) | neo4j_repo + queries.py (Cypher berparameter, READ_ACCESS)
  frontend/src/                           Vite + TypeScript + Leaflet (tanpa framework UI)
    api.ts store.ts types.ts jenis.ts format.ts dom.ts
    map/ (map.ts, marker.ts, legend.ts)   ui/ (filters, combobox, panel, timeline)   styles/ (token + komponen)
  scripts/ build_geo.py, buat_contoh.py, seed_contoh.py
```
Keputusan: TypeScript tanpa React — state hanya satu store kecil, komponen sedikit; menghindari dependensi
berat. Agregasi dilakukan di backend (satu sumber kebenaran untuk hitungan distinct, sama untuk mode file
dan Neo4j).

## Urutan kerja
1. Data: GeoJSON disederhanakan (Jatim halus 0,0025°, provinsi lain 0,02°), data contoh tervalidasi
   koordinatnya terhadap poligon Kemendagri.
2. Backend: endpoint kontrak §13, uji pytest untuk kasus tepi §15.
3. Sistem desain: token warna (kategorikal ≠ sekuensial), tipografi Barlow/Plex Mono, token gerak.
4. Peta: choropleth kelas tetap, drill-down `flyToBounds`, penanda SVG per `gazetteer_id`, klaster.
5. Analitik: filter chip + combobox, histogram mingguan + kuas, kartu kejadian, detail lokasi + tweet.
6. Penyempurnaan visual via tangkapan layar 1440/1024/768/390 px, lalu uji Playwright.
