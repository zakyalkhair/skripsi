"""Diagnosis twscrape: status akun + uji kueri dari yang paling sederhana ke kueri penuh.

    python scripts/cek_twscrape.py

Tidak menulis ke data/raw. Nilai cookie tidak dicetak.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from modul1.crawl import build_queries, load_accounts_from_env, load_kejadian  # noqa: E402
from modul1.io_utils import load_config  # noqa: E402


async def main() -> None:
    load_dotenv()
    cfg = load_config()
    if cfg.crawl.use_system_certs:
        import truststore

        truststore.inject_into_ssl()

    from twscrape import API, set_log_level

    set_log_level("INFO")
    api = API(str(cfg.paths.twscrape_db))
    for acc in load_accounts_from_env():
        if acc["cookies"]:
            await api.pool.add_account_cookies(acc["username"], acc["cookies"])

    print("\n=== Status akun ===")
    for a in await api.pool.accounts_info():
        print(f"{a['username']}: active={a['active']} logged_in={a['logged_in']} "
              f"total_req={a['total_req']} error={a['error_msg']}")

    full = build_queries(load_kejadian(cfg.paths.kejadian, True, ["GP07"]), cfg)[0].text
    rng = "since:2026-08-14 until:2026-08-30"
    t0 = int(datetime(2026, 8, 14, tzinfo=timezone.utc).timestamp())
    t1 = int(datetime(2026, 8, 30, tzinfo=timezone.utc).timestamp())
    epoch = f"since_time:{t0} until_time:{t1}"  # rentang sama, format detik-epoch
    tests = [  # (kueri, product) — product "Latest" = mode yang dipakai crawl
        ("gempa", "Latest"),
        ("gempa lang:id", "Latest"),
        (f"gempa {rng}", "Latest"),
        (f"gempa Flores {rng}", "Latest"),
        (f"gempa lang:id {rng}", "Latest"),
        (f"gempa {epoch}", "Latest"),
        ("gempa lang:id", "Top"),
        (f"gempa Flores {rng}", "Top"),
        (full, "Latest"),
    ]
    print("\n=== Uji kueri (maks 20 tweet) ===")
    results = []
    for q, product in tests:
        dates, contoh = [], ""
        async for tw in api.search(q, limit=20, kv={"product": product}):
            dates.append(tw.date)
            contoh = contoh or tw.rawContent[:70].replace("\n", " ")
        results.append((len(dates), q))
        rentang = f"{min(dates):%Y-%m-%d} s.d. {max(dates):%Y-%m-%d}" if dates else "-"
        print(f"\n[{len(dates):>2} tweet | {product:<6}] {q}\n    tanggal: {rentang}\n    contoh : {contoh or '-'}")

    if results[0][0] == 0:
        print("\n=== Respons mentah kueri 'gempa' (halaman pertama) ===")
        async for rep in api.search_raw("gempa", limit=20):
            print("HTTP", rep.status_code)
            print(json.dumps(rep.json(), ensure_ascii=False)[:1500])
            break
        else:
            print("Tidak ada respons (akun tidak tersedia / permintaan ditolak) — lihat log DEBUG di atas.")


if __name__ == "__main__":
    asyncio.run(main())
