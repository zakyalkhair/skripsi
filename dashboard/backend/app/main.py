"""API baca-saja Peta Situasi Bencana. Jalankan: uvicorn app.main:app --reload (dari folder backend)."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .config import Settings
from .domain import JENIS, Filter
from .repository import make_repository
from .repository.base import NotFound, Repository

app = FastAPI(title="Peta Situasi Bencana API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
_settings = Settings()
app.add_middleware(CORSMiddleware, allow_origins=list(_settings.cors_origins), allow_methods=["GET"], allow_headers=["*"])


@lru_cache(maxsize=1)
def get_repo() -> Repository:
    return make_repository(_settings)


@app.middleware("http")
async def read_only(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        return JSONResponse({"detail": "API ini hanya-baca"}, status_code=405)
    return await call_next(request)


@app.exception_handler(NotFound)
async def _nf(_: Request, e: NotFound):
    return JSONResponse({"detail": str(e)}, status_code=404)


def _date(v: str | None, name: str) -> date | None:
    if v in (None, ""):
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, f"{name} harus berformat YYYY-MM-DD")


def get_filter(request: Request, dari: str | None = None, sampai: str | None = None) -> Filter:
    """jenis tidak dikirim = semua jenis; jenis= (kosong) = tidak ada jenis yang dipilih."""
    jenis = None
    if "jenis" in request.query_params:
        raw = ",".join(request.query_params.getlist("jenis"))
        jenis = frozenset(j for j in (x.strip() for x in raw.split(",")) if j)
        bad = sorted(jenis - set(JENIS))
        if bad:
            raise HTTPException(422, f"jenis tidak dikenal: {', '.join(bad)} (pilihan: {', '.join(JENIS)})")
    d, s = _date(dari, "dari"), _date(sampai, "sampai")
    if d and s and d > s:
        raise HTTPException(422, "dari tidak boleh setelah sampai")
    return Filter(jenis=jenis, dari=d, sampai=s)


def _kode(kode: str) -> str:
    if not re.fullmatch(r"\d{4}", kode):
        raise HTTPException(422, "kode kab/kota harus 4 digit kode Kemendagri")
    return kode


def _prov(kode: str | None) -> str | None:
    if kode in (None, ""):
        return None
    if not re.fullmatch(r"\d{2}", kode):
        raise HTTPException(422, "kode provinsi harus 2 digit kode Kemendagri")
    return kode


@app.get("/api/health")
def health(repo: Repository = Depends(get_repo)):
    return {"status": "ok", "sumber": repo.sumber}


@app.get("/api/wilayah")
def wilayah(repo: Repository = Depends(get_repo)):
    return repo.wilayah()


@app.get("/api/kab-agregat")
def kab_agregat(f: Filter = Depends(get_filter), prov: str | None = None, repo: Repository = Depends(get_repo)):
    return repo.kab_agregat(f, _prov(prov))


@app.get("/api/kab/{kode}/kejadian")
def kab_kejadian(kode: str, f: Filter = Depends(get_filter), repo: Repository = Depends(get_repo)):
    return repo.kab_kejadian(_kode(kode), f)


@app.get("/api/kab/{kode}/titik")
def kab_titik(kode: str, f: Filter = Depends(get_filter), repo: Repository = Depends(get_repo)):
    return repo.kab_titik(_kode(kode), f)


@app.get("/api/titik/{gazetteer_id:path}/ringkasan")
def titik_ringkasan(gazetteer_id: str, f: Filter = Depends(get_filter), repo: Repository = Depends(get_repo)):
    return repo.titik_ringkasan(gazetteer_id, f)


@app.get("/api/histogram")
def histogram(request: Request, kab: str | None = Query(None), prov: str | None = Query(None),
              lokasi: str | None = Query(None), repo: Repository = Depends(get_repo)):
    """Laporan kejadian per minggu pada cakupan nasional / provinsi / kab-kota / lokasi (gazetteer_id)."""
    f = get_filter(request)
    return repo.histogram(Filter(jenis=f.jenis), _kode(kab) if kab else None, _prov(prov), lokasi or None)


# --------------------------------------------------------------------------- ekspor
_FORMULA = ("=", "+", "-", "@", "\t", "\r")
KOLOM = {
    "kejadian": ["event_id", "nama", "jenis", "kode_kab", "nama_kab", "provinsi", "start_time", "end_time", "status_ambang",
                 "jumlah_laporan_periode", "jumlah_tweet_periode", "jumlah_laporan_total", "lokasi_ids"],
    "laporan": ["mention_id", "event_id", "jenis", "kode_kab", "tanggal_lokal", "lokasi_ids", "tweet_ids"],
    "dampak": ["affected_id", "event_id", "mention_id", "tanggal_laporan", "kelas", "status", "jumlah", "satuan",
               "tingkat_atribusi", "lokasi_ids", "tweet_ids"],
    "kebutuhan": ["need_id", "event_id", "mention_id", "tanggal_laporan", "kategori", "item", "status", "tingkat_atribusi",
                  "lokasi_id", "tweet_ids"],
    "penanganan": ["org_id", "nama_kanonik", "tingkat", "wilayah", "induk", "peran", "event_id", "mention_id",
                   "tanggal_laporan", "dikerahkan_ke", "tweet_ids"],
    "tweet": ["tweet_id", "upload", "text", "url"],
}


def _sel(v) -> str:
    """Nilai sel aman: teks yang diawali karakter formula diberi apostrof (cegah injeksi formula)."""
    if v is None:
        return ""
    s = str(v)
    return "'" + s if s.startswith(_FORMULA) else s


def _csv(rows: list[dict], cols: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([_sel(r.get(c)) for c in cols])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM: dikenali spreadsheet sebagai UTF-8


@app.get("/api/ekspor")
def ekspor(f: Filter = Depends(get_filter), prov: str | None = None, kab: str | None = None, lokasi: str | None = None,
           repo: Repository = Depends(get_repo)):
    """ZIP berisi CSV ternormalisasi (kejadian, laporan, dampak, kebutuhan, penanganan, tweet) + manifest.json."""
    data = repo.ekspor(f, _prov(prov), _kode(kab) if kab else None, lokasi or None)
    tabel, cakupan = data["tabel"], data["cakupan"]
    if not tabel["kejadian"]:
        raise HTTPException(404, "Tidak ada data yang sesuai filter untuk diekspor.")
    now = datetime.now(timezone.utc).astimezone()
    manifest = {
        "judul": "Ekspor Peta Situasi Bencana",
        "dibuat": now.isoformat(timespec="seconds"),
        "sumber_data": data["dataset"],
        "filter": {**f.as_dict(), "jenis_semua": f.jenis is None},
        "cakupan": cakupan,
        "catatan": [
            "Informasi berasal dari laporan media sosial (X/Twitter) yang diekstraksi otomatis; bukan data resmi BNPB.",
            "Satu baris dampak/kebutuhan/penanganan = satu fakta per laporan sumber. Angka dari laporan berbeda TIDAK dijumlahkan.",
            "tingkat_atribusi = 'lokasi' bila fakta tertaut eksplisit ke lokasi (LOCATED_IN / lokasi kebutuhan); "
            "'kejadian' bila hanya tertaut ke kejadian.",
            "Nilai kosong berarti tidak disebutkan, bukan nol.",
            "Semua kolom *_id dan *_ids adalah teks; daftar dipisah titik koma (;). Impor dengan tipe teks agar ID tidak berubah.",
            "Kejadian disertakan bila periodenya beririsan dengan rentang tanggal; laporan & fakta memakai tanggal laporan dalam rentang.",
        ],
        "tabel": {k: {"file": f"{k}.csv", "baris": len(v), "kolom": KOLOM[k]} for k, v in tabel.items()},
        "encoding": "UTF-8 dengan BOM, dipisah koma, semua nilai dikutip",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for k, rows in tabel.items():
            z.writestr(f"{k}.csv", _csv(rows, KOLOM[k]))
    nama = re.sub(r"[^a-z0-9]+", "-", (cakupan["nama"] or "data").lower()).strip("-")
    fn = f"peta-situasi-bencana_{nama}_{now:%Y%m%d-%H%M}.zip"
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{fn}"'})
