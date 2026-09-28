"""Diagnosis twscrape: status akun + uji kueri dari yang paling sederhana ke kueri penuh.

    python scripts/cek_twscrape.py

Tidak menulis ke data/raw. Nilai cookie tidak dicetak.
"""

from __future__ import annotations

import asyncio
import json
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

    set_log_level("DEBUG")
    api = API(str(cfg.paths.twscrape_db))
    for acc in load_accounts_from_env():
        if acc["cookies"]:
            await api.pool.add_account_cookies(acc["username"], acc["cookies"])

    print("\n=== Status akun ===")
    for a in await api.pool.accounts_info():
        print(f"{a['username']}: active={a['active']} logged_in={a['logged_in']} "
              f"total_req={a['total_req']} error={a['error_msg']}")

    full = build_queries(load_kejadian(cfg.paths.kejadian, True, ["GP07"]), cfg)[0].text
    tests = [
        "gempa",
        "gempa lang:id",
        "gempa Flores lang:id",
        "gempa Flores lang:id since:2026-08-14 until:2026-08-30",
        full,
    ]
    print("\n=== Uji kueri (maks 20 tweet) ===")
    results = []
    for q in tests:
        n, contoh = 0, ""
        async for tw in api.search(q, limit=20):
            n += 1
            contoh = contoh or f"{tw.date:%Y-%m-%d} {tw.rawContent[:80]!r}"
        results.append((n, q))
        print(f"\n[{n:>2} tweet] {q}\n          contoh: {contoh or '-'}")

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
