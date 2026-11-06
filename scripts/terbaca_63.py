"""Ubah hasil ekstraksi 63 tweet (JSON) menjadi teks yang mudah dibaca.

Jalankan dari folder skripsi:
  python scripts/terbaca_63.py                       # hasil prompt v3
  python scripts/terbaca_63.py --versi v2            # hasil prompt v2 (file lama)
Keluaran: dev_2025/reports/hasil_ekstraksi_63_<versi>_terbaca.txt  (tanpa penilaian; hanya mengubah format).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = {
    "v2": ("extraction_valid_63.jsonl", "extraction_raw_63.jsonl", "validation_log_63.csv"),
    "v3": ("extraction_valid_63_v3.jsonl", "extraction_raw_63_v3.jsonl", "validation_log_63_v3.csv"),
}
KET = {
    "E_SPAN_NOT_FOUND": "dibuang: teks tidak ditemukan di tweet (diubah/dikarang/digabung model)",
    "W_SLOT_TANPA_PENANDA": "wilayah tanpa kata penanda dipindah ke 'dugaan' (tingkat ditentukan tahap 2.3)",
    "W_SLOT_UNSUPPORTED": "isian wilayah dikosongkan: tidak tertulis di teks lokasi",
    "W_LOKASI_TANPA_RELASI": "ADA kejadian dan lokasi tetapi tidak ada relasi berlokasi di",
    "W_ORG_TANPA_AKSI": "lembaga dicatat tetapi tidak menangani/ditugaskan di relasi mana pun",
    "W_KELAS_SINONIM": "nama kelas dampak lama dipetakan ke kelas Juklak",
    "W_ENUM_OBJEK": "objek dampak tidak sah untuk kelasnya, dikosongkan",
    "W_JENIS_DI_LUAR_CAKUPAN": "kejadian jenis di luar cakupan (tsunami/kekeringan/gelombang pasang) dibuang",
    "W_LOKASI_KATA_UMUM": "kata umum di depan lokasi dibuang ('wilayah', 'daerah', ...)",
    "W_LOKASI_ANGKA": "lokasi diawali angka/jumlah, kemungkinan bukan nama tempat",
    "W_NAMA_ORANG_DIPOTONG": "nama orang di belakang jabatan dipotong",
    "W_NAMA_ORANG_DIBUANG": "lembaga yang ternyata nama orang dibuang",
    "W_JABATAN_KE_LEMBAGA": "jabatan dipetakan ke lembaganya",
    "W_JABATAN_TANPA_PEMETAAN": "jabatan belum punya pemetaan ke lembaga",
    "W_PETUNJUK_TIDAK_DITEMUKAN": "petunjuk wilayah tidak ada di tweet, dibuang",
    "W_ORPHAN": "dampak/kebutuhan tersimpan tetapi tidak terhubung ke kejadian",
    "W_NO_EVENT": "tidak ada kejadian pada tweet ini",
    "E_REL_DANGLING": "relasi dibuang: menunjuk entitas yang tidak ada/sudah dibuang",
    "E_REL_DOMAIN": "relasi dibuang: arah/tipe tidak cocok",
    "E_ENUM_REL": "relasi dibuang: tipe relasi tidak sah",
    "E_ENUM_KELAS": "dampak dibuang: kelas tidak ada di daftar",
    "E_ENUM_COMBO": "dampak dibuang: kombinasi kelas dan status tidak sah",
    "E_ENUM_STATUS": "dampak dibuang: status tidak sah",
    "W_REL_KEY_FIX": "kunci relasi ditulis salah oleh model, diperbaiki",
    "W_REL_DUP": "relasi kembar dibuang",
    "W_SUBTIPE_SEBAGAI_JENIS": "subtipe ditulis sebagai jenis, dipindahkan",
    "W_ENUM_SYNONYM": "sinonim jenis dipetakan",
    "W_SLOT_PREFIX": "awalan wilayah dibuang",
}


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versi", choices=list(D), default="v3")
    a = ap.parse_args()
    fv, fr, fl = D[a.versi]
    valid = jl(ROOT / "dev_2025/data/processed" / fv)
    raw = {str(r["tweet_id"]): r for r in jl(ROOT / "dev_2025/data/interim" / fr)}
    logs = defaultdict(list)
    for r in csv.DictReader(open(ROOT / "dev_2025/reports" / fl, encoding="utf-8")):
        logs[r["tweet_id"]].append(r)
    out = [f"HASIL EKSTRAKSI {len(valid)} TWEET INFORMATIF (DATA 2025) — versi terbaca, prompt {a.versi}",
           "Catatan: 'DIBUANG' = ditolak validasi 2.2. Ini hanya perubahan format, tanpa penilaian.", "=" * 78, ""]
    for i, r in enumerate(valid, 1):
        tid = str(r["tweet_id"])
        rw = raw.get(tid, {})
        names = {}
        for bag in ("event_mention", "location", "affected_object", "humanitarian_need", "organization", "petunjuk_wilayah"):
            for e in r.get(bag, []):
                names[e["id"]] = e.get("teks") or e.get("nama") or e.get("item") or e.get("jenis") or e["id"]
        out += [f"TWEET {i} dari {len(valid)}   (ID {tid}, {str(r.get('created_at'))[:10]})", "Teks:",
                "  " + r["text_raw"].replace("\n", " "),
                f"Waktu proses: {rw.get('durasi_s', '?')} detik · {rw.get('completion_tokens', '?')} token jawaban", ""]
        ev = r["event_mention"]
        out.append("KEJADIAN:" + ("" if ev else " (tidak ada)"))
        for e in ev:
            s = f"  - {e['jenis']}" + (f" (subtipe: {e['subtipe']})" if e.get("subtipe") else "")
            s += f" · jenis laporan: {e.get('tipe_laporan')}"
            if e.get("waktu_teks"):
                s += f' · waktu tertulis: "{e["waktu_teks"]}"'
            if e.get("magnitudo") is not None:
                s += f" · M{e['magnitudo']}"
            out.append(s)
        if r["location"]:
            out.append("LOKASI:")
            for l in r["location"]:
                slot = ", ".join(f"{k}={l[k]}" for k in ("provinsi", "kab_kota", "kecamatan", "desa", "detail") if l.get(k))
                dug = l.get("wilayah_dugaan")
                out.append(f'  - "{l["teks"]}"' + (f" → {slot}" if slot else "") + (f"   [dugaan tanpa penanda: {dug}]" if dug else ""))
        if r.get("petunjuk_wilayah"):
            out.append("PETUNJUK WILAYAH:")
            out += [f'  - "{p["teks"]}" ({p.get("asal")})' for p in r["petunjuk_wilayah"]]
        if r["affected_object"]:
            out.append("DAMPAK:")
            for x in r["affected_object"]:
                j = f" · {x['jumlah']} {x.get('satuan') or ''}".rstrip() if x.get("jumlah") is not None else ""
                out.append(f"  - {x['kelas']}" + (f"/{x['objek']}" if x.get("objek") else "") + f" · {x['status']}{j}"
                           + (f' · "{x["teks"]}"' if x.get("teks") else ""))
        if r["humanitarian_need"]:
            out.append("KEBUTUHAN/BANTUAN:")
            out += [f"  - {x['kategori']}: {x.get('item')} · {'dibutuhkan' if x['status'] == 'demanded' else 'sudah disalurkan'}"
                    for x in r["humanitarian_need"]]
        if r["organization"]:
            out.append("LEMBAGA:")
            for o in r["organization"]:
                s = f"  - {o['nama']}"
                if o.get("dari_jabatan"):
                    s += f"  [dari jabatan → {o.get('nama_lembaga') or 'belum terpetakan'}]"
                out.append(s)
        if r["relations"]:
            out.append("HUBUNGAN YANG LOLOS:")
            ind = {"LOCATED_IN": "berlokasi di", "EVACUATED_TO": "mengungsi ke", "AFFECTED": "berdampak pada",
                   "REQUIRES": "membutuhkan", "DEPLOYED_TO": "ditugaskan ke", "HANDLES": "menangani"}
            for q in r["relations"]:
                out.append(f'  - {q["from"]} "{names.get(q["from"])}"  {ind[q["type"]]}  {q["to"]} "{names.get(q["to"])}"'
                           + (f' ("{q["aksi"]}")' if q.get("aksi") else ""))
        if logs.get(tid):
            out.append("CATATAN VALIDASI:")
            for x in logs[tid]:
                out.append(f"  ! {KET.get(x['kode'], x['kode'])}" + (f" — {x['detail']}" if x["detail"] else ""))
        out += ["", "-" * 78, ""]
    dst = ROOT / "dev_2025/reports" / f"hasil_ekstraksi_63_{a.versi}_terbaca.txt"
    dst.write_text("\n".join(out), encoding="utf-8")
    print("->", dst)


if __name__ == "__main__":
    main()
