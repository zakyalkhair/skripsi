"""4.1 Penguncian korpus: manifest + hash + pemeriksaan otomatis. Gagal -> eksperimen tidak boleh jalan."""
import hashlib, json, os


def kunci(repo, keluar, sumber_jsonl=None):
    tw = repo.tweets()
    baris, masalah = [], []
    for t in tw:
        txt = t.get("text_raw") or ""
        if not txt.strip(): masalah.append(f"teks kosong: {t['tweet_id']}")
        baris.append({"tweet_id": t["tweet_id"], "created_at": t["created_at"], "text_raw": txt, "hash": hashlib.sha256(txt.encode()).hexdigest()[:16]})
    ids = [b["tweet_id"] for b in baris]
    if len(ids) != len(set(ids)): masalah.append("tweet_id ganda")
    n_graf = repo.jumlah_node().get("Tweet")
    if n_graf is not None and n_graf != len(baris): masalah.append(f"jumlah baris {len(baris)} != Tweet di graf {n_graf}")
    if sumber_jsonl and os.path.exists(sumber_jsonl):       # silang dengan masukan 2.1/2.3
        src = {}
        for l in open(sumber_jsonl, encoding="utf-8"):
            r = json.loads(l); src[r["tweet_id"]] = r.get("text_raw") or ""
        if set(src) != set(ids): masalah.append(f"himpunan tweet_id beda dengan sumber: -{len(set(src)-set(ids))} +{len(set(ids)-set(src))}")
        for b in baris:
            if b["tweet_id"] in src and hashlib.sha256(src[b["tweet_id"]].encode()).hexdigest()[:16] != b["hash"]: masalah.append(f"hash teks beda: {b['tweet_id']}")
    h = hashlib.sha256("".join(b["tweet_id"] + b["hash"] for b in baris).encode()).hexdigest()
    os.makedirs(keluar, exist_ok=True)
    with open(os.path.join(keluar, "korpus_eval.jsonl"), "w", encoding="utf-8") as f:
        for b in baris: f.write(json.dumps(b, ensure_ascii=False) + "\n")
    man = {"n_tweet": len(baris), "hash_korpus": h, "lolos": not masalah, "masalah": masalah}
    json.dump(man, open(os.path.join(keluar, "korpus_manifest.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return man
