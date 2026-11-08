import os, re
import pytest
from modul3 import cq, muat, graf

DATA = "dev_2025/data/modul3"


def test_cq_lengkap_24_dan_parameter_konsisten():
    assert [c[0] for c in cq.CQ] == list(range(1, 25))
    for no, kel, tanya, par, cy in cq.CQ:
        dipakai = set(re.findall(r"\$(\w+)", cy))
        assert dipakai == set(par), (no, dipakai, par)
        assert cy.count("(") == cy.count(")") and cy.count("[") == cy.count("]") and cy.count("{") == cy.count("}"), no
        for p in par: assert p in cq.KANDIDAT, (no, p)


def test_label_dan_relasi_cq_ada_di_loader():
    muat_teks = " ".join(c for _, c in muat.LANGKAH)
    for no, *_, cy in cq.CQ:
        for rel in re.findall(r"\[(?:\w+:)?([A-Z_]+(?:\|[A-Z_]+)*)", cy):
            for r in rel.split("|"):
                assert r in muat_teks or r in ("PART_OF",), (no, r)
        for lab in re.findall(r"\(\w*:(\w+)", cy):
            assert lab in muat_teks or lab in ("Location",), (no, lab)


def test_loader_langkah_punya_baris_graf():
    for kunci, _ in muat.LANGKAH:
        assert isinstance(kunci, str)


@pytest.mark.skipif(not os.path.exists(DATA + "/disaster_event.csv"), reason="jalankan python -m modul3 proses dulu")
def test_graf_dari_sampel_utuh():
    g = graf.bangun(DATA)
    assert {l["kode_kab"] for l in g["mentions"] if l["kode_kab"]}
    ids = {m["mention_id"] for m in g["mentions"]}
    assert all(c["mention_id"] in ids for c in g["consolidated"])
    assert all(a["mention_id"] in ids for a in g["affected"])
    gids = {l["gazetteer_id"] for l in g["locations"]}
    assert all(p["anak"] in gids and p["induk"] in gids for p in g["part_of"])
    assert all(x["gazetteer_id"] in gids for x in g["located_in"])
    assert {k for k in muat_kunci()} <= set(g)


def muat_kunci(): return [k for k, _ in muat.LANGKAH]
