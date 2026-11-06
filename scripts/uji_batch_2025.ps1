# Uji jumlah tweet per permintaan (5 vs 3) dengan Qwen lokal pada data pengembangan 2025.
# Jalankan dari folder skripsi:  powershell -ExecutionPolicy Bypass -File scripts\uji_batch_2025.ps1
# Syarat: Ollama berjalan dan model qwen2.5-cpu sudah dibuat (ollama create qwen2.5-cpu -f ..\Modelfile.optimized).
# Perkiraan: +-35-60 menit. Bila terputus, jalankan ulang file ini: tweet yang sudah berlabel tidak dikirim lagi.
$ErrorActionPreference = "Stop"
$base = @("-m", "modul1", "--config", "config_2025.yaml", "--workdir", "dev_2025")

Write-Host "== Cek Ollama & model =="
ollama list | Select-String "qwen2.5-cpu"
if (-not $?) { Write-Error "Model qwen2.5-cpu belum ada di Ollama." }

Write-Host "== Run 1/2: 5 tweet per permintaan (utama), 60 tweet =="
python @base filter --limit 60

Write-Host "== Run 2/2: 3 tweet per permintaan (profil qwen_b3), 60 tweet yang sama =="
python @base filter --profil qwen_b3 --limit 60

Write-Host "== Ringkasan =="
python scripts\ringkas_uji_batch.py
Write-Host "Selesai. Ringkasan juga tersimpan di dev_2025\reports\uji_batch_2025.json"
