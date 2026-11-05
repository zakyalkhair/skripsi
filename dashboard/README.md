# Peta Situasi Bencana

Dashboard geospasial baca-saja untuk menjelajahi informasi bencana yang diekstraksi dari unggahan X
berbahasa Indonesia: **nasional → kab/kota → lokasi → laporan kejadian → tweet sumber**.

> Mode bawaan memakai **Data Contoh** ilustratif (`data/contoh/`) — bukan pemantauan bencana nyata.

## Menjalankan (mode file, tanpa Neo4j)

```bash
# 1. Backend (Python 3.11+)
cd dashboard/backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
cp .env.example .env                                # DATA_SOURCE=file
.venv/bin/uvicorn app.main:app --port 8000          # dokumentasi API: http://localhost:8000/api/docs

# 2. Frontend (Node 20+) — terminal lain
cd dashboard/frontend
npm install
npm run dev                                         # http://localhost:5173 (proxy /api -> :8000)
```

Build statis: `npm run build` → `frontend/dist/` (sajikan bersama backend; `/api` harus satu origin atau atur `CORS_ORIGINS`).

## Uji

```bash
cd dashboard/backend && .venv/bin/python -m pytest -q          # 11 uji API (hitungan distinct, semantik tanggal, kasus tepi)
cd dashboard/frontend && npx playwright test                   # 17 uji browser; menyalakan backend + vite otomatis
```
Playwright memakai Chromium terpasang di `/opt/pw-browsers` bila ada, atau `PW_CHROMIUM=/path/chrome`,
atau browser bawaan Playwright (`npx playwright install chromium`).

## Antarmuka

Peta memenuhi layar; bilah filter, remah roti, legenda, linimasa, dan panel rincian mengambang di atasnya
dan dapat diminimalkan (preferensi disimpan per perangkat). Klik kab/kota = masuk/pindah wilayah; klik laut
atau tombol rumah (kanan atas peta) = kembali ke peta nasional; klik kartu kejadian = sorot lokasinya
(klik lagi untuk melepas). Rentang tanggal diatur di bilah atas dan tersinkron dengan kuas linimasa.

## Integrasi Neo4j

```bash
# isi NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD di backend/.env, lalu (Neo4j LOKAL saja):
cd dashboard/backend && .venv/bin/python ../scripts/seed_contoh.py   # memuat data contoh (MERGE)
DATA_SOURCE=neo4j .venv/bin/uvicorn app.main:app --port 8000
```
- Dashboard **tidak pernah menulis**: sesi `READ_ACCESS` + `execute_read`, middleware menolak metode selain GET.
  Gunakan akun Neo4j berhak baca saja untuk graf produksi. Penulisan hanya ada di `scripts/seed_contoh.py`.
- Semua Cypher ada di `backend/app/repository/queries.py` (berparameter, `count(DISTINCT …)`, pattern
  comprehension agar join ke banyak dampak/kebutuhan/lembaga tidak menggandakan hitungan).
- Asumsi skema yang belum final diisolasi di `backend/app/adapter.py` (lihat laporan, "Asumsi integrasi").
- `GAZETTEER_FILE` menunjuk gazetteer lokal (`gazetteer_id → tingkat, kode_kab`); bawaan: gazetteer data contoh.
- **Mode Neo4j belum diuji terhadap basis data nyata** di lingkungan pengembangan ini (tidak ada Neo4j).

## Membangun ulang data

```bash
python scripts/build_geo.py "path/Batas Kabupaten.shp"   # butuh pyshp + shapely; sumber: Kemendagri 2020
python scripts/buat_contoh.py                            # menulis data/contoh/*.json
```

## API (baca-saja)

| Endpoint | Isi |
|---|---|
| `GET /api/wilayah` | provinsi, 514 kab/kota (`ada_data`), metadata dataset |
| `GET /api/kab-agregat?jenis=&dari=&sampai=` | kejadian unik per kab/kota + ringkasan (kejadian, laporan, tweet unik, kab) |
| `GET /api/kab/{kode}/kejadian?…` | kartu kejadian (hitungan periode & total, dampak, kebutuhan, lembaga) |
| `GET /api/kab/{kode}/titik?…` | lokasi unik yang dapat dipetakan + jenis + jumlah laporan |
| `GET /api/titik/{gazetteer_id}/ringkasan?…` | laporan dikelompokkan per kejadian, tweet sumber, dampak/kebutuhan per lokasi vs tingkat kejadian |
| `GET /api/histogram?jenis=&kab=` | laporan kejadian per minggu (Senin) |

`jenis` tidak dikirim = semua jenis; `jenis=` (kosong) = tidak ada jenis dipilih (hasil kosong).
`gazetteer_id` boleh memuat `/` atau `:` (kirim ter-encode).
