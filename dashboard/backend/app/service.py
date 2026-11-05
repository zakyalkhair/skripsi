"""Penyusun respons API dari Graph. Semua hitungan memakai himpunan id (distinct):
kejadian = event_id, laporan = mention_id, tweet = tweet_id, titik = gazetteer_id."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from . import adapter as A
from .domain import Filter, Graph


# --------------------------------------------------------------------------- dasar
def _mentions(g: Graph, f: Filter, *, kab: str | None = None) -> list[str]:
    """Laporan yang lolos filter jenis + tanggal_lokal (semantik tingkat laporan)."""
    out = []
    for mid, m in g.mentions.items():
        if not f.jenis_ok(m["jenis"]) or not f.tanggal_ok(A.to_date(m["tanggal_lokal"])):
            continue
        ev = g.m_event.get(mid)
        if ev is None or ev not in g.events:
            continue
        if kab and _ev_kab(g, ev) != kab:
            continue
        out.append(mid)
    return out


def _ev_kab(g: Graph, ev: str) -> str | None:
    cache = g.__dict__.setdefault("_kab_cache", {})
    if ev not in cache:
        cache[ev] = A.event_kode_kab(g, ev)
    return cache[ev]


def _events(g: Graph, f: Filter, kab: str | None = None) -> list[str]:
    """Kejadian yang jenisnya cocok dan interval [start_time, end_time] beririsan dengan filter."""
    out = []
    for eid, e in g.events.items():
        if not f.jenis_ok(e["jenis"]):
            continue
        if not f.tumpang_tindih(A.to_date(e["start_time"]), A.to_date(e["end_time"])):
            continue
        if kab and _ev_kab(g, eid) != kab:
            continue
        out.append(eid)
    return out


def _ev_mentions(g: Graph, eid: str) -> list[str]:
    return [m for m, e in g.m_event.items() if e == eid and m in g.mentions]


def _tweets_of(g: Graph, mids) -> set[str]:
    return {t for m in mids for t in g.m_tweets.get(m, ()) if t in g.tweets}


def _loc_ref(g: Graph, gid: str | None) -> dict | None:
    if not gid:
        return None
    loc = g.locations.get(gid)
    return {"gazetteer_id": gid, "nama": loc["nama"] if loc else gid}


def _dampak(g: Graph, mids, *, hanya_lokasi: str | None = None, tanpa_lokasi: bool = False) -> list[dict]:
    seen, out = set(), []
    for m in mids:
        for aid in sorted(g.m_affected.get(m, ())):
            if aid in seen or aid not in g.affected:
                continue
            locs = sorted(g.ao_loc.get(aid, ()))
            if hanya_lokasi is not None and hanya_lokasi not in locs:
                continue
            if tanpa_lokasi and locs:
                continue
            seen.add(aid)
            a = g.affected[aid]
            out.append({"id": aid, "kelas": a.get("kelas"), "status": a.get("status"), "jumlah": a.get("jumlah"),
                        "satuan": a.get("satuan"), "lokasi": [_loc_ref(g, l) for l in locs],
                        "event_id": g.m_event.get(m)})
    return out


def _kebutuhan(g: Graph, mids, *, lokasi: str | None = None, tanpa_lokasi: bool = False) -> list[dict]:
    seen, out = set(), []
    for m in mids:
        for hid in sorted(g.m_needs.get(m, ())):
            if hid in seen or hid not in g.needs:
                continue
            n = g.needs[hid]
            if lokasi is not None and n.get("lokasi") != lokasi:
                continue
            if tanpa_lokasi and n.get("lokasi"):
                continue
            seen.add(hid)
            out.append({"id": hid, "kategori": n.get("kategori"), "item": n.get("item"), "status": n.get("status"),
                        "lokasi": _loc_ref(g, n.get("lokasi")), "event_id": g.m_event.get(m)})
    return out


def _lembaga(g: Graph, mids, *, lokasi: str | None = None) -> list[dict]:
    mids = set(mids)
    out = []
    for oid, o in sorted(g.orgs.items()):
        peran = []
        if g.org_handles.get(oid, set()) & mids:
            peran.append("Menangani laporan")
        dep = sorted(g.org_deployed.get(oid, ()))
        if lokasi is not None:
            if lokasi in dep:
                peran.append("Dikerahkan ke lokasi ini")
            if not peran:
                continue
        else:
            if not peran:
                continue
            dep_rel = [d for d in dep if d in {l for m in mids for l in g.m_locs.get(m, ())}]
            peran += [f"Dikerahkan ke {g.locations[d]['nama']}" for d in dep_rel if d in g.locations]
        induk = g.org_parent.get(oid)
        out.append({"id": oid, "nama_kanonik": o.get("nama_kanonik"), "wilayah": o.get("wilayah"),
                    "tingkat": o.get("tingkat"), "peran": peran,
                    "induk": g.orgs[induk]["nama_kanonik"] if induk in g.orgs else None})
    return out


def _rentang(g: Graph, mids) -> tuple[str | None, str | None]:
    ds = sorted(A.to_date(g.mentions[m]["tanggal_lokal"]) for m in mids)
    return (ds[0].isoformat(), ds[-1].isoformat()) if ds else (None, None)


# --------------------------------------------------------------------------- endpoint
def kab_agregat(g: Graph, f: Filter) -> dict:
    per_kab: dict[str, set[str]] = defaultdict(set)
    for eid in _events(g, f):
        k = _ev_kab(g, eid)
        if k:
            per_kab[k].add(eid)
    evset = {e for s in per_kab.values() for e in s}
    mids = [m for m in _mentions(g, f) if g.m_event[m] in evset]
    lap_kab: dict[str, set[str]] = defaultdict(set)
    for m in mids:
        lap_kab[_ev_kab(g, g.m_event[m])].add(m)
    rows = [{"kode_kab": k, "jumlah_kejadian": len(evs), "jumlah_laporan": len(lap_kab.get(k, ())),
             "jumlah_tweet": len(_tweets_of(g, lap_kab.get(k, ())))} for k, evs in sorted(per_kab.items())]
    return {"filter": f.as_dict(), "kab": rows,
            "ringkasan": {"jumlah_kejadian": sum(r["jumlah_kejadian"] for r in rows),
                          "jumlah_laporan": len(set(mids)), "jumlah_tweet": len(_tweets_of(g, mids)),
                          "jumlah_kab": len(rows)}}


def _kartu(g: Graph, eid: str, f: Filter) -> dict:
    e = g.events[eid]
    semua = _ev_mentions(g, eid)
    periode = [m for m in semua if f.tanggal_ok(A.to_date(g.mentions[m]["tanggal_lokal"]))]
    titik = sorted({l for m in periode for l in g.m_locs.get(m, ()) if A.is_titik(g, l)})
    return {"event_id": eid, "nama": e["nama"], "jenis": e["jenis"], "status": e["status"],
            "start_time": A.to_date(e["start_time"]).isoformat(), "end_time": A.to_date(e["end_time"]).isoformat(),
            "kode_kab": _ev_kab(g, eid),
            "jumlah_laporan_periode": len(periode), "jumlah_tweet_periode": len(_tweets_of(g, periode)),
            "jumlah_laporan_total": len(semua), "jumlah_tweet_total": len(_tweets_of(g, semua)),
            "lokasi_ids": titik, "lokasi": [_loc_ref(g, l) for l in titik],
            "dampak": _dampak(g, periode), "kebutuhan": _kebutuhan(g, periode), "lembaga": _lembaga(g, periode)}


def kab_kejadian(g: Graph, kode: str, f: Filter) -> dict:
    cards = [_kartu(g, eid, f) for eid in _events(g, f, kab=kode)]
    cards.sort(key=lambda c: (c["end_time"], c["event_id"]), reverse=True)
    return {"kode_kab": kode, "filter": f.as_dict(), "kejadian": cards}


def kab_titik(g: Graph, kode: str, f: Filter) -> dict:
    evs = set(_events(g, f, kab=kode))
    mids = [m for m in _mentions(g, f, kab=kode) if g.m_event[m] in evs]
    per: dict[str, list[str]] = defaultdict(list)
    tanpa = 0
    for m in mids:
        pts = [l for l in g.m_locs.get(m, ()) if A.is_titik(g, l)]
        tanpa += not pts
        for l in pts:
            per[l].append(m)
    titik = []
    for gid, ms in sorted(per.items()):
        loc = g.locations[gid]
        lat, lon = A.koordinat(loc)
        awal, akhir = _rentang(g, ms)
        kab_l = A.kab_lokasi(g, gid)
        titik.append({"gazetteer_id": gid, "nama": loc["nama"], "tingkat": A.tingkat(g, gid),
                      "admin_path": loc.get("admin_path"), "latitude": lat, "longitude": lon,
                      "kode_kab_lokasi": kab_l, "di_luar_kab": kab_l is not None and kab_l != kode,
                      "jenis": sorted({g.mentions[m]["jenis"] for m in ms}), "jumlah_laporan": len(set(ms)),
                      "event_ids": sorted({g.m_event[m] for m in ms}), "tanggal_awal": awal, "tanggal_akhir": akhir})
    return {"kode_kab": kode, "filter": f.as_dict(), "titik": titik, "laporan_tanpa_titik": tanpa}


def titik_ringkasan(g: Graph, gid: str, f: Filter) -> dict:
    loc = g.locations[gid]
    mids = [m for m in _mentions(g, f) if gid in g.m_locs.get(m, ())]
    evac_in = [m for m in _mentions(g, f) if gid in g.m_evac.get(m, ())]
    by_ev: dict[str, list[str]] = defaultdict(list)
    for m in mids:
        by_ev[g.m_event[m]].append(m)
    kejadian = []
    for eid, ms in by_ev.items():
        e = g.events[eid]
        ms.sort(key=lambda m: (g.mentions[m]["tanggal_lokal"], m))
        kejadian.append({"event_id": eid, "nama": e["nama"], "jenis": e["jenis"], "status": e["status"],
                         "start_time": A.to_date(e["start_time"]).isoformat(),
                         "end_time": A.to_date(e["end_time"]).isoformat(), "kode_kab": _ev_kab(g, eid),
                         "laporan": [{"mention_id": m, "tanggal_lokal": A.to_date(g.mentions[m]["tanggal_lokal"]).isoformat(),
                                      "jenis": g.mentions[m]["jenis"], "tweet_ids": sorted(g.m_tweets.get(m, ()))}
                                     for m in ms]})
    kejadian.sort(key=lambda k: (k["laporan"][-1]["tanggal_lokal"], k["event_id"]), reverse=True)
    tw: dict[str, set[str]] = defaultdict(set)
    for m in mids:
        for t in g.m_tweets.get(m, ()):
            if t in g.tweets:
                tw[t].add(m)
    tweets = [{"tweet_id": t, "upload": str(g.tweets[t].get("upload")), "text": g.tweets[t].get("text"),
               "url": g.tweets[t].get("url"), "mention_ids": sorted(ms)} for t, ms in tw.items()]
    tweets.sort(key=lambda t: t["upload"], reverse=True)
    lat_lon = A.koordinat(loc)
    awal, akhir = _rentang(g, mids)
    return {
        "lokasi": {"gazetteer_id": gid, "nama": loc["nama"], "tingkat": A.tingkat(g, gid),
                   "admin_path": loc.get("admin_path"), "kode_kab_lokasi": A.kab_lokasi(g, gid),
                   "latitude": lat_lon[0] if lat_lon else None, "longitude": lat_lon[1] if lat_lon else None},
        "filter": f.as_dict(), "jumlah_laporan": len(mids), "jumlah_tweet": len(tweets),
        "tanggal_awal": awal, "tanggal_akhir": akhir,
        "jenis": sorted({g.mentions[m]["jenis"] for m in mids}), "kejadian": kejadian, "tweets": tweets,
        "dampak_lokasi": _dampak(g, mids, hanya_lokasi=gid),
        "dampak_tanpa_lokasi": _dampak(g, mids, tanpa_lokasi=True),
        "kebutuhan_lokasi": _kebutuhan(g, mids, lokasi=gid),
        "kebutuhan_tanpa_lokasi": _kebutuhan(g, mids, tanpa_lokasi=True),
        "lembaga": _lembaga(g, mids, lokasi=gid),
        "evakuasi_ke_sini": [{"mention_id": m, "event_id": g.m_event[m],
                              "asal": [_loc_ref(g, l) for l in g.m_locs.get(m, ()) if l != gid]} for m in evac_in],
        "evakuasi_dari_sini": [{"mention_id": m, "tujuan": [_loc_ref(g, l) for l in sorted(g.m_evac[m])]}
                               for m in mids if g.m_evac.get(m)],
    }


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def histogram(g: Graph, f: Filter, kab: str | None, domain: tuple[date, date] | None = None) -> dict:
    """Laporan (distinct mention_id) per minggu (Senin) berdasarkan tanggal_lokal. Filter tanggal
    tidak diterapkan agar sumbu waktu tetap utuh; rentang pilihan ditandai di frontend."""
    fj = Filter(jenis=f.jenis)
    mids = [m for m in _mentions(g, fj) if kab is None or g.mentions[m]["kode_kab"] == kab]
    all_d = [A.to_date(m["tanggal_lokal"]) for m in g.mentions.values()]
    lo, hi = domain or ((min(all_d), max(all_d)) if all_d else (None, None))
    weeks: dict[date, dict[str, set[str]]] = {}
    if lo:
        w = monday(lo)
        while w <= monday(hi):
            weeks[w] = defaultdict(set)
            w += timedelta(days=7)
    for m in mids:
        d = A.to_date(g.mentions[m]["tanggal_lokal"])
        weeks.setdefault(monday(d), defaultdict(set))[g.mentions[m]["jenis"]].add(m)
    rows = [{"mulai": w.isoformat(), "total": sum(len(s) for s in per.values()),
             "per_jenis": {j: len(s) for j, s in sorted(per.items())}} for w, per in sorted(weeks.items())]
    return {"filter": {"jenis": fj.as_dict()["jenis"], "kab": kab}, "minggu": rows,
            "rentang": {"awal": lo.isoformat() if lo else None, "akhir": hi.isoformat() if hi else None}}
