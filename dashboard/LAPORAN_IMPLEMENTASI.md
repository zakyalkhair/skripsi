# Laporan Implementasi — Peta Situasi Bencana

## Penyempurnaan antarmuka (tahap 2)
- **Tata letak peta penuh**: sidebar permanen dihapus; bilah filter, remah roti, legenda, linimasa, dan panel
  rincian kini kartu mengambang. Panel, legenda, dan linimasa dapat diminimalkan/dipulihkan tanpa kehilangan
  pilihan; di layar ≤ 820 px panel menjadi lembar bawah. Bantalan kamera dihitung dari panel yang terbuka
  sehingga wilayah terpilih tidak tertutup panel.
- **Model interaksi peta yang eksplisit**: hover & seleksi digambar di lapisan terpisah tanpa pointer-events
  (tidak ada lagi `bringToFront` saat hover — penyebab kedip); satu tooltip peta dengan pemilik tunggal dan jeda
  sembunyi singkat, disembunyikan saat kamera bergerak, saat penanda dilepas, dan saat pointer keluar. Klik
  kab/kota lain langsung berpindah; klik laut kembali ke nasional (ditunda 300 ms agar klik ganda tetap zoom);
  klik panel/kontrol tidak diteruskan ke peta. Satu kontrol rumah + zoom di kanan atas area peta terlihat.
- **Penanda**: klik = pilih + terbang secukupnya (zoom sasaran per tingkat lokasi, pusat area terlihat), tidak
  bergerak bila penanda sudah terlihat; penanda kab lama dipudarkan sebelum kamera berpindah.
- **Kartu kejadian** dapat diklik seluruhnya (tombol "Sorot" dihapus); klik lagi melepas sorotan; aksesibel
  dengan papan ketik; keadaan rincian yang dibuka dipertahankan saat filter berubah.
- **Visual**: satu keluarga huruf Plus Jakarta Sans; choropleth merah sekuensial transparan (opasitas 0,55) yang
  menyatakan *jumlah* kejadian (legenda menegaskan bukan keparahan); daratan di luar cakupan diberi warna netral
  tipis; chip filter netral dengan kotak centang kecil berwarna kategori; rentang tanggal pindah ke bilah atas
  (format Indonesia, rentang cepat di popover). Label "Ikhtisar nasional", garis warna di tepi kartu, dan label
  ganda "Indonesia/Seluruh Indonesia" dihapus. Tampilan awal = seluruh Indonesia.
- Geometri: serpihan/lubang < ~0,1 km² dibuang dan pulau < ~30 km² tidak digambar pada garis provinsi
  (hanya untuk visualisasi) — menghilangkan bercak gelap; GeoJSON 1,7 MB → 0,85 MB.

## Fitur yang selesai
- **Tiga keadaan terhubung**: ikhtisar nasional (choropleth 514 kab/kota) → kab/kota (kamera `flyToBounds`,
  penanda lokasi, kartu kejadian) → lokasi (laporan per kejadian, tweet sumber). Breadcrumb, tombol
  "Kembali ke peta nasional", Escape untuk mundur satu tingkat, daftar kab/kota di panel.
- **Filter** jenis (chip multi-pilih, "Semua jenis", keadaan kosong eksplisit), kab/kota (combobox ARIA yang
  bisa dicari; hasilnya identik dengan klik peta), rentang tanggal (kuas histogram, pegangan yang bisa digeser
  dengan mouse/papan ketik, input tanggal, rentang cepat 7/30 hari/Semua). Semua filter AND; cakupan
  geografis dipertahankan saat filter berubah; "Atur ulang filter".
- **Penanda**: satu per `gazetteer_id`; cincin bersegmen sama besar = jenis yang hadir (bukan proporsi);
  angka = laporan unik; segitiga = gunung; garis putus-putus = lokasi di kab/kota lain yang dirujuk
  (Semeru di tampilan Kab. Malang tetap di posisinya di Lumajang). Klaster tampilan menampilkan jumlah lokasi unik.
- **Sorot** kejadian: penanda terkait ditegaskan, lainnya diredupkan; sorotan yang hilang karena filter dihapus
  dengan pengumuman `aria-live`.
- **Detail lokasi**: dampak/kebutuhan yang tertaut ke lokasi dipisahkan dari yang hanya tingkat kejadian
  (kasus Kalirejo); evakuasi; lembaga beserta perannya; tweet asli dengan waktu dan "Tautan sumber tidak tersedia"
  (tidak ada URL yang dikarang).
- **Backend FastAPI** baca-saja (mode file + lapisan Neo4j terisolasi), skrip seed terpisah.

## Keputusan visual & data
- Warna kategorikal 6 jenis (`--j-*`) dipakai di chip, kartu, penanda, histogram; choropleth memakai skala
  sekuensial terpisah (batu tulis → tinta) untuk **jumlah kejadian unik**. Abu muda = 0 sesuai filter
  (di dalam cakupan), arsir = di luar cakupan data.
- Kelas choropleth **tetap** (1, 2, 3, 4–5, ≥6) alih-alih kuantil: data jarang dan miring; batas tidak berubah
  diam-diam saat filter berganti.
- Semantik tanggal: kejadian masuk bila interval `start_time–end_time` beririsan dengan rentang; laporan,
  penanda, dan histogram memakai `tanggal_lokal`. Kartu menampilkan "x laporan pada rentang ini (dari y
  sepanjang data)". `end_time` diberi label "Laporan terakhir"; status ya/tidak → "Memenuhi / Belum memenuhi
  ambang bencana".
- Bingkai awal peta mengikuti cakupan data (Jawa Timur) dengan tombol "Seluruh Indonesia", supaya peta
  nasional tidak terlalu jauh untuk data yang terpusat.
- Gerak: drill-down 800 ms, penanda muncul setelah kamera berhenti (stagger ≤ 14 × 32 ms, hanya saat masuk),
  transisi isian poligon 380 ms, panel 300 ms; `prefers-reduced-motion` mematikan animasi dan kamera berpindah langsung.
- Permintaan per kanal memakai `AbortController` → respons usang tidak menimpa filter terbaru.

## Pengujian (dijalankan di lingkungan ini)
- `pytest` backend: **11 lulus** — hitungan distinct (tweet lintas kab dihitung sekali, satu tweet dua laporan),
  irisan interval vs tanggal laporan, `jenis=` kosong ≠ semua, satu penanda per lokasi, gunung lintas kab,
  dampak tanpa atribusi, laporan tingkat kab tanpa titik (gempa tanpa episentrum), validasi, 405 untuk metode tulis.
- Playwright (Chromium headless): **17 lulus** — tampilan awal Indonesia, hover tidak macet (gerak cepat lintas
  poligon, keluar ke laut/panel), pindah kab langsung, klik laut vs klik panel, zoom penanda tanpa gerak ulang,
  kartu sorot/lepas (mouse & papan ketik), filter & dropdown, sinkronisasi rentang atas–linimasa, minimalkan
  panel/legenda/linimasa, rujukan lintas kab, klik cepat berulang, lebar 1440/1024/768/390 px, reduced motion,
  tanpa error konsol. Tile OSM diganti piksel kosong di uji (tidak ada akses jaringan dari browser uji).

## Keterbatasan (jujur)
- **Prototipe `peta-situasi-bencana.html` tidak tersedia**; data contoh dibuat baru dan **bukan** dataset prototipe.
  Jumlahnya mengikuti skenario yang diminta: 7 kab/kota Jatim, 18 lokasi titik (+7 entri tingkat kab),
  15 kejadian, 33 laporan, 31 tweet. Teks tweet, tanggal, dan angka dampak dikarang; koordinat adalah posisi
  perkiraan tempat nyata yang sudah dicek berada di poligon kab/kota yang benar (Gunung Bromo jatuh di poligon
  Pasuruan sehingga diganti Kec. Sukapura).
- **Mode Neo4j belum diuji** terhadap basis data (tidak ada Neo4j di sini); Cypher ditulis mengikuti arah relasi
  di `adapter.REL`.
- Poligon kab/kota tidak dapat difokus dengan Tab satu per satu (514 path SVG); alternatif papan ketik: combobox
  wilayah dan daftar kab/kota di panel.
- Batas Kemendagri 2020 disederhanakan untuk visualisasi; 4 provinsi pemekaran Papua 2022 belum terpisah.
- Tile OSM tidak termuat di browser uji; tampilan latar belakang peta hanya diperiksa tanpa tile.

## Asumsi integrasi (belum final di skema)
1. `DisasterEvent.kode_kab` diturunkan dari modus `EventMention.kode_kab` (`adapter.event_kode_kab`, `queries.EVENT_KAB`).
2. Atribusi lokasi dampak hanya lewat `(AffectedObject)-[:LOCATED_IN]->(Location)` eksplisit.
3. Arah relasi: Tweet-REPORTS→Mention, Mention-CONSOLIDATED_INTO→Event, Mention-MENTIONS→Location,
   Mention-AFFECTED→AffectedObject, Mention-REQUIRES→Need, Mention-EVACUATED_TO→Location,
   Org-HANDLES→Mention, Org-DEPLOYED_TO→Location, Org-PART_OF→Org, Location-LOCATED_IN→Location.
4. Tingkat lokasi (desa/kecamatan/gunung/…) dan kab/kota lokasi dibaca dari gazetteer lokal, bukan properti Location.
5. `HumanitarianNeed.lokasi` berisi `gazetteer_id` atau null; `Location.coordinates` berupa titik lat/lon (null untuk tingkat kab).

## Di luar cakupan (tidak diimplementasikan)
Sinkronisasi state ke URL (tautan berbagi), pemuatan batas kecamatan/desa sebagai poligon, mode gelap,
ekspor CSV hasil filter.
