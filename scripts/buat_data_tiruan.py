"""Buat raw.jsonl TIRUAN berformat twscrape `Tweet.dict()` untuk menguji pipeline tanpa akun X.

Isi sengaja memuat kasus sulit: templat bot BMKG (angka beda), parafrasa berita (angka sama),
salinan persis, tweet pendek, non-Indonesia, retweet, mojibake, entitas HTML, huruf tebal,
balasan, quote tweet, dan tweet yang sama dari beberapa kueri.

    python scripts/buat_data_tiruan.py --workdir demo
    python -m modul1 --workdir demo run-all --skip-fetch
"""

from __future__ import annotations

import argparse
import random
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modul1.crawl import build_queries, load_kejadian  # noqa: E402
from modul1.io_utils import load_config, write_jsonl  # noqa: E402

WILAYAH = {
    "GP07": ["Ende", "Flores", "Manggarai", "Sikka", "Nagekeo"],
    "ER03": ["Flores Timur", "Lewotobi", "Larantuka"],
    "LS01": ["Pasirlangu", "Cisarua", "Bandung Barat"],
    "GP05": ["Palu", "Sigi", "Donggala"],
    "BJ03": ["Batang", "Pati", "Magelang", "Kudus", "Demak"],
    "KH05": ["Palangka Raya", "Kotawaringin Timur", "Pulang Pisau", "Kapuas"],
}
KATA = {
    "gempa": "gempa", "erupsi": "erupsi", "longsor": "longsor", "banjir": "banjir", "karhutla": "karhutla",
}
PEMBUKA = ["", "Astaghfirullah, ", "Guys, ", "Update: ", "Duh, ", "Pagi ini ", "Barusan dapet kabar, ", "Sedih banget, "]
PENUTUP = ["", " Semoga cepat pulih.", " Tetap waspada ya.", " Mohon doanya.", " Stay safe semuanya.",
           " Tolong disebarkan.", " Pemerintah harus gerak cepat!", " Kapan ini berakhir?", " Aamiin."]
PERSONAL = [
    "Ya Allah semoga saudara kita di {w} diberi kekuatan menghadapi {b} ini",
    "Barusan kerasa {b} di {w}, semua keluarga aman alhamdulillah",
    "Posko pengungsian {b} di {w} butuh selimut, air bersih dan popok bayi",
    "Jalan menuju {w} putus akibat {b}, relawan tertahan di perbatasan",
    "Info {b} {w}: warga diminta menjauhi lokasi dan ikuti arahan petugas",
    "Kondisi terkini {b} di {w} masih mencekam, listrik padam sejak semalam",
    "Donasi untuk korban {b} {w} bisa lewat rekening resmi BPBD ya teman-teman",
    "Anak sekolah di {w} diliburkan karena {b}, orang tua diminta waspada",
    "Teman saya di {w} belum bisa dihubungi sejak {b} tadi pagi, mohon doanya",
    "Dapur umum sudah berdiri di {w}, logistik {b} mulai berdatangan",
]
BERITA = [
    ("BNPB: korban meninggal {b} di {w} bertambah menjadi {n} orang, {m} rumah rusak",
     ["Update BNPB, korban meninggal {b} di {w} bertambah jadi {n} orang dan {m} rumah rusak",
      "BNPB: korban meninggal {b} di {w} bertambah menjadi {n} orang, {m} rumah rusak berat",
      "BREAKING - BNPB: korban meninggal {b} di {w} bertambah menjadi {n} orang, {m} rumah rusak"]),
    ("Sebanyak {n} warga {w} mengungsi akibat {b}, BPBD mendirikan {m} tenda darurat",
     ["Sebanyak {n} warga {w} terpaksa mengungsi akibat {b}, BPBD mendirikan {m} tenda darurat",
      "Sebanyak {n} warga di {w} mengungsi akibat {b}; BPBD dirikan {m} tenda darurat"]),
]


def rand_id(rng: random.Random) -> str:
    return str(rng.randint(1_950_000_000_000_000_000, 1_969_999_999_999_999_999))


def tco(rng: random.Random) -> str:
    return "https://t.co/" + "".join(rng.choices(string.ascii_letters + string.digits, k=10))


def bold(s: str) -> str:
    out = []
    for ch in s:
        if "A" <= ch <= "Z":
            out.append(chr(0x1D5D4 + ord(ch) - ord("A")))
        elif "a" <= ch <= "z":
            out.append(chr(0x1D5EE + ord(ch) - ord("a")))
        else:
            out.append(ch)
    return "".join(out)


def mojibake(s: str) -> str:
    return s.encode("utf-8").decode("cp1252", errors="ignore")


def tweet(rng, text, date, lang="in", reply=False, retweet=False, quote=False):
    uid = rng.randint(10**8, 10**10)
    d = {
        "id": int(tid := rand_id(rng)), "id_str": tid, "url": f"https://x.com/u/status/{tid}",
        "date": date.isoformat(),
        "user": {"id": uid, "id_str": str(uid), "username": f"akun{uid % 9999}", "displayname": "Nama Asli",
                 "rawDescription": "bio", "location": "Indonesia", "followersCount": rng.randint(0, 5000)},
        "lang": lang, "rawContent": text, "replyCount": 0, "retweetCount": 0, "likeCount": rng.randint(0, 50),
        "quoteCount": 0, "hashtags": [w[1:] for w in text.split() if w.startswith("#")], "cashtags": [],
        "mentionedUsers": [], "links": [{"url": u, "text": None, "tcourl": u} for u in text.split() if u.startswith("https://t.co/")],
        "retweetedTweet": {"id": 1, "rawContent": text[3:]} if retweet else None,
        "quotedTweet": {"id": 2, "rawContent": "tweet yang dikutip, tidak boleh ikut"} if quote else None,
        "coordinates": {"longitude": 121.6, "latitude": -8.8} if rng.random() < 0.02 else None,
        "inReplyToTweetId": int(rand_id(rng)) if reply else None,
        "inReplyToTweetIdStr": None,
    }
    if reply:
        d["inReplyToTweetIdStr"] = str(d["inReplyToTweetId"])
    return d


def generate(cfg, n_per_event: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    kejadian = [k for k in load_kejadian(cfg.paths.kejadian, True) if k.event_id in WILAYAH]
    queries = build_queries(kejadian, cfg)
    rows = []
    for k in kejadian:
        qs = [q for q in queries if k.event_id in q.event_ids]
        start = datetime.combine(k.tanggal_mulai, datetime.min.time(), tzinfo=timezone.utc)
        span = (k.tanggal_selesai - k.tanggal_mulai).days + 1
        b = KATA[k.jenis]
        ws = WILAYAH[k.event_id]

        def when():
            return start + timedelta(seconds=rng.randint(0, span * 86400 - 1))

        def emit(d, n_queries=1):
            for q in rng.sample(qs, min(n_queries, len(qs))):
                rows.append(d | {"query_id": q.query_id, "event_ids": q.event_ids, "crawled_at": "2026-09-28T00:00:00+00:00"})

        for _ in range(n_per_event):
            r = rng.random()
            w = rng.choice(ws)
            if k.jenis == "gempa" and r < 0.15:  # templat bot BMKG, angka berbeda
                t = (f"#Gempa Mag:{rng.randint(30, 65) / 10}, {when():%d-%b-%y %H:%M:%S} WIB, Lok:{rng.randint(50, 999) / 100} LS, "
                     f"{rng.randint(11800, 12500) / 100} BT ({rng.randint(5, 150)} km BaratLaut {w.upper()}), "
                     f"Kedlmn:{rng.randint(5, 200)} Km #BMKG {tco(rng)}")
                emit(tweet(rng, t, when()))
            elif r < 0.25:  # parafrasa berita, angka sama
                base, vars_ = rng.choice(BERITA)
                n, m = rng.randint(5, 150), rng.randint(10, 900)
                t0 = when()
                for j, tpl in enumerate([base] + rng.sample(vars_, rng.randint(1, len(vars_)))):
                    txt = tpl.format(b=b, w=w, n=n, m=m) + " " + tco(rng)
                    emit(tweet(rng, txt, t0 + timedelta(minutes=17 * j)), n_queries=rng.randint(1, 2))
            elif r < 0.30:  # salinan persis (copas) oleh beberapa akun
                txt = rng.choice(PERSONAL).format(b=b, w=w) + " #PrayFor" + w.replace(" ", "")
                t0 = when()
                for j in range(rng.randint(2, 4)):
                    emit(tweet(rng, txt, t0 + timedelta(minutes=j)))
            elif r < 0.36:  # pendek
                emit(tweet(rng, rng.choice([f"{b} lagi", f"{b}!! 😭😭", "🙏🙏🙏", f"@bnpb_indonesia {b}", "ya Allah"]), when()))
            elif r < 0.41:  # bukan bahasa Indonesia
                emit(tweet(rng, f"Strong {b} reported near {w}, Indonesia. Stay safe everyone", when(), lang=rng.choice(["en", "tl", "und"])))
            elif r < 0.45:  # retweet
                emit(tweet(rng, "RT @bnpb_indonesia: " + rng.choice(PERSONAL).format(b=b, w=w), when(), retweet=True))
            elif r < 0.50:  # mojibake / HTML / huruf tebal
                txt = rng.choice([
                    mojibake(f"{b.capitalize()} di {w} 🌊 warga mengungsi ke masjid"),
                    f"Relawan &amp; TNI evakuasi korban {b} di {w} &gt;&gt; {tco(rng)}",
                    bold(f"Update {b} {w}") + f" hari ini, jalan utama ditutup",
                ])
                emit(tweet(rng, txt, when()))
            else:  # tweet personal (dengan variasi pembuka/penutup)
                txt = rng.choice(PEMBUKA) + rng.choice(PERSONAL).format(b=b, w=w) + rng.choice(PENUTUP)
                extra = rng.choice(["", f" {tco(rng)}", " @bpbd_" + w.split()[0].lower(), f" jam {rng.randint(1, 23)}",
                                    f" hari ke-{rng.randint(1, 14)}", " 😢", f" #{b}{w.replace(' ', '')}"])
                emit(tweet(rng, txt + extra, when(), reply=rng.random() < 0.15, quote=rng.random() < 0.05),
                     n_queries=rng.choice([1, 1, 1, 2]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="demo")
    ap.add_argument("--n-per-event", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    cfg = load_config(None, args.workdir)
    rows = generate(cfg, args.n_per_event, args.seed)
    n = write_jsonl(cfg.paths.raw_jsonl, rows)
    print(f"{n} baris tiruan -> {cfg.paths.raw_jsonl}")


if __name__ == "__main__":
    main()
