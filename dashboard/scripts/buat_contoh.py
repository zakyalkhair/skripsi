"""Tulis data contoh ILUSTRATIF (bukan data bencana nyata) -> dashboard/data/contoh/*.json.

Teks tweet, tanggal, angka dampak, dan kejadian dikarang untuk menguji struktur ontologi dan
kasus tepi dashboard. Koordinat adalah posisi perkiraan tempat nyata dan sudah dicek masuk ke
poligon kab/kota Kemendagri yang benar (lihat README). Jalankan ulang setelah mengubah isi.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "contoh"
P = "Jawa Timur"

KAB = {"3507": "Kab. Malang", "3508": "Kab. Lumajang", "3509": "Kab. Jember", "3513": "Kab. Probolinggo",
       "3514": "Kab. Pasuruan", "3515": "Kab. Sidoarjo", "3579": "Kota Batu"}
# gazetteer_id: (nama, tingkat, kode_kab, admin_path tambahan, lat, lon)
LOK = {
    "contoh:gunung/semeru": ("Gunung Semeru", "gunung", "3508", "Kec. Pronojiwo", -8.1077, 112.9224),
    "contoh:desa/supiturang": ("Desa Supiturang", "desa", "3508", "Kec. Pronojiwo", -8.1700, 112.9590),
    "contoh:desa/sumberwuluh": ("Desa Sumberwuluh", "desa", "3508", "Kec. Candipuro", -8.1530, 113.0060),
    "contoh:kec/candipuro": ("Kec. Candipuro", "kecamatan", "3508", "", -8.1650, 113.0450),
    "contoh:jembatan/gladak-perak": ("Jembatan Gladak Perak", "jembatan", "3508", "Kec. Candipuro", -8.2180, 112.9880),
    "contoh:kec/ampelgading": ("Kec. Ampelgading", "kecamatan", "3507", "", -8.2400, 112.8700),
    "contoh:kec/dampit": ("Kec. Dampit", "kecamatan", "3507", "", -8.2110, 112.7490),
    "contoh:desa/kalirejo": ("Desa Kalirejo", "desa", "3507", "Kec. Lawang", -7.8330, 112.7000),
    "contoh:desa/sumberbrantas": ("Desa Sumberbrantas", "desa", "3579", "Kec. Bumiaji", -7.7580, 112.5310),
    "contoh:desa/bulukerto": ("Desa Bulukerto", "desa", "3579", "Kec. Bumiaji", -7.8200, 112.5300),
    "contoh:kec/bangil": ("Kec. Bangil", "kecamatan", "3514", "", -7.5990, 112.7800),
    "contoh:kec/beji": ("Kec. Beji", "kecamatan", "3514", "", -7.5980, 112.7130),
    "contoh:gunung/arjuno": ("Gunung Arjuno", "gunung", "3514", "Kec. Prigen", -7.7647, 112.5894),
    "contoh:desa/ngadisari": ("Desa Ngadisari", "desa", "3513", "Kec. Sukapura", -7.9290, 112.9540),
    "contoh:kec/sukapura": ("Kec. Sukapura", "kecamatan", "3513", "", -7.9060, 113.0340),
    "contoh:kec/puger": ("Kec. Puger", "kecamatan", "3509", "", -8.3670, 113.4670),
    "contoh:kec/panti": ("Kec. Panti", "kecamatan", "3509", "", -8.1500, 113.6170),
    "contoh:kec/porong": ("Kec. Porong", "kecamatan", "3515", "", -7.5370, 112.6830),
}
EV = [  # event_id, nama, jenis, status
    ("DE01", "Erupsi Gunung Semeru — Kab. Lumajang", "erupsi", "ya"),
    ("DE02", "Banjir Lahar Candipuro", "banjir", "tidak"),
    ("DE03", "Erupsi Gunung Semeru — Kab. Malang", "erupsi", "tidak"),
    ("DE04", "Tanah Longsor Dampit", "longsor", "tidak"),
    ("DE05", "Cuaca Ekstrem Lawang", "cuaca", "ya"),
    ("DE06", "Tanah Longsor Sumberbrantas", "longsor", "ya"),
    ("DE07", "Banjir Bumiaji", "banjir", "tidak"),
    ("DE08", "Angin Kencang Kota Batu", "cuaca", "tidak"),
    ("DE09", "Banjir Bangil (Januari)", "banjir", "ya"),
    ("DE10", "Banjir Bangil (Maret)", "banjir", "tidak"),
    ("DE11", "Kebakaran Lahan Gunung Arjuno", "karhutla", "tidak"),
    ("DE12", "Tanah Longsor Sukapura", "longsor", "tidak"),
    ("DE13", "Gempabumi Dirasakan di Jember", "gempa", "tidak"),
    ("DE14", "Banjir Bandang Panti", "banjir", "ya"),
    ("DE15", "Banjir Porong", "banjir", "tidak"),
]
# mention: (event, kode_kab, tanggal, [lokasi], tweet, jam)
MEN = [
    ("DE01", "3508", "2026-01-12", ["semeru", "supiturang"], "T01", "06:42"),
    ("DE01", "3508", "2026-01-12", ["supiturang"], "T02", "09:15"),
    ("DE01", "3508", "2026-01-14", ["semeru"], "T03", "17:20"),
    ("DE01", "3508", "2026-01-20", ["sumberwuluh"], "T04", "08:05"),
    ("DE01", "3508", "2026-01-27", ["supiturang"], "T05", "13:30"),
    ("DE02", "3508", "2026-02-03", ["sumberwuluh", "gladak-perak"], "T06", "16:10"),
    ("DE02", "3508", "2026-02-04", ["gladak-perak", "candipuro"], "T07", "07:55"),
    ("DE02", "3508", "2026-02-05", ["candipuro"], "T08", "10:40"),
    ("DE03", "3507", "2026-01-12", ["semeru", "ampelgading"], "T01", "06:42"),
    ("DE03", "3507", "2026-01-15", ["ampelgading"], "T09", "11:00"),
    ("DE04", "3507", "2026-02-10", ["dampit"], "T10", "05:50"),
    ("DE04", "3507", "2026-02-11", ["dampit"], "T11", "12:25"),
    ("DE05", "3507", "2026-03-02", ["kalirejo"], "T12", "15:45"),
    ("DE05", "3507", "2026-03-03", ["kab:3507"], "T13", "09:10"),
    ("DE06", "3579", "2026-01-22", ["sumberbrantas"], "T14", "20:05"),
    ("DE06", "3579", "2026-01-23", ["sumberbrantas"], "T14", "20:05"),
    ("DE07", "3579", "2026-02-17", ["sumberbrantas", "bulukerto"], "T15", "14:30"),
    ("DE08", "3579", "2026-03-09", ["sumberbrantas"], "T16", "16:50"),
    ("DE08", "3579", "2026-03-09", ["bulukerto"], "T17", "17:05"),
    ("DE09", "3514", "2026-01-08", ["bangil"], "T18", "04:30"),
    ("DE09", "3514", "2026-01-09", ["bangil", "beji"], "T19", "08:20"),
    ("DE09", "3514", "2026-01-10", ["bangil"], "T20", "10:00"),
    ("DE10", "3514", "2026-03-12", ["bangil"], "T21", "19:40"),
    ("DE10", "3514", "2026-03-13", ["bangil"], "T22", "07:15"),
    ("DE11", "3514", "2026-03-16", ["arjuno"], "T23", "13:05"),
    ("DE11", "3514", "2026-03-18", ["arjuno"], "T24", "09:35"),
    ("DE12", "3513", "2026-02-06", ["sukapura", "ngadisari"], "T25", "18:20"),
    ("DE13", "3509", "2026-02-20", ["puger"], "T26", "02:14"),
    ("DE13", "3509", "2026-02-20", ["kab:3509"], "T27", "02:30"),
    ("DE14", "3509", "2026-01-30", ["panti"], "T28", "22:10"),
    ("DE14", "3509", "2026-01-31", ["panti"], "T29", "07:45"),
    ("DE15", "3515", "2026-03-05", ["porong"], "T30", "06:30"),
    ("DE15", "3515", "2026-03-06", ["porong"], "T31", "08:00"),
]
TW = {
    "T01": "Gunung Semeru erupsi pagi ini, abu vulkanik terlihat dari Supiturang sampai Ampelgading. Warga diminta menjauhi aliran sungai.",
    "T02": "Sebagian warga Supiturang mulai mengungsi ke Kecamatan Candipuro, sekitar 120 jiwa. Masker sangat dibutuhkan.",
    "T03": "Kolom abu Semeru kembali naik sore ini, pengamatan dari pos pantau.",
    "T04": "Material erupsi menimbun 8 rumah di Desa Sumberwuluh. Petugas BPBD Lumajang sudah di lokasi.",
    "T05": "Posko pengungsian Semeru butuh tenda tambahan, masker dari BNPB sudah datang ke Supiturang.",
    "T06": "Banjir lahar dingin melintas Sumberwuluh menuju Jembatan Gladak Perak, warga jangan mendekat.",
    "T07": "Jembatan Gladak Perak putus diterjang lahar, akses Candipuro terganggu.",
    "T08": "Arus lalu lintas di Candipuro dialihkan setelah banjir lahar kemarin.",
    "T09": "Hujan abu tipis di Ampelgading, warga diimbau memakai masker.",
    "T10": "Longsor menutup jalan desa di Dampit setelah hujan deras semalam.",
    "T11": "Pembersihan material longsor Dampit masih berlangsung.",
    "T12": "Angin kencang di Kalirejo Lawang, 12 rumah dilaporkan rusak. Warga butuh terpal.",
    "T13": "Cuaca ekstrem melanda Kabupaten Malang, PMI turun membantu warga terdampak.",
    "T14": "Longsor di Sumberbrantas menutup jalan, dan pagi tadi longsor susulan terjadi di titik yang sama.",
    "T15": "Banjir di Bumiaji, air masuk ke permukiman Sumberbrantas dan Bulukerto.",
    "T16": "Angin kencang merobohkan pohon di Sumberbrantas.",
    "T17": "Angin kencang juga terasa di Bulukerto, beberapa atap rumah rusak.",
    "T18": "Banjir mulai masuk permukiman Bangil dini hari ini.",
    "T19": "Sekitar 350 rumah terendam di Bangil, banjir meluas ke Beji. Warga butuh air bersih.",
    "T20": "BPBD Pasuruan masih mengevakuasi warga Bangil yang terjebak banjir.",
    "T21": "Bangil banjir lagi malam ini setelah hujan deras.",
    "T22": "Sekitar 90 rumah terendam di Bangil akibat banjir kedua bulan ini.",
    "T23": "Kebakaran lahan di lereng Gunung Arjuno, asap terlihat dari Prigen. Relawan pemadam dibutuhkan.",
    "T24": "Tim Manggala Agni memadamkan api di Arjuno, sekitar 40 hektare lahan terbakar.",
    "T25": "Longsor di Sukapura menutup akses ke Ngadisari.",
    "T26": "Gempa terasa cukup kuat di Puger dini hari, warga berhamburan keluar rumah.",
    "T27": "Gempa dirasakan di Jember, pusat gempa di laut sekitar 90 km barat daya. 3 bangunan rusak ringan.",
    "T28": "Banjir bandang menerjang Panti malam ini, Basarnas menuju lokasi.",
    "T29": "Dua warga Panti meninggal akibat banjir bandang. Obat-obatan dibutuhkan di posko.",
    "T30": "Banjir merendam rumah warga di Porong.",
    "T31": "Genangan banjir di Porong belum surut pagi ini.",
}
# Mengikuti skema: AffectedObject.kelas (6 enum) + objek (opsional; di data nyata ada di log ekstraksi)
# + lokasi (atribut gazetteer_id, hanya bila tweet menautkan angka ke tempat secara eksplisit).
AO = [  # id, mention#, kelas, objek, status, jumlah, satuan, lokasi|None
    ("AO01", 2, "manusia", "warga", "mengungsi", 120, "jiwa", "supiturang"),
    ("AO02", 4, "rumah", "rumah", "tertimbun", 8, "unit", "sumberwuluh"),
    ("AO03", 7, "prasarana_vital", "jembatan", "putus", 1, "unit", "gladak-perak"),
    ("AO04", 13, "rumah", "rumah", "rusak", 12, "unit", None),  # kasus Kalirejo: tanpa atribusi lokasi
    ("AO05", 15, "prasarana_vital", "jalan", "tertutup", None, None, "sumberbrantas"),
    ("AO06", 21, "rumah", "rumah", "terendam", 350, "unit", "bangil"),
    ("AO07", 24, "rumah", "rumah", "terendam", 90, "unit", "bangil"),
    ("AO08", 26, "sosial_ekonomi", "lahan", "terbakar", 40, "hektare", "arjuno"),
    ("AO09", 29, "lainnya", "bangunan", "rusak ringan", 3, "unit", None),
    ("AO10", 31, "manusia", "warga", "meninggal", 2, "jiwa", "panti"),
    ("AO11", 32, "rumah", None, "terendam", None, None, "porong"),  # tanpa objek: label dari kelas + status
]
HN = [  # id, mention#, kategori (10 enum), item, status, lokasi|None
    ("HN01", 2, "kesehatan_obat", "masker", "demanded", "supiturang"),
    ("HN02", 5, "hunian_tenda", "tenda pengungsian", "demanded", "candipuro"),
    ("HN03", 5, "kesehatan_obat", "masker", "supplied", "supiturang"),
    ("HN04", 13, "hunian_tenda", "terpal", "demanded", None),
    ("HN05", 21, "air_bersih_sanitasi", "air bersih", "demanded", "bangil"),
    ("HN06", 25, "lainnya", "relawan pemadam", "demanded", "arjuno"),
    ("HN07", 31, "kesehatan_obat", "obat-obatan", "demanded", "panti"),
]
# HANDLES {aksi, sumber}: target = mention# (int) atau id kebutuhan/dampak; DEPLOYED_TO {aksi, sumber}: (lokasi, aksi, mention#)
ORG = [  # id, nama, wilayah, tingkat, handles[(target, aksi, mention# sumber)], deployed[(lok, aksi, mention#)], part_of
    ("ORG01", "BPBD Kabupaten Lumajang", "Kab. Lumajang", "kabupaten",
     [(2, "evakuasi warga", 2), (4, "pencarian korban", 4), ("HN03", "membagikan masker", 5)], [("supiturang", "membuka posko pengungsian", 2)], None),
    ("ORG02", "BNPB", "Indonesia", "nasional", [(5, "mengirim bantuan logistik", 5)], [("supiturang", "pemantauan", 5)], None),
    ("ORG03", "Basarnas Surabaya", "Jawa Timur", "provinsi", [(30, "pencarian dan penyelamatan", 30)], [("panti", "pencarian korban", 30)], None),
    ("ORG04", "BPBD Kabupaten Pasuruan", "Kab. Pasuruan", "kabupaten", [(22, "evakuasi warga", 22)], [("bangil", "evakuasi warga", 22)], None),
    ("ORG05", "Manggala Agni Daops Malang", "Jawa Timur", "provinsi", [(26, "pemadaman darat", 26)], [("arjuno", "pemadaman darat", 26)], "ORG06"),
    ("ORG06", "Kementerian Lingkungan Hidup dan Kehutanan", "Indonesia", "nasional", [], [], None),
    ("ORG07", "BPBD Kota Batu", "Kota Batu", "kabupaten", [(15, "pembersihan material longsor", 15)], [("sumberbrantas", "pembersihan material longsor", 15)], None),
    ("ORG08", "PMI Kabupaten Malang", "Kab. Malang", "kabupaten", [(14, "membantu warga terdampak", 14)], [], None),
]
EVAKUASI = [(2, "candipuro")]  # (mention#, lokasi tujuan)


def gid(short: str) -> str:
    return short if short.startswith("kab:") else next(g for g in LOK if g.split("/")[-1] == short)


def main() -> None:
    nodes = {k: [] for k in ("Tweet", "EventMention", "DisasterEvent", "Location", "AffectedObject",
                             "HumanitarianNeed", "Organization")}
    rels, gaz = [], {}
    for kode, nama in KAB.items():
        g = f"kab:{kode}"
        nodes["Location"].append({"gazetteer_id": g, "nama": nama, "admin_path": f"{P} > {nama}", "coordinates": None})
        gaz[g] = {"tingkat": "kabupaten", "kode_kab": kode}
    for g, (nama, tingkat, kode, kec, lat, lon) in LOK.items():
        path = " > ".join(x for x in (P, KAB[kode], kec, nama) if x)
        nodes["Location"].append({"gazetteer_id": g, "nama": nama, "admin_path": path,
                                  "coordinates": {"latitude": lat, "longitude": lon}})
        gaz[g] = {"tingkat": tingkat, "kode_kab": kode}
        rels.append({"type": "LOCATED_IN", "from": g, "to": f"kab:{kode}"})
    ev_dates: dict[str, list[str]] = {}
    tw_time: dict[str, str] = {}
    for i, (ev, kode, tgl, loks, tw, jam) in enumerate(MEN, 1):
        mid = f"EM{i:02d}"
        jenis = next(e[2] for e in EV if e[0] == ev)
        nodes["EventMention"].append({"mention_id": mid, "jenis": jenis, "kode_kab": kode, "tanggal_lokal": tgl})
        rels.append({"type": "CONSOLIDATED_INTO", "from": mid, "to": ev})
        rels.append({"type": "REPORTS", "from": tw, "to": mid})
        rels += [{"type": "MENTIONS", "from": mid, "to": gid(l)} for l in loks]
        ev_dates.setdefault(ev, []).append(tgl)
        tw_time.setdefault(tw, f"{tgl}T{jam}:00+07:00")
    for ev, nama, jenis, status in EV:
        d = sorted(ev_dates[ev])
        nodes["DisasterEvent"].append({"event_id": ev, "nama": nama, "jenis": jenis, "start_time": d[0],
                                       "end_time": d[-1], "status": status})
    for tw, text in TW.items():
        nodes["Tweet"].append({"tweet_id": tw, "upload": tw_time[tw], "text": text, "url": None})
    tw_of = {f"EM{i:02d}": m[4] for i, m in enumerate(MEN, 1)}
    for aid, m, kelas, objek, status, jml, sat, lok in AO:
        node = {"id": aid, "kelas": kelas, "status": status, "jumlah": jml, "satuan": sat, "lokasi": gid(lok) if lok else None}
        if objek:
            node["objek"] = objek
        nodes["AffectedObject"].append(node)
        rels.append({"type": "AFFECTED", "from": f"EM{m:02d}", "to": aid})
    for hid, m, kat, item, status, lok in HN:
        nodes["HumanitarianNeed"].append({"id": hid, "kategori": kat, "item": item, "status": status,
                                          "lokasi": gid(lok) if lok else None})
        rels.append({"type": "REQUIRES", "from": f"EM{m:02d}", "to": hid})
    for oid, nama, wil, tingkat, handles, deployed, part in ORG:
        nodes["Organization"].append({"id": oid, "nama_kanonik": nama, "wilayah": wil, "tingkat": tingkat})
        for target, aksi, sm in handles:
            to = f"EM{target:02d}" if isinstance(target, int) else target
            rels.append({"type": "HANDLES", "from": oid, "to": to, "props": {"aksi": aksi, "sumber": tw_of[f"EM{sm:02d}"]}})
        for l, aksi, sm in deployed:
            rels.append({"type": "DEPLOYED_TO", "from": oid, "to": gid(l), "props": {"aksi": aksi, "sumber": tw_of[f"EM{sm:02d}"]}})
        if part:
            rels.append({"type": "PART_OF", "from": oid, "to": part})
    rels += [{"type": "EVACUATED_TO", "from": f"EM{m:02d}", "to": gid(l)} for m, l in EVAKUASI]
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"label": "Data Contoh", "keterangan": "Data ilustratif untuk menguji dashboard; bukan pemantauan bencana nyata."}
    (OUT / "graf.json").write_text(json.dumps({"metadata": meta, "nodes": nodes, "relationships": rels},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "gazetteer.json").write_text(json.dumps(gaz, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: len(v) for k, v in nodes.items()}, "rel", len(rels))


if __name__ == "__main__":
    main()
