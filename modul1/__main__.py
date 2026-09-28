"""CLI Modul 1: python -m modul1 {crawl|preprocess|dedup|calib-sample|calib-report|run-all|
filter|filter-finalize|filter-bandingkan}."""

from __future__ import annotations

import argparse
import sys

from . import calib, crawl, dedup, preprocess
from .io_utils import load_config


def _events(s: str | None) -> list[str] | None:
    return [e for e in s.split(",") if e.strip()] if s else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m modul1", description=__doc__)
    ap.add_argument("--config", default=None, help="path config.yaml (default: config.yaml di root proyek)")
    ap.add_argument("--workdir", default=None,
                    help="folder dasar untuk data/, logs/, reports/ (default: folder config)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_crawl_args(p):
        p.add_argument("--events", default=None, help="batasi event_id, mis. GP07,ER03")
        p.add_argument("--skip-fetch", action="store_true",
                       help="jangan crawl; bangun ulang crawled.parquet dari raw.jsonl yang ada")
        p.add_argument("--pause", action="store_true", help="tanya konfirmasi setelah tiap kejadian")

    add_crawl_args(sub.add_parser("crawl", help="1.1 crawling + anonimisasi + saring dasar"))
    sub.add_parser("preprocess", help="1.2 preprocessing")
    sub.add_parser("dedup", help="1.3 deduplikasi + keluaran akhir")
    sub.add_parser("calib-sample", help="ekspor sampel pasangan untuk kalibrasi ambang")
    p_rep = sub.add_parser("calib-report", help="hitung presisi per ambang dari file kalibrasi terisi")
    p_rep.add_argument("--file", default=None, help="file kalibrasi terisi (default: path di config)")
    add_crawl_args(sub.add_parser("run-all", help="1.1 -> 1.2 -> 1.3"))

    def add_profil_arg(p):
        p.add_argument("--profil", default=None,
                       help="profil penyedia LLM dari profil_llm di config (mis. ollama); keluaran -> *_<profil>")

    p_f = sub.add_parser("filter", help="1.4 filter informatif (lanjut dari yang belum berlabel)")
    p_f.add_argument("--limit", type=int, default=None, help="kirim sampel acak N tweet saja (uji coba)")
    add_profil_arg(p_f)
    add_profil_arg(sub.add_parser("filter-finalize",
                                  help="1.4 tulis ulang keluaran dari label yang ada (tanpa API)"))
    p_b = sub.add_parser("filter-bandingkan", help="1.4 kesepakatan label dua model (persen setuju, kappa)")
    p_b.add_argument("--a", required=True, help="nilai kolom model penilai A, mis. manual-claude-code")
    p_b.add_argument("--b", required=True, help="nilai kolom model penilai B, mis. gpt-oss:20b")

    args = ap.parse_args(argv)
    try:
        return _dispatch(args)
    except (FileExistsError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"GALAT: {e}", file=sys.stderr)
        return 1


def _dispatch(args) -> int:
    cfg = load_config(args.config, args.workdir)

    if args.cmd == "crawl":
        crawl.run(cfg, _events(args.events), args.skip_fetch, args.pause)
    elif args.cmd == "preprocess":
        preprocess.run(cfg)
    elif args.cmd == "dedup":
        dedup.run(cfg)
    elif args.cmd == "calib-sample":
        calib.run_sample(cfg)
    elif args.cmd == "calib-report":
        calib.run_report(cfg, args.file)
    elif args.cmd == "run-all":
        crawl.run(cfg, _events(args.events), args.skip_fetch, args.pause)
        preprocess.run(cfg)
        dedup.run(cfg)
    elif args.cmd == "filter":
        from . import filter_llm
        from .io_utils import apply_profil, setup_logger

        apply_profil(cfg, args.profil)
        log = setup_logger("filter", cfg.paths.logs_dir)
        filter_llm.run(cfg, filter_llm.make_client(cfg, log), args.limit, log)
    elif args.cmd == "filter-finalize":
        from . import filter_llm
        from .io_utils import apply_profil

        filter_llm.finalize(apply_profil(cfg, args.profil))
    elif args.cmd == "filter-bandingkan":
        from . import filter_llm

        filter_llm.compare(cfg, args.a, args.b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
