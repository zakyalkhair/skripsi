from datetime import date

from modul1.crawl import build_queries, load_kejadian
from modul1.io_utils import PROJECT_ROOT


def test_kejadian_nasional_tanpa_wilayah_dan_jendela_mingguan(cfg):
    cfg.crawl.pecah_jendela_hari = 7
    ks = load_kejadian(PROJECT_ROOT / "config" / "kejadian.csv", only_pilot=True)
    assert len(ks) == 9 and all(not k.alias_wilayah for k in ks)
    qs = build_queries([k for k in ks if k.jenis == "tsunami"], cfg)
    assert all("(" not in q.text for q in qs)              # tanpa (alias OR ...)
    assert qs[0].since == date(2026, 1, 1)
    assert max(q.until for q in qs) == date(2026, 10, 5)    # until eksklusif
    assert all((q.until - q.since).days <= 7 for q in qs)
    assert len(qs) == 40                                    # 277 hari / 7 = 40 jendela x 1 kata kunci
