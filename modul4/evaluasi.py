"""4.5 Evaluasi keluaran: nugget, abstain (Q5), sitasi, faithfulness (LLM-judge model BERBEDA), pembanding tanpa retrieval (dua urutan), biaya.
Soal draf otomatis HANYA untuk uji mekanik (kunci dari graf = melingkar); gold sungguhan: kunci nugget ditulis tangan dari tweet."""
import csv, json, os, re, random
from .llm import ekstrak_json
from .qa import TIDAK_ADA
from .laporan import normal_angka

SYS_FAITH = ("Kamu penilai kesetiaan jawaban. Diberi KONTEKS dan JAWABAN. Pecah JAWABAN menjadi klaim atomik, tandai tiap klaim 1 bila didukung KONTEKS, "
             "0 bila tidak. Balas HANYA JSON: {\"klaim\": [{\"teks\": \"...\", \"didukung\": 1}]}")
SYS_PAIR = ("Kamu penilai. Diberi PERTANYAAN, KONTEKS_BUKTI (fakta dari data), dan dua jawaban A dan B. Pilih jawaban yang lebih akurat terhadap KONTEKS_BUKTI "
            "dan tidak mengarang. Balas HANYA JSON: {\"pemenang\": \"A\"|\"B\"|\"seri\"}")
SYS_BASE = "Jawab pertanyaan berikut dalam bahasa Indonesia, ringkas. Jika tidak tahu, katakan tidak tahu."


def norm(s):
    s = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", (s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def muat_soal(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def buat_soal_draf(repo, seed=7, n_q5=3):
    """Q1 (kapan), Q3 (kabupaten mana), Q5 (tak terjawab). Kunci diambil dari graf -> hanya uji mekanik."""
    rnd, soal = random.Random(seed), []
    for e in repo.g["events"] if hasattr(repo, "g") else []:
        k = repo.kerangka(e["event_id"])
        kab = sorted({r["kab_nama"] for r in k["laporan"] if r.get("kab_nama")})
        if not kab: continue
        soal.append({"id": f"Q1-{e['event_id']}", "kelompok": "Q1", "pertanyaan": f"Kapan {e['jenis'].replace('_', ' ')} di {kab[0]} terjadi?", "nugget": [e["start_time"]], "event_id": e["event_id"], "sumber": "draf_graf"})
        soal.append({"id": f"Q3-{e['event_id']}", "kelompok": "Q3", "pertanyaan": f"Kabupaten atau kota mana saja yang terdampak {e['jenis'].replace('_', ' ')} pada {e['start_time']}?", "nugget": kab, "event_id": e["event_id"], "sumber": "draf_graf"})
    ada = {(e["jenis"], kd) for e in repo.g["events"] for kd in e["kode_wilayah"]} if hasattr(repo, "g") else set()
    nama = repo._nama()
    for kd in rnd.sample([k for k in nama if len(k) == 5], 200):
        if len(soal) and sum(1 for s in soal if s["kelompok"] == "Q5") >= n_q5: break
        if not any(kd == x[1] for x in ada):
            soal.append({"id": f"Q5-{kd}", "kelompok": "Q5", "pertanyaan": f"Berapa korban meninggal akibat banjir di {nama[kd]} pada Januari 2025?", "nugget": ["ABSTAIN"], "event_id": None, "sumber": "draf_graf"})
    return soal


def skor_nugget(jawab, nugget):
    if nugget == ["ABSTAIN"]: return 1.0 if TIDAK_ADA[:30].lower() in (jawab or "").lower() else 0.0
    j = norm(jawab)
    return sum(1 for n in nugget if norm(str(n)) in j) / max(1, len(nugget))


def faith(judge, ctx, jawab):
    if not jawab or TIDAK_ADA[:30].lower() in jawab.lower(): return None
    try:
        kl = ekstrak_json(judge.chat([{"role": "system", "content": SYS_FAITH}, {"role": "user", "content": f"KONTEKS:\n{ctx}\n\nJAWABAN:\n{jawab}"}], json_mode=True, maks_token=900).teks).get("klaim", [])
        return sum(int(x.get("didukung", 0)) for x in kl) / len(kl) if kl else None
    except (ValueError, KeyError, TypeError, AttributeError): return None


def pemenang(judge, tanya, ctx, a, b):
    try:
        w = ekstrak_json(judge.chat([{"role": "system", "content": SYS_PAIR}, {"role": "user", "content": f"PERTANYAAN: {tanya}\n\nKONTEKS_BUKTI:\n{ctx}\n\nJAWABAN A:\n{a}\n\nJAWABAN B:\n{b}"}], json_mode=True, maks_token=60).teks).get("pemenang")
        return w if w in ("A", "B", "seri") else "seri"
    except (ValueError, AttributeError): return "seri"


def evaluasi(soal, jalankan_g, gen, judge, keluar, dengan_pembanding=True):
    """jalankan_g(pertanyaan)->dict QA (modul4.qa.tanya). gen = LLM pembanding tanpa retrieval."""
    os.makedirs(keluar, exist_ok=True)
    baris = []
    for s in soal:
        r = jalankan_g(s["pertanyaan"])
        row = {"id": s["id"], "kelompok": s["kelompok"], "pertanyaan": s["pertanyaan"], "jawaban_graf": r["jawaban"], "abstain": r["abstain"],
               "skor_nugget": round(skor_nugget(r["jawaban"], s["nugget"]), 3), "sitasi_valid": r["sitasi_valid"], "n_sitasi": len(r["tweet_ids"]),
               "token_masuk": r.get("token", {}).get("masuk", 0), "token_keluar": r.get("token", {}).get("keluar", 0)}
        row["faithfulness"] = faith(judge, r["konteks"], r["jawaban"]) if r["konteks"] else None
        if dengan_pembanding:
            base = gen.chat([{"role": "system", "content": SYS_BASE}, {"role": "user", "content": s["pertanyaan"]}], maks_token=400).teks
            row["jawaban_tanpa_retrieval"] = base; row["skor_nugget_tanpa_retrieval"] = round(skor_nugget(base, s["nugget"]), 3)
            if r["konteks"]:
                w1 = pemenang(judge, s["pertanyaan"], r["konteks"], r["jawaban"], base)       # graf = A
                w2 = pemenang(judge, s["pertanyaan"], r["konteks"], base, r["jawaban"])        # graf = B
                menang = (w1 == "A") + (w2 == "B"); kalah = (w1 == "B") + (w2 == "A")
                row["hakim_pairwise"] = "graf" if menang > kalah else ("tanpa_retrieval" if kalah > menang else "seri/tak_konsisten")
        baris.append(row)
    cols = sorted({k for b in baris for k in b}, key=lambda c: ["id", "kelompok", "pertanyaan"].index(c) if c in ("id", "kelompok", "pertanyaan") else 99)
    with open(os.path.join(keluar, "evaluasi_qa.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(baris)
    ring = ringkas(baris); json.dump(ring, open(os.path.join(keluar, "evaluasi_ringkasan.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return baris, ring


def rata(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def ringkas(baris):
    out = {"n_soal": len(baris), "per_kelompok": {}, "sitasi_valid_semua": rata([1.0 if b["sitasi_valid"] else 0.0 for b in baris if b["sitasi_valid"] is not None]),
           "faithfulness_rata2": rata([b["faithfulness"] for b in baris]), "token_masuk": sum(b["token_masuk"] for b in baris), "token_keluar": sum(b["token_keluar"] for b in baris)}
    for kel in sorted({b["kelompok"] for b in baris}):
        bs = [b for b in baris if b["kelompok"] == kel]
        out["per_kelompok"][kel] = {"n": len(bs), "nugget_graf": rata([b["skor_nugget"] for b in bs]), "nugget_tanpa_retrieval": rata([b.get("skor_nugget_tanpa_retrieval") for b in bs])}
    pas = [(b["skor_nugget"], b["skor_nugget_tanpa_retrieval"]) for b in baris if b.get("skor_nugget_tanpa_retrieval") is not None]
    if len(pas) >= 6:
        try:
            from scipy.stats import wilcoxon
            if any(a != c for a, c in pas):
                st = wilcoxon([a for a, _ in pas], [c for _, c in pas]); out["wilcoxon_graf_vs_tanpa_retrieval"] = {"n": len(pas), "p": round(float(st.pvalue), 4)}
        except Exception as e: out["wilcoxon_graf_vs_tanpa_retrieval"] = f"tidak dihitung: {e}"
    out["catatan"] = "Uji mekanik; kunci nugget dari graf (melingkar) kecuali sumber='manual'. Jumlah soal terlalu kecil untuk klaim signifikansi."
    return out
