# Modul 1 (tahap 1.1–1.4): Crawling → Preprocessing → Deduplikasi → Filter informatif

Pipeline tweet bencana berbahasa Indonesia untuk skripsi. Tahap 1.4 (filter informatif dengan
LLM) menghasilkan `data/processed/informatif.parquet` untuk Modul 2 (Modul 2 tidak ada di sini).

Prinsip: **tidak ada baris yang dihapus**. Setiap tweet yang tidak lanjut diberi `drop_reason`,
setiap tahap mencatat jumlah masuk/keluar/dibuang ke `reports/alur_data.csv`, dan semua proses
acak memakai `seed` di `config.yaml`.

## Instalasi

```bash
uv venv -p 3.11 && uv pip install -r requirements.txt     # atau: python -m venv .venv && pip install -r requirements.txt
cp .env.example .env                                        # isi akun X + USER_HASH_SALT (jangan di-commit)
python -m pytest                                            # 60 test
# Panduan langkah demi langkah (PowerShell): PANDUAN.md
```

## Menjalankan

```bash
python -m modul1 crawl --events GP07          # 1.1 satu kejadian dulu, cek ringkasan & sampel
python -m modul1 crawl                        # 1.1 semua kejadian pilot (kueri selesai dilewati)
python -m modul1 crawl --pause                # tanya konfirmasi setelah tiap kejadian
python -m modul1 crawl --skip-fetch           # hanya bangun ulang crawled.parquet dari raw.jsonl
python -m modul1 preprocess                   # 1.2
python -m modul1 dedup                        # 1.3 + keluaran akhir
python -m modul1 run-all [--events ...]       # 1.1 -> 1.2 -> 1.3

python -m modul1 calib-sample                 # sekali: sampel pasangan -> reports/kalibrasi_dedup.csv
#   isi kolom label_duplikat (1 = duplikat, 0 = bukan), lalu:
python -m modul1 calib-report                 # presisi per ambang + saran ambang

python -m modul1 filter --limit 50            # 1.4 uji coba: 50 tweet acak
python -m modul1 filter                       # 1.4 sisanya; bila kuota harian habis, jalankan lagi besok
python -m modul1 filter-finalize              # 1.4 tulis ulang keluaran dari label yang ada (tanpa API)
```

Tahap 1.4 memakai API OpenAI-compatible. Default: Groq (gratis, `openai/gpt-oss-120b`), butuh
`GROQ_API_KEY` di `.env`. Penyedia lain dipilih dengan `--profil` (daftar di `profil_llm`,
`config.yaml`) tanpa mengubah config utama.

### 1.4 dengan Ollama dan membandingkan dua model

Pakai pipeline ini (`python -m modul1 filter --profil ollama`), **bukan** `ollama launch claude`.
`ollama launch claude` menjalankan aplikasi Claude Code dengan model Ollama sebagai agen: agen itu
membaca tweet lalu menulis label sendiri, sehingga hasilnya sulit direproduksi. Pipeline memakai
prompt, suhu, dan ukuran batch yang sama untuk semua tweet, dan setiap label tercatat beserta
`prompt_hash`-nya.

```bash
# 1. Ollama: https://ollama.com/download, lalu jalankan server dengan konteks lebih besar
#    (bawaan terlalu kecil untuk prompt + 10 tweet + penalaran gpt-oss)
OLLAMA_CONTEXT_LENGTH=16384 ollama serve        # Windows PowerShell: $env:OLLAMA_CONTEXT_LENGTH=16384; ollama serve
ollama pull gpt-oss:20b                          # terminal lain; atau: ollama signin (profil ollama_cloud)

# 2. Uji coba, lalu semua. Label disimpan di llm_labels_1_4.jsonl yang sama (model/prompt_hash beda)
python -m modul1 filter --profil ollama --limit 20
python -m modul1 filter --profil ollama
#    -> data/processed/informatif_ollama.parquet, hasil_1_4_ollama.parquet, reports/alur_data_ollama.csv
#       (informatif.parquet milik hasil utama tidak tertimpa)

# 3. Kesepakatan dua penilai (mis. label manual Claude vs Ollama)
python -m modul1 filter-bandingkan --a manual-claude-code --b gpt-oss:20b
#    -> reports/bandingkan_1_4.json  : n bersama, persen setuju, Cohen's kappa, matriks 2x2
#    -> data/interim/beda_1_4.jsonl  : tweet yang labelnya berbeda; isi label_final saat adjudikasi
```

Nilai `--a`/`--b` adalah isi kolom `model` di `llm_labels_1_4.jsonl`. Bila model lokal lambat atau
jawabannya sering `invalid_output` / `hilang_dari_jawaban`, kecilkan `tweet_per_permintaan` di
profil. Menjalankan ulang perintah yang sama hanya mengirim tweet yang belum berlabel.

Opsi global: `--config path/config.yaml`, `--workdir DIR` (folder dasar `data/`, `logs/`, `reports/`).

**Uji tanpa akun X (data tiruan):**

```bash
python scripts/buat_data_tiruan.py --workdir demo
python -m modul1 --workdir demo run-all --skip-fetch
```

## Berkas

| Berkas | Isi |
|---|---|
| `config.yaml` | semua parameter (kata kunci, batas crawl, ambang, seed, path) |
| `config/kejadian.csv` | 29 kejadian 2026; `only_pilot: true` → hanya 6 pilot |
| `data/raw/raw.jsonl` | mentah dari twscrape (`Tweet.dict()`) + `query_id`, `event_ids`, `crawled_at`. **Masih memuat data akun**, jangan dibagikan |
| `data/raw/crawl_log.csv` | query_id, event_ids, teks kueri, waktu, versi twscrape, jumlah hasil, status |
| `data/raw/crawl_progress.json` | kueri yang sudah selesai (untuk melanjutkan crawl) |
| `data/interim/crawled.parquet` | 1.1: teranonimkan, satu baris per `tweet_id` |
| `data/interim/preprocessed.parquet` | 1.2: + `text_raw`, `text_clean`, `too_short` |
| `data/interim/dedup.parquet` | 1.3: + kolom cluster |
| `data/processed/modul1_until_1_3.parquet` | keluaran akhir, semua tweet termasuk yang dibuang |
| `data/processed/input_1_4.parquet` | hanya wakil cluster, siap untuk 1.4 |
| `reports/alur_data.csv` | tabel alur data (langsung jadi tabel skripsi) |
| `reports/sampel_cek_kueri.csv` | 50 tweet acak per kueri untuk dicek manusia (satu-satunya CSV berisi teks) |
| `reports/dedup_ringkasan.json` | statistik 1.3 + parameter |
| `reports/kalibrasi_dedup.csv`, `kalibrasi_laporan.csv` | kalibrasi ambang |
| `reports/bandingkan_1_4.json`, `data/interim/beda_1_4.jsonl` | kesepakatan label dua model + daftar beda (1.4) |
| `logs/<tahap>_<waktu>.log` | log setiap tahap |

## Arti kolom keluaran akhir

| Kolom | Arti |
|---|---|
| `tweet_id` (str) | ID tweet, **selalu string** |
| `created_at` | waktu tweet (UTC) |
| `text` | teks asli dari X (tidak diubah) |
| `text_raw` | `text` setelah ftfy → `html.unescape` → NFKC → rapikan spasi. Tidak ada kata yang dihapus/diganti. **Dipakai 1.4 dan Modul 2** (offset karakter) |
| `text_clean` | `text_raw` + URL→`<URL>`, **mention `@x` dihapus seluruhnya**, **hashtag `#Kata` dihapus seluruhnya**, emoji/tanda baca→spasi, lowercase. **Hanya untuk dedup**. (Mode spesifikasi awal — mention→`<USER>`, hanya buang `#` — tersedia lewat `hapus_mention: false` / `hapus_hashtag: false`) |
| `lang` | kode bahasa dari X (`in` = Indonesia) |
| `hashtags`, `urls` | list hashtag dan URL (URL tujuan, bukan t.co) |
| `is_reply` | balasan (disimpan, tidak dibuang) |
| `coordinates` | `[longitude, latitude]` atau null |
| `query_id` | list kueri yang menemukan tweet ini |
| `event_id` | list kejadian asal kueri (satu tweet bisa cocok ke beberapa kejadian, mis. GP07 & ER03) |
| `user_hash` | `sha256(user_id + USER_HASH_SALT)`; null bila salt kosong. `username`, `user_id`, `displayname`, dan field profil lain tidak disimpan |
| `too_short` | `text_clean` tanpa `<URL>`/`<USER>` kurang dari `min_words` (3) kata |
| `cluster_id` | `c<tweet_id wakil>`; null untuk tweet yang tidak ikut 1.3 |
| `is_representatif` | wakil cluster (paling awal; seri → `tweet_id` numerik terkecil) |
| `member_tweet_ids` | list tweet_id seluruh anggota cluster |
| `cluster_size` | jumlah anggota cluster |
| `drop_reason` | null = lolos ke 1.4; `bukan_id`, `retweet`, `di_luar_jendela` (1.1), `terlalu_pendek` (1.2), `bukan_wakil` (1.3) |

## Keputusan metodologi (ringkas)

**1.1 Crawling**
- Kueri disusun otomatis **per (kejadian, kata kunci)**, dengan alias wilayah digabung OR:
  `"gempa bumi" (NTT OR Flores OR Ende OR …) -filter:retweets -kecelakaan since:2026-08-14 until:2026-08-30`.
  **Tanpa `lang:id`**: uji `scripts/cek_twscrape.py` (28-09-2026) menunjukkan operator itu merusak
  hasil pencarian lewat twscrape (0 tweet atau tweet 2014), sedangkan kueri yang sama tanpa `lang:id`
  normal. Bahasa disaring sesudah crawl (`lang == "in"`); `lang_operator` di config bisa diisi lagi
  bila twscrape/X sudah normal.
  `until:` di X eksklusif, jadi diisi `tanggal_selesai + 1 hari`. Jendela bisa diperlebar dengan
  `padding_hari_sebelum` / `padding_hari_sesudah` di `config.yaml` tanpa mengubah `kejadian.csv`;
  teks kueri lengkap (dengan tanggal sebenarnya) tercatat di `crawl_log.csv`. Kueri yang melebihi `max_query_chars`
  dipecah dengan membagi alias. `query_id` = `q` + 12 karakter awal sha1(teks kueri), stabil.
- Kata kunci multi-kata diapit tanda kutip (frasa persis).
- Crawl mengikuti `urutan_crawl`. Setelah tiap kejadian dicetak ringkasan (jumlah, % bahasa Indonesia, 5 contoh).
  Kueri yang gagal dicatat di `crawl_log.csv` dan diulang pada run berikutnya. Kueri yang selesai dilewati.
- Saring dasar tidak menghapus baris. Retweet dan non-`in` diberi `drop_reason`. twscrape juga
  mengembalikan tweet yang dikutip/dibalas sebagai hasil tersendiri walau tidak cocok dengan kueri;
  tweet yang `created_at`-nya di luar jendela `[since, until)` semua kueri asalnya ditandai
  `di_luar_jendela` (jendela disimpan per baris sebagai `query_window` di `raw.jsonl`). Tweet dengan ID sama
  digabung menjadi satu baris, dengan `query_id`/`event_id` jadi list. Quote tweet: hanya `rawContent`
  tweet itu sendiri.

**1.2 Preprocessing**: sesuai tabel spesifikasi. Emoji dan tanda baca diganti **spasi** (bukan dihapus
rapat) supaya `laki-laki` → `laki laki` dan `M5.2` → `m5 2`. Tidak ada normalisasi slang, pemecahan
hashtag, stemming, atau stopword removal.
Perubahan dari spesifikasi awal (keputusan peneliti): di `text_clean`, **hashtag dan mention dihapus
seluruhnya** agar tweet yang isinya sama tetapi berbeda tagar/mention (mis. `#PrayForNTT` vs
`#GempaFlores`, atau salinan dengan `@akun` berbeda) tergabung di dedup. Konsekuensi: tweet yang
isinya hampir hanya tagar/mention menjadi pendek dan lebih sering ditandai `terlalu_pendek`.
`text_raw` tidak berubah.

**1.3 Deduplikasi**
1. Exact: `sha1(text_clean)`.
2. Blocking: shingle 5 karakter, MinHash `num_perm=128` (seed tetap), `MinHashLSH(threshold=0.7)`.
   LSH dijalankan atas **teks unik** (satu per grup exact) supaya grup exact besar tidak meledakkan
   jumlah pasangan.
3. Verifikasi (AND): penjaga angka `sorted(re.findall(r"\d+", text_clean))` identik **dan**
   `fuzz.ratio ≥ 85`.
4. Union-find, lalu pemilihan wakil.

Definisi statistik di log: *dibatalkan penjaga angka* = pasangan dengan skor ≥ ambang tetapi angkanya
berbeda. *Lolos verifikasi* = skor ≥ ambang dan angka sama.

**Kalibrasi**: pasangan kandidat yang lolos penjaga angka dibagi ke bin skor 70–100 (lebar 5),
lalu diambil ±20 per bin. Karena sampelnya sama banyak per bin (bertingkat), `calib-report` menghitung
**presisi berbobot** (menurut jumlah populasi pasangan di tiap bin) di samping presisi mentah.
Saran ambang = ambang terendah dengan presisi berbobot ≥ 0,95.

**1.4 Filter informatif** (keputusan peneliti: LLM open-weight gratis, label biner)
- Masukan: `input_1_4.parquet` (wakil cluster). Keluaran: `hasil_1_4.parquet` (semua wakil +
  `label`, `label_sumber`, `llm_status`, `llm_model`, `prompt_hash`) dan `informatif.parquet`
  (hanya `label == informatif`, untuk Modul 2). Tidak ada baris yang dihapus.
- **Hibrida: aturan regex dulu, LLM untuk sisanya.** Aturan di `config.yaml` (`filter_llm.aturan`)
  dievaluasi berurutan; aturan pertama yang cocok menentukan label (`label_sumber = aturan:<nama>`).
  Prinsipnya presisi tinggi — hanya kasus yang jelas; yang ragu diserahkan ke LLM:
  - `bmkg` → informatif: laporan otomatis BMKG (`#Gempa Mag:… Lok:…`) yang menyebut salah satu
    `alias_wilayah` kejadian (I6). BMKG untuk wilayah lain tetap dinilai LLM (bisa N4).
  - `topik_lain` → noninformatif: MBG, karnaval, 17 Agustus/HUT RI, dll. (N3), **kecuali** tweet
    memuat petunjuk fakta (angka, korban, kerusakan, kebutuhan, pengungsian, bahaya, BNPB/BMKG).
  - `doa_tanpa_fakta` → noninformatif: semoga/doa/berduka/pray… (N1), dengan pengecualian yang sama.
  Log dan `alur_data.csv` mencatat jumlah per sumber label. `pakai_llm: false` + `label_default`
  = mode regex saja.
- **LLM:** API OpenAI-compatible (`/chat/completions`), default Groq `openai/gpt-oss-120b`
  (open-weight, Apache 2.0). Prompt di `config/prompt_informatif.md` (definisi + indikator
  I1–I8 / N1–N8 + aturan keputusan). Satu permintaan berisi deskripsi kejadian acuan dari
  `kejadian.csv` + `tweet_per_permintaan` (20) tweet bernomor lokal 1..n yang berbagi kejadian
  yang sama; jawaban JSON `{"hasil": [{"id", "label"}]}`, `temperature = 0`. Pengelompokan dipilih
  karena kuota token harian free tier (±200 ribu token/hari di Groq); prompt meminta setiap tweet
  dinilai terpisah.
- **Jejak:** setiap hasil disimpan di `data/interim/llm_labels_1_4.jsonl` (model, provider,
  prompt_hash, chunk, finish_reason, token). `prompt_hash` = sidik jari prompt + provider + model +
  parameter; bila salah satunya diubah, semua tweet dilabeli ulang dengan versi baru. Gagal
  (`hilang_dari_jawaban`, `invalid_output`, `errored:…`) → `label` kosong, dikirim ulang pada run
  berikutnya. HTTP 429 dengan jeda panjang (kuota harian) → proses berhenti rapi.
- **Privasi:** layanan gratis dapat memakai prompt untuk pelatihan model. Tweet sudah publik &
  teranonimkan; untuk menghindarinya sama sekali gunakan Ollama lokal.

## Catatan untuk dibahas (tidak diubah diam-diam)

1. **Nama wilayah berbeda bisa tergabung.** Penjaga angka tidak melindungi tweet yang teksnya sama
   tetapi nama wilayahnya berbeda, mis. "relawan TNI evakuasi korban gempa di **Sikka**" (GP07) vs
   "… di **Sigi**" (GP05). Skor fuzz-nya > 85 dan angkanya sama, sehingga digabung. Di data tiruan
   ada 52 dari 671 cluster yang berisi kejadian berbeda. Opsi bila dianggap masalah: penjaga
   tambahan "`event_id` harus beririsan", atau kalibrasi ambang dengan label yang memperhatikan lokasi.
2. **Jejak per alias hilang** karena kueri digabung OR (keputusan final). Yang tercatat hanya jejak per kata kunci.
3. Kata kunci **`pengungsi`/`mengungsi`** dengan alias luas (NTT, Jateng, Riau) berisiko menarik tweet
   di luar bencana, mis. pengungsi luar negeri. Cek lewat `sampel_cek_kueri.csv`.
4. `ftfy.fix_text` (setelan bawaan) juga meluruskan tanda kutip lengkung (`“ ”` → `" "`) dan
   memperbaiki lebar karakter. Panjang string umumnya tetap, tetapi ini tetap "perbaikan", bukan
   penghapusan kata.
5. **Regression check** terhadap data legacy (16.808 tweet) tidak dijalankan karena data legacy tidak
   dipakai. Importer `import-legacy` (opsional) juga tidak dibuat.

## Pemecahan masalah crawl

| Gejala | Penyebab & solusi |
|---|---|
| `Cookies must include auth_token and ct0` | format `.env` salah; pakai `X_ACCOUNT_1_COOKIES="auth_token=...; ct0=..."` |
| `ConnectError ... cooling account for 60s` berulang | Python tidak tersambung ke X. Cek `CERTIFICATE_VERIFY_FAILED` → `use_system_certs: true` (default); atau jaringan memblokir X → ganti jaringan / `TWS_PROXY=` di `.env` |
| Semua kueri `0 tweet` | jalankan `python scripts/cek_twscrape.py` (status akun + uji kueri bertahap). Kueri 0 hasil berstatus `kosong` dan otomatis diulang pada run berikutnya |
