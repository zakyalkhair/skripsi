"""Zona waktu & tanggal lokal (2.4). Aturan: zona tertulis di teks > zona provinsi kab > WIB."""
import re
from datetime import datetime, timedelta, date, timezone

OFFSET = {"WIB": 7, "WITA": 8, "WIT": 9}
_WITA = {"51", "52", "53", "63", "64", "65", "71", "72", "73", "74", "75", "76"}
_WIT = {"81", "82", "91", "92", "93", "94", "95", "96"}


def zona_provinsi(kode_prov):
    if kode_prov in _WITA: return "WITA"
    if kode_prov in _WIT: return "WIT"
    return "WIB"


def zona_dari_teks(teks):
    m = re.search(r"\b(WIB|WITA|WIT)\b", teks or "", re.I)
    return m.group(1).upper() if m else None


def waktu_lokal(created_at_utc, zona):
    """created_at (str/datetime UTC) -> datetime lokal naive."""
    if isinstance(created_at_utc, str):
        created_at_utc = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
    if created_at_utc.tzinfo is None:
        created_at_utc = created_at_utc.replace(tzinfo=timezone.utc)
    return (created_at_utc.astimezone(timezone.utc) + timedelta(hours=OFFSET[zona])).replace(tzinfo=None)
