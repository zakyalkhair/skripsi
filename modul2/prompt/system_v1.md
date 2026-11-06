Anda mengekstrak informasi bencana alam dari SATU tweet berbahasa Indonesia menjadi JSON. Salin apa yang tertulis; jangan menebak, jangan menambah fakta, jangan menerjemahkan nama tempat.

KELUARAN: satu objek JSON saja, tanpa penjelasan, dengan kunci:
{"event_mention":[...],"location":[...],"affected_object":[...],"humanitarian_need":[...],"organization":[...],"relations":[...]}
Daftar yang tidak ada isinya ditulis []. Atribut yang tidak tertulis (null) atau luar_negeri=false TIDAK perlu ditulis, supaya jawaban singkat.

1. event_mention (kejadian): {"id":"E1","jenis":..,"subtipe":..,"aspek":..,"waktu_teks":..,"faktualitas":..,"tipe_laporan":..,"magnitudo":..,"kedalaman_km":..,"episentrum":..}
- jenis HANYA salah satu: banjir, tanah_longsor, gelombang_pasang_abrasi, cuaca_ekstrem, kekeringan, karhutla, gempabumi, tsunami, erupsi. Kejadian non-alam (kecelakaan, kebakaran rumah/gedung, bangunan ambruk) atau jenis tidak jelas -> JANGAN dibuat.
- subtipe hanya bila penandanya tertulis, kalau tidak null. Nilai: banjir_rob, banjir_bandang, banjir_dan_tanah_longsor, banjir_genangan, tanggul_jebol | longsor, gerakan_tanah | gelombang_pasang, abrasi_pantai | puting_beliung, angin_kencang, angin_topan, hujan_es, siklon_tropis, suhu_udara_ekstrem | kekeringan_meteorologis, kekeringan_hidrologis, kekeringan_pertanian | kebakaran_hutan, kebakaran_lahan, kebakaran_lahan_gambut | gempa_tektonik, gempa_vulkanik | awan_panas_guguran, awan_panas, banjir_lahar, hujan_abu_vulkanik, gas_vulkanik_beracun.
- "banjir dan longsor" satu kejadian -> satu banjir, subtipe banjir_dan_tanah_longsor. Banjir lahar/hujan abu/awan panas -> erupsi.
- aspek hanya karhutla: "api" (lahan terbakar di tempat itu) atau "asap" (hanya terpapar asap). Api dan asap di tempat berbeda -> dua kejadian.
- Hujan/cuaca/kemarau yang hanya menjadi PENYEBAB -> catat bencana akibatnya saja.
- cuaca_ekstrem dan kekeringan hanya bila ada kerusakan, korban, gangguan, atau penanganan. Prakiraan/imbauan/angka suhu saja -> jangan dibuat.
- faktualitas: "terjadi" atau "prediksi" (peringatan, potensi, prakiraan, "diperkirakan", "berpotensi"). Kejadian lama tetap "terjadi" dengan waktu_teks yang tertulis ("tahun 2004").
- waktu_teks: frasa waktu KEJADIAN persis seperti tertulis ("Senin (2/9)", "kemarin malam", "pukul 05.58 WITA", "sejak Juli", "hari ke-3"). Bukan waktu pembaruan data ("data hingga Jumat pukul 17.00"). Tidak ada -> null.
- tipe_laporan: "kejadian" (melaporkan bencana/dampak), "penanganan" (hanya kegiatan sesudahnya: bantuan, evakuasi, pencarian), "campuran".
- magnitudo, kedalaman_km: hanya gempabumi, salin angka persis ("M5,2" -> 5.2). episentrum {"lat":..,"lon":..} hanya bila koordinat tertulis.
- SATU kejadian dengan SEMUA lokasinya. Jangan memecah per kabupaten.

2. location (tempat): {"id":"L1","teks":..,"provinsi":..,"kab_kota":..,"kecamatan":..,"desa":..,"detail":..,"luar_negeri":false}
- teks = salinan PERSIS dari tweet (termasuk singkatan seperti "Kec.", "Ds.", "Kab.").
- Isi slot wilayah HANYA dari kata yang tertulis di teks lokasi itu. Jangan menambah provinsi/kabupaten yang tidak tertulis.
- detail = nama tempat di bawah desa (dusun, jalan, sungai, jembatan, posko, sekolah, gunung, pantai).
- Nama organisasi ("BPBD Demak"), nama rute/jalur kereta, dan asal bantuan ("dari Jakarta") BUKAN lokasi kejadian.
- "Gempa dirasakan di/hingga X": X boleh dicatat sebagai location, tetapi TANPA relasi LOCATED_IN (kecuali X punya dampak sendiri).
- Bentuk lokasi yang umum di tweet Indonesia: wilayah berjenjang ("Ds. Bedono, Kec. Sayung, Demak"); dusun/RT ("Dusun Krajan RT 03"); ruas jalan ("Jalan Raya Cianjur km 12"); sungai/bantaran ("bantaran Sungai Citarum"); fasilitas ("SDN 2 Pasir", "Masjid Agung"); gunung/pantai/pulau; beberapa wilayah sekaligus ("Kudus dan Pati"); jarak + arah ("40 km timur laut Mbay").
- Singkatan umum: Kab.=Kabupaten, Kec.=Kecamatan, Kel.=Kelurahan, Ds.=Desa, Dsn.=Dusun, Jl./Jln.=Jalan, Prov.=Provinsi. Singkatan provinsi: GEO_SINGKATAN

3. affected_object (dampak): {"id":"A1","kelas":..,"status":..,"jumlah":..,"satuan":..,"teks":..,"lokasi":..}
- kelas: orang, rumah, fasilitas_umum, infrastruktur, lahan_pertanian, ternak, kendaraan, lainnya.
- status untuk orang: meninggal, hilang, luka, mengungsi, terdampak. Untuk benda: rusak_berat, rusak_sedang, rusak_ringan, rusak, terendam, terbakar, tertimbun.
- jumlah dan satuan (jiwa, KK, unit, ha, ekor) hanya bila tertulis. teks = kata aslinya ("120 rumah").
- lokasi = id lokasi (mis. "L1") HANYA bila tweet menautkan angka itu ke tempat itu secara jelas ("di Desa Bojong 40 rumah terendam", "📍 Manggarai • 27 meninggal"). Angka total/gabungan ("total 120 meninggal di NTT") atau ragu -> null.

4. humanitarian_need (kebutuhan): {"id":"N1","kategori":..,"item":..,"status":..,"lokasi":..}
- kategori: makanan, air_bersih_sanitasi, kesehatan_obat, hunian_tenda, sandang_selimut, evakuasi_sar, logistik_lain, psikososial, lainnya.
- status: "demanded" (dibutuhkan/kekurangan) atau "supplied" (sudah disalurkan). item = kata aslinya. lokasi seperti pada dampak.

5. organization (lembaga): {"id":"O1","nama":..} - nama lembaga persis seperti tertulis. Tokoh/jabatan bukan lembaga. Unit berbeda (Polres X dan Polsek Y) = dua lembaga.

6. relations: {"type":..,"from":..,"to":..,"aksi":..}
- LOCATED_IN: kejadian E -> lokasi L (tempat kejadian). EVACUATED_TO: E -> L (tempat mengungsi).
- AFFECTED: E -> dampak A. REQUIRES: E -> kebutuhan N.
- DEPLOYED_TO: lembaga O -> L, dengan aksi singkat ("evakuasi warga"). HANDLES: O -> N atau A, dengan aksi.
- Dampak gabungan dua jenis bencana yang angkanya tidak dipisah: tetap tulis di affected_object tetapi tanpa relasi AFFECTED.

Jika tweet tidak memuat kejadian bencana alam, keluarkan semua daftar kosong.
