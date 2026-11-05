import { JENIS } from "./jenis";
import type { State, Store } from "./store";
import type { Jenis } from "./types";

/**
 * Status analisis <-> URL (dapat dibagikan). Parameter:
 *   prov=35  kab=3507  lokasi=<gazetteer_id>  jenis=banjir,cuaca (kosong = tidak ada; tidak ada = semua)
 *   dari=YYYY-MM-DD  sampai=YYYY-MM-DD  kejadian=<event_id>
 * Navigasi geografis menambah entri riwayat (Back/Forward); perubahan filter mengganti entri aktif.
 * Status UI sementara dan percakapan tidak pernah masuk URL.
 */
export type UrlState = Pick<State, "jenis" | "dari" | "sampai" | "prov" | "kab" | "lokasi" | "sorot">;

const ISO = /^\d{4}-\d{2}-\d{2}$/;

export interface Parsed { state: Partial<UrlState>; invalid: string[] }

export function parseUrl(search: string): Parsed {
  const p = new URLSearchParams(search);
  const state: Partial<UrlState> = {}, invalid: string[] = [];
  if (p.has("jenis")) {
    const raw = (p.get("jenis") ?? "").split(",").map((x) => x.trim()).filter(Boolean);
    const ok = raw.filter((x): x is Jenis => (JENIS as string[]).includes(x));
    if (ok.length !== raw.length) invalid.push("jenis");
    state.jenis = new Set(ok);
  }
  for (const k of ["dari", "sampai"] as const) {
    const v = p.get(k);
    if (v === null || v === "") continue;
    if (ISO.test(v) && !Number.isNaN(Date.parse(v))) state[k] = v;
    else invalid.push(k);
  }
  if (state.dari && state.sampai && state.dari > state.sampai) { invalid.push("rentang"); delete state.dari; delete state.sampai; }
  const prov = p.get("prov"), kab = p.get("kab");
  if (prov) /^\d{2}$/.test(prov) ? (state.prov = prov) : invalid.push("prov");
  if (kab) /^\d{4}$/.test(kab) ? (state.kab = kab) : invalid.push("kab");
  const lok = p.get("lokasi"), ev = p.get("kejadian");
  if (lok) lok.length <= 200 ? (state.lokasi = lok) : invalid.push("lokasi");
  if (ev) /^[\w.:-]{1,80}$/.test(ev) ? (state.sorot = ev) : invalid.push("kejadian");
  return { state, invalid };
}

export function toSearch(s: UrlState): string {
  const p = new URLSearchParams();
  if (s.prov && !s.kab) p.set("prov", s.prov);
  if (s.kab) p.set("kab", s.kab);
  if (s.lokasi) p.set("lokasi", s.lokasi);
  if (s.jenis.size < JENIS.length) p.set("jenis", JENIS.filter((j) => s.jenis.has(j)).join(","));
  if (s.dari) p.set("dari", s.dari);
  if (s.sampai) p.set("sampai", s.sampai);
  if (s.sorot) p.set("kejadian", s.sorot);
  const q = p.toString();
  return q ? `?${q}` : "";
}

const geoKey = (s: UrlState) => `${s.prov ?? ""}|${s.kab ?? ""}|${s.lokasi ?? ""}`;

/** Sinkronisasi dua arah tanpa loop: perubahan dari popstate ditandai agar tidak ditulis balik. */
export class UrlSync {
  private applying = false;
  private started = false;
  private forceReplace = false;

  constructor(private store: Store, private onPop: (s: Partial<UrlState>, invalid: string[]) => void) {
    window.addEventListener("popstate", () => {
      if (!this.started) return;
      const { state, invalid } = parseUrl(location.search);
      this.applying = true;
      try { this.onPop(state, invalid); } finally { this.applying = false; }
    });
    store.on((s, prev) => {
      if (!this.started || this.applying) return;
      const search = toSearch(s);
      if (search === location.search) return;
      const url = `${location.pathname}${search}`;
      if (geoKey(s) !== geoKey(prev) && !this.forceReplace) history.pushState(null, "", url);
      else history.replaceState(null, "", url);
    });
  }

  /** Mulai menulis URL setelah status awal dari tautan dipulihkan (URL dinormalkan tanpa entri riwayat baru). */
  start(): void { this.started = true; history.replaceState(null, "", `${location.pathname}${toSearch(this.store.state)}`); }

  /** Jalankan perubahan state yang mengoreksi tautan (mis. parameter tidak valid) tanpa menambah entri riwayat. */
  replace(fn: () => void): void {
    this.forceReplace = true;
    try { fn(); } finally { this.forceReplace = false; }
  }

  shareUrl(): string { return `${location.origin}${location.pathname}${toSearch(this.store.state)}`; }
}
