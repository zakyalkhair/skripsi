"""is_bencana: ambang Juklak BNPB 7/2023 (hlm. 7). Dihitung per laporan (EventMention) lalu diambil yang memenuhi."""
KONFIG = {"mode": "per_laporan",        # atau "jumlah" (dijumlah per kejadian)
          "min_laporan": 1,              # varian uji: 2
          "meninggal": 1, "dampak_orang": 50, "rusak_unit": 5, "lahan_ha": 1.0,
          "jumlah_kosong_meninggal": 1}  # meninggal tanpa angka dianggap 1 orang (desain sendiri)
BENDA = {"rumah", "pelayanan_dasar", "prasarana_vital"}


def _jml(a, kosong=None):
    j = a.get("jumlah")
    if isinstance(j, (int, float)): return float(j)
    return float(kosong) if kosong is not None else 0.0


def nilai_laporan(objek):
    """list objek dampak satu laporan -> dict besaran."""
    v = {"meninggal": 0.0, "dampak_orang": 0.0, "rusak_unit": 0.0, "lahan_ha": 0.0}
    for a in objek:
        k, st = a.get("kelas"), a.get("status") or ""
        if k == "manusia":
            if st == "meninggal": v["meninggal"] += _jml(a, KONFIG["jumlah_kosong_meninggal"])
            if st in ("luka", "mengungsi", "terdampak"): v["dampak_orang"] += _jml(a)
        elif k in BENDA and st.startswith("rusak"):
            if (a.get("satuan") or "unit") == "unit": v["rusak_unit"] += _jml(a)
        elif k == "sosial_ekonomi" and a.get("satuan") == "ha":
            v["lahan_ha"] += _jml(a)
    return v


def memenuhi(v, k=KONFIG):
    alasan = []
    if v["meninggal"] >= k["meninggal"]: alasan.append("meninggal")
    if v["dampak_orang"] >= k["dampak_orang"]: alasan.append("terdampak_50")
    if v["rusak_unit"] >= k["rusak_unit"]: alasan.append("rusak_5")
    if v["lahan_ha"] >= k["lahan_ha"]: alasan.append("lahan_1ha")
    return alasan


def is_bencana(daftar_objek_per_laporan, k=KONFIG):
    """-> (ya/tidak, alasan). Bantuan nasional & status darurat belum dapat dibaca (dicatat sebagai batasan)."""
    vs = [nilai_laporan(o) for o in daftar_objek_per_laporan]
    if k["mode"] == "jumlah":
        tot = {x: sum(v[x] for v in vs) for x in ("meninggal", "dampak_orang", "rusak_unit", "lahan_ha")}
        a = memenuhi(tot, k)
        return ("ya" if a else "tidak"), a
    ok = [memenuhi(v, k) for v in vs]
    n = sum(1 for a in ok if a)
    alasan = sorted({x for a in ok for x in a})
    return ("ya" if n >= k["min_laporan"] else "tidak"), alasan
