"""Tahap 1.1 — Crawling (twscrape), anonimisasi, saring dasar.

Alur:
  kejadian.csv -> susun kueri (OR per kata kunci) -> twscrape -> data/raw/raw.jsonl (mentah)
  raw.jsonl -> anonimisasi + gabung tweet_id + saring dasar -> data/interim/crawled.parquet
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .io_utils import (
    dumps_jsonl,
    iter_jsonl,
    setup_logger,
    update_alur_data,
    utc_now_iso,
    write_parquet,
)
from .schemas import (
    CRAWLED_COLS,
    DROP_BUKAN_ID,
    DROP_RETWEET,
    Config,
    CrawledTweet,
    Kejadian,
    Kueri,
)

CRAWL_LOG_COLS = ["query_id", "event_ids", "query", "crawled_at", "twscrape_version", "n_hasil", "status"]


# --------------------------------------------------------------------------- kejadian & kueri
def load_kejadian(path: str | Path, only_pilot: bool, events: list[str] | None = None) -> list[Kejadian]:
    """Baca kejadian.csv, filter pilot/--events, urutkan menurut urutan_crawl (kosong di akhir)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    rows = [
        Kejadian.model_validate({k: r[k] for k in (
            "event_id", "jenis", "alias_wilayah", "tanggal_mulai", "tanggal_selesai", "pilot", "urutan_crawl")})
        for r in df.to_dict("records")
    ]
    if only_pilot:
        rows = [k for k in rows if k.pilot]
    if events:
        wanted = [e.strip().upper() for e in events if e.strip()]
        unknown = set(wanted) - {k.event_id for k in rows}
        if unknown:
            raise ValueError(f"event_id tidak ditemukan (atau bukan pilot saat only_pilot=true): {sorted(unknown)}")
        rows = [k for k in rows if k.event_id in wanted]
    return sorted(rows, key=lambda k: (k.urutan_crawl is None, k.urutan_crawl or 0, k.event_id))


def _quote(term: str) -> str:
    return f'"{term}"' if any(ch.isspace() for ch in term) else term


def _dedupe_ci(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return out


def query_id_of(text: str) -> str:
    """query_id stabil = hash isi kueri."""
    return "q" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def build_queries(kejadian: list[Kejadian], cfg: Config) -> list[Kueri]:
    """Satu kueri per (kejadian, kata kunci): `kw (alias1 OR alias2 ...) lang:id -filter:retweets
    -neg since:mulai until:selesai+1`. Bila melebihi max_query_chars, alias dipecah ke beberapa kueri.
    Kueri dengan teks identik dari kejadian berbeda digabung (event_ids jadi list)."""
    c = cfg.crawl
    by_text: dict[str, Kueri] = {}
    for k in kejadian:
        if k.jenis not in c.keywords:
            raise ValueError(f"Tidak ada kata kunci untuk jenis '{k.jenis}' ({k.event_id}) di config")
        aliases = _dedupe_ci(k.alias_wilayah)
        # until: di X bersifat eksklusif -> tambah 1 hari agar tanggal_selesai ikut
        suffix_parts = [c.lang_operator, c.retweet_operator]
        suffix_parts += [f"-{_quote(n)}" for n in c.negative_keywords]
        suffix_parts += [f"since:{k.tanggal_mulai.isoformat()}",
                         f"until:{(k.tanggal_selesai + timedelta(days=1)).isoformat()}"]
        suffix = " ".join(suffix_parts)
        for kw in _dedupe_ci(c.keywords[k.jenis]):
            for chunk in _chunk_aliases(aliases, _quote(kw), suffix, c.max_query_chars):
                text = f"{_quote(kw)} ({' OR '.join(_quote(a) for a in chunk)}) {suffix}"
                if text in by_text:
                    if k.event_id not in by_text[text].event_ids:
                        by_text[text].event_ids.append(k.event_id)
                else:
                    by_text[text] = Kueri(query_id=query_id_of(text), text=text, event_ids=[k.event_id],
                                          keyword=kw, aliases=chunk)
    return list(by_text.values())


def _chunk_aliases(aliases: list[str], kw: str, suffix: str, max_chars: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    cur: list[str] = []
    for a in aliases:
        trial = cur + [a]
        text = f"{kw} ({' OR '.join(_quote(x) for x in trial)}) {suffix}"
        if len(text) > max_chars and cur:
            chunks.append(cur)
            cur = [a]
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- akun (.env)
def load_accounts_from_env(env: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Kumpulkan akun X_ACCOUNT_<n>_*. Nilai tidak pernah dicetak."""
    env = dict(os.environ if env is None else env)
    idx = sorted({int(k.split("_")[2]) for k in env if k.startswith("X_ACCOUNT_") and k.split("_")[2].isdigit()})
    accounts = []
    for i in idx:
        p = f"X_ACCOUNT_{i}_"
        acc = {f: env.get(p + f.upper(), "").strip() for f in ("username", "password", "email", "email_password", "cookies")}
        if acc["cookies"]:
            names = {part.split("=", 1)[0].strip() for part in acc["cookies"].split(";") if "=" in part}
            missing = {"auth_token", "ct0"} - names
            if missing:
                # nilai cookie tidak pernah dicetak, hanya nama yang kurang
                raise ValueError(
                    f"X_ACCOUNT_{i}_COOKIES tidak memuat {sorted(missing)}. Format yang benar: "
                    'X_ACCOUNT_{i}_COOKIES="auth_token=NILAI; ct0=NILAI"'.replace("{i}", str(i))
                )
        if acc["username"] and (acc["cookies"] or acc["password"]):
            accounts.append(acc)
    return accounts


# --------------------------------------------------------------------------- progres
def load_progress(path: Path) -> dict[str, dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_progress(path: Path, progress: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def append_crawl_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CRAWL_LOG_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def twscrape_version() -> str:
    try:
        from importlib.metadata import version

        return version("twscrape")
    except Exception:  # pragma: no cover
        return "tidak diketahui"


# --------------------------------------------------------------------------- fetch
def use_system_certs(log) -> None:
    """Verifikasi HTTPS memakai sertifikat bawaan OS (Windows/macOS), bukan bundel certifi.

    Diperlukan di jaringan yang memeriksa HTTPS dengan sertifikat root sendiri (kantor/kampus):
    browser percaya sertifikat itu, Python tidak. Verifikasi TLS tetap aktif.
    """
    try:
        import truststore
    except ImportError:
        log.warning("truststore belum terpasang (pip install -r requirements.txt); memakai sertifikat certifi")
        return
    truststore.inject_into_ssl()
    log.info("Verifikasi HTTPS memakai sertifikat sistem operasi (truststore)")


async def make_twscrape_api(cfg: Config, log):
    """Siapkan twscrape.API dengan akun dari .env (cookies lebih diutamakan)."""
    from twscrape import API

    accounts = load_accounts_from_env()
    if not accounts:
        raise RuntimeError("Tidak ada akun X di .env (X_ACCOUNT_1_USERNAME + COOKIES/PASSWORD). Lihat .env.example")
    cfg.paths.twscrape_db.parent.mkdir(parents=True, exist_ok=True)
    api = API(str(cfg.paths.twscrape_db))
    for acc in accounts:
        if acc["cookies"]:
            await api.pool.add_account_cookies(acc["username"], acc["cookies"])
        else:
            await api.pool.add_account(acc["username"], acc["password"], acc["email"], acc["email_password"])
    await api.pool.login_all()
    log.info("%d akun X dimuat dari .env", len(accounts))
    return api


async def fetch(cfg: Config, queries: list[Kueri], kejadian: list[Kejadian], api: Any, log,
                pause: bool = False, input_fn: Callable[[str], str] = input,
                sleep_fn: Callable[[float], Any] = asyncio.sleep) -> dict[str, int]:
    """Jalankan kueri per kejadian (urut urutan_crawl), tulis raw.jsonl, crawl_log.csv, progres.

    `api` cukup punya `search(q, limit)` async-iterator yang menghasilkan objek dengan `.dict()`
    (twscrape.models.Tweet) — memudahkan test dengan API tiruan.
    """
    c = cfg.crawl
    progress = load_progress(cfg.paths.crawl_progress)
    version = twscrape_version()
    counts: dict[str, int] = {}
    cfg.paths.raw_jsonl.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg.seed)

    for k in kejadian:
        ev_queries = [q for q in queries if q.event_ids[0] == k.event_id]
        ev_tweets: list[dict] = []
        for q in ev_queries:
            if progress.get(q.query_id, {}).get("status") == "selesai":
                log.info("[%s] lewati %s (sudah selesai, %s tweet)", k.event_id, q.query_id,
                         progress[q.query_id].get("n_hasil"))
                continue
            n, status = 0, "selesai"
            crawled_at = utc_now_iso()
            try:
                with open(cfg.paths.raw_jsonl, "a", encoding="utf-8") as fh:
                    async for tw in api.search(q.text, limit=c.max_tweets_per_query):
                        d = tw.dict() if hasattr(tw, "dict") else dict(tw)
                        d["query_id"] = q.query_id
                        d["event_ids"] = q.event_ids
                        d["crawled_at"] = utc_now_iso()
                        fh.write(dumps_jsonl(d))
                        n += 1
                        ev_tweets.append(d)
                    fh.flush()
            except Exception as e:  # kueri gagal dicatat, crawl lanjut; kueri diulang di run berikutnya
                status = f"gagal: {type(e).__name__}: {e}"[:300]
                log.error("[%s] %s gagal setelah %d tweet: %s", k.event_id, q.query_id, n, status)
            if status == "selesai" and n == 0:
                # 0 hasil sering berarti akun/pencarian bermasalah, bukan kueri kosong: jangan
                # tandai selesai agar diulang pada run berikutnya
                status = "kosong"
                log.warning("[%s] %s: 0 tweet — tidak ditandai selesai, akan diulang (cek: python scripts/cek_twscrape.py)",
                            k.event_id, q.query_id)
            append_crawl_log(cfg.paths.crawl_log, {
                "query_id": q.query_id, "event_ids": ";".join(q.event_ids), "query": q.text,
                "crawled_at": crawled_at, "twscrape_version": version, "n_hasil": n, "status": status,
            })
            if status == "selesai":
                progress[q.query_id] = {"status": "selesai", "n_hasil": n, "crawled_at": crawled_at}
                save_progress(cfg.paths.crawl_progress, progress)
            counts[q.query_id] = n
            log.info("[%s] %s: %d tweet — %s", k.event_id, q.query_id, n, q.text)
            if c.sleep_between_queries_s:
                await sleep_fn(c.sleep_between_queries_s)

        # ringkasan per kejadian untuk dicek sebelum lanjut
        n_ev = len(ev_tweets)
        n_id = sum(1 for d in ev_tweets if d.get("lang") == cfg.saring_dasar.lang)
        log.info("=== Ringkasan %s: %d tweet baru, %.1f%% bahasa Indonesia ===", k.event_id, n_ev,
                 100 * n_id / n_ev if n_ev else 0.0)
        for d in rng.sample(ev_tweets, min(c.summary_sample_n, n_ev)):
            log.info("  contoh: %s", (d.get("rawContent") or "").replace("\n", " ")[:200])
        if pause and k is not kejadian[-1]:
            ans = input_fn(f"Lanjut ke kejadian berikutnya setelah {k.event_id}? [y/N] ")
            if ans.strip().lower() not in {"y", "ya", "yes"}:
                log.info("Dihentikan pengguna setelah %s", k.event_id)
                break
    return counts


# --------------------------------------------------------------------------- parse
def _user_hash(user: dict | None, salt: str | None) -> str | None:
    if not salt or not user:
        return None
    uid = user.get("id_str") or user.get("id")
    if uid is None:
        return None
    return hashlib.sha256((str(uid) + salt).encode("utf-8")).hexdigest()


def _tweet_id(d: dict) -> str:
    tid = d.get("id_str")
    if tid is None:
        tid = d.get("id")
    if isinstance(tid, float):
        raise TypeError("tweet_id berupa float — kemungkinan presisi rusak")
    return str(tid)


def is_retweet(d: dict) -> bool:
    return d.get("retweetedTweet") is not None or (d.get("rawContent") or "").startswith("RT @")


def parse_raw_record(d: dict, salt: str | None, lang_id: str) -> dict:
    """Satu baris raw.jsonl -> rekaman teranonimkan. Field user (username, user_id, displayname,
    profil) tidak disalin sama sekali; quote tweet: hanya teks tweet itu sendiri (rawContent)."""
    coords = d.get("coordinates")
    coords = [float(coords["longitude"]), float(coords["latitude"])] if coords else None
    urls = [l.get("url") for l in (d.get("links") or []) if l.get("url")]
    if is_retweet(d):
        drop = DROP_RETWEET
    elif d.get("lang") != lang_id:
        drop = DROP_BUKAN_ID
    else:
        drop = None
    qid = d.get("query_id")
    return {
        "tweet_id": _tweet_id(d),
        "created_at": d.get("date"),
        "text": d.get("rawContent") or "",
        "lang": d.get("lang"),
        "hashtags": list(d.get("hashtags") or []),
        "urls": urls,
        "is_reply": d.get("inReplyToTweetId") is not None or d.get("inReplyToTweetIdStr") is not None,
        "coordinates": coords,
        "query_id": [qid] if qid else [],
        "event_id": list(d.get("event_ids") or []),
        "user_hash": _user_hash(d.get("user"), salt),
        "drop_reason": drop,
    }


def parse_raw(raw_path: str | Path, salt: str | None, lang_id: str) -> tuple[pd.DataFrame, dict]:
    """raw.jsonl -> DataFrame satu baris per tweet_id (query_id & event_id digabung jadi list)."""
    merged: dict[str, dict] = {}
    n_lines = 0
    for d in iter_jsonl(raw_path):
        n_lines += 1
        rec = parse_raw_record(d, salt, lang_id)
        cur = merged.get(rec["tweet_id"])
        if cur is None:
            merged[rec["tweet_id"]] = rec
        else:
            for col in ("query_id", "event_id"):
                for v in rec[col]:
                    if v not in cur[col]:
                        cur[col].append(v)
    for rec in merged.values():
        CrawledTweet.model_validate(rec)  # validasi skema (tweet_id string, dsb.)
        rec["query_id"] = sorted(rec["query_id"])
        rec["event_id"] = sorted(rec["event_id"])
    df = pd.DataFrame(list(merged.values()), columns=CRAWLED_COLS)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    stats = {
        "baris_raw": n_lines,
        "tweet_unik": len(df),
        "duplikat_id": n_lines - len(df),
        "retweet": int((df["drop_reason"] == DROP_RETWEET).sum()),
        "bukan_id": int((df["drop_reason"] == DROP_BUKAN_ID).sum()),
        "lolos": int(df["drop_reason"].isna().sum()),
        "balasan": int(df.loc[df["drop_reason"].isna(), "is_reply"].sum()),
    }
    return df, stats


def export_sample(df: pd.DataFrame, crawl_log: Path, out: Path, n: int, seed: int) -> int:
    """50 tweet acak per kueri untuk dibaca manusia (satu-satunya CSV berisi teks)."""
    qtext = {}
    if crawl_log.exists():
        for r in pd.read_csv(crawl_log, dtype=str, keep_default_na=False).to_dict("records"):
            qtext[r["query_id"]] = r["query"]
    ex = df.explode("query_id").dropna(subset=["query_id"])
    rows = []
    for qid in sorted(ex["query_id"].unique()):
        g = ex[ex["query_id"] == qid].sort_values("tweet_id", key=lambda s: s.map(lambda t: (len(t), t)))
        g = g.sample(n=min(n, len(g)), random_state=seed) if len(g) > n else g
        for r in g.itertuples():
            rows.append({"query_id": qid, "query": qtext.get(qid, ""), "event_id": ";".join(r.event_id),
                         "tweet_id": r.tweet_id, "created_at": r.created_at, "lang": r.lang,
                         "drop_reason": r.drop_reason or "", "text": r.text})
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["query_id", "query", "event_id", "tweet_id", "created_at", "lang",
                                "drop_reason", "text"]).to_csv(out, index=False, encoding="utf-8-sig")
    return len(rows)


# --------------------------------------------------------------------------- run
def run(cfg: Config, events: list[str] | None = None, skip_fetch: bool = False, pause: bool = False,
        api: Any = None) -> pd.DataFrame:
    from dotenv import load_dotenv

    load_dotenv()
    log = setup_logger("crawl", cfg.paths.logs_dir)
    if not skip_fetch:
        if cfg.crawl.use_system_certs:
            use_system_certs(log)
        kejadian = load_kejadian(cfg.paths.kejadian, cfg.crawl.only_pilot, events)
        queries = build_queries(kejadian, cfg)
        log.info("%d kejadian (%s), %d kueri", len(kejadian), ",".join(k.event_id for k in kejadian), len(queries))

        async def _go():
            nonlocal api
            if api is None:
                api = await make_twscrape_api(cfg, log)
            return await fetch(cfg, queries, kejadian, api, log, pause=pause)

        counts = asyncio.run(_go())
        log.info("Crawl selesai: %d kueri dijalankan, %d tweet mentah baru", len(counts), sum(counts.values()))
    else:
        log.info("--skip-fetch: hanya membangun ulang crawled.parquet dari %s", cfg.paths.raw_jsonl)

    if not cfg.paths.raw_jsonl.exists():
        raise FileNotFoundError(f"{cfg.paths.raw_jsonl} belum ada — jalankan crawl dulu")
    salt = os.environ.get("USER_HASH_SALT") or None
    if not salt:
        log.warning("USER_HASH_SALT kosong: user_hash diisi null")
    df, st = parse_raw(cfg.paths.raw_jsonl, salt, cfg.saring_dasar.lang)
    log.info("raw.jsonl: %d baris -> %d tweet unik (duplikat ID digabung: %d)", st["baris_raw"], st["tweet_unik"], st["duplikat_id"])
    log.info("Saring dasar: retweet=%d, bukan_id=%d, lolos=%d (termasuk %d balasan, is_reply=True)",
             st["retweet"], st["bukan_id"], st["lolos"], st["balasan"])
    write_parquet(df, cfg.paths.crawled, CRAWLED_COLS)
    n_sample = export_sample(df, cfg.paths.crawl_log, cfg.paths.sampel_kueri, cfg.crawl.sample_per_query, cfg.seed)
    log.info("Ditulis: %s; sampel cek manual %d baris -> %s", cfg.paths.crawled, n_sample, cfg.paths.sampel_kueri)

    update_alur_data(cfg.paths.alur_data, "hasil crawl", st["baris_raw"], st["baris_raw"], 0, "")
    update_alur_data(cfg.paths.alur_data, "saring dasar", st["baris_raw"], st["lolos"],
                     st["baris_raw"] - st["lolos"],
                     f"{DROP_BUKAN_ID}={st['bukan_id']}; {DROP_RETWEET}={st['retweet']}; "
                     f"duplikat_id={st['duplikat_id']} (digabung, query_id jadi list)")
    return df
