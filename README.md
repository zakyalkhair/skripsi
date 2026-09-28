# Modul 1 (tahap 1.1–1.3): Crawling → Preprocessing → Deduplikasi

Pipeline tweet bencana berbahasa Indonesia untuk skripsi. Lingkup berhenti di **1.3**; tahap 1.4
(filter informatif dengan LLM) dan Modul 2 **tidak** ada di sini. Keluaran 1.3 sudah siap dipakai
1.4 (`data/processed/input_1_4.parquet`).

Prinsip: **tidak ada baris yang dihapus**. Setiap tweet yang tidak lanjut diberi `drop_reason`,
setiap tahap mencatat jumlah masuk/keluar/dibuang ke `reports/alur_data.csv`, dan semua proses
acak memakai `seed` di `config.yaml`.

## Instalasi

```bash
uv venv -p 3.11 && uv pip install -r requirements.txt     # atau: python -m venv .venv && pip install -r requirements.txt
cp .env.example .env                                        # isi akun X + USER_HASH_SALT (jangan di-commit)
python -m pytest                                            # 28 test
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
```

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
| `logs/<tahap>_<waktu>.log` | log setiap tahap |

## Arti kolom keluaran akhir

| Kolom | Arti |
|---|---|
| `tweet_id` (str) | ID tweet, **selalu string** |
| `created_at` | waktu tweet (UTC) |
| `text` | teks asli dari X (tidak diubah) |
| `text_raw` | `text` setelah ftfy → `html.unescape` → NFKC → rapikan spasi. Tidak ada kata yang dihapus/diganti. **Dipakai 1.4 dan Modul 2** (offset karakter) |
| `text_clean` | `text_raw` + URL→`<URL>`, mention→`<USER>`, buang `#`, emoji/tanda baca→spasi, lowercase. **Hanya untuk dedup** |
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
