"""Tanya-jawab GraphRAG (Modul 4) untuk dasbor. Opsional: aktif hanya bila GRAPHRAG=1 dan kunci LLM ada di .env.
Tetap GET (API ini hanya-baca). Data: hasil Modul 3 (CSV) atau Neo4j (M4_BACKEND=neo4j). Tidak ada jawaban/sitasi buatan:
semua sitasi diambil dari kerangka graf."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

router = APIRouter()
_kunci = threading.Lock()          # satu pertanyaan sekali jalan (batas laju penyedia gratis)
_state: dict = {}
JENIS_PIPA = {"banjir": "banjir", "longsor": "tanah_longsor", "cuaca": "cuaca_ekstrem", "karhutla": "karhutla", "gempa": "gempabumi", "erupsi": "erupsi"}


def aktif() -> bool:
    return os.environ.get("GRAPHRAG", "0") == "1"


def _siap():
    if _state: return _state
    from modul3.neo4j_conn import muat_env
    muat_env(str(RAIZ / ".env"))
    from modul4.llm import LLM
    from modul4 import qa
    from modul4.repo import MemRepo
    gen = os.environ.get("GRAPHRAG_GEN", "groq:openai/gpt-oss-120b"); cad = os.environ.get("GRAPHRAG_CADANGAN", "groq:openai/gpt-oss-20b")
    if os.environ.get("M4_BACKEND", "csv") == "neo4j":
        from modul3.neo4j_conn import driver
        from modul4.repo import Neo4jRepo
        drv, db = driver(); repo = Neo4jRepo(drv.session(database=db)); _state["drv"] = drv
    else:
        repo = MemRepo(str(RAIZ / os.environ.get("M4_DATA", "dev_2025/data/modul3")))
    _state.update(repo=repo, llm=LLM(gen, cadangan=cad, log=str(RAIZ / "dev_2025/data/modul4/log_llm.jsonl")), gen=gen, wil=qa.Wilayah(repo._nama()), qa=qa)
    return _state


@router.get("/api/tanya/status")
def status():
    if not aktif():
        return {"tersedia": False, "alasan": "GRAPHRAG=1 belum diatur di backend/.env"}
    try:
        s = _siap()
    except SystemExit as e:
        return {"tersedia": False, "alasan": str(e)}
    return {"tersedia": True, "model": s["gen"], "sumber": os.environ.get("M4_BACKEND", "csv")}


def _k4_ke_titik(k: str | None) -> str | None:
    return f"{k[:2]}.{k[2:]}" if k and len(k) == 4 else k


@router.get("/api/tanya")
def tanya(q: str = Query(..., min_length=3, max_length=500), kab: str | None = None, prov: str | None = None, jenis: str | None = None,
          dari: str | None = None, sampai: str | None = None, event_id: str | None = None):
    if not aktif(): raise HTTPException(503, "GraphRAG tidak aktif (GRAPHRAG=1 di backend/.env)")
    try:
        s = _siap()
    except SystemExit as e:
        raise HTTPException(503, str(e))
    js = [JENIS_PIPA[j] for j in (jenis or "").split(",") if j in JENIS_PIPA]
    default = {"kab": _k4_ke_titik(kab), "prov": prov, "jenis": js[0] if len(js) == 1 else None, "dari": dari, "sampai": sampai, "event_id": event_id}
    with _kunci:
        try:
            r = s["qa"].tanya(q, s["repo"], s["llm"], s["wil"], default={k: v for k, v in default.items() if v})
        except RuntimeError as e:
            raise HTTPException(503, f"Penyedia model sibuk/membatasi laju: {e}")
        # sitasi hanya dari tweet yang benar-benar menjadi anggota kejadian yang dipakai
        info = {}
        for eid in r["event_ids"]:
            k = s["repo"].kerangka(eid)
            for l in (k["laporan"] if k else []):
                info.setdefault(l["tweet_id"], {"event_id": eid, "mention_id": l["mention_id"], "tanggal": l["tanggal_lokal"], "teks": l["text"]})
    import re as _re
    teks, buang = r["jawaban"], [i for i in r["tweet_ids"] if i not in info]
    for i in buang:                                   # sitasi yang tidak ada di kejadian terpakai dibuang, bukan dipercaya
        teks = _re.sub(r"\s*\[[^\]]*" + i + r"[^\]]*\]", "", teks)
    if buang: teks += "\n\n(Catatan: sitasi yang tidak dapat diverifikasi pada data dibuang.)"
    cit = [{"tweet_id": t, **info[t], "url": f"https://x.com/i/web/status/{t}"} for t in r["tweet_ids"] if t in info]
    return {"text": teks, "citations": cit, "abstain": r["abstain"], "parameter": r["parameter"], "event_ids": r["event_ids"], "model": s["gen"]}


@router.get("/api/kejadian/{event_id}/laporan")
def laporan(event_id: str):
    """Laporan situasi 4.3 untuk satu kejadian. Memakai berkas tersimpan (dev_2025/data/modul4/laporan/<id>.md); tidak membuat baru (hemat kuota)."""
    if not event_id.replace("DE", "").isdigit(): raise HTTPException(422, "event_id tidak valid")
    p = RAIZ / "dev_2025/data/modul4/laporan" / f"{event_id}.md"
    if not p.exists(): raise HTTPException(404, "Laporan belum dibuat: python -m modul4 laporan --de " + event_id)
    return {"event_id": event_id, "markdown": p.read_text(encoding="utf-8")}
