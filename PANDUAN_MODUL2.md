# Modul 2 versi awal (v1) — cara menjalankan

Data: hanya data pengembangan 2025 (`dev_2025`). Model: `qwen2.5-cpu` di Ollama (sudah dibuat untuk 1.4).

1. Pastikan Ollama jalan dan model ada: `ollama list` (harus ada `qwen2.5-cpu`).
2. Dari folder `skripsi`, uji kecepatan dulu dengan 20 tweet:
   `python -m modul2 ekstrak --config config_modul2.yaml --limit 20`
   Tiap baris log menampilkan detik per tweet dan perkiraan waktu untuk 2.000 tweet.
3. Lihat ringkasan waktu: `python -m modul2 estimasi --config config_modul2.yaml --target 2000`
4. Validasi (2.2) hasilnya: `python -m modul2 validasi --config config_modul2.yaml`
   → `dev_2025/data/processed/extraction_valid_v1.jsonl` + `dev_2025/reports/validation_log_v1.csv`.
5. Bila waktunya masuk akal, lanjutkan ke 2.000 tweet (otomatis melanjutkan, tidak mengulang yang sudah selesai):
   `python -m modul2 ekstrak --config config_modul2.yaml --limit 2000`
   Boleh dihentikan (Ctrl+C) dan dijalankan lagi kapan saja.

Tes: `python -m pytest tests_modul2 -q` (8 tes, tanpa model).
Isi: `modul2/schema.py` (enum ontologi v1) · `modul2/prompt/` (system_v1, 8 contoh few-shot sintetis, singkatan wilayah)
· `modul2/extract.py` (2.1) · `modul2/validate.py` (2.2). Belum: 2.3 resolusi lokasi, 2.4 pemecahan & waktu.

## v2 (9 Okt)
`config_modul2.yaml` kini memakai prompt v2; hasil v1 tetap di `*_v1.*`. Uji lagi 20 tweet yang SAMA (seed sama):
`python -m modul2 ekstrak --config config_modul2.yaml --limit 20` lalu `python -m modul2 validasi --config config_modul2.yaml`.
Perubahan: aturan prompt (lokasi disalin persis & dipisah per wilayah, nama tanpa penanda tingkat -> detail, lembaga tidak ke kejadian,
relasi hanya ke id yang ada, laporan penanganan tetap kejadian, format laporan BMKG), 3 contoh baru (11 total); validasi menerima
`"type:"`, subtipe yang ditulis sebagai jenis, awalan "Ds./Kab." di slot, singkatan provinsi dua arah, tanda episentrum LS/LU.
