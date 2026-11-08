"""4.4 Tanya-jawab berbasis graf: LLM -> parameter tertutup -> templat kueri -> LLM menjawab hanya dari hasil, bersitasi."""
import json, re
from .llm import ekstrak_json
from .repo import JENIS
from .laporan import fakta_llm, ids_sitasi, normal_angka, kalimat_dampak
from modul3 import wilayah as W

INFO = ["situasi", "korban", "pengungsian", "kebutuhan", "lembaga", "status", "waktu", "lokasi", "ringkasan"]
TIDAK_ADA = "Tidak ada informasi di data untuk pertanyaan ini."
SYS_PARAM = ("Ubah pertanyaan pengguna menjadi JSON dengan kunci tepat: "
             f"jenis (salah satu {JENIS} atau null), wilayah (nama kabupaten/kota/provinsi persis seperti tertulis, atau null), "
             "tanggal_mulai dan tanggal_selesai (YYYY-MM-DD atau null; bila hanya bulan, isi awal dan akhir bulan), "
             f"info (salah satu {INFO}: korban=meninggal/luka/hilang/terdampak, pengungsian, kebutuhan=bantuan diminta/disalurkan, lembaga=instansi yang menangani, "
             "status=apakah tergolong bencana, waktu=kapan, lokasi=di mana/wilayah mana, ringkasan=laporan situasi utuh, situasi=lainnya). "
             "Jangan menjawab pertanyaannya. Balas HANYA JSON.")
SYS_JAWAB = ("Kamu menjawab pertanyaan tentang kejadian bencana HANYA dari KONTEKS. Aturan: (1) setiap fakta diakhiri sitasi [tweet_id] dari konteks; "
             "(2) angka disebut per laporan beserta tanggalnya, jangan dijumlahkan; "
             "(3) bila konteks sama sekali tidak memuat hal yang ditanyakan, jawab persis: "
             f"\"{TIDAK_ADA}\"; "
             "(4) bila konteks memuat sebagian (mis. ada laporan korban/pengungsi tetapi tanpa angka), sebutkan apa yang dilaporkan dengan sitasi dan nyatakan jelas bahwa angkanya tidak disebutkan; "
             "(5) jangan memakai pengetahuan di luar konteks; (6) jawab ringkas dalam bahasa Indonesia.")


def _norm(s): return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


class Wilayah:
    def __init__(self, nama=None):
        self.nama = nama or W.muat(); self.idx = {}
        for k, v in self.nama.items():
            n = _norm(v); self.idx.setdefault(n, []).append(k)
            if len(k) == 5: self.idx.setdefault(re.sub(r"^(kabupaten|kota|kab)\s+", "", n), []).append(k)

    def cari(self, teks):
        n = _norm(teks)
        if not n: return None
        c = self.idx.get(n) or self.idx.get(re.sub(r"^(kabupaten|kota|kab)\s+", "", n)) or []
        c = sorted(set(c))
        if not c: return None
        return ("prov", c) if all(len(x) == 2 for x in c) else ("kab", [x for x in c if len(x) == 5])


def ke_parameter(tanya, llm, tahun_data="2025"):
    h = llm.chat([{"role": "system", "content": SYS_PARAM + f" Data berasal dari tahun {tahun_data}; bila tahun tidak disebut, pakai itu."},
                  {"role": "user", "content": tanya}], json_mode=True, maks_token=300)
    p = ekstrak_json(h.teks)
    jenis = p.get("jenis") if p.get("jenis") in JENIS else None
    info = p.get("info") if p.get("info") in INFO else "situasi"
    tgl = lambda x: x if isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) else None
    return {"jenis": jenis, "wilayah": p.get("wilayah") or None, "tanggal_mulai": tgl(p.get("tanggal_mulai")), "tanggal_selesai": tgl(p.get("tanggal_selesai")), "info": info}


def potong(teks, n): return teks if len(teks) <= n else teks[:n] + "…"


def konteks(k, info, maks=9000):
    d = k["de"]
    L = [f"KEJADIAN {d['event_id']}: {d['nama']} | jenis {d['jenis']} | mulai {d['start_time']} ({d['sumber_tanggal']}) | laporan terakhir {d['end_time']} | tergolong bencana: {d['status']}"]
    man = [r for r in k["dampak"] if r["kelas"] == "manusia"]
    if info in ("korban", "situasi", "status"):
        L += ["DAMPAK:"] + [f"- {kalimat_dampak(r)}" for r in k["dampak"]]
    if info == "pengungsian":
        L += ["PENGUNGSIAN:"] + [f"- {kalimat_dampak(r)}" for r in man if r["status"] == "mengungsi"] + [f"- lokasi: {r['lokasi']} [{r['tweet_id']}]" for r in k["pengungsian"]]
    if info in ("kebutuhan", "situasi"):
        L += ["KEBUTUHAN:"] + [f"- {r['status']}: {r['item'] or r['kategori']} [{r['tweet_id']}]" for r in k["kebutuhan"]]
    if info in ("lembaga", "situasi"):
        L += ["LEMBAGA:"] + [f"- {r['nama_kanonik']}: {r['aksi'] or '-'} [{r['tweet_id']}]" for r in k["lembaga"]]
    if info in ("lokasi", "situasi", "waktu"):
        L += ["LOKASI:"] + [f"- {r['nama']} ({r['level']}) [{r['tweet_id']}]" for r in k["lokasi"]]
        L += ["LAPORAN:"] + [f"- tanggal {r['tanggal_lokal']} kab {r.get('kab_nama')} [{r['tweet_id']}]" for r in k["laporan"]]
    L += ["TWEET BUKTI:"] + [f"[{r['tweet_id']}] ({r['tanggal_lokal']}) {potong((r['text'] or '').strip(), 280)}" for r in k["laporan"]]
    return potong("\n".join(L), maks)


def tanya(pertanyaan, repo, llm, wil=None, maks_de=3, maks_konteks=9000, laporan_fn=None, default=None):
    """default: konteks dari antarmuka (kab/prov kode Kemendagri bertitik, jenis pipeline, dari/sampai, event_id); dipakai bila pertanyaan tidak menyebutnya."""
    wil = wil or Wilayah(); default = default or {}
    jejak = {"pertanyaan": pertanyaan}
    p = ke_parameter(pertanyaan, llm); jejak["parameter"] = p
    if default.get("event_id"):                      # kartu kejadian terpilih: jawab dari kejadian itu saja
        jejak["parameter"]["event_id"] = default["event_id"]
        return _jawab(jejak, [{"event_id": default["event_id"]}], repo, llm, p, maks_konteks, laporan_fn)
    p["jenis"] = p["jenis"] or default.get("jenis")
    p["tanggal_mulai"] = p["tanggal_mulai"] or default.get("dari"); p["tanggal_selesai"] = p["tanggal_selesai"] or default.get("sampai")
    kab = prov = None
    if not p["wilayah"]:
        kab, prov = default.get("kab"), default.get("prov")
    if p["wilayah"]:
        w = wil.cari(p["wilayah"])
        if not w: return _akhir(jejak, TIDAK_ADA, [], [], "", abstain=True, alasan="wilayah tidak dikenali di gazetir")
        kab = w[1][0] if (w[0] == "kab" and len(w[1]) == 1) else None
        prov = w[1][0] if w[0] == "prov" else None
        if w[0] == "kab" and len(w[1]) > 1:        # nama kabupaten/kota kembar: coba semuanya
            des = [d for c in w[1] for d in repo.daftar_de(p["jenis"], c, None, p["tanggal_mulai"], p["tanggal_selesai"], maks_de)]
            return _jawab(jejak, des, repo, llm, p, maks_konteks, laporan_fn)
    des = repo.daftar_de(p["jenis"], kab, prov, p["tanggal_mulai"], p["tanggal_selesai"], maks_de)
    return _jawab(jejak, des, repo, llm, p, maks_konteks, laporan_fn)


def _jawab(jejak, des, repo, llm, p, maks_konteks, laporan_fn):
    jejak["event_ditemukan"] = [d["event_id"] for d in des]
    if not des: return _akhir(jejak, TIDAK_ADA, [], [], "", abstain=True, alasan="tidak ada DisasterEvent yang cocok dengan filter")
    ks = [repo.kerangka(d["event_id"]) for d in des]
    if p["info"] == "ringkasan" and laporan_fn:
        ctx = "\n\n".join(laporan_fn(k) for k in ks)[:maks_konteks]
    else:
        per = max(1500, maks_konteks // len(ks))
        ctx = "\n\n".join(konteks(k, p["info"], per) for k in ks)
    h = llm.chat([{"role": "system", "content": SYS_JAWAB}, {"role": "user", "content": f"KONTEKS:\n{ctx}\n\nPERTANYAAN: {jejak['pertanyaan']}"}], maks_token=700)
    jejak["token"] = {"masuk": h.token_masuk, "keluar": h.token_keluar}
    return _akhir(jejak, h.teks, [d["event_id"] for d in des], ids_sitasi(h.teks), ctx, abstain=TIDAK_ADA[:30].lower() in h.teks.lower())


def _akhir(jejak, jawaban, event_ids, sitasi, ctx, abstain=False, alasan=None):
    ada = set(re.findall(r"\[(\d{6,})\]", ctx))
    jejak.update({"jawaban": jawaban, "event_ids": event_ids, "tweet_ids": sorted(set(sitasi)), "konteks": ctx, "abstain": abstain,
                  "sitasi_valid": all(i in ada for i in sitasi) if sitasi else None, "alasan_abstain": alasan})
    return jejak
