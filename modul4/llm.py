"""Klien LLM (API kompatibel OpenAI) untuk Cerebras dan Groq: pembatas laju, retry 429, cadangan, dan log pemakaian.
Kunci API hanya dari variabel lingkungan / .env (CEREBRAS_API_KEY, GROQ_API_KEY)."""
import json, os, re, time, datetime, hashlib, urllib.request, urllib.error
from dataclasses import dataclass
from modul3.neo4j_conn import muat_env

PROVIDERS = {
    "cerebras": {"base": "https://api.cerebras.ai/v1", "env": "CEREBRAS_API_KEY", "jeda": 12.0},
    "groq": {"base": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY", "jeda": 2.5},
}
_terakhir = {}


@dataclass
class Hasil:
    teks: str
    provider: str
    model: str
    token_masuk: int = 0
    token_keluar: int = 0
    detik: float = 0.0


def pisah(spec):
    p, _, m = spec.partition(":")
    if p not in PROVIDERS or not m: raise ValueError(f"spec harus 'provider:model' (provider: {', '.join(PROVIDERS)}), dapat: {spec!r}")
    return p, m


def _kunci(provider):
    muat_env()
    k = os.environ.get(PROVIDERS[provider]["env"])
    if not k: raise SystemExit(f"Isi {PROVIDERS[provider]['env']} di file .env")
    return k


def _http(provider, jalur, payload=None, timeout=120):
    req = urllib.request.Request(PROVIDERS[provider]["base"] + jalur, method="POST" if payload is not None else "GET",
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": "Bearer " + _kunci(provider), "Content-Type": "application/json",
                                          "User-Agent": "skripsi-modul4/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()), dict(r.headers)


def daftar_model(provider):
    d, _ = _http(provider, "/models")
    return sorted(m["id"] for m in d.get("data", []))


def ekstrak_json(teks):
    """JSON pertama dalam teks (toleran terhadap pagar kode/penjelasan)."""
    t = re.sub(r"```(?:json)?", "", teks or "").strip()
    for m in re.finditer(r"[\{\[]", t):
        try:
            obj, _ = json.JSONDecoder().raw_decode(t[m.start():]); return obj
        except ValueError: continue
    raise ValueError("tidak ada JSON pada keluaran model")


class LLM:
    def __init__(self, spec, cadangan=None, log=None, suhu=0.0, maks_token=1500, maks_coba=5):
        self.spec, self.cadangan, self.log, self.suhu, self.maks_token, self.maks_coba = spec, cadangan, log, suhu, maks_token, maks_coba
        self.tanpa_reasoning = False
        self.pakai = {"panggilan": 0, "token_masuk": 0, "token_keluar": 0}

    def chat(self, pesan, json_mode=False, maks_token=None):
        spec, gagal = self.spec, 0
        for coba in range(self.maks_coba):
            try:
                return self._sekali(spec, pesan, json_mode, maks_token or self.maks_token)
            except urllib.error.HTTPError as e:
                isi = e.read().decode(errors="ignore")[:300]
                if e.code == 400 and json_mode and "response_format" in isi: json_mode = False; continue
                if e.code == 400 and not self.tanpa_reasoning and "reasoning" in isi: self.tanpa_reasoning = True; continue
                if e.code in (401, 403): raise SystemExit(f"{spec}: kunci ditolak/tidak berhak ({e.code}): {isi}")
                if e.code == 404: raise SystemExit(f"{spec}: model tidak ditemukan; jalankan `python -m modul4 modelku`")
                tunggu = self._tunggu(e, isi, coba); gagal += 1
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                tunggu = 5 * (coba + 1); gagal += 1
            if gagal >= 2 and self.cadangan and spec != self.cadangan:
                print(f"  [llm] {spec} bermasalah, pindah ke cadangan {self.cadangan}"); spec = self.cadangan
            time.sleep(min(tunggu, 90))
        raise RuntimeError(f"LLM gagal setelah {self.maks_coba} percobaan ({spec})")

    @staticmethod
    def _tunggu(e, isi, coba):
        ra = e.headers.get("retry-after") if e.headers else None
        if ra:
            try: return float(ra) + 1
            except ValueError: pass
        m = re.search(r"try again in ([\d.]+)(ms|s|m)", isi)
        if m: return float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60}[m.group(2)] + 1
        return 8 * (coba + 1)

    def _sekali(self, spec, pesan, json_mode, maks_token):
        prov, model = pisah(spec)
        sisa = PROVIDERS[prov]["jeda"] - (time.time() - _terakhir.get(prov, 0))
        if sisa > 0: time.sleep(sisa)
        payload = {"model": model, "messages": pesan, "temperature": self.suhu, "max_tokens": maks_token}
        if json_mode: payload["response_format"] = {"type": "json_object"}
        if not self.tanpa_reasoning:
            if "gpt-oss" in model: payload["reasoning_effort"] = "low"
            elif prov == "groq" and "qwen" in model: payload["reasoning_effort"] = "none"     # matikan 'berpikir' agar token tidak habis; dibuang otomatis bila ditolak
        t0 = time.time()
        try: d, _ = _http(prov, "/chat/completions", payload)
        finally: _terakhir[prov] = time.time()
        msg = d["choices"][0]["message"]; u = d.get("usage", {})
        isi = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S).strip()
        h = Hasil(isi, prov, model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), time.time() - t0)
        self.pakai["panggilan"] += 1; self.pakai["token_masuk"] += h.token_masuk; self.pakai["token_keluar"] += h.token_keluar
        if self.log:
            os.makedirs(os.path.dirname(self.log) or ".", exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"waktu": datetime.datetime.now().isoformat(timespec="seconds"), "provider": prov, "model": model,
                                    "token_masuk": h.token_masuk, "token_keluar": h.token_keluar, "detik": round(h.detik, 2),
                                    "hash_prompt": hashlib.sha1(json.dumps(pesan, ensure_ascii=False).encode()).hexdigest()[:12],
                                    "pesan": pesan, "balasan": h.teks}, ensure_ascii=False) + "\n")
        return h
