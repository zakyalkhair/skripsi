"""Nama & kode wilayah (provinsi, kab/kota) dari wilayah.sql, untuk nama DE dan wilayah organisasi."""
import re
from pathlib import Path

SQL = Path(__file__).resolve().parent.parent / "data" / "gazetir" / "wilayah.sql"


def muat(sql=SQL):
    nama = {}
    for line in open(sql, encoding="utf-8"):
        m = re.match(r"\('([\d.]+)','(.*)'\)[,;]", line)
        if m and len(m.group(1)) in (2, 5):
            nama[m.group(1)] = m.group(2).replace("''", "'").strip()
    return nama


def indeks_kab(nama):
    """nama ternormalisasi (tanpa awalan Kabupaten/Kota) -> [kode]; juga bentuk dengan awalan."""
    idx = {}
    for k, v in nama.items():
        if len(k) != 5: continue
        n = re.sub(r"[^\w\s]", " ", v.lower()); n = re.sub(r"\s+", " ", n).strip()
        idx.setdefault(n, []).append(k)
        idx.setdefault(re.sub(r"^(kabupaten|kota|kab)\s+", "", n), []).append(k)
    return idx
