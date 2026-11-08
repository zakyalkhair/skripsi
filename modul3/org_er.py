"""3.1 ER organisasi deterministik: normalisasi -> alias -> blocking(jenis, wilayah) -> RapidFuzz -> union-find."""
import re
from collections import Counter
from rapidfuzz import fuzz

ALIAS = [  # (pola, jenis_baku, tingkat_bawaan, berwilayah)
    (r"\bbpbd\b|badan penanggulangan bencana daerah", "BPBD", None, True),
    (r"\bbnpb\b|badan nasional penanggulangan bencana", "BNPB", "nasional", False),
    (r"\bbasarnas\b|\bbasarda\b|badan (nasional )?pencarian dan pertolongan|\bkantor sar\b|\bsar\b", "Basarnas", None, False),
    (r"\bpmi\b|palang merah indonesia", "PMI", None, False),
    (r"\bbmkg\b|badan meteorologi", "BMKG", "nasional", False),
    (r"\bpvmbg\b|badan geologi", "PVMBG", "nasional", False),
    (r"\bkemensos\b|kementerian sosial", "Kemensos", "nasional", False),
    (r"\btni[ -]?(ad|al|au)\b", "TNI-matra", "nasional", False),
    (r"\btni\b", "TNI", "nasional", False),
    (r"\bkodam\b", "Kodam", "provinsi", True), (r"\bkorem\b", "Korem", "provinsi", True),
    (r"\bkodim\b", "Kodim", "kab", True), (r"\bkoramil\b", "Koramil", "kec", True),
    (r"\bpolda\b", "Polda", "provinsi", True), (r"\bpolres\b|\bpolresta\b", "Polres", "kab", True),
    (r"\bpolsek\b", "Polsek", "kec", True), (r"\bpolri\b|kepolisian republik", "Polri", "nasional", False),
    (r"\bpemkab\b|pemerintah kabupaten", "Pemkab", "kab", True), (r"\bpemkot\b|pemerintah kota", "Pemkot", "kab", True),
    (r"\bpemprov\b|pemerintah provinsi", "Pemprov", "provinsi", True),
    (r"\bdinsos\b|dinas sosial", "Dinsos", None, True),
    (r"\bdamkar\b|pemadam kebakaran", "Damkar", None, True),
]
JENIS_TINGKAT_NASIONAL = {"BNPB", "BMKG", "PVMBG", "Kemensos", "TNI", "Polri"}


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\bkab\.?\s", "kabupaten ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_org(nama):
    n = norm(nama)
    for pola, jenis, tingkat, berwilayah in ALIAS:
        m = re.search(pola, n)
        if m:
            if jenis == "TNI-matra": jenis = "TNI " + m.group(1).upper()
            sisa = (n[:m.start()] + " " + n[m.end():]).strip()
            sisa = re.sub(r"\b(kabupaten|kota|provinsi|daerah)\b", lambda x: x.group(1), sisa)
            wil = re.sub(r"\s+", " ", sisa).strip() if berwilayah else ""
            t = tingkat
            if jenis in ("BPBD", "Dinsos", "Damkar"):
                t = "provinsi" if re.search(r"\bprovinsi\b", wil) else ("kab" if wil else None)
            if jenis in ("Basarnas", "PMI"):
                t = "nasional" if not re.search(r"\b(kabupaten|kota|provinsi)\b", n) else ("provinsi" if "provinsi" in n else "kab")
            return {"norm": n, "jenis": jenis, "wilayah_nama": wil or None, "tingkat": t, "pemerintah": berwilayah}
    return {"norm": n, "jenis": None, "wilayah_nama": None, "tingkat": None, "pemerintah": False}


class UF:
    def __init__(s, n): s.p = list(range(n))
    def f(s, x):
        while s.p[x] != x: s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b): s.p[s.f(a)] = s.f(b)


def resolusi_organisasi(rows, ambang=90):
    """rows: [{tweet_id, org_id, nama, nama_lembaga}] -> (rows+kanonik, tabel_kanonik, pasangan_log)."""
    info = [parse_org(r.get("nama_lembaga") or r["nama"]) for r in rows]
    blok = {}
    for i, inf in enumerate(info):
        kunci = (inf["jenis"], inf["wilayah_nama"]) if inf["jenis"] else ("_bebas", None)
        blok.setdefault(kunci, []).append(i)
    uf, log = UF(len(rows)), []
    for kunci, idx in blok.items():
        uniq = {}
        for i in idx: uniq.setdefault(info[i]["norm"], []).append(i)
        for a in uniq.values():          # nama identik -> satu klaster
            for i in a[1:]: uf.u(a[0], i)
        ks = list(uniq)
        # pasangan antar nama berbeda: blok berwilayah sudah kunci keras; blok bebas dibandingkan via skor
        for x in range(len(ks)):
            for y in range(x + 1, len(ks)):
                if kunci[0] != "_bebas" and kunci[1] is not None:
                    skor = fuzz.token_sort_ratio(ks[x], ks[y])
                else:
                    skor = fuzz.token_sort_ratio(ks[x], ks[y])
                sama = skor >= ambang and (kunci[0] != "_bebas" or True)
                log.append({"a": ks[x], "b": ks[y], "blok": f"{kunci[0]}|{kunci[1]}", "skor": round(skor, 1), "gabung": sama})
                if sama: uf.u(uniq[ks[x]][0], uniq[ks[y]][0])
    klaster = {}
    for i in range(len(rows)): klaster.setdefault(uf.f(i), []).append(i)
    kanon, tabel = {}, []
    for ids in klaster.values():
        inf0 = info[ids[0]]
        sering = Counter(rows[i].get("nama_lembaga") or rows[i]["nama"] for i in ids).most_common(1)[0][0]
        if inf0["jenis"] and inf0["pemerintah"] and inf0["wilayah_nama"]:
            nama = f'{inf0["jenis"]} {inf0["wilayah_nama"].title()}'
        elif inf0["jenis"] and not inf0["pemerintah"]:
            nama = inf0["jenis"] if inf0["jenis"] in JENIS_TINGKAT_NASIONAL or True else sering
        else:
            nama = sering
        # tabrakan nama kanonik antar klaster (mis. dua klaster 'bebas' bernama sama) digabung
        for i in ids: kanon[i] = nama
        tabel.append({"nama_kanonik": nama, "alias": sorted({rows[i]["nama"] for i in ids}),
                      "wilayah": None, "wilayah_nama": inf0["wilayah_nama"], "tingkat": inf0["tingkat"],
                      "jumlah_sebutan": len(ids)})
    # gabung baris tabel dengan nama kanonik sama
    gab = {}
    for t in tabel:
        g = gab.setdefault(t["nama_kanonik"], dict(t, alias=[], jumlah_sebutan=0))
        g["alias"] = sorted(set(g["alias"]) | set(t["alias"])); g["jumlah_sebutan"] += t["jumlah_sebutan"]
    out = [dict(r, nama_kanonik=kanon[i], jenis_lembaga=info[i]["jenis"]) for i, r in enumerate(rows)]
    return out, list(gab.values()), log
