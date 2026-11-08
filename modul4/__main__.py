"""python -m modul4 <perintah>
  modelku                         daftar model tersedia di Cerebras & Groq (butuh kunci di .env)
  korpus                          4.1 kunci korpus + pemeriksaan
  soal-draf                       4.2 buat soal DRAF (uji mekanik; gold ditulis manual)
  laporan [--de DE0001|--semua]   4.3 laporan situasi per DisasterEvent
  tanya "pertanyaan"              4.4 tanya-jawab
  evaluasi --soal berkas.jsonl    4.5 evaluasi (+ pembanding tanpa retrieval, hakim model berbeda)
  semua                           korpus -> soal-draf -> laporan -> evaluasi
Pintu data: --backend neo4j (bawaan) atau csv (hasil `python -m modul3 proses`, tanpa Neo4j)."""
import argparse, json, os, sys
from contextlib import ExitStack
from . import korpus, laporan, qa, evaluasi as ev
from .llm import LLM, daftar_model, PROVIDERS
from .repo import Neo4jRepo, MemRepo

KELUAR = "dev_2025/data/modul4"


def ambil_repo(a, stack):
    if a.backend == "csv": return MemRepo(a.data)
    from modul3.neo4j_conn import driver
    drv, db = driver(); stack.enter_context(drv)
    return Neo4jRepo(stack.enter_context(drv.session(database=db)))


def buat_llm(spec, cad, log):
    return LLM(spec, cadangan=cad or None, log=log)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perintah", choices=["modelku", "korpus", "soal-draf", "laporan", "tanya", "evaluasi", "semua"])
    ap.add_argument("pertanyaan", nargs="?")
    ap.add_argument("--backend", choices=["neo4j", "csv"], default="neo4j"); ap.add_argument("--data", default="dev_2025/data/modul3")
    ap.add_argument("--keluar", default=KELUAR)
    ap.add_argument("--gen", default="groq:openai/gpt-oss-120b", help="penjawab/penulis laporan, 'provider:model'")
    ap.add_argument("--judge", default="groq:qwen/qwen3.8-27b", help="hakim; HARUS model berbeda dari --gen")
    ap.add_argument("--cadangan", default="groq:openai/gpt-oss-20b", help="model cadangan untuk --gen bila kena batas laju")
    ap.add_argument("--de"); ap.add_argument("--semua", action="store_true"); ap.add_argument("--soal")
    ap.add_argument("--tanpa-llm", action="store_true", help="laporan: hanya kerangka fakta")
    ap.add_argument("--maks-konteks", type=int, default=9000, help="karakter konteks per jawaban (batas token per menit Groq kecil)")
    a = ap.parse_args(argv)
    os.makedirs(a.keluar, exist_ok=True)
    if a.perintah == "modelku":
        for p in PROVIDERS:
            try: print(p, "->", ", ".join(daftar_model(p)))
            except BaseException as e: print(p, "gagal:", e)
        return
    if a.gen == a.judge: sys.exit("--judge harus berbeda dari --gen (hakim tidak boleh menilai keluarannya sendiri)")
    log = os.path.join(a.keluar, "log_llm.jsonl")
    with ExitStack() as st:
        repo = ambil_repo(a, st)
        gen = buat_llm(a.gen, a.cadangan, log); judge = buat_llm(a.judge, None, log)
        if a.perintah in ("korpus", "semua"):
            m = korpus.kunci(repo, a.keluar, "dev_2025/data/processed/extraction_resolved_filter200_v6pangkas.jsonl")
            print("4.1 korpus:", m)
            if not m["lolos"]: sys.exit("korpus gagal pemeriksaan; eksperimen dihentikan")
        if a.perintah in ("soal-draf", "semua"):
            if not hasattr(repo, "g"): repo_csv = MemRepo(a.data)
            else: repo_csv = repo
            soal = ev.buat_soal_draf(repo_csv)
            with open(os.path.join(a.keluar, "soal_draf.jsonl"), "w", encoding="utf-8") as f:
                for s in soal: f.write(json.dumps(s, ensure_ascii=False) + "\n")
            print(f"4.2 soal draf: {len(soal)} -> {a.keluar}/soal_draf.jsonl (kunci dari graf; BUKAN gold)")
        if a.perintah in ("laporan", "semua"):
            os.makedirs(os.path.join(a.keluar, "laporan"), exist_ok=True)
            ids = [d["event_id"] for d in repo.daftar_de(limit=10_000)] if (a.semua or a.perintah == "semua") else [a.de]
            if not ids or ids == [None]: sys.exit("pakai --de ID atau --semua")
            ok = 0
            for i in ids:
                k = repo.kerangka(i)
                if not k: print("DE tidak ada:", i); continue
                r = laporan.buat_laporan(k, None if a.tanpa_llm else gen)
                open(os.path.join(a.keluar, "laporan", f"{i}.md"), "w", encoding="utf-8").write(r["markdown"])
                ok += r["valid"]; print(f"  {i} valid={r['valid']} {r['masalah'][:2]}")
            print(f"4.3 laporan: {len(ids)} dibuat, {ok} lolos validasi sitasi/angka")
        wil = qa.Wilayah(repo._nama() if hasattr(repo, "_nama") else None)
        def laporan_fn(k): return laporan.buat_laporan(k, gen)["markdown"]
        def jalan(q): return qa.tanya(q, repo, gen, wil, maks_konteks=a.maks_konteks, laporan_fn=laporan_fn)
        if a.perintah == "tanya":
            if not a.pertanyaan: sys.exit('contoh: python -m modul4 tanya "Berapa korban banjir di Aceh Tamiang?"')
            r = jalan(a.pertanyaan)
            print(json.dumps({k: v for k, v in r.items() if k != "konteks"}, ensure_ascii=False, indent=1))
        if a.perintah in ("evaluasi", "semua"):
            path = a.soal or os.path.join(a.keluar, "soal_draf.jsonl")
            _, ring = ev.evaluasi(ev.muat_soal(path), jalan, gen, judge, a.keluar)
            print("4.5 evaluasi:", json.dumps(ring, ensure_ascii=False, indent=1))
        print("Pemakaian LLM gen:", gen.pakai, "| judge:", judge.pakai, "| log:", log)


if __name__ == "__main__":
    main()
