"""API baca-saja Peta Situasi Bencana. Jalankan: uvicorn app.main:app --reload (dari folder backend)."""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.get("/api/health")
def health(repo: Repository = Depends(get_repo)):
    return {"status": "ok", "sumber": repo.sumber}


@app.get("/api/wilayah")
def wilayah(repo: Repository = Depends(get_repo)):
    return repo.wilayah()


@app.get("/api/kab-agregat")
def kab_agregat(f: Filter = Depends(get_filter), repo: Repository = Depends(get_repo)):
    return repo.kab_agregat(f)


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
def histogram(request: Request, kab: str | None = Query(None), repo: Repository = Depends(get_repo)):
    f = get_filter(request)
    return repo.histogram(Filter(jenis=f.jenis), _kode(kab) if kab else None)
