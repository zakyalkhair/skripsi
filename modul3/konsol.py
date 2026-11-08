"""3.2 Konsolidasi EventMention -> DisasterEvent. Aturan = Tabel 3.X (satuan & aturan per jenis) + TEKNIS-3 §3.2.
Nama aturan (properti CONSOLIDATED_INTO.aturan) memakai kata, bukan kode."""
import re
from datetime import date, timedelta, datetime
from collections import defaultdict
from . import ambang as AMB
from .zona import OFFSET

CFG = {
    "banjir_jeda": 3, "banjir_lanjut": 7, "penanganan": 14, "erupsi_jeda": 14, "karhutla_jeda": 14,
    "gempa_aktif": 14, "gempa_dmag": 0.3, "gempa_detik": 120, "lanjutan_umum": 7,
}
RE_LANJUT = re.compile(r"\bmasih\b|belum surut|tak surut|tidak surut|hari ke[- ]?\d+|sepekan|seminggu|sejak\b|berlanjut|lanjutan|update|terkini", re.I)
RE_GELOMBANG = re.compile(r"banjir (kembali|susulan|lagi)|kembali (melanda|merendam|terendam|banjir)|gelombang (kedua|baru)|banjir (kedua|ke-?\d)", re.I)
RE_PENCARIAN = re.compile(r"pencarian|evakuasi korban|\bkorban longsor\b|tim sar|hari ke[- ]?\d+", re.I)
RE_SEBAB_GEMPA = re.compile(r"(akibat|pasca|imbas|dampak|picu|dipicu|usai|setelah)\s+(oleh\s+)?gempa", re.I)
RE_GUNUNG = re.compile(r"\b(?:gunung|gn\.?|g\.)\s*([A-Z][A-Za-z]+(?:\s[A-Z][a-z]+)?)")
SUMBER_KUAT = {"teks": 3, "hari": 2, "relatif": 2, "unggah": 1, "tidak_terbaca": 0}


def d(s): return date.fromisoformat(s)


def siapkan(m):
    m = dict(m)
    m["d0"], m["d1"] = d(m["tanggal_lokal"]), d(m["tanggal_akhir"])
    t = m.get("text") or ""
    m["lanjut"] = bool(RE_LANJUT.search(t) or RE_LANJUT.search(m.get("waktu_teks") or ""))
    m["gelombang"] = bool(RE_GELOMBANG.search(t))
    m["pencarian"] = bool(RE_PENCARIAN.search(t))
    m["sebab_gempa"] = bool(RE_SEBAB_GEMPA.search(t))
    m["wil_kecil"] = {c for l in m.get("lokasi_detail", []) for c in (l.get("admin_path") or [])[2:]}
    m["utc"] = _utc(m)
    return m


def _utc(m):
    mt = re.search(r"(\d{1,2})[.:](\d{2})", m.get("waktu_teks") or "")
    if not mt or m["ketepatan"] != "pasti": return None
    try:
        return datetime(m["d0"].year, m["d0"].month, m["d0"].day, int(mt.group(1)), int(mt.group(2))) - timedelta(hours=OFFSET[m["zona"]])
    except ValueError:
        return None


class DE:
    n = 0
    def __init__(s, jenis, kunci, m, aturan):
        DE.n += 1; s.no = DE.n
        s.jenis, s.kunci, s.anggota, s.tambahan = jenis, kunci, [], set()
        s.kab, s.tanggal, s.subtipe, s.mag, s.utc = set(), set(), None, None, None
        s.tambah(m, aturan)

    def tambah(s, m, aturan):
        s.anggota.append((m, aturan))
        if m["kode_kab"]: s.kab.add(m["kode_kab"])
        s.tanggal.update(m["d0"] + timedelta(days=i) for i in range((m["d1"] - m["d0"]).days + 1))
        s.subtipe = s.subtipe or m.get("subtipe")
        if m.get("magnitudo") is not None and s.mag is None: s.mag = m["magnitudo"]
        s.utc = s.utc or m["utc"]
        if m["jenis"] != s.jenis: s.tambahan.add(m["jenis"])

    start = property(lambda s: min(s.tanggal))
    last = property(lambda s: max(s.tanggal))
    wil_kecil = property(lambda s: {c for m, _ in s.anggota for c in m["wil_kecil"]})


class Konsol:
    def __init__(self, cfg=None):
        self.cfg = dict(CFG, **(cfg or {}))
        self.de = []
        self.log = []          # satu baris per mention: keputusan
        self.tidak = []

    # -- util
    def _log(self, m, aturan, de=None, catatan=None):
        self.log.append({"mention_id": m["mention_id"], "jenis": m["jenis"], "aturan": aturan,
                         "de_no": de.no if de else None, "catatan": catatan})

    def _baru(self, m, aturan, jenis=None, kunci=None):
        de = DE(jenis or m["jenis"], kunci, m, aturan); self.de.append(de); self._log(m, aturan, de); return de

    def _gabung(self, de, m, aturan, catatan=None):
        de.tambah(m, aturan); self._log(m, aturan, de, catatan); return de

    def _cari(self, jenis, kunci):
        return [x for x in self.de if x.jenis == jenis and x.kunci == kunci]

    def _terakhir(self, jenis, kunci):
        c = self._cari(jenis, kunci)
        return max(c, key=lambda x: x.last) if c else None

    # -- penanganan: umum
    def _penanganan(self, m, jenis, kunci):
        de = self._terakhir(jenis, kunci)
        if de and -1 <= (m["d0"] - de.last).days <= self.cfg["penanganan"] and m["d0"] >= de.start - timedelta(days=1):
            return self._gabung(de, m, "penanganan_14_hari")
        return self._baru(m, "penanganan_tanpa_kejadian_aktif", jenis, kunci)

    def _cocok_kecil(self, m, cands):
        """banyak kandidat aktif: pakai desa/kecamatan; gagal -> None."""
        if len(cands) == 1: return cands[0]
        sama = [c for c in cands if m["wil_kecil"] & c.wil_kecil]
        return sama[0] if len(sama) == 1 else None

    # -- per jenis
    def banjir(self, m):
        kab = m["kode_kab"]; de = self._terakhir("banjir", kab)
        if m["tipe_laporan"] == "penanganan": return self._penanganan(m, "banjir", kab)
        if not de: return self._baru(m, "kejadian_baru", kunci=kab)
        gap = (m["d0"] - de.last).days; beda_hari = m["d0"] not in de.tanggal
        if m["gelombang"] and beda_hari: return self._baru(m, "gelombang_baru", kunci=kab)
        if m.get("subtipe") and de.subtipe and m["subtipe"] != de.subtipe and beda_hari:
            return self._baru(m, "subtipe_berbeda", kunci=kab)
        if gap <= self.cfg["banjir_jeda"]: return self._gabung(de, m, "jeda_maks_3_hari")
        if m["lanjut"] and gap <= self.cfg["banjir_lanjut"]: return self._gabung(de, m, "penanda_lanjutan_7_hari")
        return self._baru(m, "jeda_melewati_batas", kunci=kab)

    def _harian(self, m, jenis, p_sama, p_baru, p_ganda):
        """cuaca ekstrem & tanah longsor: kab + tanggal kejadian."""
        kab = m["kode_kab"]
        if jenis == "tanah_longsor" and m["sebab_gempa"]:
            g = [x for x in self.de if x.jenis == "gempabumi" and kab in x.kab and x.start - timedelta(days=1) <= m["d0"] <= x.start + timedelta(days=self.cfg["gempa_aktif"])]
            if len(g) == 1:
                g[0].tambahan.add("tanah_longsor"); return self._gabung(g[0], m, "longsor_akibat_gempa")
        if m["tipe_laporan"] == "penanganan" or (jenis == "tanah_longsor" and m["pencarian"] and m["tipe_laporan"] != "kejadian"):
            return self._penanganan(m, jenis, kab)
        cs = self._cari(jenis, kab)
        pas = [c for c in cs if m["d0"] in c.tanggal]
        if m["sumber_tanggal"] == "unggah":     # tanpa tanggal di teks: tanggal publikasi atau satu hari sebelumnya
            pas = pas or [c for c in cs if (m["d0"] - timedelta(days=1)) in c.tanggal]
        if pas:
            c = self._cocok_kecil(m, pas)
            if c: return self._gabung(c, m, p_sama)
            self.tidak.append(m); self._log(m, p_ganda, catatan="kandidat ganda, desa/kecamatan tidak membedakan"); return None
        if m["lanjut"]:
            near = [c for c in cs if 0 <= (m["d0"] - c.last).days <= self.cfg["lanjutan_umum"]]
            if near: return self._gabung(max(near, key=lambda x: x.last), m, "informasi_lanjutan")
        return self._baru(m, p_baru, kunci=kab)

    def cuaca_ekstrem(self, m):
        return self._harian(m, "cuaca_ekstrem", "wilayah_tanggal_sama", "tanggal_berbeda_kejadian_baru", "kandidat_ganda_tidak_dikonsolidasi")

    def tanah_longsor(self, m):
        return self._harian(m, "tanah_longsor", "wilayah_tanggal_sama", "tanggal_berbeda_kejadian_baru", "kandidat_ganda_tidak_dikonsolidasi")

    def gempabumi(self, m):
        kab, c = m["kode_kab"], self.cfg
        aktif = [x for x in self.de if x.jenis == "gempabumi" and x.start - timedelta(days=1) <= m["d0"] <= x.start + timedelta(days=c["gempa_aktif"])]
        sekab = [x for x in aktif if kab in x.kab]
        if sekab:
            x = max(sekab, key=lambda z: z.last)
            return self._gabung(x, m, "wilayah_tanggal_sama" if m["d0"] in x.tanggal else "gempa_susulan_masa_aktif")
        # kab baru: perlu penghubung
        def penghubung(x):
            if m.get("magnitudo") is not None and x.mag is not None and abs(m["magnitudo"] - x.mag) <= c["gempa_dmag"] + 1e-9: return "selisih_magnitudo"
            if m["utc"] and x.utc and abs((m["utc"] - x.utc).total_seconds()) <= c["gempa_detik"]: return "selisih_waktu_utc"
            return None
        ok = [(x, p) for x in aktif if (p := penghubung(x))]
        if ok:
            x, p = ok[0]; return self._gabung(x, m, "lintas_wilayah_" + p)
        return self._baru(m, "gempa_baru_tanpa_penghubung", kunci=None)

    def erupsi(self, m):
        # jangkar: lokasi gunung (OSM) > nama "Gunung X" di teks > fallback kabupaten
        g = next((l["nama"] for l in m.get("lokasi_detail", []) if (l.get("gazetteer_id") or "").startswith("osm:")
                  and re.match(r"(?i)(gunung|gn\.?)\s", l.get("nama") or "")), None)
        if g: kunci, cat = ("gunung", g.lower()), None
        else:
            mt = RE_GUNUNG.search(m.get("text") or "")
            if mt: kunci, cat = ("gunung", mt.group(1).lower()), None
            elif m["kode_kab"]: kunci, cat = ("kab", m["kode_kab"]), "jangkar_gunung_tidak_ada_pakai_kabupaten"
            else: self.tidak.append(m); self._log(m, "tanpa_jangkar_gunung"); return None
        de = self._terakhir("erupsi", kunci)
        if de and (m["d0"] - de.last).days <= self.cfg["erupsi_jeda"]:
            return self._gabung(de, m, "episode_jeda_maks_14_hari", cat)
        x = self._baru(m, "episode_baru", kunci=kunci)
        if cat: self.log[-1]["catatan"] = cat
        return x

    def karhutla(self, m):
        prov = m["kode_prov"]
        if not prov or (m["status_pecah"] == "tanpa_lokasi"):
            self.tidak.append(m); self._log(m, "tanpa_provinsi_tidak_dikonsolidasi"); return None
        de = self._terakhir("karhutla", prov)
        if de and (m["d0"] - de.last).days <= self.cfg["karhutla_jeda"]:
            return self._gabung(de, m, "penanganan_provinsi_14_hari" if m["tipe_laporan"] == "penanganan" else "episode_provinsi_jeda_maks_14_hari")
        return self._baru(m, "episode_provinsi_baru", kunci=prov)

    # -- rentang & luas
    def rentang(self, m):
        cs = [x for x in self.de if x.jenis == m["jenis"] and m["kode_kab"] in x.kab
              and any(m["d0"] <= t <= m["d1"] for t in x.tanggal)]
        if len(cs) == 1: return self._gabung(cs[0], m, "rentang_menempel")
        self.tidak.append(m); self._log(m, "rentang_tanpa_kejadian" if not cs else "rentang_calon_ganda"); return None

    def luas(self, m):
        prov = m["kode_prov"]; cs = []
        if prov:
            cs = [x for x in self.de if x.jenis == m["jenis"] and prov in {k.split(".")[0] for k in x.kab}
                  and x.start - timedelta(days=1) <= m["d0"] <= x.last + timedelta(days=self.cfg["penanganan"])]
        if len(cs) == 1: return self._gabung(cs[0], m, "lokasi_luas_satu_kejadian_aktif")
        self.tidak.append(m); self._log(m, "lokasi_luas_tidak_dikonsolidasi", catatan=f"{len(cs)} kandidat"); return None

    # -- jalankan
    def jalankan(self, mentions):
        ms = sorted((siapkan(m) for m in mentions), key=lambda m: (m["d0"], m["tweet_id"]))
        tunda_rentang, tunda_luas = [], []
        order = ["gempabumi", "erupsi", "karhutla", "banjir", "cuaca_ekstrem", "tanah_longsor"]
        for jenis in order:
            for m in (x for x in ms if x["jenis"] == jenis):
                if m["di_luar_periode"]: self.tidak.append(m); self._log(m, "di_luar_periode"); continue
                if m["jenis"] == "karhutla":
                    if m["kode_prov"] is None: self.tidak.append(m); self._log(m, "tanpa_provinsi_tidak_dikonsolidasi"); continue
                    if m["ketepatan"] == "rentang": tunda_rentang.append(m); continue
                    self.karhutla(m); continue
                if not m["kode_kab"]:
                    if m["kode_prov"]: tunda_luas.append(m)
                    else: self._abaikan(m)
                    continue
                if m["ketepatan"] == "rentang": tunda_rentang.append(m); continue
                getattr(self, jenis)(m)
        for m in tunda_rentang:
            (self.rentang if m["jenis"] != "karhutla" else self._rentang_karhutla)(m)
        for m in tunda_luas: self.luas(m)
        self._majemuk()
        return self.de

    def _abaikan(self, m):
        self.tidak.append(m)
        self._log(m, "tanpa_wilayah_tidak_dikonsolidasi", catatan=m["status_pecah"])
        return None

    def _rentang_karhutla(self, m):
        cs = [x for x in self._cari("karhutla", m["kode_prov"]) if any(m["d0"] <= t <= m["d1"] for t in x.tanggal)]
        if len(cs) == 1: return self._gabung(cs[0], m, "rentang_menempel")
        self.tidak.append(m); self._log(m, "rentang_tanpa_kejadian" if not cs else "rentang_calon_ganda")

    def _majemuk(self):
        """jenis berbeda disebut dalam tweet yang sama dan kab beririsan -> satu DE; jenis = tipe utama."""
        berubah = True
        while berubah:
            berubah = False
            for a in self.de:
                for b in self.de:
                    if a is b or a.no > b.no or a.jenis == b.jenis: continue
                    ta = {m["tweet_id"] for m, _ in a.anggota}; tb = {m["tweet_id"] for m, _ in b.anggota}
                    if ta & tb and (a.kab & b.kab):
                        utama, lain = (a, b) if self._peringkat(a) >= self._peringkat(b) else (b, a)
                        utama.anggota += [(m, "majemuk") for m, _ in lain.anggota]
                        utama.tambahan |= {lain.jenis} | lain.tambahan
                        utama.kab |= lain.kab; utama.tanggal |= lain.tanggal
                        for l in self.log:
                            if l["de_no"] == lain.no: l["de_no"] = utama.no; l["catatan"] = (l["catatan"] or "") + " majemuk"
                        self.de.remove(lain); berubah = True; break
                if berubah: break

    @staticmethod
    def _peringkat(de, objek_by_mention=None):
        return {"banjir": 3, "cuaca_ekstrem": 2, "tanah_longsor": 1}.get(de.jenis, 0)


def atribut_de(de, objek_per_mention, cfg_ambang=None, nama_wil=None):
    """-> dict atribut DisasterEvent + baris log ambang."""
    objs = [objek_per_mention.get(m["mention_id"], []) for m, _ in de.anggota]
    st, alasan = AMB.is_bencana(objs, cfg_ambang or AMB.KONFIG)
    kuat = max((SUMBER_KUAT.get(m["sumber_tanggal"], 0), m["sumber_tanggal"]) for m, _ in de.anggota)[1]
    wil = sorted(de.kab) if de.kab else ([de.kunci] if isinstance(de.kunci, str) else [])
    label = {"gempabumi": "Gempa bumi", "erupsi": "Erupsi", "karhutla": "Karhutla", "banjir": "Banjir",
             "cuaca_ekstrem": "Cuaca ekstrem", "tanah_longsor": "Tanah longsor"}[de.jenis]
    kab_nama = next((m["kab_nama"] for m, _ in de.anggota if m.get("kab_nama")), None)
    nama_wil = nama_wil or {}
    if de.jenis == "karhutla":
        tempat = nama_wil.get(de.kunci, de.kunci)
    else:
        tempat = kab_nama or ", ".join(nama_wil.get(k, k) for k in wil)
    return {"event_id": f"DE{de.no:04d}", "nama": f"{label} {tempat}, {de.start.isoformat()}".replace("  ", " "),
            "jenis": de.jenis, "jenis_tambahan": sorted(de.tambahan), "start_time": de.start.isoformat(),
            "end_time": de.last.isoformat(), "status": st, "memenuhi_ambang": alasan, "sumber_tanggal": kuat,
            "kode_wilayah": wil, "kode_provinsi": sorted({k.split(".")[0] for k in wil}) if wil else ([de.kunci] if de.jenis == "karhutla" else []), "n_mention": len(de.anggota), "n_tweet": len({m["tweet_id"] for m, _ in de.anggota})}
