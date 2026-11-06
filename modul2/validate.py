"""Langkah 2.2 — validasi deterministik keluaran 2.1 (kode hanya menerima, merapikan format, atau membuang).

Versi 3 (17 Okt 2026). Urutan cek per tweet (TEKNIS-2.2): struktur -> ID -> enum -> span lokasi/organisasi/petunjuk
-> slot hierarki -> relasi -> luar negeri -> yatim -> angka gempa tertulis -> rujukan `lokasi` dampak/kebutuhan.
Setiap pembuangan/perbaikan dicatat sebagai baris log (tweet_id, cek, kode, entitas, detail).

Tambahan v3 (keputusan 17 Okt):
- pencocokan span longgar untuk tanda baca/spasi ("Bima ( NTB)"), tetap menolak lokasi hasil gabungan
- slot wilayah (provinsi, kab_kota, kecamatan, desa) hanya diisi bila ada kata penanda tertulis ("Kec.", "Kabupaten", dst.);
  nilai tanpa penanda dipindah ke `wilayah_dugaan` (petunjuk bagi 2.3, bukan hasil akhir)
- jenis di luar cakupan (tsunami, kekeringan, gelombang pasang/abrasi) dibuang dengan W_JENIS_DI_LUAR_CAKUPAN
- kelas dampak Juklak + objek; kelas lama dipetakan dengan W_KELAS_SINONIM
- lembaga: nama orang dipotong, jabatan dipetakan ke lembaga (daftar `jabatan_lembaga.csv`), W_ORG_TANPA_AKSI
- petunjuk_wilayah (tagar/singkatan) dengan pemeriksaan span
- penanda W_LOKASI_TANPA_RELASI: ada kejadian dan lokasi tetapi tidak ada relasi LOCATED_IN
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import schema as S

_PREFIX = re.compile(r"(?i)^(?:ds\.?|desa|dsn\.?|dusun|kel\.?|kelurahan|kec\.?|kecamatan|kab\.?|kabupaten|kota|prov\.?|provinsi)\s+")
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)
_KATA_UMUM = re.compile(r"(?i)^(?:wilayah|daerah|kawasan|area|sekitar)\s+")
_ANGKA_AWAL = re.compile(r"^\d+(?:[.,]\d+)?\s+(?!km\b)[A-Za-z]", re.I)
_HONORIFIK = re.compile(r"(?i)^(?:bang|bapak|pak|ibu|bu|mas|mbak|h\.|hj\.|dr\.?|drs\.?|ir\.?|prof\.?|letjen|mayjen|brigjen|"
                        r"jenderal|laksamana|marsekal|kolonel|kombes|akbp|kompol|irjen|mayor|kapten|brigadir)\b")
_JABATAN_AWAL = re.compile(r"(?i)^(?:plt\.?|pj\.?|wakil|kepala|ketua|sekretaris|direktur|juru\s+bicara|jubir|bupati|"
                           r"wali\s?kota|walikota|gubernur|menteri|menko|presiden|camat|lurah|kades|kapolres|kapolda|"
                           r"kapolsek|dandim|danramil|danrem|panglima|petugas|anggota|kabid|kasi|kalak)\b")
# kata penanda tingkat wilayah (v3): kata + (titik | spasi | tanda hubung) + nilai
_MARKER = {
    "provinsi": r"(?:prov(?:insi)?)",
    "kab_kota": r"(?:kab(?:upaten)?|kota|kodya)",
    "kecamatan": r"(?:kec(?:amatan)?)",
    "desa": r"(?:desa|ds|kel(?:urahan)?|nagari|gampong)",
}
_SLOT_WILAYAH = ("provinsi", "kab_kota", "kecamatan", "desa")
JABATAN_CSV = Path(__file__).parent / "prompt" / "jabatan_lembaga.csv"


def parse_json(raw: str | None) -> dict | None:
    """Ambil objek JSON dari jawaban model (buang pembungkus ```json, ambil kurung kurawal terluar)."""
    if not raw:
        return None
    s = _FENCE.sub("", raw.strip())
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        a, b = s.find("{"), s.rfind("}")
        if a < 0 or b <= a:
            return None
        try:
            obj = json.loads(s[a:b + 1])
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _split_camel(tag: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tag)


def find_span(teks: str, text: str) -> tuple[int, int, str] | None:
    """Cari teks entitas di tweet: persis -> abaikan kapital -> abaikan spasi -> abaikan tanda baca -> di dalam hashtag.

    Mode `punct` (v3): token yang sama berurutan dengan tanda baca/spasi apa pun di antaranya ("Bima ( NTB)").
    Lokasi hasil gabungan dua tempat yang dipisah kata lain tetap tidak ditemukan.
    """
    if not teks:
        return None
    i = text.find(teks)
    if i >= 0:
        return i, i + len(teks), "exact"
    low = text.lower()
    i = low.find(teks.lower())
    if i >= 0:
        return i, i + len(teks), "case"
    toks = [re.escape(t) for t in teks.split()]
    if toks:
        m = re.search(r"\s*".join(toks), text, re.I)
        if m:
            return m.start(), m.end(), "space"
    words = re.findall(r"\w+", teks, flags=re.UNICODE)
    if words:
        pat = r"(?<!\w)" + r"[\W_]*".join(re.escape(w) for w in words) + r"(?!\w)"
        m = re.search(pat, text, re.I)
        if m:
            return m.start(), m.end(), "punct"
    for m in re.finditer(r"#(\w+)", text):
        if _norm(_split_camel(m.group(1))) == _norm(teks) or m.group(1).lower() == re.sub(r"\s+", "", teks.lower().lstrip("#")):
            return m.start(), m.end(), "hashtag"
    return None


def _num_variants(x: float) -> set[str]:
    s = f"{x:g}"
    return {s, s.replace(".", ","), str(int(x)) if float(x).is_integer() else s}


@lru_cache(maxsize=1)
def _jabatan_default() -> tuple[tuple[re.Pattern, str], ...]:
    return tuple(load_jabatan(JABATAN_CSV))


def load_jabatan(path: Path = JABATAN_CSV) -> list[tuple[re.Pattern, str]]:
    with open(path, encoding="utf-8") as f:
        return [(re.compile(r["pola"], re.I), r["lembaga"]) for r in csv.DictReader(f)]


def petakan_jabatan(nama: str, daftar) -> tuple[bool, str | None]:
    """-> (apakah jabatan, nama lembaga hasil pemetaan atau None bila tidak terpetakan)."""
    n = re.sub(r"\s+", " ", nama).strip()
    for pat, tmpl in daftar:
        m = pat.match(n)
        if m:
            hasil = pat.sub(tmpl, n).strip() if "\\" in tmpl else tmpl
            return True, hasil
    return bool(_JABATAN_AWAL.match(n)), None


_KATA_PENANDA = {"desa", "ds", "kecamatan", "kec", "kabupaten", "kab", "kota", "provinsi", "prov", "dusun", "kelurahan", "kel", "dan"}


def _pangkas_lokasi(val: str, text: str):
    """Teks lokasi dari LLM tidak ditemukan utuh di tweet (mis. digabung dari potongan terpisah atau ditambah
    provinsi yang tidak tertulis). Cari potongan TERPANJANG yang berurutan dan benar-benar tertulis:
    (1) gabungan segmen berpemisah koma, (2) bila tidak ada, urutan kata. Tidak pernah menambah teks baru.
    Potongan hanya satu kata penanda (Desa/Kabupaten/...) tidak diterima. -> (teks, span) atau None."""
    segs = [x.strip() for x in val.split(",") if x.strip()]
    cands: list[str] = []
    for n in range(len(segs), 0, -1):
        for i in range(0, len(segs) - n + 1):
            cands.append(", ".join(segs[i:i + n]))
    toks = val.replace(",", " ").split()
    for n in range(len(toks) - 1, 0, -1):
        for i in range(0, len(toks) - n + 1):
            cands.append(" ".join(toks[i:i + n]))
    seen = set()
    terbaik = None
    for c in cands:
        if c in seen or c == val:
            continue
        seen.add(c)
        inti = [w for w in c.replace(",", " ").split() if w.lower().strip(".") not in _KATA_PENANDA]
        if not inti or max(len(w) for w in inti) < 3:
            continue
        sp = find_span(c, text)
        if sp is not None and (terbaik is None or len(c) > len(terbaik[0])):
            terbaik = (c, sp)
    return terbaik


def _punya_penanda(slot: str, nilai: str, teks_lokasi: str) -> bool:
    """Apakah `nilai` didahului kata penanda tingkat (Kec., Kabupaten, KAB-, dst.) di teks lokasi."""
    words = r"[\s\-]+".join(re.escape(w) for w in nilai.split())
    pat = rf"(?<!\w){_MARKER[slot]}(?:\.[\s\-]*|[\s\-]+){words}(?!\w)"
    return re.search(pat, teks_lokasi, re.I) is not None


def validate(tweet_id: str, text: str, raw: str | None, abbrev: dict[str, str] | None = None,
             jabatan=None) -> tuple[dict, list[dict]]:
    """Kembalikan (hasil tervalidasi, daftar log)."""
    log: list[dict] = []
    abbrev = {k.lower(): v for k, v in (abbrev or {}).items()}
    jabatan = _jabatan_default() if jabatan is None else jabatan

    def L(cek: str, kode: str, ent: str = "", detail: Any = "") -> None:
        log.append({"tweet_id": tweet_id, "cek": cek, "kode": kode, "entitas": ent, "detail": str(detail)[:200]})

    # --- V1 struktur
    obj = parse_json(raw)
    if obj is None:
        L("V1", "E_PARSE")
        return {"tweet_id": tweet_id, **S.kosong(), "validasi": {"status": "failed"}}, log
    out = S.kosong()
    for k in out:
        v = obj.get(k, [])
        if not isinstance(v, list):
            L("V1", "E_SCHEMA", k, type(v).__name__)
            v = []
        if k == "petunjuk_wilayah":  # model boleh menulis daftar string
            v = [{"teks": x} if isinstance(x, str) else x for x in v]
        out[k] = [x for x in v if isinstance(x, dict)]

    # --- V2 ID: pola & keunikan; peta id lama -> id baru
    remap: dict[str, str] = {}
    for bag, pre in S.BAGIAN.items():
        seen: set[str] = set()
        for n, ent in enumerate(out[bag], 1):
            old = str(ent.get("id", ""))
            new = old if re.fullmatch(pre + r"\d+", old) and old not in seen else f"{pre}{n}"
            while new in seen:
                n += 100
                new = f"{pre}{n}"
            if new != old and not (bag == "petunjuk_wilayah" and old == ""):
                L("V2", "W_ID_FIX", old, new)
            seen.add(new)
            remap.setdefault(old, new)
            ent["id"] = new

    # --- V3 enum
    em_ok = []
    for m in out["event_mention"]:
        j = (m.get("jenis") or "")
        j = j.strip().lower() if isinstance(j, str) else ""
        if j in S.DI_LUAR_CAKUPAN or j.replace("_", " ") in S.DI_LUAR_CAKUPAN:
            L("V3", "W_JENIS_DI_LUAR_CAKUPAN", m["id"], j)
            continue
        induk = next((jj for jj, subs in S.SUBTIPE.items() if j in subs), None)
        if j not in S.JENIS and induk:
            L("V3", "W_SUBTIPE_SEBAGAI_JENIS", m["id"], j)
            m["subtipe"] = m.get("subtipe") or j
            j = induk
        if j not in S.JENIS:
            syn = S.SINONIM_JENIS.get(j.replace("_", " "))
            if syn:
                L("V3", "W_ENUM_SYNONYM", m["id"], j)
                j, sub, asp = syn
                m["subtipe"] = m.get("subtipe") or sub
                m["aspek"] = m.get("aspek") or asp
            else:
                L("V3", "E_JENIS_NULL" if not j else "E_ENUM_JENIS", m["id"], j)
                continue
        m["jenis"] = j
        if m.get("subtipe") not in (None, "") and m["subtipe"] not in S.SUBTIPE[j]:
            L("V3", "E_ENUM_COMBO_SUBTIPE", m["id"], m["subtipe"])
            m["subtipe"] = None
        if m.get("aspek") is not None and (j != "karhutla" or m["aspek"] not in S.ASPEK):
            L("V3", "W_ASPEK_JENIS", m["id"], m["aspek"])
            m["aspek"] = None
        if m.get("tipe_laporan") not in S.TIPE_LAPORAN:
            if m.get("tipe_laporan") is not None:
                L("V3", "W_ENUM_TIPE_LAPORAN", m["id"], m.get("tipe_laporan"))
            m["tipe_laporan"] = None
        if "faktualitas" in m:  # atribut dihapus dari skema (keputusan 25 Okt); sisa dari prompt lama dibuang
            L("V3", "W_FAKTUALITAS_DIHAPUS", m["id"], m.pop("faktualitas"))
        if j != "gempabumi":
            for k in ("magnitudo", "kedalaman_km", "episentrum"):
                if m.get(k) is not None:
                    L("V3", "W_MAG_JENIS", m["id"], k)
                    m[k] = None
        em_ok.append(m)
    out["event_mention"] = em_ok

    ao_ok = []
    for a in out["affected_object"]:
        kelas, st = a.get("kelas"), a.get("status")
        if isinstance(kelas, str) and kelas not in S.KELAS_AFFECTED and kelas in S.KELAS_LAMA:
            baru, obj_baru = S.KELAS_LAMA[kelas]
            L("V3", "W_KELAS_SINONIM", a["id"], f"{kelas}->{baru}")
            a["kelas"], kelas = baru, baru
            if obj_baru and not a.get("objek"):
                a["objek"] = obj_baru
        if kelas not in S.KELAS_AFFECTED:
            L("V3", "E_ENUM_KELAS", a["id"], kelas); continue
        if st not in S.STATUS_ORANG | S.STATUS_BENDA:
            L("V3", "E_ENUM_STATUS", a["id"], st); continue
        if not S.kombinasi_sah(kelas, st):
            L("V3", "E_ENUM_COMBO", a["id"], f"{kelas}/{st}"); continue
        if not S.objek_sah(kelas, a.get("objek")):
            L("V3", "W_ENUM_OBJEK", a["id"], f"{kelas}/{a.get('objek')}"); a["objek"] = None
        if a.get("satuan") is not None and a["satuan"] not in S.SATUAN:
            L("V3", "W_ENUM_SATUAN", a["id"], a["satuan"]); a["satuan"] = None
        if a.get("jumlah") is not None:
            try:
                a["jumlah"] = int(float(str(a["jumlah"]).replace(".", "").replace(",", ".")))
            except ValueError:
                L("V3", "W_JUMLAH", a["id"], a["jumlah"]); a["jumlah"] = None
        ao_ok.append(a)
    out["affected_object"] = ao_ok

    hn_ok = []
    for n in out["humanitarian_need"]:
        if n.get("kategori") not in S.KATEGORI_NEED:
            L("V3", "W_ENUM_KATEGORI", n["id"], n.get("kategori")); n["kategori"] = "lainnya"
        if n.get("status") not in S.STATUS_NEED:
            L("V3", "E_ENUM_STATUS_NEED", n["id"], n.get("status")); continue
        hn_ok.append(n)
    out["humanitarian_need"] = hn_ok

    # --- V4 span lokasi, organisasi, petunjuk wilayah (tidak ditemukan = halusinasi / hasil gabungan)
    for loc in out["location"]:
        t0 = str(loc.get("teks") or "")
        t1 = _KATA_UMUM.sub("", t0).strip()
        if t1 != t0.strip() and t1:
            L("V4", "W_LOKASI_KATA_UMUM", loc["id"], t0)
            loc["teks"] = t1
        if _ANGKA_AWAL.match(str(loc.get("teks") or "")):
            L("V4", "W_LOKASI_ANGKA", loc["id"], loc.get("teks"))

    for org in out["organization"]:
        n0 = str(org.get("nama") or "")
        for sep in (",", " - ", " – "):
            if sep in n0:
                kiri, kanan = n0.split(sep, 1)
                if _HONORIFIK.match(kanan.strip()):
                    L("V4", "W_NAMA_ORANG_DIPOTONG", org["id"], n0)
                    org["nama"] = n0 = kiri.strip()
                    break
        if _HONORIFIK.match(n0.strip()) and not _JABATAN_AWAL.match(n0.strip()):
            org["nama"] = ""  # seluruhnya nama orang -> dibuang di bawah

    for bag, key in (("location", "teks"), ("organization", "nama"), ("petunjuk_wilayah", "teks")):
        keep = []
        for ent in sorted(out[bag], key=lambda e: -len(str(e.get(key) or ""))):
            val = str(ent.get(key) or "")
            if bag == "organization" and not val:
                L("V4", "W_NAMA_ORANG_DIBUANG", ent["id"]); continue
            sp = find_span(val, text)
            if sp is None and bag == "location":
                pangkas = _pangkas_lokasi(val, text)  # potong ke bagian yang benar-benar tertulis (tanpa menambah apa pun)
                if pangkas:
                    L("V4", "W_SPAN_DIPANGKAS", ent["id"], f"{val} -> {pangkas[0]}")
                    ent[key] = val = pangkas[0]
                    sp = pangkas[1]
            if sp is None:
                L("V4", "E_SPAN_NOT_FOUND" if bag != "petunjuk_wilayah" else "W_PETUNJUK_TIDAK_DITEMUKAN", ent["id"], val)
                continue
            ent["start"], ent["end"], ent["offset_status"] = sp
            if bag == "petunjuk_wilayah":
                ent["asal"] = "tagar" if text[sp[0]:sp[0] + 1] == "#" else "singkatan"
            keep.append(ent)
        out[bag] = sorted(keep, key=lambda e: e["start"])

    # lembaga: jabatan -> lembaga (kode), bukan LLM
    for org in out["organization"]:
        jab, lem = petakan_jabatan(org["nama"], jabatan)
        org["dari_jabatan"] = jab
        org["nama_lembaga"] = lem if jab else org["nama"]
        if jab and lem:
            L("V4", "W_JABATAN_KE_LEMBAGA", org["id"], f"{org['nama']} -> {lem}")
        elif jab:
            L("V4", "W_JABATAN_TANPA_PEMETAAN", org["id"], org["nama"])

    # --- V5 slot hierarki hanya dari teks lokasi itu; slot wilayah hanya bila ada kata penanda (v3)
    for loc in out["location"]:
        t = _norm(loc.get("teks") or "")
        dugaan: dict[str, str] = {}
        for slot in ("provinsi", "kab_kota", "kecamatan", "desa", "detail"):
            v = loc.get(slot)
            if not v:
                loc[slot] = None; continue
            bersih = re.sub(r"\s+", " ", str(v)).strip()
            if slot != "detail":  # detail boleh berawalan (\"Dusun Cikadu\")
                bersih = _PREFIX.sub("", bersih)
            if bersih != str(v).strip():
                L("V5", "W_SLOT_PREFIX", loc["id"], f"{slot}={v}")
                loc[slot] = bersih
            vn = _norm(bersih)
            ok = vn in t or any(k in t and _norm(full) == vn for k, full in abbrev.items()) \
                or any(_norm(full) in t and k == vn for k, full in abbrev.items())
            if not ok:
                L("V5", "W_SLOT_UNSUPPORTED", loc["id"], f"{slot}={v}"); loc[slot] = None
                continue
            if slot in _SLOT_WILAYAH:
                varian = {bersih} | {full for k, full in abbrev.items() if k == vn} | {k for k, full in abbrev.items() if _norm(full) == vn}
                if not any(_punya_penanda(slot, x, loc.get("teks") or "") for x in varian):
                    L("V5", "W_SLOT_TANPA_PENANDA", loc["id"], f"{slot}={bersih}")
                    dugaan[slot] = bersih
                    loc[slot] = None
        if dugaan:
            loc["wilayah_dugaan"] = dugaan
        loc["luar_negeri"] = bool(loc.get("luar_negeri", False))

    # --- V6 relasi: ujung ada, domain->range, kembar, aksi
    ids = {e["id"]: pre for bag, pre in S.BAGIAN.items() for e in out[bag] if bag != "petunjuk_wilayah"}
    foreign = {l["id"] for l in out["location"] if l["luar_negeri"]}
    rel_ok, seen_rel = [], set()
    for r0 in out["relations"]:
        r = {re.sub(r"[^a-z_]", "", str(k).lower()): v for k, v in r0.items()}  # "type:" -> "type"
        if set(r) != {re.sub(r"\s", "", str(k)) for k in r0}:
            L("V6", "W_REL_KEY_FIX", "", list(r0))
        t = r.get("type")
        f, to = remap.get(str(r.get("from")), str(r.get("from"))), remap.get(str(r.get("to")), str(r.get("to")))
        if t not in S.REL_TYPES:
            L("V6", "E_ENUM_REL", "", t); continue
        if f not in ids or to not in ids:
            L("V6", "E_REL_DANGLING", f"{f}->{to}", t); continue
        dom, rng = S.DOMAIN_RANGE[t]
        if ids[f] != dom or ids[to] not in rng:
            L("V6", "E_REL_DOMAIN", f"{f}->{to}", t); continue
        if to in foreign:  # V7
            L("V7", "W_FOREIGN_REL", to, t); continue
        key = (t, f, to)
        if key in seen_rel:
            L("V6", "W_REL_DUP", f"{f}->{to}", t); continue
        seen_rel.add(key)
        item = {"type": t, "from": f, "to": to}
        if r.get("aksi") and t in ("DEPLOYED_TO", "HANDLES"):
            item["aksi"] = r["aksi"]
        rel_ok.append(item)
    out["relations"] = rel_ok

    # penanda v3: ada kejadian dan lokasi (dalam negeri) tetapi tidak ada satu pun LOCATED_IN
    if out["event_mention"] and any(l["id"] not in foreign for l in out["location"]) \
            and not any(r["type"] == "LOCATED_IN" for r in rel_ok):
        L("V6", "W_LOKASI_TANPA_RELASI", ",".join(e["id"] for e in out["event_mention"]),
          ",".join(l["id"] for l in out["location"]))
    # penanda v3: lembaga tercatat tetapi tidak berbuat (tidak ada HANDLES/DEPLOYED_TO)
    berbuat = {r["from"] for r in rel_ok if r["type"] in ("HANDLES", "DEPLOYED_TO")}
    for o in out["organization"]:
        if o["id"] not in berbuat:
            L("V6", "W_ORG_TANPA_AKSI", o["id"], o.get("nama"))

    # --- V8 yatim: dampak/kebutuhan tanpa relasi dari kejadian (disimpan, ditandai)
    target = {r["to"] for r in rel_ok if r["type"] in ("AFFECTED", "REQUIRES")}
    for bag in ("affected_object", "humanitarian_need"):
        for e in out[bag]:
            e["orphan"] = e["id"] not in target
            if e["orphan"]:
                L("V8", "W_ORPHAN", e["id"])
    if not out["event_mention"]:
        L("V8", "W_NO_EVENT")

    # --- V9 angka gempa harus tertulis di teks
    for m in out["event_mention"]:
        for k in ("magnitudo", "kedalaman_km"):
            v = m.get(k)
            if v is None:
                continue
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                L("V9", "W_NUM_RANGE", m["id"], k); m[k] = None; continue
            lo, hi = (0, 10) if k == "magnitudo" else (0, 700)
            if not lo <= v <= hi:
                L("V9", "W_NUM_RANGE", m["id"], f"{k}={v}"); m[k] = None; continue
            if not any(s in text for s in _num_variants(v)):
                L("V9", "E_NUM_NOT_IN_TEXT", m["id"], f"{k}={v}"); m[k] = None; continue
            m[k] = v

    for m in out["event_mention"]:
        ep = m.get("episentrum")
        if not ep:
            continue
        try:
            lat, lon = float(ep["lat"]), float(ep["lon"])
        except (TypeError, KeyError, ValueError):
            L("V9", "W_COORD_RANGE", m["id"], ep); m["episentrum"] = None; continue
        if not all(any(s in text for s in _num_variants(abs(x))) for x in (lat, lon)):
            L("V9", "E_NUM_NOT_IN_TEXT", m["id"], f"episentrum={ep}"); m["episentrum"] = None; continue
        ls = re.search(re.escape(f"{abs(lat):g}") + r"\s*(LS|LU|S|N)\b", text, re.I)
        if ls:
            sgn = -1 if ls.group(1).upper() in ("LS", "S") else 1
            if lat * sgn < 0 or lat == 0:
                L("V9", "W_EPISENTRUM_TANDA", m["id"], f"{lat}->{sgn*abs(lat)}")
            lat = sgn * abs(lat)
        if not (-11 <= lat <= 6 and 95 <= lon <= 141):
            L("V9", "W_COORD_RANGE", m["id"], f"{lat},{lon}"); m["episentrum"] = None; continue
        m["episentrum"] = {"lat": lat, "lon": lon}

    # --- V10 rujukan lokasi pada dampak/kebutuhan
    loc_ids = {l["id"] for l in out["location"]}
    for bag in ("affected_object", "humanitarian_need"):
        for e in out[bag]:
            ref = e.get("lokasi")
            if ref is None:
                continue
            ref = remap.get(str(ref), str(ref))
            if ref not in loc_ids:
                L("V10", "W_LOKASI_DANGLING", e["id"], ref); e["lokasi"] = None
            elif ref in foreign:
                L("V10", "W_LOKASI_FOREIGN", e["id"], ref); e["lokasi"] = None
            else:
                e["lokasi"] = ref

    n_err = sum(1 for x in log if x["kode"].startswith("E_"))
    out["validasi"] = {"status": "ok" if n_err == 0 else "partial", "n_dibuang": n_err,
                       "kode": sorted({x["kode"] for x in log})}
    return {"tweet_id": tweet_id, **out}, log
