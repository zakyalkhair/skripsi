"""Langkah 2.1 — ekstraksi joint single-pass (satu tweet per panggilan LLM), versi awal v1.

Jalur utama: Ollama lokal (API asli /api/chat; mencatat waktu & token per tweet). Alternatif: endpoint
OpenAI-compatible (`api: openai`). Respons mentah disimpan per tweet (checkpoint): menjalankan ulang
perintah yang sama melanjutkan dari tweet yang belum selesai untuk prompt yang sama.
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

PROMPT_DIR = Path(__file__).parent / "prompt"


# ----------------------------------------------------------------------------- prompt
def load_abbrev(path: Path = PROMPT_DIR / "geo_abbrev.csv") -> dict[str, str]:
    import csv
    with open(path, encoding="utf-8") as f:
        return {r["singkatan"]: r["nama_resmi"] for r in csv.DictReader(f)}


def build_system(prompt_dir: Path = PROMPT_DIR, versi: str = "v1") -> str:
    sys_txt = (prompt_dir / f"system_{versi}.md").read_text(encoding="utf-8").strip()
    ab = load_abbrev(prompt_dir / "geo_abbrev.csv")
    sing = ", ".join(f"{k}={v}" for k, v in ab.items())
    return sys_txt.replace("GEO_SINGKATAN", sing)


def load_fewshot(prompt_dir: Path = PROMPT_DIR, versi: str = "v1", n: int | None = None) -> list[dict]:
    rows = [json.loads(l) for l in (prompt_dir / f"fewshot_{versi}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows if n is None else rows[:n]


def build_messages(text: str, system: str, fewshots: list[dict]) -> list[dict]:
    msgs = [{"role": "system", "content": system}]
    for ex in fewshots:  # urutan tetap -> awalan prompt identik antar tweet (cache KV Ollama terpakai)
        msgs.append({"role": "user", "content": f"Tweet:\n{ex['tweet']}"})
        msgs.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False, separators=(",", ":"))})
    msgs.append({"role": "user", "content": f"Tweet:\n{text}"})
    return msgs


def prompt_hash(system: str, fewshots: list[dict], model: str) -> str:
    blob = json.dumps({"s": system, "f": fewshots, "m": model}, ensure_ascii=False, sort_keys=True)
    return "p" + hashlib.sha256(blob.encode()).hexdigest()[:12]


# ----------------------------------------------------------------------------- klien
class LLMError(Exception):
    pass


class Client:
    """Klien minimal tanpa dependensi. `api`: 'ollama' (/api/chat) atau 'openai' (/v1/chat/completions)."""

    def __init__(self, base_url: str, model: str, api: str = "ollama", timeout_s: float = 900,
                 num_ctx: int = 8192, api_key: str | None = None, seed: int = 42):
        self.base, self.model, self.api, self.timeout = base_url.rstrip("/"), model, api, timeout_s
        self.num_ctx, self.key, self.seed = num_ctx, api_key, seed

    def _post(self, url: str, body: dict) -> dict:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self.key}"} if self.key else {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError(f"koneksi: {e}") from e

    def chat(self, messages: list[dict], max_tokens: int) -> dict:
        """-> {content, finish_reason, prompt_tokens, completion_tokens, durasi_s, prompt_s, gen_s}"""
        t0 = time.time()
        if self.api == "ollama":
            d = self._post(f"{self.base}/api/chat", {
                "model": self.model, "messages": messages, "stream": False, "format": "json",
                "keep_alive": "30m",
                "options": {"temperature": 0, "seed": self.seed, "num_ctx": self.num_ctx, "num_predict": max_tokens}})
            ns = 1e9
            return {"content": d.get("message", {}).get("content"),
                    "finish_reason": "length" if d.get("done_reason") == "length" else "stop",
                    "prompt_tokens": d.get("prompt_eval_count"), "completion_tokens": d.get("eval_count"),
                    "durasi_s": round(time.time() - t0, 2),
                    "prompt_s": round(d.get("prompt_eval_duration", 0) / ns, 2),
                    "gen_s": round(d.get("eval_duration", 0) / ns, 2)}
        d = self._post(f"{self.base}/chat/completions", {
            "model": self.model, "messages": messages, "temperature": 0, "seed": self.seed,
            "max_tokens": max_tokens, "response_format": {"type": "json_object"}})
        ch, u = d["choices"][0], d.get("usage", {})
        return {"content": ch["message"].get("content"), "finish_reason": ch.get("finish_reason"),
                "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                "durasi_s": round(time.time() - t0, 2), "prompt_s": None, "gen_s": None}


# ----------------------------------------------------------------------------- data
def load_input(path: Path, limit: int | None, acak: bool, seed: int = 42) -> list[dict]:
    import pandas as pd
    p = Path(path)
    df = pd.read_parquet(p) if p.suffix == ".parquet" else (
        pd.read_json(p, lines=True) if p.suffix == ".jsonl" else pd.read_csv(p))
    if "label" in df.columns:
        df = df[df["label"] == "informatif"]
    if "is_representatif" in df.columns:
        df = df[df["is_representatif"].fillna(True).astype(bool)]
    df = df[["tweet_id", "text_raw", "created_at"]].dropna(subset=["text_raw"])
    df["tweet_id"] = df["tweet_id"].astype(str)
    df["created_at"] = df["created_at"].astype(str)
    rows = df.to_dict("records")
    if acak:
        random.Random(seed).shuffle(rows)
    return rows[:limit] if limit else rows


def done_ids(out: Path, phash: str) -> set[str]:
    if not out.exists():
        return set()
    s = set()
    for line in out.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("prompt_hash") == phash and r.get("status") in ("ok", "terpotong", "json_rusak"):
            s.add(str(r["tweet_id"]))
    return s


# ----------------------------------------------------------------------------- run
def extract_one(client: Any, text: str, system: str, fewshots: list[dict], tingkat: list[int]) -> dict:
    """Satu tweet: max_tokens bertingkat; ulang 1× bila JSON rusak padahal tidak terpotong."""
    from .validate import parse_json
    msgs = build_messages(text, system, fewshots)
    hist, res, tahap = [], None, 0
    for tahap, mt in enumerate(tingkat, 1):
        res = client.chat(msgs, mt)
        hist.append(res)
        if res["finish_reason"] == "length":
            continue
        if parse_json(res["content"]) is None and len(hist) < len(tingkat) + 1:
            res = client.chat(msgs, mt)
            hist.append(res)
        break
    status = ("terpotong" if res["finish_reason"] == "length"
              else "ok" if parse_json(res["content"]) is not None else "json_rusak")
    return {"raw": res["content"], "status": status, "tahap": tahap, "max_tokens": tingkat[tahap - 1],
            "panggilan": len(hist), "durasi_s": round(sum(h["durasi_s"] for h in hist), 2),
            "prompt_tokens": res.get("prompt_tokens"), "completion_tokens": res.get("completion_tokens"),
            "prompt_s": res.get("prompt_s"), "gen_s": res.get("gen_s"), "finish_reason": res["finish_reason"]}


def run(rows: list[dict], client: Any, out: Path, system: str, fewshots: list[dict], tingkat: list[int],
        phash: str, target_estimasi: int = 2000, log: Callable[[str], None] = print) -> list[dict]:
    out.parent.mkdir(parents=True, exist_ok=True)
    skip = done_ids(out, phash)
    todo = [r for r in rows if r["tweet_id"] not in skip]
    log(f"{len(rows)} tweet masukan, {len(skip & {r['tweet_id'] for r in rows})} sudah selesai, {len(todo)} dikerjakan")
    hasil, dur = [], []
    with open(out, "a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            try:
                rec = extract_one(client, r["text_raw"], system, fewshots, tingkat)
            except LLMError as e:
                log(f"[{i}/{len(todo)}] {r['tweet_id']} GAGAL: {e}")
                if "HTTP 404" in str(e) or "koneksi" in str(e):
                    log("Berhenti: model/server tidak tersedia (cek `ollama list` / `ollama serve`).")
                    break
                continue
            rec.update({"tweet_id": r["tweet_id"], "created_at": r["created_at"], "model": client.model,
                        "prompt_hash": phash, "waktu": time.strftime("%Y-%m-%dT%H:%M:%S")})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            hasil.append(rec)
            dur.append(rec["durasi_s"])
            med = statistics.median(dur[1:] or dur)  # panggilan pertama memuat model + prompt penuh
            sisa = (len(todo) - i) * med
            log(f"[{i}/{len(todo)}] {r['tweet_id']} {rec['status']} {rec['durasi_s']:.1f}s "
                f"(in {rec['prompt_tokens']} tok/{rec['prompt_s']}s, out {rec['completion_tokens']} tok/{rec['gen_s']}s) "
                f"| median {med:.1f}s/tweet -> sisa ±{sisa/3600:.1f} jam; {target_estimasi} tweet ±{target_estimasi*med/3600:.1f} jam")
    return hasil


def ringkas_waktu(out: Path, target: int = 2000) -> dict:
    recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not recs:
        return {}
    d = [r["durasi_s"] for r in recs]
    d2 = d[1:] or d
    q = sorted(d2)
    med = statistics.median(d2)
    gen = [r["completion_tokens"] / r["gen_s"] for r in recs if r.get("gen_s") and r.get("completion_tokens")]
    return {"n": len(recs), "status": {s: sum(r["status"] == s for r in recs) for s in {r["status"] for r in recs}},
            "detik_per_tweet_median": round(med, 1), "detik_p90": round(q[int(0.9 * (len(q) - 1))], 1),
            "token_keluar_median": statistics.median([r["completion_tokens"] or 0 for r in recs]),
            "token_per_detik_generasi": round(statistics.median(gen), 2) if gen else None,
            "panggilan_pertama_s": d[0],
            f"estimasi_{target}_tweet_jam": round(target * med / 3600, 1),
            f"estimasi_{target}_tweet_jam_rata2": round(target * statistics.mean(d2) / 3600, 1)}
