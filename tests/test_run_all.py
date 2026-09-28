import importlib.util

import pandas as pd

from modul1.__main__ import main
from modul1.io_utils import PROJECT_ROOT, load_config, read_parquet, write_jsonl


def _generator():
    spec = importlib.util.spec_from_file_location("gen", PROJECT_ROOT / "scripts" / "buat_data_tiruan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_all_data_tiruan_tidak_ada_baris_hilang(tmp_path):
    cfg = load_config(None, tmp_path)
    rows = _generator().generate(cfg, n_per_event=60, seed=1)
    write_jsonl(cfg.paths.raw_jsonl, rows)
    assert main(["--workdir", str(tmp_path), "run-all", "--skip-fetch"]) == 0

    final = read_parquet(cfg.paths.final)
    ready = read_parquet(cfg.paths.input_1_4)
    n_unique = len({str(r["id_str"]) for r in rows})
    assert len(final) == n_unique and final["tweet_id"].is_unique
    assert final["tweet_id"].map(type).eq(str).all()
    # setiap baris punya alasan atau lolos sebagai wakil
    assert (final["drop_reason"].notna() | final["is_representatif"]).all()
    assert len(ready) == int(final["is_representatif"].sum())
    # setiap anggota cluster tercatat di member_tweet_ids wakilnya
    members = {m for lst in ready["member_tweet_ids"] for m in lst}
    assert members == set(final.loc[final["cluster_id"].notna(), "tweet_id"])

    alur = pd.read_csv(cfg.paths.alur_data).set_index("tahap")
    assert list(alur.index) == ["hasil crawl", "saring dasar", "preprocessing", "dedup", "Siap ke 1.4"]
    assert alur.loc["saring dasar", "keluar"] == alur.loc["preprocessing", "masuk"]
    assert alur.loc["preprocessing", "keluar"] == alur.loc["dedup", "masuk"]
    assert alur.loc["Siap ke 1.4", "masuk"] == len(ready)
    for t in ["saring dasar", "preprocessing", "dedup"]:
        assert alur.loc[t, "masuk"] - alur.loc[t, "keluar"] == alur.loc[t, "dibuang"]
