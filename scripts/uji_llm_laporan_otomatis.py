"""Uji: apakah Qwen lokal + prompt ketat membuang laporan gempa otomatis tanpa kode?  (25 Okt 2026)

Cara pakai (dari folder Skripsi, lingkungan Python Windows yang biasa dipakai; hanya pustaka bawaan):
    python scripts\\uji_llm_laporan_otomatis.py                 # uji penuh ±250 tweet, ±40 menit
    python scripts\\uji_llm_laporan_otomatis.py --limit 20      # uji kecil dulu
    python scripts\\uji_llm_laporan_otomatis.py --asli-semua    # + prompt aktif pada semua kelompok (≈ 2x waktu)

Syarat: Ollama berjalan dan model `qwen2.5-cpu` sudah dibuat (sama dengan filter 1.4).
Hasil: dev_2025/reports/uji_llm_laporan_otomatis_hasil.csv (dilanjutkan otomatis bila dihentikan) + ringkasan di layar.
Data: SAMPEL 2025 (data pengembangan), bukan 2026.
"""
import argparse, csv, json, math, random, re, sys, time, urllib.request, urllib.error
from pathlib import Path

SAMPEL = "dev_2025/reports/uji_llm_laporan_otomatis_sampel.csv"
PROMPT = {"ketat": "config/prompt_informatif_uji_ketat.md", "asli": "config/prompt_informatif.md"}
HASIL = "dev_2025/reports/uji_llm_laporan_otomatis_hasil.csv"
LABELS = {"informatif", "noninformatif"}


def pesan_pengguna(teks):
    blok = "\n".join(f'<tweet id="{i}">\n{t}\n</tweet>' for i, t in enumerate(teks, 1))
    return f"Tweet ({len(teks)}):\n{blok}"


def parse(isi, n):
    m = re.search(r"\{.*\}", isi or "", flags=re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    out = {}
    for it in (data.get("hasil") or []) if isinstance(data, dict) else []:
        try:
            i = int(str(it.get("id")).strip())
        except (ValueError, AttributeError):
            continue
        lab = str(it.get("label", "")).strip().lower()
        if 1 <= i <= n and lab in LABELS:
            out[i] = lab
    return out


def panggil(url, model, sistem, teks, timeout, coba=3):
    payload = {"model": model, "temperature": 0, "max_tokens": 2048,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": sistem},
                            {"role": "user", "content": pesan_pengguna(teks)}]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    for k in range(coba):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404):  # galat setelan (mis. model belum dibuat): berhenti, jangan catat label
                sys.exit(f"GALAT SETELAN HTTP {e.code}: {e.read()[:300]!r}. Periksa Ollama dan nama model.")
        except Exception:
            pass
        time.sleep(3 * (k + 1))
    return None


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:11434/v1/chat/completions")
    ap.add_argument("--model", default="qwen2.5-cpu")
    ap.add_argument("--batch", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None, help="batasi jumlah tweet (uji cepat)")
    ap.add_argument("--asli-semua", action="store_true", help="jalankan prompt aktif pada SEMUA kelompok (default: hanya kontrol)")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    prompts = {k: Path(v).read_text(encoding="utf-8") for k, v in PROMPT.items()}
    with open(SAMPEL, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    random.Random(42).shuffle(rows)  # campur kelompok agar satu permintaan tidak berisi kelompok yang sama
    if a.limit:
        rows = rows[:a.limit]

    sudah = {}
    if Path(HASIL).exists():
        with open(HASIL, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                sudah[(r["prompt"], r["tweet_id"])] = r
    keluar = open(HASIL, "a", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(keluar, fieldnames=["prompt", "tweet_id", "kelompok", "label", "teks"])
    if not sudah:
        w.writeheader()

    tugas = [("ketat", rows)]
    tugas.append(("asli", rows if a.asli_semua else [r for r in rows if r["kelompok"] != "otomatis_tanpa_dirasakan" and (a.asli_semua or r["kelompok"] == "kontrol_berita_gempa")]))
    for nama, data in tugas:
        todo = [r for r in data if (nama, r["tweet_id"]) not in sudah]
        print(f"[{nama}] {len(todo)} tweet ({len(data) - len(todo)} sudah ada)")
        mulai = time.time()
        for i in range(0, len(todo), a.batch):
            blok = todo[i:i + a.batch]
            isi = panggil(a.url, a.model, prompts[nama], [r["text_raw"] for r in blok], a.timeout)
            lab = parse(isi, len(blok)) if isi else None
            for j, r in enumerate(blok, 1):
                l = (lab or {}).get(j)
                if l is None:  # hilang/gagal parse: kirim ulang satu per satu (sama dengan filter 1.4)
                    one = parse(panggil(a.url, a.model, prompts[nama], [r["text_raw"]], a.timeout) or "", 1)
                    l = (one or {}).get(1, "GAGAL")
                w.writerow({"prompt": nama, "tweet_id": r["tweet_id"], "kelompok": r["kelompok"], "label": l,
                            "teks": r["text_raw"].replace("\n", " ")[:300]})
                sudah[(nama, r["tweet_id"])] = {"label": l, "kelompok": r["kelompok"], "tweet_id": r["tweet_id"], "teks": r["text_raw"], "prompt": nama}
            keluar.flush()
            selesai = min(i + a.batch, len(todo))
            print(f"  {selesai}/{len(todo)}  ({(time.time() - mulai) / 60:.1f} menit)", flush=True)
    keluar.close()
    ringkas(sudah)


def ringkas(sudah):
    print("\n================ RINGKASAN ================")
    for nama in ("ketat", "asli"):
        sub = [r for (p, _), r in sudah.items() if p == nama]
        if not sub:
            continue
        print(f"\nPrompt {nama.upper()}")
        for kel in ("otomatis_tanpa_dirasakan", "otomatis_dirasakan", "kontrol_berita_gempa"):
            g = [r for r in sub if r["kelompok"] == kel]
            if not g:
                continue
            n = len(g); ni = sum(r["label"] == "noninformatif" for r in g); inf = sum(r["label"] == "informatif" for r in g); gl = n - ni - inf
            lo, hi = wilson(ni, n)
            print(f"  {kel:28s} n={n:3d}  noninformatif={ni:3d} ({100*ni/n:5.1f}%)  informatif={inf:3d}  gagal={gl}  | noninformatif 95% CI {100*lo:.1f}-{100*hi:.1f}%")
    ket = {r["tweet_id"]: r["label"] for (p, _), r in sudah.items() if p == "ketat" and r["kelompok"] == "kontrol_berita_gempa"}
    asl = {r["tweet_id"]: r["label"] for (p, _), r in sudah.items() if p == "asli" and r["kelompok"] == "kontrol_berita_gempa"}
    ubah = [t for t in ket if t in asl and ket[t] != asl[t]]
    print(f"\nKontrol: label berubah akibat klausa baru = {len(ubah)} dari {len(set(ket) & set(asl))}")
    for (p, t), r in sudah.items():
        if p == "ketat" and t in ubah:
            print(f"   {asl[t]} -> {ket[t]} | {r['teks'][:140].replace(chr(10), ' ')}")
    print("\nTweet laporan otomatis TANPA dirasakan yang lolos sebagai informatif (prompt ketat):")
    lolos = [r for (p, _), r in sudah.items() if p == "ketat" and r["kelompok"] == "otomatis_tanpa_dirasakan" and r["label"] != "noninformatif"]
    for r in lolos[:30]:
        print(f"   [{r['label']}] {r['teks'][:150].replace(chr(10), ' ')}")
    if len(lolos) > 30:
        print(f"   ... {len(lolos) - 30} lainnya ada di berkas hasil")


if __name__ == "__main__":
    main()
