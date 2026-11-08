"""2.4: pecah EventMention per kabupaten + tanggal lokal + ketepatan + di luar periode."""
import re
from datetime import date, timedelta
from .zona import zona_provinsi, zona_dari_teks, waktu_lokal

BULAN = {"januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3, "april": 4, "apr": 4,
         "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "agustus": 8, "agu": 8, "agt": 8, "ags": 8,
         "september": 9, "sep": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11, "desember": 12, "des": 12}
HARI = {"senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "jum'at": 4, "sabtu": 5, "minggu": 6, "ahad": 6}
PERIODE_MULAI = date(2025, 1, 1)


def _tgl(d, m, y, ref):
    eksplisit = y is not None
    y = y if y else ref.year
    if y < 100: y += 2000
    try:
        dt = date(y, m, d)
    except ValueError:
        return None
    if not eksplisit and dt > ref:      # tanpa tahun & di masa depan -> tahun lalu
        dt = date(y - 1, m, d)
    return dt


def parse_waktu(teks, ref):
    """-> (list tanggal mutlak, ketepatan, sumber). ref = tanggal unggah lokal (date)."""
    t = (teks or "").lower()
    if not t.strip():
        return [ref], "pasti", "unggah"
    out = []
    for m in re.finditer(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", t):
        bln = BULAN.get(m.group(2))
        if bln:
            d = _tgl(int(m.group(1)), bln, int(m.group(3)) if m.group(3) else None, ref)
            if d: out.append(d)
    if True:
        for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t):
            d = _tgl(int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None, ref)
            if d: out.append(d)
    rentang = bool(re.search(r"\bhingga\b|\bsampai\b|\bs/d\b|\bsd\b|\d\s*-\s*\d|semalam\s*-|\bsejak\b|\bsemenjak\b", t))
    if out:
        out = sorted(set(out))
        if len(out) > 1 or rentang:
            return out, "rentang", "teks"
        return out, "pasti", "teks"
    for nama, idx in HARI.items():       # "Selasa kemarin" = selasa terakhir, bukan H-1
        if re.search(r"\b" + nama + r"\b", t) and re.search(r"kemarin|kemaren", t):
            sel = (ref.weekday() - idx) % 7 or 7
            return [ref - timedelta(days=sel)], "pasti", "hari"
    if re.search(r"kemarin|kemaren", t):
        return [ref - timedelta(days=1)], "pasti", "relatif"
    if re.search(r"semalam", t):
        return [ref - timedelta(days=1)], "rentang", "relatif"
    if re.search(r"hari ini|pagi ini|siang ini|sore ini|malam ini|tadi|barusan|\bini\b|^\d{1,2}[.:]\d{2}", t):
        return [ref], "pasti", "relatif"
    for nama, idx in HARI.items():
        if re.search(r"\b" + nama + r"\b", t):
            sel = (ref.weekday() - idx) % 7
            return [ref - timedelta(days=sel)], "pasti", "hari"
    if re.search(r"\d{1,2}[.:]\d{2}", t):
        return [ref], "pasti", "relatif"
    return [ref], "rentang", "tidak_terbaca"   # waktu_teks ada tapi tak terbaca -> hanya boleh attach


def _kab_dari_lokasi(loc):
    r = loc.get("resolution") or {}
    if r.get("status") != "resolved":
        return None, "gagal"
    ap = r.get("admin_path") or []
    if len(ap) < 2:
        return None, "prov_saja"
    nama = (r.get("admin_nama") or [None, None])[1] if r.get("admin_nama") else None
    return (ap[1], nama, ap[0]), "ok"


def _detail(loc):
    r = loc["resolution"]
    return {"id": loc["id"], "gazetteer_id": r.get("gazetteer_id"), "nama": r.get("nama_resmi") or loc.get("teks"),
            "level": r.get("level_admin"), "admin_path": r.get("admin_path"), "lat": r.get("lat"), "lon": r.get("lon")}


def pecah_record(rec, periode_mulai=PERIODE_MULAI):
    """Satu record hasil 2.3 -> list mention (satu per EM x kab)."""
    locs = {l["id"]: l for l in rec.get("location", [])}
    objs = {a["id"]: a for a in rec.get("affected_object", [])}
    needs = {n["id"]: n for n in rec.get("humanitarian_need", [])}
    rels = rec.get("relations", [])
    out = []
    for em in rec.get("event_mention", []):
        eid = em["id"]
        lids = [r["to"] for r in rels if r["type"] == "LOCATED_IN" and r["from"] == eid and r["to"] in locs]
        kabs, statuses = {}, []
        for lid in lids:
            hasil, st = _kab_dari_lokasi(locs[lid])
            statuses.append(st)
            if hasil:
                kabs.setdefault(hasil[0], {"kode_kab": hasil[0], "kab_nama": hasil[1], "kode_prov": hasil[2], "lokasi": []})["lokasi"].append(lid)
        linked = [r["to"] for r in rels if r["type"] in ("AFFECTED", "REQUIRES") and r["from"] == eid]
        obj_ids = [x for x in linked if x in objs]
        need_ids = [x for x in linked if x in needs]
        if kabs:
            grup, status = list(kabs.values()), "ok"
        else:
            kp = None
            for lid in lids:
                r_ = locs[lid].get("resolution") or {}
                if r_.get("status") == "resolved" and len(r_.get("admin_path") or []) == 1:
                    kp = r_["admin_path"][0]; break
            grup = [{"kode_kab": None, "kab_nama": None, "kode_prov": kp, "lokasi": []}]
            status = "prov_saja" if "prov_saja" in statuses else ("lokasi_gagal" if lids else "tanpa_lokasi")
        split = len(grup) > 1
        for g in grup:
            def milik(i, tab):
                lk = tab[i].get("lokasi")
                if not split: return True
                return lk in g["lokasi"]
            zt = zona_dari_teks(em.get("waktu_teks"))
            zona = zt or (zona_provinsi(g["kode_prov"]) if g["kode_prov"] else "WIB")
            ref = waktu_lokal(rec["created_at"], zona).date()
            tgl, ket, sumber = parse_waktu(em.get("waktu_teks"), ref)
            mid = f"{rec['tweet_id']}_{eid}" + (f"_{g['kode_kab']}" if split else "")
            out.append({
                "mention_id": mid, "tweet_id": rec["tweet_id"], "em_id": eid, "jenis": em["jenis"],
                "subtipe": em.get("subtipe"), "tipe_laporan": em.get("tipe_laporan"), "aspek": em.get("aspek"),
                "status_bencana": em.get("status_bencana"), "magnitudo": em.get("magnitudo"),
                "kode_kab": g["kode_kab"], "kab_nama": g["kab_nama"], "kode_prov": g["kode_prov"],
                "status_pecah": status, "zona": zona,
                "tanggal_unggah_lokal": ref.isoformat(),
                "tanggal_lokal": tgl[0].isoformat(), "tanggal_akhir": tgl[-1].isoformat(),
                "ketepatan": ket, "sumber_tanggal": sumber,
                "di_luar_periode": tgl[-1] < periode_mulai,
                "lokasi_ids": g["lokasi"],
                "lokasi_detail": [_detail(locs[i]) for i in (g["lokasi"] or lids)
                                  if (locs[i].get("resolution") or {}).get("status") == "resolved"],
                "objek_ids": [i for i in obj_ids if milik(i, objs)],
                "kebutuhan_ids": [i for i in need_ids if milik(i, needs)],
                "text": rec.get("text_raw"),
            })
    return out
