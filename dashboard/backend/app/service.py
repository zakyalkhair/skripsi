"""Penyusun respons API dari Graph. Semua hitungan memakai himpunan id (distinct):
kejadian = event_id, laporan = mention_id, tweet = tweet_id, titik = gazetteer_id.

Fakta (dampak, kebutuhan, penanganan) selalu dikelompokkan lewat relasi graf
DisasterEvent <-CONSOLIDATED_INTO- EventMention -AFFECTED/REQUIRES-> ..., HANDLES <- Organization,
tidak lewat kemiripan teks, tanggal, atau kedekatan geografis. Setiap fakta membawa sumbernya
(mention_id, tanggal laporan, tweet_id). Angka dari laporan berbeda tidak pernah dijumlahkan.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from . import adapter as A
from .domain import Filter, Graph


# --------------------------------------------------------------------------- dasar
def _ev_kab(g: Graph, ev: str) -> str | None:
    cache = g.__dict__.setdefault("_kab_cache", {})
    if ev not in cache:
        cache[ev] = A.event_kode_kab(g, ev)
    return cache[ev]


def _in_scope(g: Graph, m: str, kab: str | None, prov: str | None) -> bool:
    ev = g.m_event.get(m)
    k = _ev_kab(g, ev) if ev else None
    if kab and k != kab:
        return False
    if prov and not (k or "").startswith(prov):
        return False
    return True


def _mentions(g: Graph, f: Filter, *, kab: str | None = None, prov: str | None = None) -> list[str]:
    """Laporan yang lolos filter jenis + tanggal_lokal (semantik tingkat laporan) dan cakupan wilayah kejadiannya."""
    out = []
    for mid, m in g.mentions.items():
        if not f.jenis_ok(m["jenis"]) or not f.tanggal_ok(A.to_date(m["tanggal_lokal"])):
            continue
        ev = g.m_event.get(mid)
        if ev is None or ev not in g.events or not _in_scope(g, mid, kab, prov):
            continue
        out.append(mid)
    return out


def _events(g: Graph, f: Filter, kab: str | None = None, prov: str | None = None) -> list[str]:
    """Kejadian yang jenisnya cocok dan interval [start_time, end_time] beririsan dengan filter."""
    out = []
    for eid, e in g.events.items():
        if not f.jenis_ok(e["jenis"]) or not f.tumpang_tindih(A.to_date(e["start_time"]), A.to_date(e["end_time"])):
            continue
        k = _ev_kab(g, eid)
        if (kab and k != kab) or (prov and not (k or "").startswith(prov)):
            continue
        out.append(eid)
    return out


def _ev_mentions(g: Graph, eid: str) -> list[str]:
    return sorted((m for m, e in g.m_event.items() if e == eid and m in g.mentions),
                  key=lambda m: (A.to_date(g.mentions[m]["tanggal_lokal"]), m))


def _periode(g: Graph, eid: str, f: Filter) -> list[str]:
    return [m for m in _ev_mentions(g, eid) if f.tanggal_ok(A.to_date(g.mentions[m]["tanggal_lokal"]))]


def _tweets_of(g: Graph, mids) -> set[str]:
    return {t for m in mids for t in g.m_tweets.get(m, ()) if t in g.tweets}


def _loc_ref(g: Graph, gid: str | None) -> dict | None:
    if not gid:
        return None
    loc = g.locations.get(gid)
    return {"gazetteer_id": gid, "nama": loc["nama"] if loc else gid}


def _sumber(g: Graph, m: str) -> dict:
    return {"mention_id": m, "tanggal_lokal": A.to_date(g.mentions[m]["tanggal_lokal"]).isoformat(),
            "tweet_ids": sorted(t for t in g.m_tweets.get(m, ()) if t in g.tweets)}


def _atribusi(locs: list[str], fokus: str | None) -> str:
    """lokasi_ini | lokasi_lain | lokasi (tanpa fokus) | kejadian (tidak tertaut ke lokasi tertentu)."""
    if not locs:
        return "kejadian"
    if fokus is None:
        return "lokasi"
    return "lokasi_ini" if fokus in locs else "lokasi_lain"


def _tweet_map(g: Graph, ids) -> dict[str, dict]:
    return {t: {"upload": str(g.tweets[t].get("upload")), "text": g.tweets[t].get("text"), "url": g.tweets[t].get("url")}
            for t in sorted(ids) if t in g.tweets}


# --------------------------------------------------------------------------- fakta per kejadian
def _dampak(g: Graph, mids, *, fokus: str | None = None, hanya: str | None = None) -> list[dict]:
    """Dampak dari laporan `mids`. Satu entri per AffectedObject dengan semua laporan sumbernya.
    hanya: 'lokasi_ini' | 'kejadian' untuk menyaring menurut atribusi (dipakai field lama)."""
    acc: dict[str, list[str]] = defaultdict(list)
    for m in mids:
        for aid in g.m_affected.get(m, ()):
            if aid in g.affected and m not in acc[aid]:
                acc[aid].append(m)
    out = []
    for aid, ms in acc.items():
        a, locs = g.affected[aid], sorted(g.ao_loc.get(aid, ()))
        atr = _atribusi(locs, fokus)
        if hanya == "lokasi_ini" and atr != "lokasi_ini":
            continue
        if hanya == "kejadian" and atr != "kejadian":
            continue
        out.append({"id": aid, "kelas": a.get("kelas"), "status": a.get("status"), "jumlah": a.get("jumlah"),
                    "satuan": a.get("satuan"), "lokasi": [_loc_ref(g, l) for l in locs], "atribusi": atr,
                    "event_id": g.m_event.get(ms[0]), "sumber": [_sumber(g, m) for m in ms]})
    out.sort(key=lambda d: (d["sumber"][0]["tanggal_lokal"], d["id"]))
    return out


def _kebutuhan(g: Graph, mids, *, fokus: str | None = None, hanya: str | None = None) -> list[dict]:
    acc: dict[str, list[str]] = defaultdict(list)
    for m in mids:
        for hid in g.m_needs.get(m, ()):
            if hid in g.needs and m not in acc[hid]:
                acc[hid].append(m)
    out = []
    for hid, ms in acc.items():
        n = g.needs[hid]
        lok = n.get("lokasi")
        atr = _atribusi([lok] if lok else [], fokus)
        if hanya == "lokasi_ini" and atr != "lokasi_ini":
            continue
        if hanya == "kejadian" and atr != "kejadian":
            continue
        out.append({"id": hid, "kategori": n.get("kategori"), "item": n.get("item"), "status": n.get("status"),
                    "lokasi": _loc_ref(g, lok), "atribusi": atr, "event_id": g.m_event.get(ms[0]),
                    "sumber": [_sumber(g, m) for m in ms]})
    out.sort(key=lambda d: (d["sumber"][0]["tanggal_lokal"], d["id"]))
    return out


def _org(g: Graph, oid: str) -> dict:
    o, induk = g.orgs[oid], g.org_parent.get(oid)
    return {"id": oid, "nama_kanonik": o.get("nama_kanonik"), "wilayah": o.get("wilayah"), "tingkat": o.get("tingkat"),
            "induk": g.orgs[induk]["nama_kanonik"] if induk in g.orgs else None}


def _penanganan(g: Graph, mids) -> list[dict]:
    """Lembaga yang MENANGANI (HANDLES) laporan `mids`. Lokasi DEPLOYED_TO ditampilkan sebagai keterangan
    lembaga (relasi itu tidak tertaut ke laporan tertentu), bukan sebagai bukti keterkaitan dengan kejadian."""
    mids = set(mids)
    out = []
    for oid in sorted(g.orgs):
        ms = sorted(g.org_handles.get(oid, set()) & mids, key=lambda m: (g.mentions[m]["tanggal_lokal"], m))
        if not ms:
            continue
        dep = [_loc_ref(g, l) for l in sorted(g.org_deployed.get(oid, ())) if l in g.locations]
        peran = ["Menangani laporan"] + [f"Dikerahkan ke {d['nama']}" for d in dep]
        out.append({**_org(g, oid), "peran": peran, "dikerahkan_ke": dep, "sumber": [_sumber(g, m) for m in ms]})
    return out


def _laporan(g: Graph, mids, rel: dict[str, str] | None = None) -> list[dict]:
    return [{**_sumber(g, m), "jenis": g.mentions[m]["jenis"], "event_id": g.m_event.get(m),
             "lokasi": [_loc_ref(g, l) for l in g.m_locs.get(m, ()) if l in g.locations],
             "relasi": (rel or {}).get(m)} for m in mids]


def _rentang(g: Graph, mids) -> tuple[str | None, str | None]:
    ds = sorted(A.to_date(g.mentions[m]["tanggal_lokal"]) for m in mids)
    return (ds[0].isoformat(), ds[-1].isoformat()) if ds else (None, None)


# --------------------------------------------------------------------------- endpoint
def kab_agregat(g: Graph, f: Filter, prov: str | None = None) -> dict:
    per_kab: dict[str, set[str]] = defaultdict(set)
    for eid in _events(g, f, prov=prov):
        k = _ev_kab(g, eid)
        if k:
            per_kab[k].add(eid)
    evset = {e for s in per_kab.values() for e in s}
    mids = [m for m in _mentions(g, f, prov=prov) if g.m_event[m] in evset]
    lap_kab: dict[str, set[str]] = defaultdict(set)
    for m in mids:
        lap_kab[_ev_kab(g, g.m_event[m])].add(m)
    rows = [{"kode_kab": k, "jumlah_kejadian": len(evs), "jumlah_laporan": len(lap_kab.get(k, ())),
             "jumlah_tweet": len(_tweets_of(g, lap_kab.get(k, ())))} for k, evs in sorted(per_kab.items())]
    return {"filter": {**f.as_dict(), "prov": prov}, "kab": rows,
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
            "dampak": _dampak(g, periode), "kebutuhan": _kebutuhan(g, periode), "lembaga": _penanganan(g, periode),
            "laporan": _laporan(g, periode)}


def kab_kejadian(g: Graph, kode: str, f: Filter) -> dict:
    cards = [_kartu(g, eid, f) for eid in _events(g, f, kab=kode)]
    cards.sort(key=lambda c: (c["end_time"], c["event_id"]), reverse=True)
    tw = {t for c in cards for lap in c["laporan"] for t in lap["tweet_ids"]}
    return {"kode_kab": kode, "filter": f.as_dict(), "kejadian": cards, "tweets": _tweet_map(g, tw)}


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
    """Ringkasan lokasi berpusat-kejadian: laporan yang MENYEBUT (MENTIONS) lokasi atau menjadikannya
    tujuan EVAKUASI, dikelompokkan per kejadian. Fakta setiap kejadian diambil dari seluruh laporannya pada
    rentang terpilih dan diberi atribusi relatif terhadap lokasi ini."""
    loc = g.locations[gid]
    semua = _mentions(g, f)
    mids = [m for m in semua if gid in g.m_locs.get(m, ())]
    evac_in = [m for m in semua if gid in g.m_evac.get(m, ())]
    rel = {m: "evakuasi" for m in evac_in}
    rel.update({m: "menyebut" for m in mids})
    by_ev: dict[str, list[str]] = defaultdict(list)
    for m in sorted(rel, key=lambda m: (g.mentions[m]["tanggal_lokal"], m)):
        by_ev[g.m_event[m]].append(m)
    kejadian, tw_ids = [], set()
    for eid, ms in by_ev.items():
        e = g.events[eid]
        periode = _periode(g, eid, f)
        lap = _laporan(g, ms, rel)
        tw_ids |= _tweets_of(g, periode) | _tweets_of(g, ms)
        kejadian.append({
            "event_id": eid, "nama": e["nama"], "jenis": e["jenis"], "status": e["status"],
            "start_time": A.to_date(e["start_time"]).isoformat(), "end_time": A.to_date(e["end_time"]).isoformat(),
            "kode_kab": _ev_kab(g, eid),
            "laporan": [{"mention_id": x["mention_id"], "tanggal_lokal": x["tanggal_lokal"], "jenis": x["jenis"],
                         "tweet_ids": x["tweet_ids"], "relasi": x["relasi"]} for x in lap],
            "jumlah_laporan_kejadian": len(periode),
            "dampak": _dampak(g, periode, fokus=gid), "kebutuhan": _kebutuhan(g, periode, fokus=gid),
            "penanganan": _penanganan(g, periode),
            "evakuasi": [{**_sumber(g, m), "asal": [_loc_ref(g, l) for l in g.m_locs.get(m, ()) if l != gid],
                          "tujuan": [_loc_ref(g, l) for l in sorted(g.m_evac.get(m, ()))]}
                         for m in periode if g.m_evac.get(m) and (gid in g.m_evac[m] or gid in g.m_locs.get(m, ()))],
        })
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
    dikerahkan = [{**_org(g, oid), "peran": ["Dikerahkan ke lokasi ini"]} for oid in sorted(g.orgs)
                  if gid in g.org_deployed.get(oid, set())]
    return {
        "lokasi": {"gazetteer_id": gid, "nama": loc["nama"], "tingkat": A.tingkat(g, gid),
                   "admin_path": loc.get("admin_path"), "kode_kab_lokasi": A.kab_lokasi(g, gid),
                   "latitude": lat_lon[0] if lat_lon else None, "longitude": lat_lon[1] if lat_lon else None},
        "filter": f.as_dict(), "jumlah_laporan": len(mids), "jumlah_tweet": len(tweets),
        "tanggal_awal": awal, "tanggal_akhir": akhir,
        "jenis": sorted({g.mentions[m]["jenis"] for m in mids}), "kejadian": kejadian, "tweets": tweets,
        "tweet_map": _tweet_map(g, tw_ids),
        "lembaga_dikerahkan": dikerahkan,
        # field lama (dipertahankan untuk kompatibilitas): fakta dari laporan yang menyebut lokasi ini
        "dampak_lokasi": _dampak(g, mids, fokus=gid, hanya="lokasi_ini"),
        "dampak_tanpa_lokasi": _dampak(g, mids, fokus=gid, hanya="kejadian"),
        "kebutuhan_lokasi": _kebutuhan(g, mids, fokus=gid, hanya="lokasi_ini"),
        "kebutuhan_tanpa_lokasi": _kebutuhan(g, mids, fokus=gid, hanya="kejadian"),
    }


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def histogram(g: Graph, f: Filter, kab: str | None, domain: tuple[date, date] | None = None, *,
              prov: str | None = None, lokasi: str | None = None) -> dict:
    """Laporan (distinct mention_id) per minggu (Senin) berdasarkan tanggal_lokal, pada cakupan:
    nasional | provinsi (prov) | kab/kota (kab = kode_kab laporan) | lokasi (laporan yang MENYEBUT lokasi).
    Filter tanggal tidak diterapkan agar sumbu waktu tetap utuh; rentang pilihan ditandai di frontend."""
    fj = Filter(jenis=f.jenis)
    mids = [m for m in _mentions(g, fj)
            if (kab is None or g.mentions[m]["kode_kab"] == kab)
            and (prov is None or str(g.mentions[m]["kode_kab"]).startswith(prov))
            and (lokasi is None or lokasi in g.m_locs.get(m, ()))]
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
    cakupan = "lokasi" if lokasi else "kab" if kab else "prov" if prov else "nasional"
    return {"filter": {"jenis": fj.as_dict()["jenis"], "kab": kab, "prov": prov, "lokasi": lokasi},
            "cakupan": cakupan, "satuan": "laporan kejadian (EventMention) unik", "minggu": rows,
            "rentang": {"awal": lo.isoformat() if lo else None, "akhir": hi.isoformat() if hi else None}}


# --------------------------------------------------------------------------- ekspor
def ekspor(g: Graph, f: Filter, *, prov: str | None = None, kab: str | None = None, lokasi: str | None = None) -> dict[str, list[dict]]:
    """Tabel ternormalisasi untuk ekspor CSV. Cakupan wilayah: kejadian di prov/kab, atau kejadian yang
    laporannya menyebut lokasi. Fakta per kejadian dari laporan pada rentang terpilih (satu baris per fakta,
    per laporan sumber; tidak ada penjumlahan)."""
    if lokasi:
        rel = [m for m in _mentions(g, f) if lokasi in g.m_locs.get(m, ()) or lokasi in g.m_evac.get(m, ())]
        evs = sorted({g.m_event[m] for m in rel})
    else:
        evs = sorted(_events(g, f, kab=kab, prov=prov))
    kejadian, laporan, dampak, kebutuhan, penanganan, tw = [], [], [], [], [], set()
    for eid in evs:
        k = _kartu(g, eid, f)
        kejadian.append({"event_id": eid, "nama": k["nama"], "jenis": k["jenis"], "kode_kab": k["kode_kab"],
                         "start_time": k["start_time"], "end_time": k["end_time"], "status_ambang": k["status"],
                         "jumlah_laporan_periode": k["jumlah_laporan_periode"], "jumlah_tweet_periode": k["jumlah_tweet_periode"],
                         "jumlah_laporan_total": k["jumlah_laporan_total"], "lokasi_ids": ";".join(k["lokasi_ids"])})
        for lap in k["laporan"]:
            tw |= set(lap["tweet_ids"])
            laporan.append({"mention_id": lap["mention_id"], "event_id": eid, "jenis": lap["jenis"],
                            "kode_kab": g.mentions[lap["mention_id"]]["kode_kab"], "tanggal_lokal": lap["tanggal_lokal"],
                            "lokasi_ids": ";".join(x["gazetteer_id"] for x in lap["lokasi"]), "tweet_ids": ";".join(lap["tweet_ids"])})
        for d in k["dampak"]:
            for s in d["sumber"]:
                dampak.append({"affected_id": d["id"], "event_id": eid, "mention_id": s["mention_id"], "tanggal_laporan": s["tanggal_lokal"],
                               "kelas": d["kelas"], "status": d["status"], "jumlah": d["jumlah"], "satuan": d["satuan"],
                               "tingkat_atribusi": "lokasi" if d["lokasi"] else "kejadian",
                               "lokasi_ids": ";".join(x["gazetteer_id"] for x in d["lokasi"]), "tweet_ids": ";".join(s["tweet_ids"])})
        for n in k["kebutuhan"]:
            for s in n["sumber"]:
                kebutuhan.append({"need_id": n["id"], "event_id": eid, "mention_id": s["mention_id"], "tanggal_laporan": s["tanggal_lokal"],
                                  "kategori": n["kategori"], "item": n["item"], "status": n["status"],
                                  "tingkat_atribusi": "lokasi" if n["lokasi"] else "kejadian",
                                  "lokasi_id": n["lokasi"]["gazetteer_id"] if n["lokasi"] else None, "tweet_ids": ";".join(s["tweet_ids"])})
        for o in k["lembaga"]:
            for s in o["sumber"]:
                penanganan.append({"org_id": o["id"], "nama_kanonik": o["nama_kanonik"], "tingkat": o["tingkat"], "wilayah": o["wilayah"],
                                   "induk": o["induk"], "peran": "menangani_laporan", "event_id": eid, "mention_id": s["mention_id"],
                                   "tanggal_laporan": s["tanggal_lokal"], "dikerahkan_ke": ";".join(x["gazetteer_id"] for x in o["dikerahkan_ke"]),
                                   "tweet_ids": ";".join(s["tweet_ids"])})
    tweets = [{"tweet_id": t, **v} for t, v in _tweet_map(g, tw).items()]
    return {"kejadian": kejadian, "laporan": laporan, "dampak": dampak, "kebutuhan": kebutuhan,
            "penanganan": penanganan, "tweet": tweets}
