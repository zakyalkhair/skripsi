"""Skema ontologi untuk Modul 2 — versi 3 (17 Okt 2026). Satu sumber kebenaran untuk 2.1 dan 2.2.

Nilai enum mengikuti `ONTOLOGI-SKEMA-V1.md` (Project): 6 jenis dalam cakupan (kode BNPB) dan kelas dampak
Juklak BNPB 7/2023. LLM mengisi JSON per tweet; kode 2.2 memeriksa dan membuang yang tidak sah.
Wilayah resmi, koordinat, tanggal ternormalisasi, dan pemecahan per kabupaten TIDAK diisi LLM (2.3/2.4).

Perubahan dari versi 2 (semuanya keputusan sesi 17 Okt):
- jenis: 9 -> 6 (gelombang pasang/abrasi, kekeringan, tsunami di luar cakupan; tidak dibuatkan EventMention)
- kelas dampak: kelompok Juklak (manusia, rumah, pelayanan_dasar, prasarana_vital, sosial_ekonomi, lainnya) + objek
- status benda: ditambah `terganggu` (ONTOLOGI-SKEMA-V1) dan `terdampak` (tambahan v3: "9 rumah terdampak")
- kebutuhan: ditambah `dana`
- baru: `petunjuk_wilayah` (tagar/singkatan wilayah di teks; dipakai 2.3, bukan hasil akhir)
"""
from __future__ import annotations

JENIS = ("banjir", "tanah_longsor", "cuaca_ekstrem", "karhutla", "gempabumi", "erupsi")
KODE_BNPB = {"banjir": 101, "tanah_longsor": 102, "cuaca_ekstrem": 104, "karhutla": 106,
             "gempabumi": 107, "erupsi": 109}

# Jenis yang dikenal tetapi di luar cakupan (14 Okt): dibuang dengan peringatan, bukan galat.
DI_LUAR_CAKUPAN = {"gelombang_pasang_abrasi", "gelombang_pasang", "abrasi_pantai", "abrasi", "kekeringan",
                   "kekeringan_meteorologis", "kekeringan_hidrologis", "kekeringan_pertanian", "tsunami",
                   "tsunami_seismogenik", "tsunami_nonseismik", "tsunami_lokal", "tsunami_regional",
                   "tsunami_jarak", "tsunami_meteorologi", "mikrotsunami", "gelombang_tinggi",
                   "gelombang pasang", "gelombang tinggi"}

SUBTIPE: dict[str, set[str]] = {
    "banjir": {"banjir_rob", "banjir_bandang", "banjir_dan_tanah_longsor", "banjir_drainase_selokan",
               "banjir_waduk", "banjir_genangan", "tanggul_jebol"},
    "tanah_longsor": {"longsor", "gerakan_tanah"},
    "cuaca_ekstrem": {"puting_beliung", "angin_kencang", "angin_topan", "hujan_es", "siklon_tropis",
                      "suhu_udara_ekstrem"},
    "karhutla": {"kebakaran_hutan", "kebakaran_lahan", "kebakaran_lahan_gambut"},
    "gempabumi": {"gempa_tektonik", "gempa_vulkanik", "gempabumi_runtuhan"},
    "erupsi": {"awan_panas_guguran", "awan_panas", "banjir_lahar", "hujan_abu_vulkanik", "gas_vulkanik_beracun"},
}

# Sinonim -> (jenis, subtipe, aspek). Dipakai 2.2 (W_ENUM_SYNONYM).
SINONIM_JENIS: dict[str, tuple[str, str | None, str | None]] = {
    "gempa": ("gempabumi", None, None), "gempa bumi": ("gempabumi", None, None), "lindu": ("gempabumi", None, None),
    "longsor": ("tanah_longsor", None, None), "tanah longsor": ("tanah_longsor", None, None),
    "puting beliung": ("cuaca_ekstrem", "puting_beliung", None), "angin kencang": ("cuaca_ekstrem", "angin_kencang", None),
    "rob": ("banjir", "banjir_rob", None), "banjir rob": ("banjir", "banjir_rob", None),
    "banjir bandang": ("banjir", "banjir_bandang", None),
    "lahar": ("erupsi", "banjir_lahar", None), "banjir lahar": ("erupsi", "banjir_lahar", None),
    "letusan": ("erupsi", None, None), "erupsi gunung": ("erupsi", None, None),
    "kebakaran hutan": ("karhutla", "kebakaran_hutan", None), "kebakaran lahan": ("karhutla", "kebakaran_lahan", None),
    "kabut asap": ("karhutla", None, "asap"),
}

ASPEK = {"api", "asap"}
FAKTUALITAS = {"terjadi", "prediksi"}
TIPE_LAPORAN = {"kejadian", "penanganan", "campuran"}

# --- dampak: kelompok Juklak BNPB 7/2023 (ONTOLOGI-SKEMA-V1 §2.3, §3.4)
KELAS_AFFECTED = {"manusia", "rumah", "pelayanan_dasar", "prasarana_vital", "sosial_ekonomi", "lainnya"}
OBJEK: dict[str, set[str]] = {
    "pelayanan_dasar": {"satuan_pendidikan", "rumah_ibadat", "fasilitas_kesehatan", "kantor", "pasar"},
    "prasarana_vital": {"air_bersih", "listrik", "telekomunikasi", "irigasi", "jalan", "jembatan", "transportasi", "spbu"},
    "sosial_ekonomi": {"sawah", "lahan", "kebun", "hutan", "kolam", "kios_toko", "pabrik"},
    # `lainnya` = penampung kita sendiri untuk benda yang TIDAK ada di Juklak 7/2023 (bukan kelompok Juklak):
    # objek wisata, ternak, kendaraan. (Kelompok h Juklak "aset penanganan darurat" tidak dipakai di sini.)
    "lainnya": {"wisata", "ternak", "kendaraan"},
}
# Nama kelas versi 2 -> (kelas baru, objek). Dipetakan dengan peringatan W_KELAS_SINONIM.
KELAS_LAMA: dict[str, tuple[str, str | None]] = {
    "orang": ("manusia", None), "fasilitas_umum": ("pelayanan_dasar", None),
    "infrastruktur": ("prasarana_vital", None), "lahan_pertanian": ("sosial_ekonomi", "lahan"),
    "ternak": ("lainnya", "ternak"), "kendaraan": ("lainnya", "kendaraan"),
}
STATUS_ORANG = {"meninggal", "hilang", "luka", "mengungsi", "terdampak"}
STATUS_BENDA = {"rusak_berat", "rusak_sedang", "rusak_ringan", "rusak", "terendam", "terbakar", "tertimbun",
                "terganggu", "terdampak"}
SATUAN = {"jiwa", "KK", "unit", "ha", "ekor"}

KATEGORI_NEED = {"makanan", "air_bersih_sanitasi", "kesehatan_obat", "hunian_tenda", "sandang_selimut",
                 "evakuasi_sar", "logistik_lain", "psikososial", "dana", "lainnya"}
STATUS_NEED = {"demanded", "supplied"}

REL_TYPES = {"LOCATED_IN", "EVACUATED_TO", "AFFECTED", "REQUIRES", "DEPLOYED_TO", "HANDLES"}
DOMAIN_RANGE: dict[str, tuple[str, tuple[str, ...]]] = {
    "LOCATED_IN": ("E", ("L",)), "EVACUATED_TO": ("E", ("L",)), "AFFECTED": ("E", ("A",)),
    "REQUIRES": ("E", ("N",)), "DEPLOYED_TO": ("O", ("L",)), "HANDLES": ("O", ("N", "A")),
}

# kunci JSON -> awalan ID
BAGIAN = {"event_mention": "E", "location": "L", "affected_object": "A", "humanitarian_need": "N",
          "organization": "O", "petunjuk_wilayah": "P"}


def kombinasi_sah(kelas: str, status: str) -> bool:
    return status in (STATUS_ORANG if kelas == "manusia" else STATUS_BENDA)


def objek_sah(kelas: str, objek: str | None) -> bool:
    return objek is None or objek in OBJEK.get(kelas, set())


def kosong() -> dict:
    return {k: [] for k in BAGIAN} | {"relations": []}
