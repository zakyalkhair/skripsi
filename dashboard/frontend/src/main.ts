import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/map.css";
import "./styles/panel.css";
import "./styles/timeline.css";

import { api, isAbort, type Query } from "./api";
import { h } from "./dom";
import { rentang } from "./format";
import { JENIS, LABEL_PENDEK } from "./jenis";
import { buildLegend } from "./map/legend";
import { MapView } from "./map/map";
import { filterKey, Store, type State } from "./store";
import type { KabAgregat, KabKejadian, KabTitik, Wilayah } from "./types";
import { buildFilters } from "./ui/filters";
import { Panel } from "./ui/panel";
import { Timeline } from "./ui/timeline";

const store = new Store();
const q = (s: State): Query => ({ jenis: s.jenis, dari: s.dari, sampai: s.sampai });

let wil: Wilayah;
let agg: KabAgregat | null = null;
let kejadian: KabKejadian | null = null;
let titik: KabTitik | null = null;
let kabNames = new Map<string, Wilayah["kab"][number]>();
let markersShown = false;

// ------------------------------------------------------------------ kerangka
const app = document.getElementById("app")!;
const live = h("p", { class: "sr-only", "aria-live": "polite", id: "live" });
const badge = h("span", { class: "badge-contoh", tabindex: 0, role: "note" }, "Data Contoh");
const caption = h("p", { class: "hdr-sub" }, "Laporan kejadian bencana dari unggahan X berbahasa Indonesia");
const header = h("header", { class: "hdr" },
  h("div", { class: "hdr-brand" },
    h("span", { class: "logo", "aria-hidden": "true" }),
    h("div", {}, h("h1", { class: "hdr-title" }, "Peta Situasi Bencana"), caption)),
  h("div", { class: "hdr-meta" }, badge));

const filters = buildFilters(store, (kode) => goKab(kode));
const panel = new Panel({
  onKab: (k) => goKab(k),
  onTitik: (g) => store.set({ lokasi: g }),
  onSorot: (e) => store.set({ sorot: e }),
  onBack: () => store.set({ lokasi: null }),
  onNational: () => goKab(null),
  onReset: () => store.set({ jenis: new Set(JENIS), dari: null, sampai: null }),
  onAllDates: () => store.set({ dari: null, sampai: null }),
  onAllJenis: () => store.set({ jenis: new Set(JENIS) }),
});
const timeline = new Timeline((dari, sampai) => store.set({ dari, sampai }));

const crumbs = h("nav", { class: "crumbs", "aria-label": "Posisi geografis" });
const backBtn = h("button", { type: "button", class: "map-back", hidden: true, onclick: () => goKab(null) },
  h("span", { "aria-hidden": "true" }, "←"), "Kembali ke peta nasional");
const mapStatus = h("div", { class: "map-status", role: "status", hidden: true }, h("span", { class: "spin", "aria-hidden": "true" }), "Memuat…");
const mapEmpty = h("div", { class: "map-empty", hidden: true });
const legend = buildLegend();
const mapEl = h("div", { class: "map", id: "map", role: "application", "aria-label": "Peta kab/kota. Gunakan daftar di panel atau kolom wilayah untuk navigasi dengan papan ketik." });
const fullBtn = h("button", { type: "button", class: "map-full", title: "Tampilkan seluruh Indonesia (bingkai awal mengikuti cakupan data)",
  onclick: () => mapView.showIndonesia() }, "Seluruh Indonesia");
const mapWrap = h("div", { class: "mapwrap" }, mapEl, h("div", { class: "map-top" }, crumbs, backBtn, fullBtn), mapStatus, mapEmpty, legend.el);

app.append(header, filters.el, h("main", { class: "workspace" },
  h("div", { class: "stage" }, mapWrap, timeline.el), panel.el), live);
app.removeAttribute("aria-busy");

const mapView = new MapView(mapEl, {
  onKab: (k) => goKab(k),
  onTitik: (g) => store.set({ lokasi: g }),
  onBackground: () => { if (store.state.sorot) store.set({ sorot: null }); },
});
const fitPad = () => {
  const mobile = window.innerWidth < 700;
  mapView.setPadding([mobile ? 12 : 24, mobile ? 64 : 72], mobile ? [12, 12] : [24, legend.el.offsetHeight + 28]);
};
fitPad();
new ResizeObserver(() => { mapView.invalidate(); fitPad(); }).observe(mapEl);

// ------------------------------------------------------------------ navigasi
function goKab(kode: string | null): void {
  if (kode === store.state.kab && !store.state.lokasi) return;
  store.set({ kab: kode, lokasi: null, sorot: null });
}

function announce(t: string): void { live.textContent = ""; window.setTimeout(() => (live.textContent = t), 30); }

function renderCrumbs(): void {
  const s = store.state;
  const items: HTMLElement[] = [h("button", { type: "button", class: "crumb", onclick: () => goKab(null), "aria-current": !s.kab ? "page" : null }, "Indonesia")];
  if (s.kab) {
    const k = kabNames.get(s.kab);
    items.push(h("span", { class: "crumb crumb--static" }, k?.provinsi ?? ""));
    items.push(h("button", { type: "button", class: "crumb", "aria-current": !s.lokasi ? "page" : null, onclick: () => store.set({ lokasi: null }) }, k?.nama ?? s.kab));
  }
  if (s.lokasi && titik) {
    const t = titik.titik.find((x) => x.gazetteer_id === s.lokasi);
    items.push(h("span", { class: "crumb crumb--leaf", "aria-current": "page" }, t?.nama ?? "Lokasi"));
  }
  crumbs.replaceChildren(h("ol", {}, ...items.map((i) => h("li", {}, i))));
  backBtn.hidden = !s.kab;
  fullBtn.hidden = !!s.kab;
}

function filterText(s: State): string {
  const j = s.jenis.size === JENIS.length ? "Semua jenis" : s.jenis.size === 0 ? "Tidak ada jenis" : [...s.jenis].map((x) => LABEL_PENDEK[x]).join(", ");
  const d = s.dari || s.sampai ? rentang(s.dari ?? wil.dataset.rentang.awal, s.sampai ?? wil.dataset.rentang.akhir) : "seluruh periode";
  return `${j} · ${d}`;
}

const emptyCtx = () => ({ jenisKosong: store.state.jenis.size === 0, adaTanggal: !!(store.state.dari || store.state.sampai) });

// ------------------------------------------------------------------ pemuatan data
let busy = 0;
function loading<T>(p: Promise<T>): Promise<T> {
  busy++; mapStatus.hidden = false;
  return p.finally(() => { if (--busy === 0) mapStatus.hidden = true; });
}

async function loadAgregat(): Promise<void> {
  const s = store.state;
  try {
    agg = await loading(api.agregat(q(s)));
  } catch (e) { if (!isAbort(e)) showError(e); return; }
  const cakupan = new Set(wil.kab.filter((k) => k.ada_data).map((k) => k.kode_kab));
  mapView.setCounts(new Map(agg.kab.map((r) => [r.kode_kab, r.jumlah_kejadian])), cakupan);
  legend.update(`${filterText(s)}. Kejadian dihitung bila periodenya beririsan dengan rentang tanggal.`, !!s.kab);
  const empty = agg.ringkasan.jumlah_kejadian === 0;
  mapEmpty.hidden = !empty;
  if (empty) mapEmpty.replaceChildren(panel.empty(emptyCtx()));
  if (store.view === "nasional") panel.nasional(agg, wil, filterText(s), emptyCtx());
  else if (store.view === "kab" && kejadian) renderKab();
}

async function loadHistogram(): Promise<void> {
  const s = store.state;
  try {
    const d = await api.histogram(q(s), s.kab);
    timeline.setData(d, s.kab ? kabNames.get(s.kab)?.nama ?? s.kab : "Seluruh wilayah");
  } catch (e) { if (!isAbort(e)) showError(e); }
}

function renderKab(): void {
  const s = store.state;
  if (!kejadian || store.view !== "kab") return;
  const row = agg?.kab.find((r) => r.kode_kab === s.kab);
  panel.kab(kejadian, titik, row ? row.jumlah_tweet : 0, kabNames.get(s.kab!)?.provinsi ?? "", s.sorot, emptyCtx());
}

async function loadKab(fresh: boolean): Promise<void> {
  const s = store.state;
  const kode = s.kab!;
  if (fresh) panel.skeleton(`kab:${kode}`);
  const flight = fresh ? mapView.focusKab(kode) : Promise.resolve(true);
  let k: KabKejadian, t: KabTitik;
  try {
    [k, t] = await loading(Promise.all([api.kejadian(kode, q(s)), api.titik(kode, q(s))]));
  } catch (e) { if (!isAbort(e)) showError(e); return; }
  if (store.state.kab !== kode) return;
  kejadian = k; titik = t;
  // sorotan yang tidak lagi ada di hasil filter dihapus dengan pemberitahuan
  if (store.state.sorot && !k.kejadian.some((x) => x.event_id === store.state.sorot)) {
    store.set({ sorot: null });
    announce("Kejadian yang disorot tidak sesuai filter baru; sorotan dihapus.");
  }
  if (store.view === "kab") renderKab();
  const ok = await flight;
  if (!ok || store.state.kab !== kode) return;
  mapView.setTitik(t.titik, fresh || !markersShown);
  markersShown = true;
  const sor = store.state.sorot ? k.kejadian.find((x) => x.event_id === store.state.sorot) : null;
  mapView.setSorot(sor ? sor.lokasi_ids : null);
  mapView.setSelectedTitik(store.state.lokasi);
  legend.update(`${filterText(store.state)}. Kejadian dihitung bila periodenya beririsan dengan rentang tanggal.`, true);
  if (fresh) announce(`${k.nama}: ${k.kejadian.length} kejadian, ${t.titik.length} lokasi.`);
}

async function loadLokasi(): Promise<void> {
  const s = store.state;
  const gid = s.lokasi!;
  panel.skeleton(`lokasi:${gid}`);
  try {
    const r = await loading(api.ringkasan(gid, q(s)));
    if (store.state.lokasi !== gid) return;
    panel.lokasi(r, s.kab ? kabNames.get(s.kab)?.nama ?? null : null, s.kab);
    renderCrumbs();
    announce(`${r.lokasi.nama}: ${r.jumlah_laporan} laporan dari ${r.jumlah_tweet} tweet.`);
  } catch (e) { if (!isAbort(e)) showError(e); }
}

function showError(e: unknown): void {
  console.warn(e);
  panel.error(e instanceof Error ? e.message : "Kesalahan tidak diketahui", () => refresh(true));
}

function refresh(all: boolean): void {
  const s = store.state;
  void loadAgregat();
  void loadHistogram();
  if (s.kab && (all || store.view !== "nasional")) void loadKab(false);
  if (s.lokasi) void loadLokasi();
}

// ------------------------------------------------------------------ reaksi state
store.on((s, prev) => {
  filters.sync();
  timeline.setRange(s.dari, s.sampai);
  const fChanged = filterKey(s) !== filterKey(prev);
  const kabChanged = s.kab !== prev.kab;
  const lokChanged = s.lokasi !== prev.lokasi;
  renderCrumbs();
  document.body.dataset.view = store.view;

  if (kabChanged) {
    kejadian = null; titik = null; markersShown = false;
    void loadHistogram();
    if (s.kab) void loadKab(true);
    else {
      void mapView.national();
      legend.update(`${filterText(s)}. Kejadian dihitung bila periodenya beririsan dengan rentang tanggal.`, false);
      if (agg) panel.nasional(agg, wil, filterText(s), emptyCtx());
      announce("Peta nasional");
    }
  }
  if (fChanged) {
    void loadAgregat();
    if (!kabChanged) void loadHistogram();
    if (s.kab && !kabChanged) void loadKab(false);
    if (s.lokasi && !lokChanged) void loadLokasi();
  }
  if (lokChanged) {
    mapView.setSelectedTitik(s.lokasi, !!s.lokasi && !mapView.titikVisible(s.lokasi));
    if (s.lokasi) void loadLokasi();
    else if (s.kab && !kabChanged) renderKab();
  }
  if (s.sorot !== prev.sorot) {
    panel.setSorot(s.sorot);
    const ev = s.sorot ? kejadian?.kejadian.find((x) => x.event_id === s.sorot) : null;
    mapView.setSorot(ev ? ev.lokasi_ids : null);
  }
});

window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || (e.target as HTMLElement).closest("input")) return;
  const s = store.state;
  if (s.sorot) store.set({ sorot: null });
  else if (s.lokasi) store.set({ lokasi: null });
});

// ------------------------------------------------------------------ mulai
async function boot(): Promise<void> {
  panel.skeleton("boot");
  try {
    const [w, kab, prov] = await Promise.all([api.wilayah(), api.geo("kabkota"), api.geo("provinsi")]);
    wil = w;
    kabNames = new Map(w.kab.map((k) => [k.kode_kab, k]));
    filters.setWilayah(w);
    badge.hidden = !w.dataset.contoh;
    badge.title = w.dataset.keterangan ?? "";
    if (w.dataset.contoh) caption.textContent = "Data contoh ilustratif — bukan pemantauan bencana nyata";
    mapView.setGeo(kab, prov);
    fitPad();
    mapView.setHome(w.kab.filter((k) => k.ada_data).map((k) => k.kode_kab));
    timeline.setDomain(w.dataset.rentang.awal, w.dataset.rentang.akhir);
    timeline.setRange(null, null);
    renderCrumbs();
    filters.sync();
    document.body.dataset.view = "nasional";
    await Promise.all([loadAgregat(), loadHistogram()]);
    document.body.dataset.ready = "true";
  } catch (e) {
    panel.error(e instanceof Error ? e.message : "Gagal memuat", () => location.reload());
  }
}
void boot();
