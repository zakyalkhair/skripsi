# Panduan menjalankan Modul 3

Semua perintah dijalankan dari folder repo (`C:\Zaky\Kuliah\Skripsi\skripsi`).

## 1. Tanpa Neo4j (2.4 + perataan + 3.1 + 3.2)
    python -m modul3 proses
Hasil: CSV di `dev_2025/data/modul3/` (`disaster_event.csv`, `consolidated_into.csv`, `log_konsolidasi.csv`, `organization.csv`, dst).
Opsi: `--masuk <file hasil 2.3>` `--keluar <folder>`.

## 2. Dengan Neo4j (3.3 + 3.4)
1. `pip install neo4j`
2. Salin `.env.example` menjadi `.env`, isi `NEO4J_PASSWORD` (jangan di-commit; `.env` sudah ada di `.gitignore`).
3. Jalankan Neo4j (Desktop atau server) lalu:

       python -m modul3 muat        # constraint + indeks + MERGE berbatch (aman diulang)
       python -m modul3 cq          # 24 competency question -> dev_2025/reports/cq_hasil.csv
       python -m modul3 semua       # proses -> muat -> cq
   `--bersihkan` mengosongkan database dulu (minta konfirmasi "ya").

Melihat 24 kueri saja: `python -m modul3.cq --cetak`.

## 3. Tes
    python -m pytest tests_modul3 -q

## Catatan
- Pelari CQ mencari nilai parameter nyata dari graf, mencoba sampai kueri mengembalikan baris. Status: terjawab / kosong / galat.
- CQ nomor 6 (status darurat) pasti kosong: atribut itu belum diekstraksi.
- Loader dan pelari CQ belum pernah diuji ke Neo4j sungguhan (hanya tes struktur); jalankan pertama kali pada database kosong.
