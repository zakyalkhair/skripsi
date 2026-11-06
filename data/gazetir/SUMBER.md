# Sumber gazetir administratif

- Berkas: `wilayah.sql` dari https://github.com/cahyadsn/wilayah (lisensi MIT, hak cipta cahya dsn), `db/wilayah.sql`.
- Diunduh 27 Okt 2026 (UTC); commit master saat diunduh: 92cb44c90172f18b941ed9f652ee2106b462d73f (2026-10-27).
- Judul berkas menyebut Kepmendagri 300.2.2-2138/2025, sedangkan catatan Project menyebut 2430/2025; jumlah entri 91.599
  (38 provinsi, 514 kab/kota, 7.285 kecamatan, 83.762 desa/kelurahan) cocok dengan angka di TEKNIS-2.3 -> kemungkinan teks judul saja yang berbeda. Cek.
- Belum ada: poligon/koordinat (cahyadsn/wilayah_boundaries) dan fitur OSM (siapkan_osm.py). Koordinat = tahap berikutnya.

## Titik pusat wilayah (28 Okt 2026)
- `titik_wilayah.csv` (kode, nama, lat, lon) diekstrak dari https://github.com/cahyadsn/wilayah_boundaries (MIT), commit 2c0d8c791af7ca55ee06d17b8f34813e8e6bf1b1 (2026-10-26). Hanya kolom lat/lng; poligon (`path`) tidak disimpan.
- Judul repo ini menyebut Kepmendagri 300.2.2-2430/2025 (cocok dengan catatan Project); judul `wilayah.sql` menyebut 2138/2025. Jumlah entri 38/514/7.285/83.762 sama, jadi beda angka kemungkinan hanya di teks judul.
- Cakupan: 91.449 dari 91.599 kode; 150 desa belum punya titik (contoh 74.02.18.1001, 92.03.01.1001) -> hasil tetap sah tanpa koordinat, catatan `koordinat_belum_ada`.
- Presisi: titik pusat wilayah (bukan lokasi kejadian). Lokasi dengan `detail` (jalan, tempat) tetap menunggu OSM.

## Poligon kecamatan dan fitur OSM (30 Okt 2026)
- `poligon_kec.csv` (kode, wkt; 7.285 kecamatan, disederhanakan 0,002 derajat ±220 m) dari cahyadsn/wilayah_boundaries commit 2c0d8c79; hanya dipakai `scripts/siapkan_osm.py` untuk memberi kode kecamatan pada fitur OSM (titik-dalam-poligon, fallback poligon terdekat ≤ ±1 km).
- `osm_feat.csv` (dibuat 29 Okt 2026, 609.659 fitur: 194.966 node, 414.693 way; 7.116 tanpa kode_kec) dibuat di laptop dengan `python scripts\siapkan_osm.py --pbf data\raw\indonesia-latest.osm.pbf` (pbf dari Geofabrik, ODbL; `indonesia-latest.osm.pbf` diunduh 29 Okt 2026, 1,74 GB, tidak ikut git). Geofabrik diblokir dari lingkungan cloud maupun VM.
- Sudah dijalankan pada data OSM nyata (29 Okt 2026).
