"""Hitung kasar sebaran bentuk penulisan lokasi pada tweet informatif DATA 2025 (pengembangan).

Hanya data 2025. Hitungan berbasis pola teks (regex), bukan penilaian makna: baca contoh keluarannya.
Pakai:  python scripts/hitung_bentuk_lokasi_2025.py dev_2025/data/processed/hasil_1_4.parquet [--keluar reports/bentuk_lokasi_2025.csv]
"""
import argparse, re, sys
import pandas as pd

BENTUK = {
    "alamat_bernomor": r"\b(?:jl|jln|jalan)\.?\s+[\w .'-]{2,40}?\s+(?:no\.?|nomor)\s*\d+",
    "nama_jalan": r"\b(?:jl|jln|jalan)\.?\s+[A-Za-z]",
    "jalan_nasional_tol": r"\b(?:tol|jalan\s+tol|jalan\s+nasional|jalur\s+pantura|pantura|trans\s+(?:sumatera|jawa|sulawesi|kalimantan))\b",
    "titik_tol": r"\b(?:tol|gt|gerbang\s+tol)\b.{0,30}\bkm\.?\s*\d+|\bkm\.?\s*\d+\b",
    "persimpangan": r"\b(?:perempatan|pertigaan|simpang|persimpangan|bundaran)\b",
    "ruas_jalan": r"\bruas\b|\b[A-Z][a-z]+\s*[-–]\s*[A-Z][a-z]+\b(?=.{0,20}(?:jalan|ruas))",
    "jembatan": r"\bjembatan\b",
    "fitur_alam": r"\b(?:sungai|kali|gunung|gn\.|pantai|pulau|danau|hutan|bukit|lembah|teluk|selat|laut)\s+[A-Z]",
    "bangunan_fasilitas": r"\b(?:pasar|rsud|rs\.?|puskesmas|masjid|musala|gereja|sdn?|smp?n?|sma|smk|ponpes|pesantren|waduk|bendungan|tanggul|terminal|stasiun|bandara|pelabuhan)\b",
    "lembaga_sbg_tempat": r"\b(?:kantor|balai|gedung)\s+(?:desa|kelurahan|kecamatan|camat|bupati|dprd|polres|polsek|koramil)\b",
    "satuan_administratif": r"\b(?:desa|ds\.|kelurahan|kel\.|kecamatan|kec\.|kabupaten|kab\.|kota|provinsi|prov\.)\s+[A-Z]",
    "deretan_berurutan": r"\b(?:desa|ds\.|kel\.|kelurahan)\s+[A-Z][\w']+(?:\s+[A-Z][\w']+)?\s*,\s*(?:kec\.|kecamatan)\s+[A-Z]",
    "beberapa_wilayah": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)?,?\s+(?:dan|&)\s+[A-Z][a-z]+",
    "dusun_kampung": r"\b(?:dusun|dsn\.|kampung|kp\.|lingkungan|dukuh|rt\.?\s*\d+|rw\.?\s*\d+|rt/rw)\b",
    "patokan_dengan_nama": r"\b(?:di\s+dekat|dekat|depan|belakang|samping|sebelah|sekitar)\s+(?:terminal|pasar|masjid|sd|smp|sma|jembatan|kantor|rs|puskesmas|stasiun|polres|polsek)\s+[A-Z]",
    "patokan_tanpa_nama": r"\b(?:di\s+depan|dekat|samping|sebelah)\s+(?:pasar|masjid|sekolah|jembatan|rumah|kantor)\b(?!\s+[A-Z])|\b\d+\s*km\s+(?:dari|ke)\s+(?:pusat\s+kota|kota|ibu\s+kota)",
}
OTOMATIS = re.compile(r"(?:gempa\s+mag\s*:|#gempa\s*::)", re.I)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("hasil_1_4"); ap.add_argument("--keluar", default="reports/bentuk_lokasi_2025.csv")
    a = ap.parse_args()
    d = pd.read_parquet(a.hasil_1_4)
    inf = d[(d.label == "informatif") & (d.is_representatif.astype(bool))].copy()
    inf["otomatis"] = inf.text_raw.map(lambda t: bool(OTOMATIS.search(t)))
    subset = {"semua informatif (wakil)": inf, "tanpa laporan otomatis gempa": inf[~inf.otomatis]}
    rows = []
    for nama_s, s in subset.items():
        n = len(s)
        for b, pat in BENTUK.items():
            # pola dengan [A-Z] dibaca tanpa membedakan huruf besar-kecil pada penanda; huruf pertama nama diperiksa terpisah
            pat_c = re.compile(pat, re.IGNORECASE)
            if "[A-Z]" in pat:
                cocok = s.text_raw.map(lambda t: any(m.group(0)[-1].isupper() for m in pat_c.finditer(t)))
            else:
                cocok = s.text_raw.map(lambda t: bool(pat_c.search(t)))
            k = int(cocok.sum())
            contoh = " || ".join(s[cocok].text_raw.head(2).str.replace("\n", " ").str[:110])
            rows.append(dict(subset=nama_s, n_tweet=n, bentuk=b, n_cocok=k, persen=round(100 * k / n, 1) if n else None, contoh=contoh))
    out = pd.DataFrame(rows); out.to_csv(a.keluar, index=False)
    pd.set_option("display.width", 200)
    print(out.pivot(index="bentuk", columns="subset", values="persen").to_string())
    print({k: len(v) for k, v in subset.items()})

if __name__ == "__main__":
    main()
