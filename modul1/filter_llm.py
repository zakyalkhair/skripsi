"""Tahap 1.4 — Filter informatif: klasifikasi biner informatif/noninformatif dengan LLM open-weight.

Alur:
  input_1_4.parquet (wakil cluster)
    -> aturan regex dari config (tanpa LLM), berurutan, presisi tinggi: mis. laporan BMKG untuk
       wilayah kejadian -> informatif; MBG/karnaval atau doa murni tanpa petunjuk fakta -> noninformatif
    -> sisanya (kasus ambigu) dikirim ke LLM lewat API OpenAI-compatible (/chat/completions): Groq, OpenRouter,
       Ollama lokal, dll. — cukup ganti base_url/model di config. Beberapa tweet per permintaan.
    -> hasil_1_4.parquet (semua wakil + label) dan informatif.parquet (label == informatif)

Dapat dilanjutkan: setiap potongan (chunk) yang selesai langsung ditambahkan ke llm_labels (JSONL).
Tweet yang sudah berlabel dengan prompt_hash yang sama tidak dikirim ulang. Bila kuota harian API
habis, proses berhenti rapi; jalankan perintah yang sama lagi setelah kuota pulih.
Tidak ada baris yang dihapus: tweet yang gagal dilabeli tetap ada dengan label null + llm_status.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import pandas as pd

from .io_utils import (
    iter_jsonl,
    read_parquet,
    setup_logger,
    update_alur_data,
    utc_now_iso,
    write_jsonl,
    write_parquet,
)
from .schemas import HASIL_1_4_COLS, AturanCfg, Config

LABELS = ("informatif", "noninformatif")
SUMBER_ATURAN = "aturan:"  # + nama aturan
SUMBER_LLM = "llm"
SUMBER_DEFAULT = "default"
STATUS_OK = "ok"


class RateLimited(Exception):
    """HTTP 429. retry_after = detik tunggu yang disarankan server (None bila tidak ada)."""

    def __init__(self, retry_after: float | None, message: str = ""):
        super().__init__(message)
        self.retry_after = retry_after


class ApiError(Exception):
    """Galat API selain 429 (status HTTP, timeout, koneksi)."""

    def __init__(self, status: str, retryable: bool):
        super().__init__(status)
        self.status, self.retryable = status, retryable


# --------------------------------------------------------------------------- konteks kejadian
def load_events(path: str | Path) -> dict[str, dict]:
    """Semua baris kejadian.csv (bukan hanya pilot) sebagai konteks untuk prompt dan aturan BMKG."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    events = {}
    for r in df.to_dict("records"):
        r["aliases"] = [a.strip() for a in r["alias_wilayah"].split(";") if a.strip()]
        events[r["event_id"]] = r
    return events


def event_context(event_ids: list[str], events: dict[str, dict]) -> str:
    lines = []
    for eid in event_ids:
        e = events.get(eid)
        if e is None:
            lines.append(f"- {eid}")
            continue
        lines.append(
            f"- {eid}: {e['nama_kejadian']} (jenis: {e['jenis']}); wilayah: {e['wilayah']}; "
            f"nama lain wilayah: {', '.join(e['aliases'])}; tanggal kejadian: {e['tanggal_kejadian']} "
            f"(periode pengamatan {e['tanggal_mulai']} s.d. {e['tanggal_selesai']})"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- aturan regex
def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def mentions_region(text: str, aliases: list[str]) -> bool:
    return any(re.search(rf"(?<![\w]){re.escape(a)}(?![\w])", text, flags=re.IGNORECASE) for a in aliases)


def rule_matches(rule: AturanCfg, text: str, event_ids: list[str], events: dict[str, dict]) -> bool:
    if rule.semua and not all(re.search(p, text, flags=re.IGNORECASE) for p in rule.semua):
        return False
    if rule.salah_satu and not _any(rule.salah_satu, text):
        return False
    if rule.kecuali and _any(rule.kecuali, text):
        return False
    if rule.wilayah_kejadian:
        aliases = [a for eid in event_ids for a in events.get(eid, {}).get("aliases", [])]
        if not mentions_region(text, aliases):
            return False
    return True


def first_rule(text: str, event_ids: list[str], events: dict[str, dict], rules: list[AturanCfg]) -> AturanCfg | None:
    """Aturan pertama (berurutan sesuai config) yang cocok, atau None -> LLM."""
    return next((r for r in rules if rule_matches(r, text, event_ids, events)), None)


def rule_labels(df: pd.DataFrame, events: dict[str, dict], cfg: Config) -> pd.Series:
    """Series per baris: AturanCfg yang berlaku, atau None."""
    rules = cfg.filter_llm.aturan
    return pd.Series([first_rule(t, list(e or []), events, rules)
                      for t, e in zip(df["text_raw"], df["event_id"])], index=df.index, dtype=object)


# --------------------------------------------------------------------------- permintaan
def load_system_prompt(cfg: Config) -> str:
    return cfg.paths.prompt_informatif.read_text(encoding="utf-8").strip()


def prompt_hash(system_prompt: str, cfg: Config) -> str:
    """Sidik jari semua yang memengaruhi label; berubah -> tweet dilabeli ulang."""
    f = cfg.filter_llm
    blob = json.dumps({"system": system_prompt, "provider": urlparse(f.base_url).netloc, "model": f.model,
                       "temperature": f.temperature, "n": f.tweet_per_permintaan,
                       "extra": f.extra_body}, sort_keys=True)
    return "p" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def user_message(texts: list[str], event_ids: list[str], events: dict[str, dict]) -> str:
    """Tweet diberi nomor lokal 1..n (bukan tweet_id 19 digit) agar jawaban ringkas & tidak salah salin."""
    blocks = "\n".join(f'<tweet id="{i}">\n{t}\n</tweet>' for i, t in enumerate(texts, 1))
    return f"Kejadian acuan:\n{event_context(event_ids, events)}\n\nTweet ({len(texts)}):\n{blocks}"


def build_payload(texts: list[str], event_ids: list[str], events: dict[str, dict],
                  system_prompt: str, cfg: Config) -> dict:
    f = cfg.filter_llm
    return {
        "model": f.model,
        "temperature": f.temperature,
        "max_tokens": f.max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message(texts, event_ids, events)},
        ],
        **f.extra_body,
    }


def parse_labels(content: str | None, n: int) -> dict[int, str] | None:
    """Jawaban {"hasil": [{"id": "1", "label": "informatif"}, ...]} -> {1: "informatif", ...}.
    None bila bukan JSON yang bisa dibaca. Label di luar LABELS atau id di luar 1..n diabaikan."""
    if not content:
        return None
    m = re.search(r"\{.*\}", content, flags=re.DOTALL)  # toleran terhadap teks/```json di sekitar JSON
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    items = data.get("hasil") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    out = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            i = int(str(it.get("id")).strip())
        except ValueError:
            continue
        label = str(it.get("label", "")).strip().lower()
        if 1 <= i <= n and label in LABELS:
            out[i] = label
    return out


def make_chunks(todo: pd.DataFrame, size: int) -> list[tuple[list[str], pd.DataFrame]]:
    """Kelompokkan per kombinasi event_id (satu konteks kejadian per permintaan), lalu potong per `size`."""
    todo = todo.assign(_ev=todo["event_id"].map(lambda e: tuple(sorted(e or []))))
    todo = todo.sort_values(["_ev", "created_at", "tweet_id"], kind="mergesort")
    chunks = []
    for ev, g in todo.groupby("_ev", sort=True):
        for s in range(0, len(g), size):
            chunks.append((list(ev), g.iloc[s : s + size].drop(columns="_ev")))
    return chunks


# --------------------------------------------------------------------------- klien HTTP
class OpenAICompatClient:
    """Klien minimal untuk POST {base_url}/chat/completions (Groq, OpenRouter, Ollama, dst.)."""

    def __init__(self, base_url: str, api_key: str | None, timeout_s: float):
        import httpx

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(base_url=base_url.rstrip("/") + "/", headers=headers, timeout=timeout_s)
        self._httpx = httpx

    def chat(self, payload: dict) -> tuple[str | None, dict]:
        try:
            r = self._http.post("chat/completions", json=payload)
        except self._httpx.TimeoutException as e:
            raise ApiError("timeout", retryable=True) from e
        except self._httpx.TransportError as e:
            raise ApiError(f"koneksi:{type(e).__name__}", retryable=True) from e
        if r.status_code == 429:
            ra = r.headers.get("retry-after")
            try:
                ra = float(ra) if ra is not None else None
            except ValueError:
                ra = None
            raise RateLimited(ra, r.text[:300])
        if r.status_code >= 400:
            raise ApiError(f"http_{r.status_code}:{r.text[:200]}", retryable=r.status_code >= 500)
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content")
        usage = data.get("usage") or {}
        usage["finish_reason"] = choice.get("finish_reason")
        return content, usage


def make_client(cfg: Config, log) -> OpenAICompatClient:
    """Kunci API dibaca dari variabel lingkungan `api_key_env` (.env); None untuk Ollama lokal."""
    from dotenv import load_dotenv

    load_dotenv()
    if cfg.crawl.use_system_certs:
        from .crawl import use_system_certs

        use_system_certs(log)
    f = cfg.filter_llm
    key = os.environ.get(f.api_key_env) if f.api_key_env else None
    if f.api_key_env and not key:
        raise RuntimeError(f"{f.api_key_env} kosong — isi di .env (lihat .env.example)")
    return OpenAICompatClient(f.base_url, key, f.timeout_s)


# --------------------------------------------------------------------------- label
def load_labels(path: Path) -> list[dict]:
    return list(iter_jsonl(path)) if path.exists() else []


def labeled_ids(labels: list[dict], phash: str) -> set[str]:
    return {r["tweet_id"] for r in labels if r["status"] == STATUS_OK and r["prompt_hash"] == phash}


def call_with_retry(client: Any, payload: dict, cfg: Config, log,
                    sleep_fn: Callable[[float], Any]) -> tuple[str | None, dict]:
    """Coba ulang untuk 429 dengan jeda singkat & galat sementara. 429 dengan jeda panjang (kuota
    harian) diteruskan sebagai RateLimited agar proses berhenti rapi."""
    f = cfg.filter_llm
    attempt = 0
    while True:
        try:
            return client.chat(payload)
        except RateLimited as e:
            wait = e.retry_after if e.retry_after is not None else f.jeda_antar_permintaan_s * 2
            if wait > f.tunggu_429_maks_s or attempt >= f.max_retry:
                raise
            log.info("429 dari server, tunggu %.0f detik", wait)
            sleep_fn(wait)
        except ApiError as e:
            if not e.retryable or attempt >= f.max_retry:
                raise
            wait = f.jeda_antar_permintaan_s * (2 ** attempt)
            log.info("Galat sementara (%s), coba lagi dalam %.0f detik", e.status, wait)
            sleep_fn(wait)
        attempt += 1


def run(cfg: Config, client: Any, limit: int | None = None, log=None,
        sleep_fn: Callable[[float], Any] = time.sleep) -> pd.DataFrame:
    """Labeli tweet yang belum berlabel (bukan aturan BMKG), simpan per chunk, lalu tulis keluaran."""
    log = log or setup_logger("filter", cfg.paths.logs_dir)
    f = cfg.filter_llm
    df = read_parquet(cfg.paths.input_1_4)
    events = load_events(cfg.paths.kejadian)
    system_prompt = load_system_prompt(cfg)
    phash = prompt_hash(system_prompt, cfg)

    by_rule = rule_labels(df, events, cfg)
    has_rule = by_rule.notna()
    rule_counts = by_rule[has_rule].map(lambda r: f"{r.nama}({r.label})").value_counts().to_dict()
    log.info("Wakil: %d; dilabeli aturan: %d %s", len(df), int(has_rule.sum()), rule_counts)
    if not f.pakai_llm:
        log.info("pakai_llm: false — sisanya diberi label_default=%s", f.label_default)
        return finalize(cfg, log)
    done = labeled_ids(load_labels(cfg.paths.llm_labels), phash)
    todo = df[~has_rule & ~df["tweet_id"].isin(done)]
    log.info("Sudah berlabel LLM (prompt %s): %d; akan dikirim ke LLM: %d", phash, len(done), len(todo))
    if limit is not None and len(todo) > limit:
        ids = sorted(todo["tweet_id"], key=lambda t: (len(t), t))
        keep = set(random.Random(cfg.seed).sample(ids, limit))
        todo = todo[todo["tweet_id"].isin(keep)]
        log.info("--limit %d: sampel acak (seed %d)", limit, cfg.seed)

    chunks = make_chunks(todo, f.tweet_per_permintaan)
    log.info("Model %s @ %s; %d permintaan (%d tweet/permintaan)", f.model, f.base_url, len(chunks),
             f.tweet_per_permintaan)
    total_tokens = 0
    for k, (ev, g) in enumerate(chunks, 1):
        payload = build_payload(g["text_raw"].tolist(), ev, events, system_prompt, cfg)
        base = {"model": f.model, "provider": urlparse(f.base_url).netloc, "prompt_hash": phash,
                "chunk": f"{phash}-{g['tweet_id'].iloc[0]}", "collected_at": utc_now_iso()}
        try:
            content, usage = call_with_retry(client, payload, cfg, log, sleep_fn)
        except RateLimited as e:
            log.warning("Kuota API habis (%s). Berhenti rapi setelah %d/%d permintaan; jalankan "
                        "perintah yang sama lagi nanti — yang sudah berlabel tidak dikirim ulang.",
                        f"tunggu {e.retry_after:.0f} detik" if e.retry_after else "429", k - 1, len(chunks))
            break
        except ApiError as e:
            recs = [base | {"tweet_id": t, "label": None, "status": f"errored:{e.status}"} for t in g["tweet_id"]]
            write_jsonl(cfg.paths.llm_labels, recs, append=True)
            log.error("Permintaan %d/%d gagal: %s", k, len(chunks), e.status)
            continue
        parsed = parse_labels(content, len(g))
        tokens = usage.get("total_tokens") or 0
        total_tokens += tokens
        recs = []
        for i, tid in enumerate(g["tweet_id"], 1):
            if parsed is None:
                status, label = "invalid_output", None
            elif i in parsed:
                status, label = STATUS_OK, parsed[i]
            else:
                status, label = "hilang_dari_jawaban", None
            recs.append(base | {"tweet_id": tid, "label": label, "status": status,
                                "finish_reason": usage.get("finish_reason"), "chunk_tokens": tokens})
        write_jsonl(cfg.paths.llm_labels, recs, append=True)
        n_ok = sum(r["status"] == STATUS_OK for r in recs)
        log.info("Permintaan %d/%d: %d/%d berlabel, %d token", k, len(chunks), n_ok, len(recs), tokens)
        if k < len(chunks) and f.jeda_antar_permintaan_s:
            sleep_fn(f.jeda_antar_permintaan_s)
    log.info("Total token terpakai run ini: %d", total_tokens)
    return finalize(cfg, log)


# --------------------------------------------------------------------------- keluaran
def finalize(cfg: Config, log=None) -> pd.DataFrame:
    """Gabungkan aturan BMKG + label LLM (prompt saat ini) -> hasil_1_4.parquet & informatif.parquet."""
    log = log or setup_logger("filter_finalize", cfg.paths.logs_dir)
    df = read_parquet(cfg.paths.input_1_4)
    events = load_events(cfg.paths.kejadian)
    phash = prompt_hash(load_system_prompt(cfg), cfg)

    latest: dict[str, dict] = {}
    for r in load_labels(cfg.paths.llm_labels):
        if r["prompt_hash"] != phash:
            continue
        cur = latest.get(r["tweet_id"])
        # label ok tidak ditimpa oleh percobaan gagal yang lebih baru
        if cur is None or r["status"] == STATUS_OK or cur["status"] != STATUS_OK:
            latest[r["tweet_id"]] = r

    f = cfg.filter_llm
    by_rule = rule_labels(df, events, cfg)
    out = df.copy()
    cols: dict[str, list] = {c: [] for c in ("label", "label_sumber", "llm_status", "llm_model", "prompt_hash")}
    for tid, rule in zip(out["tweet_id"], by_rule):
        if rule is not None:
            vals = (rule.label, SUMBER_ATURAN + rule.nama, None, None, None)
        elif not f.pakai_llm:
            vals = (f.label_default, SUMBER_DEFAULT, None, None, None)
        else:
            r = latest.get(tid)
            vals = ((r["label"], SUMBER_LLM if r["label"] else None, r["status"], r["model"], r["prompt_hash"])
                    if r else (None, None, "belum_dikirim", None, None))
        for c, v in zip(cols, vals):
            cols[c].append(v)
    for c, v in cols.items():
        out[c] = v

    write_parquet(out, cfg.paths.hasil_1_4, HASIL_1_4_COLS)
    inf = out[out["label"] == "informatif"]
    write_parquet(inf, cfg.paths.informatif, HASIL_1_4_COLS)

    n_inf, n_non = len(inf), int((out["label"] == "noninformatif").sum())
    n_none = int(out["label"].isna().sum())
    per_sumber = out.dropna(subset=["label"]).groupby(["label_sumber", "label"]).size()
    rincian = "; ".join(f"{s}/{lab}={n}" for (s, lab), n in per_sumber.items())
    log.info("Hasil 1.4: informatif=%d, noninformatif=%d, belum berlabel=%d", n_inf, n_non, n_none)
    log.info("Rincian sumber label: %s", rincian or "-")
    if n_none:
        log.info("Status yang belum berlabel: %s",
                 out.loc[out["label"].isna(), "llm_status"].value_counts().to_dict())
    alasan = f"noninformatif={n_non} (rincian: {rincian})"
    if n_none:
        alasan += f"; belum berlabel={n_none} (tidak dihitung keluar/dibuang)"
    update_alur_data(cfg.paths.alur_data, "filter informatif", len(out), n_inf, n_non, alasan)
    update_alur_data(cfg.paths.alur_data, "Siap ke Modul 2", n_inf, None, None, "")
    log.info("Ditulis: %s, %s", cfg.paths.hasil_1_4, cfg.paths.informatif)
    return out
