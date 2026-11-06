"""2.3 Pemilihan kandidat oleh LLM untuk lokasi ambigu (31 Okt 2026). Rancangan: claude/TEKNIS-2.3.md (R5 butir 2).

Hanya lokasi `U_WIL_AMBIG` / `U_DETAIL_AMBIG` dengan 2-5 kandidat (`perlu_llm`). LLM TIDAK menulis nama atau koordinat:
ia hanya memilih huruf kandidat (atau `tidak_dapat_ditentukan`); nama dan titik selalu dari gazetir/OSM.
Urutan kandidat diacak dengan benih tetap per lokasi (tanpa urutan menurut popularitas/ukuran). Suhu 0.
Hasil:  dipilih -> R_OK (metode llm_pilih_kandidat) | U_AMBIG_LLM (LLM menjawab tidak dapat ditentukan) | U_LLM_INVALID (jawaban tidak sah).
Checkpoint: jawaban mentah per (tweet, lokasi) disimpan; menjalankan ulang melanjutkan yang belum selesai.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from .osm import hasil_osm
from .resolve import LEVEL

HURUF = "ABCDE"
TIDAK = "tidak_dapat_ditentukan"
_TINGKAT = {"prov": "Provinsi", "kab": "Kabupaten/Kota", "kec": "Kecamatan", "desa": "Desa/Kelurahan"}

SYSTEM = f"""Tugas Anda: menentukan wilayah atau tempat mana di Indonesia yang dimaksud sebuah unggahan X tentang bencana.
Anda diberi teks unggahan, sebutan lokasi, dan beberapa kandidat bertanda huruf dari gazetir resmi.

Aturan:
- Pilih HANYA dari kandidat yang diberikan. Jangan membuat kandidat, nama, atau koordinat baru.
- Pakai petunjuk yang TERTULIS di unggahan: nama wilayah lain, nama tempat, jenis kejadian, nama lembaga. Jangan menebak dari popularitas, ukuran, atau urutan kandidat.
- Bila petunjuk tidak cukup untuk membedakan kandidat, jawab "{TIDAK}". Menjawab "{TIDAK}" lebih baik daripada menebak.

Jawab hanya dengan JSON: {{"pilihan": "<huruf kandidat atau {TIDAK}>", "alasan": "<satu kalimat, kutip petunjuk dari unggahan>"}}"""


def _nama_kec(gaz, kode_kec: str) -> str:
    if not kode_kec:
        return "kecamatan tidak diketahui"
    n = [gaz.nama[p] for p in gaz.path(kode_kec)]
    return ", ".join(reversed(n)) if n else kode_kec


def deskripsi(c: dict, gaz) -> str:
    """Satu baris kandidat untuk prompt."""
    if "kode" in c:                                              # wilayah Kemendagri
        k = c["kode"]
        tingkat = _TINGKAT[LEVEL[len(k)]]
        induk = ", ".join(reversed(c["path"][:-1]))
        return f"{tingkat} {c['nama']}" + (f" — di {induk}" if induk else "")
    return f"{c['nama']} ({c['jenis']}, OpenStreetMap) — di {_nama_kec(gaz, c.get('kode_kec', ''))}"


def kunci(c: dict) -> str:
    return c["kode"] if "kode" in c else c["id"]


def konteks_lain(rec: dict, loc_id: str, gaz) -> list[str]:
    out = []
    for l in rec.get("location", []):
        r = l.get("resolution") or {}
        if l["id"] == loc_id or r.get("status") != "resolved" or r.get("k_kandidat") != 1:
            continue
        ap = r.get("admin_path") or []
        nama = ", ".join(reversed([gaz.nama[p] for p in gaz.path(ap[-1])])) if ap else r.get("nama_resmi", "")
        out.append(f"{l['teks']} = {r.get('nama_resmi')} ({nama})")
    return out


def susun_pesan(rec: dict, loc: dict, gaz, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """-> (messages, kandidat_berurutan_acak)."""
    kand = list(loc["resolution"]["kandidat"])
    random.Random(f"{seed}|{rec['tweet_id']}|{loc['id']}").shuffle(kand)
    baris = "\n".join(f"{HURUF[i]}. {deskripsi(c, gaz)}" for i, c in enumerate(kand))
    lain = konteks_lain(rec, loc["id"], gaz)
    user = (f"Unggahan:\n{rec['text_raw']}\n\nSebutan lokasi yang harus ditentukan: \"{loc['teks']}\"\n"
            + (f"Lokasi lain di unggahan yang sudah pasti: {'; '.join(lain)}\n" if lain else "")
            + f"\nKandidat:\n{baris}\n\nPilih huruf kandidat yang dimaksud, atau {TIDAK}.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], kand


def parse_jawaban(isi: str | None, n: int) -> tuple[str, str]:
    """-> (status, pilihan) ; status: dipilih | tidak_dapat_ditentukan | invalid."""
    m = re.search(r"\{.*\}", isi or "", flags=re.DOTALL)
    if not m:
        return "invalid", ""
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "invalid", ""
    p = str(d.get("pilihan", "")).strip()
    if p.lower() == TIDAK:
        return "tidak_dapat_ditentukan", TIDAK
    p = p.upper()[:1]
    if p and p in HURUF[:n]:
        return "dipilih", p
    return "invalid", p


def terapkan(loc: dict, kand: list[dict], status: str, pilihan: str, alasan: str, gaz) -> dict:
    """Ubah loc['resolution'] sesuai jawaban. Mengembalikan kotak resolusi baru."""
    lama = loc["resolution"]
    if status == "tidak_dapat_ditentukan":
        return {**lama, "kode_hasil": "U_AMBIG_LLM", "llm_dipakai": True, "perlu_llm": False, "llm_alasan": alasan}
    if status == "invalid":
        return {**lama, "kode_hasil": "U_LLM_INVALID", "llm_dipakai": True, "perlu_llm": False}
    c = kand[HURUF.index(pilihan)]
    if "kode" in c:
        k = c["kode"]; t = gaz.titik.get(k)
        baru = {"status": "resolved", "kode_hasil": "R_OK", "alasan": None, "path": "B",
                "gazetteer_id": f"kemendagri:{k}", "level_admin": LEVEL[len(k)], "nama_resmi": gaz.nama[k],
                "jenis_wilayah": gaz.jenis[k], "admin_path": gaz.path(k), "admin_nama": [gaz.nama[p] for p in gaz.path(k)],
                "lat": t[0] if t else None, "lon": t[1] if t else None,
                "presisi_koordinat": "titik_pusat_wilayah" if t else None,
                "catatan": [] if t else ["koordinat_belum_ada"]}
    else:
        baru = hasil_osm([{k2: c[k2] for k2 in ("tipe_osm", "osm_id", "nama", "jenis", "kode_kec", "lat", "lon")}],
                         "llm_pilih_kandidat")
    baru.update({"metode": "llm_pilih_kandidat", "dasar": ["llm"], "k_kandidat": lama.get("k_kandidat"),
                 "kandidat": lama.get("kandidat"), "perlu_llm": False, "llm_dipakai": True, "llm_alasan": alasan})
    return baru


def jalankan(resolved: Path, out: Path, raw: Path, log_csv: Path, gaz, client, max_tokens: int = 200,
             seed: int = 42, limit: int | None = None, dry_run: bool = False, log=print) -> dict:
    import csv
    from collections import Counter
    selesai: dict[str, dict] = {}
    if raw.exists() and not dry_run:
        for l in open(raw, encoding="utf-8"):
            d = json.loads(l); selesai[d["key"]] = d
    n = Counter(); baris = []; dipanggil = 0
    fo = open(out, "w", encoding="utf-8") if not dry_run else None
    fr = open(raw, "a", encoding="utf-8") if not dry_run else None
    try:
        for line in open(resolved, encoding="utf-8"):
            rec = json.loads(line)
            for loc in rec.get("location", []):
                r = loc.get("resolution") or {}
                if not (r.get("perlu_llm") and r.get("kode_hasil") in ("U_WIL_AMBIG", "U_DETAIL_AMBIG")
                        and 2 <= len(r.get("kandidat") or []) <= 5):
                    continue
                if limit and dipanggil >= limit:
                    continue
                msgs, kand = susun_pesan(rec, loc, gaz, seed)
                key = f"{rec['tweet_id']}|{loc['id']}"
                if dry_run:
                    log(f"--- {key} | {loc['teks']}\n{msgs[1]['content']}\n")
                    dipanggil += 1; continue
                if key in selesai:
                    d = selesai[key]
                else:
                    try:
                        res = client.chat(msgs, max_tokens)
                        d = {"key": key, "urutan": [kunci(c) for c in kand], "content": res["content"],
                             "durasi_s": res.get("durasi_s"), "model": client.model}
                    except Exception as e:                       # jaringan/Ollama mati: catat, jangan hentikan seluruh run
                        d = {"key": key, "urutan": [kunci(c) for c in kand], "content": None, "galat": str(e)[:200]}
                    fr.write(json.dumps(d, ensure_ascii=False) + "\n"); fr.flush()
                    dipanggil += 1
                status, pil = parse_jawaban(d.get("content"), len(kand))
                alasan = ""
                try:
                    alasan = str(json.loads(re.search(r"\{.*\}", d.get("content") or "", flags=re.DOTALL).group(0)).get("alasan", ""))[:300]
                except Exception:
                    pass
                if d.get("galat"):
                    status = "galat"
                    loc["resolution"] = {**r, "catatan": (r.get("catatan") or []) + ["llm_galat"]}
                else:
                    loc["resolution"] = terapkan(loc, kand, status, pil, alasan, gaz)
                n[loc["resolution"]["kode_hasil"]] += 1
                baris.append({"tweet_id": rec["tweet_id"], "loc_id": loc["id"], "teks": loc["teks"], "k": len(kand),
                              "urutan": " ".join(f"{HURUF[i]}={kunci(c)}" for i, c in enumerate(kand)),
                              "pilihan": pil, "status_llm": status, "hasil": loc["resolution"].get("gazetteer_id", ""),
                              "kode_hasil": loc["resolution"]["kode_hasil"], "alasan": alasan, "durasi_s": d.get("durasi_s", "")})
            if fo:
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        for f in (fo, fr):
            if f:
                f.close()
    if baris:
        with open(log_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(baris[0].keys())); w.writeheader(); w.writerows(baris)
    return {"dipanggil": dipanggil, "hasil": dict(n)}
