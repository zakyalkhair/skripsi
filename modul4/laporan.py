"""4.3 Laporan situasi per DisasterEvent: kerangka fakta (tanpa LLM) + narasi LLM bersitasi + penjaga angka/sitasi."""
import json, re
from collections import defaultdict
from .llm import ekstrak_json

DISCLAIMER = "_Disusun dari laporan media sosial; bukan data resmi BNPB._"
MANUSIA = ["meninggal", "hilang", "luka", "mengungsi", "terdampak"]
SYS = ("Kamu menyusun laporan situasi bencana berbahasa Indonesia HANYA dari data JSON yang diberikan. Aturan: "
       "(1) jangan menambah fakta, angka, nama, atau tanggal yang tidak ada di data; (2) setiap kalimat berfakta diakhiri sitasi [tweet_id] "
       "yang ada di data; (3) angka dampak selalu disebut per laporan (jangan dijumlahkan atau dirata-rata antar laporan); "
       "(4) tulis ringkas. Balas HANYA JSON: {\"kronologi\": [{\"tanggal\": \"YYYY-MM-DD\", \"kalimat\": \"...[id]\"}], \"kondisi_mutakhir\": \"...[id]\"}")


def _num(x):
    return None if x is None else (int(x) if float(x) == int(float(x)) else x)


def normal_angka(teks):
    return {a.replace(".", "") if re.fullmatch(r"\d{1,3}(\.\d{3})+", a) else a for a in re.findall(r"\d+(?:[.,]\d+)*", teks or "")}


def ids_sitasi(teks):
    out = []
    for blok in re.findall(r"\[([^\]]+)\]", teks or ""):
        out += re.findall(r"\d{6,}", blok)
    return out


def kalimat_dampak(r):
    j = _num(r.get("jumlah"))
    isi = " ".join(str(x) for x in (j, r.get("satuan"), r.get("objek") or r.get("kelas"), r.get("status")) if x not in (None, ""))
    kab = f" ({r['kab_nama']})" if r.get("kab_nama") else ""
    return f"per laporan {r['tanggal_lokal']}: {isi}{kab} [{r['tweet_id']}]"


def fakta_llm(k, maks_teks=260):
    d = k["de"]
    return {"kejadian": {"nama": d["nama"], "jenis": d["jenis"], "jenis_tambahan": d["jenis_tambahan"], "mulai": d["start_time"],
                         "laporan_terakhir": d["end_time"], "status_bencana": d["status"]},
            "laporan": [{"tweet_id": r["tweet_id"], "tanggal": r["tanggal_lokal"], "tipe": r["tipe_laporan"], "kab": r.get("kab_nama"),
                         "isi_tweet": (r["text"] or "")[:maks_teks]} for r in k["laporan"]],
            "dampak": [{"tweet_id": r["tweet_id"], "tanggal": r["tanggal_lokal"], "kelas": r["kelas"], "objek": r["objek"], "status": r["status"],
                        "jumlah": _num(r["jumlah"]), "satuan": r["satuan"]} for r in k["dampak"]],
            "kebutuhan": [{"tweet_id": r["tweet_id"], "kategori": r["kategori"], "item": r["item"], "status": r["status"]} for r in k["kebutuhan"]],
            "lembaga": [{"tweet_id": r["tweet_id"], "lembaga": r["nama_kanonik"], "aksi": r["aksi"]} for r in k["lembaga"]]}


def validasi(narasi, k, fakta):
    """-> daftar masalah (kosong = lolos)."""
    ok_ids = {r["tweet_id"] for r in k["laporan"]}
    boleh = normal_angka(json.dumps(fakta, ensure_ascii=False)) | normal_angka(" ".join(r["text"] or "" for r in k["laporan"]))
    masalah = []
    kal = [(x.get("tanggal", ""), x.get("kalimat", "")) for x in narasi.get("kronologi", [])] + [("", narasi.get("kondisi_mutakhir", ""))]
    for tgl, s in kal:
        if not s: continue
        c = ids_sitasi(s)
        if not c: masalah.append(f"tanpa sitasi: {s[:60]}")
        for i in c:
            if i not in ok_ids: masalah.append(f"sitasi tidak dikenal {i}")
        bersih = re.sub(r"\[[^\]]+\]", "", s); bersih = re.sub(r"\d{4}-\d{2}-\d{2}", "", bersih)
        for a in normal_angka(bersih):
            if a not in boleh: masalah.append(f"angka tidak ada di data: {a}")
    return masalah


def kronologi_polos(k):
    return [{"tanggal": r["tanggal_lokal"], "kalimat": f"({r['tipe_laporan']}) {(r['text'] or '').strip()[:220]} [{r['tweet_id']}]"} for r in k["laporan"]]


def narasi_llm(k, llm, percobaan=2):
    fakta, pesan, masalah = fakta_llm(k), None, []
    for i in range(percobaan):
        pesan = [{"role": "system", "content": SYS}, {"role": "user", "content": json.dumps(fakta, ensure_ascii=False)}]
        if masalah: pesan.append({"role": "user", "content": "Perbaiki, masalah sebelumnya: " + "; ".join(masalah[:6])})
        try:
            n = ekstrak_json(llm.chat(pesan, json_mode=True, maks_token=1800).teks)
            masalah = validasi(n, k, fakta)
        except (ValueError, KeyError, TypeError) as e:
            n, masalah = {}, [f"keluaran bukan JSON valid: {e}"]
        if not masalah: return n, [], True
    return {"kronologi": kronologi_polos(k), "kondisi_mutakhir": ""}, masalah, False


def susun(k, narasi, valid):
    d, lap = k["de"], k["laporan"]
    kab = sorted({r["kab_nama"] for r in lap if r.get("kab_nama")})
    kasar = "" if d["sumber_tanggal"] == "teks" else "sekitar "
    L = [f"# {d['nama']}", f"*{kasar}{d['start_time']} s.d. {d['end_time']} · jenis: {d['jenis']}" + (f" + {', '.join(d['jenis_tambahan'])}" if d["jenis_tambahan"] else "") + f" · memenuhi ambang bencana: {d['status']}*", "", DISCLAIMER, ""]
    L += ["## 1. Info kejadian", f"{d['jenis']}" + (f" ({', '.join(sorted({r['subtipe'] for r in lap if r['subtipe']}))})" if any(r["subtipe"] for r in lap) else ""), ""]
    L += ["## 2. Waktu", f"Mulai {kasar}{d['start_time']} (asal tanggal: {d['sumber_tanggal']}); laporan terakhir {d['end_time']}.", ""]
    lok = defaultdict(set)
    for r in k["lokasi"]: lok[r["level"] or "lain"].add(r["nama"])
    L += ["## 3. Lokasi kejadian", ("Kabupaten/kota: " + ", ".join(kab)) if kab else "Kabupaten/kota: tidak ada laporan"]
    for lv, ns in lok.items(): L.append(f"- {lv}: {', '.join(sorted(ns))}")
    L += ["", "## 4. Kronologi"] + [f"- {x['tanggal']}: {x['kalimat']}" for x in narasi.get("kronologi", [])]
    if not valid: L.append("_(tanpa narasi LLM atau narasi tidak lolos validasi; ditampilkan kutipan tweet apa adanya)_")
    man = [r for r in k["dampak"] if r["kelas"] == "manusia"]; benda = [r for r in k["dampak"] if r["kelas"] != "manusia"]
    L += ["", "## 5. Dampak kejadian (bangunan, prasarana, lahan)"] + ([f"- {kalimat_dampak(r)}" for r in benda] or ["- tidak ada laporan"])
    L += ["", "## 6. Korban"] + ([f"- {kalimat_dampak(r)}" for r in man if r["status"] != "mengungsi"] or ["- tidak ada laporan"])
    L += ["", "## 7. Pengungsi"] + [f"- {kalimat_dampak(r)}" for r in man if r["status"] == "mengungsi"] + [f"- lokasi pengungsian: {r['lokasi']} [{r['tweet_id']}]" for r in k["pengungsian"]]
    if not any(r["status"] == "mengungsi" for r in man) and not k["pengungsian"]: L.append("- tidak ada laporan")
    L += ["", "## 8. Upaya yang dilakukan"]
    L += [f"- {r['nama_kanonik']}: {r['aksi'] or '-'} [{r['tweet_id']}]" for r in k["lembaga"]]
    L += [f"- kebutuhan {r['status']}: {r['item'] or r['kategori']} [{r['tweet_id']}]" for r in k["kebutuhan"]]
    if not k["lembaga"] and not k["kebutuhan"]: L.append("- tidak ada laporan")
    L += ["", "## 9. Kondisi mutakhir", narasi.get("kondisi_mutakhir") or f"Laporan terakhir tanggal {d['end_time']}: " + ((lap[-1]['text'] or '')[:200] + f" [{lap[-1]['tweet_id']}]" if lap else "tidak ada laporan")]
    L += ["", "## 10. Sumber", ", ".join(sorted({r["tweet_id"] for r in lap}))]
    return "\n".join(L) + "\n"


def buat_laporan(k, llm):
    narasi, masalah, valid = narasi_llm(k, llm) if llm else ({"kronologi": kronologi_polos(k), "kondisi_mutakhir": ""}, ["tanpa LLM"], False)
    return {"event_id": k["de"]["event_id"], "markdown": susun(k, narasi, valid), "valid": valid, "masalah": masalah, "narasi": narasi}
