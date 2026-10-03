# Panduan menjalankan Modul 1 (catatan pribadi)

Panduan langkah demi langkah untuk Windows PowerShell. Detail teknis dan alasan metodologi ada di
`README.md`; file ini hanya "apa yang diketik, kapan, dan hasilnya di mana".

---

## 0. Gambaran singkat

```
1.1 crawl       → data/raw/raw.jsonl → data/interim/crawled.parquet
1.2 preprocess  → data/interim/preprocessed.parquet
1.3 dedup       → data/interim/dedup.parquet, data/processed/input_1_4.parquet (7.927 wakil, 10 kejadian)
1.4 filter      → aturan regex dulu, sisanya dilabeli LLM
                → data/processed/hasil_1_4*.parquet (semua wakil + label)
                → data/processed/informatif*.parquet (hanya yang informatif → Modul 2)
```

- Tahap 1.1–1.3 = kode Python biasa (tanpa LLM). **Sudah selesai**; hasilnya ada di repo.
- Tahap 1.4 = regex + LLM, dengan prompt pedoman B40 (`config/prompt_informatif.md`).

| Pelabel | `model` di jsonl | Keluaran | Status (3 Okt 2026) |
|---|---|---|---|
| Regex (`aturan:*` di config) | — | ikut di keluaran mana pun | otomatis |
| Qwen 2.5 7B lewat Ollama | `qwen2.5:7b` | `informatif_ollama_qwen.parquet`, `hasil_1_4_ollama_qwen.parquet` | ⏳ 1.762 berlabel, 4.878 belum |

- Label versi prompt lama (Claude manual dan 406 label Qwen pertama) **sudah dihapus**
  (keputusan 3 Okt 2026: hanya pedoman B40 yang dipakai). Riwayatnya tetap ada di git.
- Semua label disimpan di `data/interim/llm_labels_1_4.jsonl`. Bila nanti ada pelabel kedua,
  satu tweet muncul sekali per pelabel — **bukan duplikat**, itu "lembar nilai" dua penilai.
  File keluaran tetap satu baris per tweet.

---

## 1. Persiapan di laptop baru (sekali saja)

```powershell
git clone https://github.com/zakyalkhair/skripsi.git
cd skripsi
git checkout claude/new-session-swkc56

python -m venv .venv
.venv\Scripts\activate          # setiap buka terminal baru, jalankan baris ini dulu
pip install -r requirements.txt

python -m pytest -q             # harus: 60 passed
```

Bila `activate` ditolak ("running scripts is disabled"):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `.env` (tidak ada di GitHub, salin manual)

Hanya perlu bila **crawl lagi** atau memakai **Groq**. Untuk Ollama tidak perlu.

```powershell
Copy-Item .env.example .env
notepad .env
```

- `USER_HASH_SALT` **harus sama** dengan laptop lama (kalau beda, `user_hash` tidak konsisten).
- `X_ACCOUNT_1_COOKIES="auth_token=...; ct0=..."` (pakai tanda kutip).
- `GROQ_API_KEY=` hanya bila memakai Groq.

---

## 2. Tahap 1.4 dengan Qwen (Ollama)

### 2a. Siapkan Ollama

1. Install dari https://ollama.com/download (ikon muncul di tray = server sudah jalan).
2. Unduh model:

```powershell
ollama pull qwen2.5:7b
ollama list                                   # harus ada qwen2.5:7b
curl.exe http://localhost:11434/api/tags      # cek server menjawab
```

> `ollama serve` → error `bind: Only one usage of each socket address` artinya server **sudah
> jalan**. Abaikan, lanjut saja.

### 2b. Uji coba 20 tweet

```powershell
python -m modul1 filter --profil ollama_qwen --limit 20
```

Lihat log. Baik bila: `Permintaan x/y: 10/10 berlabel`.
Bila banyak `invalid_output` / `hilang_dari_jawaban` → buka `config.yaml`, bagian
`profil_llm: ollama_qwen:`, ubah `tweet_per_permintaan: 10` menjadi `5`, ulangi.

> Mengubah `tweet_per_permintaan` mengubah `prompt_hash` → label hasil uji coba sebelumnya tidak
> dipakai lagi (dilabeli ulang). Itu normal; tetapkan setelan final **sebelum** run penuh.

### 2c. Run penuh

```powershell
python -m modul1 filter --profil ollama_qwen
```

- Bisa berjam-jam tanpa GPU. Terhenti (Ctrl+C / laptop tidur)? **Jalankan perintah yang sama
  lagi** — yang sudah berlabel tidak dikirim ulang.
- Hasil: `data/processed/informatif_ollama_qwen.parquet`, `hasil_1_4_ollama_qwen.parquet`,
  `reports/alur_data_ollama_qwen.csv`, log di `logs/`.

Bila jawaban terpotong (`finish_reason: length` di log), perbesar konteks Ollama:

```powershell
# klik kanan ikon Ollama di tray → Quit, lalu:
$env:OLLAMA_CONTEXT_LENGTH=8192
ollama serve                    # biarkan jendela ini terbuka; jalankan python di terminal lain
```

### 2d. Tulis ulang keluaran tanpa memanggil model

```powershell
python -m modul1 filter-finalize --profil ollama_qwen    # versi Qwen
# Tanpa --profil = config utama (Groq); jangan dijalankan kalau belum ada label Groq
```

---

## 3. Bandingkan dua pelabel (bila ada pelabel kedua, mis. Groq atau label manual)

```powershell
python -m modul1 filter-bandingkan --a qwen2.5:7b --b openai/gpt-oss-120b
```

Hasil:

- `reports/bandingkan_1_4.json` → `n_bersama`, `persen_setuju`, `cohen_kappa`, `matriks` 2×2
  (baris = pelabel A, kolom = pelabel B). Ini tabel kesepakatan antar-penilai untuk skripsi.
- `data/interim/beda_1_4.jsonl` → tweet yang labelnya beda, dengan kolom `label_final` kosong.

Tafsiran kappa (Landis & Koch): < 0,20 buruk · 0,21–0,40 lemah · 0,41–0,60 sedang ·
0,61–0,80 kuat · > 0,80 hampir sempurna.

Lihat isi `beda_1_4.jsonl` cepat:

```powershell
python -c "import pandas as pd; d=pd.read_json('data/interim/beda_1_4.jsonl', lines=True); print(len(d)); print(d[['tweet_id','label_a','label_b','text_raw']].head(20).to_string())"
```

### Adjudikasi (opsional, disarankan)

Isi `label_final` (`"informatif"` / `"noninformatif"`) untuk setiap baris di `beda_1_4.jsonl`
(buka di VS Code). Belum ada perintah untuk menyusun `informatif` final dari file ini — minta
dibuatkan bila sudah sampai tahap ini.

---

## 4. Memakai Groq (opsional, alternatif Qwen)

```powershell
# isi GROQ_API_KEY di .env (https://console.groq.com → API Keys)
python -m modul1 filter --limit 50      # uji coba
python -m modul1 filter                 # kuota harian habis → berhenti rapi, jalankan lagi besok
```

Keluarannya: `informatif.parquet` / `hasil_1_4.parquet` (tanpa akhiran), terpisah dari versi Qwen.

---

## 5. Mengulang tahap 1.1–1.3 (hanya bila perlu)

```powershell
python -m modul1 crawl --events GP07    # crawl satu kejadian (kueri berstatus selesai dilewati)
python -m modul1 crawl                  # semua kejadian pilot
python -m modul1 crawl --skip-fetch     # bangun ulang crawled.parquet dari raw.jsonl saja
python -m modul1 preprocess             # 1.2
python -m modul1 dedup                  # 1.3 → input_1_4.parquet baru
python scripts\cek_twscrape.py         # diagnosa bila crawl 0 tweet
```

⚠️ Bila `dedup` dijalankan ulang dan `input_1_4.parquet` berubah, label yang ada hanya berlaku untuk
`tweet_id` yang masih sama; tweet baru dilabeli pada run `filter` berikutnya.

Kalibrasi ambang dedup (sekali):

```powershell
python -m modul1 calib-sample           # → reports/kalibrasi_dedup.csv, isi kolom label_duplikat (1/0)
python -m modul1 calib-report           # presisi per ambang + saran ambang
```

---

## 6. Simpan ke GitHub

```powershell
git add -A
git commit -m "Label Qwen tahap 1.4"
git push
```

`.env`, `logs/`, `reports/`, dan database akun twscrape tidak ikut ter-commit (lihat `.gitignore`).
`reports/bandingkan_1_4.json` perlu disalin manual bila ingin disimpan (atau minta ubah `.gitignore`).

⚠️ Repo **publik** dan `data/raw/raw.jsonl` memuat data akun X yang belum dianonimkan. Untuk
menutupnya: GitHub → Settings → General → Danger Zone → Change visibility → Private.

---

## 7. Masalah umum

| Gejala | Solusi |
|---|---|
| `ModuleNotFoundError: pandas` | lupa `.venv\Scripts\activate` |
| `bind: Only one usage of each socket address` | Ollama sudah jalan; abaikan |
| `koneksi:ConnectError` di 1.4 | Ollama belum jalan / model belum di-pull; cek `curl.exe http://localhost:11434/api/tags` |
| `profil 'x' tidak ada di profil_llm` | salah ketik nama profil; yang ada: `ollama`, `ollama_cloud`, `ollama_qwen` |
| `tidak ada label ok untuk model 'x'` | nilai `--a/--b` harus persis sama dengan kolom `model`; pesan galat menampilkan daftar yang ada |
| `GROQ_API_KEY kosong` | isi `.env`, atau pakai `--profil ollama_qwen` |
| Crawl `Cookies must include auth_token and ct0` | format `.env`: `X_ACCOUNT_1_COOKIES="auth_token=...; ct0=..."` |
| Crawl `CERTIFICATE_VERIFY_FAILED` | `use_system_certs: true` di `config.yaml` (default) |

---

## 8. Untuk bab metodologi

- Label Qwen: pipeline dengan prompt tetap (`config/prompt_informatif.md`), `temperature 0`,
  tercatat `prompt_hash` → dapat direproduksi.
- Laporkan persen setuju + Cohen's kappa, lalu adjudikasi manual untuk yang berbeda.
- Validasi tambahan: labeli sendiri sampel acak 100–200 tweet dan bandingkan dengan kedua versi.
