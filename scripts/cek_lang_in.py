"""Uji operator bahasa X untuk kueri "tsunami" (temuan 7 Okt 2026).

Masalah: kueri "tsunami" tanpa filter bahasa diisi tweet asing (2026: hanya 2,2% berbahasa Indonesia,
38 dari 40 kueri mentok 2.000; 2025: 0 tweet Indonesia setelah saring). Kode bahasa Indonesia di X
adalah "in" (kolom lang di data kita), bukan "id" — uji 28 Sep hanya mencoba `lang:id`.

    python scripts/cek_lang_in.py

Mencetak, per varian kueri, jumlah tweet & proporsi lang == "in" (maks 100 tweet/varian). Tidak menulis data.
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

from modul1.crawl import make_twscrape_api, use_system_certs  # noqa: E402
from modul1.io_utils import load_config, setup_logger  # noqa: E402

RNG = "since:2026-08-14 until:2026-08-21"
VARIAN = [
    f"tsunami -filter:retweets {RNG}",
    f"tsunami lang:in -filter:retweets {RNG}",
    f"tsunami lang:id -filter:retweets {RNG}",
    f"gempa lang:in -filter:retweets {RNG}",
]


async def main() -> None:
    load_dotenv()
    cfg = load_config()
    log = setup_logger("cek_lang", cfg.paths.logs_dir)
    if cfg.crawl.use_system_certs:
        use_system_certs(log)
    api = await make_twscrape_api(cfg, log)
    for q in VARIAN:
        langs = Counter()
        async for tw in api.search(q, limit=100):
            langs[tw.lang] += 1
        n = sum(langs.values())
        print(f"[{n:>3} tweet | in={langs.get('in', 0) / n if n else 0:.0%}] {q}  {dict(langs.most_common(4))}")


if __name__ == "__main__":
    asyncio.run(main())
