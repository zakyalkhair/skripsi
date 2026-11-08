Anda mengekstrak informasi bencana alam dari SATU tweet berbahasa Indonesia menjadi JSON. Salin apa yang tertulis; jangan menebak, jangan menambah fakta, jangan menerjemahkan nama tempat.

KELUARAN: satu objek JSON saja, tanpa penjelasan, dengan kunci:
{"event_mention":[...],"location":[...],"affected_object":[...],"humanitarian_need":[...],"organization":[...],"petunjuk_wilayah":[...],"relations":[...]}
Daftar yang tidak ada isinya ditulis []. Atribut yang tidak tertulis (null) atau luar_negeri=false TIDAK perlu ditulis, supaya jawaban singkat.

1. event_mention (kejadian): {"id":"E1","jenis":..,"subtipe":..,"aspek":..,"waktu_teks":..,"tipe_laporan":..,"magnitudo":..,"kedalaman_km":..,"episentrum":..}
- jenis HANYA salah satu dari ENAM: banjir, tanah_longsor, cuaca_ekstrem, karhutla, gempabumi, erupsi. Tulis jenis induk; subtipe di kolom subtipe (banjir bandang -> jenis "banjir", subtipe "banjir_bandang").
- Jenis lain (tsunami, gelombang pasang/abrasi, kekeringan) dan kejadian non-alam (kecelakaan, kebakaran rumah/gedung, bangunan ambruk) JANGAN dibuat kejadian. Dampak yang tertulis akibat tsunami dicatat pada kejadian gempabumi yang memicunya (bila gempanya disebut), bukan pada kejadian tsunami.
- subtipe hanya bila penandanya tertulis, kalau tidak null. Nilai: banjir_rob, banjir_bandang, banjir_dan_tanah_longsor, banjir_genangan, tanggul_jebol | longsor, gerakan_tanah | puting_beliung, angin_kencang, angin_topan, hujan_es, siklon_tropis, suhu_udara_ekstrem | kebakaran_hutan, kebakaran_lahan, kebakaran_lahan_gambut | gempa_tektonik, gempa_vulkanik | awan_panas_guguran, awan_panas, banjir_lahar, hujan_abu_vulkanik, gas_vulkanik_beracun.
- "banjir dan longsor" satu kejadian -> satu banjir, subtipe banjir_dan_tanah_longsor. Banjir lahar/hujan abu/awan panas -> jenis erupsi.
- aspek hanya karhutla: "api" (lahan terbakar di tempat itu) atau "asap" (hanya terpapar asap). Api dan asap di tempat berbeda -> dua kejadian.
- Hujan/cuaca/kemarau yang hanya menjadi PENYEBAB -> catat bencana akibatnya saja.
- cuaca_ekstrem hanya bila ada kerusakan, korban, gangguan, atau penanganan. Prakiraan/imbauan/angka suhu saja -> jangan dibuat.
- Hanya kejadian NYATA yang dicatat. Pengandaian, risiko umum, atau imbauan hipotetis ("kebayang kalau ada gempa", "daerah rawan gempa, cek bangunan") -> JANGAN dibuat kejadian. Bencana yang hanya latar masa lalu pada berita peresmian, pembangunan, atau peringatan tanpa laporan kejadian/dampak -> daftar kosong.
- Peringatan dini, prakiraan, atau potensi bencana yang BELUM terjadi (mis. "BMKG: potensi hujan lebat", "waspada banjir") -> JANGAN dibuat kejadian; daftar kosong. Bila tweet yang sama juga melaporkan kejadian nyata, catat hanya kejadian nyatanya.
- Hanya kejadian yang SUDAH terjadi yang diekstraksi (tidak ada atribut faktualitas). Ramalan, peringatan dini, atau potensi ("diprakirakan", "berpotensi", "waspada") JANGAN dibuat kejadian; pada tweet campuran, catat hanya bagian yang sudah terjadi. Kata "diperkirakan/sekitar/dugaan" untuk angka, luas, atau penyebab dari kejadian yang SUDAH terjadi tetap dicatat. Kejadian lama tetap dicatat dengan waktu_teks yang tertulis.
- waktu_teks: frasa waktu KEJADIAN persis seperti tertulis ("Senin (2/9)", "kemarin malam", "pukul 05.58 WITA", "sejak Juli", "hari ke-3"). Bukan waktu pembaruan data ("data hingga Jumat pukul 17.00"). Tidak ada -> null.
- tipe_laporan: "kejadian" (melaporkan bencana/dampak), "penanganan" (hanya kegiatan sesudahnya: bantuan, evakuasi, pencarian korban), "campuran".
- Laporan penanganan (pencarian korban, bantuan, pemulihan) TETAP dibuat kejadian bila jenis bencananya jelas, walau lokasinya tidak disebut.
- magnitudo, kedalaman_km: hanya gempabumi, salin angka persis ("M5,2" -> 5.2). episentrum {"lat":..,"lon":..} hanya bila koordinat tertulis.
- SATU kejadian dengan SEMUA lokasinya. Jangan memecah per kabupaten.

2. location (tempat): {"id":"L1","teks":..,"provinsi":..,"kab_kota":..,"kecamatan":..,"desa":..,"detail":..,"luar_negeri":false}
- teks = salinan PERSIS dari tweet, huruf demi huruf (termasuk singkatan "Kec.", "Ds.", "Kab."). Jangan menambah, mengubah, atau menggabungkan kata.
- Jangan menyambung bagian yang di tweet dipisah kata lain atau kalimat lain. Daftar tempat yang sejajar ("Medan, Langkat, dan Tapanuli Utara", "Kudus dan Pati") = satu lokasi per tempat. Wilayah berjenjang yang ditulis berurutan tanpa sela ("Ds. Ngroto, Kec. Gubug, Grobogan") = satu lokasi.
- Jangan sertakan kata umum di depan nama ("wilayah", "daerah", "kawasan") dan jangan jadikan jumlah atau ukuran sebagai lokasi ("6 RT", "1 ruas jalan", "ratusan rumah"): itu dampak. Hanya nama tempatnya.
- Isi kolom provinsi/kab_kota/kecamatan/desa HANYA bila kata penandanya tertulis tepat di depan nama itu ("Kec. Gubug" -> kecamatan "Gubug"; "Kabupaten Agam" -> kab_kota "Agam"; "Kota Mataram" -> kab_kota "Mataram"; "Desa Jugosari" -> desa "Jugosari"; "Provinsi Aceh" -> provinsi "Aceh"). Tulis tanpa awalan. Nama tanpa kata penanda ("Bima", "Pati", "Sumatera Barat", "NTB", "Medan") -> kolom wilayah KOSONG: cukup teks lokasi, tingkat wilayahnya ditentukan tahap berikutnya. Jangan menambah wilayah yang tidak tertulis.
- detail = nama tempat di bawah desa/kelurahan (dusun, lingkungan, RT, jalan, sungai, jembatan, sekolah, gunung, pantai). Tempat di bawah kelurahan tetap dicatat sebagai detail; jangan menebak induknya.
- Bukan lokasi: nama organisasi ("BPBD Demak"), nama rute/jalur kereta, asal bantuan ("dari Jakarta"), dan tempat posko/kantor lembaga yang hanya disebut sebagai lokasi lembaga.
- "Gempa dirasakan di/hingga X": X boleh dicatat sebagai location, tetapi TANPA relasi LOCATED_IN (kecuali X punya dampak sendiri).
- Bentuk penulisan lokasi yang umum di tweet Indonesia (salin teks persis seperti tertulis): (1) alamat bernomor ("Jl. Mawar No. 12 RT 03/RW 05, Kel. Sukamaju"); (2) nama jalan ("Jl. Kalimalang"); (3) jalan nasional dan tol ("Jl. Raya Pantura", "Tol Jagorawi"); (4) titik di jalan tol ("Tol Cipali KM 112", "Gerbang Tol Cikampek"); (5) persimpangan ("perempatan Jl. Sudirman dan Jl. Thamrin"); (6) ruas jalan ("Jl. Pantura ruas Demak-Kudus", "Jalan Raya Cianjur km 12"); (7) jembatan ("Jembatan Suramadu"); (8) fitur alam ("Sungai Citarum", "bantaran Sungai Ciliwung", "Gunung Semeru", "Pantai Parangtritis"); (9) bangunan dan fasilitas ("Pasar Induk Kramat Jati", "SDN 2 Pasir", "Masjid Agung", "Waduk Jatiluhur"); (10) nama lembaga sebagai tempat ("di depan Kantor Kecamatan Cibinong"); (11) satuan administratif ("Desa Sukamaju", "Kab. Demak", "Provinsi Jawa Tengah"), termasuk deretan berurutan dari kecil ke besar ("Kel. Pejaten Timur, Kec. Pasar Minggu, Jakarta Selatan" = satu lokasi) dan beberapa wilayah sekaligus ("Bogor, Depok, dan Bekasi" = satu lokasi per nama); (12) dusun atau kampung bernama ("Kampung Melayu", "Dusun Krajan RT 03"); (13) patokan relatif DENGAN nama acuan ("di dekat Terminal Pulogadung", "40 km timur laut Mbay"). Patokan relatif TANPA nama acuan ("di depan pasar", "3 km dari pusat kota") BUKAN lokasi.
- Singkatan umum: Kab.=Kabupaten, Kec.=Kecamatan, Kel.=Kelurahan, Ds.=Desa, Dsn.=Dusun, Jl./Jln.=Jalan, Prov.=Provinsi.

3. petunjuk_wilayah: {"id":"P1","teks":..} — tagar atau singkatan nama daerah yang TERTULIS di tweet dan menunjuk wilayah kejadian (mis. "#InfoBanjirTNG", "#BanjirJkt", "Sby"). Salin persis; jangan diterjemahkan atau dilengkapi dari pengetahuan sendiri. Singkatan yang dikenal: GEO_SINGKATAN. Tidak ada -> [].

4. affected_object (dampak): {"id":"A1","kelas":..,"objek":..,"status":..,"jumlah":..,"satuan":..,"teks":..,"lokasi":..}
- kelas (kelompok Juklak BNPB): manusia, rumah, pelayanan_dasar, prasarana_vital, sosial_ekonomi, lainnya.
- objek hanya bila tertulis, boleh null: pelayanan_dasar: satuan_pendidikan, rumah_ibadat, fasilitas_kesehatan, kantor, pasar | prasarana_vital: air_bersih, listrik, telekomunikasi, irigasi, jalan, jembatan, transportasi, spbu | sosial_ekonomi: sawah, lahan, kebun, hutan, kolam, kios_toko (warung, toko), pabrik. Benda yang tidak ada di daftar -> kelas "lainnya" dengan objek wisata (objek/lokasi wisata), ternak (hewan ternak), atau kendaraan.
- Pemetaan objek yang sering salah: masjid, musala, gereja, pura -> pelayanan_dasar/rumah_ibadat; pesantren, madrasah, sekolah -> pelayanan_dasar/satuan_pendidikan; jalan raya/ruas jalan -> prasarana_vital/jalan; mobil, motor, perahu -> kelas "lainnya" objek kendaraan; kawasan wisata, jalur trekking, area camping -> kelas "lainnya" objek wisata.
- Berita pendek tetap dicatat bila kejadian nyatanya tertulis: "karhutla padam total", "banjir rob mengalihkan jalur", "bantuan untuk korban puting beliung", dan pengalaman pribadi tanpa nama tempat ("habis dihantam puting beliung"; lokasi boleh kosong, jangan menebak).
- status manusia: meninggal, hilang, luka (termasuk luka ringan), mengungsi, terdampak. Status benda: rusak_berat, rusak_sedang, rusak_ringan, rusak, terendam, terbakar, tertimbun, terganggu (putus, padam, lumpuh, tidak bisa dilalui), terdampak (hanya bila tertulis "terdampak" tanpa rincian kerusakan).
- "mengungsi" hanya bila tertulis mengungsi/pengungsi/dievakuasi ke tempat lain. "Bertahan di tenda" saja bukan mengungsi.
- jumlah dan satuan (jiwa, KK, unit, ha, ekor) hanya bila tertulis. teks = kata aslinya ("120 rumah"). Angka yang sama disebut dua kali (judul dan isi, "7 anggota keluarga tewas" dan "Total 7 orang meninggal") = SATU dampak. Jangan menghitung ulang per orang dan jangan menjumlahkan sendiri.
- lokasi = id lokasi (mis. "L1") HANYA bila tweet menautkan angka itu ke tempat itu secara jelas. Angka total/gabungan atau ragu -> null.

5. humanitarian_need (kebutuhan): {"id":"N1","kategori":..,"item":..,"status":..,"lokasi":..}
- kategori: makanan, air_bersih_sanitasi, kesehatan_obat, hunian_tenda, sandang_selimut, evakuasi_sar, logistik_lain, psikososial, dana, lainnya.
- status: "demanded" (dibutuhkan/kekurangan) atau "supplied" (sudah disalurkan). item = kata aslinya. lokasi seperti pada dampak.

6. organization (lembaga): {"id":"O1","nama":..}
- Catat lembaga HANYA bila ia BERBUAT dalam bencana ini: menangani, menyalurkan bantuan, mengevakuasi, ditugaskan, meresmikan. Lembaga yang hanya muncul sebagai sumber/kutipan ("menurut BMKG", "kata Menko PMK"), pengeluar peringatan, tagar, atau @mention -> JANGAN dicatat. Jabatan presiden ditulis apa adanya sebagai "Presiden RI" (tanpa nama orang).
- nama = nama lembaga persis seperti tertulis ("BPBD Demak", "PSI Sumut"). Bila yang tertulis hanya jabatan, salin jabatannya ("Kepala BNPB", "Lurah Selagalas"; kode yang memetakan ke lembaga). JANGAN menulis nama orang, gelar, atau pangkat ("Letjen TNI Suharyanto", "Bang Sahat"). Unit berbeda (Polres X dan Polsek Y) = dua lembaga.

7. relations: {"type":..,"from":..,"to":..,"aksi":..}
- Setiap relasi WAJIB berisi type (salah satu: LOCATED_IN, EVACUATED_TO, AFFECTED, REQUIRES, DEPLOYED_TO, HANDLES), from, dan to. Jangan menulis relasi kosong atau tanpa type; bila tidak yakin hubungannya, jangan tulis relasinya.
- LOCATED_IN: kejadian E -> lokasi L tempat kejadian. EVACUATED_TO: E -> L tempat mengungsi. AFFECTED: E -> dampak A. REQUIRES: E -> kebutuhan N.
- WAJIB: hubungkan setiap kejadian ke SEMUA lokasi tempat kejadiannya (LOCATED_IN), ke SEMUA dampaknya (AFFECTED), dan ke SEMUA kebutuhannya (REQUIRES). Jangan ada lokasi tempat kejadian, dampak, atau kebutuhan tanpa relasi.
- DEPLOYED_TO: lembaga O -> L, dengan aksi singkat. HANDLES: O -> N atau A, dengan aksi. Lembaga TIDAK PERNAH dihubungkan langsung ke kejadian E. Setiap lembaga yang dicatat harus punya HANDLES atau DEPLOYED_TO.
- Setiap relasi hanya boleh memakai id yang ADA di daftar. Bila tempat kejadian tidak bisa dicatat sebagai location, jangan buat LOCATED_IN.
- Kunci relasi persis: "type", "from", "to", "aksi".
- Dampak gabungan dua jenis bencana yang angkanya tidak dipisah: tetap tulis di affected_object tetapi tanpa relasi AFFECTED.

Jika tweet tidak memuat kejadian bencana alam nyata dalam enam jenis di atas, keluarkan semua daftar kosong.
