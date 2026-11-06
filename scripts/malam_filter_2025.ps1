# Run semalam (+-6 jam) filter informatif Qwen lokal pada data pengembangan 2025.
# Jalankan dari folder skripsi:  powershell -ExecutionPolicy Bypass -File scripts\malam_filter_2025.ps1
# Bila terputus / laptop tidur: jalankan ulang file ini — tweet yang sudah berlabel tidak dikirim lagi.
# PENTING: matikan sleep laptop (Settings > System > Power > Sleep: Never) dan colokkan charger.
$base = @("-m", "modul1", "--config", "config_2025.yaml", "--workdir", "dev_2025")

Write-Host "== 0. Pastikan model qwen2.5-cpu ada =="
if (-not (ollama list | Select-String -SimpleMatch "qwen2.5-cpu")) {
    ollama create qwen2.5-cpu -f Modelfile.qwen2.5-cpu
}
ollama list

Write-Host "== 0b. Pulihkan label uji sah yang sempat terpindah =="
python scripts\pulihkan_label_uji.py

Write-Host "== 1. Uji 5 tweet/permintaan, 60 tweet (+-15-25 menit) =="
python @base filter --limit 60
Write-Host "== 2. Uji 3 tweet/permintaan, 60 tweet yang sama (+-20-35 menit) =="
python @base filter --profil qwen_b3 --limit 60
python scripts\ringkas_uji_batch.py

Write-Host "== 3. Label Qwen untuk 200 tweet file anotasi (+-40-70 menit) =="
python @base filter --ids dev_2025\reports\anotasi_dev_2025.csv

Write-Host "== 4. Tambahan sampel acak 1500 tweet (+-4-5 jam; 5 tweet/permintaan +-60 detik) =="
python @base filter --limit 1500

Write-Host "Selesai $(Get-Date)"
